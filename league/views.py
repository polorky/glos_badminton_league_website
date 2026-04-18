from django.shortcuts import redirect
from django.db.models import Q
from django.core.mail import send_mail
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.exceptions import ObjectDoesNotExist

from .models import *
from .forms import *
from .utilities import verify_away_players, download_fixtures, correct_duplicate_player, get_performances, get_fixture_stats, get_player_stats, parse_fixtures
from .email import email_notification, email_admin, get_all_club_contacts
import league.constants as constants

import urllib
import pandas as pd

##############################################################################################################################################
##### Main website page views #####
##############################################################################################################################################

class GenericViewMixin:
    user = None
    admin = None
    type_dict = {'X':'Mixed','L':'Ladies','M':'Mens'}

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        path = self.request.path.strip('/').split('/')
        context['active_tab'] = path[0] if path[0] else 'home'

        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
            admin = None

        if user:
            try:
                admin = Administrator.objects.get(user=user)
            except ObjectDoesNotExist:
                try:
                    admin = Member.objects.get(user=user)
                except ObjectDoesNotExist:
                    admin = None

        context.update({
            'current_season': Season.objects.get(current=True),
            'user': user,
            'admin': admin,
            })

        return context

# Basic Views
class HomeView(GenericViewMixin, TemplateView):
    template_name = "league/home.html"
    active_tab = 'home'

class JuniorsView(GenericViewMixin, TemplateView):
    template_name = "league/juniors.html"
    active_tab = 'juniors'

class HelpView(GenericViewMixin, TemplateView):
    template_name = "league/help.html"
    active_tab = 'help'

# Other Views
class DivisionsView(GenericViewMixin, TemplateView):
    template_name = "league/divisions.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        pagename = self.kwargs.get('pagename','')
        season = self.kwargs.get('season','')
        all_divs = Division.objects.all().order_by("number")

        if pagename == 'home':

            context.update({
                'status': 'home',
                **{f"{'old_' if not a else ''}{t.lower()}_divs":
                   [d for d in all_divs if d.type == t and d.active == a]
                   for t in ["Mixed", "Ladies", "Mens"] for a in [True, False]}
            })

        else:

            try:
                division = Division.objects.get(number=pagename[1:],type=self.type_dict[pagename[0]])
            except ObjectDoesNotExist:
                return {'status':'doesnotexist'}

            # current season or no specific season requested get current table
            if season == '' or season == context['current_season'].year:
                table = division.get_table()
            # Else work out table for requested season and override current_season
            else:
                context['current_season'] = Season.objects.get(year=season)
                table = division.get_table(season=context['current_season'])

            # Get fixtures and if method is post just return these
            fixtures = Fixture.objects.filter(season=context['current_season']).filter(division=division.id).order_by("date_time")

            # Work out previous/next season/division for links
            prev_season, next_season = context['current_season'].get_adj_seasons()
            prev_div = Division.objects.filter(number=division.number - 1, type=division.type)
            next_div = Division.objects.filter(number=division.number + 1, type=division.type)
            fix_list = [(fix,fix.updateable(context['user'])) for fix in fixtures]

            # If no fixtures found and not current season, division did not exist in requested season
            exist = bool(fixtures) or division.active

            # If concessions exist a note will be added next to table
            concessions = any(fix.status in ["Conceded (H)", "Conceded (A)"] for fix in fixtures)

            context.update({
                'status': 'view',
                'division': division,
                'fixtures': fix_list,
                'table': table,
                'concessions': concessions,
                'prev_season': prev_season,
                'next_season': next_season,
                'prev_div': prev_div,
                'next_div': next_div,
                'exist': exist,
            })

        return context

    def post(self, request, **kwargs):

        context = super().get_context_data(**kwargs)
        pagename = kwargs.get('pagename','')

        division = Division.objects.get(number=pagename[1:],type=self.type_dict[pagename[0]])
        fixtures = Fixture.objects.filter(season=context['current_season']).filter(division=division.id).order_by("date_time")

        if fixtures:
            return download_fixtures(fixtures)

class FixturesView(GenericViewMixin, TemplateView):
    template_name = "league/fixtures.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        pagename = self.kwargs.get('pagename','')
        fixtures = Fixture.objects.filter(season=context['current_season']).order_by('date_time')

        # If home page requested, return all fixtures
        if pagename == 'home':

            context.update({
                'pageview': 'home',
                'fixtures': [(fix,fix.updateable(context['user'])) for fix in fixtures],
            })

        # Otherwise return requested fixture for viewing
        else:

            # Check fixture exists
            try:
                fixture = Fixture.objects.get(id=pagename)
            except ObjectDoesNotExist:
                return {'pageview':'doesnotexist'}

            # Get players in user is club admin
            players = []

            if context['admin'] and context['admin'].club == fixture.home_team.club:
                players += fixture.get_players(side='home')
            if context['admin'] and context['admin'].club == fixture.away_team.club:
                players += fixture.get_players(side='away')

            # Get games for played matches
            if fixture.status == "Played" and fixture.game_results:
                batched_games = fixture.get_scores()
            else:
                batched_games = None

            # Work out number of rubbers expected per game
            if fixture.division.type == "Mixed" and fixture.season.mixed_scoring == "point per game":
                rubber_number = 3
            else:
                rubber_number = 2

            context.update({
                'pageview': 'view',
                'fixture': fixture,
                'game_results': batched_games,
                'players': players,
                'source': self.kwargs.get('source',''),
                'rubber_number': rubber_number,
            })

        return context

    def post(self, request, **kwargs):

        context = super().get_context_data(**kwargs)

        fixtures = Fixture.objects.filter(season=context['current_season']).order_by('date_time')

        return download_fixtures(fixtures)

@method_decorator(login_required, name='dispatch')
class FixUpdateView(GenericViewMixin, TemplateView):
    template_name = "league/fixtures_update.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        pagename = self.kwargs.get('pagename','')

        # Get relevant fixture
        fixture = Fixture.objects.get(id=self.kwargs['fixid'])
        context.update({'fixture': fixture})

        if pagename == 'submit':

            # Instantiate result forms
            context = self.setup_result_forms(context, fixture)

        elif pagename == 'reschedule':

            # Instantiate reschedule form
            context.update({'rform':RescheduleForm(None, instance=fixture)})

        else:

            # Default status is 'update' - different pages required where a rearrangement has been proposed
            # or the fixture is not updateable by the user
            if fixture.status == "Proposed":
                context['pagename'] = 'proposed'

            elif not fixture.updateable(context['user']):
                context['pagename'] = 'unupdateable'

        return context

    def post(self, request, **kwargs):

        context = self.get_context_data(**kwargs)

        pagename = self.kwargs.get('pagename','')

        # Get relevant fixture
        fixid = self.kwargs['fixid']
        fixture = Fixture.objects.get(id=fixid)

        # Check for basic statuses
        status_dict = {"confirmed":"Rearranged", "rejected":"Postponed", "postponed":"Postponed"}
        if pagename in status_dict:
            fixture.status = status_dict[pagename]
            fixture.save()
            email_notification(pagename, fixture)

        # Proposed reschedule date and location by home team
        elif pagename == "rescheduled":

            # Instantiate reschedule form
            rform = RescheduleForm(self.request.POST, instance=fixture)
            temp_date = fixture.date_time

            if rform.is_valid():
                if not fixture.old_date_time:
                    fixture.old_date_time = temp_date
                rform.save()
                fixture.status = 'Proposed'
                fixture.save()
                email_notification('reschedule', fixture)

        # Match conceded
        elif pagename == "concededhome" or pagename == "concededaway":
            if fixture.division.type == "Mixed":
                penalty_value = constants.PENALTY_MIXED_CONCEDED
            else:
                penalty_value = constants.PENALTY_LEVEL_CONCEDED
            if pagename == "concededhome":
                fixture.status = 'Conceded (H)'
                team=fixture.home_team
            else:
                fixture.status = 'Conceded (A)'
                team=fixture.away_team
            fixture.save()
            p = Penalty(season=fixture.season,
                        team=team,
                        penalty_value=penalty_value,
                        penalty_type='Match Conceded',
                        fixture=fixture)
            p.save()
            email_notification(pagename, fixture)

        # Result submitted by home team
        elif pagename == "submit":

            # Get relevant results form for fixture type
            if fixture.division.type == "Mixed":
                resform = MixedFixtureForm(self.request.POST, instance=fixture)
                resformset = MixedScoreFormSet(self.request.POST)
            else:
                resform = LevelFixtureForm(self.request.POST, instance=fixture)
                resformset = LevelScoreFormSet(self.request.POST)

            if resform.is_valid() and resformset.is_valid():

                # Find matches for away players or create new ones
                found_players = resformset.cleaned_data['found_players']
                verify_away_players(fixture, found_players)
                # Change fixture status
                fixture.status = 'Played'
                # Bundle up game results
                game_results = [
                    (f'{form.cleaned_data.get("forfeit")},{form.cleaned_data.get("forfeit")}' if form.cleaned_data.get("forfeit") else f"{form.cleaned_data.get('home_score')},{form.cleaned_data.get('away_score')}")
                    for form in resformset if form.cleaned_data
                    ]
                fixture.game_results = ','.join(game_results)
                # Save form and fixture data
                resform.save()
                fixture.save()
                # Check for illegal players and apply any penalties
                if fixture.season.current:
                    fixture.check_player_eligibility()
                    #fixture.check_nomination_status() # Nomination rules have changed
                    email_notification('result', fixture)
            else:
                # If forms is not valid, change pageview returned
                context['pagename'] = 'errors'

        return self.render_to_response(context)

    def setup_result_forms(self, context, fixture):

        # Get relevant results form for fixture type
        if fixture.division.type == "Mixed":
            resform = MixedFixtureForm(instance=fixture)
            resformset = MixedScoreFormSet()
        else:
            resform = LevelFixtureForm(instance=fixture)
            resformset = LevelScoreFormSet()

        games_fields = []
        games_names = constants.GAME_NAMES_MIXED if fixture.division.type == "Mixed" else constants.GAME_NAMES_LEVEL
        for i, game_name in enumerate(games_names):
            rubbers = [resformset.forms[2*i], resformset.forms[2*i+1]]
            games_fields.append((game_name, rubbers))

        if fixture.division.type == "Mixed":
            home_ladies, home_men = fixture.get_eligible_players()
            for i in range(1,4):
                resform.fields['home_player'+str(i)].choices = home_ladies
                resform.fields['home_player'+str(i+3)].choices = home_men
        else:
            home_players = fixture.get_eligible_players()
            home_fields = ['home_player1','home_player2','home_player3','home_player4']
            for field in home_fields:
                resform.fields[field].choices = home_players

        context.update({'resform':resform,
                        'resformset':resformset,
                        'games_fields': games_fields,})

        return context

class ClubsView(GenericViewMixin, TemplateView):
    template_name = "league/clubs.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        pagename = self.kwargs.get('pagename','')

        # If home page requested, return all clubs
        if pagename == 'home':

            context.update({
                'status': 'home',
                'clubs': Club.objects.filter(active=True).order_by("name"),
                'old_clubs': Club.objects.filter(active=False).order_by("name"),
            })

        # Otherwise return requested club details
        else:

            # Check requested club exists
            try:
                club = Club.objects.get(name=urllib.parse.unquote(pagename))
            except ObjectDoesNotExist:
                return {'status':'doesnotexist'}

            # Get teams and fixtures
            teams = Team.objects.filter(active=True).filter(club=club).order_by("type", "number")
            ex_teams = Team.objects.filter(active=False).filter(club=club).order_by("type", "number")
            club_fixtures = Fixture.objects.filter(season=context['current_season']).filter(Q(home_team__club=club)|Q(away_team__club=club)).order_by("date_time")
            fix_list = [(fix,fix.updateable(context['user'])) for fix in club_fixtures]

            # Get list of venues used
            venues = club.get_club_venues(context['current_season'])

            # Check whether club has public contacts
            public_info = bool(club.public_contact_name or club.public_email or club.public_num)

            context.update({
                'status': 'view',
                'club': club,
                'teams': teams,
                'ex_teams': ex_teams,
                'venues': venues,
                'fixtures': fix_list,
                'clubnights': ClubNight.objects.filter(club=club),
                'public_info': public_info,
            })

        return context

    def post(self, request, **kwargs):

        context = super().get_context_data(**kwargs)

        pagename = self.kwargs.get('pagename','')

        club = Club.objects.get(name=urllib.parse.unquote(pagename))
        fixtures = Fixture.objects.filter(season=context['current_season']).filter(Q(home_team__club=club)|Q(away_team__club=club)).order_by("date_time")

        return download_fixtures(fixtures)

class TeamsView(GenericViewMixin, TemplateView):
    template_name = "league/teams.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        pagename = self.kwargs.get('pagename','')

        # If home page requested, return all teams
        if pagename == 'home':

            context.update({
                'status': 'home',
                'teams': Team.objects.filter(active=True).order_by("club__name", "type", "number"),
                'old_teams': Team.objects.filter(active=False).order_by("club__name", "type", "number"),
            })

        # Otherwise return team requested
        else:

            # Check team exists
            try:
                team = Team.objects.get(id=urllib.parse.unquote(pagename))
            except ObjectDoesNotExist:
                return {'status':'doesnotexist'}

            # Create form for captain details
            form = TeamForm(None, instance=team)

            # Get fixtures
            fixtures = Fixture.objects.filter(season=context['current_season']).filter(Q(home_team=team)|Q(away_team=team)).order_by('date_time')
            fix_list = [(fix,fix.updateable(context['user'])) for fix in fixtures]

            # Get performances
            performances = Performance.objects.filter(team=team).order_by('season__year').reverse()

            # If admin, captain's details are updateable
            updateable = context['admin'] is not None and context['admin'].club == team.club

            context.update({
                'status': 'view',
                'team': team,
                'updateable': updateable,
                'form': form,
                'fixtures': fix_list,
                'performances': performances,
            })

        return context

    def post(self, request, **kwargs):

        pagename = self.kwargs.get('pagename','')

        team = Team.objects.get(id=urllib.parse.unquote(pagename))

        form = TeamForm(self.request.POST, instance=team)

        if form.is_valid():
            form.save()
            return redirect(f"{self.request.path}?updated=true")

class VenuesView(GenericViewMixin, TemplateView):
    template_name = "league/venues.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        pagename = self.kwargs.get('pagename','')

        # If home page requested, return all venues
        if pagename == 'home':
            context.update({
                'status': 'home',
                'venues': Venue.objects.all().order_by("name"),
            })

        # Otherwise return requested venue
        else:

            # Check venue exists
            try:
                venue = Venue.objects.get(name=urllib.parse.unquote(pagename))
            except ObjectDoesNotExist:
                return {'status':'doesnotexist'}

            # Create venue form
            form = VenueForm(None,instance=venue)

            # Get fixtures at venue
            fixtures = Fixture.objects.filter(season=context['current_season']).filter(venue=venue)

            # Find clubs with fixtures at venue
            clubs = [fix.home_team.club for fix in fixtures]
            clubs += [cn.club for cn in ClubNight.objects.filter(venue=venue)]
            clubs = list(set(clubs))

            # If admin, captain's details are updateable
            updateable = context['admin'] is not None and context['admin'].club in clubs

            context.update({
                'status': 'view',
                'venue': venue,
                'form': form,
                'clubs': clubs,
                'updateable': updateable,
            })

        return context

    def post(self, request, **kwargs):

        pagename = self.kwargs.get('pagename','')

        venue = Venue.objects.get(name=urllib.parse.unquote(pagename))

        form = VenueForm(self.request.POST, instance=venue)

        if form.is_valid():
            form.save()
            return redirect(f"{self.request.path}?updated=true")

@method_decorator(login_required, name='dispatch')
class PlayerStatsView(GenericViewMixin, TemplateView):
    template_name = "league/playerstats.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        # Get admin, club and teams
        club = context['admin'].club
        club_fixtures = Fixture.objects.filter(season=context['current_season']).filter(Q(home_team__club=club)|Q(away_team__club=club)).order_by("date_time")

        player_stats = get_player_stats(club, club_fixtures)

        # Set up context
        context.update({
            'stats': player_stats,
            'club': club,
            'season': context['current_season'],
        })

        return context

class ArchivesView(GenericViewMixin, TemplateView):
    template_name = "league/archive.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        pagename = self.kwargs.get('pagename','')

        if pagename == 'home':

            seasons = list(Season.objects.filter(current=False))
            seasons = sorted(seasons, key=lambda x: int(x.year[:4]), reverse=True)

            context.update({'view': 'home', 'seasons': seasons})

        else:

            season = Season.objects.get(year=pagename)
            fixtures = Fixture.objects.filter(season=season).order_by('date_time')

            divisions = []
            for fix in fixtures:
                if fix.division not in divisions:
                    divisions.append(fix.division)

            divisions.sort(key=lambda div: (div.type, div.number))

            full_divs = []
            for div in divisions:
                table = div.get_table(season)
                divfixs = fixtures.filter(division=div)
                full_divs.append({'division':div, 'table':table, 'fixtures':divfixs})

            context.update({'view': 'season',
                       'season': season,
                       'divisions': full_divs
                       })

        return context

    def post(self, request, **kwargs):

        pagename = self.kwargs('pagename','')

        user = self.request.user if self.request.user.is_authenticated else None

        is_admin = user is not None and user.username == "websiteAdmin"

        season = Season.objects.get(year=pagename)
        fixtures = Fixture.objects.filter(season=season).order_by('date_time')

        return download_fixtures(fixtures, is_admin)

@login_required
def clubadmin(request, update=''):
    if request.user.username == 'leagueAdmin':
        return redirect('league_admin')
    elif request.user.username == 'websiteAdmin':
        return redirect('website_admin')

    try:
        Administrator.objects.get(user=request.user)
        return redirect('club_admin')
    except ObjectDoesNotExist:
        pass

    try:
        Member.objects.get(user=request.user)
        return redirect('club_admin')
    except ObjectDoesNotExist:
        pass

    return redirect('home')

@method_decorator(login_required, name='dispatch')
class ClubAdminView(GenericViewMixin, TemplateView):
    template_name = "league/clubadmin.html"
    active_tab = 'clubadmin'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        club = context['admin'].club
        penalties = Penalty.objects.filter(team__club=club).filter(season=Season.objects.get(current=True))

        context.update({
            'status': 'admin',
            'clubform': ClubForm(instance=club),
            'clubnights': ClubNight.objects.filter(club=club),
            'clubnightform': ClubNightForm(),
            'venueform': VenueForm(),
            'players': Player.objects.filter(club=club).order_by("level","name"),
            'playerform': PlayerForm(),
            'playerstats': club.get_clubs_player_stats(),
            'teams': club.get_clubs_teams('roster'),
            'penalties': penalties})

        return context

    def post(self, request, **kwargs):
        context = self.get_context_data(kwargs)
        update = self.kwargs.get('update', '')
        club = context['admin'].club

        # Contacts form submitted
        if update == 'contacts':
            clubform = ClubForm(request.POST,instance=club)
            if clubform.is_valid():
                clubform.save()
                context.update({'status': 'contactupdated'})

        # Player form submitted
        elif update == 'players':
            playerform = PlayerForm(request.POST)
            if playerform.is_valid():
                name = playerform.cleaned_data['name']
                level = playerform.cleaned_data['level']
                if Player.objects.filter(club=club, name=name, level=level).exists():
                    context.update({'status': 'playerduplicated'})
                else:
                    Player.objects.create(club=club,name=name,level=level)
                    context.update({'status': 'playeradded'})

        # Venue form submitted
        elif update == 'venue':
            venueform = VenueForm(request.POST)
            if venueform.is_valid():
                if Venue.objects.filter(name=venueform.cleaned_data['name']).exists():
                    context.update({'status': 'venueduplicated'})
                else:
                    venueform.save()
                    send_mail(
                        "New Venue Added",
                        "Venue Created",
                        "GlosBadWebsite@gmail.com",
                        ["schofieldmark@gmail.com"],
                        )
                    context.update({'status': 'venueadded'})

        # Club Night form submitted
        elif update == 'clubnight':
            cnform = ClubNightForm(request.POST)
            if cnform.is_valid():
                ClubNight.objects.create(club=club,venue=cnform.cleaned_data['venue'],timings=cnform.cleaned_data['timings'])
                context.update({'status': 'clubnightadded'})

        # Club Night deleted
        elif 'deletecn' in update:
            cn_id = update.replace('deletecn','')
            ClubNight.objects.filter(id=cn_id).delete()
            context.update({'status': 'clubnightdeleted'})

        # Player deleted
        elif 'deleteplayer' in update:
            player_id = update.replace('deleteplayer','')
            Player.objects.filter(id=player_id).delete()
            context.update({'status': 'playerdeleted'})

        # Player error reported
        elif 'duplicateplayer' in update:
            player_id = update.replace('duplicateplayer','')
            player = Player.objects.get(id=player_id)
            club_players = Player.objects.filter(club=club)
            player_options = [(p.id, p.name) for p in club_players]
            form = DuplicatePlayerForm(player=[(player.id,player.name)],players=player_options)
            context.update({'status':'duplicateplayer', 'player':player, 'form':form})

        # Player error form submitted
        elif 'duplicatesubmit' in update:
            form = DuplicatePlayerForm(request.POST)
            inc_player = Player.objects.get(id=request.POST['incorrect_player'])
            cor_player = Player.objects.get(id=request.POST['correct_player'])
            fix = inc_player.get_own_fixtures()
            if len(fix) != 1:
                email_admin(inc_player, cor_player, fix, 'fixerror')
                context.update({'status':'duplicateerror'})
            else:
                status_code = correct_duplicate_player(inc_player, cor_player, fix[0])
                if status_code == 'done':
                    email_admin(inc_player, cor_player, fix[0], 'done')
                    inc_player.delete()
                    context.update({'status':'duplicatedeleted'})
                else:
                    email_admin(inc_player, cor_player, fix[0], 'notfound')
                    context.update({'status':'duplicateerror'})

        return self.render_to_response(context)

@method_decorator(login_required, name='dispatch')
class LeagueAdminView(GenericViewMixin, TemplateView):
    template_name = "league/leagueadmin.html"
    active_tab = 'clubadmin'

    def dispatch(self, request, *args, **kwargs):
        if request.user.username != 'leagueAdmin':
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        update = context.get('update','')
        current_season = Season.objects.get(current=True)

        ##### Player View #####
        if 'player' in update:
            player_id = int(update.replace('player',''))
            player = Player.objects.get(id=player_id)
            playerstats = {player: player.get_team_dict()}
            playermatches = player.get_own_fixtures()

            club_teams = Team.objects.filter(active=True).filter(club=player.club)

            # Split out teams
            teams = {"Mixed":club_teams.filter(type="Mixed"),
                     "Ladies":club_teams.filter(type="Ladies"),
                     "Mens":club_teams.filter(type="Mens"),
                     "All":club_teams}
            # Get length of team lists
            teams.update({"Lengths":{"Mixed":len(teams["Mixed"]),
                                     "Ladies":len(teams["Ladies"]),
                                     "Mens": len(teams["Mens"]),
                                     "All": len(teams["All"]),
                                     }})

            context.update({
                'status': 'player',
                'player': player,
                'playerstats': playerstats,
                'matches': playermatches,
                'teams': teams,
                'test': player_id
                })

        else:

            # Get nomination stats
            active_teams = Team.objects.filter(active=True).order_by("club","type","number")
            last_teams = [team for team in active_teams if team.last_team()]
            nom_teams = [team for team in active_teams if not team.last_team()]
            nom_stats = [(team, team.check_nominations()) for team in nom_teams]

            # Update context
            context.update({
                'status': 'leagueAdmin',
                'penalties': Penalty.objects.filter(season=current_season),
                'nom_teams': nom_stats,
                'last_teams': last_teams,
                'club_contacts': get_all_club_contacts()
            })

        return context

    def post(self, request, **kwargs):
        context = self.get_context_data(kwargs)
        update = self.kwargs.get('update', '')

        if 'delpen' in update:
            penID = update.replace('delpen','')
            penalty = Penalty.objects.get(id=penID)
            penalty.delete()
            context.update({'status':'penaltydeleted'})

        return self.render_to_response(context)

@method_decorator(login_required, name='dispatch')
class WebsiteAdminView(GenericViewMixin, TemplateView):
    template_name = "league/websiteadmin.html"
    active_tab = 'clubadmin'

    def dispatch(self, request, *args, **kwargs):
        if request.user.username != 'websiteAdmin':
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        solo_rubs_to_30, solo_rubs_to_other, other_rubs_to_other, forfeits, errors = get_fixture_stats()

        context.update({
            'status': 'websiteAdmin',
            's30': solo_rubs_to_30,
            'sother': solo_rubs_to_other,
            'oother': other_rubs_to_other,
            'forfeits': forfeits,
            'errors': errors
        })

        return context

    def post(self, request, **kwargs):
        context = self.get_context_data(kwargs)
        update = self.kwargs.get('update', '')

        if update == 'upload':
            myfile = request.FILES['myfile']
            #df = pd.read_csv(myfile)
            df = pd.read_excel(myfile)
            contents = df.to_dict('index')
            #parse_results(contents)
            parse_fixtures(contents)
            context.update({'status': 'fileuploaded'})

        elif update == 'getperm':
            log = get_performances()
            context.update({
                'status': 'gotperm',
                'log': log
                })

        elif update == 'clearnoms':

            nom_fields = [f'nom_player{i}' for i in range(1, 7)]
            for team in Team.objects.all():
                if any(getattr(team, f) for f in nom_fields):
                    for f in nom_fields:
                        setattr(team, f, None)
                    team.save()

            context.update({'status': 'nomscleared'})

        return self.render_to_response(context)

class NominationsView(GenericViewMixin, TemplateView):
    template_name = "league/nominations.html"
    active_tab = 'clubadmin'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pagename = context.get('pagename','')
        club = kwargs['admin'].club
        club_teams = Team.objects.filter(active=True).filter(club=club)

        # Get players
        ladies = Player.objects.filter(club=club).filter(level="Ladies").order_by("name")
        men = Player.objects.filter(club=club).filter(level="Mens").order_by("name")
        ladies = [(player.id,player) for player in ladies]
        men = [(player.id,player) for player in men]
        ladies.insert(0,('',''))
        men.insert(0,('',''))

        # Set up forms for each team (except the lowest ones)
        forms = []
        for team in club_teams:
            name = team.type + " " + str(team.number)
            code = team.type + str(team.number)

            # Check whether a team below exists if not, don't create a form for team
            try:
                Team.objects.get(club=club, type=team.type, active=True, number=team.number + 1)
            except ObjectDoesNotExist:
                continue

            # Otherwise create form for team
            if team.type == 'Mixed':
                if pagename == team.type + str(team.number):
                    form = MixedNominateForm(None, instance=team)
                else:
                    form = MixedNominateForm(instance=team)
            else:
                if pagename == team.type + str(team.number):
                    form = LevelNominateForm(None, instance=team)
                else:
                    form = LevelNominateForm(instance=team)

            # Update players choices with the ladies and men at the club
            if team.type == "Ladies":
                for i in range(1,5):
                    form.fields['nom_player'+str(i)].choices = ladies
            elif team.type == "Mens":
                for i in range(1,5):
                    form.fields['nom_player'+str(i)].choices = men
            else:
                for i in range(1,4):
                    form.fields['nom_player'+str(i)].choices = ladies
                for i in range(4,7):
                    form.fields['nom_player'+str(i)].choices = men

            forms.append((name,code,form,team.type,team))

        # Sort list of forms by team name
        forms.sort(key=lambda x: x[0])

        # Check whether there are any teams to nominate for
        noteams = True if len(forms) == 0 else False

        # Set up context
        context.update({
            'teams': club_teams,
            'noteams': noteams,
            'forms': forms,
            'pagename': pagename,
        })

        return context

    def post(self, request, **kwargs):
        context = self.get_context_data(kwargs)

        # Check which team was submitted
        for team in context['teams']:
            if context['pagename'] == team.type + str(team.number):
                current_team = team
        # Update team object
        if current_team.type == 'Mixed':
            form = MixedNominateForm(request.POST, instance=current_team)
        else:
            form = LevelNominateForm(request.POST, instance=current_team)
        if form.is_valid():
            form.save()

        return self.render_to_response(context)

class StatsView(GenericViewMixin, TemplateView):
    template_name = "league/stats.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context.update({'stats': get_league_stats()})

        return context

def get_league_stats(season='current'):

    if season == 'current':
        season_obj = Season.objects.get(current=True)
    else:
        season_obj = Season.objects.get(year=season)
    fixtures = Fixture.objects.filter(season=season_obj)

    team_dict = {}
    score_dict = defaultdict(int)
    total_dict = {'m':0,'hw':0,'d':0,'c':0,'r':0,'pt':0,'pw':0,'pl':0,'ph':0,'pa':0}

    for fixture in fixtures:

        total_dict['m'] += 1
        ht = fixture.home_team
        at = fixture.away_team
        if ht not in team_dict:
            team_dict[ht] = {'mp':0,'w':0,'d':0,'c':0,'hr':0,'ar':0,'hp':0,'hpa':0,'ap':0,'apa':0,'ww':0,'st':0,'sw':0}
        if at not in team_dict:
            team_dict[at] = {'mp':0,'w':0,'d':0,'c':0,'hr':0,'ar':0,'hp':0,'hpa':0,'ap':0,'apa':0,'ww':0,'st':0,'sw':0}

        team_dict[ht]['mp'] += 1
        team_dict[at]['mp'] += 1

        if not fixture.game_results:
            total_dict['c'] += 1
            if fixture.status == 'Conceded (H)':
                team_dict[ht]['c'] += 1
                team_dict[at]['w'] += 1
            else:
                team_dict[at]['c'] += 1
                team_dict[ht]['w'] += 1
            continue

        tp = 18 if fixture.division.type == 'Mixed' else 12
        if fixture.home_points == tp:
            team_dict[ht]['ww'] += 1
        if fixture.away_points == tp:
            team_dict[at]['ww'] += 1

        if fixture.home_points == fixture.away_points:
            team_dict[ht]['d'] += 1
            team_dict[at]['d'] += 1
            total_dict['d'] += 1
        elif fixture.home_points > fixture.away_points:
            team_dict[ht]['w'] += 1
            total_dict['hw'] += 1
        else:
            team_dict[at]['w'] += 1

        scores = fixture.game_results.split(',')
        scores = [tuple(scores[i:i+2]) for i in range(0, len(scores), 2)]
        scores = [(int(x[0]), int(x[1])) if x[0].isdigit() else x for x in scores]

        for score in scores:

            if isinstance(score[0], str):
                continue

            score_dict[score] += 1
            total_dict['r'] += 1
            total_dict['pt'] += score[0] + score[1]
            total_dict['ph'] += score[0]
            total_dict['pa'] += score[1]

            team_dict[ht]['hp'] += score[0]
            team_dict[at]['ap'] += score[1]
            team_dict[ht]['hpa'] += score[1]
            team_dict[at]['apa'] += score[0]
            if score[0] > score[1]:
                team_dict[ht]['hr'] += 1
                total_dict['pw'] += score[0]
                total_dict['pl'] += score[1]
                if score[0] > 21:
                    team_dict[ht]['st'] += 1
                    team_dict[at]['st'] += 1
                    team_dict[ht]['sw'] += 1
            else:
                team_dict[at]['ar'] += 1
                total_dict['pw'] += score[1]
                total_dict['pl'] += score[0]
                if score[0] > 21:
                    team_dict[at]['st'] += 1
                    team_dict[ht]['st'] += 1
                    team_dict[at]['sw'] += 1

    set_team = max(team_dict, key=lambda team: team_dict[team]['sw'])
    set_string = f"{set_team} ({team_dict[set_team]['sw']})"
    ww_team = max(team_dict, key=lambda team: team_dict[team]['ww'])
    ww_string = f"{ww_team} ({team_dict[ww_team]['ww']})"

    stats = {
        'Total Matches': total_dict['m'],
        'Total Home Wins': total_dict['hw'],
        'Total Away Wins': total_dict['m'] - total_dict['hw'] - total_dict['d'] - total_dict['c'],
        'Total Draws': total_dict['d'],
        'Total Conceded': total_dict['c'],
        'Total Rubbers': total_dict['r'],
        'Total Points': total_dict['pt'],
        'Total Home Points': total_dict['ph'],
        'Total Away Points': total_dict['pa'],
        'Total Points of Winner': total_dict['pw'],
        'Total Points of Loser': total_dict['pl'],
        'Average Winning Score': round(total_dict['pw'] / total_dict['r'], 2),
        'Average Losing Score': round(total_dict['pl'] / total_dict['r'], 2),
        'Most Common Scoreline': max(score_dict, key=score_dict.get),
        'Teams with perfect records': [],
        'Mixed Team with most points per match': None,
        "Women's Team with most points per match": None,
        "Men's Team with most points per match": None,
        'Most games won on setting': set_string,
        'Most matches whitewashed': ww_string,
        'Biggest Average Game Winning Margin (Mixed)': None,
        "Biggest Average Game Winning Margin (Women's)": None,
        "Biggest Average Game Winning Margin (Men's)": None,
    }

    for team, team_stats in team_dict.items():
        team_type = team.type
        if team_stats['mp'] == team_stats['w']:
            stats['Teams with perfect records'].append(str(team))
        ppm = round((team_stats['hr'] + team_stats['ar']) / (team_stats['mp'] - team_stats['c']), 2)
        rpm = 18 if team_type == 'Mixed' else 12
        avemgn = round((team_stats['hp'] + team_stats['ap'] - team_stats['hpa'] - team_stats['apa']) / ((team_stats['mp'] - team_stats['c']) * rpm), 2)
        if team_type == 'Mixed':
            if not stats['Mixed Team with most points per match']:
                stats['Mixed Team with most points per match'] = f'{team} ({ppm})'
            else:
                current = float(stats['Mixed Team with most points per match'].split('(')[1].replace(')',''))
                if ppm > current:
                    stats['Mixed Team with most points per match'] = f'{team} ({ppm})'
            if not stats['Biggest Average Game Winning Margin (Mixed)']:
                stats['Biggest Average Game Winning Margin (Mixed)'] = f'{team} ({avemgn})'
            else:
                current = float(stats['Biggest Average Game Winning Margin (Mixed)'].split('(')[1].replace(')',''))
                if avemgn > current:
                    stats['Biggest Average Game Winning Margin (Mixed)'] = f'{team} ({avemgn})'
        elif team_type == 'Ladies':
            if not stats["Women's Team with most points per match"]:
                stats["Women's Team with most points per match"] = f'{team} ({ppm})'
            else:
                current = float(stats["Women's Team with most points per match"].split('(')[1].replace(')',''))
                if ppm > current:
                    stats["Women's Team with most points per match"] = f'{team} ({ppm})'
            if not stats["Biggest Average Game Winning Margin (Women's)"]:
                stats["Biggest Average Game Winning Margin (Women's)"] = f'{team} ({avemgn})'
            else:
                current = float(stats["Biggest Average Game Winning Margin (Women's)"].split('(')[1].replace(')',''))
                if avemgn > current:
                    stats["Biggest Average Game Winning Margin (Women's)"] = f'{team} ({avemgn})'
        elif team_type == 'Mens':
            if not stats["Men's Team with most points per match"]:
                stats["Men's Team with most points per match"] = f'{team} ({ppm})'
            else:
                current = float(stats["Men's Team with most points per match"].split('(')[1].replace(')',''))
                if ppm > current:
                    stats["Men's Team with most points per match"] = f'{team} ({ppm})'
            if not stats["Biggest Average Game Winning Margin (Men's)"]:
                stats["Biggest Average Game Winning Margin (Men's)"] = f'{team} ({avemgn})'
            else:
                current = float(stats["Biggest Average Game Winning Margin (Men's)"].split('(')[1].replace(')',''))
                if avemgn > current:
                    stats["Biggest Average Game Winning Margin (Men's)"] = f'{team} ({avemgn})'

    return stats


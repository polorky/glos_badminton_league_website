from django.shortcuts import redirect
from django.db.models import Q
from django.core.mail import send_mail
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages

from .models import *
from .forms import *
from .utilities.player import verify_away_players, correct_duplicate_player, get_player_stats, get_player_appearances
from .utilities.download import download_fixtures, parse_fixtures
from .utilities.team import get_performances
from .utilities.fixture import get_fixture_stats, get_scores
from .utilities.email import email_notification, email_admin, get_all_club_contacts
from .utilities.table import build_table
from .utilities.season import get_adj_seasons
from .utilities.roster import build_roster, get_clubs_teams
import league.constants as constants
from datetime import date
from collections import defaultdict

import urllib
import pandas as pd

##############################################################################################################################################
##### Main website page views #####
##############################################################################################################################################

class GenericViewMixin:
    user = None
    admin = None
    type_dict = {'X':'Mixed','W':'Womens','M':'Mens'}

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        path = self.request.path.strip('/').split('/')
        context['active_tab'] = path[0] if path[0] else 'home'
        member = None

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
                    member = True
                except ObjectDoesNotExist:
                    admin = None

        context.update({
            'current_season': Season.objects.get(current=True),
            'user': user,
            'admin': admin,
            'member': member,
            'settings': LeagueSettings.get(),
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

            # Extract all divisions, split into the three leagues and active/not active
            context.update({
                'status': 'home',
                **{f"{'old_' if not a else ''}{t.lower()}_divs":
                   [d for d in all_divs if d.type == t and d.active == a]
                   for t in ["Mixed", "Womens", "Mens"] for a in [True, False]}
            })

        else:

            # Get specified division
            try:
                division = Division.objects.get(number=pagename[1:],type=self.type_dict[pagename[0]])
            except ObjectDoesNotExist:
                return {'status':'doesnotexist'}

            # If season other than current one requested, override current_season
            if season != '' and season != context['current_season'].year:
                context['current_season'] = Season.objects.get(year=season)
            table = build_table(division, context['current_season'])

            # Get fixtures and if method is post just return these
            fixtures = Fixture.objects.filter(season=context['current_season']).filter(division=division.id).order_by("date_time")

            # Work out previous/next season/division for links
            prev_season, next_season = get_adj_seasons(context['current_season'])
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
            batched_games = get_scores(fixture)

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

        is_admin = context['user'] is not None and context['user'].username == "websiteAdmin"

        return download_fixtures(fixtures, is_admin)

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
            context = self._setup_result_forms(context, fixture)

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
        context['errors'] = False

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

            self._reschedule_match(fixture)

        # Match conceded
        elif pagename == "concededhome" or pagename == "concededaway":

            self._conceded_match(pagename, fixture)

        # Result submitted by home team
        elif pagename == "submit":

            context = self._process_result(fixture)

        return self.render_to_response(context)

    def _reschedule_match(self, fixture):

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

    def _conceded_match(self, pagename, fixture):

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

        Penalty.objects.create(season=fixture.season,
                               team=team,
                               penalty_value=penalty_value,
                               penalty_type='Match Conceded',
                               fixture=fixture)

        email_notification(pagename, fixture)

    def _process_result(self, fixture):

        # Get relevant results form for fixture type
        if fixture.division.type == "Mixed":
            resform = MixedFixtureForm(self.request.POST, instance=fixture)
            resformset = MixedScoreFormSet(self.request.POST)
        else:
            resform = LevelFixtureForm(self.request.POST, instance=fixture)
            resformset = LevelScoreFormSet(self.request.POST)

        if resform.is_valid() and resformset.is_valid():

            # Find matches for away players or create new ones
            a = resform.cleaned_data
            found_players = resform.cleaned_data['players_found']
            verify_away_players(fixture, found_players)

            # Change fixture status
            fixture.status = 'Played'

            # Bundle up game results
            game_results = [self._get_game_result(form.cleaned_data) for form in resformset if form.cleaned_data]
            fixture.game_results = ','.join(game_results)

            # Save form and fixture data
            resform.save()
            fixture.save()

            # Check for illegal players and apply any penalties
            fixture.check_player_eligibility()
            email_notification('result', fixture)

            context['pagename'] = 'submitted'

        else:
            # If forms is not valid, change pageview returned
            context['errors'] = True
            context = self._setup_result_forms(context, fixture, resform, resformset)

        return context

    def _get_game_result(self, cleaned_data: dict) -> str:
        if forfeit := cleaned_data.get("forfeit"):
            return f"{forfeit},{forfeit}"
        home = cleaned_data.get("home_score")
        away = cleaned_data.get("away_score")
        return f"{home},{away}"

    def _setup_result_forms(self, context, fixture, resform=None, resformset=None):

        # Get relevant results form for fixture type
        if resform is None:
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
            home_women, home_men = fixture.get_eligible_players()
            for i in range(1,4):
                resform.fields['home_player'+str(i)].choices = home_women
                resform.fields['home_player'+str(i+3)].choices = home_men
        else:
            home_players = fixture.get_eligible_players()
            for field in ['home_player1','home_player2','home_player3','home_player4']:
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
            home_fix = Fixture.objects.filter(season=context['current_season']).filter(home_team__club=club)
            venues = {fix.venue for fix in home_fix}

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

class PlayerView(GenericViewMixin, TemplateView):
    template_name = "league/player.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        player_id = int(kwargs['playerid'])
        player = Player.objects.get(id=player_id)

        context.update({
            'status': 'player',
            'player': player,
            'playerstats': {player: get_player_appearances(player)},
            'matches': player.get_own_fixtures(),
            'teams': get_clubs_teams(player.club),
            'test': player_id,
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
                table = build_table(div, season)
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

    def dispatch(self, request, *args, **kwargs):
        if request.user.username == 'leagueAdmin':
            return redirect('league_admin')
        elif request.user.username == 'websiteAdmin':
            return redirect('website_admin')
        return super().dispatch(request, *args, **kwargs)

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
            'playerstats': build_roster(club),
            'teams': get_clubs_teams(club),
            'penalties': penalties})

        return context

    def post(self, request, **kwargs):
        context = self.get_context_data(**kwargs)
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
                    return redirect("/clubadmin/club/?updated=venueduplicated#newvenue")
                else:
                    venueform.save()
                    send_mail(
                        "New Venue Added",
                        "Venue Created",
                        "GlosBadWebsite@gmail.com",
                        ["schofieldmark@gmail.com"],
                        )
                    return redirect("/clubadmin/club/?updated=newvenue#newvenue")

        # Club Night form submitted
        elif update == 'clubnight':
            cnform = ClubNightForm(request.POST)
            if cnform.is_valid():
                ClubNight.objects.create(club=club,venue=cnform.cleaned_data['venue'],timings=cnform.cleaned_data['timings'])
                return redirect("/clubadmin/club/?updated=clubnightadded#clubnights")

        # Club Night deleted
        elif 'deletecn' in update:
            cn_id = update.replace('deletecn','')
            ClubNight.objects.filter(id=cn_id).delete()
            return redirect("/clubadmin/club/?updated=clubnightdeleted#clubnights")

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

        current_season = Season.objects.get(current=True)

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
        context = self.get_context_data(**kwargs)
        update = self.kwargs.get('update', '')

        if 'delpen' in update:
            penID = update.replace('delpen','')
            penalty = Penalty.objects.get(id=penID)
            penalty.delete()
            context.update({'status':'penaltydeleted'})

        if 'noms' in update:
            settings = LeagueSettings.get()
            settings.nomination_window_open = 'nomination_window_open' in request.POST
            settings.save()
            return redirect(f"{self.request.path}?noms_updated=true")

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
        context = self.get_context_data(**kwargs)
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

            TeamNomination.objects.all().delete()

            context.update({'status': 'nomscleared'})

        return self.render_to_response(context)

class NominationsView(GenericViewMixin, TemplateView):
    template_name = "league/nominations.html"
    active_tab = 'clubadmin'

    def get_context_data(self, **kwargs):

        def get_form_list(data, club, club_teams):

            women = Player.objects.filter(club=club).filter(level="Womens").order_by("name")
            men = Player.objects.filter(club=club).filter(level="Mens").order_by("name")

            form_list = []

            for team in club_teams:

                if team.last_team():
                    continue

                existing_noms = TeamNomination.objects.filter(
                    team=team,
                    date_to=None  # currently active nominations
                ).order_by('position')

                if team.type == 'Mixed':
                    women_existing = existing_noms.filter(player__level='Womens')
                    men_existing = existing_noms.filter(player__level='Mens')
                    women_extra = 3 - women_existing.count()
                    men_extra = 3 - men_existing.count()

                    WomensFormSet = modelformset_factory(TeamNomination, form=NominationForm, extra=women_extra)
                    MensFormSet = modelformset_factory(TeamNomination, form=NominationForm, extra=men_extra)

                    womens_formset = WomensFormSet(
                        data,
                        queryset=women_existing,
                        form_kwargs={'players': women},
                        prefix=f'women_{team.id}'
                    )
                    mens_formset = MensFormSet(
                        data,
                        queryset=men_existing,
                        form_kwargs={'players': men},
                        prefix=f'men_{team.id}'
                    )

                    form_list.append((team,womens_formset,mens_formset))

                else:
                    players = women if team.type == 'Womens' else men
                    extra = 4 - existing_noms.count()

                    FormSet = modelformset_factory(TeamNomination, form=NominationForm, extra=extra)

                    formset = FormSet(
                        data,
                        queryset=existing_noms,
                        form_kwargs={'players': players},
                        prefix=f'team_{team.id}'
                    )

                    form_list.append((team,formset))

            return form_list

        context = super().get_context_data(**kwargs)
        pagename = context.get('pagename','')

        # If 'update' page requested and nomination window open, return team forms
        if pagename == 'update' and context['settings'].nomination_window_open:

            data = self.request.POST or None
            club = context['admin'].club
            club_teams = Team.objects.filter(active=True).filter(club=club).order_by("type", "number")

            form_list = get_form_list(data, club, club_teams)

            # Set up context
            context.update({
                'teams': club_teams,
                'forms': form_list,
                'view': 'teamupdate',
            })

        # If 'update' page requested but nomination window closed, return 'unavailable'
        elif pagename == 'update':

            context.update({'view':'unavailable'})

        # If admin view requested return current and requested nominations and player stats
        elif pagename == 'admin':
            nom = TeamNomination.objects.get(id=kwargs['type'])
            current_nom = TeamNomination.objects.get(team=nom.team, position=nom.position, date_to=None, approved=True)

            context.update({'view': 'admin',
                            'nom': nom,
                            'current_nom': current_nom,
                            'new_player_stats': get_player_appearances(nom.player),
                            'cur_player_stats': get_player_appearances(nom.player)})

        # Otherwise return specific individual nomination form
        else:

            nom_player = Player.objects.get(id=pagename)
            team_type = 'Mixed' if context['type'] == 'mixed' else nom_player.level
            nom = TeamNomination.objects.get(player=nom_player, date_to=None, approved=True, team__type=team_type)
            replacement_options = nom.get_possible_replacements()
            form = NominationForm(None, players=replacement_options, variant='change')

            context.update({'view':'indiupdate', 'playerselectform':form, 'current_nom':nom})

        return context


    def post(self, request, **kwargs):
        context = self.get_context_data(**kwargs)

        if context['view'] == 'teamupdate':

            # Check which team was submitted
            team = Team.objects.get(id=self.kwargs['pagename'])
            current = next(form_list for form_list in context['forms'] if form_list[0] == team)

            # Rebind the relevant formsets with POST data
            if team.type == 'Mixed':
                womens_formset = current[1]
                mens_formset = current[2]

                if womens_formset.is_valid() and mens_formset.is_valid():
                    self.save_nominations(womens_formset, team, range(1, 4))
                    self.save_nominations(mens_formset, team, range(4, 7))
                    return redirect(request.path)
            else:
                formset = current[1]

                if formset.is_valid():
                    self.save_nominations(formset, team, range(1, 5))
                    return redirect(request.path)

            return redirect('nominations_success')

        elif context['view'] == 'admin_approved':

            context['cur_nom'].approved = True
            context['cur_nom'].save()
            email_notification('nomination_approved', None, {'nom':context['cur_num']})

        elif context['view'] == 'admin_rejected':

            context['cur_nom'].delete()

        else:

            player_in = Player.objects.get(id=request.POST.get('player'))

            TeamNomination.objects.create(
                team=context['current_nom'].team,
                player=player_in,
                position=context['current_nom'].position,
                date_from=date.today(),
                notes=request.POST.get('notes')
            )

            return redirect('nomination_change_success')

    def save_nominations(self, formset, team, positions):
        for position, form in zip(positions, formset):
            if form.cleaned_data.get('player'):
                nomination = form.save(commit=False)
                nomination.team = team
                nomination.position = position
                nomination.date_from = date.today()
                nomination.approved = True
                nomination.save()

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
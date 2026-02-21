from django.shortcuts import render, redirect
from django.db.models import Q
from django.core.mail import send_mail
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.decorators import method_decorator

from .models import Administrator, Member, Club, ClubNight, Team, Player, Venue, Fixture, Division, Season, Penalty, Performance
from .forms import ClubForm, PlayerForm, MixedNominateForm, LevelNominateForm, VenueForm, EmailForm, DuplicatePlayerForm
from .forms import TeamForm, RescheduleForm, MixedFixtureForm, LevelFixtureForm, ClubNightForm

import urllib
import pandas as pd
from fuzzywuzzy import fuzz
from io import BytesIO
from datetime import datetime


##### Constants #####
fuzzy_match_ratio = 85
alt_names_list = (('David','Dave'),('Stuart','Stu'),('Richard','Rich'),('Alexander','Alex'),('Christopher','Chris'),('Andrew','Andy'),('Daniel','Dan'),('Matthew','Matt'),
('Michael','Mike'),('Oliver','Oli'),('Oliver','Ollie'),('Phillip','Phil'),('Philip','Phil'),('Robert','Rob'),('Simon','Si'),('Thomas','Tom'),('William','Will'),
('Rebecca','Becky'))
conceded_penalty_mixed = 5
conceded_penalty_level = 7
cardinal_dict = {1:'st',2:'nd',3:'rd'}

##### Change of season checklist #####
# Code up any changes in league rules
# Create new season and untick 'active' flag on previous season
# Download full results for previous season
# Get perfomances for teams (on league admin Club Admin page)
# Create new clubs/teams
# Update teams with new divisions and 'active' flag
# Upload fixtures
# Open nominations
# Close nominations and apply any penalties

##### Auxillary functions #####

def check_away_players(fixture, detdata):
    '''
        Takes data from results form and checks for matches for away players
        If a fuzzy match is not found, a new player is created for the club
        The updated Fixture object is returned
    '''

    match_dict = {}
    club = fixture.away_team.club
    players = ['away_player1','away_player2','away_player3','away_player4']
    level = ['Ladies','Ladies','Ladies','Mens','Mens','Mens']

    if fixture.division.type == "Mixed":
        players += ['away_player5','away_player6']

    for i, player_title in enumerate(players):

        player_name = detdata[player_title]

        if not player_name:
            continue

        # Try direct match
        try:
            match_dict[player_title] = Player.objects.get(club=club,name=player_name)
        # Else try fuzzy match with all club players
        except:
            fuzzy_max = ('',0)
            for player in Player.objects.filter(club=club):
                if fuzz.ratio(player_name.upper(),player.name.upper()) > fuzzy_max[1]:
                    fuzzy_max = (player,fuzz.ratio(player_name.upper(),player.name.upper()))
            if fuzzy_max[1] >= fuzzy_match_ratio:
                match_dict[player_title] = fuzzy_max[0]
            else:
                # Else try replacing name with long/short version
                player_found = False
                for name_tuple in alt_names_list:
                    if name_tuple[0] in player_name:
                        try:
                            match_dict[player_title] = Player.objects.get(club=club,name=player_name.replace(name_tuple[0],name_tuple[1]))
                            player_found = True
                        except:
                            pass
                    elif name_tuple[1] in player_name:
                        try:
                            match_dict[player_title] = Player.objects.get(club=club,name=player_name.replace(name_tuple[1],name_tuple[0]))
                            player_found = True
                        except:
                            pass

                # If player still not found, create them
                if not player_found:
                    if fixture.division.type == "Mixed":
                        player_level = level[i]
                    else:
                        player_level = fixture.division.type
                    new_player = Player(club=club,name=player_name.title(),level=player_level)
                    new_player.save()
                    email_notification('new_player',fixture,player_name=player_name)
                    match_dict[player_title] = new_player

    if "away_player1" in match_dict.keys():
        fixture.away_player1 = match_dict["away_player1"]
    if "away_player2" in match_dict.keys():
        fixture.away_player2 = match_dict["away_player2"]
    if "away_player3" in match_dict.keys():
        fixture.away_player3 = match_dict["away_player3"]
    if "away_player4" in match_dict.keys():
        fixture.away_player4 = match_dict["away_player4"]
    if fixture.division.type == "Mixed":
        if "away_player5" in match_dict.keys():
            fixture.away_player5 = match_dict["away_player5"]
        if "away_player6" in match_dict.keys():
            fixture.away_player6 = match_dict["away_player6"]

    return fixture

def email_notification(status, fix, sender='GlosBadWebsite@gmail.com', player_name=''):

    def get_recipients(fix, team):

        if team == 'home':
            recipients = [fix.home_team.club.contact1_email, fix.home_team.club.contact2_email, fix.home_team.captain_email]
        elif team == 'away':
            recipients = [fix.away_team.club.contact1_email, fix.away_team.club.contact2_email, fix.away_team.captain_email]
        else:
            recipients = [fix.home_team.club.contact1_email, fix.home_team.club.contact2_email, fix.home_team.captain_email]
            recipients += [fix.away_team.club.contact1_email, fix.away_team.club.contact2_email, fix.away_team.captain_email]
        for i in range(len(recipients),0,-1):
            if not recipients[i-1]:
                recipients.pop(i-1)

        return recipients

    html = ''

    if status == 'new_player':
        subject = 'New Club Player Created'
        body = 'Hi,\n\nFollowing the submission of the result for the match ' + str(fix) + ' a new player called ' + player_name \
        + ' was created due to this being the name supplied on the match scorecard and there not being a player of that name already ' \
        + 'recorded in your club roster. If this is correct then no further action is required. However, if this player already exists ' \
        + 'you can mark the incorrect player as a duplicate by pressing the orange button next to their name on the Club Admin page and then selecting the correct ' \
        + 'player. The system will swap them on the match result and delete the incorrect player.\n\nRegards\n\nLeague Committee\n\n' \
        + '***This is an automated email from the league website***'
        html = 'Hi,<br><br>Following the submission of the result for the match ' + str(fix) + ' a new player called <b>' + player_name \
        + '</b> was created due to this being the name supplied on the match scorecard and there not being a player of that name already ' \
        + 'recorded in your club roster. If this is correct then no further action is required. However, if this player already exists ' \
        + 'you can mark the incorrect player as a duplicate by pressing the orange button next to their name on the Club Admin page and then selecting the correct ' \
        + 'player. The system will swap them on the match result and delete the incorrect player.<br><br>Regards<br><br>League Committee<br><br>' \
        + '***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'away')
    elif status == 'confirmed':
        subject = str(fix) + ' - Rearrangement Confirmed'
        body = 'Hi,\n\nThe away team have confirmed the rearrangement of the match ' + str(fix) + ' originally scheduled for ' \
        + fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' and now scheduled for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + ' at ' + str(fix.venue) + '.\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'home')
    elif status == 'rejected':
        subject = str(fix) + ' - Rearrangement Rejected'
        body = 'Hi,\n\nThe away team have REJECTED the proposed rearrangement of the match ' + str(fix) + ' originally scheduled for ' \
        + fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' and proposed to be rearranged for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' at ' \
        + str(fix.venue) + '.\n\nPlease contact the away team to discuss why the rearrangement was rejected and agree a new date/venue. Fixture status has ' \
        + 'been returned to "Postponed".\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'home')
    elif status == 'postponed':
        subject = str(fix) + ' - Match Postponed'
        body = 'Hi,\n\nThe home team have postponed the match ' + str(fix) + ' originally scheduled for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + '. Hopefully, they have been in touch to explain why and to initiate the process of finding a new date/venue.\n\nRegards\n\nLeague Committee\n\n' \
        + '***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'away')
    elif status == 'reschedule':
        subject = str(fix) + ' - New Date Proposed'
        body = 'Hi,\n\nThe home team have proposed a new date/venue for the match ' + str(fix) + ' originally scheduled for ' \
        + fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S") + '. The proposed new date is ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' at ' + str(fix.venue) \
        + '.\n\nPlease confirm or reject this rearrangement via this page: https://gloubadleague.pythonanywhere.com/fixtures/' \
        + str(fix.id) + '/update/div\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        html = 'Hi,<br><br>The home team have proposed a new date/venue for the match ' + str(fix) + ' originally scheduled for ' \
        + fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S") + '. The proposed new date is ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' at ' + str(fix.venue) \
        + '.<br><br>Please confirm or reject this rearrangement by clicking ' + '<a href="https://gloubadleague.pythonanywhere.com/fixtures/' \
        + str(fix.id) + '/update/div">here</a>.<br><br>Regards<br><br>League Committee<br><br>***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'away')
    elif status == 'concededhome':
        if fix.division.type == "Mixed":
            penalty_value = conceded_penalty_mixed
        else:
            penalty_value = conceded_penalty_level
        subject = str(fix) + ' - Match Conceded'
        body = 'Hi,\n\nThe home team have conceded the match ' + str(fix) + ' scheduled for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + 'The home team will be penalised ' + str(penalty_value) + ". The away team's points will not be updated to reflect the concession until the end of the season " \
        + 'but the fixture status has been updated to record the concession\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'both')
    elif status == 'concededaway':
        if fix.division.type == "Mixed":
            penalty_value = conceded_penalty_mixed
        else:
            penalty_value = conceded_penalty_level
        subject = str(fix) + ' - Match Conceded'
        body = 'Hi,\n\nThe away team have conceded the match ' + str(fix) + ' scheduled for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + 'The away team will be penalised ' + str(penalty_value) + ". The home team's points will not be updated to reflect the concession until the end of the season " \
        + 'but the fixture status has been updated to record the concession\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'both')
    elif status == 'result':
        subject = str(fix) + ' - Result Submitted'
        body = 'Hi,\n\nThe home team have submitted the results for the match ' + str(fix) + ' played on ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + '. You can view the score submitted on this page: https://gloubadleague.pythonanywhere.com/fixtures/' + str(fix.id) \
        + '\n\nIf you believe the result has been entered incorrectly, please contact the league by replying to this email.\n\nRegards\n\nLeague Committee \
        \n\n***This is an automated email from the league website***'
        html = 'Hi,<br><br>The home team have submitted the results for the match ' + str(fix) + ' played on ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + '. You can view the score submitted <a href="https://gloubadleague.pythonanywhere.com/fixtures/' + str(fix.id) \
        + '/div">here</a>.<br><br>If you believe the result has been entered incorrectly, please contact the league by replying to this email.<br><br>Regards<br><br>' \
        + 'League Committee<br><br>***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'away')

    body += '\n\nFor any issues surrounding fixtures, please contact GlosBadFixtures@outlook.com\nFor technical issues with the website, please reply to this email'
    #recipients = ['schofieldmark@gmail.com']

    if html:

        html += '<br><br>For any issues surrounding fixtures, please contact <a href="mailto:GlosBadFixtures@outlook.com">GlosBadFixtures@outlook.com</a>' \
        + '<br>For technical issues with the website, please reply to this email'
        #html = html.replace('\n','<br>')

        send_mail(subject, body, sender, recipients, html_message = html)

    else:

        send_mail(subject, body, sender, recipients)

    return

def email_admin(dup_player, cor_player, fix, code):

    if code == 'done':
        body = str(dup_player.club) + ' have submitted a player correction for ' + str(fix) + '. The erroneously created player was ' + dup_player.name \
        + ' and the correct player is ' + cor_player.name + '. Update was successful.'
        subject = 'Duplicate Player'
    elif code == 'notfound':
        body = str(dup_player.club) + ' have submitted a player correction for ' + str(fix) + '. The erroneously created player was ' + dup_player.name \
        + ' and the correct player is ' + cor_player.name + '. Fixture containing player not found.'
        subject = 'Duplicate Player Error'
    elif code == 'fixerror':
        body = str(dup_player.club) + ' have submitted a player correction for ' + str(fix) + '. The erroneously created player was ' + dup_player.name \
        + ' and the correct player is ' + cor_player.name + '. Player has played too many fixtures.'
        subject = 'Duplicate Player Error'

    send_mail(subject, body, 'GlosBadWebsite@gmail.com', ['schofieldmark@gmail.com'])

    return

def build_dataframe(fixtures, admin=False):

    def localiseDT(dtvalue):
        if not pd.isnull(dtvalue):
            return dtvalue.tz_localize(None)
        else:
            return dtvalue

    fixDict = {'Division':[],'Date and Time':[],'Home Team':[], 'Home Points':[], 'Away Points':[],
               'Away Team':[], 'Venue':[], 'Status':[], 'Original Date and Time':[]}
    if admin:
        fixDict.update({'Game Breakdown':[]})

    for fix in fixtures:
        fixDict['Division'].append(str(fix.division))
        fixDict['Date and Time'].append(fix.date_time)
        fixDict['Home Team'].append(str(fix.home_team))
        fixDict['Home Points'].append(fix.home_points)
        fixDict['Away Points'].append(fix.away_points)
        fixDict['Away Team'].append(str(fix.away_team))
        fixDict['Venue'].append(str(fix.venue))
        fixDict['Status'].append(fix.status)
        fixDict['Original Date and Time'].append(fix.old_date_time)
        if admin:
            fixDict['Game Breakdown'].append(fix.game_results)

    df = pd.DataFrame(fixDict)
    df['Date and Time'] = df['Date and Time'].dt.tz_localize(None)
    df['Original Date and Time'] = df['Original Date and Time'].apply(localiseDT)

    return df

def get_all_club_contacts():

    clubs = Club.objects.filter(active=True)
    email_list = {}

    for club in clubs:
        if club.contact1_email:
            email_list[f'{club.short_name} Contact 1'] = club.contact1_email
        if club.contact2_email:
            email_list[f'{club.short_name} Contact 2'] = club.contact2_email

    return email_list

def correct_duplicate_player(dup_player,cor_player,fix):

    home_players = ['home_player1','home_player2','home_player3','home_player4','home_player5','home_player6']
    away_players = ['away_player1','away_player2','away_player3','away_player4','away_player5','away_player6']
    players = home_players + away_players

    for player in players:
        if getattr(fix, player) == dup_player:
            setattr(fix, player, cor_player)
            fix.save()
            return 'done'

    return 'notfound'

##############################################################################################################################################
##### Main website page views #####
##############################################################################################################################################

class GenericViewMixin:
    user = None
    admin = None
    type_dict = {'X':'Mixed','L':'Ladies','M':'Mens'}

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None

        try:
            admin = Administrator.objects.get(user=user)
        except:
            try:
                admin = Member.objects.get(user=user)
            except:
                admin = None

        context.update({
            'current_season': Season.objects.get(current=True),
            'user': user,
            'admin': admin,
            })

        return context

    def download_fixtures(self, fixtures, is_admin=False):

        df = self.build_dataframe(fixtures, is_admin)

        with BytesIO() as b:
            with pd.ExcelWriter(b) as writer:
                df.to_excel(writer)
            filename = "fixtures.xlsx"
            res = HttpResponse(b.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            res['Content-Disposition'] = f'attachment; filename={filename}'

            return res

    def build_dataframe(self, fixtures, is_admin):

        def localiseDT(dtvalue):
            if not pd.isnull(dtvalue):
                return dtvalue.tz_localize(None)
            else:
                return dtvalue

        fixDict = {'Division':[],'Date and Time':[],'Home Team':[], 'Home Points':[], 'Away Points':[],
                   'Away Team':[], 'Venue':[], 'Status':[], 'Original Date and Time':[]}
        if is_admin:
            fixDict.update({'Game Breakdown':[]})

        for fix in fixtures:
            fixDict['Division'].append(str(fix.division))
            fixDict['Date and Time'].append(fix.date_time)
            fixDict['Home Team'].append(str(fix.home_team))
            fixDict['Home Points'].append(fix.home_points)
            fixDict['Away Points'].append(fix.away_points)
            fixDict['Away Team'].append(str(fix.away_team))
            fixDict['Venue'].append(str(fix.venue))
            fixDict['Status'].append(fix.status)
            fixDict['Original Date and Time'].append(fix.old_date_time)
            if is_admin:
                fixDict['Game Breakdown'].append(fix.game_results)

        df = pd.DataFrame(fixDict)
        df['Date and Time'] = df['Date and Time'].dt.tz_localize(None)
        df['Original Date and Time'] = df['Original Date and Time'].apply(localiseDT)

        return df


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
                # Check whether requested division exists - will error if doesn't exist
                division = Division.objects.get(number=pagename[1:],type=self.type_dict[pagename[0]])
            except:
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
                'exist': exist
            })

        return context

    def post(self, request, **kwargs):

        context = super().get_context_data(**kwargs)
        pagename = kwargs.get('pagename','')

        division = Division.objects.get(number=pagename[1:],type=self.type_dict[pagename[0]])
        fixtures = Fixture.objects.filter(season=context['current_season']).filter(division=division.id).order_by("date_time")

        if fixtures:
            return self.download_fixtures(fixtures)

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
            except:
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

        return self.download_fixtures(fixtures)

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

            # Get relevant results form for fixture type
            if fixture.division.type == "Mixed":
                detform = MixedFixtureForm(None, instance=fixture)
            else:
                detform = LevelFixtureForm(None, instance=fixture)

            if fixture.division.type == "Mixed":
                home_ladies, home_men = fixture.get_eligible_players()
                for i in range(1,4):
                    detform.fields['home_player'+str(i)].choices = home_ladies
                    detform.fields['home_player'+str(i+3)].choices = home_men
            else:
                home_players = fixture.get_eligible_players()
                home_fields = ['home_player1','home_player2','home_player3','home_player4']
                for field in home_fields:
                    detform.fields[field].choices = home_players

            context.update({'detform':detform})

        elif pagename == 'reschedule':

            # Instantiate reschedule form
            rform = RescheduleForm(None, instance=fixture)

            context.update({'rform':rform})

        # If not a POST request, set up initial form view
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

        # Confirmation by the away team of a proposed rearrangement
        if pagename == "confirmed":
            fixture.status = 'Rearranged'
            fixture.save()
            email_notification('confirmed',fixture)

        # Proposed new date rejected by away team
        elif pagename == "rejected":
            fixture.status = 'Postponed'
            fixture.save()
            email_notification('rejected',fixture)

        # Postponement by the home team without a new date
        elif pagename == "postponed":
            fixture.status = 'Postponed'
            fixture.save()
            email_notification('postponed',fixture)

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
                email_notification('reschedule',fixture)

        # Match conceded by home team
        elif pagename == "concededhome":
            fixture.status = 'Conceded (H)'
            fixture.save()
            if fixture.division.type == "Mixed":
                penalty_value = conceded_penalty_mixed
            else:
                penalty_value = conceded_penalty_level
            p = Penalty(season=fixture.season, team=fixture.home_team, penalty_value=penalty_value, penalty_type='Match Conceded', fixture=fixture)
            p.save()
            email_notification('concededhome',fixture)

        # Match conceded by away team
        elif pagename == "concededaway":
            fixture.status = 'Conceded (A)'
            fixture.save()
            if fixture.division.type == "Mixed":
                penalty_value = conceded_penalty_mixed
            else:
                penalty_value = conceded_penalty_level
            p = Penalty(season=fixture.season, team=fixture.away_team, penalty_value=penalty_value, penalty_type='Match Conceded', fixture=fixture)
            p.save()
            email_notification('concededaway',fixture)

        # Result submitted by home team
        elif pagename == "submit":

            # Get relevant results form for fixture type
            if fixture.division.type == "Mixed":
                detform = MixedFixtureForm(self.request.POST, instance=fixture)
            else:
                detform = LevelFixtureForm(self.request.POST, instance=fixture)

            if detform.is_valid():

                # Get form data
                detdata = detform.cleaned_data
                # Find matches for away players or create new ones
                fixture = check_away_players(fixture,detdata)
                # Change fixture status
                fixture.status = 'Played'
                # Bundle up game results
                game_results = [detdata[x] for x in detdata.keys() if 'player' not in x and 'points' not in x and 'score' not in x]
                game_results = ['' if x==None else str(x) for x in game_results]
                game_results = ','.join(game_results)
                fixture.game_results = game_results
                # Save form and fixture data
                detform.save()
                fixture.save()
                # Check for illegal players and apply any penalties
                if fixture.season.current:
                    fixture.check_player_eligibility()
                    #fixture.check_nomination_status() # Nomination rules have changed
                    email_notification('result',fixture)
            else:
                # If forms is not valid, change pageview returned
                context['pagename'] = 'errors'

        return self.render_to_response(context)

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
            except:
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

        return self.download_fixtures(fixtures)

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
            except:
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

        pagename = self.kwargs('pagename','')

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
            context = {
                'status': 'home',
                'venues': Venue.objects.all().order_by("name"),
            }

        # Otherwise return requested venue
        else:

            # Check venue exists
            try:
                venue = Venue.objects.get(name=urllib.parse.unquote(pagename))
            except:
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

        pagename = self.kwargs('pagename','')

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

        return self.download_fixtures(fixtures, is_admin)

################ Old function based views ################

def divisions(request, pagename, season=''):
    '''
        View for Divisions page
        If 'Home' view accessed then lists of divisions are returned
        Otherwise, specific division information is returned
    '''

    # For home page return list of divisions
    if pagename == 'home':
        mixed_divs = Division.objects.filter(type="Mixed",active=True).order_by("number")
        ladies_divs = Division.objects.filter(type="Ladies",active=True).order_by("number")
        mens_divs = Division.objects.filter(type="Mens",active=True).order_by("number")
        old_mixed_divs = Division.objects.filter(type="Mixed",active=False).order_by("number")
        old_ladies_divs = Division.objects.filter(type="Ladies",active=False).order_by("number")
        old_mens_divs = Division.objects.filter(type="Mens",active=False).order_by("number")

        context = {
            'status': 'home',
            'mixed_divs': mixed_divs,
            'ladies_divs': ladies_divs,
            'mens_divs': mens_divs,
            'old_mixed_divs': old_mixed_divs,
            'old_ladies_divs': old_ladies_divs,
            'old_mens_divs': old_mens_divs,
        }

    # Otherwise return specific division
    else:

        # Check user
        if request.user.is_authenticated:
            user = request.user
        else:
            user = None

        # Check whether requested division exists
        try:
            type_dict = {'X':'Mixed','L':'Ladies','M':'Mens'}
            division = Division.objects.get(number=pagename[1:],type=type_dict[pagename[0]])
        except:
            return render(request, "league/divisions.html", {'status':'doesnotexist'})

        # Get current season
        current_season = Season.objects.get(current=True)

        # If current season or no specific season requested get current table
        if season == '' or season == current_season.year:
            table = division.get_table()
        # Else work out table for requested season
        else:
            current_season = Season.objects.get(year=season)
            table = division.get_table(season=current_season)

        # Work out previous/next season/division for links
        prev_season, next_season = current_season.get_adj_seasons()
        prev_div = Division.objects.filter(number=division.number - 1, type=division.type)
        next_div = Division.objects.filter(number=division.number + 1, type=division.type)
        fixtures = Fixture.objects.filter(season=current_season).filter(division=division.id).order_by("date_time")
        fix_list = [(fix,fix.updateable(user)) for fix in fixtures]
        concessions = False

        # If no fixtures found and not current season, division did not exist in requested season
        if len(fixtures) == 0 and not division.active:
            exist = False
        else:
            exist = True

        # If concessions exist a note will be added next to table
        for fix in fixtures:
            if fix.status == "Conceded (H)" or fix.status == "Conceded (A)":
                concessions = True
                break

        # Download fixtures to Excel
        if request.method == 'POST':
            if len(fixtures) != 0:
                df = build_dataframe(fixtures)
                with BytesIO() as b:
                    with pd.ExcelWriter(b) as writer:
                        df.to_excel(writer)
                    filename = "fixtures.xlsx"
                    res = HttpResponse(b.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    res['Content-Disposition'] = f'attachment; filename={filename}'
                    return res

        context = {
            'status': 'view',
            'division': division,
            'fixtures': fix_list,
            'table': table,
            'concessions': concessions,
            'cur_season': current_season,
            'prev_season': prev_season,
            'next_season': next_season,
            'prev_div': prev_div,
            'next_div': next_div,
            'exist': exist
        }

    return render(request, "league/divisions.html", context)

def fixtures(request, pagename, source=''):
    '''
        View for the Fixtures page
        If 'Home' view requested, full fixture list is returned
        Otherwise details of a specific fixture are returned
        Note that updating fixtures is done by the 'fixupdate' view
    '''

    # Check user
    if request.user.is_authenticated:
        user = request.user
    else:
        user = None

    # Check for admin
    try:
        admin = Administrator.objects.get(user=user)
    except:
        try:
            admin = Member.objects.get(user=user)
        except:
            admin = None

    # Get current season
    current_season = Season.objects.get(current=True)

    # If home page requested, return all fixtures
    if pagename == 'home':

        # Download fixtures
        if request.method == 'POST':
            fixtures = Fixture.objects.filter(season=current_season).order_by('date_time')
            df = build_dataframe(fixtures)
            with BytesIO() as b:
                with pd.ExcelWriter(b) as writer:
                    df.to_excel(writer)
                filename = "fixtures.xlsx"
                res = HttpResponse(b.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                res['Content-Disposition'] = f'attachment; filename={filename}'
                return res

        # Get all fixtures ordered by date
        fixtures = Fixture.objects.filter(season=current_season).order_by('date_time')
        fix_list = [(fix,fix.updateable(user)) for fix in fixtures]

        context = {
            'pageview': 'home',
            'fixtures': fix_list,
            'season': current_season,
        }

    # Otherwise return requested fixture for viewing
    else:

        # Check fixture exists
        try:
            fixture = Fixture.objects.get(id=pagename)
        except:
            return render(request, "league/fixtures.html", {'pageview':'doesnotexist'})

        # Get players in user is club admin
        players = []

        if admin and admin.club == fixture.home_team.club:
            players += fixture.get_players(side='home')
        if admin and admin.club == fixture.away_team.club:
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

        context = {
            'pageview': 'view',
            'fixture': fixture,
            'game_results': batched_games,
            'players': players,
            'source': source,
            'rubber_number': rubber_number,
        }

    return render(request, "league/fixtures.html", context)

@login_required
def fixupdate(request, pagename, status='', source=''):
    '''
        View for updating fixtures including postponing, rescheduling or submitting a result
    '''

    # Get relevant fixture
    fixture = Fixture.objects.get(id=pagename)

    # Get relevant results form for fixture type
    if fixture.division.type == "Mixed":
        detform = MixedFixtureForm(request.POST or None,instance=fixture)
    else:
        detform = LevelFixtureForm(request.POST or None,instance=fixture)

    # Instantiate reschedule form
    rform = RescheduleForm(request.POST or None, instance=fixture)

    # Set up initial context values
    context = {
        'pageview': status,
        'source': source,
        'fixture': fixture,
        'rform': rform,
        'detform': detform,
    }

    # If there is posted form information, check which type...
    if request.method == 'POST':

        # Confirmation by the away team of a proposed rearrangement
        if status == "confirmed":
            fixture.status = 'Rearranged'
            fixture.save()
            email_notification('confirmed',fixture)

        # Proposed new date rejected by away team
        if status == "rejected":
            fixture.status = 'Postponed'
            fixture.save()
            email_notification('rejected',fixture)

        # Postponement by the home team without a new date
        elif status == "postpone":
            fixture.status = 'Postponed'
            fixture.save()
            email_notification('postponed',fixture)

        # Proposed reschedule date and location by home team
        elif status == "reschedule":
            temp_date = fixture.date_time
            if rform.is_valid():
                if not fixture.old_date_time:
                    fixture.old_date_time = temp_date
                rform.save()
                fixture.status = 'Proposed'
                fixture.save()
                email_notification('reschedule',fixture)

        # Match conceded by home team
        elif status == "concededhome":
            fixture.status = 'Conceded (H)'
            fixture.save()
            if fixture.division.type == "Mixed":
                penalty_value = conceded_penalty_mixed
            else:
                penalty_value = conceded_penalty_level
            p = Penalty(season=fixture.season, team=fixture.home_team, penalty_value=penalty_value, penalty_type='Match Conceded', fixture=fixture)
            p.save()
            email_notification('concededhome',fixture)

        # Match conceded by away team
        elif status == "concededaway":
            fixture.status = 'Conceded (A)'
            fixture.save()
            if fixture.division.type == "Mixed":
                penalty_value = conceded_penalty_mixed
            else:
                penalty_value = conceded_penalty_level
            p = Penalty(season=fixture.season, team=fixture.away_team, penalty_value=penalty_value, penalty_type='Match Conceded', fixture=fixture)
            p.save()
            email_notification('concededaway',fixture)

        # Result submitted by home team
        elif status == "result":
            if detform.is_valid():

                    # Get form data
                    detdata = detform.cleaned_data
                    # Find matches for away players or create new ones
                    fixture = check_away_players(fixture,detdata)
                    # Change fixture status
                    fixture.status = 'Played'
                    # Bundle up game results
                    game_results = [detdata[x] for x in detdata.keys() if 'player' not in x and 'points' not in x and 'score' not in x]
                    game_results = ['' if x==None else str(x) for x in game_results]
                    game_results = ','.join(game_results)
                    fixture.game_results = game_results
                    # Save form and fixture data
                    detform.save()
                    fixture.save()
                    # Check for illegal players and apply any penalties
                    if fixture.season.current:
                        fixture.check_player_eligibility()
                        #fixture.check_nomination_status() # Nomination rules have changed
                        email_notification('result',fixture)
            else:
                # If forms is not valid, change pageview returned
                context['pageview'] = 'errors'

    # If not a POST request, set up initial form view
    else:

        # Default status is 'update' - different pages required where a rearrangement has been proposed
        # or the fixture is not updateable by the user
        if fixture.status == "Proposed":
            context['pageview'] = 'proposed'

        elif not fixture.updateable(request.user):
            context['pageview'] = 'unupdateable'

    # Reduce the number of options for home players to club players of the relevant level doubles type
    if context['pageview'] == 'update' or context['pageview'] == 'errors':

        if fixture.division.type == "Mixed":
            home_ladies, home_men = fixture.get_eligible_players()
            for i in range(1,4):
                detform.fields['home_player'+str(i)].choices = home_ladies
                detform.fields['home_player'+str(i+3)].choices = home_men
        else:
            home_players = fixture.get_eligible_players()
            home_fields = ['home_player1','home_player2','home_player3','home_player4']
            for field in home_fields:
                detform.fields[field].choices = home_players

        context['detform'] = detform

    return render(request, "league/fixtures.html", context)

def clubs(request, pagename):
    '''
        View for Clubs page
        If 'Home' view accessed then lists of clubs are returned
        Otherwise, specific club information is returned
    '''

    if request.user.is_authenticated:
        user = request.user
    else:
        user = None

    # If home page requested, return all clubs
    if pagename == 'home':
        context = {
            'status': 'home',
            'clubs': Club.objects.filter(active=True).order_by("name"),
            'old_clubs': Club.objects.filter(active=False).order_by("name"),
        }

    # Otherwise return requested club details
    else:
        name = urllib.parse.unquote(pagename)

        # Check requested club exists
        try:
            club = Club.objects.get(name=name)
        except:
            return render(request, "league/clubs.html", {'status':'doesnotexist'})

        # Get teams and fixtures
        teams = Team.objects.filter(active=True).filter(club=club).order_by("type", "number")
        ex_teams = Team.objects.filter(active=False).filter(club=club).order_by("type", "number")
        current_season = Season.objects.get(current=True)
        club_fixtures = Fixture.objects.filter(season=current_season).filter(Q(home_team__club=club)|Q(away_team__club=club)).order_by("date_time")
        fix_list = [(fix,fix.updateable(user)) for fix in club_fixtures]

        # Get list of venues used
        venues = set()
        for team in teams:
            fixtures = Fixture.objects.filter(season=current_season).filter(home_team=team)
            for fix in fixtures:
                venues.add(fix.venue)

        # Get contacts
        if club.public_contact_name or club.public_email or club.public_num:
            public_info = True
        else:
            public_info = False

        # Download fixtures
        if request.method == 'POST':
            df = build_dataframe(club_fixtures)
            with BytesIO() as b:
                with pd.ExcelWriter(b) as writer:
                    df.to_excel(writer)
                filename = "fixtures.xlsx"
                res = HttpResponse(b.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                res['Content-Disposition'] = f'attachment; filename={filename}'
                return res

        context = {
            'status': 'view',
            'club': club,
            'teams': teams,
            'ex_teams': ex_teams,
            'venues': venues,
            'fixtures': fix_list,
            'clubnights': ClubNight.objects.filter(club=club),
            'public_info': public_info,
        }

    return render(request, "league/clubs.html", context)

def teams(request, pagename):
    '''
        View for Teams page
        If 'Home' view accessed then lists of teams are returned
        Otherwise, specific team information is returned
    '''

    # If home page requested, return all teams
    if pagename == 'home':
        context = {
            'status': 'home',
            'teams': Team.objects.filter(active=True).order_by("club__name", "type", "number"),
            'old_teams': Team.objects.filter(active=False).order_by("club__name", "type", "number"),
        }

    # Otherwise return team requested
    else:

        # Check user
        if request.user.is_authenticated:
            user = request.user
        else:
            user = None

        # Check for admin
        try:
            admin = Administrator.objects.get(user=user)
        except:
            try:
                admin = Member.objects.get(user=user)
            except:
                admin = None

        # Check team exists
        id = urllib.parse.unquote(pagename)
        try:
            team = Team.objects.get(id=id)
        except:
            return render(request, "league/teams.html", {'status':'doesnotexist'})

        # Create form for captain details
        form = TeamForm(request.POST or None,instance=team)

        # Get fixtures
        current_season = Season.objects.get(current=True)
        fixtures = Fixture.objects.filter(season=current_season).filter(Q(home_team=team)|Q(away_team=team)).order_by('date_time')
        fix_list = [(fix,fix.updateable(user)) for fix in fixtures]

        # Get performances
        performances = Performance.objects.filter(team=team).order_by('season__year').reverse()

        # Check whether captain details have been updated
        updated = False

        # Process updated form
        if request.method == 'POST':
            if form.is_valid():
                form.save()
                updated = True

        # If admin, captain's details are updateable
        if admin and admin.club == team.club:
            updateable = True
        else:
            updateable = False

        context = {
            'status': 'view',
            'team': team,
            'updateable': updateable,
            'updated': updated,
            'form': form,
            'fixtures': fix_list,
            'performances': performances,
        }

    return render(request, "league/teams.html", context)

def venues(request, pagename):
    '''
        View for Venue page
        If 'Home' view accessed then lists of venues are returned
        Otherwise, specific venue information is returned
    '''
    # If home page requested, return all venues
    if pagename == 'home':
        context = {
            'status': 'home',
            'venues': Venue.objects.all().order_by("name"),
        }

    # Otherwise return requested venue
    else:

        # Check user
        if request.user.is_authenticated:
            user = request.user
        else:
            user = None

        # Check for admin
        try:
            admin = Administrator.objects.get(user=user)
        except:
            admin = None

        # Check venue exists
        name = urllib.parse.unquote(pagename)
        try:
            venue = Venue.objects.get(name=name)
        except:
            return render(request, "league/venues.html", {'status':'doesnotexist'})

        # Create venue form
        form = VenueForm(request.POST or None,instance=venue)

        # Get fixtures at venue
        current_season = Season.objects.get(current=True)
        fixtures = Fixture.objects.filter(season=current_season).filter(venue=venue)

        # Find clubs with fixtures at venue
        clubs = [fix.home_team.club for fix in fixtures]
        clubs += [cn.club for cn in ClubNight.objects.filter(venue=venue)]
        clubs = list(set(clubs))

        # Check whether venue details have been updated
        updated = False

        # Process updated form
        if request.method == 'POST':
            if form.is_valid():
                form.save()
                updated = True

        # If admin, captain's details are updateable
        if admin and admin.club in clubs:
            updateable = True
        else:
            updateable = False

        context = {
            'status': 'view',
            'venue': venue,
            'form': form,
            'clubs': clubs,
            'updateable': updateable,
            'updated': updated,
        }

    return render(request, "league/venues.html", context)

@login_required
def clubadmin(request, update=''):
    '''
        View for Club Administrator page
        Provides clubs contacts and players
    '''

    user = request.user
    current_season = Season.objects.get(current=True)

    # If user is league admin
    if user.username == "leagueAdmin":

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

            context = {
                'status': 'player',
                'player': player,
                'playerstats': playerstats,
                'matches': playermatches,
                'teams': teams,
                'test': player_id
                }

            return render(request, "league/clubadmin.html", context)

        penalties = Penalty.objects.filter(season=current_season)
        active_teams = Team.objects.filter(active=True).order_by("club","type","number")
        nom_teams = [team for team in active_teams if not team.last_team()]
        nom_stats = [(team, team.check_nominations()) for team in nom_teams]
        last_teams = [team for team in active_teams if team.last_team()]
        #inactive_teams = Team.objects.filter(active=False).order_by("club","type","number")
        clubs = Club.objects.filter(active=True).order_by("name")
        #club_players = {club: Player.objects.filter(club=club).order_by("name") for club in clubs}
        teamlengths = ((1,2,3),(1,2,3,4,5,6,7,8))
        club_contacts = get_all_club_contacts()

        ##### Send Email #####
        if request.method == 'POST':
            # if update == 'massemail':
            #     form = EmailForm(request.POST)
            #     recipients = get_all_club_contacts()
            #     #recipients = ['schofieldmark@gmail.com']
            #     if form.is_valid():
            #         data = form.cleaned_data
            #         msg = EmailMultiAlternatives(
            #             data['subject'],
            #             data['body'],
            #             'glosbadwebsite@gmail.com', # from
            #             [data['replyto']], # to
            #             recipients, # bcc
            #             reply_to=[data['replyto'],]
            #             )
            #         if data['html'] != '':
            #             msg.attach_alternative(data['html'], "text/html")
            #         msg.send()
            #         status = 'emailsent'

            if 'delpen' in update:
                penID = update.replace('delpen','')
                penalty = Penalty.objects.get(id=penID)
                penalty.delete()
                status = 'penaltydeleted'
        else:
            status = 'leagueAdmin'

        context = {
            'status': status,
            'email_form': EmailForm(),
            'penalties': penalties,
            'nom_teams': nom_stats,
            'last_teams': last_teams,
            #'inactive_teams': inactive_teams,
            #'players': club_players,
            'teamlengths': teamlengths,
            'club_contacts': club_contacts,
        }

        return render(request, "league/clubadmin.html", context)

    # If user is website admin
    elif user.username == "websiteAdmin":

        if request.method == 'POST':
            if update == 'upload':
                myfile = request.FILES['myfile']
                #df = pd.read_csv(myfile)
                df = pd.read_excel(myfile)
                contents = df.to_dict('index')
                #parse_results(contents)
                parse_fixtures(contents)
                context = {
                    'status': 'fileuploaded',
                }
            elif update == 'getperm':
                log = get_performances()
                context = {
                    'status': 'gotperm',
                    'log': log
                    }
            elif update == 'clearnoms':
                clear_nominations()
                context = {
                    'status': 'nomscleared',
                    }
        else:
            solo_rubs_to_30, solo_rubs_to_other, other_rubs_to_other, forfeits, errors = get_fixture_stats()
            context = {
                'status': 'websiteAdmin',
                's30': solo_rubs_to_30,
                'sother': solo_rubs_to_other,
                'oother': other_rubs_to_other,
                'forfeits': forfeits,
                'errors': errors
            }

        return render(request, "league/clubadmin.html", context)

    # Otherwise user will be club admin or member
    try:
        admin = Administrator.objects.get(user=user)
        club = admin.club
        member = None
    except:
        member = Member.objects.get(user=user)
        club = member.club
        admin = None

    # Get club and teams
    club_teams = Team.objects.filter(active=True).filter(club=club)

    # If form has been submitted
    if request.method == 'POST':

        # Contacts form submitted
        if update == 'contacts':
            clubform = ClubForm(request.POST,instance=club)
            if clubform.is_valid():
                clubform.save()
                status = 'contactupdated'
        # Player form submitted
        elif update == 'players':
            playerform = PlayerForm(request.POST)
            if playerform.is_valid():
                if len(Player.objects.filter(club=club).filter(name=playerform.cleaned_data['name']).filter(level=playerform.cleaned_data['level'])) > 0:
                    status = 'playerduplicated'
                else:
                    player = Player(club=club,name=playerform.cleaned_data['name'],level=playerform.cleaned_data['level'])
                    player.save()
                    status = 'playeradded'
        # Venue form submitted
        elif update == 'venue':
            venueform = VenueForm(request.POST)
            if venueform.is_valid():
                if len(Venue.objects.filter(name=venueform.cleaned_data['name'])) > 0:
                    status = 'venueduplicated'
                else:
                    venueform.save()
                    send_mail(
                        "New Venue Added",
                        "Venue Created",
                        "GlosBadWebsite@gmail.com",
                        ["schofieldmark@gmail.com"],
                        )
                    status = 'venueadded'
        # Club Night form submitted
        elif update == 'clubnight':
            cnform = ClubNightForm(request.POST)
            if cnform.is_valid():
                cn = ClubNight(club=club,venue=cnform.cleaned_data['venue'],timings=cnform.cleaned_data['timings'])
                cn.save()
                status = 'clubnightadded'
        # Club Night deleted
        elif 'deletecn' in update:
            cn_id = update.replace('deletecn','')
            ClubNight.objects.filter(id=cn_id).delete()
            status = 'clubnightdeleted'
        # Player deleted
        elif 'deleteplayer' in update:
            player_id = update.replace('deleteplayer','')
            Player.objects.filter(id=player_id).delete()
            status = 'playerdeleted'
        # Player error
        elif 'duplicateplayer' in update:
            player_id = update.replace('duplicateplayer','')
            player = Player.objects.get(id=player_id)
            club_players = Player.objects.filter(club=club)
            player_options = [(p.id, p.name) for p in club_players]
            #form = DuplicatePlayerForm(player=player,players=club_players)
            form = DuplicatePlayerForm(player=[(player.id,player.name)],players=player_options)
            return render(request, "league/clubadmin.html", {'status':'duplicateplayer','player':player,'form':form})
        elif 'duplicatesubmit' in update:
            #try:
            form = DuplicatePlayerForm(request.POST)
            inc_player = Player.objects.get(id=request.POST['incorrect_player'])
            cor_player = Player.objects.get(id=request.POST['correct_player'])
            fix = inc_player.get_own_fixtures()
            if len(fix) != 1:
                email_admin(inc_player, cor_player, fix, 'fixerror')
                return render(request, "league/clubadmin.html", {'status':'duplicateerror'})
            status_code = correct_duplicate_player(inc_player, cor_player, fix[0])
            if status_code == 'done':
                email_admin(inc_player, cor_player, fix[0], 'done')
                inc_player.delete()
                return render(request, "league/clubadmin.html", {'status':'duplicatedeleted'})
            else:
                email_admin(inc_player, cor_player, fix[0], 'notfound')
                return render(request, "league/clubadmin.html", {'status':'duplicateerror'})

    else:
        status = 'admin'

    # Get players and players stats
    players = Player.objects.filter(club=club).order_by("level","name")
    playerstats = club.get_clubs_player_stats()
    #playerstats = {player:player.get_team_dict() for player in players}
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
    # Get club penalties
    penalties = Penalty.objects.filter(team__club=club).filter(season=current_season)

    # Set up context
    context = {
        'status': status,
        'admin': admin,
        'member': member,
        'clubform': ClubForm(instance=club),
        'clubnights': ClubNight.objects.filter(club=club),
        'clubnightform': ClubNightForm(),
        'venueform': VenueForm(),
        'players': players,
        'playerform': PlayerForm(),
        'playerstats': playerstats,
        'teams': teams,
        'penalties': penalties,
    }

    return render(request, "league/clubadmin.html", context)

@login_required
def nominations(request, pagename):
    '''
        View for team nominations
    '''

    # Get admin, club and teams
    admin = Administrator.objects.get(user=request.user)
    club = admin.club
    club_teams = Team.objects.filter(active=True).filter(club=club)

    # If form submitted
    if request.method == 'POST':
        # Check which team was submitted
        for team in club_teams:
            if pagename == team.type + str(team.number):
                current_team = team
        # Update team object
        if current_team.type == 'Mixed':
            form = MixedNominateForm(request.POST,instance=current_team)
        else:
            form = LevelNominateForm(request.POST,instance=current_team)
        if form.is_valid():
            form.save()

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
            Team.objects.get(club=club,type=team.type,active=True,number=team.number + 1)
        except:
            continue

        # Otherwise create form for team
        if team.type == 'Mixed':
            if pagename == team.type + str(team.number):
                form = MixedNominateForm(request.POST or None,instance=team)
            else:
                form = MixedNominateForm(instance=team)
        else:
            if pagename == team.type + str(team.number):
                form = LevelNominateForm(request.POST or None,instance=team)
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
    if len(forms) == 0:
        noteams = True
    else:
        noteams = False

    # Set up context
    context = {
        'teams': club_teams,
        'noteams': noteams,
        'forms': forms,
        'pagename': pagename,
    }

    return render(request, "league/nominations.html", context)

@login_required
def player_stats(request, pagename):
    '''
    View to get breakdown for individual players' stats
    '''

    # Get admin, club and teams
    admin = Administrator.objects.get(user=request.user)
    club = admin.club
    current_season = Season.objects.get(current=True)
    club_fixtures = Fixture.objects.filter(season=current_season).filter(Q(home_team__club=club)|Q(away_team__club=club)).order_by("date_time")

    player_stats = get_player_stats(club, club_fixtures)

    # Set up context
    context = {
        'stats': player_stats,
        'club': club,
        'season': current_season,
        'pagename': pagename,
    }

    return render(request, "league/playerstats.html", context)

def archive(request, pagename):

    if pagename == 'home':

        seasons = list(Season.objects.filter(current=False))
        seasons = sorted(seasons, key=lambda x: int(x.year[:4]), reverse=True)

        context = {'view': 'home',
                   'seasons': seasons}

    else:

        season = Season.objects.get(year=pagename)
        fixtures = Fixture.objects.filter(season=season).order_by('date_time')

        if request.method == 'POST':

            if request.user.is_authenticated:
                user = request.user
            else:
                user = None
            if user and user.username == "websiteAdmin":
                df = build_dataframe(fixtures, admin=True)
            else:
                df = build_dataframe(fixtures)
            with BytesIO() as b:
                with pd.ExcelWriter(b) as writer:
                    df.to_excel(writer)
                filename = f"fixtures_{str(season)}.xlsx"
                res = HttpResponse(b.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                res['Content-Disposition'] = f'attachment; filename={filename}'
                return res


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


        context = {'view': 'season',
                   'season': season,
                   'divisions': full_divs}

    return render(request, "league/archive.html", context)


############################### Admin Functions ##################################

def clear_nominations():

    teams = Team.objects.all()

    for team in teams:
        changed = False
        if team.nom_player1:
            team.nom_player1 = None
            changed = True
        if team.nom_player2:
            team.nom_player2 = None
            changed = True
        if team.nom_player3:
            team.nom_player3 = None
            changed = True
        if team.nom_player4:
            team.nom_player4 = None
            changed = True
        if team.nom_player5:
            team.nom_player5 = None
            changed = True
        if team.nom_player6:
            team.nom_player6 = None
            changed = True
        if changed:
            team.save()

def get_performances():

    seasons_not_done = ['2024-2025']
    log = ''
    for season_text in seasons_not_done:
        season = Season.objects.get(year=season_text)
        log += 'Season: ' + str(season)
        fixtures = Fixture.objects.filter(season=season)
        log += ' -- Fixtures: ' + str(len(fixtures))
        divisions = list(set([fix.division for fix in fixtures]))
        log += ' -- Divisions: ' + str(len(divisions))
        for division in divisions:
            table = division.get_table(season)
            position = 1
            for row in table:
                team = row[1]['Object']
                if not Performance.objects.filter(team=team,season=season,division=division):
                    cardinal = str(position) + cardinal_dict.get(position,'th') + ' out of ' + str(len(table))
                    p = Performance(team=team,season=season,division=division,position=cardinal)
                    p.save()
                position += 1

    return log

def parse_fixtures(fixtures):
    '''
        Parses and creates fixtures from an uploaded file
    '''

    for row in fixtures.keys():
        fix = fixtures[row]
        home_club = Club.objects.get(short_name=fix['Home Club'])
        away_club = Club.objects.get(short_name=fix['Away Club'])
        fixture = Fixture(
            home_team = Team.objects.get(club=home_club,number=fix['Home Team Num'],type=fix['Division Type']),
            away_team = Team.objects.get(club=away_club,number=fix['Away Team Num'],type=fix['Division Type']),
            date_time = datetime.combine(fix['Date'].date(), fix['Start Time']),
            end_time = fix['End Time'],
            season = Season.objects.get(year=fix['Season']),
            venue = Venue.objects.get(name=fix['Venue']),
            division = Division.objects.get(number=fix['Division No.'],type=fix['Division Type']),
        )
        fixture.save()

    return

def parse_results(fixtures):
    '''
        Parses and creates archive results from an uploaded file
    '''

    for row in fixtures.keys():
        fix = fixtures[row]
        home_club = Club.objects.get(short_name=fix['home club'])
        away_club = Club.objects.get(short_name=fix['away club'])
        fixture = Fixture(
            home_team = Team.objects.get(club=home_club,number=fix['home num'],type=fix['type']),
            away_team = Team.objects.get(club=away_club,number=fix['away num'],type=fix['type']),
            home_points = fix['home score'],
            away_points = fix['away score'],
            date_time = fix['date_time'],
            season = Season.objects.get(year=fix['season']),
            division = Division.objects.get(number=fix['div num'],type=fix['type']),
        )
        fixture.save()

    return

def get_fixture_stats():

    solo_rubs_to_30 = []
    solo_rubs_to_other = []
    other_rubs_to_other = []
    forfeits = []
    errors = []

    current_season = Season.objects.get(current=True)
    fixtures = Fixture.objects.filter(season=current_season)

    for fix in fixtures:
        if fix.status == 'Conceded (H)' or fix.status == 'Conceded (A)':
            continue
        try:
            srt30 = False
            srto = False
            orto = False
            scores = fix.game_results.split(',')
            if 'FH' in scores or 'FA' in scores:
                forfeits.append(fix)
            scores = [scores[x:x+2] for x in range(0,len(scores),2)]
            if fix.division.type == 'Mixed':
                games = [scores[0:3],scores[3:6],scores[6:9],scores[9:12],scores[12:15],scores[15:18],scores[18:21],scores[21:24],scores[24:27]]
            else:
                games = [scores[0:2],scores[2:4],scores[4:6],scores[6:8],scores[8:10],scores[10:12]]
            for game in games:
                if game[1][0] == '':
                    if game[0][0] == '30' or game[0][1] == '30':
                        srt30 = True
                    else:
                        srto = True
                else:
                    for rubber in game:
                        if rubber[0] != '' and rubber[0] != 'FH' and rubber[0] != 'FA' and rubber[0] != '21' and rubber[1] != '21':
                            if abs(int(rubber[0]) - int(rubber[1])) != 2:
                                if rubber[0] != '30' and rubber[1] != '30':
                                    orto = True
            if srt30:
                solo_rubs_to_30.append(fix)
            if srto:
                solo_rubs_to_other.append(fix)
            if orto:
                other_rubs_to_other.append(fix)
        except:
            errors.append(fix)

    return solo_rubs_to_30, solo_rubs_to_other, other_rubs_to_other, forfeits, errors

def get_player_stats(club, fixtures):

    player_dict = {}

    for fixture in fixtures:

        if fixture.status != 'Played':
            continue

        game_split = fixture.game_results.split(',')

        home_players = fixture.get_players(side='home')
        away_players = fixture.get_players(side='away')
        club_home = False
        club_away = False

        if fixture.home_team.club == club:
            for player in home_players:
                if player.id not in player_dict:
                    player_dict[player.id] = {'obj':player,'mixed':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0},'level':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0}}
            club_home = True
        if fixture.away_team.club == club:
            for player in away_players:
                if player.id not in player_dict:
                    player_dict[player.id] = {'obj':player,'mixed':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0},'level':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0}}
            club_away = True

        if fixture.division.type == "Mixed":
            #mixed_games = ["Mixed 3v2","Mixed 2v3","Mixed 1v1","Mixed 2v2","Mixed 3v3","Mens 1&2","Ladies 1&2","Mens 1&3","Ladies 1&3"]
            mixed_games = [[[3,6],[2,5]],[[2,5],[3,6]],[[1,4],[1,4]],[[2,5],[2,5]],[[3,6],[3,6]],[[4,5],[4,5]],[[1,2],[1,2]],[[4,6],[4,6]],[[1,3],[1,3]]]
            batched_games = [game_split[i:i + 6] for i in range(0, len(game_split), 6)]
        else:
            #level_games = ["2+3 v 2+3","1+4 v 1+4","2+4 v 2+4","1+3 v 1+3","3+4 v 3+4","1+2 v 1+2"]
            level_games = [[2,3],[1,4],[2,4],[1,3],[3,4],[1,2]]
            batched_games = [game_split[i:i + 4] for i in range(0, len(game_split), 4)]

        for x, game in enumerate(batched_games):

            rubbers = [game[i:i+2] for i in range(0, len(game), 2)]
            for rubber in rubbers:
                try:

                    if rubber[0] in ['FH','FA',''] or rubber[1] in ['FH','FA','']:
                        continue

                    if club_home:

                        if fixture.division.type == "Mixed":
                            players_involved = [home_players[mixed_games[x][0][0] - 1], home_players[mixed_games[x][0][1] - 1]]
                            match_type = "mixed"
                        else:
                            players_involved = [home_players[level_games[x][0] - 1], home_players[level_games[x][1] - 1]]
                            match_type = "level"

                        for player in players_involved:
                            player_dict[player.id][match_type]['played'] += 1
                            player_dict[player.id][match_type]['pf'] += int(rubber[0])
                            player_dict[player.id][match_type]['pa'] += int(rubber[1])
                            player_dict[player.id][match_type]['diff'] = player_dict[player.id][match_type]['pf'] - player_dict[player.id][match_type]['pa']
                            if int(rubber[0]) > int(rubber[1]):
                                player_dict[player.id][match_type]['won'] += 1
                            player_dict[player.id][match_type]['percent'] = round(player_dict[player.id][match_type]['won'] / player_dict[player.id][match_type]['played'] * 100, 1)

                    if club_away:

                        if fixture.division.type == "Mixed":
                            players_involved = [away_players[mixed_games[x][1][0] - 1], away_players[mixed_games[x][1][1] - 1]]
                            match_type = "mixed"
                        else:
                            players_involved = [away_players[level_games[x][0] - 1], away_players[level_games[x][1] - 1]]
                            match_type = "level"

                        for player in players_involved:
                            player_dict[player.id][match_type]['played'] += 1
                            player_dict[player.id][match_type]['pf'] += int(rubber[1])
                            player_dict[player.id][match_type]['pa'] += int(rubber[0])
                            player_dict[player.id][match_type]['diff'] = player_dict[player.id][match_type]['pf'] - player_dict[player.id][match_type]['pa']
                            if int(rubber[0]) < int(rubber[1]):
                                player_dict[player.id][match_type]['won'] += 1
                            player_dict[player.id][match_type]['percent'] = round(player_dict[player.id][match_type]['won'] / player_dict[player.id][match_type]['played'] * 100, 1)

                except Exception as e:
                    raise Exception(f'Error - {x}, {game}, {rubber}, {level_games}, {level_games[x]}, {level_games[x][1]}, {home_players}, {away_players}, {e}')

    return player_dict

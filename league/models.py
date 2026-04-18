from django.db import models
from django.db.models import Q
from django.core.mail import send_mail
from django.contrib.auth.models import User
import urllib

#################### Constants ####################
max_plays_for_higher_teams = 3
ineligible_player_penalty_value = 5
nomination_penalty_value = 5
late_submission_penalty_value = 5
penaltyDict = {"Ineligible Player":ineligible_player_penalty_value,
               "Nomination Violation":nomination_penalty_value,
               "Late Submission":late_submission_penalty_value,}
cardinal_dict = {'1':'st','2':'nd','3':'rd'}
mixed_game_format = ["Mixed 3v2","Mixed 2v3","Mixed 1v1","Mixed 2v2","Mixed 3v3","Men 1&2","Women 1&2","Men 1&3","Women 1&3"]
level_game_format = ["2+3 v 2+3","1+4 v 1+4","2+4 v 2+4","1+3 v 1+3","3+4 v 3+4","1+2 v 1+2"]
mixed_scoring_format = 'point per game'
level_scoring_format = 'point per rubber'
scoring_options = (('point per game','point per game'),('point per rubber','point per rubber'))

def sort_table(team_list):

    revised_list = []
    points_dict = {}

    for team in team_list:
        points = team[1]['PFor']
        if points in points_dict.keys():
            points_dict[points].append(team)
        else:
            points_dict[points] = [team]

    points_list = list(points_dict.keys())
    points_list.sort(reverse=True)
    for point in points_list:
        if len(points_dict[point]) == 1:
            revised_list.append(points_dict[point][0])
        else:
            pass

def email_notification(status, fix, team, sender='GlosBadWebsite@gmail.com', player_name=''):

    def get_recipients(fix, team):

        recipients = [team.club.contact1_email, team.club.contact2_email, team.captain_email]

        for i in range(len(recipients),0,-1):
            if not recipients[i-1]:
                recipients.pop(i-1)

        return recipients

    if status == 'nomination_penalty':
        subject = 'Nomination Penalty Applied'
        recipients = get_recipients(fix, team)
        body = 'Hi,\n\nFollowing the submission of the result for the match ' + str(fix) + ", your club's team has played their first three matches." \
        + 'However, nominated player ' + player_name + ' has not played at least two of these matches and so the team has been penalised ' + str(nomination_penalty_value) \
        + ' points. Please contact the League Committee at GlosBadCorrespondence@outlook.com if there are extenuating circumstances you would like to raise.' \
        + '\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        html =  'Hi,<br><br>Following the submission of the result for the match ' + str(fix) + ", your club's team has played their first three matches." \
        + 'However, nominated player <b>' + player_name + '</b> has not played at least two of these matches and so the team has been penalised ' + str(nomination_penalty_value) \
        + ' points. Please contact the League Committee at GlosBadCorrespondence@outlook.com if there are extenuating circumstances you would like to raise.' \
        + '<br><br>Regards<br><br>League Committee<br><br>***This is an automated email from the league website***'
    elif status == 'eligibility_penalty':
        subject = 'Eligibility Penalty Applied'
        recipients = get_recipients(fix, team)
        body = 'Hi,\n\nFollowing the submission of the result for the match ' + str(fix) + ', it has been identified that player ' + player_name + ' was ineligible' \
        + " to play and so your club's team has been penalised " + str(ineligible_player_penalty_value) + ' points. Please contact the League Committee at' \
        + ' GlosBadCorrespondence@outlook.com if there are extenuating circumstances you would like to raise.\n\nRegards\n\nLeague Committee\n\n***This is an automated' \
        + 'email from the league website***'
        html = 'Hi,<br><br>Following the submission of the result for the match ' + str(fix) + ', it has been identified that player <b>' + player_name + '</b> was ineligible' \
        + " to play and so your club's team has been penalised " + str(ineligible_player_penalty_value) + ' points. Please contact the League Committee at' \
        + ' GlosBadCorrespondence@outlook.com if there are extenuating circumstances you would like to raise.<br><br>Regards<br><br>League Committee<br><br>***This is an' \
        + 'automated email from the league website***'

    #recipients = ['schofieldmark@gmail.com']

    send_mail(
        subject,
        body,
        sender,
        recipients,
        html_message = html
    )

    return

class Season(models.Model):
    year = models.CharField(max_length=10)
    current = models.BooleanField()
    archive_info = models.TextField(blank=True,null=True)
    historic_divs = models.BooleanField(default=False)
    mixed_scoring = models.CharField(max_length=20,null=True,choices=scoring_options,default=scoring_options[0][0])

    def __str__(self):
        return self.year

    def get_adj_seasons(self):

        seasons = list(Season.objects.all())
        seasons = sorted(seasons, key=lambda x: int(x.year[:4]), reverse=True)

        current_count = 0

        for season in seasons:
            if season.year == self.year:
                self_count = current_count
            current_count += 1

        if self_count == 0:
            return seasons[1], None
        elif self_count == len(seasons)-1:
            return None, seasons[-2]
        else:
            return seasons[self_count+1], seasons[self_count-1]

class Division(models.Model):
    number = models.IntegerField()
    historic = models.CharField(max_length=3,blank=True,null=True,default=None)
    type = models.CharField(max_length=10,choices=(('Mixed','Mixed'),('Ladies','Ladies'),('Mens','Mens')))
    active = models.BooleanField(default=True)

    def __str__(self):
            return self.type + " Division " + str(self.number)

    def get_historic_name(self):
        return self.type + " Division " + self.historic

    def get_short_name(self):
        return self.type + " Div " + str(self.number)

    def get_division_url(self):
        if self.type == 'Mixed':
            url_string = 'X'
        elif self.type == 'Ladies':
            url_string = 'L'
        elif self.type == 'Mens':
            url_string = 'M'
        return url_string + str(self.number)

    def get_table(self, season=''):
        '''
        Get table for division. If no season is passed, current season and teams currently registered to division are used
        Otherwise, the table is constructed purely from fixtures so if there aren't any, a blank table will be returned
        Format of output:
            list of tuples -- tuples are team short name and dictionary of that team's stats -- 'Object' key holds the team object
        '''
        if season == '':
            season = Season.objects.get(current=True)
            teams = Team.objects.filter(division=self)
            fixtures = Fixture.objects.filter(season=season).filter(division=self)
        else:
            fixtures = Fixture.objects.filter(season=season).filter(division=self)
            teams = set()
            for fix in fixtures:
                teams.add(fix.home_team)
                teams.add(fix.away_team)

        teams = list(teams)
        team_names = [team.get_short_name() for team in teams]
        team_dict = {team:{'Played':0,'Won':0,'Drawn':0,'Lost':0,'PFor':0,'PAgainst':0,'Object':''} for team in team_names}
        concessions = []

        for fix in fixtures:

            home = fix.home_team.get_short_name()
            away = fix.away_team.get_short_name()

            if fix.status == 'Conceded (H)':
                concessions.append((fix.away_team, fix.home_team, "home"))
                team_dict[home]['Played'] += 1
                team_dict[away]['Played'] += 1
                team_dict[home]['Lost'] += 1
                team_dict[away]['Won'] += 1
                continue
            if fix.status == 'Conceded (A)':
                concessions.append((fix.home_team, fix.away_team, "away"))
                team_dict[home]['Played'] += 1
                team_dict[away]['Played'] += 1
                team_dict[home]['Won'] += 1
                team_dict[away]['Lost'] += 1
                continue

            if fix.home_points == 0 and fix.away_points == 0:
                continue

            if fix.home_points == fix.away_points:
                team_dict[home]['Drawn'] += 1
                team_dict[away]['Drawn'] += 1
            elif fix.home_points > fix.away_points:
                team_dict[home]['Won'] += 1
                team_dict[away]['Lost'] += 1
            elif fix.home_points < fix.away_points:
                team_dict[home]['Lost'] += 1
                team_dict[away]['Won'] += 1

            team_dict[home]['Played'] += 1
            team_dict[away]['Played'] += 1
            team_dict[home]['PFor'] += fix.home_points
            team_dict[home]['PAgainst'] += fix.away_points
            team_dict[away]['PFor'] += fix.away_points
            team_dict[away]['PAgainst'] += fix.home_points

        for concession in concessions:
            total_points = 0
            matches_played = 0
            for fix in fixtures:
                if fix.status != "Played":
                    continue
                if (concession[2] == "home" and fix.home_team == concession[1]) or (concession[2] == "away" and fix.away_team == concession[1]):
                    matches_played += 1
                    if concession[2] == "home":
                        total_points += fix.away_points
                    elif concession [2] == "away":
                        total_points += fix.home_points
            receiving_team = concession[0].get_short_name()
            if matches_played > 0:
                team_dict[receiving_team]['PFor'] += round(total_points/matches_played,1)

        for team in teams:
            team_dict[team.get_short_name()]['Object'] = team
            team_dict[team.get_short_name()]['Penalties'] = team.get_penalties(season)
            team_dict[team.get_short_name()]['PFor'] -= team.get_penalties(season)

        team_list = [(k,team_dict[k]) for k in team_dict]
        team_list.sort(key=lambda x: (x[1]['PFor'],x[1]['Won'],x[1]['Drawn']),reverse=True)
        #points_list = [x[1]['PFor'] for x in team_list]
        #if len(points_list) != len(list(set(points_list))):
            #team_list = sort_table(team_list)

        return team_list

class Club(models.Model):
    name = models.CharField(max_length=50)
    short_name = models.CharField(max_length=20)
    public_contact_name = models.CharField(max_length=30,blank=True,null=True)
    public_num = models.CharField(max_length=15,blank=True,null=True)
    public_email = models.EmailField(blank=True,null=True)
    contact1_name = models.CharField(max_length=30,blank=True,null=True)
    contact1_num = models.CharField(max_length=15,blank=True,null=True)
    contact1_landline = models.CharField(max_length=15,blank=True,null=True)
    contact1_email = models.EmailField(blank=True,null=True)
    contact2_name = models.CharField(max_length=30,blank=True,null=True)
    contact2_num = models.CharField(max_length=15,blank=True,null=True)
    contact2_landline = models.CharField(max_length=15,blank=True,null=True)
    contact2_email = models.EmailField(blank=True,null=True)
    website = models.URLField(blank=True,null=True)
    blurb = models.TextField(blank=True,null=True)
    active = models.BooleanField(default=True)
    club_notifications = models.BooleanField(default=False)
    captain_notifications = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def get_club_url(self):
        return urllib.parse.quote(self.name)

    def get_clubs_teams(self, version):

        teams = Team.objects.filter(club=self).filter(active=True)
        mixed = sorted([team.number for team in teams.filter(type="Mixed")])
        ladies = sorted([team.number for team in teams.filter(type="Ladies")])
        mens = sorted([team.number for team in teams.filter(type="Mens")])

        # Used in player model method get_team_dict
        # This counts the time a player has played for each team
        if version == "count_version":
            team_dict = {
                         "Mixed":{team:0 for team in mixed},
                         "Ladies":{team:0 for team in ladies},
                         "Mens":{team:0 for team in mens},
                         }
        # Otherwise just return the lists of teams
        else:
            team_dict = {"Mixed":mixed, "Ladies":ladies, "Mens":mens}

        return team_dict

    def get_clubs_player_stats(self):

        def update_dict(players,player_dict,team):

            for player in players:
                if player:
                    count = player_dict[player]["teams"][team.type][team.number]
                    if isinstance(count,int):
                        player_dict[player]["teams"][team.type][team.number] += 1
                    else:
                        if count == "X":
                            player_dict[player]["teams"][team.type][team.number] = "X (1)"
                        else:
                            num = int(count.replace("X (","").replace(")",""))
                            player_dict[player]["teams"][team.type][team.number] = "X (" + str(num + 1) + ")"

            return player_dict

        def simple_eligibility(player,team,mixed_nom,level_nom):

            if team.type != 'Mixed' and team.type != player.level:
                return False

            if team.type == 'Mixed' and mixed_nom and mixed_nom[0].number < team.number:
                return False
            elif team.type != 'Mixed' and level_nom and level_nom[0].number < team.number:
                return False

            return True

        current_season = Season.objects.get(current=True)
        club_fixtures = Fixture.objects.filter(season=current_season).filter(Q(home_team__club=self)|Q(away_team__club=self)).filter(status="played")
        club_teams = Team.objects.filter(club=self).filter(active=True)
        club_players = Player.objects.filter(club=self).order_by('level','name')
        team_dict = {t:0 for t in club_teams}
        player_dict = {}
        for player in club_players:
            mixed_nom = player.get_nominated_team("Mixed")
            level_nom = player.get_nominated_team(player.level)
            mixed_nom_str = ''
            level_nom_str = ''
            if mixed_nom:
                mixed_nom_str = str(mixed_nom[0].number) + cardinal_dict.get(str(mixed_nom[0].number),'th')
            if level_nom:
                level_nom_str = str(level_nom[0].number) + cardinal_dict.get(str(level_nom[0].number),'th')

            player_dict[player] = {"teams":{"Mixed":{},"Ladies":{},"Mens":{}},"noms":{"mixed":mixed_nom_str,"level":level_nom_str}}

            for team in club_teams:
                eligible = simple_eligibility(player,team,mixed_nom,level_nom)
                if not eligible:
                    player_dict[player]["teams"][team.type][team.number] = "X"
                else:
                    player_dict[player]["teams"][team.type][team.number] = 0

        # Don't forget that club teams can play eachother!
        for fixture in club_fixtures:
            if fixture.home_team.club == self:
                players = fixture.get_players("home")
                team = fixture.home_team
                player_dict = update_dict(players,player_dict,team)
                team_dict[team] += 1
            if fixture.away_team.club == self:
                players = fixture.get_players("away")
                team = fixture.away_team
                player_dict = update_dict(players,player_dict,team)
                team_dict[team] += 1

        for player in player_dict:
            for team in club_teams:
                if team_dict[team] > 0:
                    played = player_dict[player]["teams"][team.type][team.number]
                    if isinstance(played, str) and played != "X":
                        played = int(played.split("(")[1].replace(")",""))
                        percent = int(played/team_dict[team]*100)
                        player_dict[player]["teams"][team.type][team.number] = f"X ({played} ({percent}%))"
                    elif played != "X" and played != 0:
                        percent = int(played/team_dict[team]*100)
                        player_dict[player]["teams"][team.type][team.number] = f"{played} ({percent}%)"

        return player_dict

    def get_club_venues(self, season):

        # Get list of venues used
        venues = set()
        home_fixtures = Fixture.objects.filter(season=season).filter(home_team__club=self)
        for fix in home_fixtures:
            venues.add(fix.venue)

        return venues

class Administrator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)

class Member(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)

class Player(models.Model):
    name = models.CharField(max_length=30)
    level = models.CharField(max_length=10,choices=(('Ladies','Ladies'),('Mens','Mens')))
    club = models.ForeignKey(Club,on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def get_own_fixtures(self):

        current_season = Season.objects.get(current=True)
        club_fixtures = Fixture.objects.filter(season=current_season).filter(Q(home_team__club=self.club)|Q(away_team__club=self.club))

        player_fixtures = club_fixtures.filter(Q(home_player1=self)|Q(home_player2=self)|
                                               Q(home_player3=self)|Q(home_player4=self)|
                                               Q(home_player5=self)|Q(home_player6=self)|
                                               Q(away_player1=self)|Q(away_player2=self)|
                                               Q(away_player3=self)|Q(away_player4=self)|
                                               Q(away_player5=self)|Q(away_player6=self))

        return player_fixtures

    def get_team_dict(self):
        '''
            Pulls stats for player - times played for each team and teams nominated for
        '''

        player_fixtures = self.get_own_fixtures()
        team_dict = {}
        team_dict["teams"] = self.club.get_clubs_teams("count_version")

        # Count the times player has played for each team
        for fixture in player_fixtures:
            if self in fixture.get_players(side='home'):
                num = fixture.home_team.number
                type = fixture.home_team.type
            else:
                num = fixture.away_team.number
                type = fixture.away_team.type

            if num in team_dict["teams"][type].keys():
                team_dict["teams"][type][num] += 1

        for team_type in team_dict["teams"].keys():
            for team_num in team_dict["teams"][team_type].keys():
                team = Team.objects.get(club=self.club,number=team_num,type=team_type)
                if not self.check_eligibility(team):
                    count = team_dict["teams"][team_type][team_num]
                    if count == 0:
                        team_dict["teams"][team_type][team_num] = "X"
                    else:
                        team_dict["teams"][team_type][team_num] = "X (" + str(count) + ")"

        teams = Team.objects.filter(club=self.club)
        mixed_nom = ''
        level_nom = ''

        # Find the teams player has been nominated for - should be at most 1 mixed and 1 level
        for team in teams:
            player_fields = [team.nom_player1,team.nom_player2,team.nom_player3,team.nom_player4,team.nom_player5,team.nom_player6]
            for field in player_fields:
                if field == self:
                    if team.type == "Mixed":
                        mixed_nom = str(team.number)
                    else:
                        level_nom = str(team.number)

        if mixed_nom != '':
            mixed_nom += cardinal_dict.get(mixed_nom,'th')
        if level_nom != '':
            level_nom += cardinal_dict.get(level_nom,'th')

        team_dict["noms"] = {"mixed":mixed_nom,"level":level_nom}

        return team_dict

    def get_nominated_team(self,match_type):
        '''
            Returns mixed/level team player has been nominated for (or empty list if none)
        '''

        club_teams = Team.objects.filter(active=True).filter(type=match_type).filter(club=self.club)
        nom_team = club_teams.filter(Q(nom_player1=self)|Q(nom_player2=self)|
                                     Q(nom_player3=self)|Q(nom_player4=self)|
                                     Q(nom_player5=self)|Q(nom_player6=self))

        if nom_team:
            try:
                Team.objects.get(active=True, type=match_type, club=self.club, number=nom_team[0].number + 1)
                return nom_team
            except:
                return []
        return []

    def check_eligibility(self, team):
        '''
            Checks how many times player has played for teams above given one
            Return true if ok to play for given team or false if not eligible any more
        '''

        team_num = team.number
        team_type = team.type
        club_teams = Team.objects.filter(active=True).filter(type=team_type).filter(club=self.club)

        # Check if player has played in the wrong level league
        if team_type != 'Mixed' and team_type != self.level:
            return False

        # Find team player is nominated for (already filtered for league)
        nom_team = club_teams.filter(Q(nom_player1=self)|Q(nom_player2=self)|
                                     Q(nom_player3=self)|Q(nom_player4=self)|
                                     Q(nom_player5=self)|Q(nom_player6=self))

        # If they are nominated for a team, check whether this is higher than the team just played for
        if nom_team and nom_team[0].number < team_num:
            return False

        # Check whether player has played up too many times
        player_fixtures = self.get_own_fixtures()

        above_teams = 0
        for fixture in player_fixtures:
            if self in fixture.get_players(side='home'):
                num = fixture.home_team.number
                type = fixture.home_team.type
            else:
                num = fixture.away_team.number
                type = fixture.away_team.type

            if team_type == type and num < team_num:
                above_teams += 1

        if above_teams > max_plays_for_higher_teams:
            return False
        else:
            return True

    def deletable(self):

        if len(self.get_own_fixtures()) > 0:
            return False

        if len(self.get_nominated_team('Mixed')) > 0:
            return False

        if len(self.get_nominated_team(self.level)) > 0:
            return False

        return True

    def possible_duplicate(self):

        if len(self.get_own_fixtures()) == 1:
            return True

        return False

class Team(models.Model):
    division = models.ForeignKey(Division,on_delete=models.SET_NULL,blank=True,null=True)
    club = models.ForeignKey(Club,on_delete=models.CASCADE)
    type = models.CharField(max_length=10,choices=(('Mixed','Mixed'),('Ladies','Ladies'),('Mens','Mens')))
    number = models.IntegerField(default=1)
    penalties = models.IntegerField(default=0)
    captain = models.CharField(max_length=30,blank=True,null=True)
    captain_num = models.CharField(max_length=15,blank=True,null=True)
    captain_email = models.EmailField(blank=True,null=True)
    nom_player1 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="np1")
    nom_player2 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="np2")
    nom_player3 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="np3")
    nom_player4 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="np4")
    nom_player5 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="np5")
    nom_player6 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="np6")
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.club.short_name + " " + self.type + " " + str(self.number)

    def get_short_name(self):
        return self.club.short_name + " " + str(self.number)

    def get_fixtures(self, status=''):

        current_season = Season.objects.get(current=True)
        home_filter = Q(home_team=self.id)
        away_filter = Q(away_team=self.id)

        if not status:
            all_fix = list(Fixture.objects.filter(season=current_season).filter(home_filter|away_filter))
        else:
            all_fix = list(Fixture.objects.filter(season=current_season).filter(home_filter|away_filter).filter(status=status))

        all_fix.sort(key=lambda x: x.date_time)

        return all_fix

    def get_team_url(self):
        return urllib.parse.quote(str(self.id))

    def player_in_team(self, player):
        if self.nom_player1 == player:
            return True
        elif self.nom_player2 == player:
            return True
        elif self.nom_player3 == player:
            return True
        elif self.nom_player4 == player:
            return True
        elif self.nom_player5 == player:
            return True
        elif self.nom_player6 == player:
            return True
        return False

    def count_nominations(self):

        nom_count = 0

        if self.nom_player1:
            nom_count += 1
        if self.nom_player2:
            nom_count += 1
        if self.nom_player3:
            nom_count += 1
        if self.nom_player4:
            nom_count += 1
        if self.type == 'Mixed' and self.nom_player5:
            nom_count += 1
        if self.type == 'Mixed' and self.nom_player6:
            nom_count += 1

        return nom_count

    def last_team(self):

        try:
            team = Team.objects.get(club=self.club,type=self.type,number=self.number + 1)
            if team.active:
                return False
            else:
                return True
        except:
            return True

    def get_penalties(self, season):

        pens = Penalty.objects.filter(season=season).filter(team=self)
        total_pens = 0
        for pen in pens:
            total_pens += pen.penalty_value

        return total_pens

    def check_nominations(self):

        fixtures = self.get_fixtures()
        played = self.get_fixtures('Played')
        player_count = {self.nom_player1: 0,
                        self.nom_player2: 0,
                        self.nom_player3: 0,
                        self.nom_player4: 0}
        if self.type == 'Mixed':
            player_count.update({self.nom_player5: 0, self.nom_player6: 0})

        for fixture in fixtures:
            team_str = 'home' if fixture.home_team == self else 'away'
            counter = 7 if self.type == 'Mixed' else 5
            for i in range(1,counter):
                player = getattr(fixture, f'{team_str}_player{i}')
                if player in player_count:
                    player_count[player] += 1

        final_str = f'{len(fixtures)} - {len(played)}'
        for player in player_count:
            cur_count = player_count[player]
            final_str += f' - {round(cur_count/len(fixtures)*100,1)}% ({cur_count})'

        return final_str

class Venue(models.Model):
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=255)
    additional_information = models.CharField(max_length=255,blank=True,null=True)
    map = models.CharField(max_length=500,blank=True,null=True)

    def __str__(self):
        return self.name

    def get_venue_url(self):
        return urllib.parse.quote(self.name)

class Fixture(models.Model):

    fixStatuses = (('Unplayed','Unplayed'),
                   ('Postponed','Postponed'),
                   ('Proposed','New Date Proposed'),
                   ('Rearranged','Rearranged'),
                   ('Played','Played'),
                   ('Conceded (H)','Conceded (H)'),
                   ('Conceded (A)','Conceded (A)'))

    home_team = models.ForeignKey(Team,on_delete=models.CASCADE,related_name="home")
    away_team = models.ForeignKey(Team,on_delete=models.CASCADE,related_name="away")
    date_time = models.DateTimeField()
    end_time = models.TimeField(default=None,blank=True,null=True)
    season = models.ForeignKey(Season,on_delete=models.CASCADE)
    home_points = models.IntegerField(default=0,blank=True,null=True)
    away_points = models.IntegerField(default=0,blank=True,null=True)
    venue = models.ForeignKey(Venue,on_delete=models.SET_NULL,blank=True,null=True)
    division = models.ForeignKey(Division,on_delete=models.CASCADE)
    status = models.CharField(max_length=20,choices=fixStatuses,default='Unplayed')
    old_date_time = models.DateTimeField(blank=True,null=True)
    game_results = models.CharField(max_length=300,blank=True,null=True)

    home_player1 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="hp1")
    home_player2 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="hp2")
    home_player3 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="hp3")
    home_player4 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="hp4")
    home_player5 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="hp5")
    home_player6 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="hp6")
    away_player1 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="ap1")
    away_player2 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="ap2")
    away_player3 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="ap3")
    away_player4 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="ap4")
    away_player5 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="ap5")
    away_player6 = models.ForeignKey(Player,on_delete=models.SET_NULL,blank=True,null=True,related_name="ap6")

    def __str__(self):
        return self.division.type + " Div" + str(self.division.number) + " - " + self.home_team.__str__() + " v " + self.away_team.__str__()

    def updateable(self,user):
        '''
            Determines whether a fixture is updateable by the given user
        '''

        # If user is None nothing can be updated
        if not user:
            return False

        # If user is staff, can update everything
        if user.is_staff:
            return True

        try:
            admin = Administrator.objects.get(user=user)
        except:
            admin = Member.objects.get(user=user)

        # Away teams can update fixtures with new date proposed
        if admin.club == self.away_team.club and self.status == 'Proposed':
            return True
        # If club is not the home club, cannot update (bar the above condition)
        if admin.club != self.home_team.club:
            return False
        # Home club cannot update fixtures with new date proposed
        if admin.club == self.home_team.club and self.status == 'Proposed':
            return False
        # Played fixtures cannot be updated
        if self.status == 'Played':
            return False
        # Conceded fixtures cannot be updated
        if self.status == 'Conceded (H)':
            return False
        # Conceded fixtures cannot be updated
        if self.status == 'Conceded (A)':
            return False

        # Otherwise fixture is updateable
        return True

    def get_players(self,side='both'):
        '''
            Simply returns list of players that played in fixture - can be home, away or all players depending on input
        '''

        hp = [self.home_player1,self.home_player2,self.home_player3,self.home_player4]
        ap = [self.away_player1,self.away_player2,self.away_player3,self.away_player4]

        if self.division.type == 'Mixed':
            hp += [self.home_player5,self.home_player6]
            ap += [self.away_player5,self.away_player6]

        hp = [player for player in hp if player]
        ap = [player for player in ap if player]

        if side == 'both':
            return hp + ap
        elif side == 'home':
            return hp
        elif side == 'away':
            return ap

    def check_nomination_status(self):
        '''
            Checks whether this fixture is the third for any club and if so
            whether nominated players have played the correct amount of matches
            Applies penalty points if not
            NO LONGER REQUIRED AFTER CHANGE IN NOMINATION RULES
        '''
        ht = self.home_team
        at = self.away_team
        htf = ht.get_fixtures(status='Played')
        atf = at.get_fixtures(status='Played')
        teams = [(ht,htf),(at,atf)]
        violations = []

        for team in teams:
            if len(team[1]) == 3 and not team[0].last_team():
                player_dict = {team[0].nom_player1:0,team[0].nom_player2:0,team[0].nom_player3:0,team[0].nom_player4:0}
                if self.division.type == 'Mixed':
                    player_dict.update({team[0].nom_player5:0,team[0].nom_player6:0})
                for fix in team[1]:
                    for player in fix.get_players():
                        if player in player_dict.keys():
                            player_dict[player] += 1
                for player in player_dict.keys():
                    if player_dict[player] < 2:
                        violations.append((team[0],player))

        if violations:
            for violation in violations:
                email_notification('nomination_penalty', self, violation[0], player_name=violation[1].name)
                p = Penalty(season=self.season, team=violation[0], penalty_value=nomination_penalty_value, penalty_type='Nomination Violation', player=violation[1].name, fixture=self)
                p.save()

    def check_player_eligibility(self):
        '''
            Checks whether players are uneligible for these teams due to playing for higher teams
            Applies penalty points for any uneligible players played
        '''

        for player in self.get_players('home'):
            if not player.check_eligibility(self.home_team):
                email_notification('eligibility_penalty', self, self.home_team, player_name=player.name)
                p = Penalty(season=self.season, team=self.home_team, penalty_value=ineligible_player_penalty_value, penalty_type='Ineligible Player', player=player.name, fixture=self)
                p.save()
        for player in self.get_players('away'):
            if not player.check_eligibility(self.away_team):
                email_notification('eligibility_penalty', self, self.away_team, player_name=player.name)
                p = Penalty(season=self.season, team=self.away_team, penalty_value=ineligible_player_penalty_value, penalty_type='Ineligible Player', player=player.name, fixture=self)
                p.save()

    def get_scores(self):
        '''
            Adds match points to game scores for viewing match result
            This function will need to be changed if there is an change in the format of the matches
        '''

        game_split = self.game_results.split(',')

        if self.division.type == 'Mixed' and len(game_split) == 54:
            batched_games = {mixed_game_format[int(i/6)]: game_split[i:i + 6] for i in range(0, len(game_split), 6)}
        elif self.division.type == 'Mixed' and len(game_split) == 36:
            batched_games = {mixed_game_format[int(i/4)]: game_split[i:i + 4] for i in range(0, len(game_split), 4)}
        else:
            batched_games = {level_game_format[int(i/4)]: game_split[i:i + 4] for i in range(0, len(game_split), 4)}

        for game in batched_games.keys():

            rubbers = [batched_games[game][i:i+2] for i in range(0, len(batched_games[game]), 2)]
            home_score = 0
            away_score = 0

            for rubber in rubbers:

                if rubber[0] == '':
                    break
                elif rubber[0] == 'FA':
                    home_score += 1
                elif rubber[0] == 'FH':
                    away_score += 1
                elif int(rubber[0]) > int(rubber[1]):
                    home_score += 1
                else:
                    away_score += 1

            if self.division.type == 'Mixed':
                scoring_format = self.season.mixed_scoring
            else:
                scoring_format = level_scoring_format

            if scoring_format == 'point per game':
                if home_score > away_score:
                    batched_games[game] += [1,0]
                else:
                    batched_games[game] += [0,1]
            else:
                if home_score + away_score != len(rubbers):
                    if rubbers[0][0] == 'FH':
                        batched_games[game] += [len(rubbers),0]
                    else:
                        batched_games[game] += [0,len(rubbers)]
                else:
                    batched_games[game] += [home_score,away_score]

        return batched_games

    def get_eligible_players(self):
        '''
            Returns home players for dropdown on results form
            Will put nominated players for the team at the top of the list
            Will not include players nominated for other teams
            Will include players that are otherwise ineligible to catch illegal players
        '''

        if self.division.type == "Mixed":

            home_ladies = Player.objects.filter(club=self.home_team.club).filter(level="Ladies")
            home_men = Player.objects.filter(club=self.home_team.club).filter(level="Mens")

            eligible_home_ladies = [('','')]
            for player in home_ladies:
                nom_team = player.get_nominated_team("Mixed")
                if not nom_team:
                    eligible_home_ladies.append((player.id,player))
                elif nom_team[0] == self.home_team:
                    eligible_home_ladies.insert(1,(player.id,player))
                elif int(nom_team[0].number) > int(self.home_team.number):
                    eligible_home_ladies.append((player.id,player))
            eligible_home_men = [('','')]
            for player in home_men:
                nom_team = player.get_nominated_team("Mixed")
                if not nom_team:
                    eligible_home_men.append((player.id,player))
                elif nom_team[0] == self.home_team:
                    eligible_home_men.insert(1,(player.id,player))
                elif int(nom_team[0].number) > int(self.home_team.number):
                    eligible_home_men.append((player.id,player))
            return eligible_home_ladies, eligible_home_men

        else:
            if self.division.type == "Ladies":
                home_players = Player.objects.filter(club=self.home_team.club).filter(level="Ladies")
            else:
                home_players = Player.objects.filter(club=self.home_team.club).filter(level="Mens")

            eligible_home_players = [('','')]
            for player in home_players:
                nom_team = player.get_nominated_team(player.level)
                if not nom_team:
                    eligible_home_players.append((player.id,player))
                elif nom_team[0] == self.home_team:
                    eligible_home_players.insert(1,(player.id,player))
                elif int(nom_team[0].number) > int(self.home_team.number):
                    eligible_home_players.append((player.id,player))
            return eligible_home_players

class ClubNight(models.Model):

    club = models.ForeignKey(Club,on_delete=models.CASCADE)
    venue = models.ForeignKey(Venue,on_delete=models.CASCADE)
    timings = models.CharField(max_length=100)

class Penalty(models.Model):

    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    penalty_type = models.CharField(max_length=30)
    penalty_value = models.IntegerField()
    player = models.CharField(max_length=30, blank=True, null=True)
    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE)

class Performance(models.Model):

    team = models.ForeignKey(Team,on_delete=models.CASCADE)
    season = models.ForeignKey(Season,on_delete=models.CASCADE)
    division = models.ForeignKey(Division,on_delete=models.CASCADE)
    position = models.CharField(max_length=100)




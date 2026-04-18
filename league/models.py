from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
import urllib
import league.constants as constants
from django.core.exceptions import ObjectDoesNotExist

class LeagueSettings(models.Model):
    '''Holds league settings that need changing by league admins mid-sesason'''
    nomination_window_open = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'League settings'

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce single instance of class
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        '''Creates an instance if one doesn't already exist'''
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

class Season(models.Model):
    year = models.CharField(max_length=10) # Format: YYYY-YYYY
    current = models.BooleanField()
    archive_info = models.TextField(blank=True,null=True) # Notes e.g. on missing scores
    historic_divs = models.BooleanField(default=False) # In the past, there used to be A and B divisions on the same level
    # The way mixed matches were scored changed so this records the format for each season
    mixed_scoring = models.CharField(max_length=20,null=True,choices=constants.SCORING_OPTIONS,default=constants.SCORING_MIXED)

    def __str__(self):
        return self.year

class Division(models.Model):
    number = models.IntegerField()
    # In some seasons there were A and B divisions on the same level
    # the 'historic' attribute gives the actual name of the division in this instance and 'number' becomes irrelevant
    historic = models.CharField(max_length=3,blank=True,null=True,default=None)
    type = models.CharField(max_length=10,choices=(("Mixed","Mixed"),("Womens","Women's"),("Mens","Men's")))
    active = models.BooleanField(default=True)

    def __str__(self):
            return f'{self.get_type_display()} Division {self.number}'

    def get_historic_name(self):
        '''Used on the archive page'''
        return f'{self.get_type_display()} Division {self.historic}'

    def get_short_name(self):
        '''Used in on All Fixtures page'''
        return f'{self.get_type_display()} Div {self.number}'

    def get_division_url(self):
        type_dict = {'Mixed':'X', 'Womens':'W', 'Mens':'M'}
        return f"{type_dict[self.type]}{self.number}"

class Club(models.Model):
    name = models.CharField(max_length=50)
    short_name = models.CharField(max_length=20)
    # Contact information
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
    # Club still in existance
    active = models.BooleanField(default=True)
    # Notifications of upcoming fixtures by email
    club_notifications = models.BooleanField(default=False)
    captain_notifications = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def get_club_url(self):
        return urllib.parse.quote(self.name)

    def get_clubs_teams(self, version):
        '''Return club's team in various formats'''
        teams = Team.objects.filter(club=self).filter(active=True)
        mixed = sorted([team.number for team in teams.filter(type="Mixed")])
        womens = sorted([team.number for team in teams.filter(type="Womens")])
        mens = sorted([team.number for team in teams.filter(type="Mens")])

        # Used in player model method get_team_dict
        # This counts the time a player has played for each team
        if version == 'count':
            team_dict = {
                         "Mixed":{team:0 for team in mixed},
                         "Womens":{team:0 for team in womens},
                         "Mens":{team:0 for team in mens},
                         }      
        # Otherwise just return the lists of teams
        else:
            team_dict = {"Mixed":mixed, "Womens":womens, "Mens":mens}

        return team_dict
    
    def requires_noms(self):
        '''Checks whether club needs to submit nominations'''
        teams = Team.objects.filter(club=self)
        return any([team.number > 1 for team in teams])

class Administrator(models.Model):
    '''Club administrator - has access to all editable sections'''
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)

class Member(models.Model):
    '''Club member - has access to submit results and view roster only'''
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE)

class Player(models.Model):
    name = models.CharField(max_length=50)
    level = models.CharField(max_length=10,choices=(("Womens","Women's"),("Mens","Men's")))
    club = models.ForeignKey(Club,on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def get_own_fixtures(self):
        '''Gets fixtures player has played in'''
        current_season = Season.objects.get(current=True)
        club_fixtures = Fixture.objects.filter(season=current_season).filter(Q(home_team__club=self.club)|Q(away_team__club=self.club))

        player_fixtures = club_fixtures.filter(Q(home_player1=self)|Q(home_player2=self)|
                                               Q(home_player3=self)|Q(home_player4=self)|
                                               Q(home_player5=self)|Q(home_player6=self)|
                                               Q(away_player1=self)|Q(away_player2=self)|
                                               Q(away_player3=self)|Q(away_player4=self)|
                                               Q(away_player5=self)|Q(away_player6=self))

        return player_fixtures

    def get_nominated_team(self, match_type):
        '''Returns team for which player has been nominated - team type determined by input'''
        return TeamNomination.objects.filter(team__type=match_type, player=self, date_to=None, approved=True)

    def get_noms_strings(self):
        noms = [self.get_nominated_team('Mixed'), self.get_nominated_team(self.level)]
        noms_strings = ['','']
        cardinal_dict = {1:'st',2:'nd',3:'rd'}
        if noms[0]:
            noms_strings[0] = f'{noms[0][0].team.number}{cardinal_dict.get(noms[0][0].team.number, "th")}'
        if noms[1]:
            noms_strings[1] = f'{noms[1][0].team.number}{cardinal_dict.get(noms[1][0].team.number, "th")}'

        return noms_strings

    def check_eligibility(self, team):
        '''
            Checks how many times player has played for teams above given one
            Return true if ok to play for given team or false if not eligible any more
        '''

        # Check if player has played in the wrong level league
        if team.type != 'Mixed' and team.type != self.level:
            return False

        # Find team player is nominated for
        nom_team = TeamNomination.objects.filter(team__type=team.type, player=self, date_to=None, approved=True)

        # If they are nominated for a team, check whether this is higher than the team just played for
        if nom_team and nom_team[0].team.number < team.number:
            return False

        # Check whether player has played up too many times
        return self.get_higher_plays(team).count() <= constants.MAX_PLAYS_FOR_HIGHER_TEAMS

    def get_higher_plays(self, team):
        home_player_q = (
            Q(home_player1=self) | Q(home_player2=self) |
            Q(home_player3=self) | Q(home_player4=self) |
            Q(home_player5=self) | Q(home_player6=self) 
        )
        away_player_q = (
            Q(away_player1=self) | Q(away_player2=self) |
            Q(away_player3=self) | Q(away_player4=self) |
            Q(away_player5=self) | Q(away_player6=self)
        )

        return Fixture.objects.filter(
            Q(home_player_q & Q(home_team__number__lt=team.number) & Q(division__type=team.type)) |
            Q(away_player_q & Q(away_team__number__lt=team.number) & Q(division__type=team.type))
        )

    def deletable(self):
        '''Checks whether player has played any fixtures or been nominated, if so they can't be deleted'''
        if len(self.get_own_fixtures()) > 0:
            return False
        
        if TeamNomination.objects.filter(player=self).exists():
            return False

        return True

    def possible_duplicate(self):
        return len(self.get_own_fixtures()) == 1

class Team(models.Model):
    division = models.ForeignKey(Division,on_delete=models.SET_NULL,blank=True,null=True)
    club = models.ForeignKey(Club,on_delete=models.CASCADE)
    type = models.CharField(max_length=10,choices=(("Mixed","Mixed"),("Womens","Women's"),("Mens","Men's")))
    number = models.IntegerField(default=1)
    penalties = models.IntegerField(default=0)
    captain = models.CharField(max_length=30,blank=True,null=True)
    captain_num = models.CharField(max_length=15,blank=True,null=True)
    captain_email = models.EmailField(blank=True,null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.club.short_name} {self.get_type_display()} {self.number}'

    def get_short_name(self):
        return f'{self.club.short_name} {self.number}'

    def get_team_url(self):
        return urllib.parse.quote(str(self.id))

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

    def count_nominations(self):
        return TeamNomination.objects.filter(team=self, date_to=None, approved=True).count()

    def last_team(self):
        try:
            team = Team.objects.get(club=self.club,type=self.type,number=self.number + 1)
            return not team.active
        except ObjectDoesNotExist:
            return True

    def get_penalties(self, season):
        pens = Penalty.objects.filter(season=season).filter(team=self)
        return sum([pen.penalty_value for pen in pens])

    def check_nominations(self):

        noms = TeamNomination.objects.filter(team=self, approved=True)
        players_nom = {tm.player: {'pos':tm.position, 'count':0} for tm in noms}
        fixtures = self.get_fixtures()
        played = self.get_fixtures('Played')

        for fixture in fixtures:
            team_str = 'home' if fixture.home_team == self else 'away'
            counter = 7 if self.type == 'Mixed' else 5
            for i in range(1,counter):
                player = getattr(fixture, f'{team_str}_player{i}')
                if player in players_nom:
                    players_nom[player]['count'] += 1

        all_pos = {x['pos'] for x in players_nom.values()}
        position_dict = {pos:0 for pos in all_pos}
        for values in players_nom.values():
            position_dict[values['pos']] += position_dict[values['count']]
        
        final_str = f'{len(fixtures)} - {len(played)}'
        for pos, count in position_dict.items():
            final_str += f'{pos} - {round(count/len(fixtures)*100,1)}% ({count})'

        return final_str

    def get_nomination_stats(self):
        
        season = Season.objects.get(current=True)

        fixtures = (Fixture.objects
                    .filter(season=season)
                    .filter(Q(home_team=self) | Q(away_team=self))
                    .filter(status='Played'))
        
        total_matches = fixtures.count()
        nominations = TeamNomination.objects.filter(team=self, season=season)
        
        positions = {}
        for nomination in nominations:
            if nomination.position not in positions:
                positions[nomination.position] = []
            positions[nomination.position].append(nomination.player)
        
        stats = {}
        
        for position, players in positions.items():
            played = sum(
                1 for fix in fixtures
                if any(player in fix.get_players() for player in players)
            )
            stats[position] = {
                'players': players,
                'played': played,
                'total': total_matches,
                'percent': round(played / total_matches * 100, 1) if total_matches else 0,
            }
        
        return stats

class TeamNomination(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='nominations')
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    position = models.IntegerField()
    date_from = models.DateField()
    date_to = models.DateField(null=True, blank=True)
    approved = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)
    
    class Meta:
        unique_together = ['team', 'position', 'date_from', 'approved']

    def get_possible_replacements(self):
        club_players = Player.objects.filter(club=self.team.club, level=self.player.level)
        eligible_ids = [p.id for p in club_players if p.check_eligibility(self.team)]
        return Player.objects.filter(id__in=eligible_ids)

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
    date_time = models.DateTimeField(default=None,blank=True,null=True)
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
        '''Determines whether a fixture is updateable by the given user'''

        # If user is None nothing can be updated
        if not user:
            return False

        # If user is staff, can update everything
        if user.is_staff:
            return True

        try:
            admin = Administrator.objects.get(user=user)
        except ObjectDoesNotExist:
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
        # Played and Conceded fixtures cannot be updated
        if self.status in ['Played', 'Conceded (H)', 'Conceded (A)']:
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

    def get_eligible_players(self):
        '''
            Returns home players for dropdown on results form
            Will put nominated players for the team at the top of the list
            Will not include players nominated for other teams
            Will include players that are otherwise ineligible to catch illegal players
        '''

        home_women = Player.objects.filter(club=self.home_team.club).filter(level="Womens")
        home_men = Player.objects.filter(club=self.home_team.club).filter(level="Mens")
        home_noms = TeamNomination.objects.filter(team=self.home_team, date_to=None, approved=True)

        if self.division.type == "Mixed":

            nom_women = [tn.player for tn in home_noms if tn.player.level != 'Mens']
            nom_men = [tn.player for tn in home_noms if tn.player.level == 'Mens']

            all_women = nom_women + [woman for woman in home_women if woman not in nom_women]
            all_men = nom_men + [man for man in home_men if man not in nom_men]

            all_women = [(woman.id, woman) for woman in all_women]
            all_men = [(man.id, man) for man in all_men]

            return all_women, all_men

        else:
            
            nom_players = [tn.player for tn in home_noms]
            
            if self.division.type == "Womens":
                all_players = nom_players + [woman for woman in home_women if woman not in home_noms]
            else:
                all_players = nom_players + [man for man in home_men if man not in home_noms]

            return [(player.id, player) for player in all_players]

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
    fixture = models.ForeignKey(Fixture, blank=True, null=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'Penalties'

class Performance(models.Model):

    team = models.ForeignKey(Team,on_delete=models.CASCADE)
    season = models.ForeignKey(Season,on_delete=models.CASCADE)
    division = models.ForeignKey(Division,on_delete=models.CASCADE)
    position = models.CharField(max_length=100)

class PendingPlayerVerification(models.Model):
    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE)
    submitted_name = models.CharField(max_length=50)
    level = models.CharField(max_length=10,choices=(("Mixed","Mixed"),("Womens","Women's"),("Mens","Men's")))
    suggested_player = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_player = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_verifications')


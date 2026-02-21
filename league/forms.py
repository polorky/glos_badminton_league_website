from django.forms import ModelForm
from django import forms
from .models import Fixture, Club, ClubNight, Player, Venue, Team
from django.core.exceptions import ValidationError
from fuzzywuzzy import fuzz

fuzzy_match_ratio = 85
alt_names_list = (('David','Dave'),('Stuart','Stu'),('Richard','Rich'),('Alexander','Alex'),('Christopher','Chris'),('Andrew','Andy'),('Daniel','Dan'),('Matthew','Matt'),
('Michael','Mike'),('Oliver','Oli'),('Oliver','Ollie'),('Phillip','Phil'),('Philip','Phil'),('Robert','Rob'),('Simon','Si'),('Thomas','Tom'),('William','Will'),
('Rebecca','Becky'))

def clean_fixture_form(cleaned_data,match_type,total_pts,hp_fields,fix_inst):

    hpts = cleaned_data.get('home_points')
    apts = cleaned_data.get('away_points')

    # Check score totals - MUST BE CORRECT
    if hpts + apts != total_pts:
        raise ValidationError(['points','Points do not add up to the correct amount'])

    hps = [cleaned_data[player] for player in hp_fields]
    player_errors = []

    # Check all home players are entered and different - CAN BE BLANK BUT NOT DUPLICATED
    for hp in hp_fields:
        if not cleaned_data[hp] and not cleaned_data['player_name_check']:
            player_errors.append('You have not entered all home players')
    valid_hps = [player for player in hps if player]
    if len(valid_hps) != len(list(set(valid_hps))):
        raise ValidationError(['player','You have duplicated home player(s)'])

    # Check away players are not duplicated, are right gender and exist - CAN BE OVERRIDDEN
    player_errors += check_away_players(cleaned_data,match_type,fix_inst)

    # Check game scores - CAN BE OVERRIDDEN
    game_results = [cleaned_data[field] for field in cleaned_data.keys() if 'player' not in field and 'points' not in field and 'score' not in field]
    game_errors, score = check_game_results_new(game_results, match_type)

    # If errors and overrides not checked, raise error
    if player_errors and not cleaned_data['player_name_check'] and game_errors and not cleaned_data['score_check']:
        player_errors = ['Away Player Error: ' + x for x in player_errors]
        game_errors = ['Game Error: ' + x for x in game_errors]
        raise ValidationError(['player'] + player_errors + game_errors)

    # If player errors and player override not checked, raise error
    if player_errors and not cleaned_data['player_name_check']:
        raise ValidationError(['player',player_errors])
    # If game errors and game override not checked, raise error
    if game_errors and not cleaned_data['score_check']:
        raise ValidationError(['game',game_errors])

    # Overall score from game scores must match overall score given in separate field - CANNOT BE OVERRIDDEN
    if score[0] != hpts or score[1] != apts:
        raise ValidationError(['game','Game results do not match the overall score (current total ' + str(score[0]) + ':' + str(score[1]) + ')'])

def check_away_players(data,match_type,fixture):
    '''
        Validation function for checking away player names
        Looks for existing players that match or closely match
        If none are found, return errors messages unless checkbox is ticked
    '''

    player_errors = []
    players_found = []
    players = ['away_player1','away_player2','away_player3','away_player4']
    club = fixture.away_team.club
    new_player_check = data['player_name_check']

    if match_type == "Mixed":
        players += ['away_player5','away_player6']

    for player_title in players:
        player_name = data.get(player_title)
        if not player_name:
            if not new_player_check:
                player_errors.append("Away Player " + player_title[-1] + " has not been entered, please tick the box below to confirm this is correct")
            continue

        try:
            player = Player.objects.get(club=club,name=player_name)
            if player in players_found:
                player_errors.append("There are duplicated away players")
            else:
                players_found.append(player)

            if match_type == "Mixed":
                if player_title[-1] in ['1','2','3'] and player.level == "Mens":
                    player_errors.append("Away Player " + player_title[-1] + " found but is recorded as a man, please check you have entered them in the correct position")
                if player_title[-1] in ['4','5','6'] and player.level == "Ladies":
                    player_errors.append("Away Player " + player_title[-1] + " found but is recorded as a lady, please check you have entered them in the correct position")
            else:
                if fixture.division.type != player.level:
                    if fixture.division.type == "Ladies":
                        player_errors.append("Away Player " + player_title[-1] + " found but is recorded as playing in mens league")
                    else:
                        player_errors.append("Away Player " + player_title[-1] + " found but is recorded as playing in ladies league")
        except:
            if new_player_check:
                continue
            fuzzy_max = ('',0)
            for player in Player.objects.filter(club=club):
                if fuzz.ratio(player_name.upper(),player.name.upper()) > fuzzy_max[1]:
                    fuzzy_max = (player,fuzz.ratio(player_name.upper(),player.name.upper()))
            if fuzzy_max[1] < fuzzy_match_ratio:
                player_found = False
                for name_tuple in alt_names_list:
                    if name_tuple[0] in player_name:
                        try:
                            player = Player.objects.get(club=club,name=player_name.replace(name_tuple[0],name_tuple[1]))
                            player_found = True
                            break
                        except:
                            pass
                    elif name_tuple[1] in player_name:
                        try:
                            player = Player.objects.get(club=club,name=player_name.replace(name_tuple[1],name_tuple[0]))
                            player_found = True
                            break
                        except:
                            pass
                if not player_found:
                    player_errors.append("Away Player " + player_title[-1] + " has not been recognised, please double check. \
                    If you are sure that you have entered the name correctly please tick the box below")
                    continue
            else:
                player = fuzzy_max[0]
            if player in players_found:
                player_errors.append("There are duplicated away players")
            else:
                players_found.append(fuzzy_max[0])

    return player_errors

def check_game_results_old(game_results, match_type):
    '''
    Validate the scores submitted for matches
    Used when mixed matches were best of three rubbers
    '''

    def check_scores(pair, errors):
        '''
        Checks numeric values for a rubber's scores
        '''

        # If one score is 21 and other score is not 23 but is over 19, raise error
        if pair[0] == '21' and pair[1] != '23' and int(pair[1]) > 19:
            errors.append('Game ' + game + ' rubber ' + rubber + ' - score looks wrong, please check')
        elif pair[1] == '21' and pair[0] != '23' and int(pair[0]) > 19:
            errors.append('Game ' + game + ' rubber ' + rubber + ' - score looks wrong, please check')

        # If one of the scores is over 21, check setting...
        if int(pair[0]) > 21 or int(pair[1]) > 21:
            # Difference must be two unless one score is 30, if not raise error
            if abs(int(pair[0]) - int(pair[1])) != 2 and pair[0] != '30' and pair[1] != '30':
                errors.append('Game ' + game + ' rubber ' + rubber + ' - setting score looks wrong, please check')
            # If one score hit 30 the other one must be 28 or 29, if not raise error
            elif pair[0] == '30' and pair[1] not in ['28','29']:
                errors.append('Game ' + game + ' rubber ' + rubber + ' - setting score looks wrong, please check')
            elif pair[1] == '30' and pair[0] not in ['28','29']:
                errors.append('Game ' + game + ' rubber ' + rubber + ' - setting score looks wrong, please check')

        return errors

    paired = [game_results[x:x + 2] for x in range(0, len(game_results), 2)]
    errors = []
    score = [0,0]

    if match_type != 'Mixed':

        for i, pair in enumerate(paired):

            game = str((i+2) // 2)
            rubber = str(i % 2 + 1)

            # Check the values are numeric or forfeits, otherwise raise an error
            if pair[0] not in ('FH','FA') and (int(pair[0]) < 0 or int(pair[0]) > 30):
                return ['Game ' + game + ' rubber ' + rubber + ' - home score is not a number or FH/FA'], score
            elif pair[1] not in ('FH','FA') and (int(pair[1]) < 0 or int(pair[1]) > 30):
                return ['Game ' + game + ' rubber ' + rubber + ' - away score is not a number or FH/FA'], score

            # Check numeric values match expected scoring
            if pair[0] not in ('FH','FA'):
                errors = check_scores(pair, errors)

            # Work out whether rubber scores for home or away
            if pair[0] == 'FH':
                score[1] += 1
            elif pair[0] == 'FA':
                score[0] += 1
            elif int(pair[0]) > int(pair[1]):
                score[0] += 1
            elif int(pair[0]) < int(pair[1]):
                score[1] += 1
            else:
                errors.append('Game ' + game + ' rubber ' + rubber + ' - score looks wrong, please check')

    else:

        for i, pair in enumerate(paired):

            game = str((i+3) // 3)
            rubber = str(i % 3 + 1)

            # Check the values are numeric or forfeits or are BOTH blank, otherwise raise an error
            if pair[0] not in ('FH','FA','') and (int(pair[0]) < 0 or int(pair[0]) > 31):
                return ['Game ' + game + ' rubber ' + rubber + ' - home score is not a number or FH/FA'], score
            elif pair[1] not in ('FH','FA','') and (int(pair[1]) < 0 or int(pair[1]) > 31):
                return ['Game ' + game + ' rubber ' + rubber + ' - away score is not a number or FH/FA'], score
            elif (pair[0] == '' and pair[1] != '') or (pair[1] != '' and pair[0] == ''):
                return ['Game ' + game + ' rubber ' + rubber + ' - one score is blank but the other is not, please correct'], score

            # Check numeric values match expected scoring
            if pair[0] not in ('FH','FA',''):
                if pair[0] == '30' or pair[1] == '30':
                    if paired[i+1][0] == '':
                        continue
                errors = check_scores(pair, errors)

        rubbers = [paired[i:i+3] for i in range(0,27,3)]

        for i, rubber in enumerate(rubbers):

            # If any rubber forfeited, add point to other team
            if rubber[0][0] == 'FH' or rubber[1][0] == 'FH' or rubber[2][0] == 'FH':
                score[1] += 1
            elif rubber[0][0] == 'FA' or rubber[1][0] == 'FA' or rubber[2][0] == 'FA':
                score[0] += 1
            else:
                # If second rubber is blank, the third rubber should also be blank and the first rubber should be to 30 (this can be overridden)
                if rubber[1][0] == '':
                    if rubber[2][0] != '':
                        return ['Game ' + str(i+1) + ' - there appears to be a score in the third rubber but not the second, please correct'], score
                    if rubber[0][0] != '30' and rubber[0][1] != '30':
                        errors.append('Game ' + str(i+1) + ' - this game appears to have been played to one rubber but no score of 30 was found, if this is correct please tick the box and resubmit')

                # If the third rubber is blank, the first two rubbers should have been won by the same team
                elif rubber[2][0] == '':
                    if int(rubber[0][0]) > int(rubber[0][1]) and int(rubber[1][0]) < int(rubber[1][1]):
                        return ['Game ' + str(i+1) + ' - the first two games were won by different teams but there is no score for the third game, if it was forfeited please enter either "FH" or "FA"'], score
                    elif int(rubber[0][0]) < int(rubber[0][1]) and int(rubber[1][0]) > int(rubber[1][1]):
                        return ['Game ' + str(i+1) + ' - the first two games were won by different teams but there is no score for the third game, if it was forfeited please enter either "FH" or "FA"'], score

                # Work out which team won the game by checking third rubber, if blank, check who won the first, if not point goes to winner of decider
                if rubber[2][0] == '' and int(rubber[0][0]) > int(rubber[0][1]):
                    score[0] += 1
                elif rubber[2][0] == '' and int(rubber[0][0]) < int(rubber[0][1]):
                    score[1] += 1
                elif rubber[2][0] == '' and int(rubber[0][0]) == int(rubber[0][1]):
                    pass
                elif int(rubber[2][0]) > int(rubber[2][1]):
                    score[0] += 1
                elif int(rubber[2][0]) < int(rubber[2][1]):
                    score[1] += 1
                else:
                    errors.append('Game ' + str(i+1) + ' - score looks wrong, please check')

    return errors, score

def check_game_results_new(game_results, match_type):
    '''
    Validate the scores submitted for matches
    '''

    def check_scores(pair, errors):
        '''
        Checks numeric values for a rubber's scores
        '''

        # If one score is 21 and other score is not 23 but is over 19, raise error
        if pair[0] == '21' and pair[1] != '23' and int(pair[1]) > 19:
            errors.append('Game ' + game + ' rubber ' + rubber + ' - score looks wrong, please check')
        elif pair[1] == '21' and pair[0] != '23' and int(pair[0]) > 19:
            errors.append('Game ' + game + ' rubber ' + rubber + ' - score looks wrong, please check')

        # If one of the scores is over 21, check setting...
        if int(pair[0]) > 21 or int(pair[1]) > 21:
            # Difference must be two unless one score is 30, if not raise error
            if abs(int(pair[0]) - int(pair[1])) != 2 and pair[0] != '30' and pair[1] != '30':
                errors.append('Game ' + game + ' rubber ' + rubber + ' - setting score looks wrong, please check')
            # If one score hit 30 the other one must be 28 or 29, if not raise error
            elif pair[0] == '30' and pair[1] not in ['28','29']:
                errors.append('Game ' + game + ' rubber ' + rubber + ' - setting score looks wrong, please check')
            elif pair[1] == '30' and pair[0] not in ['28','29']:
                errors.append('Game ' + game + ' rubber ' + rubber + ' - setting score looks wrong, please check')

        return errors

    paired = [game_results[x:x + 2] for x in range(0, len(game_results), 2)]
    errors = []
    score = [0,0]

    for i, pair in enumerate(paired):

        # Work out game and rubber
        game = str((i+2) // 2)
        rubber = str(i % 2 + 1)

        # Check the values are numeric or forfeits, otherwise raise an error
        if pair[0] not in ('FH','FA') and (int(pair[0]) < 0 or int(pair[0]) > 30):
            return ['Game ' + game + ' rubber ' + rubber + ' - home score is not a number or FH/FA'], score
        elif pair[1] not in ('FH','FA') and (int(pair[1]) < 0 or int(pair[1]) > 30):
            return ['Game ' + game + ' rubber ' + rubber + ' - away score is not a number or FH/FA'], score

        # Check numeric values match expected scoring
        if pair[0] not in ('FH','FA'):
            errors = check_scores(pair, errors)

        # Work out whether rubber scores for home or away
        if pair[0] == 'FH':
            score[1] += 1
        elif pair[0] == 'FA':
            score[0] += 1
        elif int(pair[0]) > int(pair[1]):
            score[0] += 1
        elif int(pair[0]) < int(pair[1]):
            score[1] += 1
        else:
            errors.append('Game ' + game + ' rubber ' + rubber + ' - score looks wrong, please check')

    return errors, score

class ClubForm(ModelForm):

    class Meta:
        model = Club
        fields = ['public_contact_name','public_email','public_num','website','blurb','contact1_name','contact1_num','contact1_landline','contact1_email',
                  'contact2_name','contact2_num','contact2_landline','contact2_email','club_notifications','captain_notifications']
        labels = {'public_contact_name':'Club Contact Name (publicly available)',
                  'public_email':'Club Email (publicly available)',
                  'public_num':'Club Phone Number (publicly available)',
                  'contact1_name':'1st League Contact Name',
                  'contact1_num':'1st League Contact Mobile Number',
                  'contact1_landline':'1st League Contact Home Number',
                  'contact1_email':'1st League Contact Email',
                  'contact2_name':'2nd League Contact Name',
                  'contact2_num':'2nd League Contact Mobile Number',
                  'contact2_landline':'2nd League Contact Home Number',
                  'contact2_email':'2nd League Contact Email',
                  'website':'Website (publicly available)',
                  'blurb':'Club Information (publicly available)',
                  'club_notifications':'Fixture Notifications (Club Contacts)',
                  'captain_notifications':'Fixture Notifications (Captains)'}

class VenueForm(ModelForm):

    class Meta:
        model = Venue
        fields = ['name','address','additional_information']
        labels = {'additional_information':'Additional Information'}
        widgets = {'address':forms.Textarea(attrs={'rows': '5'}), 'additional_information':forms.Textarea(attrs={'rows': '2'})}

class TeamForm(ModelForm):

    class Meta:
        model = Team
        fields = ['captain','captain_num','captain_email']

class PlayerForm(ModelForm):

    class Meta:
        model = Player
        fields = ['name','level']

class MixedNominateForm(ModelForm):

    class Meta:
        model = Team
        fields = ['nom_player1','nom_player2','nom_player3','nom_player4','nom_player5','nom_player6']

    def clean(self):
        cleaned_data = super().clean()
        for i, field in enumerate(cleaned_data.keys()):
            player = cleaned_data[field]
            if not player:
                raise ValidationError('Player ' + str(i+1) + ' has not been nominated')
            club = player.club
            teams = Team.objects.filter(club=club).filter(type='Mixed')
            for team in teams:
                if self.instance.id == team.id:
                    continue
                if team.player_in_team(player):
                    raise ValidationError('Player ' + str(i+1) + ' has already been nominated for a team')

class LevelNominateForm(ModelForm):

    class Meta:
        model = Team
        fields = ['nom_player1','nom_player2','nom_player3','nom_player4']

    def clean(self):
        cleaned_data = super().clean()
        for i, field in enumerate(cleaned_data.keys()):
            player = cleaned_data[field]
            if not player:
                raise ValidationError('Player ' + str(i+1) + ' has not been nominated')
            club = player.club
            teams = Team.objects.filter(club=club).filter(type=player.level)
            for team in teams:
                if self.instance.id == team.id:
                    continue
                if team.player_in_team(player):
                    raise ValidationError('Player ' + str(i+1) + ' has already been nominated for a team')

class RescheduleForm(ModelForm):

    class Meta:
        model = Fixture
        fields = ['date_time','end_time','venue']
        widgets = {'date_time':forms.DateTimeInput(attrs={'type': 'datetime-local'}),
                   'end_time':forms.TimeInput(attrs={'type': 'time'})}

class MixedFixtureForm(ModelForm):

    player_name_check = forms.BooleanField(required=False)
    score_check = forms.BooleanField(required=False)
    away_player1 = forms.CharField(required=False, max_length=30)
    away_player2 = forms.CharField(required=False, max_length=30)
    away_player3 = forms.CharField(required=False, max_length=30)
    away_player4 = forms.CharField(required=False, max_length=30)
    away_player5 = forms.CharField(required=False, max_length=30)
    away_player6 = forms.CharField(required=False, max_length=30)
    g1r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g1r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g1r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g1r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g1r3h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g1r3a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g2r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g2r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g2r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g2r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g2r3h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g2r3a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g3r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g3r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g3r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g3r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g3r3h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g3r3a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g4r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g4r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g4r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g4r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g4r3h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g4r3a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g5r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g5r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g5r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g5r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g5r3h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g5r3a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g6r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g6r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g6r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g6r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g6r3h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g6r3a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g7r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g7r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g7r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g7r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g7r3h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g7r3a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g8r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g8r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g8r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g8r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g8r3h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g8r3a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g9r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g9r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g9r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g9r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g9r3h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    #g9r3a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))

    class Meta:
        model = Fixture
        fields = ['home_points','away_points','home_player1','home_player2','home_player3','home_player4','home_player5','home_player6']

    def clean(self):
        cleaned_data = super().clean()
        hp_fields = ['home_player1','home_player2','home_player3','home_player4','home_player5','home_player6']
        clean_fixture_form(cleaned_data,'Mixed',18,hp_fields,self.instance)

class LevelFixtureForm(ModelForm):

    player_name_check = forms.BooleanField(required=False)
    score_check = forms.BooleanField(required=False)
    away_player1 = forms.CharField(max_length=30)
    away_player2 = forms.CharField(max_length=30)
    away_player3 = forms.CharField(max_length=30)
    away_player4 = forms.CharField(max_length=30)
    g1r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g1r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g1r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g1r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g2r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g2r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g2r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g2r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g3r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g3r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g3r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g3r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g4r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g4r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g4r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g4r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g5r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g5r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g5r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g5r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g6r1h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g6r1a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g6r2h = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))
    g6r2a = forms.CharField(required=False, max_length=2, widget=forms.TextInput(attrs={'style': 'width:4ch'}))

    class Meta:
        model = Fixture
        fields = ['home_points','away_points','home_player1','home_player2','home_player3','home_player4']

    def clean(self):
        cleaned_data = super().clean()
        hp_fields = ['home_player1','home_player2','home_player3','home_player4']
        clean_fixture_form(cleaned_data,'Level',12,hp_fields,self.instance)

class ClubNightForm(ModelForm):

    class Meta:
        model = ClubNight
        fields = ['venue','timings']

class EmailForm(forms.Form):

    subject = forms.CharField()
    body = forms.CharField(widget=forms.Textarea)
    html = forms.CharField(widget=forms.Textarea,required=False)
    replyto = forms.ChoiceField(choices=[('glosbadwebsite@gmail.com','glosbadwebsite@gmail.com'),
                                         ('GlosBadCorrespondence@outlook.com','GlosBadCorrespondence@outlook.com'),
                                         ('GlosBadFixtures@outlook.com','GlosBadFixtures@outlook.com')])

class DuplicatePlayerForm(forms.Form):

    def __init__(self,*args,**kwargs):

        if 'player' in kwargs:
            player = kwargs.pop('player')
            players = kwargs.pop('players')
            super(DuplicatePlayerForm,self).__init__(*args, **kwargs)
            self.fields['incorrect_player'].choices = player
            self.fields['correct_player'].choices = players
        else:
            super(DuplicatePlayerForm,self).__init__(*args, **kwargs)

    incorrect_player = forms.ChoiceField(choices=[])
    correct_player = forms.ChoiceField(choices=[])

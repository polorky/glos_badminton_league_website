from django.forms import ModelForm, BaseFormSet, Form, IntegerField, ChoiceField, CharField, formset_factory, modelformset_factory
from django import forms
from .models import Fixture, Club, ClubNight, Player, Venue, Team, TeamNomination
from django.core.exceptions import ValidationError
import league.constants as constants
from .utilities.player import find_away_players


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

class NominationForm(forms.ModelForm):
    class Meta:
        model = TeamNomination
        fields = ['player','notes']

    def __init__(self, *args, players=None, variant='Team', **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['player'].queryset = players
        if variant == 'Team':
            del self.fields['notes']

NominationFormSet = modelformset_factory(
    TeamNomination,
    form=NominationForm,
    extra=0,
)            

class RescheduleForm(ModelForm):

    class Meta:
        model = Fixture
        fields = ['date_time','end_time','venue']
        widgets = {'date_time':forms.DateTimeInput(attrs={'type': 'datetime-local'}),
                   'end_time':forms.TimeInput(attrs={'type': 'time'})}

class FixtureForm(ModelForm):

    player_name_check = forms.BooleanField(required=False)
    score_check = forms.BooleanField(required=False)
    away_player1 = forms.CharField(max_length=30, required=False)
    away_player2 = forms.CharField(max_length=30, required=False)
    away_player3 = forms.CharField(max_length=30, required=False)
    away_player4 = forms.CharField(max_length=30, required=False)

    class Meta:
        model = Fixture
        fields = ['home_points','away_points']

    def clean(self):
        cd = super().clean()

        # Check score totals - MUST BE CORRECT
        tp = constants.TOTAL_POINTS_MIXED if self.instance.division.type == 'Mixed' else constants.TOTAL_POINTS_LEVEL
        if cd.get('home_points') + cd.get('away_points') != tp:
            raise ValidationError(['points','Points do not add up to the correct amount'])

        player_errors = []

        # Check all home players are entered and different - CAN BE BLANK BUT NOT DUPLICATED
        hps = [k for k in cd.keys() if 'home' in k]
        for hp in hps:
            if not cd[hp] and not cd['player_name_check']:
                player_errors.append('You have not entered all home players')
        valid_hps = [player for player in hps if player]
        if len(valid_hps) != len(list(set(valid_hps))):
            raise ValidationError(['player','You have duplicated home player(s)'])
        
        # Check away players are not duplicated, are right gender and exist - CAN BE OVERRIDDEN
        players_found, player_errors = find_away_players(cd, self.instance)

        # If errors and overrides not checked, raise error
        if player_errors and not cd['player_name_check']:
            raise ValidationError(['player',player_errors])

        cd['players_found'] = players_found

        return cd

class MixedFixtureForm(FixtureForm):

    away_player5 = forms.CharField(max_length=30, required=False)
    away_player6 = forms.CharField(max_length=30, required=False)

    class Meta:
        model = Fixture
        fields = ['home_points','away_points','home_player1','home_player2','home_player3','home_player4','home_player5','home_player6']

class LevelFixtureForm(FixtureForm):

    class Meta:
        model = Fixture
        fields = ['home_points','away_points','home_player1','home_player2','home_player3','home_player4']

class BaseScoreFormSet(BaseFormSet):
    
    def clean(self):
        super().clean()

        all_scores = []
        for form in self.forms:
            cd = form.cleaned_data
            if cd['forfeit']:
                all_scores.append([cd['forfeit'], cd['forfeit']])
            else:
                all_scores.append([cd['home_score'], cd['away_score']])
        
        # Check game scores - CAN BE OVERRIDDEN
        game_errors = self.check_game_results(all_scores)

        # If game errors and game override not checked, raise error
        if game_errors and not cd['score_check']:
            raise ValidationError(['game',game_errors])
        
    def check_game_results(self, game_results):
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

        errors = []

        for i, pair in enumerate(game_results):

            # Work out game and rubber
            game = str((i+2) // 2)
            rubber = str(i % 2 + 1)

            # Check numeric values match expected scoring
            if pair[0] not in ('FH','FA'):
                errors = check_scores(pair, errors)

            # Check scores aren't the same
            if int(pair[0]) == int(pair[1]):
                errors.append('Game ' + game + ' rubber ' + rubber + ' - scores the same, please check')

        return errors

class ScoreForm(Form):
    home_score = IntegerField(
        min_value=0, max_value=30, required=False,
        widget=forms.NumberInput(attrs={'style': 'width:5ch', 'placeholder': 'H'})
    )
    away_score = IntegerField(
        min_value=0, max_value=30, required=False,
        widget=forms.NumberInput(attrs={'style': 'width:5ch', 'placeholder': 'A'})
    )
    forfeit = ChoiceField(
        choices=[('', 'None'), ('FH', 'Home'), ('FA', 'Away')],
        required=False,
        widget=forms.Select(attrs={'style': 'width:8ch'})
    )

# Formsets for different match types
MixedScoreFormSet = formset_factory(ScoreForm, extra=18, formset=BaseScoreFormSet)  # 9 games x 2 rubbers
LevelScoreFormSet = formset_factory(ScoreForm, extra=12, formset=BaseScoreFormSet)  # 6 games x 2 rubbers

class ClubNightForm(ModelForm):

    class Meta:
        model = ClubNight
        fields = ['venue','timings']

class EmailForm(Form):

    subject = CharField()
    body = CharField(widget=forms.Textarea)
    html = CharField(widget=forms.Textarea,required=False)
    replyto = ChoiceField(choices=[('glosbadwebsite@gmail.com','glosbadwebsite@gmail.com'),
                                   ('GlosBadCorrespondence@outlook.com','GlosBadCorrespondence@outlook.com'),
                                   ('GlosBadFixtures@outlook.com','GlosBadFixtures@outlook.com')])

class DuplicatePlayerForm(Form):

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


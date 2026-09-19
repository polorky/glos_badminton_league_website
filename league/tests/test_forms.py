from django.test import TestCase
from league.models import Season, Division, Club, Team, Fixture, Player
from league.forms import LevelFixtureForm, MixedFixtureForm, LevelScoreFormSet


# ---------------------------------------------------------------------------
# Helpers shared across fixture form tests
# ---------------------------------------------------------------------------

def make_level_fixture():
    season = Season.objects.create(year='2024/25', current=True)
    division = Division.objects.create(number=1, type='Open')
    home_club = Club.objects.create(name='Home Club', short_name='HC')
    away_club = Club.objects.create(name='Away Club', short_name='AC')
    home_team = Team.objects.create(number=1, type='Open', club=home_club, division=division)
    away_team = Team.objects.create(number=1, type='Open', club=away_club, division=division)
    fixture = Fixture.objects.create(
        season=season, division=division,
        home_team=home_team, away_team=away_team,
    )
    return fixture, home_club, away_club


def make_mixed_fixture():
    season = Season.objects.create(year='2024/25', current=True)
    division = Division.objects.create(number=1, type='Mixed')
    home_club = Club.objects.create(name='Home Club', short_name='HC')
    away_club = Club.objects.create(name='Away Club', short_name='AC')
    home_team = Team.objects.create(number=1, type='Mixed', club=home_club, division=division)
    away_team = Team.objects.create(number=1, type='Mixed', club=away_club, division=division)
    fixture = Fixture.objects.create(
        season=season, division=division,
        home_team=home_team, away_team=away_team,
    )
    return fixture, home_club, away_club


# ---------------------------------------------------------------------------
# LevelFixtureForm
# ---------------------------------------------------------------------------

class TestLevelFixtureForm(TestCase):

    def setUp(self):
        self.fixture, home_club, self.away_club = make_level_fixture()
        self.hp = [Player.objects.create(club=home_club, name=f'Home {i}', level='Open') for i in range(1, 5)]
        self.ap = [Player.objects.create(club=self.away_club, name=f'Away {i}', level='Open') for i in range(1, 5)]

    def _data(self, **overrides):
        d = {
            'home_points': '8',
            'away_points': '4',
            'home_player1': str(self.hp[0].pk),
            'home_player2': str(self.hp[1].pk),
            'home_player3': str(self.hp[2].pk),
            'home_player4': str(self.hp[3].pk),
            'away_player1': 'Away 1',
            'away_player2': 'Away 2',
            'away_player3': 'Away 3',
            'away_player4': 'Away 4',
            'player_name_check': '',
        }
        d.update(overrides)
        return d

    def test_valid_form(self):
        form = LevelFixtureForm(data=self._data(), instance=self.fixture)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn('players_found', form.cleaned_data)

    def test_wrong_points_total(self):
        form = LevelFixtureForm(data=self._data(home_points='7'), instance=self.fixture)
        self.assertFalse(form.is_valid())
        self.assertIn('Points do not add up', str(form.errors))

    def test_missing_home_player_without_override(self):
        form = LevelFixtureForm(data=self._data(home_player1=''), instance=self.fixture)
        self.assertFalse(form.is_valid())
        self.assertIn('not entered all home players', str(form.errors))

    def test_missing_home_player_with_override(self):
        form = LevelFixtureForm(
            data=self._data(home_player1='', player_name_check='on'),
            instance=self.fixture,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_home_players_not_overridable(self):
        # player_name_check ticked — duplicate home players still blocked
        form = LevelFixtureForm(
            data=self._data(home_player2=str(self.hp[0].pk), player_name_check='on'),
            instance=self.fixture,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('duplicated home', str(form.errors))

    def test_away_player_not_found_without_override(self):
        form = LevelFixtureForm(data=self._data(away_player1='Nobody'), instance=self.fixture)
        self.assertFalse(form.is_valid())

    def test_away_player_not_found_with_override(self):
        form = LevelFixtureForm(
            data=self._data(away_player1='Nobody', player_name_check='on'),
            instance=self.fixture,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_away_player_without_override(self):
        form = LevelFixtureForm(data=self._data(away_player1=''), instance=self.fixture)
        self.assertFalse(form.is_valid())

    def test_missing_away_player_with_override(self):
        form = LevelFixtureForm(
            data=self._data(away_player1='', player_name_check='on'),
            instance=self.fixture,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_away_player_wrong_level_not_overridable(self):
        Player.objects.create(club=self.away_club, name='Lady Player', level='Womens')
        form = LevelFixtureForm(
            data=self._data(away_player1='Lady Player', player_name_check='on'),
            instance=self.fixture,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('recorded as playing', str(form.errors))

    def test_duplicate_away_players_not_overridable(self):
        form = LevelFixtureForm(
            data=self._data(away_player2='Away 1', player_name_check='on'),
            instance=self.fixture,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('duplicated away', str(form.errors))


# ---------------------------------------------------------------------------
# MixedFixtureForm
# ---------------------------------------------------------------------------

class TestMixedFixtureForm(TestCase):

    def setUp(self):
        self.fixture, home_club, self.away_club = make_mixed_fixture()
        hw = [Player.objects.create(club=home_club, name=f'Home Lady {i}', level='Womens') for i in range(1, 4)]
        hm = [Player.objects.create(club=home_club, name=f'Home Man {i}', level='Open') for i in range(1, 4)]
        self.ap_w = [Player.objects.create(club=self.away_club, name=f'Away Lady {i}', level='Womens') for i in range(1, 4)]
        self.ap_m = [Player.objects.create(club=self.away_club, name=f'Away Man {i}', level='Open') for i in range(1, 4)]
        self.home_pks = [str(p.pk) for p in hw + hm]

    def _data(self, **overrides):
        d = {
            'home_points': '10',
            'away_points': '8',
            'home_player1': self.home_pks[0],
            'home_player2': self.home_pks[1],
            'home_player3': self.home_pks[2],
            'home_player4': self.home_pks[3],
            'home_player5': self.home_pks[4],
            'home_player6': self.home_pks[5],
            'away_player1': 'Away Lady 1',
            'away_player2': 'Away Lady 2',
            'away_player3': 'Away Lady 3',
            'away_player4': 'Away Man 1',
            'away_player5': 'Away Man 2',
            'away_player6': 'Away Man 3',
            'player_name_check': '',
        }
        d.update(overrides)
        return d

    def test_valid_form(self):
        form = MixedFixtureForm(data=self._data(), instance=self.fixture)
        self.assertTrue(form.is_valid(), form.errors)

    def test_man_in_womens_position_not_overridable(self):
        form = MixedFixtureForm(
            data=self._data(away_player1='Away Man 1', player_name_check='on'),
            instance=self.fixture,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('open player', str(form.errors))

    def test_woman_in_mens_position_not_overridable(self):
        form = MixedFixtureForm(
            data=self._data(away_player4='Away Lady 1', player_name_check='on'),
            instance=self.fixture,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('recorded as playing', str(form.errors))


# ---------------------------------------------------------------------------
# BaseScoreFormSet (tested via LevelScoreFormSet, 12 rubbers)
# ---------------------------------------------------------------------------

class TestBaseScoreFormSet(TestCase):

    def _data(self, rubbers, home_points=None, away_points=None, score_check=False):
        """
        Build POST data for LevelScoreFormSet.
        rubbers: list of exactly 12 (home, away) string pairs; use ('FH','') or ('FA','')
                 for forfeits.
        home_points / away_points: auto-computed from rubbers if omitted.
        """
        data = {
            'form-TOTAL_FORMS': '12',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
        }
        score = [0, 0]
        for i, (h, a) in enumerate(rubbers):
            if h == 'FH':
                data[f'form-{i}-home_score'] = ''
                data[f'form-{i}-away_score'] = ''
                data[f'form-{i}-forfeit'] = 'FH'
                score[1] += 1  # home forfeits → away wins
            elif h == 'FA':
                data[f'form-{i}-home_score'] = ''
                data[f'form-{i}-away_score'] = ''
                data[f'form-{i}-forfeit'] = 'FA'
                score[0] += 1  # away forfeits → home wins
            else:
                data[f'form-{i}-home_score'] = h
                data[f'form-{i}-away_score'] = a
                data[f'form-{i}-forfeit'] = ''
                if h and a and int(h) > int(a):
                    score[0] += 1
                elif h and a and int(a) > int(h):
                    score[1] += 1
        data['home_points'] = str(home_points if home_points is not None else score[0])
        data['away_points'] = str(away_points if away_points is not None else score[1])
        if score_check:
            data['score_check'] = 'on'
        return data

    def _fill(self, first_rubber, home_wins=7, away_wins=4):
        """12 rubbers: first_rubber then home_wins + away_wins clean rubbers."""
        return [first_rubber] + [('21', '15')] * home_wins + [('15', '21')] * away_wins

    # --- valid cases ---

    def test_valid_formset(self):
        rubbers = [('21', '15')] * 8 + [('15', '21')] * 4
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    def test_valid_with_setting_23_21(self):
        rubbers = self._fill(('23', '21'))  # valid extended play
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    def test_valid_with_setting_22_20(self):
        rubbers = self._fill(('22', '20'))
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    def test_valid_with_setting_30_29(self):
        rubbers = self._fill(('30', '29'))
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    def test_valid_with_setting_30_28(self):
        rubbers = self._fill(('30', '28'))
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    def test_valid_with_home_forfeit(self):
        # Away wins the forfeit rubber; home wins 8 others → 8 home, 4 away
        rubbers = [('21', '15')] * 8 + [('FH', '')] + [('15', '21')] * 3
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    def test_valid_with_away_forfeit(self):
        # Home wins the forfeit rubber
        rubbers = [('21', '15')] * 7 + [('FA', '')] + [('15', '21')] * 4
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    # --- non-overridable errors ---

    def test_forfeit_with_score_raises(self):
        data = self._data([('21', '15')] * 8 + [('15', '21')] * 4)
        # Manually add a forfeit to a form that already has scores
        data['form-0-forfeit'] = 'FH'
        fs = LevelScoreFormSet(data=data)
        self.assertFalse(fs.is_valid())
        self.assertIn('cannot be entered if a forfeit', str(fs.non_form_errors()))

    def test_final_score_mismatch_not_overridable(self):
        rubbers = [('21', '15')] * 8 + [('15', '21')] * 4  # computed → 8-4
        fs = LevelScoreFormSet(data=self._data(rubbers, home_points=7, away_points=5, score_check=True))
        self.assertFalse(fs.is_valid())
        self.assertIn('does not match', str(fs.non_form_errors()))

    # --- overridable errors ---

    def test_equal_scores_raises_without_override(self):
        rubbers = self._fill(('21', '21'))  # equal → error; score = [7, 4]
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertFalse(fs.is_valid())
        self.assertIn('scores the same', str(fs.non_form_errors()))

    def test_equal_scores_allowed_with_score_check(self):
        rubbers = self._fill(('21', '21'))
        fs = LevelScoreFormSet(data=self._data(rubbers, score_check=True))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    def test_both_under_21_raises_without_override(self):
        rubbers = self._fill(('15', '14'))  # home wins but both < 21
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertFalse(fs.is_valid())
        self.assertIn('under 21', str(fs.non_form_errors()))

    def test_both_under_21_allowed_with_score_check(self):
        rubbers = self._fill(('15', '14'))
        fs = LevelScoreFormSet(data=self._data(rubbers, score_check=True))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    def test_score_21_20_raises_without_override(self):
        rubbers = self._fill(('21', '20'))
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertFalse(fs.is_valid())
        self.assertIn('score looks wrong', str(fs.non_form_errors()))

    def test_score_21_20_allowed_with_score_check(self):
        rubbers = self._fill(('21', '20'))
        fs = LevelScoreFormSet(data=self._data(rubbers, score_check=True))
        self.assertTrue(fs.is_valid(), fs.non_form_errors())

    def test_setting_22_21_raises(self):
        # Difference of 1 at setting is invalid
        rubbers = self._fill(('22', '21'))
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertFalse(fs.is_valid())
        self.assertIn('setting score looks wrong', str(fs.non_form_errors()))

    def test_setting_30_27_raises(self):
        # 30-27 is not a valid cap score
        rubbers = self._fill(('30', '27'))
        fs = LevelScoreFormSet(data=self._data(rubbers))
        self.assertFalse(fs.is_valid())
        self.assertIn('setting score looks wrong', str(fs.non_form_errors()))

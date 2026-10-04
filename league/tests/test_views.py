from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from league.models import (
    Season, Division, Club, Team, Fixture, Player,
    Administrator, Penalty, Venue,
)
from league import constants


def _make_setup():
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
    home_user = User.objects.create_user(username='homeuser', password='pass')
    Administrator.objects.create(user=home_user, club=home_club)
    return fixture, home_club, away_club, home_team, away_team, home_user


# ---------------------------------------------------------------------------
# FixUpdateView — GET
# ---------------------------------------------------------------------------

class TestFixUpdateViewGet(TestCase):

    def setUp(self):
        self.fixture, self.home_club, self.away_club, \
            self.home_team, self.away_team, self.home_user = _make_setup()
        self.client.force_login(self.home_user)

    def _url(self, pagename, source='div'):
        return f'/fixtures/update/{self.fixture.id}/{pagename}/{source}'

    def test_submit_includes_result_forms(self):
        r = self.client.get(self._url('submit'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('resform', r.context)
        self.assertIn('resformset', r.context)

    def test_reschedule_includes_reschedule_form(self):
        r = self.client.get(self._url('reschedule'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('rform', r.context)

    def test_proposed_fixture_overrides_pagename(self):
        self.fixture.status = 'Proposed'
        self.fixture.save()
        r = self.client.get(self._url('update'))
        self.assertEqual(r.context['pagename'], 'proposed')

    def test_away_user_on_unplayed_fixture_is_unupdateable(self):
        away_user = User.objects.create_user(username='awayuser', password='pass')
        Administrator.objects.create(user=away_user, club=self.away_club)
        self.client.force_login(away_user)
        r = self.client.get(self._url('update'))
        self.assertEqual(r.context['pagename'], 'unupdateable')


# ---------------------------------------------------------------------------
# FixUpdateView — POST
# ---------------------------------------------------------------------------

class TestFixUpdateViewPost(TestCase):

    def setUp(self):
        self.fixture, self.home_club, self.away_club, \
            self.home_team, self.away_team, self.home_user = _make_setup()
        self.client.force_login(self.home_user)

    def _url(self, pagename, source='div'):
        return f'/fixtures/update/{self.fixture.id}/{pagename}/{source}'

    # --- confirmed ---

    @patch('league.views.email_notification')
    def test_confirmed_sets_rearranged(self, mock_email):
        self.fixture.status = 'Proposed'
        self.fixture.save()
        r = self.client.post(self._url('confirmed'))
        self.fixture.refresh_from_db()
        self.assertEqual(self.fixture.status, 'Rearranged')
        self.assertEqual(r.context['pagename'], 'confirmed')
        mock_email.assert_called_once_with('confirmed', fixture=self.fixture)

    # --- rejected ---

    @patch('league.views.email_notification')
    def test_rejected_sets_postponed_status(self, mock_email):
        self.fixture.status = 'Proposed'
        self.fixture.save()
        r = self.client.post(self._url('rejected'))
        self.fixture.refresh_from_db()
        self.assertEqual(self.fixture.status, 'Postponed')
        self.assertEqual(r.context['pagename'], 'rejected')

    # --- postponed ---

    @patch('league.views.email_notification')
    def test_postponed_sets_postponed_status(self, mock_email):
        r = self.client.post(self._url('postponed'))
        self.fixture.refresh_from_db()
        self.assertEqual(self.fixture.status, 'Postponed')
        self.assertEqual(r.context['pagename'], 'postponed')

    # --- rescheduled ---

    @patch('league.views.email_notification')
    def test_rescheduled_valid_sets_proposed(self, mock_email):
        venue = Venue.objects.create(name='Test Venue', address='123 Test St')
        r = self.client.post(self._url('rescheduled'), {
            'date_time': '2025-01-15T19:00',
            'end_time': '21:30',
            'venue': venue.id,
        })
        self.fixture.refresh_from_db()
        self.assertEqual(self.fixture.status, 'Proposed')
        self.assertEqual(r.context['pagename'], 'rescheduled')
        mock_email.assert_called_once_with('reschedule', fixture=self.fixture)

    @patch('league.views.email_notification')
    def test_rescheduled_invalid_form_falls_back_to_reschedule(self, mock_email):
        original_status = self.fixture.status
        r = self.client.post(self._url('rescheduled'), {'date_time': 'not-a-date'})
        self.fixture.refresh_from_db()
        self.assertEqual(self.fixture.status, original_status)
        self.assertEqual(r.context['pagename'], 'reschedule')
        mock_email.assert_not_called()

    # --- conceded ---

    @patch('league.views.email_notification')
    def test_concededhome_sets_status_and_penalty(self, mock_email):
        r = self.client.post(self._url('concededhome'))
        self.fixture.refresh_from_db()
        self.assertEqual(self.fixture.status, 'Conceded (H)')
        self.assertEqual(r.context['pagename'], 'concededhome')
        penalty = Penalty.objects.get(fixture=self.fixture)
        self.assertEqual(penalty.team, self.home_team)
        self.assertEqual(penalty.penalty_value, constants.PENALTY_LEVEL_CONCEDED)
        self.assertEqual(penalty.penalty_type, 'Match Conceded')

    @patch('league.views.email_notification')
    def test_concededaway_sets_status_and_penalty(self, mock_email):
        r = self.client.post(self._url('concededaway'))
        self.fixture.refresh_from_db()
        self.assertEqual(self.fixture.status, 'Conceded (A)')
        self.assertEqual(r.context['pagename'], 'concededaway')
        penalty = Penalty.objects.get(fixture=self.fixture)
        self.assertEqual(penalty.team, self.away_team)
        self.assertEqual(penalty.penalty_value, constants.PENALTY_LEVEL_CONCEDED)
        self.assertEqual(penalty.penalty_type, 'Match Conceded')

    # --- submit ---

    @patch('league.utilities.player.email_notification')
    @patch('league.views.email_notification')
    def test_submit_valid_sets_played(self, mock_view_email, mock_player_email):
        hp = [Player.objects.create(club=self.home_club, name=f'Home {i}', level='Open') for i in range(1, 5)]
        ap = [Player.objects.create(club=self.away_club, name=f'Away {i}', level='Open') for i in range(1, 5)]
        rubbers = [('21', '15')] * 8 + [('15', '21')] * 4
        data = {
            'home_points': '8',
            'away_points': '4',
            'home_player1': str(hp[0].pk),
            'home_player2': str(hp[1].pk),
            'home_player3': str(hp[2].pk),
            'home_player4': str(hp[3].pk),
            'away_player1': ap[0].name,
            'away_player2': ap[1].name,
            'away_player3': ap[2].name,
            'away_player4': ap[3].name,
            'player_name_check': '',
            'form-TOTAL_FORMS': '12',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
        }
        for i, (h, a) in enumerate(rubbers):
            data[f'form-{i}-home_score'] = h
            data[f'form-{i}-away_score'] = a
            data[f'form-{i}-forfeit'] = ''
        r = self.client.post(self._url('submit'), data)
        self.fixture.refresh_from_db()
        self.assertEqual(self.fixture.status, 'Played')
        self.assertEqual(r.context['pagename'], 'submitted')
        mock_view_email.assert_called_once_with('result', fixture=self.fixture)

    @patch('league.views.email_notification')
    def test_submit_invalid_returns_errors(self, mock_email):
        # home_points + away_points must equal TOTAL_POINTS_LEVEL (12); 5+5=10 fails validation
        r = self.client.post(self._url('submit'), {
            'home_points': '5',
            'away_points': '5',
            'form-TOTAL_FORMS': '12',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
        })
        self.fixture.refresh_from_db()
        self.assertNotEqual(self.fixture.status, 'Played')
        self.assertTrue(r.context['errors'])
        mock_email.assert_not_called()

from unittest.mock import patch
from django.test import TestCase
from league.models import Season, Division, Club, Team, Fixture, Player, Penalty, TeamNomination
from league.utilities.player import check_player_eligibility
from league import constants


def _make_season():
    return Season.objects.create(year='2024/25', current=True)


def _make_open_setup(season):
    """Two Open teams (1=higher, 2=lower) at one club, plus a away club."""
    div1 = Division.objects.create(number=1, type='Open')
    div2 = Division.objects.create(number=2, type='Open')
    club = Club.objects.create(name='Club', short_name='CL')
    away_club = Club.objects.create(name='Away Club', short_name='AC')
    team1 = Team.objects.create(number=1, type='Open', club=club, division=div1)
    team2 = Team.objects.create(number=2, type='Open', club=club, division=div2)
    away_team = Team.objects.create(number=1, type='Open', club=away_club, division=div1)
    return club, away_club, team1, team2, away_team, div1, div2


def _make_fixture(season, division, home_team, away_team, **player_kwargs):
    fix = Fixture.objects.create(
        season=season, division=division,
        home_team=home_team, away_team=away_team,
    )
    for field, player in player_kwargs.items():
        setattr(fix, field, player)
    fix.save()
    return fix


# ---------------------------------------------------------------------------
# Player.check_eligibility  (unit tests — no fixture submission)
# ---------------------------------------------------------------------------

class TestCheckEligibility(TestCase):

    def setUp(self):
        self.season = _make_season()
        self.club, self.away_club, self.team1, self.team2, self.away_team, self.div1, self.div2 = _make_open_setup(self.season)
        self.player = Player.objects.create(club=self.club, name='Test Player', level='Open')

    def test_eligible_correct_level_no_nomination_no_plays(self):
        self.assertTrue(self.player.check_eligibility(self.team2))

    def test_ineligible_wrong_level(self):
        womens_player = Player.objects.create(club=self.club, name='Lady', level='Womens')
        # Womens player trying to play for Open team → ineligible
        self.assertFalse(womens_player.check_eligibility(self.team2))

    def test_mixed_team_bypasses_level_check(self):
        div_mixed = Division.objects.create(number=1, type='Mixed')
        mixed_team = Team.objects.create(number=1, type='Mixed', club=self.club, division=div_mixed)
        womens_player = Player.objects.create(club=self.club, name='Lady', level='Womens')
        # Mixed teams do not check player level
        self.assertTrue(womens_player.check_eligibility(mixed_team))

    def test_ineligible_nominated_for_higher_team(self):
        # Nominated for team 1 (better), playing for team 2 (worse) → ineligible
        TeamNomination.objects.create(
            player=self.player, team=self.team1,
            date_from='2024-09-01', date_to=None, approved=True, position=1,
        )
        self.assertFalse(self.player.check_eligibility(self.team2))

    def test_eligible_nominated_for_same_team(self):
        TeamNomination.objects.create(
            player=self.player, team=self.team2,
            date_from='2024-09-01', date_to=None, approved=True, position=1,
        )
        self.assertTrue(self.player.check_eligibility(self.team2))

    def test_eligible_unapproved_nomination_ignored(self):
        # Unapproved nomination for team1 should not block playing for team2
        TeamNomination.objects.create(
            player=self.player, team=self.team1,
            date_from='2024-09-01', date_to=None, approved=False, position=1,
        )
        self.assertTrue(self.player.check_eligibility(self.team2))

    def test_eligible_expired_nomination_ignored(self):
        TeamNomination.objects.create(
            player=self.player, team=self.team1,
            date_from='2024-09-01', date_to='2024-12-01', approved=True, position=1,
        )
        self.assertTrue(self.player.check_eligibility(self.team2))

    def test_eligible_at_play_limit(self):
        # Exactly MAX_PLAYS_FOR_HIGHER_TEAMS appearances for team1 → still eligible for team2
        for i in range(constants.MAX_PLAYS_FOR_HIGHER_TEAMS):
            _make_fixture(self.season, self.div1, self.team1, self.away_team,
                          home_player1=self.player)
        self.assertTrue(self.player.check_eligibility(self.team2))

    def test_ineligible_over_play_limit(self):
        # One more than MAX → ineligible
        for i in range(constants.MAX_PLAYS_FOR_HIGHER_TEAMS + 1):
            _make_fixture(self.season, self.div1, self.team1, self.away_team,
                          home_player1=self.player)
        self.assertFalse(self.player.check_eligibility(self.team2))

    def test_plays_for_different_season_not_counted(self):
        old_season = Season.objects.create(year='2023/24', current=False)
        # Plays for team1 in a different season should not count
        for i in range(constants.MAX_PLAYS_FOR_HIGHER_TEAMS + 1):
            _make_fixture(old_season, self.div1, self.team1, self.away_team,
                          home_player1=self.player)
        self.assertTrue(self.player.check_eligibility(self.team2))

    def test_plays_as_away_player_count(self):
        # Playing up as away player should also count
        for i in range(constants.MAX_PLAYS_FOR_HIGHER_TEAMS + 1):
            _make_fixture(self.season, self.div1, self.away_team, self.team1,
                          away_player1=self.player)
        self.assertFalse(self.player.check_eligibility(self.team2))


# ---------------------------------------------------------------------------
# check_player_eligibility  (integration — penalty creation)
# ---------------------------------------------------------------------------

class TestCheckPlayerEligibility(TestCase):

    def setUp(self):
        self.season = _make_season()
        self.club, self.away_club, self.team1, self.team2, self.away_team, self.div1, self.div2 = _make_open_setup(self.season)

    @patch('league.utilities.player.email_notification')
    def test_eligible_players_no_penalties(self, mock_email):
        player = Player.objects.create(club=self.club, name='Good Player', level='Open')
        away_player = Player.objects.create(club=self.away_club, name='Away Good', level='Open')
        fix = _make_fixture(self.season, self.div2, self.team2, self.away_team,
                            home_player1=player, away_player1=away_player)
        check_player_eligibility(fix)
        self.assertEqual(Penalty.objects.count(), 0)
        mock_email.assert_not_called()

    @patch('league.utilities.player.email_notification')
    def test_ineligible_home_player_creates_penalty(self, mock_email):
        # Womens player in Open team → ineligible
        bad_player = Player.objects.create(club=self.club, name='Wrong Level', level='Womens')
        fix = _make_fixture(self.season, self.div2, self.team2, self.away_team,
                            home_player1=bad_player)
        check_player_eligibility(fix)
        self.assertEqual(Penalty.objects.count(), 1)
        penalty = Penalty.objects.first()
        self.assertEqual(penalty.team, self.team2)
        self.assertEqual(penalty.penalty_type, 'Ineligible Player')
        self.assertEqual(penalty.penalty_value, constants.PENALTY_INELIGIBLE_PLAYER)
        self.assertEqual(penalty.player, bad_player.name)
        mock_email.assert_called_once_with(
            'eligibility_penalty', fixture=fix, team=self.team2, player_name=bad_player.name
        )

    @patch('league.utilities.player.email_notification')
    def test_ineligible_away_player_creates_penalty(self, mock_email):
        womens_player = Player.objects.create(club=self.away_club, name='Wrong Level', level='Womens')
        fix = _make_fixture(self.season, self.div1, self.team1, self.away_team,
                            away_player1=womens_player)
        check_player_eligibility(fix)
        self.assertEqual(Penalty.objects.count(), 1)
        penalty = Penalty.objects.first()
        self.assertEqual(penalty.team, self.away_team)

    @patch('league.utilities.player.email_notification')
    def test_played_up_too_many_times_creates_penalty(self, mock_email):
        player = Player.objects.create(club=self.club, name='Play Up Player', level='Open')
        # Create MAX+1 fixtures where player played for team1
        for i in range(constants.MAX_PLAYS_FOR_HIGHER_TEAMS + 1):
            _make_fixture(self.season, self.div1, self.team1, self.away_team,
                          home_player1=player)
        # Now player plays for team2 → should be ineligible
        fix = _make_fixture(self.season, self.div2, self.team2, self.away_team,
                            home_player1=player)
        check_player_eligibility(fix)
        self.assertEqual(Penalty.objects.count(), 1)

    @patch('league.utilities.player.email_notification')
    def test_nominated_for_higher_team_creates_penalty(self, mock_email):
        player = Player.objects.create(club=self.club, name='Nom Player', level='Open')
        TeamNomination.objects.create(
            player=player, team=self.team1,
            date_from='2024-09-01', date_to=None, approved=True, position=1,
        )
        fix = _make_fixture(self.season, self.div2, self.team2, self.away_team,
                            home_player1=player)
        check_player_eligibility(fix)
        self.assertEqual(Penalty.objects.count(), 1)

    @patch('league.utilities.player.email_notification')
    def test_multiple_ineligible_players_multiple_penalties(self, mock_email):
        bad1 = Player.objects.create(club=self.club, name='Bad 1', level='Womens')
        bad2 = Player.objects.create(club=self.away_club, name='Bad 2', level='Womens')
        fix = _make_fixture(self.season, self.div2, self.team2, self.away_team,
                            home_player1=bad1, away_player1=bad2)
        check_player_eligibility(fix)
        self.assertEqual(Penalty.objects.count(), 2)
        self.assertEqual(mock_email.call_count, 2)

    @patch('league.utilities.player.email_notification')
    def test_at_play_limit_no_penalty(self, mock_email):
        player = Player.objects.create(club=self.club, name='Limit Player', level='Open')
        # Exactly MAX plays → still eligible
        for i in range(constants.MAX_PLAYS_FOR_HIGHER_TEAMS):
            _make_fixture(self.season, self.div1, self.team1, self.away_team,
                          home_player1=player)
        fix = _make_fixture(self.season, self.div2, self.team2, self.away_team,
                            home_player1=player)
        check_player_eligibility(fix)
        self.assertEqual(Penalty.objects.count(), 0)

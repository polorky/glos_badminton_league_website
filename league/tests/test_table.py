# league/tests/test_table.py

from django.test import TestCase
from league.models import Division, Season, Team, Fixture, Club, Penalty
from league.utilities.table import build_table
from league import constants

class TestBuildTable(TestCase):

    def setUp(self):
        """Create the base objects every test needs."""
        self.season = Season.objects.create(year="2024/25", current=True)
        self.division = Division.objects.create(number=1, type="Mixed")
        self.club = Club.objects.create(name="TeamName", short_name="ShortName")
        self.team_a = Team.objects.create(number=1, type="Mixed", club=self.club, division=self.division)
        self.team_b = Team.objects.create(number=2, type="Mixed", club=self.club, division=self.division)
        self.team_c = Team.objects.create(number=3, type="Mixed", club=self.club, division=self.division)

    def _make_fixture(self, home, away, home_points, away_points, status="Played"):
        """Helper to reduce repetition when creating fixtures."""
        return Fixture.objects.create(
            season=self.season,
            division=self.division,
            home_team=home,
            away_team=away,
            home_points=home_points,
            away_points=away_points,
            status=status,
        )

    def _make_penalty(self, team):
        return Penalty.objects.create(
            season=self.season,
            team=team,
            penalty_type="Match Conceded",
            penalty_value=constants.PENALTY_MIXED_CONCEDED
        )

    def test_basic_win_loss(self):
        """Team A beats Team B -- check won/lost counts are correct."""
        self._make_fixture(self.team_a, self.team_b, 8, 4)

        table = build_table(self.division, self.season)
        table_dict = {name: stats for name, stats in table}

        a = table_dict[self.team_a.get_short_name()]
        b = table_dict[self.team_b.get_short_name()]

        self.assertEqual(a['Won'], 1)
        self.assertEqual(a['Lost'], 0)
        self.assertEqual(a['PFor'], 8)
        self.assertEqual(b['Won'], 0)
        self.assertEqual(b['Lost'], 1)
        self.assertEqual(b['PAgainst'], 8)

    def test_draw(self):
        """Equal points should count as a draw for both teams."""
        self._make_fixture(self.team_a, self.team_b, 6, 6)

        table = build_table(self.division, self.season)
        table_dict = {name: stats for name, stats in table}

        self.assertEqual(table_dict[self.team_a.get_short_name()]['Drawn'], 1)
        self.assertEqual(table_dict[self.team_b.get_short_name()]['Drawn'], 1)

    def test_table_ordering(self):
        """Team with more points should appear first."""
        self._make_fixture(self.team_a, self.team_b, 8, 4)
        self._make_fixture(self.team_a, self.team_c, 9, 3)

        table = build_table(self.division, self.season)
        self.assertEqual(table[0][0], self.team_a.get_short_name())

    def test_conceded_home(self):
        """When home team concedes, away team gets a win."""
        self._make_fixture(self.team_a, self.team_b, 0, 0, status='Conceded (H)')
        self._make_penalty(self.team_a)

        table = build_table(self.division, self.season)
        table_dict = {name: stats for name, stats in table}

        self.assertEqual(table_dict[self.team_b.get_short_name()]['Won'], 1)
        self.assertEqual(table_dict[self.team_a.get_short_name()]['Lost'], 1)
        self.assertEqual(table_dict[self.team_a.get_short_name()]['PFor'], constants.PENALTY_MIXED_CONCEDED * -1)
        self.assertEqual(table_dict[self.team_a.get_short_name()]['Penalties'], constants.PENALTY_MIXED_CONCEDED)

    def test_conceded_away(self):
        """When home team concedes, away team gets a win."""
        self._make_fixture(self.team_a, self.team_b, 0, 0, status='Conceded (A)')
        self._make_fixture(self.team_c, self.team_b, 12, 6, status='Played')
        self._make_fixture(self.team_c, self.team_b, 13, 5, status='Played')
        self._make_penalty(self.team_b)

        table = build_table(self.division, self.season)
        table_dict = {name: stats for name, stats in table}

        self.assertEqual(table_dict[self.team_a.get_short_name()]['Won'], 1)
        self.assertEqual(table_dict[self.team_a.get_short_name()]['PFor'], 12.5)
        self.assertEqual(table_dict[self.team_b.get_short_name()]['Lost'], 3)
        self.assertEqual(table_dict[self.team_b.get_short_name()]['PFor'], 11 - constants.PENALTY_MIXED_CONCEDED)
        self.assertEqual(table_dict[self.team_b.get_short_name()]['Penalties'], constants.PENALTY_MIXED_CONCEDED)

    def test_no_fixtures_returns_blank_table(self):
        """With no fixtures played, all stats should be zero."""
        table = build_table(self.division, self.season)

        for name, stats in table:
            self.assertEqual(stats['Played'], 0)
            self.assertEqual(stats['PFor'], 0)
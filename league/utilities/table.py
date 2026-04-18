from typing import TypedDict
from league.models import Team, Division, Season, Fixture
from collections import defaultdict

class TableColumns(TypedDict):
    Played: int
    Won: int
    Drawn: int
    Lost: int
    PFor: float
    PAgaint: float
    Penalties: int
    Object: Team

def build_table(division: Division, season: Season) -> list[tuple[str, TableColumns]]:
    """Entry point — builds, sorts and returns the division table."""
    fixtures = Fixture.objects.filter(season=season, division=division)
    teams = _get_teams(division, season, fixtures)
    team_dict = _initialise_team_dict(teams)
    team_dict, concessions = _process_fixtures(fixtures, team_dict)
    team_dict = _apply_concessions(concessions, fixtures, team_dict)
    team_dict = _apply_penalties(team_dict, season)
    return _sort_table(team_dict, fixtures)

def _get_teams(division, season, fixtures):
    if season.current:
        return list(Team.objects.filter(division=division))
    teams = set()
    for fix in fixtures:
        teams.add(fix.home_team)
        teams.add(fix.away_team)
    return list(teams)

def _initialise_team_dict(teams: list[Team]) -> dict[str, TableColumns]:
    return {
        team.get_short_name(): TableColumns(
            Played=0, Won=0, Drawn=0, Lost=0,
            PFor=0, PAgainst=0, Penalties=0, Object=team
        )
        for team in teams
    }

def _process_fixtures(fixtures, team_dict):
    """Update team_dict from fixture results. Returns updated dict and concessions list."""
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
        else:
            team_dict[home]['Lost'] += 1
            team_dict[away]['Won'] += 1

        team_dict[home]['Played'] += 1
        team_dict[away]['Played'] += 1
        team_dict[home]['PFor'] += fix.home_points
        team_dict[home]['PAgainst'] += fix.away_points
        team_dict[away]['PFor'] += fix.away_points
        team_dict[away]['PAgainst'] += fix.home_points

    return team_dict, concessions

def _apply_concessions(concessions, fixtures, team_dict):
    for concession in concessions:
        total_points = 0
        matches_played = 0
        for fix in fixtures:
            if fix.status != "Played":
                continue
            if (concession[2] == "home" and fix.home_team == concession[1]) or \
               (concession[2] == "away" and fix.away_team == concession[1]):
                matches_played += 1
                total_points += fix.away_points if concession[2] == "home" else fix.home_points
        receiving_team = concession[0].get_short_name()
        if matches_played > 0:
            team_dict[receiving_team]['PFor'] += round(total_points / matches_played, 1)
    return team_dict

def _apply_penalties(team_dict, season):
    for team in team_dict:
        pens = team_dict[team]['Object'].get_penalties(season)
        team_dict[team]['Penalties'] = pens
        team_dict[team]['PFor'] -= pens
    return team_dict

def _sort_table(team_dict, fixtures):
    team_list = sorted(
        team_dict.items(),
        key=lambda x: (x[1]['PFor'], x[1]['Won'], x[1]['Drawn']),
        reverse=True
    )
    points_dict = defaultdict(list)
    for team, stats in team_dict.items():
        k = f"{stats['PFor']}{stats['Won']}{stats['Drawn']}"
        points_dict[k].append(team)

    if any(len(v) > 1 for v in points_dict.values()):
        team_list = _break_ties(team_list, team_dict, points_dict, fixtures)

    return team_list

def _break_ties(team_list, team_dict, points_dict, fixtures):
    team_order = []
    for team, stats in team_list:
        if team in team_order:
            continue
        k = f"{stats['PFor']}{stats['Won']}{stats['Drawn']}"
        tied_teams = points_dict[k]
        if len(tied_teams) == 1:
            team_order.append(team)
            continue
        total_points = {t: 0 for t in tied_teams}
        for fixture in fixtures:
            if fixture.home_team in total_points and fixture.away_team in total_points:
                total_points[fixture.home_team] += fixture.home_points
                total_points[fixture.away_team] += fixture.away_points
        for t in sorted(total_points, key=total_points.get, reverse=True):
            team_order.append(t)

    return [(team, team_dict[team]) for team in team_order]

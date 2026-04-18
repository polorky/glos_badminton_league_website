from league.models import Season, Fixture, Team, Player, Club
from dataclasses import dataclass, field
from django.db.models import Q

def get_clubs_teams(club):
    '''Return club's teams for player roster'''
    teams = Team.objects.filter(club=club).filter(active=True)

    # Split out teams
    team_dict = {"Mixed":teams.filter(type="Mixed"),
            "Womens":teams.filter(type="Womens"),
            "Mens":teams.filter(type="Mens"),
            "All":teams} 
    # Get length of team lists for formatting size of table
    team_dict.update({"Lengths":{"Mixed":len(team_dict["Mixed"]),
                            "Womens":len(team_dict["Womens"]),
                            "Mens": len(team_dict["Mens"]),
                            "All": len(team_dict["All"]),
                            }})  
    
    return team_dict  

@dataclass
class TeamAppearances:
    '''Class to deal with the slightly awkward string value displayed in the player roster'''
    count: int = 0
    eligible: bool = True
    team_total: int = 0

    def increment(self):
        self.count += 1

    def display(self) -> str:
        if not self.eligible and self.count == 0:
            return "X"
        elif self.eligible and self.count == 0:
            return "0"
        percent = int(self.count / self.team_total * 100) if self.team_total > 0 else 0
        played_str = f"{self.count} ({percent}%)" if self.team_total > 0 else str(self.count)
        return f"X ({self.count})" if not self.eligible else played_str

def build_roster(club: Club) -> dict:
    '''Build player roster with appearance counts and nomination statuses'''
    current_season = Season.objects.get(current=True)
    club_fixtures = Fixture.objects.filter(
        season=current_season,
        status="Played"
    ).filter(Q(home_team__club=club) | Q(away_team__club=club))
    club_teams = list(Team.objects.filter(club=club, active=True).order_by('number'))
    club_players = list(Player.objects.filter(club=club).order_by('level', 'name'))

    team_fixture_counts = {team: 0 for team in club_teams}
    player_dict = _initialise_player_dict(club_players, club_teams)
    player_dict = _process_fixtures(club, club_fixtures, player_dict, team_fixture_counts)
    player_dict = _apply_percentages(player_dict, club_teams, team_fixture_counts)

    return player_dict

def _initialise_player_dict(players, teams):
    '''Initiate TeamAppearance objects for each team and get nominations'''
    player_dict = {}
    for player in players:
        noms_strings = player.get_noms_strings()
        player_dict[player] = {
            "appearances": {
                "Mixed": {team: TeamAppearances(eligible=player.check_eligibility(team)) for team in teams if team.type == 'Mixed'},
                "Womens": {team: TeamAppearances(eligible=player.check_eligibility(team)) for team in teams if team.type == 'Womens'},
                "Mens": {team: TeamAppearances(eligible=player.check_eligibility(team)) for team in teams if team.type == 'Mens'}
            },
            "noms": {"mixed": noms_strings[0], "level": noms_strings[1]}
        }
    return player_dict

def _process_fixtures(club, fixtures, player_dict, team_fixture_counts):
    '''Iterate over fixtures and update player counts and team totals'''
    for fixture in fixtures:
        for side, team in [("home", fixture.home_team), ("away", fixture.away_team)]:
            if team.club != club:
                continue
            team_fixture_counts[team] += 1
            for player in fixture.get_players(side):
                if player in player_dict and team in player_dict[player]['appearances'][team.type]:
                    player_dict[player]['appearances'][team.type][team].increment()
    return player_dict

def _apply_percentages(player_dict, teams, team_fixture_counts):
    """Add team totals to player dictionary so percentages can be worked out"""
    for stats in player_dict.values():
        for team in teams:
            total = team_fixture_counts[team]
            stats['appearances'][team.type][team].team_total = total
    return player_dict

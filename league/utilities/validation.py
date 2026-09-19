import league.constants as constants
from league.models import Player
from rapidfuzz import fuzz

class PlayerValidation:

    def __init__(self, data, fixture):
        self.data = data
        self.fixture = fixture
        self.away_club = fixture.away_team.club
        self.critical_errors = []
        self.overridable_errors = []
        self.home_players = [v for k, v in data.items() if 'home_player' in k]
        self.away_titles = ['away_player1','away_player2','away_player3','away_player4']
        if self.fixture.division.type == "Mixed":
            self.away_titles += ['away_player5','away_player6']
        self.players_found = {
            player_title:{
                    'player': None, 
                    'suggest_only': False, 
                    'name': self.data.get(player_title)
                } for player_title in self.away_titles
            }
        self.validate()

    def validate(self):

        # Check all home players are entered - CAN BE OVERRIDDEN
        self.check_home_players_exist()

        # Check for duplicated home players - CANNOT BE OVERRIDDEN
        self.check_home_players_unique()

        for player_title, player_dict in self.players_found.items():

            # Check away player exists - CAN BE OVERRIDDEN
            self.check_away_player_exists(player_title, player_dict)

            try:
                # Check whether name as entered matches a player at the club
                player = Player.objects.get(club=self.away_club,
                                            name=player_dict['name'])
                player_dict['player'] = player

            except Player.DoesNotExist:

                # Try fuzzy matches
                self.attempt_fuzzy_match(player_title)

                # If player still not found - add error unless validation is being bypassed
                if not self.players_found[player_title]['player'] or self.players_found[player_title]['suggest_only']:
                    self.overridable_errors.append(f"Away Player {player_title[-1]} has not been recognised, please double check.")
                    continue

            # Check away player is the right gender for the match/position - CANNOT BE OVERRIDDEN
            self.check_away_player_level(player_title)

        # Check for duplicated away players - CANNOT BE OVERRIDDEN
        self.check_away_players_unique()

    def check_home_players_exist(self):
        
        for hp in self.home_players:
            if not hp:
                self.overridable_errors.append('You have not entered all home players.')
                break

    def check_home_players_unique(self):

        valid_hps = [player for player in self.home_players if player]

        if len(valid_hps) != len(list(set(valid_hps))):
            self.critical_errors.append('You have duplicated home player(s)')

    def check_away_player_exists(self, player_title, player_dict):

        if not player_dict['name']:
            self.overridable_errors.append(f"Away Player {player_title[-1]} has not been entered")
            return

    def check_away_players_unique(self):

        players = [d['player'] for d in self.players_found.values() if d['player']]
        if len(players) != len(list(set(players))):
            self.critical_errors.append('There are duplicated away players')

    def check_away_player_level(self, player_title):

        player = self.players_found[player_title]['player']
        if not player:
            return

        match_type = self.fixture.division.type

        # If mixed match and player male in female position, report error
        if match_type == "Mixed" and player_title[-1] in ['1','2','3'] and player.level == "Open":
            self.critical_errors.append((f"Away Player {player_title[-1]} found but is recorded as an open player, "
                                         f"please check you have entered them in the correct position"))
        # If mixed match and player female in male position, report error
        elif match_type == "Mixed" and player_title[-1] in ['4','5','6'] and player.level == "Womens":
            self.critical_errors.append((f"Away Player {player_title[-1]} found but is recorded as playing in the women's league, "
                                         f"please check you have entered them in the correct position"))
        # If ladies match but player is male, report error
        elif match_type == "Womens" and player.level == "Open":
            self.critical_errors.append(f"Away Player {player_title[-1]} found but is recorded as playing in the open league")
        # If mens match but player is female, report error
        elif match_type == "Open" and player.level == "Womens":
            self.critical_errors.append(f"Away Player {player_title[-1]} found but is recorded as playing in the women's league")

    def attempt_fuzzy_match(self, player_title):

        fuzzy_max = ('',0)
        player_name = self.players_found[player_title]['name']

        # Iterate through club players
        for club_player in Player.objects.filter(club=self.away_club):
            # Check whether fuzzy ratio of current player it higher than the current max
            fuzzy_ratio = fuzz.ratio(player_name.upper(), club_player.name.upper())
            if fuzzy_ratio > fuzzy_max[1]:
                # If so, update the current max
                fuzzy_max = (club_player, fuzzy_ratio)

        # If fuzzy_max is above acceptable threshold
        if fuzzy_max[1] >= constants.PLAYER_NAME_FUZZY_MATCH_RATIO:
            self.players_found[player_title]['player'] = fuzzy_max[0]
        else:
            # Check nicknames e.g. Dave instead of David etc.
            found = self.check_nicknames(player_title, player_name)
            if not found:
                # If fuzzy_max is above the suggestion threshold, return the player but flag as suggest_only
                if fuzzy_max[1] >= constants.PLAYER_NAME_FUZZY_SUGGEST_RATIO:
                    self.players_found[player_title]['player'] = fuzzy_max[0]
                    self.players_found[player_title]['suggest_only'] = True

    def check_nicknames(self, player_title, player_name):
        # Attempt alternate versions of commonly abbreviated name
        for name_tuple in constants.ALTERNATE_NAMES:
            # Try names both ways round, i.e. Dave instead of David and David instead of Dave
            for original, replacement in [(name_tuple[0], name_tuple[1]), (name_tuple[1], name_tuple[0])]:
                # If either version is found in name...
                if original in player_name:
                    try:
                        # ...see whether amended name is a player at the club
                        player = Player.objects.get(club=self.away_club, name=player_name.replace(original, replacement))
                        # If found record such and break from inner loop...
                        self.players_found[player_title]['player'] = player
                        return True
                    except Player.DoesNotExist:
                        pass
        return False

from .models import Player
import league.constants as constants
from RapidFuzz import fuzz

def find_away_players(data, fixture):
    '''
        Validation function for checking away player names
        Looks for existing players that match or closely match
        If none are found, return errors messages unless checkbox is ticked
    '''

    match_type = fixture.division.type
    club = fixture.away_team.club

    player_errors = []
    players_found = {}

    bypass_validation = data['player_name_check']

    players = ['away_player1','away_player2','away_player3','away_player4']
    if match_type == "Mixed":
        players += ['away_player5','away_player6']

    for player_title in players:

        suggest_only = False
        
        # Check for nulls
        player_name = data.get(player_title)
        if not player_name:
            if not bypass_validation:
                player_errors.append("Away Player " + player_title[-1] + " has not been entered, please tick the box below to confirm \
                                     this is correct")
            continue

        try:
            # Check whether name as entered matches a player at the club
            player = Player.objects.get(club=club,name=player_name)

        except Player.DoesNotExist:

            # Try fuzzy matches
            player, suggest_only = attempt_fuzzy_match(player_name, club)

            # If player still not found - add error unless validation is being bypassed
            if not bypass_validation and (not player or suggest_only):
                player_errors.append("Away Player " + player_title[-1] + " has not been recognised, please double check. \
                If you are sure that you have entered the name correctly please tick the box below")
                continue

        # If player already found, report duplicate
        if player in players_found:
            player_errors.append("There are duplicated away players")
        # If mixed match and player male in female position, report error
        elif match_type == "Mixed" and player_title[-1] in ['1','2','3'] and player.level == "Mens":
            player_errors.append("Away Player " + player_title[-1] + " found but is recorded as a man, please check you have entered \
                                 them in the correct position")
        # If mixed match and player female in male position, report error
        elif match_type == "Mixed" and player_title[-1] in ['4','5','6'] and player.level == "Ladies":
            player_errors.append("Away Player " + player_title[-1] + " found but is recorded as a lady, please check you have entered \
                                 them in the correct position")
        # If ladies match but player is male, report error
        elif match_type == "Ladies" and player.level == "Mens":
            player_errors.append("Away Player " + player_title[-1] + " found but is recorded as playing in mens league")
        # If mens match but player is female, report error
        elif match_type == "Mens" and player.level == "Ladies":
            player_errors.append("Away Player " + player_title[-1] + " found but is recorded as playing in ladies league")
        # Otherwise add player to players found dictionary
        else:
            players_found[player_title] = {'player': player, 'suggest_only': suggest_only}

    return players_found, player_errors

def attempt_fuzzy_match(player_name, club):

    player = None
    fuzzy_max = ('',0)
    suggest_only = False

    # Iterate through club players
    for player in Player.objects.filter(club=club):
        # Check whether fuzzy ratio of current player it higher than the current max
        if fuzz.ratio(player_name.upper(), player.name.upper()) > fuzzy_max[1]:
            # If so, update the current max
            fuzzy_max = (player, fuzz.ratio(player_name.upper(), player.name.upper()))

    # If fuzzy_max is not above acceptable threshold
    if fuzzy_max[1] >= constants.PLAYER_NAME_FUZZY_MATCH_RATIO:
        player = fuzzy_max[0]
    else:
        if fuzzy_max[1] >= constants.PLAYER_NAME_FUZZY_SUGGEST_RATIO:
            player = fuzzy_max[0]
            suggest_only = True
        # Attempt alternate versions of commonly abbreviated name
        player_found = False
        for name_tuple in constants.ALTERNATE_NAMES:
            # Try names both ways round, i.e. Dave instead of David and David instead of Dave
            for original, replacement in [(name_tuple[0], name_tuple[1]), (name_tuple[1], name_tuple[0])]:
                # If either version is found in name...
                if original in player_name:
                    try:
                        # ...see whether amended name is a player at the club
                        player = Player.objects.get(club=club, name=player_name.replace(original, replacement))
                        # If found record such and break from inner loop...
                        player_found = True
                        suggest_only = False
                        break
                    except Player.DoesNotExist:
                        pass
            # ...and break from outer loop
            if player_found:
                break

    return player, suggest_only
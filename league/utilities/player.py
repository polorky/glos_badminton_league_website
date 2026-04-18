import league.constants as constants
from rapidfuzz import fuzz
from django.core import signing
from .email import email_notification
from league.models import Team, PendingPlayerVerification, Penalty

# Player related functions
def find_away_players(data, fixture):
    '''
        Validation function for checking away player names
        Looks for existing players that match or closely match
        If none are found, return errors messages unless checkbox is ticked
    '''
    from league.models import Player

    match_type = fixture.division.type
    club = fixture.away_team.club

    player_errors = []
    

    bypass_validation = data['player_name_check']

    players = ['away_player1','away_player2','away_player3','away_player4']
    if match_type == "Mixed":
        players += ['away_player5','away_player6']
    
    players_found = {player_title:{'player':None, 'suggest_only':False, 'name':data.get(player_title)} for player_title in players}

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
        if player in [d['player'] for d in players_found.values()]:
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
            players_found[player_title]['player'] = player
            players_found[player_title]['suggest_only'] = suggest_only

    return players_found, player_errors

def verify_away_players(fixture, players_found):
    '''
        Takes list of away players from results form and does the following:
            1. If player found, add to fixture object
            2. Else send email to away club to get confirmation of correct player
    '''
    
    div_type = fixture.division.type
    mixed_player_type = ['Ladies','Ladies','Ladies','Men','Men','Men']
    verifications = []

    for player_title, player_dict in players_found.items():
        if player_dict['player'] and not player_dict['suggest_only']:
            setattr(fixture, player_title, player_dict['player'])
            fixture.save()
        else:
            level = div_type if div_type != 'Mixed' else mixed_player_type[int(player_title[-1])]
            verification = PendingPlayerVerification.objects.create(
                fixture=fixture,
                submitted_name=player_dict['name'],
                level=level,
                token=''
            )
            verification.token = signing.dumps({'verification_id': verification.id})
            verification.save()
            if player_dict['player']:
                verification.suggested_player = player_dict['player']
                verification.save()
            verifications.append(verification)
    
    if verifications:
        email_notification('playernotfound', fixture, verifications=verifications)

def verify_player(request, token):
    try:
        data = signing.loads(token, max_age=86400 * 7)  # 7 day expiry
        verification = PendingPlayerVerification.objects.get(
            id=data['verification_id'],
            resolved=False
        )

    except (signing.BadSignature, signing.SignatureExpired, PendingPlayerVerification.DoesNotExist):
        pass

def check_player_eligibility(fixture):
    '''
        Checks whether players are uneligible for these teams due to playing for higher teams
        Applies penalty points for any uneligible players played
    '''

    for player in fixture.get_players('home'):
        if not player.check_eligibility(fixture.home_team):
            email_notification('eligibility_penalty', fixture, team=fixture.home_team, player_name=player.name)
            Penalty.objects.create(season=fixture.season, 
                                   team=fixture.home_team, 
                                   penalty_value=constants.PENALTY_INELIGIBLE_PLAYER, 
                                   penalty_type='Ineligible Player', 
                                   player=player.name, 
                                   fixture=fixture)

    for player in fixture.get_players('away'):
        if not player.check_eligibility(fixture.away_team):
            email_notification('eligibility_penalty', fixture, team=fixture.away_team, player_name=player.name)
            Penalty.objects.create(season=fixture.season, 
                                   team=fixture.away_team,
                                   penalty_value=constants.PENALTY_INELIGIBLE_PLAYER, 
                                   penalty_type='Ineligible Player', 
                                   player=player.name, 
                                   fixture=fixture)

def attempt_fuzzy_match(player_name, club):
    from league.models import Player

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

def correct_duplicate_player(dup_player,cor_player,fix):

    player_fields = [f'home_player{i}' for i in range(1, 7)] + [f'away_player{i}' for i in range(1, 7)]

    for player in player_fields:
        if getattr(fix, player) == dup_player:
            setattr(fix, player, cor_player)
            fix.save()
            return 'done'

    return 'notfound'

def get_player_stats(club, fixtures):
    '''Stats for the player stats page'''
    player_dict = {}

    for fixture in fixtures:

        if fixture.status != 'Played':
            continue

        game_split = fixture.game_results.split(',')

        home_players = fixture.get_players(side='home')
        away_players = fixture.get_players(side='away')
        club_home = False
        club_away = False

        if fixture.home_team.club == club:
            for player in home_players:
                if player.id not in player_dict:
                    player_dict[player.id] = {'obj':player,'mixed':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0},'level':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0}}
            club_home = True
        if fixture.away_team.club == club:
            for player in away_players:
                if player.id not in player_dict:
                    player_dict[player.id] = {'obj':player,'mixed':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0},'level':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0}}
            club_away = True

        if fixture.division.type == "Mixed":
            #mixed_games = ["Mixed 3v2","Mixed 2v3","Mixed 1v1","Mixed 2v2","Mixed 3v3","Mens 1&2","Ladies 1&2","Mens 1&3","Ladies 1&3"]
            mixed_games = [[[3,6],[2,5]],[[2,5],[3,6]],[[1,4],[1,4]],[[2,5],[2,5]],[[3,6],[3,6]],[[4,5],[4,5]],[[1,2],[1,2]],[[4,6],[4,6]],[[1,3],[1,3]]]
            batched_games = [game_split[i:i + 6] for i in range(0, len(game_split), 6)]
        else:
            #level_games = ["2+3 v 2+3","1+4 v 1+4","2+4 v 2+4","1+3 v 1+3","3+4 v 3+4","1+2 v 1+2"]
            level_games = [[2,3],[1,4],[2,4],[1,3],[3,4],[1,2]]
            batched_games = [game_split[i:i + 4] for i in range(0, len(game_split), 4)]

        for x, game in enumerate(batched_games):

            rubbers = [game[i:i+2] for i in range(0, len(game), 2)]
            for rubber in rubbers:
                try:

                    if rubber[0] in ['FH','FA',''] or rubber[1] in ['FH','FA','']:
                        continue

                    if club_home:

                        if fixture.division.type == "Mixed":
                            players_involved = [home_players[mixed_games[x][0][0] - 1], home_players[mixed_games[x][0][1] - 1]]
                            match_type = "mixed"
                        else:
                            players_involved = [home_players[level_games[x][0] - 1], home_players[level_games[x][1] - 1]]
                            match_type = "level"

                        for player in players_involved:
                            player_dict[player.id][match_type]['played'] += 1
                            player_dict[player.id][match_type]['pf'] += int(rubber[0])
                            player_dict[player.id][match_type]['pa'] += int(rubber[1])
                            player_dict[player.id][match_type]['diff'] = player_dict[player.id][match_type]['pf'] - player_dict[player.id][match_type]['pa']
                            if int(rubber[0]) > int(rubber[1]):
                                player_dict[player.id][match_type]['won'] += 1
                            player_dict[player.id][match_type]['percent'] = round(player_dict[player.id][match_type]['won'] / player_dict[player.id][match_type]['played'] * 100, 1)

                    if club_away:

                        if fixture.division.type == "Mixed":
                            players_involved = [away_players[mixed_games[x][1][0] - 1], away_players[mixed_games[x][1][1] - 1]]
                            match_type = "mixed"
                        else:
                            players_involved = [away_players[level_games[x][0] - 1], away_players[level_games[x][1] - 1]]
                            match_type = "level"

                        for player in players_involved:
                            player_dict[player.id][match_type]['played'] += 1
                            player_dict[player.id][match_type]['pf'] += int(rubber[1])
                            player_dict[player.id][match_type]['pa'] += int(rubber[0])
                            player_dict[player.id][match_type]['diff'] = player_dict[player.id][match_type]['pf'] - player_dict[player.id][match_type]['pa']
                            if int(rubber[0]) < int(rubber[1]):
                                player_dict[player.id][match_type]['won'] += 1
                            player_dict[player.id][match_type]['percent'] = round(player_dict[player.id][match_type]['won'] / player_dict[player.id][match_type]['played'] * 100, 1)

                except Exception as e:
                    raise Exception(f'Error - {x}, {game}, {rubber}, {level_games}, {level_games[x]}, {level_games[x][1]}, {home_players}, {away_players}, {e}')

    return player_dict

def get_player_appearances(player):
    '''Pulls stats for player - times played for each team and teams nominated for
        Used in the league admin view to provide a summary for player'''

    player_fixtures = player.get_own_fixtures()
    team_dict = {}
    team_dict["teams"] = player.club.get_clubs_teams("count")

    team_dict = _count_appearances(player_fixtures, team_dict, player)
    team_dict = _add_eligibility(team_dict, player)
    
    noms = player.get_noms_strings()
    team_dict["noms"] = {"mixed":noms[0],"level":noms[1]}

def _count_appearances(fixtures, team_dict, player):
    '''Count the times player has played for each team'''
    for fixture in fixtures:
        if player in fixture.get_players(side='home'):
            num = fixture.home_team.number
            type = fixture.home_team.type
        else:
            num = fixture.away_team.number
            type = fixture.away_team.type

        team_dict["teams"][type][num] += 1
    
    return team_dict

def _add_eligibility(team_dict, player):
    '''Add player's eligibility status to each team'''
    for team_type in team_dict["teams"].keys():
        for team_num in team_dict["teams"][team_type].keys():
            team = Team.objects.get(club=player.club,number=team_num,type=team_type)
            if not player.check_eligibility(team):
                count = team_dict["teams"][team_type][team_num]
                if count == 0:
                    team_dict["teams"][team_type][team_num] = "X"
                else:
                    team_dict["teams"][team_type][team_num] = "X (" + str(count) + ")"

    return team_dict
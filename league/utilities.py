import league.constants as constants
from rapidfuzz import fuzz
from django.core import signing
from django.http import HttpResponse
from io import BytesIO
import pandas as pd
from datetime import datetime
from .email import email_notification

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
    from league.models import PendingPlayerVerification

    div_type = fixture.division.type
    mixed_player_type = ['Ladies','Ladies','Ladies','Men','Men','Men']
    verifications = []

    for player_title, player_dict in players_found:
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
        email_notification('playernotfound', verifications)

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

# Team related functions
def get_performances():
    '''
    Creates performance records for all teams 
    '''
    from league.models import Season, Fixture, Performance

    season = Season.objects.get(current=True)
    log = f'Season: {season}'
    fixtures = Fixture.objects.filter(season=season)
    log += f' -- Fixtures: {len(fixtures)}'
    divisions = list(set([fix.division for fix in fixtures]))
    log += f' -- Divisions: {len(divisions)}'
    for division in divisions:
        table = division.get_table(season)
        position = 1
        for row in table:
            team = row[1]['Object']
            if not Performance.objects.filter(team=team,season=season,division=division):
                suffix = {1:'st',2:'nd',3:'rd'}.get(position,'th')
                cardinal = f"{position}{suffix} out of {len(table)}"
                p = Performance(team=team, season=season, division=division, position=cardinal)
                p.save()
            position += 1

    return log

# Fixture related functions
def get_fixture_stats():

    from league.models import Season, Fixture

    solo_rubs_to_30 = []
    solo_rubs_to_other = []
    other_rubs_to_other = []
    forfeits = []
    errors = []

    current_season = Season.objects.get(current=True)
    fixtures = Fixture.objects.filter(season=current_season)

    for fix in fixtures:
        if fix.status == 'Conceded (H)' or fix.status == 'Conceded (A)':
            continue
        try:
            srt30 = False
            srto = False
            orto = False
            scores = fix.game_results.split(',')
            if 'FH' in scores or 'FA' in scores:
                forfeits.append(fix)
            scores = [scores[x:x+2] for x in range(0,len(scores),2)]
            if fix.division.type == 'Mixed':
                games = [scores[0:3],scores[3:6],scores[6:9],scores[9:12],scores[12:15],scores[15:18],scores[18:21],scores[21:24],scores[24:27]]
            else:
                games = [scores[0:2],scores[2:4],scores[4:6],scores[6:8],scores[8:10],scores[10:12]]
            for game in games:
                if game[1][0] == '':
                    if game[0][0] == '30' or game[0][1] == '30':
                        srt30 = True
                    else:
                        srto = True
                else:
                    for rubber in game:
                        if rubber[0] != '' and rubber[0] != 'FH' and rubber[0] != 'FA' and rubber[0] != '21' and rubber[1] != '21':
                            if abs(int(rubber[0]) - int(rubber[1])) != 2:
                                if rubber[0] != '30' and rubber[1] != '30':
                                    orto = True
            if srt30:
                solo_rubs_to_30.append(fix)
            if srto:
                solo_rubs_to_other.append(fix)
            if orto:
                other_rubs_to_other.append(fix)
        except Exception:
            errors.append(fix)

    return solo_rubs_to_30, solo_rubs_to_other, other_rubs_to_other, forfeits, errors

# Fixture Download/Upload
def download_fixtures(fixtures, is_admin=False):

    df = build_dataframe(fixtures, is_admin)

    with BytesIO() as b:
        with pd.ExcelWriter(b) as writer:
            df.to_excel(writer)
        filename = "fixtures.xlsx"
        res = HttpResponse(b.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        res['Content-Disposition'] = f'attachment; filename={filename}'

        return res

def build_dataframe(fixtures, is_admin):

    def localiseDT(dtvalue):
        if not pd.isnull(dtvalue):
            return dtvalue.tz_localize(None)
        else:
            return dtvalue

    fixDict = {'Division':[],'Date and Time':[],'Home Team':[], 'Home Points':[], 'Away Points':[],
                'Away Team':[], 'Venue':[], 'Status':[], 'Original Date and Time':[]}
    if is_admin:
        fixDict.update({'Game Breakdown':[]})

    for fix in fixtures:
        fixDict['Division'].append(str(fix.division))
        fixDict['Date and Time'].append(fix.date_time)
        fixDict['Home Team'].append(str(fix.home_team))
        fixDict['Home Points'].append(fix.home_points)
        fixDict['Away Points'].append(fix.away_points)
        fixDict['Away Team'].append(str(fix.away_team))
        fixDict['Venue'].append(str(fix.venue))
        fixDict['Status'].append(fix.status)
        fixDict['Original Date and Time'].append(fix.old_date_time)
        if is_admin:
            fixDict['Game Breakdown'].append(fix.game_results)

    df = pd.DataFrame(fixDict)
    df['Date and Time'] = df['Date and Time'].dt.tz_localize(None)
    df['Original Date and Time'] = df['Original Date and Time'].apply(localiseDT)

    return df

def parse_fixtures(fixtures):
    '''
        Parses and creates fixtures from an uploaded file
    '''
    from league.models import Club, Team, Division, Fixture, Season, Venue

    for row in fixtures.keys():
        fix = fixtures[row]
        home_club = Club.objects.get(short_name=fix['Home Club'])
        away_club = Club.objects.get(short_name=fix['Away Club'])
        fixture = Fixture(
            home_team = Team.objects.get(club=home_club,number=fix['Home Team Num'],type=fix['Division Type']),
            away_team = Team.objects.get(club=away_club,number=fix['Away Team Num'],type=fix['Division Type']),
            date_time = datetime.combine(fix['Date'].date(), fix['Start Time']),
            end_time = fix['End Time'],
            season = Season.objects.get(year=fix['Season']),
            venue = Venue.objects.get(name=fix['Venue']),
            division = Division.objects.get(number=fix['Division No.'],type=fix['Division Type']),
        )
        fixture.save()

# NOT CURRENTLY IMPLEMENTED
def parse_results(fixtures):
    '''
        Parses and creates archive results from an uploaded file
    '''
    from league.models import Club, Fixture, Team, Season, Division

    for row in fixtures.keys():
        fix = fixtures[row]
        home_club = Club.objects.get(short_name=fix['home club'])
        away_club = Club.objects.get(short_name=fix['away club'])
        fixture = Fixture(
            home_team = Team.objects.get(club=home_club,number=fix['home num'],type=fix['type']),
            away_team = Team.objects.get(club=away_club,number=fix['away num'],type=fix['type']),
            home_points = fix['home score'],
            away_points = fix['away score'],
            date_time = fix['date_time'],
            season = Season.objects.get(year=fix['season']),
            division = Division.objects.get(number=fix['div num'],type=fix['type']),
        )
        fixture.save()

    return

def sort_table(team_list):
    # team_list is list of team dictionaries:
    # team_name:{'Played':0,'Won':0,'Drawn':0,'Lost':0,'PFor':0,'PAgainst':0,'Object':''}

    revised_list = []
    points_dict = {}

    for team in team_list:
        points = team[1]['PFor']
        if points in points_dict.keys():
            points_dict[points].append(team)
        else:
            points_dict[points] = [team]

    points_list = list(points_dict.keys())
    points_list.sort(reverse=True)
    for point in points_list:
        if len(points_dict[point]) == 1:
            revised_list.append(points_dict[point][0])
        else:
            pass
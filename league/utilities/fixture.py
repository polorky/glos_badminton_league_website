from league import constants

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

def get_scores(fixture):
    '''
        Adds match points to game scores for viewing match result
        This function will need to be changed if there is an change in the format of the matches
    '''

    if fixture.status != "Played" or not fixture.game_results:
        return None

    # Split game scores which are saved as a single string
    game_split = fixture.game_results.split(',')

    # Batch individual scores into games (now two rubbers each, mixed was previously best of three rubbers)
    # If mixed match and 54 scores (meaning old best of three rubber format)
    if fixture.division.type == 'Mixed' and len(game_split) == 54:
        batched_games = {constants.GAME_NAMES_MIXED[int(i/6)]: game_split[i:i + 6] for i in range(0, len(game_split), 6)}
    # If mixed match and 36 scores (meaning new two rubber format)
    elif fixture.division.type == 'Mixed' and len(game_split) == 36:
        batched_games = {constants.GAME_NAMES_MIXED[int(i/4)]: game_split[i:i + 4] for i in range(0, len(game_split), 4)}
    # Otherwise level format
    else:
        batched_games = {constants.GAME_NAMES_LEVEL[int(i/4)]: game_split[i:i + 4] for i in range(0, len(game_split), 4)}

    # Iterate through batched_games
    for game in batched_games.keys():

        # Separate out individual rubbers
        rubbers = [batched_games[game][i:i+2] for i in range(0, len(batched_games[game]), 2)]
        home_score = 0
        away_score = 0

        # Iterate over rubbers
        for rubber in rubbers:

            # If blank break loop as no further scores
            if rubber[0] == '':
                break
            # Handle away forfeits
            elif rubber[0] == 'FA':
                home_score += 1
            # Handle home forfeits
            elif rubber[0] == 'FH':
                away_score += 1
            # Otherwise find highest score
            elif int(rubber[0]) > int(rubber[1]):
                home_score += 1
            else:
                away_score += 1

        # Work out scoring format (mixed changed from best of three to point per rubber)
        if fixture.division.type == 'Mixed':
            scoring_format = fixture.season.mixed_scoring
        else:
            scoring_format = constants.SCORING_LEVEL

        # If point per game, work out who won most games and add one point
        if scoring_format == 'point per game':
            if home_score > away_score:
                batched_games[game] += [1,0]
            else:
                batched_games[game] += [0,1]
        # Else add point per rubber accounting for forfeited rubbers
        else:
            if home_score + away_score != len(rubbers):
                if rubbers[0][0] == 'FH':
                    batched_games[game] += [len(rubbers),0]
                else:
                    batched_games[game] += [0,len(rubbers)]
            else:
                batched_games[game] += [home_score,away_score]

    return batched_games

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

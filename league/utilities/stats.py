from collections import defaultdict
from league.models import Season, Fixture

def get_league_stats(season='current'):

    if season == 'current':
        season_obj = Season.objects.get(current=True)
    else:
        season_obj = Season.objects.get(year=season)
    fixtures = Fixture.objects.filter(season=season_obj)

    team_dict = {}
    score_dict = defaultdict(int)
    total_dict = {'m':0,'hw':0,'d':0,'c':0,'r':0,'pt':0,'pw':0,'pl':0,'ph':0,'pa':0}

    for fixture in fixtures:

        total_dict['m'] += 1
        ht = fixture.home_team
        at = fixture.away_team
        if ht not in team_dict:
            team_dict[ht] = {'mp':0,'w':0,'d':0,'c':0,'hr':0,'ar':0,'hp':0,'hpa':0,'ap':0,'apa':0,'ww':0,'st':0,'sw':0}
        if at not in team_dict:
            team_dict[at] = {'mp':0,'w':0,'d':0,'c':0,'hr':0,'ar':0,'hp':0,'hpa':0,'ap':0,'apa':0,'ww':0,'st':0,'sw':0}

        team_dict[ht]['mp'] += 1
        team_dict[at]['mp'] += 1

        if not fixture.game_results:
            total_dict['c'] += 1
            if fixture.status == 'Conceded (H)':
                team_dict[ht]['c'] += 1
                team_dict[at]['w'] += 1
            else:
                team_dict[at]['c'] += 1
                team_dict[ht]['w'] += 1
            continue

        tp = 18 if fixture.division.type == 'Mixed' else 12
        if fixture.home_points == tp:
            team_dict[ht]['ww'] += 1
        if fixture.away_points == tp:
            team_dict[at]['ww'] += 1

        if fixture.home_points == fixture.away_points:
            team_dict[ht]['d'] += 1
            team_dict[at]['d'] += 1
            total_dict['d'] += 1
        elif fixture.home_points > fixture.away_points:
            team_dict[ht]['w'] += 1
            total_dict['hw'] += 1
        else:
            team_dict[at]['w'] += 1

        scores = fixture.game_results.split(',')
        scores = [tuple(scores[i:i+2]) for i in range(0, len(scores), 2)]
        scores = [(int(x[0]), int(x[1])) if x[0].isdigit() else x for x in scores]

        for score in scores:

            if isinstance(score[0], str):
                continue

            score_dict[score] += 1
            total_dict['r'] += 1
            total_dict['pt'] += score[0] + score[1]
            total_dict['ph'] += score[0]
            total_dict['pa'] += score[1]

            team_dict[ht]['hp'] += score[0]
            team_dict[at]['ap'] += score[1]
            team_dict[ht]['hpa'] += score[1]
            team_dict[at]['apa'] += score[0]
            if score[0] > score[1]:
                team_dict[ht]['hr'] += 1
                total_dict['pw'] += score[0]
                total_dict['pl'] += score[1]
                if score[0] > 21:
                    team_dict[ht]['st'] += 1
                    team_dict[at]['st'] += 1
                    team_dict[ht]['sw'] += 1
            else:
                team_dict[at]['ar'] += 1
                total_dict['pw'] += score[1]
                total_dict['pl'] += score[0]
                if score[0] > 21:
                    team_dict[at]['st'] += 1
                    team_dict[ht]['st'] += 1
                    team_dict[at]['sw'] += 1

    set_team = max(team_dict, key=lambda team: team_dict[team]['sw'])
    set_string = f"{set_team} ({team_dict[set_team]['sw']})"
    ww_team = max(team_dict, key=lambda team: team_dict[team]['ww'])
    ww_string = f"{ww_team} ({team_dict[ww_team]['ww']})"

    stats = {
        'Total Matches': total_dict['m'],
        'Total Home Wins': total_dict['hw'],
        'Total Away Wins': total_dict['m'] - total_dict['hw'] - total_dict['d'] - total_dict['c'],
        'Total Draws': total_dict['d'],
        'Total Conceded': total_dict['c'],
        'Total Rubbers': total_dict['r'],
        'Total Points': total_dict['pt'],
        'Total Home Points': total_dict['ph'],
        'Total Away Points': total_dict['pa'],
        'Total Points of Winner': total_dict['pw'],
        'Total Points of Loser': total_dict['pl'],
        'Average Winning Score': round(total_dict['pw'] / total_dict['r'], 2),
        'Average Losing Score': round(total_dict['pl'] / total_dict['r'], 2),
        'Most Common Scoreline': max(score_dict, key=score_dict.get),
        'Teams with perfect records': [],
        'Mixed Team with most points per match': None,
        "Women's Team with most points per match": None,
        "Men's Team with most points per match": None,
        'Most games won on setting': set_string,
        'Most matches whitewashed': ww_string,
        'Biggest Average Game Winning Margin (Mixed)': None,
        "Biggest Average Game Winning Margin (Women's)": None,
        "Biggest Average Game Winning Margin (Men's)": None,
    }

    for team, team_stats in team_dict.items():
        team_type = team.type
        if team_stats['mp'] == team_stats['w']:
            stats['Teams with perfect records'].append(str(team))
        ppm = round((team_stats['hr'] + team_stats['ar']) / (team_stats['mp'] - team_stats['c']), 2)
        rpm = 18 if team_type == 'Mixed' else 12
        avemgn = round((team_stats['hp'] + team_stats['ap'] - team_stats['hpa'] - team_stats['apa']) / ((team_stats['mp'] - team_stats['c']) * rpm), 2)
        if team_type == 'Mixed':
            if not stats['Mixed Team with most points per match']:
                stats['Mixed Team with most points per match'] = f'{team} ({ppm})'
            else:
                current = float(stats['Mixed Team with most points per match'].split('(')[1].replace(')',''))
                if ppm > current:
                    stats['Mixed Team with most points per match'] = f'{team} ({ppm})'
            if not stats['Biggest Average Game Winning Margin (Mixed)']:
                stats['Biggest Average Game Winning Margin (Mixed)'] = f'{team} ({avemgn})'
            else:
                current = float(stats['Biggest Average Game Winning Margin (Mixed)'].split('(')[1].replace(')',''))
                if avemgn > current:
                    stats['Biggest Average Game Winning Margin (Mixed)'] = f'{team} ({avemgn})'
        elif team_type == 'Ladies':
            if not stats["Women's Team with most points per match"]:
                stats["Women's Team with most points per match"] = f'{team} ({ppm})'
            else:
                current = float(stats["Women's Team with most points per match"].split('(')[1].replace(')',''))
                if ppm > current:
                    stats["Women's Team with most points per match"] = f'{team} ({ppm})'
            if not stats["Biggest Average Game Winning Margin (Women's)"]:
                stats["Biggest Average Game Winning Margin (Women's)"] = f'{team} ({avemgn})'
            else:
                current = float(stats["Biggest Average Game Winning Margin (Women's)"].split('(')[1].replace(')',''))
                if avemgn > current:
                    stats["Biggest Average Game Winning Margin (Women's)"] = f'{team} ({avemgn})'
        elif team_type == 'Mens':
            if not stats["Men's Team with most points per match"]:
                stats["Men's Team with most points per match"] = f'{team} ({ppm})'
            else:
                current = float(stats["Men's Team with most points per match"].split('(')[1].replace(')',''))
                if ppm > current:
                    stats["Men's Team with most points per match"] = f'{team} ({ppm})'
            if not stats["Biggest Average Game Winning Margin (Men's)"]:
                stats["Biggest Average Game Winning Margin (Men's)"] = f'{team} ({avemgn})'
            else:
                current = float(stats["Biggest Average Game Winning Margin (Men's)"].split('(')[1].replace(')',''))
                if avemgn > current:
                    stats["Biggest Average Game Winning Margin (Men's)"] = f'{team} ({avemgn})'

    return stats

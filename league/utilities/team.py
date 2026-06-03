from league.models import Season, Fixture, Performance, Club, Team

def get_performances():
    '''
    Creates performance records for all teams 
    '''

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

def check_team_entries():

    results_dict = {}
    errors_dict = {'Clubs':[], 'Teams':[]}

    for club in Club.objects.filter(active=True):

        if not club.teams_confirmed:
            errors_dict['Clubs'].append(club)

        all_teams = Team.objects.filter(active=True, club=club)
        mixed_teams = Team.objects.filter(active=True, club=club, type='Mixed')
        womens_teams = Team.objects.filter(active=True, club=club, type='Womens')
        mens_teams = Team.objects.filter(active=True, club=club, type='Mens')

        results_dict[club] = {'Mixed': mixed_teams, 'Womens': womens_teams, 'Mens': mens_teams}

        for team in all_teams:
            if not team.home_venue or not team.start_time or not team.end_time:
                errors_dict['Teams'].append({'Venue': team.home_venue, 'Start': team.start_time, 'End': team.end_time})

    return results_dict, errors_dict

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

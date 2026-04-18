from django.http import HttpResponse
from io import BytesIO
import pandas as pd
from datetime import datetime

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

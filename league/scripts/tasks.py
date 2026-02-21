import sys
path = '/home/gloubadleague/leagueWebsite'
if path not in sys.path:
    sys.path.append(path)

import django
import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'leagueWebsite.settings'
django.setup()

from django.core.mail import send_mail
from datetime import datetime, timedelta
from league.models import Fixture, Penalty, Season, Club
from django.db.models import Q
from django.utils import timezone
import pytz

late_submission_penalty_value = 5

def run(test):

    def get_recipients(fix, team, club=None):

        if club:
            recipients = [club.contact1_email, club.contact2_email]
        else:
            recipients = [team.club.contact1_email, team.club.contact2_email, team.captain_email]

        for i in range(len(recipients),0,-1):
            if not recipients[i-1]:
                recipients.pop(i-1)

        return recipients

    sender = 'GlosBadWebsite@gmail.com'

    #right_now = datetime(2022,10,4,9,0,0,0, pytz.UTC)
    right_now = timezone.now()
    current_season = Season.objects.get(current=True)
    all_fix = list(Fixture.objects.filter(season=current_season))
    outstanding_fixtures = []
    overdue_fixtures = []
    proposed_fixtures = []
    all_proposed_fixtures = []
    postponed_fixtures = {}
    bad_statuses = ['Unplayed','Rearranged']

    if right_now.weekday() == 5 or test:
        saturday = True
    else:
        saturday = False

    for fix in all_fix:
        if fix.date_time < (right_now - timedelta(14)) and fix.status in bad_statuses:
            overdue_fixtures.append(fix)
        elif fix.date_time < (right_now - timedelta(7)) and fix.status in bad_statuses:
            outstanding_fixtures.append(fix)
        elif fix.date_time < right_now and fix.status == 'Proposed':
            proposed_fixtures.append(fix)
        if (saturday or test) and fix.status == 'Postponed':
            if fix.home_team.club.name in postponed_fixtures.keys():
                postponed_fixtures[fix.home_team.club.name].append(fix)
            else:
                postponed_fixtures[fix.home_team.club.name] = [fix]
        if (saturday or test) and fix.status == 'Proposed':
            all_proposed_fixtures.append(fix)

    for fix in overdue_fixtures:
        try:
            Penalty.objects.get(team=fix.home_team, penalty_type='Late Submission', fixture=fix)
        except:
            subject = 'Late Results Submission - Penalty Applied'
            recipients = get_recipients(fix, fix.home_team)
            body = "Hi,\n\nThe result of the match " + str(fix) + " has still not been submitted and is now two weeks late so a penalty has been applied to your team." \
            + "\nPlease contact the League Committee at GlosBadCorrespondence@outlook.com if there are extenuating circumstances you would like to raise." \
            + "\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***"

            if test:
                recipients = ['schofieldmark@gmail.com']

            send_mail(subject, body, sender, recipients)

            if test:
                break

            p = Penalty(season=fix.season, team=fix.home_team, penalty_value=late_submission_penalty_value, penalty_type='Late Submission', player='', fixture=fix)
            p.save()

    for fix in outstanding_fixtures:
        subject = 'Results Submission Outstanding'
        recipients = get_recipients(fix, fix.home_team)
        body = "Hi,\n\nThe result of the match " + str(fix) + " has not been yet been submitted despite it being scheduled for at least a week ago. If the result is not submitted" \
        + " within 14 days of the match date, your club's team will get an automatic penalty. If the match has been postponed or rescheduled, please update it on the league website to avoid" \
        + " a penalty being applied.\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***"

        if test:
            recipients = ['schofieldmark@gmail.com']

        send_mail(subject, body, sender, recipients)

    for fix in proposed_fixtures:
        subject = 'Proposed Match Date Passed'
        recipients = get_recipients(fix, fix.away_team)
        body = "Hi,\n\nThe match " + str(fix) + ' is still in a "Proposed" state meaning that the home team have proposed a new date for the fixture but your club have not' \
        + " confirmed it. This date is also now in the past so please either accept the date if the match was played so that the home team can submit the result or reject" \
        + " the date if the match was not played so that the home team can submit a new date.\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league" \
        + " website***"

        if test:
            recipients = ['schofieldmark@gmail.com']

        send_mail(subject, body, sender, recipients)

    if saturday or test:

        for clubname in postponed_fixtures.keys():
            club = Club.objects.get(name=clubname)
            subject = 'Postponed Matches not yet Rescheduled'
            recipients = get_recipients(fix, None, club=club)
            body = "Hi,\n\nThis is your weekly reminder of postponed home matches that have yet to be rescheduled. Please ensure a new date is found for these matches as" \
            + " soon as possible noting that the league rules state that matches must be rearranged within 21 days of the original date.\n\n"
            for fix in postponed_fixtures[clubname]:
                body += str(fix) + '\n'
            body += "\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***"

            if test:
                recipients = ['schofieldmark@gmail.com']

            send_mail(subject, body, sender, recipients)

        for fix in all_proposed_fixtures:
            subject = 'Reschedule Proposals Not Yet Accepted'
            recipients = get_recipients(fix, fix.away_team)
            body = "Hi,\n\nThe home team for following match have proposed a new date/venue but your team has yet to accept the new details." \
            + " Please accept (or reject) the proposed details via the league website (if rejecting, please also contact the other club to say why).\n\n" \
            + str(fix) + "\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***"
            html = "Hi,<br><br>The home team for the following match have proposed a new date/venue but your team has yet to accept the new details." \
            + " Please accept (or reject) the proposed details by clicking on the link below (if rejecting, please also contact the other club to say why).<br><br>" \
            + '<a href="https://gloubadleague.pythonanywhere.com/fixtures/' + str(fix.id) + '/update/div">' + str(fix) + "</a><br><br>Regards<br><br>League Committee" \
            + "<br><br>***This is an automated email from the league website***"

            if test:
                recipients = ['schofieldmark@gmail.com']

            send_mail(subject, body, sender, recipients, html_message = html)

        next_week = right_now + timedelta(14)
        upcoming_fixtures = Fixture.objects.filter(season=current_season).filter(date_time__lte=next_week).filter(date_time__gte=right_now).filter(status__in=['Unplayed','Rearranged','Proposed'])

        clubs = [fix.home_team.club for fix in upcoming_fixtures]
        clubs += [fix.away_team.club for fix in upcoming_fixtures]
        clubs = list(set(clubs))

        for club in clubs:
            if not club.club_notifications:
                continue
            club_fix = upcoming_fixtures.filter(Q(home_team__club=club)|Q(away_team__club=club))
            subject = 'Upcoming Club Fixtures'
            recipients = get_recipients(fix, None, club=club)
            body = "Hi,\n\nHere are the fixtures for your club in the next TWO WEEKS (time period has been extended to give more notice for games earlier in the week):\n\n"
            for fix in club_fix:
                body += fix.date_time.strftime("%d/%m/%Y %H:%M") + ' - ' + str(fix) + '\n'
            body += "\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***"
            html = "Hi,<br><br>Here are the fixtures for your club in the next TWO WEEKS (time period has been extended to give more notice for games earlier in the week):<br><br>"
            for fix in club_fix:
                html += fix.date_time.strftime("%d/%m/%Y %H:%M") + ' - <a href="https://gloubadleague.pythonanywhere.com/fixtures/' + str(fix.id) + '/fix">' + str(fix) + '</a><br>'
            html += "<br><br>Regards<br><br>League Committee<br><br>***This is an automated email from the league website***"

            if test:
                recipients = ['schofieldmark@gmail.com']

            send_mail(subject, body, sender, recipients, html_message = html)

            if test:
                break

        teams = [fix.home_team for fix in upcoming_fixtures]
        teams += [fix.away_team for fix in upcoming_fixtures]
        teams = list(set(teams))

        for team in teams:

            if not team.captain_email or not team.club.captain_notifications:
                continue

            team_fix = upcoming_fixtures.filter(Q(home_team=team)|Q(away_team=team))
            subject = 'Upcoming Team Fixtures'
            recipients = [team.captain_email]
            body = "Hi,\n\nHere are the fixtures for your team in the next TWO WEEKS (time period has been extended to give more notice for games earlier in the week):\n\n"
            for fix in team_fix:
                body += fix.date_time.strftime("%d/%m/%Y %H:%M") + ' - ' + str(fix) + '\n'
            body += "\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***"
            html = "Hi,<br><br>Here are the fixtures for your team in the next TWO WEEKS (time period has been extended to give more notice for games earlier in the week):<br><br>"
            for fix in team_fix:
                html += fix.date_time.strftime("%d/%m/%Y %H:%M") + ' - <a href="https://gloubadleague.pythonanywhere.com/fixtures/' + str(fix.id) + '/fix">' + str(fix) + '</a><br>'
            html += "<br><br>Regards<br><br>League Committee<br><br>***This is an automated email from the league website***"

            if test:
                recipients = ['schofieldmark@gmail.com']

            send_mail(subject, body, sender, recipients, html_message = html)

            if test:
                break

run(False)
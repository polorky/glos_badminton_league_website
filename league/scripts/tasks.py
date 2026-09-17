import sys
import os
import django

path = '/home/gloubadleague/leagueWebsite'
if path not in sys.path:
    sys.path.append(path)
os.environ['DJANGO_SETTINGS_MODULE'] = 'leagueWebsite.settings'
django.setup()

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils import timezone
from django.conf import settings

from datetime import timedelta

from league import constants
from league.models import Fixture, Penalty, Season, Club, Team
from league.utilities.email import email_notification


def run(test):

    right_now = timezone.now()
    current_season = Season.objects.get(current=True)
    saturday = right_now.weekday() == 5 or test

    fourteen_ago = right_now - timedelta(14)
    seven_ago    = right_now - timedelta(7)
    bad_statuses = ['Unplayed', 'Rearranged']

    base = Fixture.objects.filter(season=current_season).select_related(
        'home_team__club', 'away_team__club', 'season'
    )

    # No result submitted and 14+ days past
    overdue_fixtures = base.filter(date_time__lt=fourteen_ago, status__in=bad_statuses)

    # No result submitted and 7–14 days past
    outstanding_fixtures = base.filter(
        date_time__gte=fourteen_ago, date_time__lt=seven_ago, status__in=bad_statuses
    )

    # Proposed date has now passed without acceptance
    proposed_fixtures = base.filter(date_time__lt=right_now, status='Proposed')

    for fix in overdue_fixtures:
        try:
            Penalty.objects.get(team=fix.home_team, penalty_type='Late Submission', fixture=fix)
        except ObjectDoesNotExist:
            email_notification('late_result_penalty', fixture=fix)
            if not test:
                Penalty.objects.create(
                    season=fix.season, team=fix.home_team,
                    penalty_value=constants.PENALTY_LATE_SUBMISSION,
                    penalty_type='Late Submission', player='', fixture=fix
                )

    for fix in outstanding_fixtures:
        email_notification('outstanding_results', fixture=fix)

    for fix in proposed_fixtures:
        email_notification('proposed_date_passed', fixture=fix)

    if saturday:

        # Postponed fixtures grouped by home club
        postponed = base.filter(status='Postponed')
        postponed_clubs = Club.objects.filter(
            id__in=postponed.values('home_team__club')
        ).distinct()
        for club in postponed_clubs:
            club_postponed = postponed.filter(home_team__club=club)
            email_notification(
                'postponed_not_rescheduled',
                fixture=club_postponed.first(),
                club=club,
                postponed_fixtures=club_postponed,
            )

        # All still-open proposed fixtures
        for fix in base.filter(status='Proposed'):
            email_notification('proposed_not_accepted', fixture=fix)

        # Upcoming fixtures in the next 14 days
        upcoming = base.filter(
            date_time__gte=right_now,
            date_time__lte=right_now + timedelta(14),
            status__in=['Unplayed', 'Rearranged', 'Proposed'],
        )

        clubs = Club.objects.filter(
            Q(id__in=upcoming.values('home_team__club')) |
            Q(id__in=upcoming.values('away_team__club'))
        ).distinct()

        for club in clubs:
            if not club.club_notifications:
                continue
            club_fix = upcoming.filter(Q(home_team__club=club) | Q(away_team__club=club))
            email_notification('upcoming_fixtures', fixtures=club_fix, obj=club, obj_type='club')
            if test:
                break

        teams = Team.objects.filter(
            Q(id__in=upcoming.values('home_team')) |
            Q(id__in=upcoming.values('away_team'))
        ).select_related('club')

        for team in teams:
            if not team.captain_email or not team.club.captain_notifications:
                continue
            team_fix = upcoming.filter(Q(home_team=team) | Q(away_team=team))
            email_notification('upcoming_fixtures', fixtures=team_fix, obj=team, obj_type='team')
            if test:
                break

run(settings.DEBUG)
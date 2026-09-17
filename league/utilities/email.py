from django.core.mail import send_mail
from django.conf import settings
import league.constants as constants

BASE_URL = 'https://gloubadleague.pythonanywhere.com'
SENDER = 'GlosBadWebsite@gmail.com'
ADMIN_EMAIL = 'schofieldmark@gmail.com'
FIXTURES_EMAIL = 'GlosBadCorrespondence@outlook.com'
COMMITTEE_EMAILS = [
    'martin.godwin@btinternet.com',
    'johnsexton1955@yahoo.co.uk',
    'peter.sexton@bt.com',
    'schofieldmark@gmail.com'
]
TESTING_ENV = settings.DEBUG

class LeagueEmail:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.subject = ''
        self.body = ''
        self.html = ''
        self.recipients = []

    def get_admin_recipients(self):
        if TESTING_ENV:
            return [ADMIN_EMAIL]
        else:
            return COMMITTEE_EMAILS

    def get_recipients(self, obj, obj_type='team'):
        if TESTING_ENV:
            return [ADMIN_EMAIL,]
        if obj_type == 'team':
            return self._filter_emails([
                obj.club.contact1_email,
                obj.club.contact2_email,
                obj.captain_email
            ])
        elif obj_type == 'club':
            return self._filter_emails([
                obj.contact1_email,
                obj.contact2_email
            ])
        
    def get_team_recipients(self, team):
        if TESTING_ENV:
            return [ADMIN_EMAIL,]
        fix = self.kwargs['fixture']
        emails = []
        if team == 'home' or team == 'both':
            emails.extend([
                fix.home_team.club.contact1_email,
                fix.home_team.club.contact2_email,
                fix.home_team.captain_email
            ])
        elif team == 'away' or team == 'both':
            emails.extend([
                fix.away_team.club.contact1_email,
                fix.away_team.club.contact2_email,
                fix.away_team.captain_email
            ])
        return self._filter_emails(emails)
    
    def _filter_emails(self, emails):
        return [e for e in emails if e]

    def _footer(self, html=False):
        if html:
            return (f'<br><br>For any issues surrounding fixtures, please contact '
                    f'<a href="mailto:{FIXTURES_EMAIL}">{FIXTURES_EMAIL}</a>'
                    f'<br>For technical issues with the website, please reply to this email')
        return (f'\n\nFor any issues surrounding fixtures, please contact {FIXTURES_EMAIL}'
                f'\nFor technical issues with the website, please reply to this email')

    def _regards(self, html=False):
        if html:
            return '<br><br>Regards<br><br>League Committee<br><br>***This is an automated email from the league website***'
        return '\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'

    def send(self):
        body = self.body + self._regards() + self._footer()
        if self.html:
            html = self.html + self._regards(html=True) + self._footer(html=True)
            send_mail(self.subject, body, SENDER, self.recipients, html_message=html)
        else:
            send_mail(self.subject, body, SENDER, self.recipients)


class ResultEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = self.kwargs['fixture']
        self.subject = f'{fix} - Result Submitted'
        self.recipients = self.get_team_recipients('away')
        fix_url = f'{BASE_URL}/fixtures/{fix.id}'
        self.body = (f'Hi,\n\nThe home team have submitted the results for the match {fix} '
                     f'played on {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")}. '
                     f'You can view the score submitted on this page: {fix_url}\n\n'
                     f'If you believe the result has been entered incorrectly, please contact '
                     f'the league by replying to this email.')
        self.html = (f'Hi,<br><br>The home team have submitted the results for the match {fix} '
                     f'played on {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")}. '
                     f'You can view the score submitted <a href="{fix_url}">here</a>.<br><br>'
                     f'If you believe the result has been entered incorrectly, please contact '
                     f'the league by replying to this email.')


class RescheduleEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = self.kwargs['fixture']
        self.subject = f'{fix} - New Date Proposed'
        self.recipients = self.get_team_recipients('away')
        fix_url = f'{BASE_URL}/fixtures/{fix.id}/update/div'
        self.body = (f'Hi,\n\nThe home team have proposed a new date/venue for the match {fix} '
                     f'originally scheduled for {fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S")}. '
                     f'The proposed new date is {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")} '
                     f'at {fix.venue}.\n\nPlease confirm or reject this rearrangement via this page: {fix_url}')
        self.html = (f'Hi,<br><br>The home team have proposed a new date/venue for the match {fix} '
                     f'originally scheduled for {fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S")}. '
                     f'The proposed new date is {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")} '
                     f'at {fix.venue}.<br><br>'
                     f'Please confirm or reject this rearrangement by clicking '
                     f'<a href="{fix_url}">here</a>.')


class RearrangedEmail(LeagueEmail):
    def __int__(self, **kwargs):
        super().__init__(**kwargs)
        fix = self.kwargs['fixture']
        self.subject = f'{fix} - Rearrangement Confirmed'
        self.recipients = self.get_team_recipients('home')
        self.body = (f'Hi,\n\nThe away team have confirmed the rearrangement of the match {fix} '
                     f'originally scheduled for {fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S")} '
                     f'and now scheduled for {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")} at '
                     f'{fix.venue}.')


class RejectedEmail(LeagueEmail):
    def __int__(self, **kwargs):
        super().__init__(**kwargs)
        fix = self.kwargs['fixture']
        self.subject = f'{fix} - Rearrangement Rejected'
        self.recipients = self.get_team_recipients('home')
        self.body = (f'Hi,\n\nThe away team have REJECTED the proposed rearrangement of the match '
                     f'{fix} originally scheduled for {fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S")} '
                     f'and proposed to be rearranged for {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")} '
                     f'at {fix.venue}.\n\nPlease contact the away team to discuss why the rearrangement '
                     f'was rejected and agree a new date/venue. Fixture status has been returned to '
                     f'"Postponed".')


class ConcessionEmail(LeagueEmail):
    def __init__(self, side, **kwargs):
        super().__init__(**kwargs)
        fix = self.kwargs['fixture']
        penalty_value = constants.PENALTY_MIXED_CONCEDED if fix.division.type == "Mixed" else constants.PENALTY_LEVEL_CONCEDED
        team = 'home' if side == 'home' else 'away'
        other_team = 'away' if side == 'home' else 'home'
        self.subject = f'{fix} - Match Conceded'
        self.recipients = self.get_team_recipients('both')
        self.body = (f'Hi,\n\nThe {team} team have conceded the match {fix} scheduled for '
                     f'{fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")}. '
                     f'The {team} team will be penalised {penalty_value}. '
                     f"The {other_team} team's points will not be updated to reflect the concession until "
                     f'the end of the season but the fixture status has been updated to record the concession.')


class PlayerNotFoundEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = self.kwargs['fixture']
        self.subject = 'Player Not Found - Action Required'
        self.recipients = self.get_team_recipients('away')
        verifications = kwargs['verifications']
        self.body = f'Hi,\n\nNot all away players for the match {fix} could be identified.'
        self.html = f'Hi,<br><br>Not all away players for the match {fix} could be identified.'

        for v in verifications:
            verify_url = f'{BASE_URL}/verify-player/{v.token}'
            if v.suggested_player:
                self.body += (f'\nEntered name: {v.submitted_name} --- '
                              f'Suggested Player: {v.suggested_player} --- '
                              f'Correct: {verify_url}/correct --- '
                              f'Not correct: {verify_url}/incorrect')
                self.html += (f'<br>Entered name: {v.submitted_name} --- '
                              f'Suggested Player: {v.suggested_player} --- '
                              f'<a href="{verify_url}/correct">Correct player</a> --- '
                              f'<a href="{verify_url}/incorrect">Not correct</a>')
            else:
                self.body += f'\nEntered name: {v.submitted_name} --- Find/create player: {verify_url}/nosuggest'
                self.html += (f'<br>Entered name: {v.submitted_name} --- '
                              f'<a href="{verify_url}/nosuggest">Find/create player</a>')


class PostponedEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = self.kwargs['fixture']
        self.subject = f'{fix} - Match Postponed'
        self.recipients = self.get_team_recipients('away')
        self.body = (f'Hi,\n\nThe home team have postponed the match {fix} originally scheduled '
                     f'for {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")}. Hopefully, they have '
                     f'been in touch to explain why and to initiate the process of finding a new '
                     f'date/venue.')


class NominationPenEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = self.kwargs['fixture']
        self.subject = 'Nomination Penalty Applied'
        self.recipients = self.get_recipients(kwargs['team'])
        self.body = (f'Hi,\n\nFollowing the submission of the result for the match {fix}, your '
                     f"club's team has played their first three matches. However, nominated player "
                     f"{kwargs['player_name']} has not played at least 50% of the team's matches "
                     f'and so the team has been penalised {constants.PENALTY_NOMINATION_VIOLATION} '
                     f'points. Please contact the League Committee at GlosBadCorrespondence@outlook.com '
                     f'if there are extenuating circumstances you would like to raise.')
        self.html = (f'Hi,<br><br>Following the submission of the result for the match {fix}, your '
                     f"club's team has played their first three matches. However, nominated player "
                     f"<b>{kwargs['player_name']}</b> has not played at least 50% of the team's matches "
                     f'and so the team has been penalised {constants.PENALTY_NOMINATION_VIOLATION} '
                     f'points. Please contact the League Committee at GlosBadCorrespondence@outlook.com '
                     f'if there are extenuating circumstances you would like to raise.')


class EligibilityPenEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = self.kwargs['fixture']
        self.subject = 'Eligibility Penalty Applied'
        self.recipients = self.get_recipients(kwargs['team'])
        self.body = (f'Hi,\n\nFollowing the submission of the result for the match {fix}, it has been '
                     f'identified that player {kwargs["player_name"]} was ineligible to play and so your '
                     f"club's team has been penalised {constants.PENALTY_INELIGIBLE_PLAYER} points. Please "
                     f'contact the League Committee at GlosBadCorrespondence@outlook.com if there are '
                     f'extenuating circumstances you would like to raise.')
        self.html = (f'Hi,<br><br>Following the submission of the result for the match {fix}, it has been '
                     f'identified that player <b>{kwargs["player_name"]}</b> was ineligible to play and so your '
                     f"club's team has been penalised {constants.PENALTY_INELIGIBLE_PLAYER} points. Please "
                     f'contact the League Committee at GlosBadCorrespondence@outlook.com if there are '
                     f'extenuating circumstances you would like to raise.')


class LateResultPenEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = kwargs.get('fixture')
        self.subject = 'Late Results Submission - Penalty Applied'
        self.recipients = self.get_team_recipients('home')
        self.body = (f"Hi,\n\nThe result of the match {fix} has still not been submitted and is now two "
                     f"weeks late so a penalty has been applied to your team.\nPlease contact the League "
                     f"Committee at {FIXTURES_EMAIL} if there are extenuating circumstances "
                     f"you would like to raise.")


class OutstandingResultsEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = kwargs.get('fixture')
        self.subject = 'Results Submission Outstanding'
        self.recipients = self.get_team_recipients('home')
        self.body = (f"Hi,\n\nThe result of the match {fix} has not been yet been submitted despite it being "
                     f"scheduled for at least a week ago. If the result is not submitted within 14 days of the "
                     f"match date, your club's team will get an automatic penalty. If the match has been postponed "
                     f"or rescheduled, please update it on the league website to avoid a penalty being applied.")


class ProposedDatePassedEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = kwargs.get('fixture')
        self.subject = 'Proposed Match Date Passed'
        self.recipients = self.get_team_recipients('away')
        self.body = (f"Hi,\n\nThe match {fix} is still in a 'Proposed' state meaning that the home team have proposed "
                     f"a new date for the fixture but your club have not confirmed it. This date is also now in the "
                     f"past so please either accept the date if the match was played so that the home team can submit "
                     f"the result or reject the date if the match was not played so that the home team can submit a new date.")


class PostponedFixturesEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = kwargs.get('fixture')
        club = kwargs.get('club')
        postponed_fixtures = kwargs.get('postponed_fixtures')
        self.subject = 'Postponed Matches not yet Rescheduled'
        self.recipients = self.get_recipients(club, obj_type='club')
        self.body = (f"Hi,\n\nThis is your weekly reminder of postponed home matches that have yet to be rescheduled. Please "
                     f"ensure a new date is found for these matches as soon as possible noting that the league rules state "
                     f"that matches must be rearranged within 21 days of the original date.\n\n")
        for fix in postponed_fixtures:
            self.body += f'{fix}\n'


class ProposedFixturesEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fix = kwargs.get('fixture')
        self.subject = 'Reschedule Proposals Not Yet Accepted'
        self.recipients = self.get_team_recipients('away')
        self.body = (f"Hi,\n\nThe home team for following match have proposed a new date/venue but your team has yet to accept "
                     f"the new details. Please accept (or reject) the proposed details via the league website (if rejecting, "
                     f"please also contact the other club to say why).\n\n{fix}")
        self.html = (f"Hi,<br><br>The home team for the following match have proposed a new date/venue but your team has yet to "
                     f"accept the new details. Please accept (or reject) the proposed details by clicking on the link below (if "
                     f"rejecting, please also contact the other club to say why).<br><br>"
                     f'<a href="https://gloubadleague.pythonanywhere.com/fixtures/{fix.id}/update/div">{fix}</a>')


class UpcomingFixturesEmail(LeagueEmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        fixtures = kwargs.get('fixtures')
        obj = kwargs.get('obj')
        obj_type = kwargs.get('obj_type')
        self.subject = f'Upcoming {obj_type.title()} Fixtures'
        self.recipients = self.get_recipients(obj, obj_type=obj_type)
        self.body = f"Hi,\n\nHere are the fixtures for your {obj_type} in the next TWO WEEKS:\n\n"
        for fix in fixtures:
            self.body += f'{fix.date_time.strftime("%d/%m/%Y %H:%M")} - {fix}\n'
        self.html = f"Hi,<br><br>Here are the fixtures for your {obj_type} in the next TWO WEEKS:<br><br>"
        for fix in fixtures:
            self.html += f'{fix.date_time.strftime("%d/%m/%Y %H:%M")} - <a href="https://gloubadleague.pythonanywhere.com/fixtures/{fix.id}/fix">{fix}</a><br>'


class NominationSubmittedEmail(LeagueEmail):
    def __init__(self, nom, **kwargs):
        super().__init__(**kwargs)
        nom_url = f'{BASE_URL}/nominations/admin/{nom.id}'
        self.subject = 'Nomination Change Request'
        self.recipients = self.get_admin_recipients()
        self.body = (f'Hi,\n\n{nom.team.club} has submitted a request to change a nomination for the team {nom.team}. '
                     f'Please go to the following page to view the players involved and their current playing stats:'
                     f'\n\n{nom_url}\n\nPlease approve/reject the request via that page, if rejecting it please contact '
                     f'the club directly to explain why.')
        self.html = (f'Hi,<br><br>{nom.team.club} has submitted a request to change a nomination for the team {nom.team}. '
                     f'Please <a href={nom_url}>click here</a> to view the players involved and their current '
                     f'playing stats. Please approve/reject the request via that page, if rejecting it please contact '
                     f'the club directly to explain why.')


class NominationApprovedEmail(LeagueEmail):
    def __init__(self, nom, cur_nom, **kwargs):
        super().__init__(**kwargs)
        self.subject = 'Nomination Change Approved'
        self.recipients = self.get_recipients(nom.team)
        self.body = (f"Hi,\n\nThe nomination change request to replace {cur_nom.player} with "
                     f"{nom.player} for {nom.team} has been approved.")
        self.html = (f"Hi,<br><br>The nomination change request to replace {cur_nom.player} with "
                     f"{nom.player} for {nom.team} has been approved.")


class NominationRejectedEmail(LeagueEmail):
    def __init__(self, nom, cur_nom, **kwargs):
        super().__init__(**kwargs)
        reason = kwargs.get('reason', '')
        self.subject = 'Nomination Change Request Rejected'
        self.recipients = self.get_recipients(nom.team)
        reason_text = f'\n\nReason: {reason}' if reason else ''
        reason_html = f'<br><br>Reason: {reason}' if reason else ''
        self.body = (f"Hi,\n\nThe league committee has rejected the nomination change request "
                     f"to replace {cur_nom.player} with {nom.player} for {nom.team}.{reason_text}\n\n"
                     f"Please contact the league committee if you would like to discuss this.")
        self.html = (f"Hi,<br><br>The league committee has rejected the nomination change request "
                     f"to replace {cur_nom.player} with {nom.player} for {nom.team}.{reason_html}<br><br>"
                     f"Please contact the league committee if you would like to discuss this.")




EMAIL_CLASSES = {
    'result': ResultEmail,
    'postponed': PostponedEmail,
    'reschedule': RescheduleEmail,
    'confirmed': RearrangedEmail,
    'rejected': RejectedEmail,
    'playernotfound': PlayerNotFoundEmail,
    'nomination_penalty': NominationPenEmail,
    'eligibility_penalty': EligibilityPenEmail,
    'late_result_penalty': LateResultPenEmail,
    'outstanding_results': OutstandingResultsEmail,
    'proposed_date_passed': ProposedDatePassedEmail,
    'postponed_not_rescheduled': PostponedFixturesEmail,
    'proposed_not_accepted': ProposedFixturesEmail,
    'upcoming_fixtures': UpcomingFixturesEmail,
    'nomination_submitted': NominationSubmittedEmail,
    'nomination_approved': NominationApprovedEmail,
    'nomination_rejected': NominationRejectedEmail,
}


def email_notification(status, *args, **kwargs):
    if status in ('concededhome', 'concededaway'):
        side = 'home' if status == 'concededhome' else 'away'
        email = ConcessionEmail(side, *args, **kwargs)
    else:
        email_class = EMAIL_CLASSES[status]
        email = email_class(*args, **kwargs)
    email.send()


def email_admin(dup_player, cor_player, fix, code):

    if code == 'done':
        body = str(dup_player.club) + ' have submitted a player correction for ' + str(fix) + '. The erroneously created player was ' + dup_player.name \
        + ' and the correct player is ' + cor_player.name + '. Update was successful.'
        subject = 'Duplicate Player'
    elif code == 'notfound':
        body = str(dup_player.club) + ' have submitted a player correction for ' + str(fix) + '. The erroneously created player was ' + dup_player.name \
        + ' and the correct player is ' + cor_player.name + '. Fixture containing player not found.'
        subject = 'Duplicate Player Error'
    elif code == 'fixerror':
        body = str(dup_player.club) + ' have submitted a player correction for ' + str(fix) + '. The erroneously created player was ' + dup_player.name \
        + ' and the correct player is ' + cor_player.name + '. Player has played too many fixtures.'
        subject = 'Duplicate Player Error'

    send_mail(subject, body, 'GlosBadWebsite@gmail.com', ['schofieldmark@gmail.com'])

    return


def get_all_club_contacts():
    from league.models import Club

    clubs = Club.objects.filter(active=True)
    email_list = {}

    for club in clubs:
        if club.contact1_email:
            email_list[f'{club.short_name} Contact 1'] = club.contact1_email
        if club.contact2_email:
            email_list[f'{club.short_name} Contact 2'] = club.contact2_email

    return email_list

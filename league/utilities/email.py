from django.core.mail import send_mail
import league.constants as constants

BASE_URL = 'https://gloubadleague.pythonanywhere.com'
SENDER = 'GlosBadWebsite@gmail.com'
ADMIN_EMAIL = 'schofieldmark@gmail.com'
FIXTURES_EMAIL = 'GlosBadFixtures@outlook.com'
TESTING_ENV = True

class LeagueEmail:
    def __init__(self, fix, **kwargs):
        self.fix = fix
        self.kwargs = kwargs
        self.subject = ''
        self.body = ''
        self.html = ''
        self.recipients = []

    def get_recipients(self, team, non_fix=False):
        if TESTING_ENV:
            return ['schofieldmark@gmail.com',]
        fix = self.fix
        if non_fix:
            team_obj = self.kwargs.get('team')
            return self._filter_emails([
                team_obj.club.contact1_email,
                team_obj.club.contact2_email,
                team_obj.captain_email
            ])
        elif team == 'home':
            return self._filter_emails([
                fix.home_team.club.contact1_email,
                fix.home_team.club.contact2_email,
                fix.home_team.captain_email
            ])
        elif team == 'away':
            return self._filter_emails([
                fix.away_team.club.contact1_email,
                fix.away_team.club.contact2_email,
                fix.away_team.captain_email
            ])
        else:  # both
            return self._filter_emails([
                fix.home_team.club.contact1_email,
                fix.home_team.club.contact2_email,
                fix.home_team.captain_email,
                fix.away_team.club.contact1_email,
                fix.away_team.club.contact2_email,
                fix.away_team.captain_email
            ])
    
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
    def __init__(self, fix, **kwargs):
        super().__init__(fix, **kwargs)
        self.subject = f'{fix} - Result Submitted'
        self.recipients = self.get_recipients('away')
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
    def __init__(self, fix, **kwargs):
        super().__init__(fix, **kwargs)
        self.subject = f'{fix} - New Date Proposed'
        self.recipients = self.get_recipients('away')
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
    def __int__(self, fix, **kwargs):
        super().__init__(fix, **kwargs)
        self.subject = f'{fix} - Rearrangement Confirmed'
        self.recipients = self.get_recipients('home')
        self.body = (f'Hi,\n\nThe away team have confirmed the rearrangement of the match {fix} '
                     f'originally scheduled for {fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S")} '
                     f'and now scheduled for {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")} at '
                     f'{fix.venue}.')


class RejectedEmail(LeagueEmail):
    def __int__(self, fix, **kwargs):
        super().__init__(fix, **kwargs)
        self.subject = f'{fix} - Rearrangement Rejected'
        self.recipients = self.get_recipients('home')
        self.body = (f'Hi,\n\nThe away team have REJECTED the proposed rearrangement of the match '
                     f'{fix} originally scheduled for {fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S")} '
                     f'and proposed to be rearranged for {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")} '
                     f'at {fix.venue}.\n\nPlease contact the away team to discuss why the rearrangement '
                     f'was rejected and agree a new date/venue. Fixture status has been returned to '
                     f'"Postponed".')


class ConcessionEmail(LeagueEmail):
    def __init__(self, fix, side, **kwargs):
        super().__init__(fix, **kwargs)
        penalty_value = constants.PENALTY_MIXED_CONCEDED if fix.division.type == "Mixed" else constants.PENALTY_LEVEL_CONCEDED
        team = 'home' if side == 'home' else 'away'
        other_team = 'away' if side == 'home' else 'home'
        self.subject = f'{fix} - Match Conceded'
        self.recipients = self.get_recipients('both')
        self.body = (f'Hi,\n\nThe {team} team have conceded the match {fix} scheduled for '
                     f'{fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")}. '
                     f'The {team} team will be penalised {penalty_value}. '
                     f"The {other_team} team's points will not be updated to reflect the concession until "
                     f'the end of the season but the fixture status has been updated to record the concession.')


class PlayerNotFoundEmail(LeagueEmail):
    def __init__(self, fix, **kwargs):
        super().__init__(fix, **kwargs)
        self.subject = 'Player Not Confirmed'
        self.recipients = self.get_recipients('away')
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
    def __int__(self, fix, **kwargs):
        super().__init__(fix, **kwargs)
        self.subject = f'{fix} - Match Postponed'
        self.recipients = self.get_recipients('away')
        self.body = (f'Hi,\n\nThe home team have postponed the match {fix} originally scheduled '
                     f'for {fix.date_time.strftime("%d/%m/%Y, %H:%M:%S")}. Hopefully, they have '
                     f'been in touch to explain why and to initiate the process of finding a new '
                     f'date/venue.')


class NominationPenEmail(LeagueEmail):
    def __init__(self, fix, **kwargs):
        super().__init__(fix, **kwargs)
        self.subject = 'Nomination Penalty Applied'
        self.recipients = self.get_recipients(kwargs['team'], non_fix=True)
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
    def __init__(self, fix, **kwargs):
        super().__init__(fix, **kwargs)
        self.subject = 'Eligibility Penalty Applied'
        self.recipients = self.get_recipients(kwargs['team'], non_fix=True)
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


class NominationApprovedEmail(LeagueEmail):
    def __init__(self, fix, **kwargs):
        super().__init__(fix, **kwargs)
        self.subject = 'Nomination Change Approved'
        team = kwargs['nom'].team
        kwargs['team'] = team
        cur_player = kwargs['cur_nom'].player
        new_player = kwargs['nom'].player
        self.recipients = self.get_recipients('', kwargs, non_fix=True)
        self.body = (f"Hi,\n\nThe nomination change request to replace {cur_player} with "
                     f"{new_player} for {team} has been approved.")
        self.html = (f"Hi,<br><br>The nomination change request to replace {cur_player} with "
                     f"{new_player} for {team} has been approved.")


EMAIL_CLASSES = {
    'result': ResultEmail,
    'postponed': PostponedEmail,
    'reschedule': RescheduleEmail,
    'confirmed': RearrangedEmail,
    'rejected': RejectedEmail,
    'playernotfound': PlayerNotFoundEmail,
    'nomination_penalty': NominationPenEmail,
    'eligibility_penalty': EligibilityPenEmail,
    'nomination_approved': NominationApprovedEmail,
}


def email_notification(status, fix, **kwargs):
    if status in ('concededhome', 'concededaway'):
        side = 'home' if status == 'concededhome' else 'away'
        email = ConcessionEmail(fix, side=side, **kwargs)
    else:
        email_class = EMAIL_CLASSES[status]
        email = email_class(fix, **kwargs)
    email.send()


class AdminEmail:
    def __init__(self, all_admin=False, **kwargs):
        self.kwargs = kwargs
        self.subject = ''
        self.body = ''
        self.html = ''
        self.recipients = self.get_recipients(all_admin)

    def get_recipients(self, all_admin):
        if all_admin and not TESTING_ENV:
            return ['martin.godwin@btinternet.com','johnsexton1955@yahoo.co.uk','peter.sexton@bt.com','schofieldmark@gmail.com']
        else:
            return ['schofieldmark@gmail.com',]

    def _footer(self, html=False):
        if html:
            return '<br><br>***This is an automated email from the league website***'
        return '\n\n***This is an automated email from the league website***'

    def send(self):
        body = self.body + self._footer()
        if self.html:
            html = self.html + self._footer(html=True)
            send_mail(self.subject, body, SENDER, self.recipients, html_message=html)
        else:
            send_mail(self.subject, body, SENDER, self.recipients)


class NominationChangeEmail(AdminEmail):
    def __init__(self, all_admin, **kwargs):
        super().__init__(all_admin, **kwargs)
        nom = self.kwargs['nom_object']
        nom_url = f'{BASE_URL}/nominations/admin/{nom.id}'
        self.subject = 'Nomination Change Request'
        self.body = (f'Hi,\n\n{nom.team.club} has submitted a request to change a nomination for the team {nom.team}. '
                     f'Please go to the following page to view the players involved and their current playing stats:'
                     f'\n\n{nom_url}\n\nPlease approve/reject the request via that page, if rejecting it please contact '
                     f'the club directly to explain why.')
        self.html = (f'Hi,<br><br>{nom.team.club} has submitted a request to change a nomination for the team {nom.team}. '
                     f'Please <a href={nom_url}>click here</a> to view the players involved and their current '
                     f'playing stats. Please approve/reject the request via that page, if rejecting it please contact '
                     f'the club directly to explain why.')


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

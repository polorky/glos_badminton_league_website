from .models import Player
import league.constants as constants
from RapidFuzz import fuzz
from django.core.mail import send_mail

def find_away_players(data, fixture):
    '''
        Validation function for checking away player names
        Looks for existing players that match or closely match
        If none are found, return errors messages unless checkbox is ticked
    '''

    match_type = fixture.division.type
    club = fixture.away_team.club

    player_errors = []
    

    bypass_validation = data['player_name_check']

    players = ['away_player1','away_player2','away_player3','away_player4']
    if match_type == "Mixed":
        players += ['away_player5','away_player6']
    
    players_found = {player:{'player':None, 'suggest_only':False, 'name':data.get(player_title)} for player in players}

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

def attempt_fuzzy_match(player_name, club):

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

def email_notification(status, fix, sender='GlosBadWebsite@gmail.com', verifications=()):

    def get_recipients(fix, team):

        if team == 'home':
            recipients = [fix.home_team.club.contact1_email, fix.home_team.club.contact2_email, fix.home_team.captain_email]
        elif team == 'away':
            recipients = [fix.away_team.club.contact1_email, fix.away_team.club.contact2_email, fix.away_team.captain_email]
        else:
            recipients = [fix.home_team.club.contact1_email, fix.home_team.club.contact2_email, fix.home_team.captain_email]
            recipients += [fix.away_team.club.contact1_email, fix.away_team.club.contact2_email, fix.away_team.captain_email]
        for i in range(len(recipients),0,-1):
            if not recipients[i-1]:
                recipients.pop(i-1)

        return recipients

    html = ''

    if status == 'playernotfound':
        subject = 'Player Not Confirmed'
        body = f'Hi,\n\nNot all away players for the match {fix} could be identified.'
        if any([v.suggested_player for v in verifications]):
            body += 'The following player(s) where a close match to the name entered, if the correct player has been identified, \
                please click on "Correct Player" link, otherwise click on the "Incorrect Player"'
            html = body
            for v in verifications:
                if v.suggested_player:
                    body += f'\nEntered name: {v.submitted_name} --- Suggested Player: {v.suggested_player} --- \
                        Click this link if this is the correct player: https://gloubadleague.pythonanywhere.com/verify-player/{v.token}/correct --- \
                        Click this link if this is NOT the correct player: https://gloubadleague.pythonanywhere.com/verify-player/{v.token}/incorrect'
                    html += f'\nEntered name: {v.submitted_name} --- Suggested Player: {v.suggested_player} --- \
                        <a href="https://gloubadleague.pythonanywhere.com/verify-player/{v.token}/correct">This is the correct player</a> --- \
                        <a href="https://gloubadleague.pythonanywhere.com/verify-player/{v.token}/incorrect">This is NOT the correct player</a>' 
                else:
                    body += f'\nEntered name: {v.submitted_name} --- Click this link to find/create player: \
                        https://gloubadleague.pythonanywhere.com/verify-player/{v.token}/nosuggest'
                    html += f'\nEntered name: {v.submitted_name} --- \
                        <a href="https://gloubadleague.pythonanywhere.com/verify-player/{v.token}/nosuggest"> \
                        Click this link to find/create player</a>'    
        recipients = get_recipients(fix, 'away')
    elif status == 'confirmed':
        subject = str(fix) + ' - Rearrangement Confirmed'
        body = 'Hi,\n\nThe away team have confirmed the rearrangement of the match ' + str(fix) + ' originally scheduled for ' \
        + fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' and now scheduled for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + ' at ' + str(fix.venue) + '.\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'home')
    
    elif status == 'rejected':
        subject = str(fix) + ' - Rearrangement Rejected'
        body = 'Hi,\n\nThe away team have REJECTED the proposed rearrangement of the match ' + str(fix) + ' originally scheduled for ' \
        + fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' and proposed to be rearranged for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' at ' \
        + str(fix.venue) + '.\n\nPlease contact the away team to discuss why the rearrangement was rejected and agree a new date/venue. Fixture status has ' \
        + 'been returned to "Postponed".\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'home')
    
    elif status == 'postponed':
        subject = str(fix) + ' - Match Postponed'
        body = 'Hi,\n\nThe home team have postponed the match ' + str(fix) + ' originally scheduled for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + '. Hopefully, they have been in touch to explain why and to initiate the process of finding a new date/venue.\n\nRegards\n\nLeague Committee\n\n' \
        + '***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'away')
    
    elif status == 'reschedule':
        subject = str(fix) + ' - New Date Proposed'
        body = 'Hi,\n\nThe home team have proposed a new date/venue for the match ' + str(fix) + ' originally scheduled for ' \
        + fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S") + '. The proposed new date is ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' at ' + str(fix.venue) \
        + '.\n\nPlease confirm or reject this rearrangement via this page: https://gloubadleague.pythonanywhere.com/fixtures/' \
        + str(fix.id) + '/update/div\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        html = 'Hi,<br><br>The home team have proposed a new date/venue for the match ' + str(fix) + ' originally scheduled for ' \
        + fix.old_date_time.strftime("%d/%m/%Y, %H:%M:%S") + '. The proposed new date is ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") + ' at ' + str(fix.venue) \
        + '.<br><br>Please confirm or reject this rearrangement by clicking ' + '<a href="https://gloubadleague.pythonanywhere.com/fixtures/' \
        + str(fix.id) + '/update/div">here</a>.<br><br>Regards<br><br>League Committee<br><br>***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'away')
    
    elif status == 'concededhome':
        if fix.division.type == "Mixed":
            penalty_value = constants.PENALTY_MIXED_CONCEDED
        else:
            penalty_value = constants.PENALTY_LEVEL_CONCEDED
        subject = str(fix) + ' - Match Conceded'
        body = 'Hi,\n\nThe home team have conceded the match ' + str(fix) + ' scheduled for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + 'The home team will be penalised ' + str(penalty_value) + ". The away team's points will not be updated to reflect the concession until the end of the season " \
        + 'but the fixture status has been updated to record the concession\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'both')
    
    elif status == 'concededaway':
        if fix.division.type == "Mixed":
            penalty_value = constants.PENALTY_MIXED_CONCEDED
        else:
            penalty_value = constants.PENALTY_LEVEL_CONCEDED
        subject = str(fix) + ' - Match Conceded'
        body = 'Hi,\n\nThe away team have conceded the match ' + str(fix) + ' scheduled for ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + 'The away team will be penalised ' + str(penalty_value) + ". The home team's points will not be updated to reflect the concession until the end of the season " \
        + 'but the fixture status has been updated to record the concession\n\nRegards\n\nLeague Committee\n\n***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'both')
    
    elif status == 'result':
        subject = str(fix) + ' - Result Submitted'
        body = 'Hi,\n\nThe home team have submitted the results for the match ' + str(fix) + ' played on ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + '. You can view the score submitted on this page: https://gloubadleague.pythonanywhere.com/fixtures/' + str(fix.id) \
        + '\n\nIf you believe the result has been entered incorrectly, please contact the league by replying to this email.\n\nRegards\n\nLeague Committee \
        \n\n***This is an automated email from the league website***'
        html = 'Hi,<br><br>The home team have submitted the results for the match ' + str(fix) + ' played on ' + fix.date_time.strftime("%d/%m/%Y, %H:%M:%S") \
        + '. You can view the score submitted <a href="https://gloubadleague.pythonanywhere.com/fixtures/' + str(fix.id) \
        + '/div">here</a>.<br><br>If you believe the result has been entered incorrectly, please contact the league by replying to this email.<br><br>Regards<br><br>' \
        + 'League Committee<br><br>***This is an automated email from the league website***'
        recipients = get_recipients(fix, 'away')

    body += '\n\nFor any issues surrounding fixtures, please contact GlosBadFixtures@outlook.com\nFor technical issues with the website, please reply to this email'
    #recipients = ['schofieldmark@gmail.com']

    if html:

        html += '<br><br>For any issues surrounding fixtures, please contact <a href="mailto:GlosBadFixtures@outlook.com">GlosBadFixtures@outlook.com</a>' \
        + '<br>For technical issues with the website, please reply to this email'
        #html = html.replace('\n','<br>')

        send_mail(subject, body, sender, recipients, html_message = html)

    else:

        send_mail(subject, body, sender, recipients)

    return

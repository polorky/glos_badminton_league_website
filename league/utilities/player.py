import league.constants as constants
from django.core import signing
from .email import email_notification
from league.models import Team, PendingPlayerVerification, Penalty

# PLAYER VERIFICATION VIEW
def _get_user_club(user):
    """Return the Club for a logged-in Administrator or Member, or None."""
    from league.models import Administrator, Member
    if not user.is_authenticated:
        return None
    try:
        return user.administrator.club
    except Exception:
        pass
    try:
        return user.member.club
    except Exception:
        return None


def _load_verification(verification_id):
    return PendingPlayerVerification.objects.select_related(
        'fixture__away_team__club', 'fixture__home_team__club',
        'fixture__division', 'suggested_player'
    ).get(id=verification_id)


def _resolve(verification, player):
    verification.resolved_player = player
    verification.resolved = True
    verification.save()
    setattr(verification.fixture, verification.player_field, player)
    verification.fixture.save()


def _handle_post(request, verification, post_url):
    from django.shortcuts import render
    from league.models import Player

    club = verification.fixture.away_team.club
    choice = request.POST.get('choice', '')
    player_name = request.POST.get('player_name', '').strip()
    error = None

    if choice == 'new':
        if not player_name:
            error = 'Please enter a name for the new player.'
        else:
            player = Player.objects.create(club=club, name=player_name, level=verification.level)
    elif choice.startswith('existing_'):
        try:
            player = Player.objects.get(id=choice[9:], club=club)
        except (Player.DoesNotExist, ValueError):
            error = 'Invalid player selected.'
    else:
        error = 'Please select a player or choose to create a new one.'

    if not error:
        _resolve(verification, player)
        return render(request, 'league/verify_player.html', {
            'view': 'confirmed',
            'player': player,
            'fixture': verification.fixture,
        })

    roster = Player.objects.filter(club=club, level=verification.level).order_by('name')
    return render(request, 'league/verify_player.html', {
        'view': 'select',
        'verification': verification,
        'post_url': post_url,
        'roster': roster,
        'error': error,
    })


def VerifyPlayerView(request, token, action=''):
    from django.shortcuts import render
    from league.models import Player

    post_url = f'/verify-player/{token}/'

    try:
        data = signing.loads(token, max_age=86400 * 7)
        verification = _load_verification(data['verification_id'])
    except signing.SignatureExpired:
        # Decode without age check to extract the verification ID for the auth fallback
        try:
            data = signing.loads(token)
            v_id = data['verification_id']
        except signing.BadSignature:
            return render(request, 'league/verify_player.html', {'view': 'invalid'})

        auth_url = f'/verify-player/auth/{v_id}/'
        user_club = _get_user_club(request.user)
        if user_club:
            # Already logged in — go straight to form if the club is correct
            try:
                verification = _load_verification(v_id)
            except PendingPlayerVerification.DoesNotExist:
                return render(request, 'league/verify_player.html', {'view': 'already_resolved'})
            if not verification.resolved and user_club == verification.fixture.away_team.club:
                if request.method == 'POST':
                    return _handle_post(request, verification, auth_url)
                roster = Player.objects.filter(
                    club=user_club, level=verification.level
                ).order_by('name')
                return render(request, 'league/verify_player.html', {
                    'view': 'select',
                    'verification': verification,
                    'post_url': auth_url,
                    'roster': roster,
                })
            if verification.resolved:
                return render(request, 'league/verify_player.html', {
                    'view': 'already_resolved',
                    'player': verification.resolved_player,
                })

        return render(request, 'league/verify_player.html', {
            'view': 'expired',
            'login_url': f'/login/?next={auth_url}',
        })
    except (signing.BadSignature, PendingPlayerVerification.DoesNotExist):
        return render(request, 'league/verify_player.html', {'view': 'invalid'})

    if verification.resolved:
        return render(request, 'league/verify_player.html', {
            'view': 'already_resolved',
            'player': verification.resolved_player,
        })

    club = verification.fixture.away_team.club

    if request.method == 'POST':
        return _handle_post(request, verification, post_url)

    # GET — handle actions from email link
    if action == 'correct' and verification.suggested_player:
        _resolve(verification, verification.suggested_player)
        return render(request, 'league/verify_player.html', {
            'view': 'confirmed',
            'player': verification.suggested_player,
            'fixture': verification.fixture,
        })

    roster = Player.objects.filter(club=club, level=verification.level).order_by('name')
    return render(request, 'league/verify_player.html', {
        'view': 'select',
        'verification': verification,
        'post_url': post_url,
        'roster': roster,
        'wrong_suggestion': verification.suggested_player if action == 'incorrect' else None,
    })


def AuthVerifyPlayerView(request, pk):
    from django.shortcuts import render, redirect
    from league.models import Player

    if not request.user.is_authenticated:
        return redirect(f'/login/?next=/verify-player/auth/{pk}/')

    user_club = _get_user_club(request.user)
    if not user_club:
        return render(request, 'league/verify_player.html', {'view': 'invalid'})

    try:
        verification = _load_verification(pk)
    except PendingPlayerVerification.DoesNotExist:
        return render(request, 'league/verify_player.html', {'view': 'invalid'})

    if verification.resolved:
        return render(request, 'league/verify_player.html', {
            'view': 'already_resolved',
            'player': verification.resolved_player,
        })

    if user_club != verification.fixture.away_team.club:
        return render(request, 'league/verify_player.html', {'view': 'invalid'})

    post_url = f'/verify-player/auth/{pk}/'

    if request.method == 'POST':
        return _handle_post(request, verification, post_url)

    roster = Player.objects.filter(club=user_club, level=verification.level).order_by('name')
    return render(request, 'league/verify_player.html', {
        'view': 'select',
        'verification': verification,
        'post_url': post_url,
        'roster': roster,
    })


# Functions for validating players in results submission
def verify_away_players(fixture, players_found):
    '''
        Takes list of away players from results form and does the following:
            1. If player found, add to fixture object
            2. Else send email to away club to get confirmation of correct player
        Used when results are submitted
    '''
    
    div_type = fixture.division.type
    mixed_player_type = ['Womens','Womens','Womens','Open','Open','Open']
    verifications = []

    for player_title, player_dict in players_found.items():
        if not player_dict['name']:
            continue
        elif player_dict['player'] and not player_dict['suggest_only']:
            setattr(fixture, player_title, player_dict['player'])
            fixture.save()
        else:
            level = div_type if div_type != 'Mixed' else mixed_player_type[int(player_title[-1])]
            verification = PendingPlayerVerification.objects.create(
                fixture=fixture,
                player_field=player_title,
                submitted_name=player_dict['name'],
                level=level,
                token=''
            )
            verification.token = signing.dumps({'verification_id': verification.id})
            verification.save()
            if player_dict['player']:
                verification.suggested_player = player_dict['player']
                verification.save()
            verifications.append(verification)
    
    if verifications:
        email_notification('playernotfound', fixture=fixture, verifications=verifications)

def check_player_eligibility(fixture):
    '''
        Checks whether players are uneligible for these teams due to playing for higher teams
        Applies penalty points for any uneligible players played
        Used when results are submitted
    '''

    for player in fixture.get_players('home'):
        if not player.check_eligibility(fixture.home_team):
            email_notification('eligibility_penalty', fixture=fixture, team=fixture.home_team, player_name=player.name)
            Penalty.objects.create(season=fixture.season, 
                                   team=fixture.home_team, 
                                   penalty_value=constants.PENALTY_INELIGIBLE_PLAYER, 
                                   penalty_type='Ineligible Player', 
                                   player=player.name, 
                                   fixture=fixture)

    for player in fixture.get_players('away'):
        if not player.check_eligibility(fixture.away_team):
            email_notification('eligibility_penalty', fixture=fixture, team=fixture.away_team, player_name=player.name)
            Penalty.objects.create(season=fixture.season, 
                                   team=fixture.away_team,
                                   penalty_value=constants.PENALTY_INELIGIBLE_PLAYER, 
                                   penalty_type='Ineligible Player', 
                                   player=player.name, 
                                   fixture=fixture)

# Club Admin related functions
def correct_duplicate_player(dup_player, cor_player, fix):
    '''
        Updates a fixture to replace a duplicate player with the correct player
    '''

    player_fields = [f'home_player{i}' for i in range(1, 7)] + [f'away_player{i}' for i in range(1, 7)]

    for player in player_fields:
        if getattr(fix, player) == dup_player:
            setattr(fix, player, cor_player)
            fix.save()
            return 'done'

    return 'notfound'

def get_player_appearances(player):
    '''Pulls stats for player - times played for each team and teams nominated for
        Used in the league admin view to provide a summary for player'''

    player_fixtures = player.get_own_fixtures()
    team_dict = {}
    team_dict["teams"] = player.club.get_clubs_teams("count")

    team_dict = _count_appearances(player_fixtures, team_dict, player)
    team_dict = _add_eligibility(team_dict, player)
    
    noms = player.get_noms_strings()
    team_dict["noms"] = {"mixed":noms[0],"level":noms[1]}
    
    return team_dict

def _count_appearances(fixtures, team_dict, player):
    '''Count the times player has played for each team'''
    for fixture in fixtures:
        if player in fixture.get_players(side='home'):
            num = fixture.home_team.number
            type = fixture.home_team.type
        else:
            num = fixture.away_team.number
            type = fixture.away_team.type

        team_dict["teams"][type][num] += 1
    
    return team_dict

def _add_eligibility(team_dict, player):
    '''Add player's eligibility status to each team'''
    for team_type in team_dict["teams"].keys():
        for team_num in team_dict["teams"][team_type].keys():
            team = Team.objects.get(club=player.club,number=team_num,type=team_type)
            if not player.check_eligibility(team):
                count = team_dict["teams"][team_type][team_num]
                if count == 0:
                    team_dict["teams"][team_type][team_num] = "X"
                else:
                    team_dict["teams"][team_type][team_num] = "X (" + str(count) + ")"
    
    return team_dict

# Functions for player stats page
def get_player_stats(club, fixtures):
    '''Stats for the player stats page'''
    
    player_dict = {}

    for fixture in fixtures:

        if fixture.status != 'Played':
            continue

        game_split = fixture.game_results.split(',')

        home_players = fixture.get_players(side='home')
        away_players = fixture.get_players(side='away')
        club_home = False
        club_away = False

        if fixture.home_team.club == club:
            for player in home_players:
                if player.id not in player_dict:
                    player_dict[player.id] = {'obj':player,'mixed':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0},'level':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0}}
            club_home = True
        if fixture.away_team.club == club:
            for player in away_players:
                if player.id not in player_dict:
                    player_dict[player.id] = {'obj':player,'mixed':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0},'level':{'played':0,'won':0,'percent':0,'pf':0,'pa':0,'diff':0}}
            club_away = True

        if fixture.division.type == "Mixed":
            #mixed_games = ["Mixed 2v1","Mixed 3v2","Mixed 1v3","Mixed 3v1","Mixed 1v2","Mixed 2v3","Mixed 1v1","Mixed 2v2","Mixed 3v3"]
            mixed_games = [[[3,6],[2,5]],[[2,5],[3,6]],[[1,4],[1,4]],[[2,5],[2,5]],[[3,6],[3,6]],[[4,5],[4,5]],[[1,2],[1,2]],[[4,6],[4,6]],[[1,3],[1,3]]]
            batched_games = [game_split[i:i + 6] for i in range(0, len(game_split), 6)]
        else:
            #level_games = ["2+3 v 2+3","1+4 v 1+4","2+4 v 2+4","1+3 v 1+3","3+4 v 3+4","1+2 v 1+2"]
            level_games = [[2,3],[1,4],[2,4],[1,3],[3,4],[1,2]]
            batched_games = [game_split[i:i + 4] for i in range(0, len(game_split), 4)]

        for x, game in enumerate(batched_games):

            rubbers = [game[i:i+2] for i in range(0, len(game), 2)]
            for rubber in rubbers:
                try:

                    if rubber[0] in ['FH','FA',''] or rubber[1] in ['FH','FA','']:
                        continue

                    if club_home:

                        if fixture.division.type == "Mixed":
                            players_involved = [home_players[mixed_games[x][0][0] - 1], home_players[mixed_games[x][0][1] - 1]]
                            match_type = "mixed"
                        else:
                            players_involved = [home_players[level_games[x][0] - 1], home_players[level_games[x][1] - 1]]
                            match_type = "level"

                        for player in players_involved:
                            player_dict[player.id][match_type]['played'] += 1
                            player_dict[player.id][match_type]['pf'] += int(rubber[0])
                            player_dict[player.id][match_type]['pa'] += int(rubber[1])
                            player_dict[player.id][match_type]['diff'] = player_dict[player.id][match_type]['pf'] - player_dict[player.id][match_type]['pa']
                            if int(rubber[0]) > int(rubber[1]):
                                player_dict[player.id][match_type]['won'] += 1
                            player_dict[player.id][match_type]['percent'] = round(player_dict[player.id][match_type]['won'] / player_dict[player.id][match_type]['played'] * 100, 1)

                    if club_away:

                        if fixture.division.type == "Mixed":
                            players_involved = [away_players[mixed_games[x][1][0] - 1], away_players[mixed_games[x][1][1] - 1]]
                            match_type = "mixed"
                        else:
                            players_involved = [away_players[level_games[x][0] - 1], away_players[level_games[x][1] - 1]]
                            match_type = "level"

                        for player in players_involved:
                            player_dict[player.id][match_type]['played'] += 1
                            player_dict[player.id][match_type]['pf'] += int(rubber[1])
                            player_dict[player.id][match_type]['pa'] += int(rubber[0])
                            player_dict[player.id][match_type]['diff'] = player_dict[player.id][match_type]['pf'] - player_dict[player.id][match_type]['pa']
                            if int(rubber[0]) < int(rubber[1]):
                                player_dict[player.id][match_type]['won'] += 1
                            player_dict[player.id][match_type]['percent'] = round(player_dict[player.id][match_type]['won'] / player_dict[player.id][match_type]['played'] * 100, 1)

                except Exception as e:
                    raise Exception(f'Error - {x}, {game}, {rubber}, {level_games}, {level_games[x]}, {level_games[x][1]}, {home_players}, {away_players}, {e}')

    return player_dict

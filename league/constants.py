# League defined parameters

# Scoring formats
SCORING_MIXED = 'point per game' # Current scoring format for mixed league (used as default for new seasons)
SCORING_LEVEL = 'point per rubber' # Current scoring format for level league
# Note level scoring is hard coded for seasons as it has not historically been changed
SCORING_OPTIONS = (('point per game','point per game'),('point per rubber','point per rubber')) # Used only to note mixed scoring format for seasons as it has changed
TOTAL_POINTS_MIXED = 18
TOTAL_POINTS_LEVEL = 12

# Game names for display
GAME_NAMES_MIXED = ['Mixed 3v2','Mixed 2v3','Mixed 1v1','Mixed 2v2','Mens 1&2','Ladies 1&2','Mens 1&3','Ladies 1&3']
GAME_NAMES_LEVEL = ['2+3 v 2+3', '1+4 v 1+4', '2+4 v 2+4', '1+3 v 1+3', '3+4 v 3+4', '1+2 v 1+2']

# Penalties
PENALTY_MIXED_CONCEDED = 10
PENALTY_LEVEL_CONCEDED = 7
PENALTY_INELIGIBLE_PLAYER = 5
PENALTY_NOMINATION_VIOLATION = 5
PENALTY_LATE_SUBMISSION = 5

# Other playing rules
MAX_PLAYS_FOR_HIGHER_TEAMS = 3

# Player related constants
PLAYER_NAME_FUZZY_MATCH_RATIO = 85
PLAYER_NAME_FUZZY_SUGGEST_RATIO = 60
ALTERNATE_NAMES = (('David','Dave'),('Stuart','Stu'),('Richard','Rich'),('Alexander','Alex'),('Christopher','Chris'),('Andrew','Andy'),('Daniel','Dan'),('Matthew','Matt'),
('Michael','Mike'),('Oliver','Oli'),('Oliver','Ollie'),('Phillip','Phil'),('Philip','Phil'),('Robert','Rob'),('Simon','Si'),('Thomas','Tom'),('William','Will'),
('Rebecca','Becky'))

##### Change of season checklist #####
# Code up any changes in league rules
# Create new season and untick 'active' flag on previous season
# Download full results for previous season
# Get perfomances for teams (on league admin Club Admin page)
# Create new clubs/teams
# Update teams with new divisions and 'active' flag
# Upload fixtures
# Open nominations
# Close nominations and apply any penalties
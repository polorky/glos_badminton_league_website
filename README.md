# Gloucestershire Badminton League
Welcome to the code for the website of Gloucestershire Badminton League!

## Models
The following are the basic self-explanatory models used in the website:

* Season
    * year (str) - format YYYY-YYYY
    * current (bool) - whether the active season
    * archive_info (str) - notes on historic seasons
    * historic_divs (bool) - some historic seasons had multiple divisions on the same level which doesn't fit with the standard numbering, so this attribute is used to take account of that structure
    * mixed_scoring (str) - mixed scoring changed from best of three to two rubbers and a point for each. This attribute ensures scorecards are formatted correctly
* Division
    * number (int)
    * type (str) - mixed/women's/men's
    * historic (str) - for historic divisions that had multiple divisions on the same level, this field contains the name of that division which involved a letter so does not work with the standard int "number" attribute
    * active (bool)
* Club
    * name (str)
    * short_name (str)
    * active (bool)
    * [contact information fields] - used for public and league communications
    * [notification settings] - used for notifications from the website of upcoming fixtures
* Player
    * name (str)
    * level (str) - women's/men's
    * club (Club)
* Team
    * division (Division)
    * club (Club)
    * type (str) - mixed/women's/men's
    * number (int)
    * active (bool)
    * [captain name and contact information]
* Venue
    * name (str)
    * address (str)
    * additional_information (str)
    * map (str) - Google Maps reference
* Fixture
    * home_team (Team)
    * away_team (Team)
    * date_time (DateTime)
    * end_time (Time)
    * season (Season)
    * home_points (int)
    * away_points (int)
    * venue (Venue)
    * division (Division)
    * status (str) - unplayed/postponed/proposed/rearranged/played/conceded (H or A)
    * old_date_time (DateTime) - original date if match has been rearranged
    * game_results (str) - comma separated scores for each game/rubber
    * [home_players/away_players] - players that played in the match
    
The following models are less intuitive but used for administration purposes:

* LeagueSettings - used for league wide attributes that change across the season
    * nomination_window_open
* Administrator - club-based website user that has full access to club functions
    * user (User)
    * club (Club)
* Member - club-based website user that has partial access to club functions
    * user (User)
    * club (Club)
* TeamNomination - used to record team nominations - both approved and proposed
    * team (Team)
    * player (Player)
    * position
    * date_from
    * date_to - if player has been replaced
    * approved - approved by league admin
    * notes - reasons for any change
* ClubNight - used by clubs to record when their club night session are held
    * club (Club)
    * venue (Venue)
    * timings (str) - free-text field to give days and times
* Penalty - used to record penalties incurred by teams
    * season (Season)
    * team (Team)
    * penalty_type (str)
    * penalty_value (int)
    * player (str) - if penalty involves a player e.g. nomination violation
    * fixture = if penalty involves a fixture e.g. conceded match
* Performance - used to record where a team finished each season so a full table doesn't have to be reconstructed each time
    * team (Team)
    * season (Season)
    * division (Division)
    * position (str) - where the team finished
* PendingPlayerVerification - used when the away player name inputted by the home team isn't found in the away team roster and the away club haven't confirmed whether it is a new player or a misspelt existing one
    * fixture (Fixture)
    * submitted_name (str)
    * level (str) - mixed/women's/men's
    * suggested_player - Player
    * token (str)
    * created_at (DateTime)
    * resolved (bool)
    * resolved_player (Player)
from league.models import Season

def get_adj_seasons(target_season):
    '''Returns the previous and next seasons or None if not applicable'''
    
    seasons = sorted(Season.objects.all(), key=lambda x: int(x.year[:4]), reverse=True)
    idx = next(i for i, s in enumerate(seasons) if s.year == target_season.year)
    
    prev_season = seasons[idx + 1] if idx < len(seasons) - 1 else None
    next_season = seasons[idx - 1] if idx > 0 else None
    
    return prev_season, next_season
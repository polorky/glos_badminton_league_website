from .models import Season

def current_season(request):
    try:
        season = Season.objects.get(current=True)
    except Season.DoesNotExist:
        season = None
    return {'season_menu': season}
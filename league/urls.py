from django.urls import path
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    #path('nominations/<str:pagename>', views.nominations, name='nominations'),

    
    path('clubadmin/<str:update>', views.clubadmin, name='clubadmin'),
    path('clubadmin', views.clubadmin, name='clubadmin'),

    path("divisions/<str:pagename>/<str:season>", views.DivisionsView.as_view(), name='divisions'),
    path("divisions/<str:pagename>", views.DivisionsView.as_view(), name='divisions'),
    path('fixtures/update/<str:fixid>/<str:pagename>/<str:source>', views.FixUpdateView.as_view(), name='fixture_update'),
    #path('fixtures/<str:pagename>/<status>/<source>', views.fixupdate, name='fixupdate'),
    path('fixtures/<str:pagename>/<str:source>', views.FixturesView.as_view(), name='fixtures'),
    path('fixtures/<str:pagename>', views.FixturesView.as_view(), name='fixtures'),
    path('clubs/<str:pagename>', views.ClubsView.as_view(), name='clubs'),
    path('teams/<str:pagename>', views.TeamsView.as_view(), name='teams'),
    path('venues/<str:pagename>', views.VenuesView.as_view(), name='venues'),
    path('playerstats/<str:pagename>', views.PlayerStatsView.as_view(), name='playerstats'),
    path('archive/<str:pagename>', views.ArchivesView.as_view(), name='archive'),

    path('juniors', TemplateView.as_view(template_name="league/juniors.html"), name='juniors'),
    path('help', TemplateView.as_view(template_name="league/help.html"), name='help'),
    path('', TemplateView.as_view(template_name="league/home.html"), name='home'),
]

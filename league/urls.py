from django.urls import path
from . import views

urlpatterns = [
    #path('nominations/<str:pagename>', views.nominations, name='nominations'),


    path('clubadmin/<str:update>', views.clubadmin, name='clubadmin'),

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

    path('clubadmin/', views.clubadmin, name='clubadmin'),
    path('admin/league/', views.LeagueAdminView.as_view(), name='league_admin'),
    path('admin/website/', views.WebsiteAdminView.as_view(), name='website_admin'),
    path('admin/club/', views.ClubAdminView.as_view(), name='club_admin'),

    path('juniors', views.JuniorsView.as_view(), name='juniors'),
    path('help', views.HelpView.as_view(), name='help'),
    path('', views.HomeView.as_view(), name='home'),

    path('stats', views.StatsView.as_view(), name='stats'),
]

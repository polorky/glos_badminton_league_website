from django.urls import path
from . import views
from league.utilities.player import verify_player

urlpatterns = [
<<<<<<< HEAD
=======
    #path('nominations/<str:pagename>', views.nominations, name='nominations'),


    path('clubadmin/<str:update>', views.clubadmin, name='clubadmin'),

>>>>>>> e4f0df6de8da34f9cbb8b6e2dad315165dff4045
    path("divisions/<str:pagename>/<str:season>", views.DivisionsView.as_view(), name='divisions'),
    path("divisions/<str:pagename>", views.DivisionsView.as_view(), name='divisions'),
    path('clubs/<str:pagename>', views.ClubsView.as_view(), name='clubs'),
    path('teams/<str:pagename>', views.TeamsView.as_view(), name='teams'),
    path('venues/<str:pagename>', views.VenuesView.as_view(), name='venues'),
    path('playerstats/<str:pagename>', views.PlayerStatsView.as_view(), name='playerstats'),
    path('player/<str:playerid>/<str:from>', views.PlayerView.as_view(), name='player'),
    path('archive/<str:pagename>', views.ArchivesView.as_view(), name='archive'),
<<<<<<< HEAD
=======

    path('clubadmin/', views.clubadmin, name='clubadmin'),
    path('admin/league/', views.LeagueAdminView.as_view(), name='league_admin'),
    path('admin/website/', views.WebsiteAdminView.as_view(), name='website_admin'),
    path('admin/club/', views.ClubAdminView.as_view(), name='club_admin'),

>>>>>>> e4f0df6de8da34f9cbb8b6e2dad315165dff4045
    path('juniors', views.JuniorsView.as_view(), name='juniors'),
    path('help', views.HelpView.as_view(), name='help'),
    path('stats', views.StatsView.as_view(), name='stats'),
    
    path('fixtures/update/<str:fixid>/<str:pagename>/<str:source>', views.FixUpdateView.as_view(), name='fixture_update'),
    path('fixtures/<str:pagename>/<str:source>', views.FixturesView.as_view(), name='fixtures'),
    path('fixtures/<str:pagename>', views.FixturesView.as_view(), name='fixtures'),

    path('clubadmin/', views.clubadmin, name='clubadmin'),
    path('clubadmin/league/', views.LeagueAdminView.as_view(), name='league_admin'),
    path('clubadmin/website/', views.WebsiteAdminView.as_view(), name='website_admin'),
    path('clubadmin/club/', views.ClubAdminView.as_view(), name='club_admin'),
    path('clubadmin/club/<str:update>', views.ClubAdminView.as_view(), name='club_admin'),
    path('nominations/<str:pagename>', views.NominationsView.as_view(), name='nominations'),
    path('nominations/<str:pagename>/<str:type>', views.NominationsView.as_view(), name='nom_change'),
    path('verify-player/<str:token>/<str:action>/', verify_player, name='verify_player'), # note this view is in the player.py file

    path('', views.HomeView.as_view(), name='home'),

    path('stats', views.StatsView.as_view(), name='stats'),
]

from django.contrib import admin
from . import models

def admin_username(obj):
    return obj.user.username

def admin_last_login(obj):
    return obj.user.last_login

class AdministratorAdmin(admin.ModelAdmin):
    list_display = ('club',admin_username,admin_last_login)

class MemberAdmin(admin.ModelAdmin):
    list_display = ('club',admin_username,admin_last_login)

class ClubAdmin(admin.ModelAdmin):
    list_display = ('name','short_name','active','website','club_notifications','captain_notifications')

class PlayerAdmin(admin.ModelAdmin):
    list_display = ('id','name','club','level')
    list_filter = ['club']

class SeasonAdmin(admin.ModelAdmin):
    list_display = ('year','current','historic_divs','archive_info')

class FixtureAdmin(admin.ModelAdmin):
    list_display = ('id','season','division','home_points','away_points','home_team','away_team','date_time','old_date_time','venue','status')
    list_filter = ['season','status','division','home_team','away_team']
    list_editable = ['status']

class TeamAdmin(admin.ModelAdmin):
    list_display = ('club','type','number','active','division','penalties','captain')
    list_filter = ['active','club','type','number']

class DivisionAdmin(admin.ModelAdmin):
    list_display = ('number','historic','type','active')

class VenueAdmin(admin.ModelAdmin):
    list_display = ('name','address','additional_information','map')

class PenaltyAdmin(admin.ModelAdmin):
    list_display = ('season','team','penalty_type','player','fixture')
    raw_id_fields = ('fixture',)

class ClubNightAdmin(admin.ModelAdmin):
    list_display = ('club','venue','timings')

class PerformanceAdmin(admin.ModelAdmin):
    list_display = ('team','season','division','position')

class NominationAdmin(admin.ModelAdmin):
    list_display = ('team', 'player', 'position', 'date_to', 'approved')
    list_filter = ['team__club']

class SettingsAdmin(admin.ModelAdmin):
    list_display = ('nomination_window_open',)

admin.site.register(models.Administrator, AdministratorAdmin)
admin.site.register(models.Member, MemberAdmin)
admin.site.register(models.Club, ClubAdmin)
admin.site.register(models.Team, TeamAdmin)
admin.site.register(models.Venue, VenueAdmin)
admin.site.register(models.Fixture, FixtureAdmin)
admin.site.register(models.Division, DivisionAdmin)
admin.site.register(models.Season, SeasonAdmin)
admin.site.register(models.Player, PlayerAdmin)
admin.site.register(models.Penalty, PenaltyAdmin)
admin.site.register(models.ClubNight, ClubNightAdmin)
admin.site.register(models.Performance, PerformanceAdmin)
admin.site.register(models.TeamNomination, NominationAdmin)
admin.site.register(models.LeagueSettings, SettingsAdmin)
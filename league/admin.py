from django.contrib import admin
from .models import Administrator, Member, Club, Team, Venue, Fixture, Division, Season, Player, Penalty, ClubNight, Performance

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
    list_display = ('name','club','level')
    list_filter = ['club']

class SeasonAdmin(admin.ModelAdmin):
    list_display = ('year','current','historic_divs')

class FixtureAdmin(admin.ModelAdmin):
    list_display = ('id','season','division','home_points','away_points','home_team','away_team','date_time','venue','status')
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

class ClubNightAdmin(admin.ModelAdmin):
    list_display = ('club','venue','timings')

class PerformanceAdmin(admin.ModelAdmin):
    list_display = ('team','season','division','position')

admin.site.register(Administrator, AdministratorAdmin)
admin.site.register(Member, MemberAdmin)
admin.site.register(Club, ClubAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(Venue, VenueAdmin)
admin.site.register(Fixture, FixtureAdmin)
admin.site.register(Division, DivisionAdmin)
admin.site.register(Season, SeasonAdmin)
admin.site.register(Player, PlayerAdmin)
admin.site.register(Penalty, PenaltyAdmin)
admin.site.register(ClubNight, ClubNightAdmin)
admin.site.register(Performance, PerformanceAdmin)
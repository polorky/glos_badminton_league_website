from rest_framework import serializers
from league.models import Club, Division, Team, Fixture, Venue


class ClubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = [
            'id', 'name', 'short_name',
            'public_contact_name', 'public_email', 'public_num',
            'website', 'blurb', 'active',
        ]


class DivisionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Division
        fields = ['id', 'number', 'type', 'type_display', 'active']


class TeamSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source='club.name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    division_display = serializers.SerializerMethodField()

    def get_division_display(self, obj):
        return str(obj.division) if obj.division else None

    class Meta:
        model = Team
        fields = [
            'id', 'club', 'club_name', 'type', 'type_display',
            'number', 'division', 'division_display', 'active',
        ]


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ['id', 'name', 'address', 'additional_information']


class FixtureSerializer(serializers.ModelSerializer):
    home_team_name = serializers.CharField(source='home_team.__str__', read_only=True)
    away_team_name = serializers.CharField(source='away_team.__str__', read_only=True)
    division_display = serializers.CharField(source='division.__str__', read_only=True)
    venue_name = serializers.SerializerMethodField()

    def get_venue_name(self, obj):
        return obj.venue.name if obj.venue else None

    class Meta:
        model = Fixture
        fields = [
            'id',
            'home_team', 'home_team_name',
            'away_team', 'away_team_name',
            'date_time', 'end_time',
            'season',
            'home_points', 'away_points',
            'venue', 'venue_name',
            'division', 'division_display',
            'status', 'game_results',
        ]

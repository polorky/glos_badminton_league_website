from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.shortcuts import get_object_or_404

from league.models import Club, Division, Team, Fixture, Season
from league.utilities.table import build_table
from .serializers import (
    ClubSerializer, DivisionSerializer, TeamSerializer,
    FixtureSerializer, VenueSerializer,
)


class ClubViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClubSerializer
    queryset = Club.objects.filter(active=True).order_by('name')


class DivisionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DivisionSerializer
    queryset = Division.objects.order_by('type', 'number')

    @action(detail=True, methods=['get'])
    def table(self, request, pk=None):
        division = self.get_object()
        season_year = request.query_params.get('season')
        if season_year:
            season = get_object_or_404(Season, year=season_year)
        else:
            season = Season.objects.get(current=True)

        standings = build_table(division, season)
        return Response({
            'season': season.year,
            'division': str(division),
            'table': [
                {
                    'team': name,
                    'played': stats['Played'],
                    'won': stats['Won'],
                    'drawn': stats['Drawn'],
                    'lost': stats['Lost'],
                    'points_for': stats['PFor'],
                    'points_against': stats['PAgainst'],
                    'penalties': stats['Penalties'],
                }
                for name, stats in standings
            ],
        })


class TeamViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TeamSerializer

    def get_queryset(self):
        qs = (Team.objects
              .filter(active=True)
              .select_related('club', 'division')
              .order_by('club__name', 'type', 'number'))
        club = self.request.query_params.get('club')
        division = self.request.query_params.get('division')
        if club:
            qs = qs.filter(club=club)
        if division:
            qs = qs.filter(division=division)
        return qs


class FixtureViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FixtureSerializer

    def get_queryset(self):
        season_year = self.request.query_params.get('season')
        if season_year:
            season = get_object_or_404(Season, year=season_year)
        else:
            season = Season.objects.get(current=True)

        qs = (Fixture.objects
              .filter(season=season)
              .select_related('home_team__club', 'away_team__club', 'division', 'venue', 'season')
              .order_by('date_time'))

        division = self.request.query_params.get('division')
        team = self.request.query_params.get('team')
        status = self.request.query_params.get('status')

        if division:
            qs = qs.filter(division=division)
        if team:
            qs = qs.filter(Q(home_team=team) | Q(away_team=team))
        if status:
            qs = qs.filter(status=status)

        return qs

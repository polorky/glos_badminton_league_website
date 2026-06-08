from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('clubs', views.ClubViewSet, basename='club')
router.register('divisions', views.DivisionViewSet, basename='division')
router.register('teams', views.TeamViewSet, basename='team')
router.register('fixtures', views.FixtureViewSet, basename='fixture')

urlpatterns = router.urls

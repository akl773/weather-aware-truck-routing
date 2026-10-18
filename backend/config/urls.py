from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from config.health import HealthView
from trips.views import CorridorView, PlacesView, PlanView

urlpatterns = [
    path("api/health", HealthView.as_view(), name="health"),
    path("api/places", PlacesView.as_view(), name="places"),
    path("api/plan", PlanView.as_view(), name="plan"),
    path("api/corridor", CorridorView.as_view(), name="corridor"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]

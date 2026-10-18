from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from config.health import HealthView
from trips.views import PlacesView

urlpatterns = [
    path("api/health", HealthView.as_view(), name="health"),
    path("api/places", PlacesView.as_view(), name="places"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]

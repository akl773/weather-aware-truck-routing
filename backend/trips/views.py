from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from providers import open_meteo, stadia
from providers.geo import Point
from trips.plan import plan_trip
from trips.serializers import (
    PlaceSerializer,
    PlanRequestSerializer,
    PlanResponseSerializer,
    plan_response,
)


class PlacesQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=100, trim_whitespace=True)


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text="What went wrong, ready to show to the user.")
    fields = serializers.DictField(
        required=False, help_text="Per-field messages, present when the input was invalid."
    )


class PlacesView(APIView):
    """Place suggestions for the trip form, proxied so the provider key stays here (routing D6)."""

    @extend_schema(
        operation_id="places",
        parameters=[
            OpenApiParameter(
                "q", str, required=True, description="What the user has typed, 2+ chars."
            )
        ],
        responses={200: PlaceSerializer(many=True), 400: ErrorSerializer, 502: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        query = PlacesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        places = stadia.default().autocomplete(query.validated_data["q"])
        return Response(
            [{"label": p.label, "lat": p.point.lat, "lon": p.point.lon} for p in places]
        )


class PlanView(APIView):
    """Three routes ranked by forecast risk at the truck's ETA (plan-api.md)."""

    @extend_schema(
        operation_id="plan",
        request=PlanRequestSerializer,
        responses={
            200: PlanResponseSerializer,
            400: ErrorSerializer,
            422: ErrorSerializer,
            502: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        now = timezone.now()
        trip = PlanRequestSerializer(data=request.data, context={"now": now})
        trip.is_valid(raise_exception=True)
        data = trip.validated_data
        plan = plan_trip(
            origin=Point(data["origin"]["lat"], data["origin"]["lon"]),
            destination=Point(data["destination"]["lat"], data["destination"]["lon"]),
            departure=data["departure"],
            load_lb=data["load_lb"],
            interval_mi=data["interval_mi"],
            router=stadia.default(),
            weather=open_meteo.default(),
            now=now,
        )
        return Response(plan_response(plan))

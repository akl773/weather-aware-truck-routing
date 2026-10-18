from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from providers import stadia


class PlacesQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=100, trim_whitespace=True)


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()


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

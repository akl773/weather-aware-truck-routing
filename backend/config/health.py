from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    version = serializers.CharField(help_text="Git SHA of the running build.")


class HealthView(APIView):
    @extend_schema(responses=HealthSerializer, operation_id="health")
    def get(self, request: Request) -> Response:
        return Response({"status": "ok", "version": settings.GIT_SHA})

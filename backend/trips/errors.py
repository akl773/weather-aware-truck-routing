"""Map provider failures to HTTP responses for every API view."""

from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from providers.errors import NoRouteError, ProviderError


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, NoRouteError):
        # The request was valid; the places it names have no truck route between them.
        return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if isinstance(exc, ProviderError):
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    return drf_exception_handler(exc, context)

"""One error shape for every API failure: `{"detail": str}`, plus `fields` for invalid input."""

from typing import Any

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from providers.errors import NoRouteError, ProviderError


def _first_message(errors: Any) -> str:
    """The first human-readable message in DRF's nested error structure."""
    if isinstance(errors, dict):
        field, value = next(iter(errors.items()))
        message = _first_message(value)
        return message if field == "non_field_errors" else f"{field}: {message}"
    if isinstance(errors, list) and errors:
        return _first_message(errors[0])
    return str(errors)


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, NoRouteError):
        # The request was valid; the places it names have no truck route between them.
        return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if isinstance(exc, ProviderError):
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    if isinstance(exc, ValidationError):
        return Response(
            {"detail": _first_message(exc.detail), "fields": exc.detail},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return drf_exception_handler(exc, context)

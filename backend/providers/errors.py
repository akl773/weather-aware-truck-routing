"""Failures every adapter raises, whatever its provider. Views map them to HTTP statuses."""


class ProviderError(Exception):
    """The provider could not answer: unreachable, timed out, rate limited or misconfigured."""


class NoRouteError(Exception):
    """The provider answered, and there is no truck route between the places given."""

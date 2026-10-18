"""Trips the provider fixtures were recorded for. Tests and the recorder share these inputs."""

from providers.geo import Point

DENVER = Point(39.7392, -104.9903)
SALT_LAKE_CITY = Point(40.7608, -111.8910)
ATLANTA = Point(33.7490, -84.3880)
CHARLOTTE = Point(35.2271, -80.8431)
DALLAS = Point(32.7767, -96.7970)
HOUSTON = Point(29.7604, -95.3698)
# A point in the Colorado backcountry with no road Valhalla can snap a truck to.
BACKCOUNTRY = Point(39.5501, -105.7821)

LOAD_LB = 30_000

ROUTE_SCENARIOS = {
    # Valhalla returns three routes itself.
    "stadia_route_denver_salt_lake_city": (DENVER, SALT_LAKE_CITY),
    # Valhalla returns two; the third is a via-point fallback.
    "stadia_route_atlanta_charlotte": (ATLANTA, CHARLOTTE),
    # Valhalla returns one; both others are fallbacks.
    "stadia_route_dallas_houston": (DALLAS, HOUSTON),
    "stadia_route_no_path": (DENVER, BACKCOUNTRY),
}

PLACES_SCENARIOS = {"stadia_places_denv": "Denv"}

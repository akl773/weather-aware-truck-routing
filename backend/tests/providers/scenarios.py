"""Trips the provider fixtures were recorded for. Tests and the recorder share these inputs."""

from datetime import UTC, datetime

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

# Weather. Recorded once against the live forecast; the start is fixed so replays never move.
WEATHER_START = datetime(2026, 10, 19, 11, 0, tzinfo=UTC)
WEATHER_HOURS = 72
# Along I-70 west of Denver. The first two are 1 km apart and share a lattice point.
I70_POINTS = (
    Point(39.7392, -104.9903),
    Point(39.7431, -104.9989),
    Point(39.7420, -105.5130),
    Point(39.6400, -106.3700),
    Point(39.5500, -107.3200),
)
WEATHER_SCENARIOS = {
    "openmeteo_i70": (I70_POINTS, None),
    # The same points with a batch size of 2, to record a multi-request fetch.
    "openmeteo_i70_batched": (I70_POINTS, 2),
}

# A whole plan: Denver to Salt Lake City at the default interval. Routes replay from
# stadia_route_denver_salt_lake_city; the checkpoint weather from the plan recording.
PLAN_NOW = datetime(2026, 10, 18, 18, 0, tzinfo=UTC)
PLAN_DEPARTURE = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
PLAN_INTERVAL_MI = 25
PLAN_WEATHER_FIXTURE = "openmeteo_plan_denver_salt_lake_city"

# A corridor small enough to keep its recording small: Denver to Boulder in a straight line, at the
# plan's departure.
BOULDER = Point(40.0150, -105.2705)
CORRIDOR_PATH = (DENVER, BOULDER)
CORRIDOR_WEATHER_FIXTURE = "openmeteo_corridor_denver_boulder"

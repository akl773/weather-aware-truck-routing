import json
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest

from providers import open_meteo
from providers.errors import ProviderError
from providers.geo import Point
from providers.open_meteo import (
    BASE_URL,
    OpenMeteo,
    Series,
    fetch_window,
    parse_location,
    snap,
)
from tests.providers.replay import FIXTURES, replay_client
from tests.providers.scenarios import I70_POINTS, WEATHER_HOURS, WEATHER_START


def weather(fixture: str) -> OpenMeteo:
    return OpenMeteo(replay_client(fixture, BASE_URL))


def location(**hourly) -> dict:
    base = {
        "time": [0, 3600],
        "wind_speed_10m": [10.0, 12.0],
        "wind_gusts_10m": [20.0, 22.0],
        "rain": [0.1, 0.2],
        "showers": [0.05, 0.0],
        "snowfall": [0.0, 0.4],
    }
    return {"hourly": base | hourly}


# --- Units and variables (D2) --------------------------------------------------------------------


def test_rain_adds_showers():
    series = parse_location(location())
    assert series.rain_in_hr == pytest.approx((0.15, 0.2))


def test_snow_is_snowfall_depth():
    assert parse_location(location()).snow_in_hr == (0.0, 0.4)


def test_a_non_finite_value_is_missing_not_a_reading():
    series = parse_location(
        location(wind_speed_10m=[float("nan"), 12.0], snowfall=[float("inf"), 0])
    )
    assert series.wind_mph[0] is None
    assert series.snow_in_hr[0] is None


def test_a_missing_value_stays_missing():
    series = parse_location(location(rain=[None, 0.2], wind_speed_10m=[None, 12.0]))
    assert series.rain_in_hr[0] is None
    assert series.wind_mph[0] is None


def test_requests_ask_for_mph_and_inches():
    sent = []

    def handler(request):
        sent.append(dict(httpx.QueryParams(request.content.decode())))
        return httpx.Response(200, json=location())

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    OpenMeteo(client).hourly([I70_POINTS[0]], WEATHER_START, 2)
    assert sent[0]["wind_speed_unit"] == "mph"
    assert sent[0]["precipitation_unit"] == "inch"
    assert sent[0]["hourly"] == "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"
    assert sent[0]["timeformat"] == "unixtime"
    assert sent[0]["timezone"] == "GMT"


def test_a_start_in_another_zone_is_requested_in_utc():
    sent = []

    def handler(request):
        sent.append(dict(httpx.QueryParams(request.content.decode())))
        return httpx.Response(200, json=location())

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    denver = timezone(timedelta(hours=-6))
    OpenMeteo(client).hourly([I70_POINTS[0]], WEATHER_START.astimezone(denver), 2)
    assert sent[0]["start_hour"] == "2026-10-19T11:00"
    assert sent[0]["end_hour"] == "2026-10-19T12:00"


# --- Timing (D3) ---------------------------------------------------------------------------------


def test_hourly_totals_sit_mid_hour():
    series = parse_location(location(time=[7200, 10800]))
    assert series.times == (7200.0, 10800.0)
    assert series.period_times == (5400.0, 9000.0)


# --- Lattice and batching (D4) -------------------------------------------------------------------


def test_snap_rounds_to_the_0_05_degree_lattice():
    assert snap(Point(39.7392, -104.9903)) == Point(39.75, -105.0)
    assert snap(Point(39.724, -104.976)) == Point(39.7, -105.0)


def test_nearby_points_share_one_location():
    result = weather("openmeteo_i70").hourly(I70_POINTS, WEATHER_START, WEATHER_HOURS)
    # Five points, the first two 1 km apart: four locations, one series per point asked about.
    assert list(result) == list(I70_POINTS)
    assert snap(I70_POINTS[0]) == snap(I70_POINTS[1])
    assert result[I70_POINTS[0]] is result[I70_POINTS[1]]
    assert len({id(series) for series in result.values()}) == 4


def test_each_point_gets_the_answer_for_its_own_location():
    recorded = json.loads((FIXTURES / "openmeteo_i70.json").read_text())[0]
    request = dict(recorded["request"]["body"])
    lattice = [
        Point(float(lat), float(lon))
        for lat, lon in zip(
            request["latitude"].split(","), request["longitude"].split(","), strict=True
        )
    ]
    answers = dict(zip(lattice, recorded["response"]["body"], strict=True))
    result = weather("openmeteo_i70").hourly(I70_POINTS, WEATHER_START, WEATHER_HOURS)
    for point in I70_POINTS:
        answer = answers[snap(point)]
        assert result[point] == parse_location(answer)
        assert answer["latitude"] == pytest.approx(snap(point).lat, abs=0.1)
        assert answer["longitude"] == pytest.approx(snap(point).lon, abs=0.1)


def test_recorded_series_cover_the_window_hourly():
    result = weather("openmeteo_i70").hourly(I70_POINTS, WEATHER_START, WEATHER_HOURS)
    for series in result.values():
        assert len(series.times) == WEATHER_HOURS
        assert series.times[0] == WEATHER_START.timestamp()
        assert all(b - a == 3600 for a, b in zip(series.times, series.times[1:], strict=False))


def test_large_requests_are_batched(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return replay_client("openmeteo_i70_batched", BASE_URL).send(request)

    monkeypatch.setattr(open_meteo, "BATCH_SIZE", 2)
    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    result = OpenMeteo(client).hourly(I70_POINTS, WEATHER_START, WEATHER_HOURS)
    assert len(calls) == 2  # four locations in batches of two
    assert list(result) == list(I70_POINTS)


def test_a_failed_batch_keeps_the_batches_before_it(monkeypatch):
    calls = []

    def second_batch_rate_limited(request):
        calls.append(request)
        if len(calls) == 2:
            return httpx.Response(429)
        return replay_client("openmeteo_i70_batched", BASE_URL).send(request)

    monkeypatch.setattr(open_meteo, "BATCH_SIZE", 2)
    client = httpx.Client(
        base_url=BASE_URL, transport=httpx.MockTransport(second_batch_rate_limited)
    )
    with pytest.raises(ProviderError, match="rate limiting"):
        OpenMeteo(client).hourly(I70_POINTS, WEATHER_START, WEATHER_HOURS)
    OpenMeteo(client).hourly(I70_POINTS, WEATHER_START, WEATHER_HOURS)
    # The retry asks only for the batch that failed.
    assert len(calls) == 3


def test_a_single_location_answer_is_not_a_list():
    client = httpx.Client(
        base_url=BASE_URL,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=location())),
    )
    result = OpenMeteo(client).hourly([I70_POINTS[0]], WEATHER_START, 2)
    assert list(result) == [I70_POINTS[0]]


# --- Window (D5) ---------------------------------------------------------------------------------

NOW = datetime(2026, 10, 18, 17, 30, tzinfo=UTC)


def test_window_starts_the_hour_before_departure():
    start, _ = fetch_window(datetime(2026, 10, 19, 6, 45, tzinfo=UTC), NOW, NOW)
    assert start == datetime(2026, 10, 19, 5, 0, tzinfo=UTC)


def test_window_is_shared_by_plan_and_heatmap():
    departure = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
    plan = fetch_window(departure, departure + timedelta(hours=9), NOW)
    heatmap = fetch_window(departure, departure + timedelta(hours=48), NOW)
    assert plan == heatmap
    assert plan[1] == 72


def test_window_grows_by_whole_days_for_long_trips():
    departure = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
    assert fetch_window(departure, departure + timedelta(hours=75), NOW)[1] == 96


def last_total_at(start: datetime, hours: int) -> datetime:
    """When the window's last hourly total is valid (D3)."""
    return start + timedelta(hours=hours - 1, minutes=-30)


def test_window_covers_a_last_eta_on_its_last_hourly_total():
    departure = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
    start = datetime(2026, 10, 19, 5, 0, tzinfo=UTC)
    needed = start + timedelta(hours=70, minutes=30)
    _, hours = fetch_window(departure, needed, NOW)
    assert hours == 72
    assert last_total_at(start, hours) == needed


def test_window_grows_when_a_last_eta_passes_its_last_hourly_total():
    departure = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
    start = datetime(2026, 10, 19, 5, 0, tzinfo=UTC)
    needed = start + timedelta(hours=70, minutes=30, seconds=1)
    _, hours = fetch_window(departure, needed, NOW)
    assert hours == 96
    assert last_total_at(start, hours) >= needed


def test_window_is_clamped_to_the_provider_range():
    departure = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)  # 15 days out
    start, hours = fetch_window(departure, departure + timedelta(hours=40), NOW)
    assert start + timedelta(hours=hours - 1) == datetime(2026, 11, 2, 23, 0, tzinfo=UTC)


def test_departure_past_the_range_is_refused():
    departure = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="beyond the weather forecast"):
        fetch_window(departure, departure, NOW)


# --- Cache (D6) ----------------------------------------------------------------------------------


def test_a_second_identical_fetch_makes_no_call():
    calls = []

    def handler(request):
        calls.append(request)
        return replay_client("openmeteo_i70", BASE_URL).send(request)

    adapter = OpenMeteo(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)))
    adapter.hourly(I70_POINTS, WEATHER_START, WEATHER_HOURS)
    adapter.hourly(I70_POINTS, WEATHER_START, WEATHER_HOURS)
    assert len(calls) == 1


def test_a_subset_of_cached_points_makes_no_call():
    calls = []

    def handler(request):
        calls.append(request)
        return replay_client("openmeteo_i70", BASE_URL).send(request)

    adapter = OpenMeteo(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)))
    adapter.hourly(I70_POINTS, WEATHER_START, WEATHER_HOURS)
    adapter.hourly(I70_POINTS[:2], WEATHER_START, WEATHER_HOURS)
    assert len(calls) == 1


# --- Failures ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (httpx.Response(429), "rate limiting"),
        (httpx.Response(400, json={"error": True, "reason": "bad"}), "failed to answer"),
        (httpx.Response(200, text="<html>"), "unreadable"),
        (httpx.Response(200, json=[location(), location()]), "wrong number"),
        (httpx.Response(200, json={"hourly": {"time": [0]}}), "unreadable"),
        (httpx.Response(200, json=location(rain=[0.1])), "unreadable"),
    ],
)
def test_bad_answers_are_provider_errors(answer, message):
    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(lambda r: answer))
    with pytest.raises(ProviderError, match=message):
        OpenMeteo(client).hourly([I70_POINTS[0]], WEATHER_START, 2)


def test_unreachable_provider_is_a_provider_error():
    def handler(request):
        raise httpx.ConnectTimeout("down")

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="could not be reached"):
        OpenMeteo(client).hourly([I70_POINTS[0]], WEATHER_START, 2)


def test_series_fields_carry_app_units_not_provider_names():
    fields = set(Series.__dataclass_fields__)
    assert fields == {"times", "wind_mph", "gust_mph", "rain_in_hr", "snow_in_hr"}

"""The trip corridor and its hourly weather frames (corridor-heatmap.md)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from providers.geo import Point, cumulative_mi, haversine_mi, resample
from providers.open_meteo import OpenMeteo, fetch_window
from risk.levels import Level
from trips.plan import HEATMAP_HOURS, Readings, classify_checkpoint, readings_at

BUFFER_MI = 25
# Multiples of the 0.05° weather lattice, so cell centres are lattice points (D1).
CELL_SIZES_DEG = (0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0)
MAX_CELLS = 250
DENSIFY_MI = 2.0
MI_PER_DEG_LAT = 69.0


@dataclass(frozen=True)
class Corridor:
    cell_deg: float
    cells: tuple[Point, ...]  # centres, south to north, then west to east


@dataclass(frozen=True)
class Frame:
    hour: int
    readings: tuple[Readings, ...]  # one per cell, in corridor order
    levels: tuple[Level | None, ...]


class CorridorTooLarge(ValueError):
    pass


def _cells_within(samples: Sequence[Point], size: float, limit: int) -> set[tuple[int, int]] | None:
    """Grid indices of cells near the samples at `size`, or `None` once there are over `limit`."""
    # A route point inside a cell is at most half the cell's diagonal from its centre, and at most
    # half a densify step from a sample, so this radius includes every cell a route crosses (D1).
    half_diagonal = size * MI_PER_DEG_LAT * math.sqrt(2) / 2
    radius = max(BUFFER_MI, half_diagonal + DENSIFY_MI / 2)
    radius_lat = radius / MI_PER_DEG_LAT
    found: set[tuple[int, int]] = set()
    for p in samples:
        # Longitude degrees shrink towards the poles: size the search for the box's polar edge.
        polar_lat = min(89.0, abs(p.lat) + radius_lat)
        radius_lon = radius / (MI_PER_DEG_LAT * math.cos(math.radians(polar_lat)))
        for row in range(
            math.ceil((p.lat - radius_lat) / size), math.floor((p.lat + radius_lat) / size) + 1
        ):
            for col in range(
                math.ceil((p.lon - radius_lon) / size), math.floor((p.lon + radius_lon) / size) + 1
            ):
                if (row, col) in found:
                    continue
                if haversine_mi(p, Point(row * size, col * size)) <= radius:
                    found.add((row, col))
                    if len(found) > limit:
                        return None
    return found


def corridor_cells(paths: Sequence[Sequence[Point]], max_cells: int = MAX_CELLS) -> Corridor:
    """The corridor around `paths` at the finest cell size with at most `max_cells` cells (D1)."""
    samples = [p for path in paths for p in resample(path, cumulative_mi(path), DENSIFY_MI)]
    for size in CELL_SIZES_DEG:
        found = _cells_within(samples, size, max_cells)
        if found is not None:
            cells = tuple(
                Point(round(row * size, 4), round(col * size, 4)) for row, col in sorted(found)
            )
            return Corridor(cell_deg=size, cells=cells)
    raise CorridorTooLarge(
        f"The routes cover too much ground to map: more than {max_cells} cells at "
        f"{CELL_SIZES_DEG[-1]}°."
    )


def corridor_frames(
    corridor: Corridor,
    *,
    departure: datetime,
    load_lb: float,
    weather: OpenMeteo,
    now: datetime,
) -> tuple[Frame, ...]:
    """Every cell's readings and level at departure + 0 to 48 hours (D2)."""
    start, hours = fetch_window(departure, departure + timedelta(hours=HEATMAP_HOURS), now)
    series = weather.hourly(corridor.cells, start, hours)
    cell_series = [series[cell] for cell in corridor.cells]
    frames = []
    for hour in range(HEATMAP_HOURS + 1):
        at = departure + timedelta(hours=hour)
        readings = tuple(readings_at(s, at) for s in cell_series)
        levels = tuple(classify_checkpoint(r, load_lb)[0] for r in readings)
        frames.append(Frame(hour=hour, readings=readings, levels=levels))
    return tuple(frames)

"""
Data acquisition from the Open-Meteo Historical Weather API.

Why HOURLY and not DAILY?
--------------------------
Two of the required raw variables for this project - relative_humidity_2m and
cloud_cover - do NOT have an official daily aggregate in the Open-Meteo Historical
Weather API's `daily=` parameter (see the API docs: the daily endpoint only
exposes things like temperature_2m_max/min, precipitation_sum, wind_speed_10m_max,
wind_gusts_10m_max, etc. - there is no daily relative humidity or daily cloud
cover). To keep both target formulas exactly as specified, we therefore pull
HOURLY data for all required variables and aggregate to daily ourselves, with
explicit, documented aggregation choices (see `aggregate_hourly_to_daily`).

This module performs real, live HTTP calls - no synthetic/mocked weather data
is used anywhere in this project, per the assignment requirement.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Iterable, List

import pandas as pd
import requests

from .config import (
    OPEN_METEO_ARCHIVE_URL,
    REQUIRED_HOURLY_VARIABLES,
    SYDNEY_LATITUDE,
    SYDNEY_LONGITUDE,
    SYDNEY_TIMEZONE,
)


def _chunk_date_ranges(start_date: str, end_date: str, chunk_years: int = 4) -> List[tuple]:
    """Split a [start_date, end_date] range into smaller chunks.

    The Open-Meteo archive API can technically return very long hourly ranges
    in one call, but large single requests are slower, harder to retry, and
    more likely to time out. Chunking by a few years at a time keeps each
    request small, makes partial failures cheap to retry, and lets us cache
    intermediate raw pulls to disk.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    chunks = []
    cur = start
    while cur < end:
        chunk_end = min(cur + timedelta(days=365 * chunk_years), end)
        chunks.append((cur.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cur = chunk_end + timedelta(days=1)
    return chunks


def fetch_open_meteo_hourly(
    start_date: str,
    end_date: str,
    latitude: float = SYDNEY_LATITUDE,
    longitude: float = SYDNEY_LONGITUDE,
    hourly_variables: Iterable[str] = REQUIRED_HOURLY_VARIABLES,
    timezone: str = SYDNEY_TIMEZONE,
    chunk_years: int = 4,
    max_retries: int = 3,
    retry_backoff_seconds: float = 2.0,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Fetch real hourly historical weather observations from Open-Meteo.

    Parameters
    ----------
    start_date, end_date : str
        ISO8601 dates (YYYY-MM-DD), inclusive.
    latitude, longitude : float
        Defaults to the fixed Sydney, NSW coordinates required by AT2.
    hourly_variables : iterable of str
        Variables passed to the API's `hourly=` parameter.
    timezone : str
        IANA timezone name. Using the local timezone (rather than UTC)
        means each returned day boundary lines up with a Sydney calendar day,
        which matters for daily aggregation and for the +3 day / +7 day
        prediction horizons defined in the assignment.
    chunk_years : int
        Number of years fetched per HTTP request (see `_chunk_date_ranges`).
    max_retries, retry_backoff_seconds :
        Simple retry policy for transient network/HTTP errors.

    Returns
    -------
    pandas.DataFrame
        One row per hourly timestamp, columns = ['time'] + hourly_variables.
    """
    hourly_variables = list(hourly_variables)
    sess = session or requests.Session()

    frames = []
    for chunk_start, chunk_end in _chunk_date_ranges(start_date, end_date, chunk_years):
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": chunk_start,
            "end_date": chunk_end,
            "hourly": ",".join(hourly_variables),
            "timezone": timezone,
        }

        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                response = sess.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=60)
                response.raise_for_status()
                payload = response.json()
                if "error" in payload and payload.get("error"):
                    raise ValueError(f"Open-Meteo API error: {payload.get('reason')}")
                break
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                if attempt == max_retries:
                    raise RuntimeError(
                        f"Failed to fetch Open-Meteo data for {chunk_start}..{chunk_end} "
                        f"after {max_retries} attempts: {exc}"
                    ) from exc
                time.sleep(retry_backoff_seconds * attempt)
        else:  # pragma: no cover - defensive
            raise last_exc  # type: ignore[misc]

        hourly = payload["hourly"]
        chunk_df = pd.DataFrame(hourly)
        chunk_df["time"] = pd.to_datetime(chunk_df["time"])
        frames.append(chunk_df)

        # Be a good API citizen: Open-Meteo's non-commercial usage licence
        # caps daily call volume; a short pause between chunked requests
        # avoids hammering the endpoint.
        time.sleep(0.5)

    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset="time").sort_values("time")
    df = df.reset_index(drop=True)
    return df


def aggregate_hourly_to_daily(hourly_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hourly Open-Meteo observations into one row per calendar day.

    Documented aggregation choices (justified in the experimentation
    notebooks' Data Preparation section):

    | Variable              | Daily aggregation | Rationale                                   |
    |------------------------|--------------------|---------------------------------------------|
    | temperature_2m         | mean               | CCI/WHI formulas expect a single representative temperature for the day |
    | relative_humidity_2m   | mean               | Representative daily comfort level |
    | wind_speed_10m         | mean               | Average sustained wind experienced during the day (CCI) |
    | wind_gusts_10m         | max                | Hazard is driven by the PEAK gust, not the average (WHC) |
    | cloud_cover             | mean               | Average sky obstruction across the day |
    | precipitation           | sum                | Total daily rainfall accumulation |
    | snowfall                | sum                | Total daily snowfall accumulation |

    Returns
    -------
    pandas.DataFrame indexed by 'date' (calendar day, tz-naive).
    """
    df = hourly_df.copy()
    df["date"] = df["time"].dt.floor("D")

    agg_map = {
        "temperature_2m": "mean",
        "relative_humidity_2m": "mean",
        "wind_speed_10m": "mean",
        "wind_gusts_10m": "max",
        "cloud_cover": "mean",
        "precipitation": "sum",
        "snowfall": "sum",
    }
    # Only aggregate columns actually present (in case a caller fetched a subset)
    agg_map = {k: v for k, v in agg_map.items() if k in df.columns}

    daily = df.groupby("date").agg(agg_map).reset_index()
    daily = daily.sort_values("date").reset_index(drop=True)
    return daily

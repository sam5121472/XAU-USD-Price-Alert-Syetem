"""
weather_ml_utils
=================

Reusable functionality for the AT2 - Machine Learning as a Service project
(Open-Meteo based weather intelligence services for Sydney, NSW, Australia).

This package is intended to be extended from the AT1 custom package and
published to TestPyPI. It is imported by:
  - The experimentation notebooks in this repository (Repository 1)
  - The FastAPI deployment application (Repository 2)

so that target-variable formulas, feature engineering and data-acquisition
logic are defined ONCE and reused consistently across training and serving,
avoiding train/serve skew.
"""

from .config import SYDNEY_LATITUDE, SYDNEY_LONGITUDE, SYDNEY_CITY, SYDNEY_TIMEZONE
from .data import fetch_open_meteo_hourly, aggregate_hourly_to_daily
from .targets import compute_cci, compute_whi, whi_to_whc_label, WHC_CLASS_MAP
from .features import add_lag_features, add_rolling_features, add_calendar_features
from .splits import time_based_split
from .inference import (
    build_feature_snapshot,
    build_cci_multi_day_snapshots,
    InsufficientHistoryError,
    SEASON_COLUMNS,
    MAX_LOOKBACK_DAYS,
)

__all__ = [
    "SYDNEY_LATITUDE",
    "SYDNEY_LONGITUDE",
    "SYDNEY_CITY",
    "SYDNEY_TIMEZONE",
    "fetch_open_meteo_hourly",
    "aggregate_hourly_to_daily",
    "compute_cci",
    "compute_whi",
    "whi_to_whc_label",
    "WHC_CLASS_MAP",
    "add_lag_features",
    "add_rolling_features",
    "add_calendar_features",
    "time_based_split",
    "build_feature_snapshot",
    "build_cci_multi_day_snapshots",
    "InsufficientHistoryError",
    "SEASON_COLUMNS",
    "MAX_LOOKBACK_DAYS",
]

__version__ = "0.2.0"

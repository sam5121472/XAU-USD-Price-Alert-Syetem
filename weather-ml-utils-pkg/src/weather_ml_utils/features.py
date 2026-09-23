"""
Feature engineering utilities.

CRITICAL data-leakage note
---------------------------
Both targets are FUTURE values (CCI = +3 days ahead, WHC = +7 days ahead).
At inference time (in the deployed API), the only weather information
available for a given `date` is everything UP TO AND INCLUDING `date` -
nothing about the future is known. Therefore every feature engineered here
is derived ONLY from information available at or before the "as-of" date:
lag values, rolling statistics computed with a trailing (backward-looking)
window, and calendar features of the "as-of" date itself.

The raw same-day weather values for the TARGET date are never used as
features - only their derived, past-looking counterparts are.
"""

from __future__ import annotations

from typing import Iterable, List

import numpy as np
import pandas as pd


def add_lag_features(
    df: pd.DataFrame,
    columns: Iterable[str],
    lags: Iterable[int] = (1, 2, 3, 7, 14),
    date_col: str = "date",
) -> pd.DataFrame:
    """Add lagged versions of the given columns (t-1, t-2, ... days).

    The dataframe must already be sorted by `date_col` ascending and have
    one row per calendar day (no gaps assumed, but missing dates simply
    produce NaN lags which are handled at the train/test split stage).
    """
    out = df.sort_values(date_col).reset_index(drop=True).copy()
    for col in columns:
        for lag in lags:
            out[f"{col}_lag{lag}"] = out[col].shift(lag)
    return out


def add_rolling_features(
    df: pd.DataFrame,
    columns: Iterable[str],
    windows: Iterable[int] = (3, 7, 14),
    date_col: str = "date",
) -> pd.DataFrame:
    """Add trailing rolling mean/std features.

    Uses `.shift(1)` before rolling so the window for day t only includes
    days strictly BEFORE t (t-1, t-2, ... t-window) - i.e. it never includes
    day t itself, which keeps this leakage-safe for same-day inference.
    """
    out = df.sort_values(date_col).reset_index(drop=True).copy()
    for col in columns:
        shifted = out[col].shift(1)
        for window in windows:
            out[f"{col}_rollmean{window}"] = shifted.rolling(window, min_periods=max(2, window // 2)).mean()
            out[f"{col}_rollstd{window}"] = shifted.rolling(window, min_periods=max(2, window // 2)).std()
    return out


def add_calendar_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Add cyclical/calendar features of the 'as-of' date (always known)."""
    out = df.copy()
    dt = pd.to_datetime(out[date_col])
    out["day_of_year"] = dt.dt.dayofyear
    out["month"] = dt.dt.month
    out["day_of_week"] = dt.dt.dayofweek
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)

    # Southern Hemisphere season (Sydney): Dec-Feb summer, Mar-May autumn,
    # Jun-Aug winter, Sep-Nov spring
    season_map = {
        12: "summer", 1: "summer", 2: "summer",
        3: "autumn", 4: "autumn", 5: "autumn",
        6: "winter", 7: "winter", 8: "winter",
        9: "spring", 10: "spring", 11: "spring",
    }
    out["season"] = out["month"].map(season_map)

    # Cyclical encodings so the model sees Dec 31 -> Jan 1 as adjacent
    out["day_of_year_sin"] = np.sin(2 * np.pi * out["day_of_year"] / 365.25)
    out["day_of_year_cos"] = np.cos(2 * np.pi * out["day_of_year"] / 365.25)
    return out


def make_future_target(
    df: pd.DataFrame,
    target_col: str,
    horizon_days: int,
    date_col: str = "date",
    out_col: str | None = None,
) -> pd.DataFrame:
    """Attach the value of `target_col`, `horizon_days` days in the future, to each row.

    Row at date D gets a new column equal to target_col's value at date D+horizon_days.
    Assumes one row per consecutive calendar day (validated by caller via a
    complete date range / reindex step in the notebooks).
    """
    out = df.sort_values(date_col).reset_index(drop=True).copy()
    out_col = out_col or f"{target_col}_future_{horizon_days}d"
    out[out_col] = out[target_col].shift(-horizon_days)
    return out

"""
Inference-time feature building.

This module is the bridge between training (the experimentation notebooks in Repository 1)
and serving (the FastAPI application in Repository 2). It exists so that BOTH sides call the
exact same underlying feature-engineering primitives (`add_lag_features`, `add_rolling_features`,
`add_calendar_features` from this same package) - if training and serving ever built features
differently, predictions would silently be wrong (train/serve skew). Extending this package with
inference-time logic, rather than duplicating feature code inside the FastAPI app, is the reason
this functionality lives here rather than in the `app/` deployment code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import numpy as np
import pandas as pd

from .features import add_calendar_features, add_lag_features, add_rolling_features

SEASON_COLUMNS = ["season_autumn", "season_spring", "season_summer", "season_winter"]

DEFAULT_LAGS = (1, 2, 3, 7, 14)
DEFAULT_WINDOWS = (3, 7, 14)

# The longest lookback any engineered feature depends on (14-day lag / 14-day rolling window).
# A snapshot date needs at least this many PRIOR calendar days of history to avoid NaNs in the
# resulting feature vector - fewer than this and the model would receive features it never saw
# NaN-free during training.
MAX_LOOKBACK_DAYS = max(max(DEFAULT_LAGS), max(DEFAULT_WINDOWS))


class InsufficientHistoryError(ValueError):
    """Raised when there is not enough historical daily data before the requested date to
    compute a NaN-free, leakage-safe feature snapshot."""


def build_feature_snapshot(
    daily_df: pd.DataFrame,
    raw_columns: Sequence[str],
    as_of_date,
    feature_columns: Sequence[str],
    lags: Iterable[int] = DEFAULT_LAGS,
    windows: Iterable[int] = DEFAULT_WINDOWS,
    date_col: str = "date",
) -> pd.DataFrame:
    """Build a single-row, model-ready feature DataFrame "as of" a given date.

    Parameters
    ----------
    daily_df : DataFrame with one row per calendar day, already containing every column in
        `raw_columns` (for CCI this includes a precomputed 'CCI' column; for WHC it does not,
        since WHC's training features never used WHI/WHC's own history - see the WHC
        experimentation notebook's feature-selection section).
    raw_columns : the columns to compute lag/rolling features from (must match what the target
        model was trained on).
    as_of_date : the date whose feature snapshot to build. Every lag/rolling feature is computed
        using ONLY rows at or before this date, and calendar features describe this date itself -
        never anything after it. This mirrors exactly how the experimentation notebooks built
        leakage-safe features, so a model trained there behaves identically here.
    feature_columns : the exact, ordered list of feature names the trained model expects
        (as recorded in that model's `*_model_metadata.json`). The returned row is reindexed to
        match this exactly, which is what protects against subtle column-order or one-hot
        category mismatches between training and serving.

    Raises
    ------
    InsufficientHistoryError if there are not enough prior days of history to compute every
    lag/rolling feature without NaNs, or if `as_of_date` itself is not present in `daily_df`.
    """
    as_of_ts = pd.Timestamp(as_of_date)
    df = daily_df[daily_df[date_col] <= as_of_ts].sort_values(date_col).reset_index(drop=True)

    if df.empty or df[date_col].iloc[-1] != as_of_ts:
        raise InsufficientHistoryError(
            f"No daily weather observation found for {as_of_ts.date()}. "
            "Historical data must include the requested date itself."
        )

    days_of_prior_history = len(df) - 1
    if days_of_prior_history < MAX_LOOKBACK_DAYS:
        raise InsufficientHistoryError(
            f"Only {days_of_prior_history} day(s) of history are available before "
            f"{as_of_ts.date()}, but at least {MAX_LOOKBACK_DAYS} are required to compute "
            "this model's lag/rolling features without gaps. Choose a later date, or ensure "
            "more historical data is available."
        )

    feat = add_lag_features(df, columns=list(raw_columns), lags=list(lags), date_col=date_col)
    feat = add_rolling_features(feat, columns=list(raw_columns), windows=list(windows), date_col=date_col)
    feat = add_calendar_features(feat, date_col=date_col)

    row = feat[feat[date_col] == as_of_ts]
    if row.empty:
        raise InsufficientHistoryError(f"Could not locate {as_of_ts.date()} after feature engineering.")
    row = row.iloc[[-1]].copy()

    dummies = pd.get_dummies(row["season"], prefix="season")
    for col in SEASON_COLUMNS:
        if col not in dummies.columns:
            dummies[col] = 0
    row = row.drop(columns=["season"]).join(dummies[SEASON_COLUMNS])

    X = row.reindex(columns=list(feature_columns))
    if X.isna().any(axis=None):
        missing = X.columns[X.isna().any()].tolist()
        raise InsufficientHistoryError(
            f"Computed feature snapshot for {as_of_ts.date()} has missing values in: {missing}. "
            "This usually means the supplied daily history has a gap (a missing calendar day)."
        )
    return X


@dataclass
class CCIForecast:
    target_date: pd.Timestamp
    as_of_date: pd.Timestamp
    value: float


def build_cci_multi_day_snapshots(
    daily_df_with_cci: pd.DataFrame,
    input_date,
    feature_columns: Sequence[str],
    raw_columns: Sequence[str],
    horizon_days: int = 3,
    date_col: str = "date",
) -> List[pd.DataFrame]:
    """Build the feature snapshots needed to forecast CCI for EACH of the next `horizon_days` days.

    The trained CCI model predicts a single fixed horizon ("the CCI value exactly `horizon_days`
    days after the as-of date it was fed"). The API contract, however, asks for a value on each
    of the next `horizon_days` days (see `/predict/index/comfort_climate`'s example response).
    Rather than training `horizon_days` separate models, the SAME model is reused `horizon_days`
    times, each time fed a feature snapshot "as of" one extra day earlier
    (input_date, input_date-1, input_date-2, ...). Feeding the model a snapshot as of
    (input_date - k) yields a prediction for (input_date - k) + horizon_days:
        as_of = input_date             -> prediction date = input_date + horizon_days
        as_of = input_date - 1         -> prediction date = input_date + horizon_days - 1
        as_of = input_date - 2         -> prediction date = input_date + horizon_days - 2
        ...
    This only uses historical data at or before `input_date`, which is exactly what is actually
    available at request time - no future information is used for any of the `horizon_days`
    outputs, preserving the same leakage-safety guarantee used during training.
    """
    input_ts = pd.Timestamp(input_date)
    snapshots = []
    for k in range(horizon_days - 1, -1, -1):
        as_of = input_ts - pd.Timedelta(days=k)
        snapshot = build_feature_snapshot(daily_df_with_cci, raw_columns, as_of, feature_columns, date_col=date_col)
        target_date = as_of + pd.Timedelta(days=horizon_days)
        snapshots.append((target_date, snapshot))
    return snapshots

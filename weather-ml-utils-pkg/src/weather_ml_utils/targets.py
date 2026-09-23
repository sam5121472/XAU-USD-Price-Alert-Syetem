"""
Target variable definitions, implemented exactly as specified in the
AT2 assignment brief.

Target 1 - Climate Comfort Index (CCI)   -> regression, range 0-100
Target 2 - Weather Hazard Category (WHC) -> multiclass classification (4 classes)

Both are computed from the DAILY-aggregated weather observations produced by
`weather_ml_utils.data.aggregate_hourly_to_daily`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WHC_CLASS_MAP = {
    0: "Low Risk",
    1: "Moderate Risk",
    2: "High Risk",
    3: "Extreme Risk",
}


def compute_cci(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Compute the Climate Comfort Index (CCI) for each day.

    Formulas (as specified in the AT2 brief):
        TempScore     = MAX(0, 1 - ABS(temperature_2m - 22) / 20)
        HumidityScore = MAX(0, 1 - ABS(relative_humidity_2m - 50) / 50)
        WindScore     = MAX(0, 1 - ABS(wind_speed_10m - 10) / 40)
        CloudScore    = MAX(0, 1 - cloud_cover / 100)
        RainScore     = MAX(0, 1 - precipitation / 20)

        CCI = 100 * (0.35*TempScore + 0.20*HumidityScore + 0.15*WindScore
                      + 0.15*CloudScore + 0.15*RainScore)
    """
    df = daily_df.copy()

    df["TempScore"] = np.maximum(0, 1 - (df["temperature_2m"] - 22).abs() / 20)
    df["HumidityScore"] = np.maximum(0, 1 - (df["relative_humidity_2m"] - 50).abs() / 50)
    df["WindScore"] = np.maximum(0, 1 - (df["wind_speed_10m"] - 10).abs() / 40)
    df["CloudScore"] = np.maximum(0, 1 - df["cloud_cover"] / 100)
    df["RainScore"] = np.maximum(0, 1 - df["precipitation"] / 20)

    df["CCI"] = 100 * (
        0.35 * df["TempScore"]
        + 0.20 * df["HumidityScore"]
        + 0.15 * df["WindScore"]
        + 0.15 * df["CloudScore"]
        + 0.15 * df["RainScore"]
    )
    return df


def compute_whi(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Compute the Weather Hazard Index (WHI) for each day.

    Formulas (as specified in the AT2 brief):
        RainHazard = MIN(precipitation / 30, 1)
        WindHazard = MIN(wind_gusts_10m / 100, 1)
        CloudHazard = MIN(cloud_cover / 100, 1)
        SnowHazard = MIN(snowfall / 15, 1)
        TempHazard = MIN(ABS(temperature_2m - 22) / 25, 1)

        WHI = 100 * (0.30*RainHazard + 0.30*WindHazard + 0.20*CloudHazard
                      + 0.10*SnowHazard + 0.10*TempHazard)
    """
    df = daily_df.copy()

    df["RainHazard"] = np.minimum(df["precipitation"] / 30, 1)
    df["WindHazard"] = np.minimum(df["wind_gusts_10m"] / 100, 1)
    df["CloudHazard"] = np.minimum(df["cloud_cover"] / 100, 1)
    df["SnowHazard"] = np.minimum(df["snowfall"] / 15, 1)
    df["TempHazard"] = np.minimum((df["temperature_2m"] - 22).abs() / 25, 1)

    df["WHI"] = 100 * (
        0.30 * df["RainHazard"]
        + 0.30 * df["WindHazard"]
        + 0.20 * df["CloudHazard"]
        + 0.10 * df["SnowHazard"]
        + 0.10 * df["TempHazard"]
    )
    return df


def whi_to_whc_label(whi: pd.Series | np.ndarray | float):
    """Convert a continuous WHI value into the WHC classification label (0-3).

    Condition            -> Class
    WHI < 25              -> 0 (Low Risk)
    25 <= WHI < 50         -> 1 (Moderate Risk)
    50 <= WHI < 75         -> 2 (High Risk)
    WHI >= 75              -> 3 (Extreme Risk)
    """
    bins = [-np.inf, 25, 50, 75, np.inf]
    labels = [0, 1, 2, 3]
    if isinstance(whi, (pd.Series, np.ndarray)):
        whi_series = pd.Series(whi)
        return pd.cut(whi_series, bins=bins, labels=labels, right=False).astype(int)
    # scalar
    for lo, hi, cls in zip(bins[:-1], bins[1:], labels):
        if lo <= whi < hi:
            return cls
    raise ValueError(f"Unexpected WHI value: {whi}")

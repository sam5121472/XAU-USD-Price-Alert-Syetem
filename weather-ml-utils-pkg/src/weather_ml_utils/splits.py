"""
Time-based data splitting.

Weather data is a time series with strong autocorrelation, so a random
shuffled train/test split would leak information from the future into
training (e.g. training on a day that sits between two test days) and
would give an overly optimistic estimate of real-world performance.
Instead we split chronologically: the earliest observations are used for
training, the next slice for validation, and the most recent pre-2026
slice for testing - mimicking how the deployed model will actually be used
(trained on the past, evaluated on data it has not seen "yet").
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd


def time_based_split(
    df: pd.DataFrame,
    date_col: str = "date",
    train_frac: float = 0.70,
    val_frac: float = 0.15,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split a dataframe chronologically into train / validation / test sets.

    Parameters
    ----------
    train_frac, val_frac : float
        Fractions of the (chronologically sorted) rows assigned to train and
        validation respectively. The remainder goes to test.
    """
    assert 0 < train_frac < 1 and 0 < val_frac < 1 and train_frac + val_frac < 1

    ordered = df.sort_values(date_col).reset_index(drop=True)
    n = len(ordered)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))

    train_df = ordered.iloc[:train_end].copy()
    val_df = ordered.iloc[train_end:val_end].copy()
    test_df = ordered.iloc[val_end:].copy()
    return train_df, val_df, test_df

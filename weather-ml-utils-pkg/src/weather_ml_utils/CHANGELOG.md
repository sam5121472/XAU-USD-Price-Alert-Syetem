# Changelog — weather-ml-utils

## 0.2.0 (Repository 2 / deployment extension)
- Added `weather_ml_utils.inference` module: `build_feature_snapshot`,
  `build_cci_multi_day_snapshots`, `InsufficientHistoryError`.
- This extends the package (originally built for Repository 1's experimentation notebooks) so
  that the FastAPI deployment app in Repository 2 can build model-ready feature vectors at
  request time using the EXACT same feature-engineering logic used during training, avoiding
  train/serve skew.
- Published to TestPyPI as version 0.2.0 (see Repository 2's README for the publish command
  used and the resulting package URL).

## 0.1.0 (Repository 1 / experimentation)
- Initial release: `data`, `targets`, `features`, `splits` modules covering Open-Meteo data
  acquisition, the CCI/WHI target formulas, leakage-safe feature engineering, and chronological
  train/val/test splitting.

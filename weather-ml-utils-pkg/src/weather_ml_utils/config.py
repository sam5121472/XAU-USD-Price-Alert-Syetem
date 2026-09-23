"""
Fixed project configuration.

AT2 requires ALL target variables to be generated using historical weather
observations for exactly one location: Sydney, NSW, Australia.
These constants are imported everywhere instead of being hard-coded in
multiple places, so the location is defined once and cannot drift between
the experimentation repo and the FastAPI deployment repo.
"""

SYDNEY_CITY = "Sydney, NSW, Australia"
SYDNEY_LATITUDE = -33.8688
SYDNEY_LONGITUDE = 151.2093
SYDNEY_TIMEZONE = "Australia/Sydney"

# Required hourly variables per the AT2 brief (union of CCI + WHC requirements)
REQUIRED_HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_gusts_10m",
    "cloud_cover",
    "precipitation",
    "snowfall",
]

# Data availability cut-off enforced by the assignment:
#   < 2026-01-01  -> usable for train / validation / test
#   >= 2026-01-01 -> "production" data, must NOT be used during model development
PRODUCTION_DATA_START_DATE = "2026-01-01"

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

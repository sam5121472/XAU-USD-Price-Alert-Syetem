import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load .env from the project root regardless of current working directory
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_ROOT, ".env"))


def _default_excel_path() -> str:
    configured = os.getenv("EXCEL_PATH", "data/alerts.xlsx")
    if os.path.isabs(configured):
        return configured
    return os.path.join(_ROOT, configured)


@dataclass
class Settings:
    PROJECT_ROOT: str = _ROOT

    GOLDPRICE_API_KEY: str = field(default_factory=lambda: os.getenv("GOLDPRICE_API_KEY", ""))
    GOLDPRICE_BASE_URL: str = field(
        default_factory=lambda: os.getenv("GOLDPRICE_BASE_URL", "https://api.goldprice.dev/v1/prices")
    )

    RESEND_API_KEY: str = field(default_factory=lambda: os.getenv("RESEND_API_KEY", ""))
    RESEND_FROM_EMAIL: str = field(
        default_factory=lambda: os.getenv("RESEND_FROM_EMAIL", "Samzy Alerts <onboarding@resend.dev>")
    )
    ALERT_TO_EMAIL: str = field(default_factory=lambda: os.getenv("ALERT_TO_EMAIL", ""))

    POLL_INTERVAL_MINUTES: float = field(
        default_factory=lambda: float(os.getenv("POLL_INTERVAL_MINUTES", "60"))
    )
    EXCEL_PATH: str = field(default_factory=_default_excel_path)


settings = Settings()

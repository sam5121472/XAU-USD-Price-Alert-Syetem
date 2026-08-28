"""Thin client for the goldprice.dev live spot price API."""
import requests

from app.config import settings


def get_xau_usd_price() -> dict:
    """
    Fetch the live XAU/USD spot price.

    Returns a dict: {"price": float, "is_stale": bool, "computed_at": str}
    """
    if not settings.GOLDPRICE_API_KEY:
        raise RuntimeError("GOLDPRICE_API_KEY is not set in .env")

    resp = requests.get(
        settings.GOLDPRICE_BASE_URL,
        params={"symbol": "XAU-USD-SPOT"},
        headers={"Authorization": f"Bearer {settings.GOLDPRICE_API_KEY}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    # The API has been observed returning either a top-level object
    # or a {"symbols": [...]} wrapper — handle both defensively.
    if isinstance(data, dict) and "symbols" in data and data["symbols"]:
        row = data["symbols"][0]
    else:
        row = data

    return {
        "price": float(row["price"]),
        "is_stale": bool(row.get("is_stale", False)),
        "computed_at": row.get("computed_at"),
    }

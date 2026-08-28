"""
Samzy XAU/USD Assistant — MCP server.

Exposes gold-price and alert-management tools over stdio (the MCP
transport). app/web_app.py drives these tools directly (create/list/delete
alert, get price) to power a plain dashboard UI — no LLM in the loop. The
same server can also be plugged into any other MCP client, such as Claude
Desktop, if you want a natural-language front end for it later.

Run directly for local testing:
    python -m app.mcp_server
"""
from mcp.server.fastmcp import FastMCP

from app.alert_system.price_client import get_xau_usd_price
from app.alert_system.excel_store import create_alert, list_alerts, delete_alert

mcp = FastMCP("samzy-xau-assistant")


@mcp.tool()
def get_price() -> dict:
    """Get the current live XAU/USD (gold spot) price in US dollars per troy ounce."""
    return get_xau_usd_price()


@mcp.tool()
def create_price_alert(condition: str, target_price: float, email: str = "", note: str = "") -> dict:
    """
    Create a new XAU/USD price alert. When the condition becomes true, an
    email is sent automatically and the alert is marked as triggered.

    Args:
        condition: "above" or "below" — fire when price rises above, or falls below, target_price.
        target_price: the XAU/USD price (USD per troy ounce) that triggers the alert.
        email: destination email address. If left blank, the account default (ALERT_TO_EMAIL) is used.
        note: optional short label for the alert, e.g. "breakout watch".
    """
    return create_alert(condition, target_price, email or None, note or None)


@mcp.tool()
def list_price_alerts(status: str = "all") -> list:
    """
    List XAU/USD price alerts.

    Args:
        status: one of "all", "active", or "triggered".
    """
    return list_alerts(status)


@mcp.tool()
def delete_price_alert(alert_id: str) -> dict:
    """Cancel/delete a XAU/USD price alert by its id."""
    ok = delete_alert(alert_id)
    return {"deleted": ok, "id": alert_id}


if __name__ == "__main__":
    mcp.run(transport="stdio")

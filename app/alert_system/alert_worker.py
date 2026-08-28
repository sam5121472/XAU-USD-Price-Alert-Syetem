"""
Samzy XAU/USD Assistant — Alert Worker.

Runs continuously in the background (separate process from the web app).
Polls the goldprice.dev API on a timer, compares the price against every
active alert in alerts.xlsx, and sends an email via Resend whenever a
target is hit.

Run:
    python -m app.alert_system.alert_worker
"""
import time
import traceback
from datetime import datetime

from app.config import settings
from app.alert_system.excel_store import list_alerts, mark_triggered
from app.alert_system.price_client import get_xau_usd_price
from app.alert_system.email_client import send_alert_email


def check_once() -> None:
    price_info = get_xau_usd_price()
    price = price_info["price"]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] XAU/USD = ${price:,.2f}")

    active = list_alerts(status="active")
    for alert in active:
        target = float(alert["target_price"])
        hit = (
            (alert["condition"] == "above" and price >= target)
            or (alert["condition"] == "below" and price <= target)
        )
        if not hit:
            continue

        try:
            send_alert_email(
                to_email=alert["email"],
                target_price=target,
                condition=alert["condition"],
                current_price=price,
                note=alert.get("note", ""),
            )
            mark_triggered(alert["id"], price)
            print(f"  -> ALERT FIRED: {alert['id']} ({alert['condition']} {target}) -> emailed {alert['email']}")
        except Exception:
            print(f"  -> failed to send alert {alert['id']}:")
            traceback.print_exc()


def main() -> None:
    interval = max(settings.POLL_INTERVAL_MINUTES, 1) * 60
    print("Samzy alert worker starting.")
    print(f"Polling every {settings.POLL_INTERVAL_MINUTES} minute(s). Watching: {settings.EXCEL_PATH}")
    while True:
        try:
            check_once()
        except Exception:
            print("Worker error:")
            traceback.print_exc()
        time.sleep(interval)


if __name__ == "__main__":
    main()

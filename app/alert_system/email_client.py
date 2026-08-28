"""Thin client for sending alert emails via Resend."""
import resend

from app.config import settings

resend.api_key = settings.RESEND_API_KEY


def send_alert_email(to_email: str, target_price: float, condition: str, current_price: float, note: str = "") -> dict:
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not set in .env")

    direction = "risen above" if condition == "above" else "fallen below"
    subject = f"🔔 XAU/USD {direction} ${target_price:,.2f}"
    note_html = f"<p style='color:#8B8D93'>Note: {note}</p>" if note else ""

    html = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#C9A227; margin-bottom: 4px;">Samzy XAU/USD Assistant</h2>
      <p style="color:#333;">Your gold price alert has triggered.</p>
      <table style="width:100%; border-collapse: collapse; margin: 16px 0;">
        <tr><td style="padding:6px 0; color:#666;">Condition</td>
            <td style="padding:6px 0; text-align:right; font-weight:600;">Price {direction} target</td></tr>
        <tr><td style="padding:6px 0; color:#666;">Target price</td>
            <td style="padding:6px 0; text-align:right; font-weight:600;">${target_price:,.2f}</td></tr>
        <tr><td style="padding:6px 0; color:#666;">Current price</td>
            <td style="padding:6px 0; text-align:right; font-weight:600; color:#C9A227;">${current_price:,.2f}</td></tr>
      </table>
      {note_html}
      <p style="color:#999; font-size:12px;">This alert has been marked as triggered and won't fire again.</p>
    </div>
    """

    return resend.Emails.send({
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html,
    })

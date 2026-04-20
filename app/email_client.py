"""
Email notifications via Gmail SMTP (or any SMTP server).
Only fires when NOTIFY_EMAIL_SENDER, NOTIFY_EMAIL_PASSWORD, and
NOTIFY_EMAIL_TO are all set in .env — safe to leave blank.

Gmail setup (one-time):
  1. Google Account → Security → enable 2-Step Verification
  2. Google Account → Security → App Passwords → generate one for "Mail"
  3. Use that 16-character password as NOTIFY_EMAIL_PASSWORD
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import (
    NOTIFY_EMAIL_SENDER,
    NOTIFY_EMAIL_PASSWORD,
    NOTIFY_EMAIL_TO,
    NOTIFY_EMAIL_SMTP_HOST,
    NOTIFY_EMAIL_SMTP_PORT,
)

_ENABLED = all([NOTIFY_EMAIL_SENDER, NOTIFY_EMAIL_PASSWORD, NOTIFY_EMAIL_TO])


def _send(subject: str, body_text: str, body_html: str) -> None:
    """Low-level send. Raises on failure — callers decide whether to surface the error."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = NOTIFY_EMAIL_SENDER
    msg["To"] = NOTIFY_EMAIL_TO

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(NOTIFY_EMAIL_SMTP_HOST, NOTIFY_EMAIL_SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(NOTIFY_EMAIL_SENDER, NOTIFY_EMAIL_PASSWORD)
        server.sendmail(NOTIFY_EMAIL_SENDER, NOTIFY_EMAIL_TO.split(","), msg.as_string())


def send_onboarding_notification(
    customer_name: str,
    epic_key: str,
    jira_url: str,
    subtask_keys: list[str],
    actor_email: str,
) -> None:
    """Send an onboarding summary email when Jira tickets are created."""
    if not _ENABLED:
        return

    task_lines_text = "\n".join(f"  - {k}" for k in subtask_keys) if subtask_keys else "  (none)"
    task_rows_html = "".join(
        f"<tr><td style='padding:4px 8px;'>{k}</td></tr>" for k in subtask_keys
    ) if subtask_keys else "<tr><td style='padding:4px 8px; color:#888;'>none</td></tr>"

    subject = f"[Brinc] New customer onboarded: {customer_name}"

    body_text = (
        f"New Customer Onboarded\n"
        f"{'=' * 40}\n"
        f"Customer:    {customer_name}\n"
        f"Jira Epic:   {epic_key}  ({jira_url})\n"
        f"Tasks ({len(subtask_keys)}):\n{task_lines_text}\n"
        f"Triggered by: {actor_email}\n"
    )

    body_html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;">
      <h2 style="color:#0052cc;">&#x1F680; New Customer Onboarded</h2>
      <table style="border-collapse:collapse;">
        <tr><td style="padding:4px 8px;font-weight:bold;">Customer</td>
            <td style="padding:4px 8px;">{customer_name}</td></tr>
        <tr><td style="padding:4px 8px;font-weight:bold;">Jira Epic</td>
            <td style="padding:4px 8px;"><a href="{jira_url}">{epic_key}</a></td></tr>
        <tr><td style="padding:4px 8px;font-weight:bold;">Triggered by</td>
            <td style="padding:4px 8px;">{actor_email}</td></tr>
      </table>
      <h3>Tasks created ({len(subtask_keys)})</h3>
      <table style="border-collapse:collapse;background:#f4f5f7;border-radius:4px;">
        {task_rows_html}
      </table>
    </body></html>
    """

    try:
        _send(subject, body_text, body_html)
    except Exception:
        pass  # Email is best-effort; never block ticket creation on a notification failure


def send_status_change_notification(
    customer_name: str,
    epic_key: str,
    jira_url: str,
    new_status: str,
) -> None:
    """Send an alert when an epic's status changes during a dashboard refresh."""
    if not _ENABLED:
        return

    subject = f"[Brinc] Epic {epic_key} status → {new_status}"

    body_text = (
        f"Epic Status Update\n"
        f"{'=' * 40}\n"
        f"Customer:   {customer_name}\n"
        f"Epic:       {epic_key}  ({jira_url})\n"
        f"New Status: {new_status}\n"
    )

    body_html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;">
      <h2 style="color:#0052cc;">&#x1F504; Epic Status Update</h2>
      <table style="border-collapse:collapse;">
        <tr><td style="padding:4px 8px;font-weight:bold;">Customer</td>
            <td style="padding:4px 8px;">{customer_name}</td></tr>
        <tr><td style="padding:4px 8px;font-weight:bold;">Epic</td>
            <td style="padding:4px 8px;"><a href="{jira_url}">{epic_key}</a></td></tr>
        <tr><td style="padding:4px 8px;font-weight:bold;">New Status</td>
            <td style="padding:4px 8px;"><strong>{new_status}</strong></td></tr>
      </table>
    </body></html>
    """

    try:
        _send(subject, body_text, body_html)
    except Exception:
        pass

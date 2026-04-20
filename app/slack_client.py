"""
Slack notifications via Incoming Webhook.
Only fires when SLACK_WEBHOOK_URL is set in .env — safe to leave unset.
"""
import requests

from app.config import SLACK_WEBHOOK_URL


def send_onboarding_notification(
    customer_name: str,
    epic_key: str,
    jira_url: str,
    subtask_keys: list[str],
    actor_email: str,
) -> None:
    """Post an onboarding summary to the configured Slack channel."""
    if not SLACK_WEBHOOK_URL:
        return

    subtask_list = "\n".join(f"  • {k}" for k in subtask_keys) if subtask_keys else "  _none_"
    message = (
        f":rocket: *New Customer Onboarded*\n"
        f"*Customer:* {customer_name}\n"
        f"*Jira Epic:* <{jira_url}|{epic_key}>\n"
        f"*Tasks created ({len(subtask_keys)}):*\n{subtask_list}\n"
        f"*Triggered by:* {actor_email}"
    )
    payload = {"text": message}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        pass  # Slack is best-effort; never block ticket creation on a notification failure


def send_status_change_notification(
    customer_name: str,
    epic_key: str,
    jira_url: str,
    new_status: str,
) -> None:
    """Post a status change alert to Slack when an epic moves to a new state."""
    if not SLACK_WEBHOOK_URL:
        return

    emoji = ":white_check_mark:" if new_status.lower() == "done" else ":arrows_counterclockwise:"
    message = (
        f"{emoji} *Epic Status Update*\n"
        f"*Customer:* {customer_name}\n"
        f"*Epic:* <{jira_url}|{epic_key}>\n"
        f"*New Status:* {new_status}"
    )
    payload = {"text": message}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        pass

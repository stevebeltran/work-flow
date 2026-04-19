import requests
from requests.auth import HTTPBasicAuth

from app.config import JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY


class JiraError(Exception):
    pass


def _auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(JIRA_USER_EMAIL, JIRA_API_TOKEN)


def _headers() -> dict:
    return {"Content-Type": "application/json", "Accept": "application/json"}


def _raise_for_status(resp: requests.Response) -> None:
    if not resp.ok:
        try:
            detail = resp.json()
            msg = detail.get("errorMessages") or detail.get("errors") or resp.text
        except Exception:
            msg = resp.text
        raise JiraError(f"Jira API {resp.status_code}: {msg}")


def create_epic(customer_name: str, deal_id: str) -> str:
    """Create a Jira Epic for a new customer onboarding. Returns the issue key."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": f"Onboarding: {customer_name}",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Customer onboarding epic for {customer_name}. "
                                    f"HubSpot Deal ID: {deal_id}"
                                ),
                            }
                        ],
                    }
                ],
            },
            "issuetype": {"name": "Epic"},
        }
    }
    resp = requests.post(url, json=payload, auth=_auth(), headers=_headers())
    _raise_for_status(resp)
    return resp.json()["key"]


def create_subtask(
    epic_key: str,
    summary: str,
    description: str,
    assignee_email: str | None = None,
) -> str:
    """Create a Task linked under the given Epic. Returns the issue key."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    fields: dict = {
        "project": {"key": JIRA_PROJECT_KEY},
        "summary": summary,
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description or summary}],
                }
            ],
        },
        "issuetype": {"name": "Task"},
        "parent": {"key": epic_key},
    }
    if assignee_email:
        fields["assignee"] = {"emailAddress": assignee_email}

    resp = requests.post(url, json={"fields": fields}, auth=_auth(), headers=_headers())
    _raise_for_status(resp)
    return resp.json()["key"]


def get_issue_status(issue_key: str) -> str:
    """Return the current status name for a Jira issue."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}?fields=status"
    resp = requests.get(url, auth=_auth(), headers=_headers())
    _raise_for_status(resp)
    return resp.json()["fields"]["status"]["name"]


def build_tickets_preview(templates: list[dict], customer_name: str, deal_id: str = "") -> list[dict]:
    """
    Pure function — substitutes {customer_name} and {deal_id} tokens in template
    summaries and descriptions. Returns a list ready to render as a preview table.
    """
    preview = []
    for t in sorted(templates, key=lambda r: int(r.get("step_order", 0))):
        preview.append(
            {
                "step": t.get("step_order", ""),
                "summary": t.get("summary", "").replace("{customer_name}", customer_name).replace("{deal_id}", deal_id),
                "description": t.get("description", "").replace("{customer_name}", customer_name).replace("{deal_id}", deal_id),
                "issue_type": t.get("issue_type", "Task"),
                "assignee_email": t.get("assignee_email", ""),
            }
        )
    return preview

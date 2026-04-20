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


def create_epic(customer_name: str, deal_id: str, project_key: str | None = None) -> str:
    """Create a Jira Epic for a new customer onboarding. Returns the issue key."""
    key = project_key or JIRA_PROJECT_KEY
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": key},
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
    project_key: str | None = None,
) -> str:
    """Create a Task linked under the given Epic. Returns the issue key."""
    key = project_key or JIRA_PROJECT_KEY
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    fields: dict = {
        "project": {"key": key},
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
    summaries and descriptions. Includes project_key per ticket so the UI can
    show which Jira project each task will be created in.
    """
    preview = []
    for t in sorted(templates, key=lambda r: int(r.get("step_order", 0))):
        proj = (t.get("project_key") or JIRA_PROJECT_KEY).strip().upper()
        preview.append(
            {
                "step": t.get("step_order", ""),
                "project_key": proj,
                "summary": t.get("summary", "").replace("{customer_name}", customer_name).replace("{deal_id}", deal_id),
                "description": t.get("description", "").replace("{customer_name}", customer_name).replace("{deal_id}", deal_id),
                "issue_type": t.get("issue_type", "Task"),
                "assignee_email": t.get("assignee_email", ""),
            }
        )
    return preview


def create_tickets_for_customer(
    customer_name: str,
    deal_id: str,
    preview: list[dict],
) -> dict:
    """
    Create one Epic per distinct project_key found in preview, then create
    each task under its project's epic.

    Returns:
        {
            "epics": {"DFR": "DFR-12", "LOGO": "LOGO-5"},
            "subtask_keys": ["DFR-13", "DFR-14", "LOGO-6"],
            "errors": ["Task 3: ..."],
        }
    """
    # Gather distinct project keys from the preview
    project_keys = list(dict.fromkeys(t["project_key"] for t in preview))

    epics: dict[str, str] = {}
    subtask_keys: list[str] = []
    errors: list[str] = []

    # Create one epic per project
    for proj in project_keys:
        try:
            epic_key = create_epic(customer_name, deal_id, project_key=proj)
            epics[proj] = epic_key
        except JiraError as e:
            errors.append(f"Epic ({proj}): {e}")

    # Create tasks under their respective epic
    for ticket in preview:
        proj = ticket["project_key"]
        epic_key = epics.get(proj)
        if not epic_key:
            errors.append(f"Task '{ticket['summary']}' skipped — epic for {proj} was not created")
            continue
        try:
            key = create_subtask(
                epic_key=epic_key,
                summary=ticket["summary"],
                description=ticket["description"],
                assignee_email=ticket["assignee_email"] or None,
                project_key=proj,
            )
            subtask_keys.append(key)
        except JiraError as e:
            errors.append(f"Task {ticket['step']} ({proj}): {e}")

    return {"epics": epics, "subtask_keys": subtask_keys, "errors": errors}

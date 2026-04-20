"""
One-time setup script — creates all required Google Sheets tabs with
headers and starter onboarding template rows.

Run once:
    python setup_sheets.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.oauth2.service_account import Credentials
import gspread
from app.config import (
    GOOGLE_SA_JSON_PATH,
    GOOGLE_SHEET_ID,
    SHEET_TAB_CONFIG,
    SHEET_TAB_DASHBOARD,
    SHEET_TAB_AUDIT,
    JIRA_PROJECT_KEY,
)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Tab definitions ───────────────────────────────────────────────────────────

CONFIG_HEADERS = [
    "step_order", "summary", "description",
    "issue_type", "project_key", "assignee_email", "is_active",
]

DASHBOARD_HEADERS = [
    "deal_id", "customer_name", "contact_email", "deal_stage",
    "deal_owner", "epic_key", "epic_status", "tickets_created_at",
    "tickets_created_by", "jira_url", "doc_url",
]

AUDIT_HEADERS = [
    "timestamp", "actor", "action", "deal_id",
    "customer_name", "epic_key", "subtask_keys", "details",
]

STARTER_TEMPLATES = [
    [1, "Kickoff Call — {customer_name}",       "Schedule and conduct initial kickoff call with {customer_name} to align on scope and expectations.",           "Task", JIRA_PROJECT_KEY, "", "TRUE"],
    [2, "Contract & Insurance Review",           "Review signed contract and verify proof of insurance is on file for {customer_name}.",                         "Task", JIRA_PROJECT_KEY, "", "TRUE"],
    [3, "Site Survey Scheduling",                "Coordinate site survey date and logistics with {customer_name}.",                                               "Task", JIRA_PROJECT_KEY, "", "TRUE"],
    [4, "Pilot Assignment & Briefing",           "Assign pilot team and conduct mission briefing for {customer_name} job.",                                       "Task", JIRA_PROJECT_KEY, "", "TRUE"],
    [5, "Equipment Pre-flight Checklist",        "Complete pre-flight equipment inspection and confirm all gear is mission-ready.",                               "Task", JIRA_PROJECT_KEY, "", "TRUE"],
    [6, "Deliverables Handoff",                  "Deliver all final outputs and data to {customer_name} and confirm acceptance.",                                 "Task", JIRA_PROJECT_KEY, "", "TRUE"],
    [7, "Post-Mission Debrief & Invoicing",      "Conduct post-mission debrief with {customer_name} and send final invoice.",                                    "Task", JIRA_PROJECT_KEY, "", "TRUE"],
]


def _get_or_create_worksheet(spreadsheet, title: str, rows=100, cols=20):
    """Return existing worksheet or create it if missing."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def main():
    print("Connecting to Google Sheets...")
    creds = Credentials.from_service_account_file(GOOGLE_SA_JSON_PATH, scopes=_SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    print(f"Connected to: {spreadsheet.title}")

    # ── Onboarding Templates ──────────────────────────────────────────────────
    print(f"\nSetting up '{SHEET_TAB_CONFIG}'...")
    ws_config = _get_or_create_worksheet(spreadsheet, SHEET_TAB_CONFIG)
    existing = ws_config.get_all_values()

    if not existing or existing[0] != CONFIG_HEADERS:
        ws_config.clear()
        ws_config.append_row(CONFIG_HEADERS)
        print("  Headers written.")
    else:
        print("  Headers already present.")

    if len(existing) <= 1:
        for row in STARTER_TEMPLATES:
            ws_config.append_row([str(v) for v in row])
        print(f"  {len(STARTER_TEMPLATES)} starter template rows added.")
    else:
        print(f"  {len(existing) - 1} existing row(s) kept.")

    # ── Dashboard ─────────────────────────────────────────────────────────────
    print(f"\nSetting up '{SHEET_TAB_DASHBOARD}'...")
    ws_dash = _get_or_create_worksheet(spreadsheet, SHEET_TAB_DASHBOARD)
    existing_dash = ws_dash.get_all_values()

    if not existing_dash or existing_dash[0] != DASHBOARD_HEADERS:
        ws_dash.clear()
        ws_dash.append_row(DASHBOARD_HEADERS)
        print("  Headers written.")
    else:
        print("  Headers already present.")

    # ── Audit Log ─────────────────────────────────────────────────────────────
    print(f"\nSetting up '{SHEET_TAB_AUDIT}'...")
    ws_audit = _get_or_create_worksheet(spreadsheet, SHEET_TAB_AUDIT)
    existing_audit = ws_audit.get_all_values()

    if not existing_audit or existing_audit[0] != AUDIT_HEADERS:
        ws_audit.clear()
        ws_audit.append_row(AUDIT_HEADERS)
        print("  Headers written.")
    else:
        print("  Headers already present.")

    print("\nDone! Your Google Sheet is ready.")
    print(f"Open it at: https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit")


if __name__ == "__main__":
    main()

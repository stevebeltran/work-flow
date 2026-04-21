import json
import gspread
from google.oauth2.service_account import Credentials

from app.config import (
    GOOGLE_SA_JSON_PATH,
    GOOGLE_SHEET_ID,
    SHEET_TAB_CONFIG,
    SHEET_TAB_DASHBOARD,
    SHEET_TAB_AUDIT,
)
from app.utils import format_timestamp

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

_client: gspread.Client | None = None
_spreadsheet: gspread.Spreadsheet | None = None


def _get_spreadsheet() -> gspread.Spreadsheet:
    global _client, _spreadsheet
    if _spreadsheet is None:
        print(f"[sheets_client] SA JSON : {GOOGLE_SA_JSON_PATH}")
        print(f"[sheets_client] Sheet ID: {GOOGLE_SHEET_ID}")
        with open(GOOGLE_SA_JSON_PATH) as f:
            sa_email = json.load(f).get("client_email", "unknown")
        print(f"[sheets_client] SA email: {sa_email}")
        creds = Credentials.from_service_account_file(GOOGLE_SA_JSON_PATH, scopes=_SCOPES)
        _client = gspread.authorize(creds)
        _spreadsheet = _client.open_by_key(GOOGLE_SHEET_ID)
    return _spreadsheet


def get_onboarding_templates() -> list[dict]:
    """Return active template rows from the Onboarding Templates tab."""
    sheet = _get_spreadsheet().worksheet(SHEET_TAB_CONFIG)
    rows = sheet.get_all_records()
    return [r for r in rows if str(r.get("is_active", "")).upper() == "TRUE"]


def get_dashboard_rows() -> list[dict]:
    """Return all rows from the Dashboard tab."""
    sheet = _get_spreadsheet().worksheet(SHEET_TAB_DASHBOARD)
    return sheet.get_all_records()


def upsert_dashboard_row(row_data: dict) -> None:
    """Update the row matching deal_id, or append a new row."""
    sheet = _get_spreadsheet().worksheet(SHEET_TAB_DASHBOARD)
    headers = sheet.row_values(1)
    if not headers:
        # Sheet is empty — write headers first
        headers = [
            "deal_id", "customer_name", "contact_email", "deal_stage",
            "deal_owner", "epic_key", "epic_status", "tickets_created_at",
            "tickets_created_by", "jira_url",
        ]
        sheet.append_row(headers)

    deal_id = str(row_data.get("deal_id", ""))
    all_values = sheet.get_all_values()
    # Row 1 is headers, data starts at row 2
    for i, row in enumerate(all_values[1:], start=2):
        if row and row[0] == deal_id:
            new_row = [str(row_data.get(h, "")) for h in headers]
            sheet.update(f"A{i}:{_col_letter(len(headers))}{i}", [new_row])
            return

    # Not found — append
    new_row = [str(row_data.get(h, "")) for h in headers]
    sheet.append_row(new_row)


def append_audit_log(action: str, actor: str, details: dict) -> None:
    """Append a row to the Audit Log tab."""
    sheet = _get_spreadsheet().worksheet(SHEET_TAB_AUDIT)
    row = [
        format_timestamp(),
        actor,
        action,
        str(details.get("deal_id", "")),
        str(details.get("customer_name", "")),
        str(details.get("epic_key", "")),
        str(details.get("subtask_keys", "")),
        json.dumps({k: v for k, v in details.items()
                    if k not in ("deal_id", "customer_name", "epic_key", "subtask_keys")}),
    ]
    sheet.append_row(row)


def _col_letter(n: int) -> str:
    """Convert 1-based column index to letter (e.g. 1→A, 26→Z, 27→AA)."""
    result = ""
    while n:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result

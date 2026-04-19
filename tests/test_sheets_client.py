"""
Tests for sheets_client.py

These tests mock gspread so they can run without real Google credentials.
To run: pytest tests/test_sheets_client.py
"""
import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_mock_spreadsheet(records: list[dict], all_values: list[list]):
    ws = MagicMock()
    ws.get_all_records.return_value = records
    ws.get_all_values.return_value = all_values
    ws.row_values.return_value = list(records[0].keys()) if records else []

    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value = ws
    return spreadsheet, ws


# ── Tests ─────────────────────────────────────────────────────────────────────

@patch("app.sheets_client._get_spreadsheet")
def test_get_onboarding_templates_filters_inactive(mock_get):
    records = [
        {"step_order": 1, "summary": "Kickoff", "is_active": "TRUE"},
        {"step_order": 2, "summary": "Review", "is_active": "FALSE"},
        {"step_order": 3, "summary": "Handoff", "is_active": "true"},
    ]
    spreadsheet, _ = _make_mock_spreadsheet(records, [])
    mock_get.return_value = spreadsheet

    from app.sheets_client import get_onboarding_templates
    result = get_onboarding_templates()

    assert len(result) == 2
    assert all(r["is_active"].upper() == "TRUE" for r in result)


@patch("app.sheets_client._get_spreadsheet")
def test_append_audit_log_appends_row(mock_get):
    spreadsheet, ws = _make_mock_spreadsheet([], [])
    mock_get.return_value = spreadsheet

    from app.sheets_client import append_audit_log
    append_audit_log(
        action="TICKETS_CREATED",
        actor="test@brincdrones.com",
        details={"deal_id": "123", "customer_name": "Acme", "epic_key": "OB-1", "subtask_keys": "OB-2,OB-3"},
    )

    ws.append_row.assert_called_once()
    row = ws.append_row.call_args[0][0]
    assert "TICKETS_CREATED" in row
    assert "test@brincdrones.com" in row


@patch("app.sheets_client._get_spreadsheet")
def test_upsert_dashboard_row_appends_when_not_found(mock_get):
    headers = ["deal_id", "customer_name", "contact_email", "deal_stage",
               "deal_owner", "epic_key", "epic_status", "tickets_created_at",
               "tickets_created_by", "jira_url"]
    spreadsheet, ws = _make_mock_spreadsheet([], [headers])
    ws.row_values.return_value = headers
    mock_get.return_value = spreadsheet

    from app.sheets_client import upsert_dashboard_row
    upsert_dashboard_row({
        "deal_id": "999",
        "customer_name": "New Customer",
        "epic_key": "OB-10",
    })

    ws.append_row.assert_called_once()

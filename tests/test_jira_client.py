"""
Tests for jira_client.py

These tests mock requests so they can run without real Jira credentials.
To run: pytest tests/test_jira_client.py
"""
import pytest
from unittest.mock import MagicMock, patch


@patch("app.jira_client.requests.post")
def test_create_epic_returns_key(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"key": "OB-42"}
    mock_post.return_value = mock_resp

    from app.jira_client import create_epic
    key = create_epic("Acme Drones", "deal_123")
    assert key == "OB-42"
    mock_post.assert_called_once()


@patch("app.jira_client.requests.post")
def test_create_epic_raises_on_error(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 403
    mock_resp.json.return_value = {"errorMessages": ["Unauthorized"]}
    mock_post.return_value = mock_resp

    from app.jira_client import create_epic, JiraError
    with pytest.raises(JiraError, match="403"):
        create_epic("Acme", "deal_1")


def test_build_tickets_preview_substitutes_tokens():
    from app.jira_client import build_tickets_preview

    templates = [
        {
            "step_order": 1,
            "summary": "Kickoff — {customer_name}",
            "description": "Call with {customer_name} (Deal {deal_id})",
            "issue_type": "Task",
            "assignee_email": "ops@brincdrones.com",
            "is_active": "TRUE",
        }
    ]
    preview = build_tickets_preview(templates, customer_name="Acme Corp", deal_id="D-99")
    assert preview[0]["summary"] == "Kickoff — Acme Corp"
    assert "Acme Corp" in preview[0]["description"]
    assert "D-99" in preview[0]["description"]


def test_build_tickets_preview_sorts_by_step_order():
    from app.jira_client import build_tickets_preview

    templates = [
        {"step_order": 3, "summary": "Step 3", "description": "", "issue_type": "Task", "assignee_email": ""},
        {"step_order": 1, "summary": "Step 1", "description": "", "issue_type": "Task", "assignee_email": ""},
        {"step_order": 2, "summary": "Step 2", "description": "", "issue_type": "Task", "assignee_email": ""},
    ]
    preview = build_tickets_preview(templates, "Customer")
    assert [p["step"] for p in preview] == [1, 2, 3]

"""
Google Docs integration — copies a template doc and fills in placeholders.

Uses the same service account JSON as sheets_client.py.
The service account must have Editor access on the template doc.

Supported placeholders in the template doc (any text in the body):
    {customer_name}   — deal name from HubSpot
    {deal_id}         — HubSpot deal ID
    {contact_name}    — contact full name
    {contact_email}   — contact email
    {deal_stage}      — HubSpot deal stage
    {date}            — today's date (YYYY-MM-DD)
    {epic_keys}       — comma-separated Jira epic keys e.g. DFR-12, LOGO-5
"""
from datetime import date

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.config import GOOGLE_SA_JSON_PATH, GOOGLE_DOC_TEMPLATE_ID

_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

_drive_service = None
_docs_service = None


def _get_services():
    global _drive_service, _docs_service
    if _drive_service is None:
        creds = Credentials.from_service_account_file(GOOGLE_SA_JSON_PATH, scopes=_SCOPES)
        _drive_service = build("drive", "v3", credentials=creds)
        _docs_service = build("docs", "v1", credentials=creds)
    return _drive_service, _docs_service


def create_customer_doc(
    customer_name: str,
    deal_id: str = "",
    contact_name: str = "",
    contact_email: str = "",
    deal_stage: str = "",
    epic_keys: str = "",
) -> str:
    """
    Copy the template doc, rename it, substitute all placeholders,
    and return the URL of the new document.
    """
    if not GOOGLE_DOC_TEMPLATE_ID:
        raise ValueError("GOOGLE_DOC_TEMPLATE_ID is not set in .env")

    drive, docs = _get_services()

    # 1. Copy the template
    copy_title = f"Onboarding — {customer_name}"
    copied = drive.files().copy(
        fileId=GOOGLE_DOC_TEMPLATE_ID,
        body={"name": copy_title},
    ).execute()
    new_doc_id = copied["id"]

    # 2. Build replacement map
    today = date.today().isoformat()
    replacements = {
        "{customer_name}": customer_name,
        "{deal_id}": deal_id,
        "{contact_name}": contact_name,
        "{contact_email}": contact_email,
        "{deal_stage}": deal_stage,
        "{date}": today,
        "{epic_keys}": epic_keys,
    }

    # 3. Replace all placeholders in one batchUpdate call
    requests_body = [
        {
            "replaceAllText": {
                "containsText": {"text": placeholder, "matchCase": True},
                "replaceText": value,
            }
        }
        for placeholder, value in replacements.items()
    ]
    docs.documents().batchUpdate(
        documentId=new_doc_id,
        body={"requests": requests_body},
    ).execute()

    return f"https://docs.google.com/document/d/{new_doc_id}/edit"


def get_doc_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/edit"

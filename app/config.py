import os
from dotenv import load_dotenv

load_dotenv()

_REQUIRED = [
    "HUBSPOT_PRIVATE_APP_TOKEN",
    "JIRA_BASE_URL",
    "JIRA_USER_EMAIL",
    "JIRA_API_TOKEN",
    "JIRA_PROJECT_KEY",
    "GOOGLE_SHEET_ID",
    "GOOGLE_SA_JSON_PATH",
]

_missing = [k for k in _REQUIRED if not os.getenv(k)]
if _missing:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(_missing)}\n"
        "Copy .env.example to .env and fill in your credentials."
    )

HUBSPOT_TOKEN: str = os.environ["HUBSPOT_PRIVATE_APP_TOKEN"]
JIRA_BASE_URL: str = os.environ["JIRA_BASE_URL"].rstrip("/")
JIRA_USER_EMAIL: str = os.environ["JIRA_USER_EMAIL"]
JIRA_API_TOKEN: str = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY: str = os.environ["JIRA_PROJECT_KEY"]
GOOGLE_SHEET_ID: str = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_SA_JSON_PATH: str = os.environ["GOOGLE_SA_JSON_PATH"]

# Google Sheets tab names
SHEET_TAB_CONFIG = "Onboarding Templates"
SHEET_TAB_DASHBOARD = "Dashboard"
SHEET_TAB_AUDIT = "Audit Log"

import os
import ssl
import certifi
from dotenv import load_dotenv

# Fix SSL certificate verification on Windows with Python 3.12
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
ssl.create_default_context = lambda *a, **kw: ssl.create_default_context(
    *a, cafile=certifi.where(), **kw
)

# Always resolve paths relative to the project root (where .env lives)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)

# These are always required
_REQUIRED = [
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

# Optional — app falls back to CSV upload if not set
HUBSPOT_TOKEN: str | None = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN") or None

JIRA_BASE_URL: str = os.environ["JIRA_BASE_URL"].rstrip("/")
JIRA_USER_EMAIL: str = os.environ["JIRA_USER_EMAIL"]
JIRA_API_TOKEN: str = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY: str = os.environ["JIRA_PROJECT_KEY"]
GOOGLE_SHEET_ID: str = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_SA_JSON_PATH: str = os.path.join(_PROJECT_ROOT, os.environ["GOOGLE_SA_JSON_PATH"])

# Optional — Google Doc template to copy per customer
GOOGLE_DOC_TEMPLATE_ID: str | None = os.getenv("GOOGLE_DOC_TEMPLATE_ID") or None

# Optional — email notifications sent only when all three are set
NOTIFY_EMAIL_SENDER: str | None = os.getenv("NOTIFY_EMAIL_SENDER") or None
NOTIFY_EMAIL_PASSWORD: str | None = os.getenv("NOTIFY_EMAIL_PASSWORD") or None
NOTIFY_EMAIL_TO: str | None = os.getenv("NOTIFY_EMAIL_TO") or None
NOTIFY_EMAIL_SMTP_HOST: str = os.getenv("NOTIFY_EMAIL_SMTP_HOST", "smtp.gmail.com")
NOTIFY_EMAIL_SMTP_PORT: int = int(os.getenv("NOTIFY_EMAIL_SMTP_PORT", "587"))

# Google Sheets tab names
SHEET_TAB_CONFIG = "Onboarding Templates"
SHEET_TAB_DASHBOARD = "Dashboard"
SHEET_TAB_AUDIT = "Audit Log"

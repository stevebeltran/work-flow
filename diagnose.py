"""Quick diagnostic — run this to find the exact connection issue."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("1. Loading config...")
from app.config import GOOGLE_SA_JSON_PATH, GOOGLE_SHEET_ID, SHEET_TAB_CONFIG
print(f"   SA JSON path : {GOOGLE_SA_JSON_PATH}")
print(f"   Sheet ID     : {GOOGLE_SHEET_ID}")
print(f"   Tab name     : {SHEET_TAB_CONFIG}")

print("\n2. Checking JSON file exists...")
if os.path.exists(GOOGLE_SA_JSON_PATH):
    print(f"   FOUND: {GOOGLE_SA_JSON_PATH}")
else:
    print(f"   NOT FOUND: {GOOGLE_SA_JSON_PATH}")
    sys.exit(1)

print("\n3. Authenticating with Google...")
from google.oauth2.service_account import Credentials
import gspread
creds = Credentials.from_service_account_file(
    GOOGLE_SA_JSON_PATH,
    scopes=["https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly"],
)
client = gspread.authorize(creds)
print("   Auth OK")

print("\n4. Opening spreadsheet...")
spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
print(f"   Opened: {spreadsheet.title}")

print("\n5. Listing tabs...")
for ws in spreadsheet.worksheets():
    print(f"   - '{ws.title}'")

print("\n6. Reading Onboarding Templates...")
ws = spreadsheet.worksheet(SHEET_TAB_CONFIG)
rows = ws.get_all_records()
print(f"   {len(rows)} row(s) found")
for r in rows[:3]:
    print(f"   {r}")

print("\nAll checks passed!")

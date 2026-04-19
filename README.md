# Brinc Drones — Customer Workflow App

A Streamlit app that bridges HubSpot (sales) and Jira (delivery) for drone services customer onboarding.

**What it does:**
1. Search and select a HubSpot deal from inside the app
2. Preview the onboarding Jira tickets that will be created (configurable via Google Sheets)
3. Create a Jira Epic + subtasks with one click
4. Track all customers, deal stages, and Jira epic statuses in a live Google Sheets dashboard

---

## Prerequisites

- Python 3.11+
- A HubSpot account with Private App access
- A Jira Cloud account with a project for onboarding
- A Google Cloud service account with Sheets + Drive access
- Git

---

## Setup

### 1. Clone and install

```bash
git clone <your-github-repo-url>
cd work-flow
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in all values. See credential setup steps below.

### 3. Place Google Service Account JSON

Copy your service account JSON to:
```
credentials/google_service_account.json
```

This path is in `.gitignore` and will never be committed.

### 4. Set up Google Sheets

Create a new Google Sheet and share it with the `client_email` from your service account JSON (Editor access).

Copy the Sheet ID from the URL:
```
https://docs.google.com/spreadsheets/d/<<SHEET_ID>>/edit
```

Add it to `.env` as `GOOGLE_SHEET_ID`.

Create these three tabs with the exact names and headers shown:

**Tab: `Onboarding Templates`**
```
step_order | summary | description | issue_type | assignee_email | is_active
```

Starter rows for drone services onboarding:
| step_order | summary | description | issue_type | assignee_email | is_active |
|---|---|---|---|---|---|
| 1 | Kickoff Call — {customer_name} | Schedule and conduct kickoff call with {customer_name} | Task | ops@brincdrones.com | TRUE |
| 2 | Contract & Insurance Review | Review signed contract and proof of insurance | Task | ops@brincdrones.com | TRUE |
| 3 | Site Survey Scheduling | Coordinate site survey date with {customer_name} | Task | pilots@brincdrones.com | TRUE |
| 4 | Pilot Assignment & Briefing | Assign and brief the pilot team | Task | pilots@brincdrones.com | TRUE |
| 5 | Equipment Pre-flight Checklist | Complete pre-flight equipment inspection | Task | pilots@brincdrones.com | TRUE |
| 6 | Deliverables Handoff | Deliver final outputs to {customer_name} | Task | ops@brincdrones.com | TRUE |
| 7 | Post-Mission Debrief & Invoicing | Conduct debrief and send final invoice | Task | ops@brincdrones.com | TRUE |

Set `is_active = FALSE` on any row to skip that step without deleting it.

**Tab: `Dashboard`**
```
deal_id | customer_name | contact_email | deal_stage | deal_owner | epic_key | epic_status | tickets_created_at | tickets_created_by | jira_url
```

**Tab: `Audit Log`**
```
timestamp | actor | action | deal_id | customer_name | epic_key | subtask_keys | details
```

---

## Credential Setup

### HubSpot Private App Token

1. Go to `app.hubspot.com` → top-right avatar → **Account Settings**
2. Navigate to **Integrations → Private Apps**
3. Click **Create a private app**
4. Name: `Brinc Workflow App`
5. Scopes needed:
   - `crm.objects.deals.read`
   - `crm.objects.contacts.read`
   - `crm.objects.owners.read`
6. Click **Create app** → copy the token (starts with `pat-na1-...`)
7. Add to `.env` as `HUBSPOT_PRIVATE_APP_TOKEN`

### Jira Cloud API Token

1. Go to `id.atlassian.com/manage-profile/security/api-tokens`
2. Click **Create API token** → label: `Brinc Workflow App`
3. Copy the token immediately (shown once only)
4. Add to `.env`:
   - `JIRA_USER_EMAIL` — your Atlassian account email
   - `JIRA_API_TOKEN` — the token you just copied
   - `JIRA_BASE_URL` — e.g. `https://brincdrones.atlassian.net`
   - `JIRA_PROJECT_KEY` — the prefix before the dash in your Jira issue keys (e.g. `OB`)
5. Verify your user has **Create Issues** permission in the target project

To find your project key: open any Jira issue — the prefix before the `-` (e.g. `OB` in `OB-12`) is the key.

---

## Running the App

```bash
streamlit run app/main.py
```

The app opens at `http://localhost:8501`.

---

## Running Tests

```bash
pytest tests/
```

Tests mock all external APIs and do not require real credentials.

---

## GitHub Setup

```bash
git init                          # already done if you cloned
git remote add origin <your-github-repo-url>
git add .
git commit -m "Initial commit: HubSpot → Jira → Sheets workflow app"
git push -u origin main
```

**Important:** `.env` and `credentials/` are in `.gitignore`. Never commit them.

---

## Project Structure

```
work-flow/
├── app/
│   ├── main.py            # Streamlit UI
│   ├── config.py          # Environment variable loading
│   ├── hubspot_client.py  # HubSpot API wrapper
│   ├── jira_client.py     # Jira REST API v3 wrapper
│   ├── sheets_client.py   # Google Sheets (gspread) wrapper
│   └── utils.py           # Shared helpers
├── tests/
│   ├── test_hubspot_client.py
│   ├── test_jira_client.py
│   └── test_sheets_client.py
├── credentials/           # gitignored — place SA JSON here
├── .env                   # gitignored — your secrets
├── .env.example           # committed — template for secrets
├── requirements.txt
└── README.md
```

---

## Adding or Changing Onboarding Steps

No code changes needed. Just edit the `Onboarding Templates` tab in Google Sheets:
- Change `is_active` to `FALSE` to disable a step
- Add a new row with the next `step_order` to add a step
- Use `{customer_name}` and `{deal_id}` as substitution tokens in summary/description

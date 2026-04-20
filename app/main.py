import streamlit as st
import pandas as pd

import app.hubspot_client as hs
import app.jira_client as jira
import app.sheets_client as sheets
import app.slack_client as slack
from app.config import JIRA_BASE_URL, HUBSPOT_TOKEN, SLACK_WEBHOOK_URL
from app.utils import format_timestamp

st.set_page_config(
    page_title="Brinc Drones — Customer Workflow",
    page_icon="🚁",
    layout="wide",
)

st.title("🚁 Brinc Drones Customer Workflow")

# ── Sidebar status indicators ─────────────────────────────────────────────────
with st.sidebar:
    st.header("Integration Status")
    st.write("**HubSpot**", ":white_check_mark: API" if HUBSPOT_TOKEN else ":file_folder: CSV mode")
    st.write("**Jira**", ":white_check_mark: Connected")
    st.write("**Google Sheets**", ":white_check_mark: Connected")
    st.write("**Slack**", ":white_check_mark: Enabled" if SLACK_WEBHOOK_URL else ":mute: Disabled")
    st.divider()
    st.caption("Set SLACK_WEBHOOK_URL in .env to enable Slack notifications.")
    if not HUBSPOT_TOKEN:
        st.caption("Set HUBSPOT_PRIVATE_APP_TOKEN in .env to enable live HubSpot search.")


tab_onboard, tab_dashboard = st.tabs(["Onboard Customer", "Dashboard"])


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper: ticket creation + post-processing
# Called the same way regardless of whether deal came from API or CSV
# ─────────────────────────────────────────────────────────────────────────────
def run_ticket_creation(deal: dict, actor_email: str) -> None:
    templates = st.session_state.get("_templates", [])
    if not templates:
        st.warning("No active templates loaded. Cannot create tickets.")
        return

    preview = jira.build_tickets_preview(
        templates,
        customer_name=deal["deal_name"],
        deal_id=deal["deal_id"],
    )

    epic_key = None
    subtask_keys: list[str] = []
    errors: list[str] = []
    total_steps = 1 + len(preview)
    progress = st.progress(0, text="Starting...")

    with st.status("Creating Jira tickets...", expanded=True) as status_box:
        st.write(f"Creating Epic for **{deal['deal_name']}**...")
        try:
            epic_key = jira.create_epic(
                customer_name=deal["deal_name"],
                deal_id=deal["deal_id"],
            )
            st.write(f"Epic created: `{epic_key}`")
            progress.progress(1 / total_steps, text=f"Epic {epic_key} created")
        except jira.JiraError as e:
            errors.append(str(e))
            st.error(f"Epic creation failed: {e}")

        if epic_key:
            for i, ticket in enumerate(preview, start=1):
                st.write(f"Creating task: _{ticket['summary']}_")
                try:
                    key = jira.create_subtask(
                        epic_key=epic_key,
                        summary=ticket["summary"],
                        description=ticket["description"],
                        assignee_email=ticket["assignee_email"] or None,
                    )
                    subtask_keys.append(key)
                    progress.progress((1 + i) / total_steps, text=f"Created {key}")
                except jira.JiraError as e:
                    errors.append(f"Task {ticket['step']}: {e}")
                    st.warning(f"Task {ticket['step']} failed: {e}")

        if errors and not epic_key:
            status_box.update(label="Failed — no tickets created", state="error")
        elif errors:
            status_box.update(
                label=f"Partial — {len(subtask_keys)}/{len(preview)} tasks created",
                state="error",
            )
        else:
            status_box.update(label="All tickets created!", state="complete")

    progress.empty()

    if epic_key:
        jira_url = f"{JIRA_BASE_URL}/browse/{epic_key}"
        st.success(
            f"Epic **[{epic_key}]({jira_url})** created with {len(subtask_keys)} task(s).  \n"
            f"Subtasks: {', '.join(subtask_keys) or 'none'}"
        )

        # Google Sheets
        try:
            sheets.upsert_dashboard_row({
                "deal_id": deal["deal_id"],
                "customer_name": deal["deal_name"],
                "contact_email": deal.get("contact_email", ""),
                "deal_stage": deal.get("deal_stage", ""),
                "deal_owner": deal.get("owner_id", ""),
                "epic_key": epic_key,
                "epic_status": "To Do",
                "tickets_created_at": format_timestamp(),
                "tickets_created_by": actor_email,
                "jira_url": jira_url,
            })
            sheets.append_audit_log(
                action="TICKETS_CREATED",
                actor=actor_email,
                details={
                    "deal_id": deal["deal_id"],
                    "customer_name": deal["deal_name"],
                    "epic_key": epic_key,
                    "subtask_keys": ", ".join(subtask_keys),
                },
            )
            st.caption("Dashboard and audit log updated in Google Sheets.")
        except Exception as e:
            st.warning(f"Sheets update failed (tickets were still created in Jira): {e}")

        # Slack
        try:
            slack.send_onboarding_notification(
                customer_name=deal["deal_name"],
                epic_key=epic_key,
                jira_url=jira_url,
                subtask_keys=subtask_keys,
                actor_email=actor_email,
            )
            if SLACK_WEBHOOK_URL:
                st.caption("Slack notification sent.")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Onboard Customer
# ─────────────────────────────────────────────────────────────────────────────
with tab_onboard:
    st.header("Onboard a New Customer")

    # ── Section 1: Find a deal (API or CSV) ──────────────────────────────────
    st.subheader("1. Find a HubSpot Deal")

    if HUBSPOT_TOKEN:
        input_mode = st.radio(
            "Source",
            ["Search HubSpot API", "Upload CSV export"],
            horizontal=True,
            label_visibility="collapsed",
        )
    else:
        st.info(
            "HubSpot API token not configured. Using CSV upload mode.  \n"
            "Export your deals from HubSpot: **CRM → Deals → Actions → Export**"
        )
        input_mode = "Upload CSV export"

    # ── API search ────────────────────────────────────────────────────────────
    if input_mode == "Search HubSpot API":
        col_search, col_btn = st.columns([4, 1])
        with col_search:
            query = st.text_input("Search by deal name", placeholder="e.g. Acme Corp")
        with col_btn:
            st.write("")
            do_search = st.button("Search", use_container_width=True)

        if do_search and query:
            with st.spinner("Searching HubSpot..."):
                try:
                    results = hs.search_deals(query)
                    st.session_state["search_results"] = results
                    st.session_state["selected_deal"] = None
                except hs.HubSpotError as e:
                    st.error(f"HubSpot error: {e}")
                    st.session_state["search_results"] = []

        if st.session_state.get("search_results"):
            results = st.session_state["search_results"]
            df_res = pd.DataFrame(results)[["deal_name", "deal_stage", "contact_name", "contact_email"]]
            df_res.columns = ["Deal Name", "Stage", "Contact", "Email"]
            st.dataframe(df_res, use_container_width=True, hide_index=True)

            deal_options = {f"{r['deal_name']} ({r['deal_id']})": r for r in results}
            selected_label = st.selectbox("Select deal to onboard", list(deal_options.keys()))
            st.session_state["selected_deal"] = deal_options[selected_label]
        elif do_search and query:
            st.info("No deals found. Try a different search term.")

    # ── CSV upload ────────────────────────────────────────────────────────────
    else:
        uploaded = st.file_uploader(
            "Upload HubSpot deals export (.csv)",
            type=["csv"],
            help="In HubSpot: CRM → Deals → Actions → Export → select fields → download CSV",
        )

        if uploaded:
            with st.spinner("Parsing CSV..."):
                try:
                    raw_deals = hs.parse_deals_csv(uploaded.read())
                    st.session_state["csv_deals"] = raw_deals
                    st.session_state["selected_deal"] = None
                    st.success(f"Loaded {len(raw_deals)} deal(s) from CSV.")
                except Exception as e:
                    st.error(f"Could not parse CSV: {e}")
                    st.session_state["csv_deals"] = []

        if st.session_state.get("csv_deals"):
            csv_deals = st.session_state["csv_deals"]

            col_filter, _ = st.columns([3, 3])
            with col_filter:
                filter_query = st.text_input("Filter by name", placeholder="e.g. Acme")

            filtered = hs.search_deals_csv(filter_query, csv_deals) if filter_query else csv_deals

            if filtered:
                df_csv = pd.DataFrame(filtered)[["deal_name", "deal_stage", "contact_name", "contact_email"]]
                df_csv.columns = ["Deal Name", "Stage", "Contact", "Email"]
                st.dataframe(df_csv, use_container_width=True, hide_index=True)

                deal_options = {f"{r['deal_name']} ({r['deal_id']})": r for r in filtered}
                selected_label = st.selectbox("Select deal to onboard", list(deal_options.keys()))
                st.session_state["selected_deal"] = deal_options[selected_label]
            else:
                st.info("No matching deals.")

    # ── Section 2: Deal summary + ticket preview ──────────────────────────────
    deal = st.session_state.get("selected_deal")
    if deal:
        st.divider()
        st.subheader("2. Deal Summary")
        st.info(
            f"**{deal['deal_name']}**  \n"
            f"Contact: {deal.get('contact_name') or '—'} ({deal.get('contact_email') or '—'})  \n"
            f"Stage: `{deal.get('deal_stage') or '—'}`"
        )

        st.subheader("3. Onboarding Ticket Preview")
        with st.spinner("Loading templates from Google Sheets..."):
            try:
                templates = sheets.get_onboarding_templates()
                st.session_state["_templates"] = templates
            except Exception as e:
                st.error(f"Could not load templates from Google Sheets: {e}")
                templates = []
                st.session_state["_templates"] = []

        if not templates:
            st.warning(
                "No active templates found. "
                f"Add rows to the '{sheets.SHEET_TAB_CONFIG}' tab with `is_active = TRUE`."
            )
        else:
            preview = jira.build_tickets_preview(
                templates,
                customer_name=deal["deal_name"],
                deal_id=deal["deal_id"],
            )
            preview_df = pd.DataFrame(preview)[["step", "summary", "assignee_email"]]
            preview_df.columns = ["Step", "Ticket Summary", "Assignee"]
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

            with st.expander("View full descriptions"):
                for p in preview:
                    st.markdown(f"**{p['step']}. {p['summary']}**")
                    st.caption(p["description"] or "_No description_")
                    st.divider()

            # ── Section 3: Trigger ────────────────────────────────────────────
            st.subheader("4. Create Jira Tickets")
            actor_email = st.text_input(
                "Your email (for audit log)",
                value="",
                placeholder="you@brincdrones.com",
            )
            trigger = st.button("Create Jira Tickets", type="primary")

            if trigger:
                if not actor_email:
                    st.warning("Please enter your email before creating tickets.")
                else:
                    run_ticket_creation(deal, actor_email)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Dashboard
# ─────────────────────────────────────────────────────────────────────────────
with tab_dashboard:
    st.header("Onboarding Dashboard")

    col_refresh, col_ts = st.columns([2, 5])
    with col_refresh:
        do_refresh = st.button("Refresh from Jira", use_container_width=True)

    if do_refresh:
        with st.spinner("Refreshing statuses..."):
            try:
                rows = sheets.get_dashboard_rows()
                updated = 0
                for row in rows:
                    epic_key = row.get("epic_key", "").strip()
                    customer = row.get("customer_name", "")
                    jira_url = row.get("jira_url", "")
                    if epic_key:
                        try:
                            old_status = row.get("epic_status", "")
                            new_status = jira.get_issue_status(epic_key)
                            row["epic_status"] = new_status
                            sheets.upsert_dashboard_row(row)
                            updated += 1
                            # Notify Slack if status changed
                            if old_status != new_status:
                                slack.send_status_change_notification(
                                    customer_name=customer,
                                    epic_key=epic_key,
                                    jira_url=jira_url,
                                    new_status=new_status,
                                )
                        except jira.JiraError:
                            pass
                sheets.append_audit_log(
                    action="DASHBOARD_REFRESHED",
                    actor="system",
                    details={"rows_refreshed": str(updated)},
                )
                st.session_state["dashboard_rows"] = rows
                with col_ts:
                    st.caption(f"Last refreshed: {format_timestamp()} UTC — {updated} epic(s) updated")
            except Exception as e:
                st.error(f"Refresh failed: {e}")

    if "dashboard_rows" not in st.session_state or do_refresh:
        try:
            st.session_state["dashboard_rows"] = sheets.get_dashboard_rows()
        except Exception as e:
            st.error(f"Could not load dashboard: {e}")
            st.session_state["dashboard_rows"] = []

    rows = st.session_state.get("dashboard_rows", [])

    if rows:
        df = pd.DataFrame(rows)

        total = len(df)
        done_epics = len(df[df.get("epic_status", pd.Series(dtype=str)).str.lower() == "done"])
        open_epics = total - done_epics

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Customers Onboarded", total)
        m2.metric("Open Epics", open_epics)
        m3.metric("Completed Epics", done_epics)

        st.divider()

        display_cols = [c for c in [
            "customer_name", "contact_email", "deal_stage",
            "epic_key", "epic_status", "tickets_created_at", "tickets_created_by", "jira_url",
        ] if c in df.columns]

        column_config = {}
        if "jira_url" in df.columns:
            column_config["jira_url"] = st.column_config.LinkColumn("Jira Link", display_text="Open in Jira")
        if "customer_name" in df.columns:
            column_config["customer_name"] = st.column_config.TextColumn("Customer")
        if "epic_key" in df.columns:
            column_config["epic_key"] = st.column_config.TextColumn("Epic")
        if "epic_status" in df.columns:
            column_config["epic_status"] = st.column_config.TextColumn("Status")

        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
        )
    else:
        st.info("No customers onboarded yet. Use the 'Onboard Customer' tab to get started.")

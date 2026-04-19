import streamlit as st
import pandas as pd

import app.hubspot_client as hs
import app.jira_client as jira
import app.sheets_client as sheets
from app.config import JIRA_BASE_URL, JIRA_PROJECT_KEY
from app.utils import format_timestamp

st.set_page_config(
    page_title="Brinc Drones — Customer Workflow",
    page_icon="🚁",
    layout="wide",
)

st.title("🚁 Brinc Drones Customer Workflow")

# Cache API clients across reruns
@st.cache_resource
def get_sheets():
    sheets._get_spreadsheet()  # warm up connection
    return sheets

@st.cache_resource
def get_hs():
    hs._get_client()
    return hs


tab_onboard, tab_dashboard = st.tabs(["Onboard Customer", "Dashboard"])


# ──────────────────────────────────────────────
# TAB 1: Onboard Customer
# ──────────────────────────────────────────────
with tab_onboard:
    st.header("Onboard a New Customer")

    # ── Section 1: Search HubSpot ──
    st.subheader("1. Find a HubSpot Deal")
    col_search, col_btn = st.columns([4, 1])
    with col_search:
        query = st.text_input("Search by deal name", placeholder="e.g. Acme Corp")
    with col_btn:
        st.write("")  # vertical alignment spacer
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
        df = pd.DataFrame(results)[["deal_name", "deal_stage", "owner_id", "contact_name", "contact_email"]]
        df.columns = ["Deal Name", "Stage", "Owner ID", "Contact", "Email"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        deal_options = {f"{r['deal_name']} ({r['deal_id']})": r for r in results}
        selected_label = st.selectbox("Select deal to onboard", list(deal_options.keys()))
        st.session_state["selected_deal"] = deal_options[selected_label]

    elif do_search and query:
        st.info("No deals found. Try a different search term.")

    # ── Section 2: Deal Summary + Ticket Preview ──
    deal = st.session_state.get("selected_deal")
    if deal:
        st.divider()
        st.subheader("2. Deal Summary")
        st.info(
            f"**{deal['deal_name']}**  \n"
            f"Contact: {deal['contact_name'] or '—'} ({deal['contact_email'] or '—'})  \n"
            f"Stage: `{deal['deal_stage']}`"
        )

        st.subheader("3. Onboarding Ticket Preview")
        with st.spinner("Loading templates from Google Sheets..."):
            try:
                templates = sheets.get_onboarding_templates()
            except Exception as e:
                st.error(f"Could not load templates from Google Sheets: {e}")
                templates = []

        if not templates:
            st.warning(
                "No active templates found in Google Sheets. "
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

            # ── Section 3: Trigger ──
            st.subheader("4. Create Jira Tickets")
            actor_email = st.text_input(
                "Your email (for audit log)",
                value="",
                placeholder="you@brincdrones.com",
            )
            trigger = st.button("Create Jira Tickets", type="primary", use_container_width=False)

            if trigger:
                if not actor_email:
                    st.warning("Please enter your email before creating tickets.")
                else:
                    epic_key = None
                    subtask_keys = []
                    errors = []

                    progress = st.progress(0, text="Starting...")
                    total_steps = 1 + len(preview)  # 1 for epic + N subtasks

                    with st.status("Creating Jira tickets...", expanded=True) as status_box:
                        # Create Epic
                        st.write(f"Creating Epic for **{deal['deal_name']}**...")
                        try:
                            epic_key = jira.create_epic(
                                customer_name=deal["deal_name"],
                                deal_id=deal["deal_id"],
                            )
                            st.write(f"Epic created: `{epic_key}`")
                            progress.progress(1 / total_steps, text=f"Epic {epic_key} created")
                        except jira.JiraError as e:
                            errors.append(f"Epic creation failed: {e}")
                            st.error(f"Epic creation failed: {e}")

                        # Create subtasks
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
                                    errors.append(f"Task {ticket['step']} failed: {e}")
                                    st.warning(f"Task {ticket['step']} failed: {e}")

                        if errors and not epic_key:
                            status_box.update(label="Failed — no tickets created", state="error")
                        elif errors:
                            status_box.update(
                                label=f"Partial success — {len(subtask_keys)}/{len(preview)} tasks created",
                                state="error",
                            )
                        else:
                            status_box.update(label="All tickets created!", state="complete")

                    progress.empty()

                    if epic_key:
                        jira_url = f"{JIRA_BASE_URL}/browse/{epic_key}"
                        st.success(
                            f"Epic **[{epic_key}]({jira_url})** created with "
                            f"{len(subtask_keys)} task(s).  \n"
                            f"Subtasks: {', '.join(subtask_keys) or 'none'}"
                        )

                        # Write to Google Sheets
                        try:
                            sheets.upsert_dashboard_row(
                                {
                                    "deal_id": deal["deal_id"],
                                    "customer_name": deal["deal_name"],
                                    "contact_email": deal["contact_email"],
                                    "deal_stage": deal["deal_stage"],
                                    "deal_owner": deal.get("owner_id", ""),
                                    "epic_key": epic_key,
                                    "epic_status": "To Do",
                                    "tickets_created_at": format_timestamp(),
                                    "tickets_created_by": actor_email,
                                    "jira_url": jira_url,
                                }
                            )
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
                            st.warning(f"Tickets created in Jira, but Sheets update failed: {e}")


# ──────────────────────────────────────────────
# TAB 2: Dashboard
# ──────────────────────────────────────────────
with tab_dashboard:
    st.header("Onboarding Dashboard")

    col_refresh, col_ts = st.columns([2, 5])
    with col_refresh:
        do_refresh = st.button("Refresh from Jira + HubSpot", use_container_width=True)

    if do_refresh:
        with st.spinner("Refreshing statuses..."):
            try:
                rows = sheets.get_dashboard_rows()
                updated = 0
                for row in rows:
                    epic_key = row.get("epic_key", "").strip()
                    if epic_key:
                        try:
                            status = jira.get_issue_status(epic_key)
                            row["epic_status"] = status
                            sheets.upsert_dashboard_row(row)
                            updated += 1
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

    # Load rows on first render or after refresh
    if "dashboard_rows" not in st.session_state or do_refresh:
        try:
            st.session_state["dashboard_rows"] = sheets.get_dashboard_rows()
        except Exception as e:
            st.error(f"Could not load dashboard from Google Sheets: {e}")
            st.session_state["dashboard_rows"] = []

    rows = st.session_state.get("dashboard_rows", [])

    if rows:
        df = pd.DataFrame(rows)

        # Metric cards
        total = len(df)
        open_epics = len(df[df.get("epic_status", pd.Series(dtype=str)).str.lower() != "done"])
        done_epics = total - open_epics

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Customers Onboarded", total)
        m2.metric("Open Epics", open_epics)
        m3.metric("Completed Epics", done_epics)

        st.divider()

        # Display columns — show jira_url as a clickable link
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

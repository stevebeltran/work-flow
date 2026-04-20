import io
import pandas as pd
from hubspot import Client
from hubspot.crm.deals import ApiException

from app.config import HUBSPOT_TOKEN


class HubSpotError(Exception):
    pass


_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client.create(access_token=HUBSPOT_TOKEN)
    return _client


def _extract_deal(deal) -> dict:
    props = deal.properties or {}
    return {
        "deal_id": deal.id,
        "deal_name": props.get("dealname", ""),
        "deal_stage": props.get("dealstage", ""),
        "owner_id": props.get("hubspot_owner_id", ""),
        "contact_name": "",
        "contact_email": "",
    }


def search_deals(query: str) -> list[dict]:
    """Search HubSpot deals by name. Returns simplified deal dicts."""
    try:
        client = _get_client()
        from hubspot.crm.deals.models import PublicObjectSearchRequest, Filter, FilterGroup

        filter_ = Filter(
            property_name="dealname",
            operator="CONTAINS_TOKEN",
            value=query,
        )
        filter_group = FilterGroup(filters=[filter_])
        search_request = PublicObjectSearchRequest(
            filter_groups=[filter_group],
            properties=["dealname", "dealstage", "hubspot_owner_id"],
            limit=20,
        )
        results = client.crm.deals.search_api.do_search(
            public_object_search_request=search_request
        )
        deals = [_extract_deal(d) for d in (results.results or [])]
        return _enrich_with_contacts(client, deals)
    except ApiException as e:
        raise HubSpotError(f"HubSpot deal search failed: {e.status} {e.reason}") from e
    except Exception as e:
        raise HubSpotError(f"HubSpot error: {e}") from e


def get_deal_details(deal_id: str) -> dict:
    """Fetch a single deal with associated contact info."""
    try:
        client = _get_client()
        deal = client.crm.deals.basic_api.get_by_id(
            deal_id=deal_id,
            properties=["dealname", "dealstage", "hubspot_owner_id"],
            associations=["contacts"],
        )
        result = _extract_deal(deal)
        enriched = _enrich_with_contacts(client, [result])
        return enriched[0] if enriched else result
    except ApiException as e:
        raise HubSpotError(f"HubSpot deal fetch failed: {e.status} {e.reason}") from e
    except Exception as e:
        raise HubSpotError(f"HubSpot error: {e}") from e


def get_all_won_deals() -> list[dict]:
    """Fetch all Closed Won deals for the dashboard."""
    try:
        client = _get_client()
        from hubspot.crm.deals.models import PublicObjectSearchRequest, Filter, FilterGroup

        filter_ = Filter(
            property_name="dealstage",
            operator="EQ",
            value="closedwon",
        )
        filter_group = FilterGroup(filters=[filter_])
        search_request = PublicObjectSearchRequest(
            filter_groups=[filter_group],
            properties=["dealname", "dealstage", "hubspot_owner_id"],
            limit=100,
        )
        results = client.crm.deals.search_api.do_search(
            public_object_search_request=search_request
        )
        deals = [_extract_deal(d) for d in (results.results or [])]
        return _enrich_with_contacts(client, deals)
    except ApiException as e:
        raise HubSpotError(f"HubSpot fetch failed: {e.status} {e.reason}") from e
    except Exception as e:
        raise HubSpotError(f"HubSpot error: {e}") from e


def parse_deals_csv(file_bytes: bytes) -> list[dict]:
    """
    Parse a HubSpot deals CSV export into the same deal dict format used by
    search_deals(). Handles the column names HubSpot uses in its exports.

    Expected columns (HubSpot default export names):
      Record ID, Deal Name, Deal Stage, Deal Owner,
      Contact: First Name, Contact: Last Name, Contact: Email
    Also accepts lowercase/snake_case variants.
    """
    df = pd.read_csv(io.BytesIO(file_bytes), dtype=str).fillna("")

    # Normalise column names: lower + strip
    df.columns = [c.strip().lower() for c in df.columns]

    # Column name aliases — HubSpot exports vary by account/view
    def _col(df, *candidates):
        for c in candidates:
            if c in df.columns:
                return df[c]
        return pd.Series([""] * len(df))

    deals = []
    for _, row in df.iterrows():
        deal_id   = _col(df, "record id", "deal id", "id", "hs_object_id").iloc[row.name] or f"csv_{row.name}"
        deal_name = _col(df, "deal name", "dealname", "name").iloc[row.name]
        stage     = _col(df, "deal stage", "dealstage", "stage").iloc[row.name]
        owner     = _col(df, "deal owner", "hubspot owner name", "owner").iloc[row.name]
        fname     = _col(df, "contact: first name", "first name", "firstname").iloc[row.name]
        lname     = _col(df, "contact: last name", "last name", "lastname").iloc[row.name]
        email     = _col(df, "contact: email", "email", "contact email").iloc[row.name]

        if not deal_name:
            continue  # skip blank rows

        deals.append({
            "deal_id": str(deal_id).strip(),
            "deal_name": deal_name.strip(),
            "deal_stage": stage.strip(),
            "owner_id": owner.strip(),
            "contact_name": f"{fname} {lname}".strip(),
            "contact_email": email.strip(),
        })
    return deals


def search_deals_csv(query: str, deals: list[dict]) -> list[dict]:
    """Filter an already-parsed CSV deal list by deal name (case-insensitive)."""
    q = query.lower()
    return [d for d in deals if q in d["deal_name"].lower()]


def _enrich_with_contacts(client: Client, deals: list[dict]) -> list[dict]:
    """Best-effort: look up the first associated contact for each deal."""
    for deal in deals:
        try:
            assoc = client.crm.deals.associations_api.get_all(
                deal_id=deal["deal_id"],
                to_object_type="contacts",
            )
            if assoc.results:
                contact_id = assoc.results[0].id
                contact = client.crm.contacts.basic_api.get_by_id(
                    contact_id=contact_id,
                    properties=["firstname", "lastname", "email"],
                )
                cp = contact.properties or {}
                deal["contact_name"] = f"{cp.get('firstname', '')} {cp.get('lastname', '')}".strip()
                deal["contact_email"] = cp.get("email", "")
        except Exception:
            pass  # Contact enrichment is best-effort; don't fail the whole search
    return deals

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

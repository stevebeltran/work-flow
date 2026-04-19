"""
Tests for hubspot_client.py

These tests mock the HubSpot SDK so they can run without real credentials.
To run: pytest tests/test_hubspot_client.py
"""
from unittest.mock import MagicMock, patch


@patch("app.hubspot_client._get_client")
def test_search_deals_returns_simplified_dicts(mock_get_client):
    mock_deal = MagicMock()
    mock_deal.id = "deal_001"
    mock_deal.properties = {
        "dealname": "Acme Drones",
        "dealstage": "closedwon",
        "hubspot_owner_id": "owner_42",
    }

    mock_results = MagicMock()
    mock_results.results = [mock_deal]

    client = MagicMock()
    client.crm.deals.search_api.do_search.return_value = mock_results
    # contact enrichment will fail gracefully
    client.crm.deals.associations_api.get_all.side_effect = Exception("no assoc")
    mock_get_client.return_value = client

    from app.hubspot_client import search_deals
    results = search_deals("Acme")

    assert len(results) == 1
    assert results[0]["deal_id"] == "deal_001"
    assert results[0]["deal_name"] == "Acme Drones"
    assert results[0]["deal_stage"] == "closedwon"


@patch("app.hubspot_client._get_client")
def test_search_deals_raises_hubspot_error_on_api_exception(mock_get_client):
    from hubspot.crm.deals import ApiException
    from app.hubspot_client import HubSpotError

    client = MagicMock()
    client.crm.deals.search_api.do_search.side_effect = ApiException(status=401, reason="Unauthorized")
    mock_get_client.return_value = client

    import pytest
    with pytest.raises(HubSpotError):
        from app.hubspot_client import search_deals
        search_deals("test")

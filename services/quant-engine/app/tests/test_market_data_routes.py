from fastapi.testclient import TestClient

from app.api.main import app


def test_market_data_quote_route_returns_mocked_quote(mocker) -> None:
    mock_service = mocker.patch("app.api.routes.market_data.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_latest_quotes.return_value = {
        "AAPL": {"symbol": "AAPL", "price": 123.45, "change": 1.23}
    }
    service_instance.get_last_fetch_meta.return_value = {"type": "quote", "resolved_symbol": "AAPL", "cached": True}
    client = TestClient(app)

    response = client.get("/market-data/quote-short?symbol=AAPL")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"][0]["price"] == 123.45
    assert payload["meta"]["type"] == "quote"


def test_market_data_history_route_returns_mocked_rows(mocker) -> None:
    mock_service = mocker.patch("app.api.routes.market_data.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [
        {"date": "2025-01-02", "price": 100.0},
        {"date": "2025-01-03", "price": 101.0},
    ]
    service_instance.get_last_fetch_meta.return_value = {"type": "history", "resolved_symbol": "SPY", "cached": True}
    client = TestClient(app)

    response = client.get("/market-data/historical-price-light?symbol=SPY&from=2025-01-01&to=2025-01-31")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["rows"]) == 2
    assert payload["meta"]["type"] == "history"


def test_strategy_lab_holdings_refresh_route_returns_refresh_counts(mocker) -> None:
    mock_service = mocker.patch("app.api.routes.strategy_lab.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.refresh_etf_holdings_snapshot.return_value = ("XLK", [{"asset": "MSFT"}, {"asset": "AAPL"}])
    service_instance.holdings_history.get_snapshot_count.return_value = 2
    client = TestClient(app)

    response = client.post("/strategy-lab/holdings/refresh", json={"symbols": ["XLK"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["refreshed"][0]["symbol"] == "XLK"
    assert payload["refreshed"][0]["rows"] == 2
    assert payload["refreshed"][0]["snapshots"] == 2

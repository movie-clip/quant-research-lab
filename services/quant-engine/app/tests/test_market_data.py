from pathlib import Path

from app.services.market_data import MarketDataService, detect_histories_return_basis, detect_history_return_basis
from app.services.holdings_history import HoldingsHistoryStore
from app.core.symbols import canonicalize_symbol, resolve_symbol_candidates


def test_symbol_resolver_canonicalizes_aliases() -> None:
    assert canonicalize_symbol("ISLN.L") == "ISLN"
    assert canonicalize_symbol("VUAA.L") == "VUAA"
    assert canonicalize_symbol("BRK-B") == "BRK B"


def test_symbol_resolver_returns_kind_specific_candidates() -> None:
    assert resolve_symbol_candidates("ISLN", kind="quote") == ["ISLN.L", "ISLN"]
    assert resolve_symbol_candidates("ISLN", kind="history", include_proxy=True) == ["ISLN.L", "ISLN", "SLV"]


def test_get_historical_prices_uses_etf_holdings_proxy_fallback(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = [[], [], [{"date": "2024-01-02", "price": 100.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("VUAA", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 100.0}]
    assert instance.get_historical_price_light.call_args_list[0].args[0] == "VUAA.L"
    assert instance.get_historical_price_light.call_args_list[1].args[0] == "VUAA"
    assert instance.get_historical_price_light.call_args_list[-1].args[0] == "SPY"
    assert service.get_last_fetch_meta("VUAA") == {"type": "history", "resolved_symbol": "SPY", "cached": True}


def test_get_historical_prices_does_not_use_proxy_fallback_by_default(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = [[], []]

    service = MarketDataService()
    rows = service.get_historical_prices("VUAA", "2024-01-01", "2024-01-31")

    assert rows == []
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["VUAA.L", "VUAA"]


def test_get_historical_prices_uses_gld_proxy_fallback_for_sgld(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = [[], [], [{"date": "2024-01-02", "price": 200.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("SGLD", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 200.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["SGLD.L", "SGLD", "GLD"]
    assert service.get_last_fetch_meta("SGLD") == {"type": "history", "resolved_symbol": "GLD", "cached": True}


def test_get_historical_prices_uses_dbc_proxy_fallback_for_icom(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = [[], [{"date": "2024-01-02", "price": 25.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("ICOM", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 25.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["ICOM", "DBC"]
    assert service.get_last_fetch_meta("ICOM") == {"type": "history", "resolved_symbol": "DBC", "cached": True}


def test_get_historical_prices_uses_slv_proxy_fallback_for_isln(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = [[], [], [{"date": "2024-01-02", "price": 21.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("ISLN.L", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 21.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["ISLN.L", "ISLN", "SLV"]
    assert service.get_last_fetch_meta("ISLN") == {"type": "history", "resolved_symbol": "SLV", "cached": True}


def test_get_historical_prices_uses_proxy_for_continuous_future_roots(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = [[{"date": "2024-01-02", "price": 500.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("ES", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 500.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["SPY"]
    assert service.get_last_fetch_meta("ES") == {"type": "history", "resolved_symbol": "SPY", "cached": True}


def test_get_etf_holdings_records_snapshot_and_reads_dated_history(mocker, tmp_path) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_etf_holders.return_value = [
        {"asset": "MSFT", "name": "Microsoft", "weightPercentage": 6.0, "updated": "2026-04-09 11:04:21"},
    ]
    mocked_settings = mocker.patch("app.services.holdings_history.get_settings")
    mocked_settings.return_value.fmp_holdings_snapshot_dir = str(tmp_path)
    history_store = HoldingsHistoryStore(str(tmp_path))

    service = MarketDataService()
    service.holdings_history = history_store

    resolved_symbol, rows = service.get_etf_holdings("XLK")

    assert resolved_symbol == "XLK"
    assert rows
    assert history_store.list_snapshot_dates("XLK") == ["2026-04-09"]

    instance.get_etf_holders.reset_mock()
    dated_resolved_symbol, dated_rows = service.get_etf_holdings_for_date("XLK", "2026-04-10")

    assert dated_resolved_symbol == "XLK"
    assert dated_rows == rows
    instance.get_etf_holders.assert_not_called()
    assert Path(tmp_path, "XLK", "2026-04-09.json").exists()


def test_refresh_etf_holdings_snapshot_reloads_symbol(mocker, tmp_path) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_etf_holders.return_value = [
        {"asset": "MSFT", "name": "Microsoft", "weightPercentage": 6.0, "updated": "2026-04-12 11:04:21"},
    ]
    mocked_settings = mocker.patch("app.services.holdings_history.get_settings")
    mocked_settings.return_value.fmp_holdings_snapshot_dir = str(tmp_path)

    service = MarketDataService()
    service.holdings_history = HoldingsHistoryStore(str(tmp_path))
    service.holdings_history.record_snapshot("XLK", "XLK", [{"asset": "AAPL", "updated": "2026-04-09 11:04:21"}])

    resolved_symbol, rows = service.refresh_etf_holdings_snapshot("XLK")

    assert resolved_symbol == "XLK"
    assert rows[0]["asset"] == "MSFT"
    assert service.holdings_history.list_snapshot_dates("XLK") == ["2026-04-12"]


def test_detect_history_return_basis_returns_unavailable_for_empty_rows() -> None:
    assert detect_history_return_basis([]) == "unavailable"


def test_detect_history_return_basis_returns_verified_only_when_all_rows_have_adjusted_fields() -> None:
    assert detect_history_return_basis([
        {"date": "2024-01-02", "price": 100.0, "adjClose": 99.5},
        {"date": "2024-01-03", "price": 101.0, "adjusted_close": 100.4},
    ]) == "verified_adjusted_close"


def test_detect_history_return_basis_returns_unverified_when_adjusted_fields_are_missing() -> None:
    assert detect_history_return_basis([
        {"date": "2024-01-02", "price": 100.0},
        {"date": "2024-01-03", "price": 101.0, "adjClose": 100.2},
    ]) == "unverified_close_only"


def test_detect_histories_return_basis_requires_all_populated_histories_to_be_verified() -> None:
    assert detect_histories_return_basis({
        "SPY": [{"date": "2024-01-02", "price": 100.0, "adjClose": 99.5}],
        "QQQ": [{"date": "2024-01-02", "price": 200.0}],
    }) == "unverified_close_only"

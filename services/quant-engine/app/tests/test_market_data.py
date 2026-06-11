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


def test_dfnd_resolves_to_ishares_aerospace_defence_line() -> None:
    # US-18.3 (corrected): DFND = iShares Global Aerospace & Defence UCITS ETF
    # (LSE, GBP) → DFND.L on Yahoo, ahead of the bare DFND.
    history = resolve_symbol_candidates("DFND", kind="history")
    assert "DFND.L" in history
    assert history.index("DFND.L") < history.index("DFND")


def test_dfnd_never_maps_to_vaneck_lines() -> None:
    # DFNS.L / DFEN.DE / DFNG.L are VanEck Defense — a DIFFERENT fund. They must
    # never appear in any DFND candidate list (wrong-fund guard).
    for kind in ("quote", "history", "holdings"):
        candidates = resolve_symbol_candidates("DFND", kind=kind)
        for wrong in ("DFNS.L", "DFEN.DE", "DFNG.L"):
            assert wrong not in candidates


def test_defs_and_idfn_resolution_unchanged() -> None:
    # US-18.3 AC3: these already resolved correctly via US-18.1 — leading .L line.
    assert resolve_symbol_candidates("DEFS", kind="history")[0] == "DEFS.L"
    assert resolve_symbol_candidates("IDFN", kind="history")[0] == "IDFN.L"


def test_icom_and_vdst_resolve_to_lse_lines() -> None:
    # US-18.3 follow-up: both are LSE/USD UCITS ETFs → .L line on Yahoo.
    # ICOM.L = iShares Diversified Commodity Swap; VDST.L = Vanguard US Treasury 0-1y.
    assert resolve_symbol_candidates("ICOM", kind="history") == ["ICOM.L", "ICOM"]
    assert resolve_symbol_candidates("VDST", kind="history") == ["VDST.L", "VDST"]
    assert canonicalize_symbol("ICOM.L") == "ICOM"
    assert canonicalize_symbol("VDST.L") == "VDST"


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
    # Superset assertion: last_fetch_meta is intentionally extensible (vendor was
    # added in US-18.1); pin the fields this test cares about, tolerate additions.
    assert {"type": "history", "resolved_symbol": "SPY", "cached": True, "vendor": "fmp"}.items() <= service.get_last_fetch_meta("VUAA").items()


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
    assert {"type": "history", "resolved_symbol": "GLD", "cached": True, "vendor": "fmp"}.items() <= service.get_last_fetch_meta("SGLD").items()


def test_get_historical_prices_uses_dbc_proxy_fallback_for_icom(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = [[], [], [{"date": "2024-01-02", "price": 25.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("ICOM", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 25.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["ICOM.L", "ICOM", "DBC"]
    assert {"type": "history", "resolved_symbol": "DBC", "cached": True, "vendor": "fmp"}.items() <= service.get_last_fetch_meta("ICOM").items()


def test_get_historical_prices_uses_slv_proxy_fallback_for_isln(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = [[], [], [{"date": "2024-01-02", "price": 21.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("ISLN.L", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 21.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["ISLN.L", "ISLN", "SLV"]
    assert {"type": "history", "resolved_symbol": "SLV", "cached": True, "vendor": "fmp"}.items() <= service.get_last_fetch_meta("ISLN").items()


def test_get_historical_prices_uses_proxy_for_continuous_future_roots(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = [[{"date": "2024-01-02", "price": 500.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("ES", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 500.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["SPY"]
    assert {"type": "history", "resolved_symbol": "SPY", "cached": True, "vendor": "fmp"}.items() <= service.get_last_fetch_meta("ES").items()


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


def test_get_direct_spy_benchmark_history_records_direct_vendor_scope_metadata(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.return_value = [{"date": "2024-01-02", "price": 100.0, "adjClose": 99.5}]

    service = MarketDataService()
    rows = service.get_direct_spy_benchmark_history("2024-01-01", "2024-01-31")

    assert rows == [{"date": "2024-01-02", "price": 100.0, "adjClose": 99.5}]
    instance.get_historical_price_light.assert_called_once_with("SPY", "2024-01-01", "2024-01-31")
    assert service.get_last_fetch_meta("SPY") == {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": True,
        "fallback_used": False,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }


def test_get_direct_verified_benchmark_history_records_direct_vendor_scope_metadata_for_qqq(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.return_value = [{"date": "2024-01-02", "price": 400.0, "adjClose": 399.0}]

    service = MarketDataService()
    rows = service.get_direct_verified_benchmark_history("QQQ", "2024-01-01", "2024-01-31")

    assert rows == [{"date": "2024-01-02", "price": 400.0, "adjClose": 399.0}]
    instance.get_historical_price_light.assert_called_once_with("QQQ", "2024-01-01", "2024-01-31")
    assert service.get_last_fetch_meta("QQQ") == {
        "type": "history",
        "requested_symbol": "QQQ",
        "resolved_symbol": "QQQ",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": True,
        "fallback_used": False,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }


def test_get_direct_verified_benchmark_history_rejects_non_allowlisted_symbols(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value

    service = MarketDataService()
    rows = service.get_direct_verified_benchmark_history("VOO", "2024-01-01", "2024-01-31")

    assert rows == []
    instance.get_historical_price_light.assert_not_called()
    assert service.get_last_fetch_meta("VOO") is None


def test_fmp_client_exposes_statement_endpoints(mocker) -> None:
    response_mock = mocker.Mock()
    response_mock.json.return_value = [{"symbol": "AAPL", "date": "2023-12-31"}]
    response_mock.raise_for_status.return_value = None
    client_get = mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    mocked_settings = mocker.patch("app.clients.fmp.get_settings")
    mocked_settings.return_value.fmp_api_key = "test-key"
    mocked_settings.return_value.fmp_base_url = "https://financialmodelingprep.com/stable"
    mocked_settings.return_value.fmp_quote_cache_ttl_seconds = 300
    mocked_settings.return_value.fmp_history_cache_ttl_seconds = 86400
    mocked_settings.return_value.fmp_max_requests_per_minute = 0
    mocked_settings.return_value.fmp_cache_enabled = False
    mocked_settings.return_value.fmp_cache_dir = "unused"

    from app.clients.fmp import FmpClient

    client = FmpClient()
    assert client.get_income_statements("AAPL", limit=4, period="quarter") == [{"symbol": "AAPL", "date": "2023-12-31"}]
    assert client.get_balance_sheet_statements("AAPL", limit=4, period="quarter") == [{"symbol": "AAPL", "date": "2023-12-31"}]
    assert client.get_cash_flow_statements("AAPL", limit=4, period="quarter") == [{"symbol": "AAPL", "date": "2023-12-31"}]

    assert client_get.call_args_list[0].kwargs["params"] == {"symbol": "AAPL", "limit": 4, "period": "quarter", "apikey": "test-key"}
    assert client_get.call_args_list[0].args[0].endswith("/income-statement")
    assert client_get.call_args_list[1].args[0].endswith("/balance-sheet-statement")
    assert client_get.call_args_list[2].args[0].endswith("/cash-flow-statement")

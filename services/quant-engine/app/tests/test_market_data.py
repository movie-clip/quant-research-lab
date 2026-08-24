from pathlib import Path

import pytest

from app.services.market_data import MarketDataService, detect_histories_return_basis, detect_history_return_basis
from app.services.holdings_history import HoldingsHistoryStore
from app.clients.yfinance_client import YFinanceClient
from app.core.symbols import canonicalize_symbol, resolve_proxy_candidates, resolve_symbol_candidates


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


def test_semi_never_maps_to_bare_us_listed_line() -> None:
    # US-31.4 (Epic 31 F-5): bare "SEMI" on FMP is a DIFFERENT US-listed
    # security (40.58 vs the held SEMI.L 17.998 GBP). It must never appear in
    # any real-data candidate list — the wrong-fund guard, mirroring
    # test_dfnd_never_maps_to_vaneck_lines.
    for kind in ("quote", "history", "holdings"):
        candidates = resolve_symbol_candidates("SEMI", kind=kind)
        assert "SEMI" not in candidates
        assert candidates == ["SEMI.L"]


def test_semi_resolves_to_lse_ucits_line() -> None:
    # US-31.4 AC2: SEMI.L (iShares MSCI Global Semiconductors UCITS, GBP) is the
    # sole leading real-data candidate; the alias still canonicalizes.
    assert resolve_symbol_candidates("SEMI", kind="history")[0] == "SEMI.L"
    assert canonicalize_symbol("SEMI.L") == "SEMI"


def test_semi_us_line_only_reachable_as_labeled_proxy() -> None:
    # US-31.4 AC3: the US line is reachable ONLY via the explicit proxy path;
    # bare "SEMI" is not silently reintroduced as a proxy, and the deliberate
    # SOXX/SMH semiconductor proxies are unchanged.
    assert resolve_symbol_candidates("SEMI", kind="history", include_proxy=True) == ["SEMI.L", "SOXX", "SMH"]
    assert resolve_proxy_candidates("SEMI") == ["SOXX", "SMH"]


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
    instance.is_cached.return_value = True
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
    instance.is_cached.return_value = True
    instance.get_historical_price_light.side_effect = [[], [], [{"date": "2024-01-02", "price": 200.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("SGLD", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 200.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["SGLD.L", "SGLD", "GLD"]
    assert {"type": "history", "resolved_symbol": "GLD", "cached": True, "vendor": "fmp"}.items() <= service.get_last_fetch_meta("SGLD").items()


def test_get_historical_prices_uses_dbc_proxy_fallback_for_icom(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.is_cached.return_value = True
    instance.get_historical_price_light.side_effect = [[], [], [{"date": "2024-01-02", "price": 25.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("ICOM", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 25.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["ICOM.L", "ICOM", "DBC"]
    assert {"type": "history", "resolved_symbol": "DBC", "cached": True, "vendor": "fmp"}.items() <= service.get_last_fetch_meta("ICOM").items()


def test_get_historical_prices_uses_slv_proxy_fallback_for_isln(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.is_cached.return_value = True
    instance.get_historical_price_light.side_effect = [[], [], [{"date": "2024-01-02", "price": 21.0}]]

    service = MarketDataService()
    rows = service.get_historical_prices("ISLN.L", "2024-01-01", "2024-01-31", allow_proxy_fallback=True)

    assert rows == [{"date": "2024-01-02", "price": 21.0}]
    assert [call.args[0] for call in instance.get_historical_price_light.call_args_list] == ["ISLN.L", "ISLN", "SLV"]
    assert {"type": "history", "resolved_symbol": "SLV", "cached": True, "vendor": "fmp"}.items() <= service.get_last_fetch_meta("ISLN").items()


def test_get_historical_prices_uses_proxy_for_continuous_future_roots(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.is_cached.return_value = True
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
    instance.is_cached.return_value = True
    instance.get_historical_price_dividend_adjusted.return_value = [{"date": "2024-01-02", "price": 100.0, "adjClose": 99.5}]

    service = MarketDataService()
    rows = service.get_direct_spy_benchmark_history("2024-01-01", "2024-01-31")

    assert rows == [{"date": "2024-01-02", "price": 100.0, "adjClose": 99.5}]
    # US-20.2: the client is called with the canonical (year-quantized) range;
    # the result is sliced back to the requested window.
    # US-34.9: via the DIVIDEND-ADJUSTED endpoint — the light one returns no
    # `adjClose`, so the verified rung could never fire on it (F-9).
    instance.get_historical_price_dividend_adjusted.assert_called_once_with("SPY", "2024-01-01", "2024-12-31")
    instance.get_historical_price_light.assert_not_called()
    assert service.get_last_fetch_meta("SPY") == {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/dividend-adjusted",
        "direct_path_only": True,
        "fallback_used": False,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }


def test_get_direct_verified_benchmark_history_records_direct_vendor_scope_metadata_for_qqq(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.is_cached.return_value = True
    instance.get_historical_price_dividend_adjusted.return_value = [{"date": "2024-01-02", "price": 400.0, "adjClose": 399.0}]

    service = MarketDataService()
    rows = service.get_direct_verified_benchmark_history("QQQ", "2024-01-01", "2024-01-31")

    assert rows == [{"date": "2024-01-02", "price": 400.0, "adjClose": 399.0}]
    instance.get_historical_price_dividend_adjusted.assert_called_once_with("QQQ", "2024-01-01", "2024-12-31")
    instance.get_historical_price_light.assert_not_called()
    assert service.get_last_fetch_meta("QQQ") == {
        "type": "history",
        "requested_symbol": "QQQ",
        "resolved_symbol": "QQQ",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/dividend-adjusted",
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
    # US-34.9: neither endpoint is reached — the allowlist is checked first.
    instance.get_historical_price_dividend_adjusted.assert_not_called()
    instance.get_historical_price_light.assert_not_called()
    assert service.get_last_fetch_meta("VOO") is None


# ── US-20.2: history range normalization ────────────────────────────────────

def test_canonical_history_range_quantizes_to_calendar_years() -> None:
    from app.services.market_data import _canonical_history_range

    assert _canonical_history_range("2026-03-05", "2026-05-25") == ("2026-01-01", "2026-12-31")
    # Multi-year window widens to span both year boundaries.
    assert _canonical_history_range("2021-08-01", "2026-05-25") == ("2021-01-01", "2026-12-31")


def test_slice_price_rows_keeps_only_in_window_rows_in_order() -> None:
    from app.services.market_data import _slice_price_rows

    rows = [
        {"date": "2024-01-31", "price": 1.0},
        {"date": "2024-03-10", "price": 2.0},
        {"date": "2024-03-25", "price": 3.0},
        {"date": "2024-06-01", "price": 4.0},
        {"date": None, "price": 5.0},
    ]
    sliced = _slice_price_rows(rows, "2024-03-01", "2024-03-31")
    assert sliced == [
        {"date": "2024-03-10", "price": 2.0},
        {"date": "2024-03-25", "price": 3.0},
    ]


def _canonical_year_rows() -> list[dict]:
    return [
        {"date": "2024-01-15", "price": 10.0},
        {"date": "2024-03-10", "price": 11.0},
        {"date": "2024-03-25", "price": 12.0},
        {"date": "2024-09-30", "price": 13.0},
    ]


def test_overlapping_requests_share_one_canonical_cache_key(mocker) -> None:
    # Two different windows in the same year must fetch the SAME canonical range
    # (one cache key → one underlying FMP fetch via FmpClient's cache).
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.return_value = _canonical_year_rows()

    service = MarketDataService()
    service.get_historical_prices("AAA", "2024-03-01", "2024-03-31")
    service.get_historical_prices("AAA", "2024-08-01", "2024-10-31")

    canonical_calls = [
        (call.args[0], call.args[1], call.args[2])
        for call in instance.get_historical_price_light.call_args_list
    ]
    assert canonical_calls == [
        ("AAA", "2024-01-01", "2024-12-31"),
        ("AAA", "2024-01-01", "2024-12-31"),
    ]


def test_normalized_result_equals_direct_window_slice(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.return_value = _canonical_year_rows()

    service = MarketDataService()
    rows = service.get_historical_prices("AAA", "2024-03-01", "2024-03-31")

    # Exactly the March bars — nothing outside the requested window leaks in.
    assert rows == [
        {"date": "2024-03-10", "price": 11.0},
        {"date": "2024-03-25", "price": 12.0},
    ]


def test_window_with_no_in_range_bars_returns_empty(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    # Canonical fetch has bars, but none inside the requested window → [].
    instance.get_historical_price_light.return_value = _canonical_year_rows()

    service = MarketDataService()
    rows = service.get_historical_prices("AAA", "2024-12-01", "2024-12-31")

    assert rows == []
    assert service.get_last_fetch_meta("AAA") is None


def test_yfinance_fallback_rows_are_normalized_and_sliced(mocker) -> None:
    # FMP empty for all candidates → Yahoo fallback; its rows must also be
    # fetched over the canonical range and sliced.
    fmp_mock = mocker.patch("app.services.market_data.FmpClient")
    fmp_mock.return_value.get_historical_price_light.return_value = []
    yf_mock = mocker.patch("app.services.market_data.YFinanceClient")
    yf_mock.return_value.get_historical_price_light.return_value = _canonical_year_rows()

    service = MarketDataService()
    rows = service.get_historical_prices("VUAA", "2024-03-01", "2024-03-31")

    assert rows == [
        {"date": "2024-03-10", "price": 11.0},
        {"date": "2024-03-25", "price": 12.0},
    ]
    # Yahoo was asked for the canonical range, not the raw window.
    yf_call = yf_mock.return_value.get_historical_price_light.call_args_list[0]
    assert (yf_call.args[1], yf_call.args[2]) == ("2024-01-01", "2024-12-31")
    assert {"vendor": "yfinance"}.items() <= service.get_last_fetch_meta("VUAA").items()


def test_verified_benchmark_overlapping_windows_share_canonical_call(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.is_cached.return_value = True
    instance.get_historical_price_dividend_adjusted.return_value = [
        {"date": "2024-03-10", "price": 500.0, "adjClose": 499.0},
        {"date": "2024-09-30", "price": 510.0, "adjClose": 509.0},
    ]

    service = MarketDataService()
    first = service.get_direct_verified_benchmark_history("SPY", "2024-03-01", "2024-03-31")
    service.get_direct_verified_benchmark_history("SPY", "2024-08-01", "2024-10-31")

    assert first == [{"date": "2024-03-10", "price": 500.0, "adjClose": 499.0}]
    canonical_calls = [
        (call.args[0], call.args[1], call.args[2])
        for call in instance.get_historical_price_dividend_adjusted.call_args_list
    ]
    assert canonical_calls == [
        ("SPY", "2024-01-01", "2024-12-31"),
        ("SPY", "2024-01-01", "2024-12-31"),
    ]
    # Verified-benchmark meta unchanged in shape/values (no provenance regression).
    assert {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "direct_path_only": True,
    }.items() <= service.get_last_fetch_meta("SPY").items()


# ── US-20.3: parallel multi-symbol fetch ────────────────────────────────────

def test_for_symbols_fetches_all_symbols_concurrently(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value

    def _light(symbol: str, *_a, **_k) -> list[dict]:
        return [{"date": "2024-03-10", "price": 100.0 + len(symbol)}]

    instance.get_historical_price_light.side_effect = _light

    service = MarketDataService()
    result = service.get_historical_prices_for_symbols(["AAA", "BBB", "CCC"], "2024-03-01", "2024-03-31")

    assert set(result.keys()) == {"AAA", "BBB", "CCC"}
    for symbol in ("AAA", "BBB", "CCC"):
        assert result[symbol] == [{"date": "2024-03-10", "price": 100.0 + len(symbol)}]


def test_for_symbols_populates_meta_for_every_symbol(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.side_effect = lambda *_a, **_k: [{"date": "2024-03-10", "price": 50.0}]

    service = MarketDataService()
    service.get_historical_prices_for_symbols(["AAA", "BBB"], "2024-03-01", "2024-03-31")

    assert {"vendor": "fmp"}.items() <= service.get_last_fetch_meta("AAA").items()
    assert {"vendor": "fmp"}.items() <= service.get_last_fetch_meta("BBB").items()


def test_for_symbols_empty_symbol_fails_closed_under_concurrency(mocker) -> None:
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.get_historical_price_light.return_value = []  # FMP empty for every candidate

    service = MarketDataService()
    result = service.get_historical_prices_for_symbols(["AAA", "BBB"], "2024-03-01", "2024-03-31")

    # No data anywhere → each symbol maps to [] (never fabricated), keys preserved.
    assert result == {"AAA": [], "BBB": []}


def test_fmp_client_exposes_statement_endpoints(mocker) -> None:
    response_mock = mocker.Mock()
    response_mock.json.return_value = [{"symbol": "AAPL", "date": "2023-12-31"}]
    response_mock.raise_for_status.return_value = None
    client_get = mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    mocked_settings = mocker.patch("app.clients.fmp.get_settings")
    mocked_settings.return_value.fmp_api_key = "test-key"
    mocked_settings.return_value.fmp_base_url = "https://financialmodelingprep.com/stable"
    mocked_settings.return_value.fmp_legacy_base_url = "https://financialmodelingprep.com/api/v3"
    mocked_settings.return_value.fmp_quote_cache_ttl_seconds = 300
    mocked_settings.return_value.fmp_history_cache_ttl_seconds = 86400
    mocked_settings.return_value.fmp_max_requests_per_minute = 0
    mocked_settings.return_value.fmp_request_timeout_seconds = 30.0
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


# ── US-24.6: FMP client transport config (escaped URL + timeout) ──────────────


def _mock_fmp_settings(mocker, **overrides):
    """Patch app.clients.fmp.get_settings with explicit values for every
    setting FmpClient reads (no Mock auto-attributes standing in for real
    transport config — US-24.6 AC7)."""
    mocked = mocker.patch("app.clients.fmp.get_settings")
    values = {
        "fmp_api_key": "test-key",
        "fmp_base_url": "https://financialmodelingprep.com/stable",
        "fmp_legacy_base_url": "https://financialmodelingprep.com/api/v3",
        "fmp_quote_cache_ttl_seconds": 300,
        "fmp_history_cache_ttl_seconds": 86400,
        "fmp_max_requests_per_minute": 0,
        "fmp_request_timeout_seconds": 30.0,
        "fmp_cache_enabled": False,
        "fmp_cache_dir": "unused",
    }
    values.update(overrides)
    for key, value in values.items():
        setattr(mocked.return_value, key, value)
    return mocked


def test_get_etf_holders_builds_url_from_configured_legacy_base(mocker) -> None:
    """AC1/AC2 — the etf-holder call is redirectable: its URL comes from
    fmp_legacy_base_url, not a hardcoded vendor host."""
    response_mock = mocker.Mock()
    response_mock.json.return_value = [{"asset": "AAPL", "weightPercentage": 7.1}]
    response_mock.raise_for_status.return_value = None
    client_get = mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(mocker, fmp_legacy_base_url="https://proxy.internal/v3-mirror")

    from app.clients.fmp import FmpClient

    rows = FmpClient().get_etf_holders("SPY")

    assert rows == [{"asset": "AAPL", "weightPercentage": 7.1}]
    assert client_get.call_args.args[0] == "https://proxy.internal/v3-mirror/etf-holder/SPY"


def test_get_etf_holders_default_url_matches_pre_refactor_endpoint(mocker) -> None:
    """AC2/AC5 — at default settings the URL is byte-identical to the previous
    hardcoded literal, so live behaviour is unchanged."""
    response_mock = mocker.Mock()
    response_mock.json.return_value = []
    response_mock.raise_for_status.return_value = None
    client_get = mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(mocker)

    from app.clients.fmp import FmpClient

    FmpClient().get_etf_holders("SPY")

    assert client_get.call_args.args[0] == "https://financialmodelingprep.com/api/v3/etf-holder/SPY"


def test_get_etf_holders_cache_identity_is_unchanged_by_url_refactor(mocker) -> None:
    """AC4 — the cache key is derived from the v3 PATH string, deliberately
    independent of the (now configurable) host. Changing the base URL must not
    invalidate cached holdings entries or break in-flight coalescing."""
    import json

    response_mock = mocker.Mock()
    response_mock.json.return_value = [{"asset": "AAPL"}]
    response_mock.raise_for_status.return_value = None
    mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)

    build_key = mocker.Mock(return_value="holdings-key")
    cache = mocker.Mock()
    cache.build_key = build_key
    cache.get.return_value = None
    mocker.patch("app.clients.fmp.JsonFileCache", return_value=cache)
    # A non-default host proves the cache identity does NOT track the base URL.
    _mock_fmp_settings(mocker, fmp_cache_enabled=True, fmp_legacy_base_url="https://proxy.internal/v3")

    from app.clients.fmp import FmpClient

    FmpClient().get_etf_holders("SPY")

    namespace, identifier = build_key.call_args.args
    assert namespace == "holdings"
    assert identifier == json.dumps({"path": "api/v3/etf-holder/SPY", "params": {}}, sort_keys=True)


def test_fmp_client_timeout_comes_from_settings(mocker) -> None:
    """AC3 — the transport timeout is configurable, defaulting to 30.0."""
    httpx_client = mocker.patch("app.clients.fmp.httpx.Client")
    _mock_fmp_settings(mocker, fmp_request_timeout_seconds=7.5)

    from app.clients.fmp import FmpClient

    FmpClient()

    assert httpx_client.call_args.kwargs["timeout"] == 7.5

    from app.core.settings import Settings

    assert Settings().fmp_request_timeout_seconds == 30.0
    assert Settings().fmp_legacy_base_url == "https://financialmodelingprep.com/api/v3"


# -- US-35.1 (Epic 35 F-1): the error has to survive the service layer -------


def test_an_auth_error_propagates_instead_of_being_flattened_to_no_data(mocker) -> None:
    """US-35.1 AC4 — fixing the client alone would have changed nothing.

    `MarketDataService` catches `Exception` at every call site, so a raised
    auth error would have been swallowed one layer up and turned back into the
    empty result this story exists to eliminate.
    """
    from app.clients.fmp import MarketDataAuthError

    client_mock = mocker.patch("app.services.market_data.FmpClient")
    client_mock.return_value.get_historical_price_light.side_effect = MarketDataAuthError("rejected")

    service = MarketDataService()
    with pytest.raises(MarketDataAuthError):
        service.get_historical_prices("AAPL", "2024-01-01", "2024-01-31")


def test_a_non_auth_failure_at_the_same_call_site_still_degrades(mocker) -> None:
    """US-35.1 AC4, the other direction — the broad catches stay load-bearing.

    Symbol resolution tries VUAA.L -> VUAA -> a US proxy and expects most
    candidates to fail. If narrowing the auth case had also narrowed these, a
    normal resolution miss would become a hard error.
    """
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    client_mock.return_value.get_historical_price_light.side_effect = RuntimeError("transient blip")

    service = MarketDataService()
    assert service.get_historical_prices("AAPL", "2024-01-01", "2024-01-31") == []


# ── US-37.2 (T-37.2.4): get_company_profile cache-status accuracy (AC3/AC4) ──
#
# `last_fetch_meta[...]["cached"]` used to be hardcoded True on every
# successful profile call (services/market_data.py:474, pre-fix). These pin
# the fix: a fresh call reports the true miss, a subsequent call for the same
# symbol within the cache's TTL reports the true hit. Per the story's test
# plan, this asserts the REPORTED value only — not FmpClient's internal call
# count or sequence, which is an implementation detail of the fix.


def test_get_company_profile_reports_true_miss_then_true_hit_within_ttl(mocker, tmp_path) -> None:
    response_mock = mocker.Mock()
    response_mock.json.return_value = [
        {"symbol": "AAPL", "sector": "Technology", "isin": "US0378331005"},
    ]
    response_mock.raise_for_status.return_value = None
    mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(
        mocker,
        fmp_cache_enabled=True,
        fmp_cache_dir=str(tmp_path),
        fmp_profile_cache_ttl_seconds=86400,
    )

    service = MarketDataService()

    first_profile = service.get_company_profile("AAPL")
    first_meta = service.get_last_fetch_meta("AAPL")
    second_profile = service.get_company_profile("AAPL")
    second_meta = service.get_last_fetch_meta("AAPL")

    assert first_profile == {"symbol": "AAPL", "sector": "Technology", "isin": "US0378331005"}
    assert second_profile == first_profile
    assert first_meta["cached"] is False
    assert second_meta["cached"] is True


def test_get_company_profile_reports_miss_for_different_symbols_independently(mocker, tmp_path) -> None:
    """A hit for one symbol must not leak into another symbol's cache status —
    the pre-check is keyed per-symbol, not a single shared flag."""
    response_mock = mocker.Mock()
    response_mock.json.side_effect = [
        [{"symbol": "AAPL", "sector": "Technology", "isin": "US0378331005"}],
        [{"symbol": "MSFT", "sector": "Technology", "isin": "US5949181045"}],
    ]
    response_mock.raise_for_status.return_value = None
    mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(
        mocker,
        fmp_cache_enabled=True,
        fmp_cache_dir=str(tmp_path),
        fmp_profile_cache_ttl_seconds=86400,
    )

    service = MarketDataService()

    service.get_company_profile("AAPL")
    aapl_meta = service.get_last_fetch_meta("AAPL")
    service.get_company_profile("MSFT")
    msft_meta = service.get_last_fetch_meta("MSFT")

    assert aapl_meta["cached"] is False
    assert msft_meta["cached"] is False


def test_one_unresolvable_symbol_does_not_fail_the_whole_portfolio(mocker) -> None:
    """US-35.1 AC5 — a per-symbol failure must stay per-symbol."""
    client_mock = mocker.patch("app.services.market_data.FmpClient")

    def by_symbol(symbol, *_a, **_k):
        if symbol == "NOPE":
            raise RuntimeError("unresolvable")
        return [{"date": "2024-01-02", "price": 100.0}]

    client_mock.return_value.get_historical_price_light.side_effect = by_symbol

    service = MarketDataService()
    result = service.get_historical_prices_for_symbols(
        ["AAPL", "NOPE", "MSFT"], "2024-01-01", "2024-01-31"
    )

    assert result.get("AAPL"), "a good symbol must still return rows"
    assert result.get("MSFT"), "a good symbol must still return rows"
    assert not result.get("NOPE"), "the unresolvable one degrades on its own"


# ── US-38.2 (T-38.2.3): cache-flag accuracy for the five remaining methods ──
#
# Mirrors the get_company_profile AC3/AC4 shape directly above: real
# JsonFileCache + real FmpClient, only the HTTP transport is stubbed. A fresh
# call reports the true miss; a second call for the same inputs within TTL
# reports the true hit. A fully-mocked FmpClient (as the fixed 8 tests above
# do) can't tell these apart from the pre-existing bug's hardcoded `True` —
# that is why these use the real client/cache instead.


def test_get_latest_quotes_reports_true_miss_then_true_hit_within_ttl(mocker, tmp_path) -> None:
    """AC1/AC6."""
    response_mock = mocker.Mock()
    response_mock.json.return_value = [{"symbol": "AAPL", "price": 150.0}]
    response_mock.raise_for_status.return_value = None
    mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(
        mocker, fmp_cache_enabled=True, fmp_cache_dir=str(tmp_path), fmp_quote_cache_ttl_seconds=86400
    )

    service = MarketDataService()

    service.get_latest_quotes(["AAPL"])
    first_meta = service.get_last_fetch_meta("AAPL")
    service.get_latest_quotes(["AAPL"])
    second_meta = service.get_last_fetch_meta("AAPL")

    assert first_meta["cached"] is False
    assert second_meta["cached"] is True


def test_get_historical_prices_fmp_branch_reports_true_miss_then_true_hit_within_ttl(mocker, tmp_path) -> None:
    """AC2/AC6 — the primary (FMP) success path."""
    response_mock = mocker.Mock()
    response_mock.json.return_value = [{"symbol": "AAPL", "date": "2024-01-02", "price": 100.0}]
    response_mock.raise_for_status.return_value = None
    mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(
        mocker, fmp_cache_enabled=True, fmp_cache_dir=str(tmp_path), fmp_history_cache_ttl_seconds=86400
    )

    service = MarketDataService()

    service.get_historical_prices("AAPL", "2024-01-01", "2024-01-31")
    first_meta = service.get_last_fetch_meta("AAPL")
    service.get_historical_prices("AAPL", "2024-01-01", "2024-01-31")
    second_meta = service.get_last_fetch_meta("AAPL")

    assert first_meta["cached"] is False
    assert first_meta["vendor"] == "fmp"
    assert second_meta["cached"] is True


def test_get_historical_prices_yfinance_branch_reports_true_miss_then_true_hit_within_ttl(
    mocker, monkeypatch, tmp_path
) -> None:
    """AC2/AC6 — the yfinance-fallback success path (a distinct call site).

    FMP returns empty for every candidate (the 402/no-listing case), so the
    fallback is reached. This overrides the autouse `_disable_yfinance_fallback`
    fixture (test-body patch wins, per that fixture's own docstring) so the
    REAL YFinanceClient + its real cache are exercised — only yfinance's own
    `Ticker` is stubbed.
    """
    response_mock = mocker.Mock()
    response_mock.json.return_value = []
    response_mock.raise_for_status.return_value = None
    mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(mocker, fmp_cache_enabled=True, fmp_cache_dir=str(tmp_path / "fmp"))

    monkeypatch.setattr("app.services.market_data.YFinanceClient", YFinanceClient)
    yf_settings = mocker.patch("app.clients.yfinance_client.get_settings")
    yf_settings.return_value.fmp_history_cache_ttl_seconds = 86400
    yf_settings.return_value.fmp_cache_enabled = True
    yf_settings.return_value.fmp_cache_dir = str(tmp_path / "yf")

    import pandas as pd

    frame = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [10.0], "Adj Close": [9.0], "Volume": [100]},
        index=pd.to_datetime(["2024-01-02"]),
    )

    class FakeTicker:
        def __init__(self, symbol) -> None:  # noqa: ANN001
            pass

        def history(self, start, end, auto_adjust=False):  # noqa: ANN001
            return frame

    monkeypatch.setattr("yfinance.Ticker", FakeTicker)

    service = MarketDataService()

    service.get_historical_prices("VUAA", "2024-01-01", "2024-01-31")
    first_meta = service.get_last_fetch_meta("VUAA")
    service.get_historical_prices("VUAA", "2024-01-01", "2024-01-31")
    second_meta = service.get_last_fetch_meta("VUAA")

    assert first_meta["cached"] is False
    assert first_meta["vendor"] == "yfinance"
    assert second_meta["cached"] is True


def test_get_direct_verified_benchmark_history_reports_true_miss_then_true_hit_within_ttl(mocker, tmp_path) -> None:
    """AC3/AC6."""
    response_mock = mocker.Mock()
    response_mock.json.side_effect = [
        [{"symbol": "SPY", "date": "2024-01-02", "close": 100.0}],
        [{"symbol": "SPY", "date": "2024-01-02", "adjClose": 99.5}],
    ]
    response_mock.raise_for_status.return_value = None
    mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(
        mocker, fmp_cache_enabled=True, fmp_cache_dir=str(tmp_path), fmp_history_cache_ttl_seconds=86400
    )

    service = MarketDataService()

    service.get_direct_verified_benchmark_history("SPY", "2024-01-01", "2024-01-31")
    first_meta = service.get_last_fetch_meta("SPY")
    service.get_direct_verified_benchmark_history("SPY", "2024-01-01", "2024-01-31")
    second_meta = service.get_last_fetch_meta("SPY")

    assert first_meta["cached"] is False
    assert second_meta["cached"] is True


def test_get_direct_verified_benchmark_history_requires_both_underlying_paths_cached(mocker, tmp_path) -> None:
    """AC3 — `get_historical_price_dividend_adjusted` issues TWO underlying FMP
    calls (full, dividend-adjusted) per fetch. A hit on only ONE of them must
    still report `cached: False`, since a live request still happens for the
    other — proving this is an AND, not an OR or a single-call check."""
    from app.services.market_data import _canonical_history_range

    response_mock = mocker.Mock()
    response_mock.json.side_effect = [
        [{"symbol": "SPY", "date": "2024-01-02", "close": 100.0}],  # pre-warms "full" only
        [{"symbol": "SPY", "date": "2024-01-02", "adjClose": 99.5}],  # the benchmark call's own live "dividend-adjusted" fetch
    ]
    response_mock.raise_for_status.return_value = None
    mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(
        mocker, fmp_cache_enabled=True, fmp_cache_dir=str(tmp_path), fmp_history_cache_ttl_seconds=86400
    )

    service = MarketDataService()
    canonical_from, canonical_to = _canonical_history_range("2024-01-01", "2024-01-31")
    params = {"symbol": "SPY", "from": canonical_from, "to": canonical_to}
    # Pre-warm ONLY the "full" endpoint's cache entry — the dividend-adjusted
    # one stays a miss.
    service.client._get(  # noqa: SLF001 — deliberately reaching in to prime one of the two cache entries
        "history", "historical-price-eod/full", params, ttl_seconds=service.client.history_ttl_seconds
    )

    service.get_direct_verified_benchmark_history("SPY", "2024-01-01", "2024-01-31")
    meta = service.get_last_fetch_meta("SPY")

    assert meta["cached"] is False


def test_get_etf_holdings_reports_true_miss_then_true_hit_within_ttl(mocker, tmp_path) -> None:
    """AC4/AC6."""
    response_mock = mocker.Mock()
    response_mock.json.return_value = [
        {"asset": "AAPL", "name": "Apple Inc.", "weightPercentage": 7.0, "updated": "2026-04-09 11:04:21"},
    ]
    response_mock.raise_for_status.return_value = None
    mocker.patch("app.clients.fmp.httpx.Client.get", return_value=response_mock)
    _mock_fmp_settings(
        mocker, fmp_cache_enabled=True, fmp_cache_dir=str(tmp_path), fmp_history_cache_ttl_seconds=86400
    )
    mocked_settings = mocker.patch("app.services.holdings_history.get_settings")
    mocked_settings.return_value.fmp_holdings_snapshot_dir = str(tmp_path / "holdings")

    service = MarketDataService()
    service.holdings_history = HoldingsHistoryStore(str(tmp_path / "holdings"))

    service.get_etf_holdings("XLK")
    first_meta = service.get_last_fetch_meta("XLK")
    service.get_etf_holdings("XLK")
    second_meta = service.get_last_fetch_meta("XLK")

    assert first_meta["cached"] is False
    assert second_meta["cached"] is True


def test_get_etf_holdings_for_date_inherits_cache_flag_via_delegation(mocker, tmp_path) -> None:
    """AC5 — the non-history-cache branch has no separate cache-flag
    implementation of its own; it delegates to `get_etf_holdings`, which
    already writes the right `last_fetch_meta`. Proven by spying on
    `get_etf_holdings` itself, not just matching its output."""
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.is_cached.return_value = True
    instance.get_etf_holders.return_value = [{"asset": "AAPL", "weightPercentage": 7.0}]

    mocked_settings = mocker.patch("app.services.holdings_history.get_settings")
    mocked_settings.return_value.fmp_holdings_snapshot_dir = str(tmp_path)

    service = MarketDataService()
    service.holdings_history = HoldingsHistoryStore(str(tmp_path))
    spy = mocker.spy(service, "get_etf_holdings")

    resolved_symbol, rows = service.get_etf_holdings_for_date("XLK", "2099-01-01")

    spy.assert_called_once_with("XLK", None)
    assert resolved_symbol == "XLK"
    assert rows == [{"asset": "AAPL", "weightPercentage": 7.0}]
    assert service.get_last_fetch_meta("XLK")["cached"] is True


def test_will_be_served_from_cache_delegates_to_fmp_client_is_cached(mocker) -> None:
    """AC7 — `MarketDataService._will_be_served_from_cache` must be a pure
    passthrough to `FmpClient.is_cached`, not a re-derivation of the cache-key
    formula. Proven structurally: the exact args passed through unchanged,
    and the return value passed straight back, not recomputed."""
    client_mock = mocker.patch("app.services.market_data.FmpClient")
    instance = client_mock.return_value
    instance.is_cached.return_value = True

    service = MarketDataService()
    result = service._will_be_served_from_cache(  # noqa: SLF001
        "quote", "quote-short", {"symbol": "AAPL"}, 300
    )

    assert result is True
    instance.is_cached.assert_called_once_with("quote", "quote-short", {"symbol": "AAPL"}, 300)

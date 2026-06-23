from datetime import date, datetime, timedelta

import pytest

from app.analytics import risk as risk_module
from app.analytics.activity import build_activity_series
from app.analytics.portfolio_imports import (
    apply_simulated_trades_to_state,
    build_performance_summary,
    build_portfolio_overview,
    build_rebalance_preview,
    build_reconciliation_summary,
    build_simulated_rebalance_trades,
    build_true_performance_series,
)
from app.analytics.risk import DEFAULT_FACTOR_DEFINITIONS, build_etf_overlap_pairs, build_factor_exposures, build_factor_registry, build_factor_shift_diagnostics, build_lookthrough_exposure, build_lookthrough_sector_exposure, build_market_overlap_summary, build_model_reliability_snapshot, build_portfolio_risk_summary, build_relative_risk_summary, build_risk_contribution_breakdown, build_rolling_risk_series, build_statistical_factor_model, build_stress_scenarios, build_volatility_regime_payload, is_history_series_verified_adjusted, select_history_price_series, selected_history_price_map
from app.analytics.risk import apply_return_basis_status_to_factor_model, apply_return_basis_status_to_model_reliability
from app.core.symbols import canonicalize_symbol
from app.domain.ledger import reconstruct_position_lots, snapshot_to_ledger
from app.engine.portfolio_state import PortfolioStateEngine
from app.importers.interactive_brokers import import_statement
from app.instruments import InstrumentRegistry
from app.schemas.imports import (
    ImportedCashBalance,
    ImportedInstrument,
    ImportedLedgerEntry,
    ImportedPortfolioSnapshot,
    ImportedPosition,
    ImportedStatement,
    ImportedStatementTotals,
)
from app.schemas.dashboard_history import DashboardHistoryEngineRequest
from app.schemas.diagnostics import DiagnosticsEngineRequest
from app.schemas.exposure import ExposureAvailability, ExposureCurrentStateConcentration, ExposureProvenance, ExposureResult, ExposureRunMetadata
from app.schemas.exposure import ExposureRunReproducibilityMetadata, ExposureRunSourceStatus
from app.schemas.portfolio_engine import PortfolioCashBalanceSnapshot, PortfolioHistoryContext, PortfolioPositionSnapshot
from app.schemas.reconciliation import DailyPortfolioState, DailyStatePosition, PerformancePoint, PortfolioRiskSummary
from app.schemas.reconciliation import LookThroughConstituent, LookThroughOverview, LookThroughSource, MarketOverlapSummary, PortfolioOverview
from app.services.dashboard_history_engine import (
    _allow_future_exact_slice_excess_return_output,
    _compute_future_exact_slice_excess_return_pct,
    run_dashboard_history_engine,
    run_imported_dashboard_history,
)
from app.services.diagnostics_engine import run_diagnostics_engine, run_imported_diagnostics_engine
from app.services.portfolio_proof import build_portfolio_proof_metadata
from app.services.exposure_engine import build_exposure_result
from app.services.import_engine import build_import_bootstrap_from_snapshot
from app.services.market_data import build_histories_return_basis_evidence, build_history_return_basis_evidence
from app.services.statement_importer import import_statements
from app.tests._statement_fixtures import (
    ESPP_PATH as ESPP_FIXTURE_PATH,
    FREEDOM24_PATH as FREEDOM24_FIXTURE_PATH,
    STATEMENT_2026_PATH as STATEMENT_2026_FIXTURE_PATH,
)


STATEMENT_2026_PATH = STATEMENT_2026_FIXTURE_PATH


FF2026_DASHBOARD_GOLDEN = {
    "account_id": "185960",
    "statement_period": "2025-12-31 - 2026-04-11",
    "summary": {
        "start_value": 4033.48,
        "end_value": 3071.00,
        "net_contributions": 0.0,
        "time_weighted_return_pct": None,
        "money_weighted_return_pct": -23.86,
        "max_drawdown_pct": None,
    },
    "monthly_returns": [
        ("2025-12", 0.14),
        ("2026-01", 0.95),
        ("2026-02", -0.81),
        ("2026-03", -3.90),
        ("2026-04", -22.04),
    ],
    "overview": {
        "total_market_value": 3018.96,
        "cash_by_currency": {"USD": 52.04, "EUR": 0.0},
        "broad_market_sector": "Broad Market",
        "vti_market_value": 3018.96,
        "vti_weight": 1.0,
    },
}


def _compute_dashboard_visible_summary(
    daily_states: list[DailyPortfolioState],
    performance_series: list,
    *,
    allow_compounded_return_outputs: bool = True,
) -> dict[str, float | None]:
    if not daily_states:
        return {
            "start_value": None,
            "end_value": None,
            "net_contributions": 0.0,
            "time_weighted_return_pct": None,
            "money_weighted_return_pct": None,
        }

    anchor_index = next((index for index, state in enumerate(daily_states) if state.total_portfolio_value > 0), 0)
    anchored_states = daily_states[anchor_index:]
    anchor_date = anchored_states[0].date if anchored_states else daily_states[0].date
    anchored_perf = [point for point in performance_series if point.date >= anchor_date]

    start_value = anchored_states[0].total_portfolio_value if anchored_states else None
    end_value = daily_states[-1].total_portfolio_value
    net_contributions = round(sum(state.external_cash_flow for state in anchored_states[1:]), 2) if anchored_states else 0.0
    time_weighted_return_pct = anchored_perf[-1].portfolio_return_pct if anchored_perf and allow_compounded_return_outputs else None

    money_weighted_return_pct = None
    if anchored_states and len(anchored_states) >= 2:
        flow_states = anchored_states[1:]
        total_flows = sum(state.external_cash_flow for state in flow_states)
        total_periods = max(len(anchored_states) - 1, 1)
        weighted_flows = sum(
            state.external_cash_flow * ((total_periods - index - 1) / total_periods)
            for index, state in enumerate(flow_states)
        )
        start_value_amount = start_value if start_value is not None else 0.0
        denominator = start_value_amount + weighted_flows
        if denominator != 0:
            money_weighted_return_pct = round(((end_value - start_value_amount - total_flows) / denominator) * 100, 2)

    return {
        "start_value": round(start_value, 2) if start_value is not None else None,
        "end_value": round(end_value, 2),
        "net_contributions": net_contributions,
        "time_weighted_return_pct": time_weighted_return_pct,
        "money_weighted_return_pct": money_weighted_return_pct,
    }


def _compute_dashboard_monthly_returns(daily_states: list[DailyPortfolioState]) -> list[tuple[str, float]]:
    anchor_index = next((index for index, state in enumerate(daily_states) if state.total_portfolio_value > 0), 0)
    anchored_states = daily_states[anchor_index:]
    if not anchored_states:
        return []

    grouped: dict[str, list[DailyPortfolioState]] = {}
    for state in anchored_states:
        grouped.setdefault(state.date[:7], []).append(state)

    monthly_returns: list[tuple[str, float]] = []
    for month, month_states in grouped.items():
        cumulative_growth = 1.0
        previous_state = None
        for state in month_states:
            if previous_state is not None and previous_state.total_portfolio_value != 0:
                daily_return = ((state.total_portfolio_value - state.external_cash_flow) / previous_state.total_portfolio_value) - 1
                cumulative_growth *= 1 + daily_return
            previous_state = state
        monthly_returns.append((month, round((cumulative_growth - 1) * 100, 2)))
    return monthly_returns


def _compute_dashboard_max_drawdown(performance_series: list, *, allow_drawdown_outputs: bool = True) -> float | None:
    if not allow_drawdown_outputs:
        return None
    peak = 0.0
    max_drawdown = 0.0
    for point in performance_series:
        peak = max(peak, point.portfolio_value)
        if peak > 0:
            max_drawdown = min(max_drawdown, ((point.portfolio_value - peak) / peak) * 100)
    return round(max_drawdown, 2)


def _mock_ib2026_dashboard_market_data(mocker, snapshot: ImportedPortfolioSnapshot) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    valuation_dates = [
        "2026-01-08",
        "2026-01-31",
        "2026-02-28",
        "2026-03-31",
        "2026-04-30",
    ]
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-01-08", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-01-31", "price": 101.5, "adjClose": 101.5},
        {"date": "2026-02-28", "price": 99.8, "adjClose": 99.8},
        {"date": "2026-03-31", "price": 98.4, "adjClose": 98.4},
        {"date": "2026-04-30", "price": 103.1, "adjClose": 103.1},
    ]
    service.get_last_fetch_meta.return_value = {
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
    service.get_historical_prices_for_symbols.return_value = {
        position.symbol: [
            {"date": valuation_date, "price": float(position.close_price), "basis": "broker_proven_mark_to_market"}
            for valuation_date in valuation_dates
        ]
        for position in snapshot.positions
    }


def _sample_snapshot() -> ImportedPortfolioSnapshot:
    return ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 1, 1),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2025",
            page_count=5,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            stock_total=1000.0,
            cash_total=200.0,
            dividends_total=50.0,
            withholding_tax_total=10.0,
            interest_total=5.0,
            other_fees_total=2.0,
            deposits_total=100.0,
            starting_nav=1100.0,
            ending_nav=1200.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=100.0, ending_cash=200.0)],
        positions=[ImportedPosition(as_of_date=date(2025, 12, 31), symbol="AAPL", quantity=10.0, cost_basis=800.0, close_price=100.0, market_value=1000.0, unrealized_pnl=200.0, currency="USD")],
        ledger_entries=[
            ImportedLedgerEntry(entry_type="DIVIDEND", trade_date=date(2025, 6, 1), symbol="AAPL", gross_amount=50.0, net_amount=50.0, currency="USD", source_section="Dividends"),
            ImportedLedgerEntry(entry_type="WITHHOLDING_TAX", trade_date=date(2025, 6, 1), symbol="AAPL", gross_amount=-10.0, net_amount=-10.0, currency="USD", source_section="Withholding Tax"),
            ImportedLedgerEntry(entry_type="INTEREST", trade_date=date(2025, 7, 1), gross_amount=5.0, net_amount=5.0, currency="USD", source_section="Interest"),
            ImportedLedgerEntry(entry_type="FEE", trade_date=date(2025, 8, 1), gross_amount=-2.0, net_amount=-2.0, currency="USD", source_section="Fees"),
            ImportedLedgerEntry(entry_type="DEPOSIT", trade_date=date(2025, 1, 2), gross_amount=100.0, net_amount=100.0, currency="USD", source_section="Deposits & Withdrawals"),
        ],
    )


def _sample_overview(snapshot: ImportedPortfolioSnapshot) -> PortfolioOverview:
    return PortfolioOverview(
        account_id=snapshot.statement.account_id,
        base_currency=snapshot.statement.base_currency,
        statement_period=snapshot.statement.statement_period,
        positions_count=len(snapshot.positions),
        instruments_count=len(snapshot.instruments),
        ledger_entries_count=len(snapshot.ledger_entries),
        total_market_value=sum(position.market_value for position in snapshot.positions),
        total_cost_basis=sum(position.cost_basis for position in snapshot.positions),
        total_unrealized_pnl=sum(position.unrealized_pnl for position in snapshot.positions),
        cash_by_currency={balance.currency: float(balance.ending_cash or 0) for balance in snapshot.cash_balances},
        top_positions=[],
        sector_allocation=[],
        sector_position_breakdown={},
        ledger_counts={},
        realized_cash_flow={},
    )


def _sample_exposure_result(snapshot: ImportedPortfolioSnapshot) -> ExposureResult:
    return ExposureResult(
        snapshot=snapshot,
        provenance=ExposureProvenance(
            snapshot_basis="snapshot_request",
            historical_basis="current_state_only",
            price_basis="not_applicable",
            note="Exposure is a current-state engine view built from the submitted snapshot and look-through resolution inputs. Historical diagnostics are separate.",
        ),
        run_metadata=ExposureRunMetadata(
            engine_id="exposure_engine_v1",
            methodology_id="exposure_current_state_methodology_v1",
            price_basis="not_applicable",
            source_status=ExposureRunSourceStatus(
                lookthrough_resolution="live",
                benchmark_holdings="verified",
            ),
            confidence="high",
            reproducibility=ExposureRunReproducibilityMetadata(
                input_imported_at="2026-01-01T00:00:00",
                snapshot_as_of_date="2025-12-31",
                benchmark_symbol="SPY",
                dataset_version="market_data_service_v1",
            ),
        ),
        overview=_sample_overview(snapshot),
        lookthrough=LookThroughOverview(
            portfolio_market_value=sum(position.market_value for position in snapshot.positions),
            covered_market_value=sum(position.market_value for position in snapshot.positions),
            coverage_ratio=1.0,
            etf_resolution={},
            uncovered_positions=[],
            top_constituents=[],
        ),
        lookthrough_sector_exposure=[],
        market_overlap=MarketOverlapSummary(
            benchmark_symbol="SPY",
            overlap_weight=0.0,
            active_share=1.0,
            portfolio_in_benchmark_weight=0.0,
            benchmark_covered_weight=1.0,
        ),
        current_state_concentration=ExposureCurrentStateConcentration(
            top_positions=[],
            top_sectors=[],
            top_1_position_weight=None,
            top_3_position_weight=None,
            top_5_position_weight=None,
            top_sector_weight=None,
            top_3_sector_weight=None,
            position_hhi=None,
            sector_hhi=None,
            effective_holdings=None,
        ),
        availability=ExposureAvailability(
            lookthrough_status="live",
            lookthrough_confidence="high",
            benchmark_overlap_status="live",
            benchmark_overlap_confidence="high",
            note=None,
        ),
    )


def test_build_portfolio_overview_returns_expected_totals() -> None:
    overview = build_portfolio_overview(_sample_snapshot())

    assert overview.total_market_value == 1000.0
    assert overview.total_unrealized_pnl == 200.0
    assert overview.positions_count == 1
    assert overview.cash_by_currency["USD"] == 200.0


def test_build_exposure_result_populates_structured_run_metadata(mocker) -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[],
        positions=[
            ImportedPosition(as_of_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=100.0, market_value=1000.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 10), symbol="VUAA", quantity=2.0, cost_basis=200.0, close_price=100.0, market_value=200.0, unrealized_pnl=0.0, currency="USD"),
        ],
        ledger_entries=[],
    )

    market_data = mocker.patch("app.services.exposure_engine.MarketDataService")
    service = market_data.return_value
    service.get_etf_holdings.side_effect = [
        ("SPY", [{"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 100.0}]),
        ("SPY", [{"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 100.0}]),
    ]
    service.get_company_profile.return_value = None

    result = build_exposure_result(snapshot, "SPY")

    assert result.run_metadata.source_status.model_dump() == {
        "lookthrough_resolution": "live",
        "benchmark_holdings": "verified",
    }
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": "2026-04-10",
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }


def test_build_exposure_result_marks_partial_lookthrough_and_unavailable_benchmark_holdings(mocker) -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[],
        positions=[
            ImportedPosition(as_of_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=100.0, market_value=1000.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 10), symbol="VUAA", quantity=2.0, cost_basis=200.0, close_price=100.0, market_value=200.0, unrealized_pnl=0.0, currency="USD"),
        ],
        ledger_entries=[],
    )

    market_data = mocker.patch("app.services.exposure_engine.MarketDataService")
    service = market_data.return_value
    service.get_etf_holdings.side_effect = [
        (None, []),
        (None, []),
    ]
    service.get_company_profile.return_value = None

    result = build_exposure_result(snapshot, "SPY")

    assert result.run_metadata.source_status.model_dump() == {
        "lookthrough_resolution": "partial",
        "benchmark_holdings": "unavailable",
    }
    assert result.availability.lookthrough_status == "partial"
    assert result.availability.benchmark_overlap_status == "unavailable"


def test_build_portfolio_overview_classifies_2026_ucits_and_thematic_holdings() -> None:
    snapshot = import_statement(STATEMENT_2026_PATH)

    overview = build_portfolio_overview(snapshot)

    assert "FICO" not in {position.symbol for position in snapshot.positions}
    # Statement updated 2026-06-12: DFND and IUIT were sold (they appear only in
    # the trade history, not as open positions); CIBR (First Trust Nasdaq
    # Cybersecurity UCITS, IE00BF16M727) is a new Technology holding.
    assert "DFND" not in {position.symbol for position in snapshot.positions}
    assert "IUIT" not in {position.symbol for position in snapshot.positions}
    assert any(item["symbol"] == "DEFS" for item in overview.sector_position_breakdown["Defense"])
    assert any(item["symbol"] == "IDFN" for item in overview.sector_position_breakdown["Defense"])
    assert any(item["symbol"] == "CIBR" for item in overview.sector_position_breakdown["Technology"])
    assert any(item["symbol"] == "SEMI" for item in overview.sector_position_breakdown["Technology"])
    assert any(item["symbol"] == "SXRV" for item in overview.sector_position_breakdown["Technology"])
    assert any(item["symbol"] == "VUAA" for item in overview.sector_position_breakdown["Broad Market"])
    assert any(item["symbol"] == "VDST" for item in overview.sector_position_breakdown["Fixed Income"])
    assert all(item["symbol"] != "IUFS" for item in overview.sector_position_breakdown.get("Financials", []))
    assert all(item["symbol"] != "IUHC" for item in overview.sector_position_breakdown.get("Health Care", []))


def test_attach_snapshot_metadata_classifies_isln_as_commodities() -> None:
    registry = InstrumentRegistry()
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[ImportedInstrument(symbol="ISLN", description="ISHARES PHYSICAL SILVER ETC", currency=None, instrument_type="ETF", listing_exchange="LSEETF")],
        cash_balances=[],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 10), symbol="ISLN", quantity=10.0, cost_basis=100.0, close_price=10.0, market_value=100.0, unrealized_pnl=0.0, currency="USD")],
        ledger_entries=[],
    )

    metadata = registry.attach_snapshot_metadata(snapshot)

    assert metadata["ISLN"].sector == "Commodities"
    assert metadata["ISLN"].category == "Commodity UCITS ETF"


def test_attach_snapshot_metadata_classifies_sxrv_as_technology() -> None:
    registry = InstrumentRegistry()
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[ImportedInstrument(symbol="SXRV", description="ISHARES NASDAQ 100 USD ACC", currency="EUR", instrument_type="ETF", listing_exchange="IBIS2")],
        cash_balances=[],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 10), symbol="SXRV", quantity=10.0, cost_basis=100.0, close_price=10.0, market_value=100.0, unrealized_pnl=0.0, currency="EUR")],
        ledger_entries=[],
    )

    metadata = registry.attach_snapshot_metadata(snapshot)

    assert metadata["SXRV"].sector == "Technology"
    assert metadata["SXRV"].category == "Thematic UCITS ETF"


def test_canonicalize_symbol_normalizes_lse_aliases() -> None:
    assert canonicalize_symbol("ISLN.L") == "ISLN"
    assert canonicalize_symbol("SGLD.L") == "SGLD"


def test_build_import_bootstrap_from_snapshot_merges_statement_windows_into_history_context(mocker) -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="combined.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2025-01-01 - 2026-04-08",
            page_count=2,
        ),
        statements=[
            ImportedStatement(
                importer="interactive_brokers",
                imported_at=datetime(2026, 1, 1),
                source_path="IB2025.pdf",
                detected_format="pdf",
                account_id="U123",
                base_currency="USD",
                statement_period="2025-01-01 - 2025-12-31",
                page_count=1,
            ),
            ImportedStatement(
                importer="interactive_brokers",
                imported_at=datetime(2026, 4, 10),
                source_path="IB2026.pdf",
                detected_format="pdf",
                account_id="U123",
                base_currency="USD",
                statement_period="2026-01-01 - 2026-04-08",
                page_count=1,
            ),
        ],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 8), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=110.0, market_value=110.0, unrealized_pnl=10.0, currency="USD")],
        ledger_entries=[],
    )
    mocker.patch("app.services.import_engine.build_exposure_result", return_value=_sample_exposure_result(snapshot))

    result = build_import_bootstrap_from_snapshot(snapshot, "SPY", {})

    assert result.history_context is not None
    assert result.history_context.statement_period == "2025-01-01 - 2026-04-08"
    assert result.history_context.source_file_names == ["IB2025.pdf", "IB2026.pdf"]
    assert result.history_context.history_start_date == "2025-01-01"
    assert result.history_context.history_end_date == "2026-04-08"
    assert result.risk_summary.start_date == "2025-01-01"
    assert result.risk_summary.end_date == "2026-04-08"


def test_build_import_bootstrap_from_snapshot_falls_back_to_ledger_and_position_dates_when_statement_period_missing(mocker) -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period=None,
            page_count=1,
        ),
        statements=[
            ImportedStatement(
                importer="interactive_brokers",
                imported_at=datetime(2026, 4, 10),
                source_path="snapshot.pdf",
                detected_format="pdf",
                account_id="U123",
                base_currency="USD",
                statement_period=None,
                page_count=1,
            ),
        ],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=50.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 10), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=110.0, market_value=110.0, unrealized_pnl=10.0, currency="USD")],
        ledger_entries=[
            ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 1, 15), symbol="AAPL", quantity=1.0, price=100.0, gross_amount=100.0, net_amount=100.0, currency="USD", source_section="Trades"),
        ],
    )
    mocker.patch("app.services.import_engine.build_exposure_result", return_value=_sample_exposure_result(snapshot))

    result = build_import_bootstrap_from_snapshot(snapshot, "SPY", {})

    assert result.history_context is not None
    assert result.history_context.statement_period is None
    assert result.history_context.history_start_date == "2026-01-15"
    assert result.history_context.history_end_date == "2026-04-10"
    assert result.risk_summary.start_date == "2026-01-15"
    assert result.risk_summary.end_date == "2026-04-10"


def test_run_dashboard_history_engine_returns_unavailable_without_complete_history_context(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    request = DashboardHistoryEngineRequest(
        benchmark_symbol="QQQ",
        base_currency="USD",
        statement_period="2025",
        imported_at=datetime(2026, 4, 10),
        importer="interactive_brokers",
        source_file_names=["IB2025.pdf"],
        positions=[],
        cash_balances=[],
        history_context=PortfolioHistoryContext(
            benchmark_symbol="SPY",
            history_start_date="2025-01-01",
            history_end_date=None,
        ),
    )

    result = run_dashboard_history_engine(request)

    assert result.daily_states == []
    assert result.performance_series == []
    assert result.source_status == {"performance_history": "unavailable", "monthly_returns": "unavailable"}
    assert result.run_metadata.source_status.model_dump() == {
        "performance_history": "unavailable",
        "monthly_returns": "unavailable",
        "benchmark_history": "unavailable",
    }
    assert result.run_metadata.return_basis_evidence.model_dump() == {
        "portfolio_path": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "benchmark_path": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
    }
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert result.run_metadata.investor_economics_partial_unlock.model_dump() == {
        "mode": "allowlisted_exact_slice_scalars_only",
        "exact_slice_scalar_allowlist": [
            {
                "field": "range_metrics[*].summary.time_weighted_return_pct",
                "unlock_condition": "identical_admitted_exact_slice_only",
                "runtime_enabled": True,
            },
            {
                "field": "range_metrics[*].summary.benchmark_return_pct",
                "unlock_condition": "identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only",
                "runtime_enabled": True,
            },
            {
                "field": "range_metrics[*].summary.excess_return_pct",
                "unlock_condition": "identical_admitted_exact_slice_pair_only",
                "runtime_enabled": True,
            },
        ],
        "client_derivation_rule": "server_side_scalar_only_no_daily_series_subtraction_equivalence",
        "withheld_families": [
            "benchmark_relative_series",
            "benchmark_relative_path_derived_outputs",
            "drawdown_family",
            "rebucketed_window_summaries",
            "rewindowed_range_summaries",
            "diagnostics_benchmark_relative_outputs",
            "replay_benchmark_relative_outputs",
            "strategy_lab_benchmark_relative_outputs",
        ],
    }
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": "2026-04-10",
        "history_start_date": "2025-01-01",
        "history_end_date": None,
        "benchmark_symbol": "QQQ",
        "dataset_version": "market_data_service_v1",
    }
    assert result.benchmark is None
    assert result.range_metrics is not None
    assert result.range_metrics["3M"].summary.start_value is None
    assert result.range_metrics["3M"].max_drawdown_pct is None
    assert result.range_metrics["3M"].monthly_returns == []
    market_data.assert_not_called()


def test_run_dashboard_history_engine_returns_unavailable_for_snapshot_only_requests(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    request = DashboardHistoryEngineRequest(
        benchmark_symbol="QQQ",
        base_currency="USD",
        statement_period="2025",
        imported_at=datetime(2026, 4, 10),
        importer="interactive_brokers",
        source_file_names=["IB2025.pdf"],
        positions=[PortfolioPositionSnapshot(symbol="AAPL", market_value=1000.0, quantity=10.0, currency="USD")],
        cash_balances=[PortfolioCashBalanceSnapshot(currency="USD", amount=100.0)],
        history_context=PortfolioHistoryContext(
            benchmark_symbol="SPY",
            history_start_date="2026-04-10",
            history_end_date="2026-04-11",
            source_file_names=["IB2025.pdf"],
        ),
    )

    result = run_dashboard_history_engine(request)

    assert result.source_status == {"performance_history": "unavailable", "monthly_returns": "unavailable"}
    assert result.run_metadata.source_status.model_dump() == {
        "performance_history": "unavailable",
        "monthly_returns": "unavailable",
        "benchmark_history": "unavailable",
    }
    assert result.run_metadata.return_basis_evidence.model_dump() == {
        "portfolio_path": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "benchmark_path": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
    }
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": "2026-04-10",
        "history_start_date": "2026-04-10",
        "history_end_date": "2026-04-11",
        "benchmark_symbol": "QQQ",
        "dataset_version": "market_data_service_v1",
    }
    assert result.benchmark is None
    assert result.daily_states == []
    assert result.performance_series == []
    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.start_value is None
    market_data.assert_not_called()


def test_run_diagnostics_engine_returns_unavailable_for_snapshot_only_requests(mocker) -> None:
    market_data = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    request = DiagnosticsEngineRequest(
        benchmark_symbol="SPY",
        base_currency="USD",
        statement_period="2026-04-10 - 2026-04-11",
        imported_at=datetime(2026, 4, 10),
        importer="interactive_brokers",
        source_file_names=["snapshot.json"],
        positions=[PortfolioPositionSnapshot(symbol="AAPL", market_value=1000.0, quantity=10.0, currency="USD")],
        cash_balances=[PortfolioCashBalanceSnapshot(currency="USD", amount=100.0)],
    )

    result = run_diagnostics_engine(request)

    assert result.availability.historical_sections_available is False
    assert result.availability.history_context_required is True
    assert result.availability.status == "unavailable"
    assert result.availability.note == "Historical diagnostics are unavailable from snapshot-only input. Attach PortfolioHistoryContext to run rolling diagnostics accurately."
    assert result.provenance.snapshot_basis == "snapshot_request"
    assert result.provenance.historical_basis == "unavailable"
    assert result.run_metadata.source_status.model_dump() == {
        "portfolio_history": "unavailable",
        "benchmark_history": "unavailable",
        "factor_history": "unavailable",
    }
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert result.run_metadata.investor_economics_partial_unlock.model_dump() == {
        "mode": "allowlisted_exact_slice_scalars_only",
        "exact_slice_scalar_allowlist": [
            {
                "field": "range_metrics[*].summary.time_weighted_return_pct",
                "unlock_condition": "identical_admitted_exact_slice_only",
                "runtime_enabled": True,
            },
            {
                "field": "range_metrics[*].summary.benchmark_return_pct",
                "unlock_condition": "identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only",
                "runtime_enabled": True,
            },
            {
                "field": "range_metrics[*].summary.excess_return_pct",
                "unlock_condition": "identical_admitted_exact_slice_pair_only",
                "runtime_enabled": True,
            },
        ],
        "client_derivation_rule": "server_side_scalar_only_no_daily_series_subtraction_equivalence",
        "withheld_families": [
            "benchmark_relative_series",
            "benchmark_relative_path_derived_outputs",
            "drawdown_family",
            "rebucketed_window_summaries",
            "rewindowed_range_summaries",
            "diagnostics_benchmark_relative_outputs",
            "replay_benchmark_relative_outputs",
            "strategy_lab_benchmark_relative_outputs",
        ],
    }
    market_data.assert_not_called()


def test_run_diagnostics_engine_uses_history_context_for_snapshot_requests(mocker) -> None:
    market_data = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service = market_data.return_value
    service.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 101.0},
        {"date": "2026-04-14", "price": 102.0},
        {"date": "2026-04-15", "price": 103.0},
        {"date": "2026-04-16", "price": 104.0},
        {"date": "2026-04-17", "price": 105.0},
        {"date": "2026-04-18", "price": 106.0},
        {"date": "2026-04-21", "price": 107.0},
        {"date": "2026-04-22", "price": 108.0},
        {"date": "2026-04-23", "price": 109.0},
    ]
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 100.0},
            {"date": "2026-04-11", "price": 101.0},
            {"date": "2026-04-14", "price": 102.0},
            {"date": "2026-04-15", "price": 103.0},
            {"date": "2026-04-16", "price": 104.0},
            {"date": "2026-04-17", "price": 105.0},
            {"date": "2026-04-18", "price": 106.0},
            {"date": "2026-04-21", "price": 107.0},
            {"date": "2026-04-22", "price": 108.0},
            {"date": "2026-04-23", "price": 109.0},
        ],
        "SPY": [
            {"date": "2026-04-10", "price": 100.0},
            {"date": "2026-04-11", "price": 100.5},
            {"date": "2026-04-14", "price": 101.0},
            {"date": "2026-04-15", "price": 101.5},
            {"date": "2026-04-16", "price": 102.0},
            {"date": "2026-04-17", "price": 102.5},
            {"date": "2026-04-18", "price": 103.0},
            {"date": "2026-04-21", "price": 103.5},
            {"date": "2026-04-22", "price": 104.0},
            {"date": "2026-04-23", "price": 104.5},
        ],
        **{definition.us_proxy: [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 100.1}, {"date": "2026-04-14", "price": 100.2}, {"date": "2026-04-15", "price": 100.3}, {"date": "2026-04-16", "price": 100.4}, {"date": "2026-04-17", "price": 100.5}, {"date": "2026-04-18", "price": 100.6}, {"date": "2026-04-21", "price": 100.7}, {"date": "2026-04-22", "price": 100.8}, {"date": "2026-04-23", "price": 100.9}] for definition in DEFAULT_FACTOR_DEFINITIONS},
    }

    request = DiagnosticsEngineRequest(
        benchmark_symbol="SPY",
        base_currency="USD",
        statement_period="2026-04-10 - 2026-04-23",
        imported_at=datetime(2026, 4, 23),
        importer="interactive_brokers",
        source_file_names=["snapshot.json"],
        positions=[PortfolioPositionSnapshot(symbol="AAPL", market_value=1000.0, quantity=10.0, currency="USD")],
        cash_balances=[PortfolioCashBalanceSnapshot(currency="USD", amount=100.0)],
        history_context=PortfolioHistoryContext(
            benchmark_symbol="SPY",
            history_start_date="2026-04-10",
            history_end_date="2026-04-23",
        ),
    )

    result = run_diagnostics_engine(request)

    assert result.availability.historical_sections_available is True
    assert result.availability.history_context_required is True
    assert result.provenance.snapshot_basis == "snapshot_request"
    assert result.provenance.historical_basis == "market_data_history"
    assert result.drawdown_summary.current_drawdown_pct is None
    assert result.drawdown_summary.max_drawdown_pct is None
    assert result.volatility_regime.snapshot.current_drawdown_pct is None
    assert result.volatility_regime.snapshot.max_drawdown_pct is None
    assert result.volatility_summary.portfolio_volatility_pct == result.risk_summary.portfolio_volatility_pct
    assert result.volatility_summary.benchmark_volatility_pct == result.risk_summary.benchmark_volatility_pct
    assert result.volatility_summary.downside_volatility_pct == result.volatility_regime.snapshot.downside_vol_60d
    assert result.volatility_summary.tracking_error_pct == result.relative_risk.tracking_error_pct
    assert result.risk_concentration_summary.factor_hhi == result.risk_contribution_breakdown.concentration.factor_hhi
    assert result.risk_concentration_summary.position_hhi == result.risk_contribution_breakdown.concentration.position_hhi
    assert result.risk_summary.observations > 0
    assert result.statistical_factor_model.windows


def test_variant_snapshot_diagnostics_history_stays_in_plausible_bounds() -> None:
    ib_2026_path = STATEMENT_2026_PATH
    ff_2026_path = FREEDOM24_FIXTURE_PATH
    espp_2026_path = ESPP_FIXTURE_PATH

    snapshot = import_statements([str(espp_2026_path), str(ff_2026_path), str(ib_2026_path)])
    modified_positions = []
    for position in snapshot.positions:
        payload = position.model_dump()
        if payload['symbol'] == 'DFND':
            payload['market_value'] = 6500.0
        modified_positions.append(PortfolioPositionSnapshot(symbol=payload['symbol'], market_value=payload['market_value'], quantity=payload.get('quantity'), currency=payload.get('currency')))

    request = DiagnosticsEngineRequest(
        benchmark_symbol='SPY',
        base_currency=snapshot.statement.base_currency,
        statement_period=snapshot.statement.statement_period,
        imported_at=snapshot.statement.imported_at,
        importer=snapshot.statement.importer,
        source_file_names=['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'],
        positions=modified_positions,
        cash_balances=[PortfolioCashBalanceSnapshot(currency=balance.currency, amount=balance.ending_cash or 0.0) for balance in snapshot.cash_balances],
        history_context=PortfolioHistoryContext(
            benchmark_symbol='SPY',
            statement_period=snapshot.statement.statement_period,
            imported_at=snapshot.statement.imported_at,
            importer=snapshot.statement.importer,
            source_file_names=['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'],
            history_start_date='2026-01-02',
            history_end_date='2026-04-10',
        ),
    )

    result = run_diagnostics_engine(request)

    assert result.availability.historical_sections_available is True
    assert result.availability.history_context_required is True
    assert result.provenance.snapshot_basis == "snapshot_request"
    assert result.provenance.historical_basis == "market_data_history"
    assert result.risk_summary.observations > 20
    assert result.risk_summary.portfolio_beta is not None
    assert abs(result.risk_summary.portfolio_beta) < 10
    assert result.relative_risk.tracking_error_pct is not None
    assert result.relative_risk.tracking_error_pct < 500
    assert result.volatility_regime.snapshot.realized_vol_20d is not None
    assert result.volatility_regime.snapshot.realized_vol_20d < 500
    growth_snapshot = next((item for item in result.statistical_factor_model.current_factor_snapshot if item.key == 'growth'), None)
    assert growth_snapshot is not None
    assert growth_snapshot.latest_loading is not None


def test_run_imported_diagnostics_engine_returns_unavailable_without_imported_history_dates(mocker) -> None:
    market_data = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=1000.0)],
        positions=[],
        ledger_entries=[],
    )

    result = run_imported_diagnostics_engine(snapshot, "SPY")

    assert result.availability.historical_sections_available is False
    assert result.availability.history_context_required is False
    assert result.availability.note == "Historical diagnostics are unavailable because this imported snapshot does not contain enough broker history to reconstruct a historical portfolio path."
    assert result.provenance.snapshot_basis == "imported_snapshot"
    assert result.provenance.historical_basis == "unavailable"
    assert result.provenance.note == "Historical diagnostics are unavailable because imported broker history could not be reconstructed from this snapshot."
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": None,
        "history_start_date": None,
        "history_end_date": None,
        "dataset_version": "market_data_service_v1",
    }
    assert result.run_metadata.factor_model_parameters.model_dump() == {
        "rolling_windows_days": [20, 60, 252],
        "current_reliability_window_days": 60,
        "minimum_window_observations": {"20": 25, "60": 75, "252": 275},
        "collinearity_warning_threshold": 0.85,
        "orthogonalization_basis": "factor_proxy_definition_order",
        "ridge_lambda": 1e-05,
    }
    assert result.run_metadata.source_status.model_dump() == {
        "portfolio_history": "unavailable",
        "benchmark_history": "unavailable",
        "factor_history": "unavailable",
    }
    assert result.run_metadata.return_basis_evidence.model_dump() == {
        "portfolio_history": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "benchmark_history": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "factor_history": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
    }
    portfolio_proof = result.run_metadata.portfolio_proof.model_dump()
    assert portfolio_proof["admission"]["readiness_status"] == "not_applicable"
    assert {key: value for key, value in portfolio_proof["admission"].items() if key != "readiness_status"} == {
        "status": "not_applicable",
        "scope": {
            "account_id": None,
            "base_currency": None,
            "history_source": "unavailable",
            "valuation_window_start": None,
            "valuation_window_end": None,
            "valuation_date_count": 0,
            "statement_window_start": None,
            "statement_window_end": None,
            "statement_window_count": 0,
        },
        "blocking_reasons": [
            {
                "code": "portfolio_history_unavailable",
                "bucket": "portfolio_admission",
                "provenance_bucket": "portfolio_history",
                "reason_type": "missing",
            }
        ],
        "missing_proof_buckets": [
            "boundary_hardening",
            "capital_boundary_proof",
            "corporate_action_proof",
            "fx_proof",
            "investor_economics_proof",
            "opening_state_admission",
            "return_basis_metadata",
            "valuation_basis_separation",
        ],
        "bucket_decisions": [
            {
                "bucket": bucket,
                "status": "not_applicable",
                "blocks_admission": True,
                "provenance_buckets": [bucket],
                "blocking_reasons": ["portfolio_history_unavailable"],
                "scope": {
                    "account_id": None,
                    "base_currency": None,
                    "history_source": "unavailable",
                    "valuation_window_start": None,
                    "valuation_window_end": None,
                    "valuation_date_count": 0,
                    "statement_window_start": None,
                    "statement_window_end": None,
                    "statement_window_count": 0,
                },
            }
            for bucket in [
                "return_basis_metadata",
                "capital_boundary_proof",
                "valuation_basis_separation",
                "boundary_hardening",
                "opening_state_admission",
                "fx_proof",
                "corporate_action_proof",
                "investor_economics_proof",
            ]
        ],
    }
    proof_without_admission = {key: value for key, value in portfolio_proof.items() if key != "admission"}
    preparation = proof_without_admission.pop("preparation")
    assert proof_without_admission == {
        "proof_system": "portfolio_verified_total_return_v1",
        "portfolio_path": "unavailable",
        "verification_status": "unavailable",
        "output_status": "unavailable",
        "replay_status": "replay_unavailable",
        "opening_state_status": "opening_state_unavailable",
        "verified_total_return_emitted": False,
        "benchmark_proof_independent": True,
        "disqualifiers": ["portfolio_history_unavailable"],
        "hard_disqualifiers": ["portfolio_history_unavailable"],
        "evidence": {
            "opening_state_basis": {
                "status": "disqualified",
                "positive_evidence": [],
                "negative_evidence": ["portfolio_history_unavailable"],
                "disqualifiers": ["portfolio_history_unavailable"],
                "hard_disqualifiers": ["portfolio_history_unavailable"],
                "witnesses": [],
            },
            "valuation_basis": {
                "status": "disqualified",
                "positive_evidence": [],
                "negative_evidence": ["portfolio_history_unavailable"],
                "disqualifiers": ["portfolio_history_unavailable"],
                "hard_disqualifiers": ["portfolio_history_unavailable"],
                "witnesses": [],
            },
            "cash_flow_basis": {
                "status": "disqualified",
                "positive_evidence": [],
                "negative_evidence": ["portfolio_history_unavailable"],
                "disqualifiers": ["portfolio_history_unavailable"],
                "hard_disqualifiers": ["portfolio_history_unavailable"],
                "witnesses": [],
            },
            "fx_basis": {
                "status": "disqualified",
                "positive_evidence": [],
                "negative_evidence": ["portfolio_history_unavailable"],
                "disqualifiers": ["portfolio_history_unavailable"],
                "hard_disqualifiers": ["portfolio_history_unavailable"],
                "witnesses": [],
            },
            "corporate_action_basis": {
                "status": "disqualified",
                "policy": {
                    "scope": "broker_scope_unproven",
                    "cash_dividend_coverage_status": "cash_dividend_coverage_unproven",
                    "cash_dividend_observation_status": "cash_dividend_observation_unproven",
                    "non_dividend_status": "non_dividend_corporate_actions_unproven_and_disqualifying",
                    "scope_start_date": None,
                    "scope_end_date": None,
                    "statement_window_count": 0,
                },
                "positive_evidence": [],
                "negative_evidence": ["portfolio_history_unavailable"],
                "disqualifiers": ["portfolio_history_unavailable"],
                "hard_disqualifiers": ["portfolio_history_unavailable"],
                "witnesses": [],
            },
            "terminal_reconciliation_basis": {
                "status": "disqualified",
                "positive_evidence": [],
                "negative_evidence": ["portfolio_history_unavailable"],
                "disqualifiers": ["portfolio_history_unavailable"],
                "hard_disqualifiers": ["portfolio_history_unavailable"],
                "witnesses": [],
            },
            "calendar_coverage_basis": {
                "status": "disqualified",
                "positive_evidence": [],
                "negative_evidence": ["portfolio_history_unavailable"],
                "disqualifiers": ["portfolio_history_unavailable"],
                "hard_disqualifiers": ["portfolio_history_unavailable"],
                "witnesses": [],
            },
            "investor_economics_proof": {
                "status": "unavailable",
                "claim_id": "portfolio_investor_economics_proof_v1",
                "claim": "For a specific portfolio account set, base currency, valuation window, and statement window, the computed portfolio wealth path is proven enough to support investor-economics outputs that require portfolio total-return equivalence.",
                "decision": "not_applicable",
                "preparation_status": "not_applicable",
                "required_inputs": [
                    "capital_boundary_proof",
                    "valuation_basis_proof",
                    "boundary_calendar_terminal_proof",
                    "opening_state_proof",
                    "fx_proof",
                    "corporate_action_proof",
                    "cross_bucket_scope_consistency",
                ],
                "positive_evidence": [],
                "negative_evidence": ["portfolio_history_unavailable"],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [],
                "blocking_reasons": ["portfolio_history_unavailable"],
                "missing_proof_buckets": [
                    "capital_boundary_proof",
                    "valuation_basis_proof",
                    "boundary_calendar_terminal_proof",
                    "opening_state_proof",
                    "fx_proof",
                    "corporate_action_proof",
                    "cross_bucket_scope_consistency",
                ],
                "scope_mismatches": [],
                "scope": {
                    "account_id": None,
                    "base_currency": None,
                    "history_source": "unavailable",
                    "valuation_window_start": None,
                    "valuation_window_end": None,
                    "valuation_date_count": 0,
                    "statement_window_start": None,
                    "statement_window_end": None,
                    "statement_window_count": 0,
                },
            },
        },
    }
    assert preparation == {
        "readiness_status": "not_applicable",
        "all_prerequisite_buckets_supported": False,
        "exact_slice_target": {
            "account_set": [],
            "base_currency": None,
            "valuation_window": {"start_date": None, "end_date": None, "count": 0},
            "statement_window": {"start_date": None, "end_date": None, "count": 0},
            "opening_state_anchor": {
                "required_anchor_date": None,
                "observed_anchor_date": None,
                "status": "unavailable",
            },
            "fx_scope": {
                "translation_case": "unavailable",
                "base_currency": None,
                "observed_currencies": [],
                "required_pairs": [],
                "required_pair_dates": [],
            },
            "corporate_action_scope": {
                "scope": "broker_scope_unproven",
                "scope_start_date": None,
                "scope_end_date": None,
                "statement_window_count": 0,
                "positive_proof_classes": ["cash_dividend"],
                "unproven_disqualifying_classes": [
                    "splits",
                    "reverse_splits",
                    "spin_offs",
                    "mergers",
                    "rights",
                    "return_of_capital",
                    "symbol_changes",
                ],
            },
        },
        "readiness_gaps": [
            {
                "code": "portfolio_history_unavailable",
                "bucket": "portfolio_history",
                "provenance_buckets": ["portfolio_history"],
                "gap_type": "missing",
            }
        ],
        "policy_blockers": [],
    }
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert result.drawdown_summary.current_drawdown_pct is None
    assert result.drawdown_summary.max_drawdown_pct is None
    assert result.volatility_summary.portfolio_volatility_pct is None
    assert result.volatility_summary.tracking_error_pct is None
    assert result.risk_concentration_summary.factor_hhi is None
    assert result.risk_concentration_summary.position_hhi is None
    assert result.risk_summary.benchmark_symbol == "SPY"
    assert result.risk_summary.observations == 0
    assert result.rolling_risk == []
    assert result.statistical_factor_model.status == "unavailable"
    market_data.assert_not_called()


def test_run_imported_diagnostics_engine_populates_history_derived_summary_fields(mocker) -> None:
    market_data = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service = market_data.return_value
    service.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 101.0},
        {"date": "2026-04-14", "price": 102.0},
        {"date": "2026-04-15", "price": 103.0},
        {"date": "2026-04-16", "price": 104.0},
        {"date": "2026-04-17", "price": 105.0},
        {"date": "2026-04-18", "price": 106.0},
        {"date": "2026-04-21", "price": 107.0},
        {"date": "2026-04-22", "price": 108.0},
        {"date": "2026-04-23", "price": 109.0},
    ]
    service.get_historical_prices_for_symbols.side_effect = [
        {
            "AAPL": [
                {"date": "2026-04-10", "price": 100.0},
                {"date": "2026-04-11", "price": 101.0},
                {"date": "2026-04-14", "price": 102.0},
                {"date": "2026-04-15", "price": 103.0},
                {"date": "2026-04-16", "price": 104.0},
                {"date": "2026-04-17", "price": 105.0},
                {"date": "2026-04-18", "price": 106.0},
                {"date": "2026-04-21", "price": 107.0},
                {"date": "2026-04-22", "price": 108.0},
                {"date": "2026-04-23", "price": 109.0},
            ]
        },
        {
            definition.us_proxy: [
                {"date": "2026-04-10", "price": 100.0},
                {"date": "2026-04-11", "price": 100.1},
                {"date": "2026-04-14", "price": 100.2},
                {"date": "2026-04-15", "price": 100.3},
                {"date": "2026-04-16", "price": 100.4},
                {"date": "2026-04-17", "price": 100.5},
                {"date": "2026-04-18", "price": 100.6},
                {"date": "2026-04-21", "price": 100.7},
                {"date": "2026-04-22", "price": 100.8},
                {"date": "2026-04-23", "price": 100.9},
            ]
            for definition in DEFAULT_FACTOR_DEFINITIONS
        },
    ]
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-23",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 23), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=109.0, market_value=1090.0, unrealized_pnl=90.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_diagnostics_engine(snapshot, "SPY")

    assert result.availability.historical_sections_available is True
    assert result.provenance.snapshot_basis == "imported_snapshot"
    assert result.provenance.historical_basis == "imported_portfolio_history"
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-23T00:00:00",
        "snapshot_as_of_date": "2026-04-23",
        "history_start_date": "2026-04-10",
        "history_end_date": "2026-04-23",
        "dataset_version": "market_data_service_v1",
    }
    assert result.run_metadata.factor_model_parameters.model_dump() == {
        "rolling_windows_days": [20, 60, 252],
        "current_reliability_window_days": 60,
        "minimum_window_observations": {"20": 25, "60": 75, "252": 275},
        "collinearity_warning_threshold": 0.85,
        "orthogonalization_basis": "factor_proxy_definition_order",
        "ridge_lambda": 1e-05,
    }
    assert result.run_metadata.source_status.model_dump() == {
        "portfolio_history": "imported_replay",
        "benchmark_history": "live_market_data_unverified_return_basis",
        "factor_history": "live_market_data_unverified_return_basis",
    }
    assert result.run_metadata.return_basis_evidence.model_dump() == {
        "portfolio_history": {
            "verification_status": "unverified",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_portfolio_return_basis_proof"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "benchmark_history": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
        "factor_history": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
    }
    portfolio_proof = result.run_metadata.portfolio_proof.model_dump()
    assert portfolio_proof["admission"]["status"] == "withheld"
    assert portfolio_proof["admission"]["readiness_status"] == "exact_slice_prerequisites_incomplete"
    assert portfolio_proof["admission"]["missing_proof_buckets"] == [
        "boundary_calendar_terminal_proof",
        "boundary_hardening",
        "investor_economics_proof",
        "opening_state_admission",
        "opening_state_proof",
        "return_basis_metadata",
        "valuation_basis_proof",
        "valuation_basis_separation",
    ]
    assert portfolio_proof["admission"]["bucket_decisions"][0] == {
        "bucket": "return_basis_metadata",
        "status": "withheld",
        "blocks_admission": True,
        "provenance_buckets": ["valuation_basis"],
        "blocking_reasons": [
            "raw_price_used_for_valuation",
            "return_basis_positive_support_missing_for_portfolio_slice",
        ],
        "scope": {
            "base_currency": "USD",
            "history_source": "imported_replay",
            "valuation_window_start": "2026-04-10",
            "valuation_window_end": "2026-04-23",
            "valuation_date_count": 10,
        },
    }
    assert portfolio_proof["admission"]["bucket_decisions"][5] == {
        "bucket": "fx_proof",
        "status": "withheld",
        "blocks_admission": False,
        "provenance_buckets": ["fx_basis"],
        "blocking_reasons": [],
        "scope": {
            "base_currency": "USD",
            "valuation_window_start": "2026-04-10",
            "valuation_window_end": "2026-04-23",
            "valuation_date_count": 10,
        },
    }
    assert portfolio_proof["admission"]["bucket_decisions"][7] == {
        "bucket": "investor_economics_proof",
        "status": "withheld",
        "blocks_admission": True,
        "provenance_buckets": [
            "boundary_calendar_terminal_proof",
            "capital_boundary_proof",
            "corporate_action_proof",
            "cross_bucket_scope_consistency",
            "fx_proof",
            "opening_state_proof",
            "valuation_basis_proof",
        ],
        "blocking_reasons": [
            "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
            "opening_cash_state_missing",
            "opening_state_positive_support_missing_for_portfolio_slice",
            "opening_state_unverified_for_portfolio_slice",
            "raw_price_used_for_valuation",
            "return_basis_positive_support_missing_for_portfolio_slice",
            "valuation_basis_positive_support_missing_for_portfolio_slice",
        ],
        "scope": {
            "account_id": "U123",
            "base_currency": "USD",
            "history_source": "imported_replay",
            "valuation_window_start": "2026-04-10",
            "valuation_window_end": "2026-04-23",
            "valuation_date_count": 10,
            "statement_window_start": "2026-04-10",
            "statement_window_end": "2026-04-23",
            "statement_window_count": 1,
        },
    }
    proof_without_admission = {key: value for key, value in portfolio_proof.items() if key != "admission"}
    preparation = proof_without_admission.pop("preparation")
    evidence = proof_without_admission.pop("evidence")
    assert proof_without_admission == {
        "proof_system": "portfolio_verified_total_return_v1",
        "portfolio_path": "withheld",
        "verification_status": "unverified",
        "output_status": "withheld",
        "replay_status": "replay_usable",
        "opening_state_status": "opening_state_unverified",
        "verified_total_return_emitted": False,
        "benchmark_proof_independent": True,
        "disqualifiers": [
            "opening_cash_state_missing",
            "portfolio_verified_total_return_withheld",
            "raw_price_used_for_valuation",
        ],
        "hard_disqualifiers": [
            "opening_cash_state_missing",
            "raw_price_used_for_valuation",
        ],
    }
    assert evidence["opening_state_basis"] == {
                "status": "disqualified",
                "positive_evidence": [
                    "broker_ledger_entries_available",
                    "broker_statement_account_id_available",
                    "broker_statement_base_currency_available",
                    "opening_holdings_covered_by_observed_trade_window",
                    "opening_quantities_covered_by_observed_trade_window",
                    "opening_timestamp_semantics_backed_by_broker_statement_period",
                ],
                "negative_evidence": ["opening_cash_state_missing_broker_evidence"],
                "disqualifiers": ["opening_cash_state_missing"],
                "hard_disqualifiers": ["opening_cash_state_missing"],
                "witnesses": [
                    {
                        "label": "opening_account_identity",
                        "status": "broker_proven",
                        "evidence": ["accepted_source:broker_statement_account_id"],
                        "counts": {},
                    },
                    {
                        "label": "opening_base_currency_state",
                        "status": "broker_proven",
                        "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                        "counts": {},
                    },
                    {
                        "label": "opening_cash_state",
                        "status": "missing_broker_evidence",
                        "evidence": ["accepted_source_missing:broker_cash_report_starting_cash"],
                        "counts": {},
                    },
                    {
                        "label": "opening_holdings_state",
                        "status": "trade_window_covered",
                        "evidence": ["accepted_source:broker_trade_window_opening_holdings"],
                        "counts": {"covered_symbol_count": 1},
                    },
                    {
                        "label": "opening_quantities_state",
                        "status": "trade_window_covered",
                        "evidence": ["accepted_source:broker_trade_window_opening_quantities"],
                        "counts": {"covered_symbol_count": 1},
                    },
                    {
                        "label": "opening_timestamp_semantics",
                        "status": "broker_statement_period_boundary",
                        "evidence": ["accepted_source:broker_statement_period_boundary:2026-04-10"],
                        "counts": {"statement_window_count": 1},
                    },
                    {
                        "label": "opening_state_admission",
                        "status": "opening_state_unverified",
                        "evidence": [
                            "replay_status:replay_usable",
                            "proof_eligibility_blocked_until_opening_state_verified",
                        ],
                        "counts": {},
                    },
                ],
            }
    assert evidence["valuation_basis"] == {
                "status": "disqualified",
                "positive_evidence": ["valuation_dates_available", "position_price_histories_loaded"],
                "negative_evidence": ["vendor_raw_price_used_for_valuation"],
                "disqualifiers": ["raw_price_used_for_valuation"],
                "hard_disqualifiers": ["raw_price_used_for_valuation"],
                "witnesses": [
                    {
                        "label": "valuation_input_policy",
                        "status": "explicit_withholding_contract",
                        "evidence": [
                            "proof_eligible:broker_proven_mark_to_market_inputs",
                            "replay_only:raw_vendor_price",
                            "replay_only:forward_fill",
                            "replay_only:synthetic_snapshot_history",
                            "replay_only:snapshot_fallback",
                            "replay_only:other_fallback_construction",
                            "replay_only:mixed_basis_construction",
                            "verified_total_return_withheld_when_any_replay_only_valuation_input_is_observed",
                        ],
                        "counts": {"proof_eligible_input_types": 1, "replay_only_input_types": 6},
                    },
                    {
                        "label": "valuation_history_construction",
                        "status": "imported_replay",
                        "evidence": ["valuation_states_replayed_from_imported_broker_activity"],
                        "counts": {"valuation_date_count": 10},
                    },
                    {
                        "label": "valuation_window_basis:2026-04-10:2026-04-23",
                        "status": "raw_vendor_price",
                        "evidence": [
                            "valuation_window_dates:2026-04-10->2026-04-23",
                            "valuation_window_uses:raw_vendor_price",
                        ],
                        "counts": {"valuation_date_count": 10, "valued_symbol_count": 10, "raw_vendor_price": 10},
                    },
                ],
            }
    assert evidence["cash_flow_basis"] == {
                "status": "supported",
                "positive_evidence": [
                    "broker_ledger_entries_available",
                    "cash_movement_entries_classified_with_broker_native_evidence",
                ],
                "negative_evidence": [],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "cash_flow_classification",
                        "status": "not_observed",
                        "evidence": ["no_broker_proven_external_capital_flow_entries_observed"],
                        "counts": {"external_capital_flow": 0},
                    },
                    {
                        "label": "internal_trading_flow_classification",
                        "status": "broker_proven",
                        "evidence": ["broker_trade_ledger_line"],
                        "counts": {"internal_trading_flow": 1},
                    },
                    {
                        "label": "broker_explicit_income_expense_classification",
                        "status": "not_observed",
                        "evidence": ["no_broker_explicit_income_or_expense_cash_flows_observed"],
                        "counts": {
                            "broker_explicit_dividend": 0,
                            "broker_explicit_interest": 0,
                            "broker_explicit_fee": 0,
                            "broker_explicit_tax": 0,
                        },
                    },
                    {
                        "label": "unknown_cash_flow_classification",
                        "status": "none_observed",
                        "evidence": ["no_unknown_cash_flow_entries_observed"],
                        "counts": {"unknown": 0},
                    },
                ],
            }
    assert evidence["fx_basis"] == {
                "status": "supported",
                "positive_evidence": ["all_observed_statement_currencies_match_base_currency"],
                "negative_evidence": [],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "fx_base_currency_state",
                        "status": "broker_proven",
                        "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                        "counts": {},
                    },
                    {
                        "label": "fx_currency_observation_scope",
                        "status": "observed_currency_scope",
                        "evidence": [
                            "observed_statement_currencies:USD",
                            "observed_cash_currencies:USD",
                            "observed_ledger_currencies:USD",
                            "observed_position_currencies:USD",
                        ],
                        "counts": {
                            "statement_currency_count": 1,
                            "cash_currency_count": 1,
                            "ledger_currency_count": 1,
                            "position_currency_count": 1,
                            "observed_currency_count": 1,
                        },
                    },
                    {
                        "label": "fx_translation_requirement",
                        "status": "identity_case_supported",
                        "evidence": ["all_observed_currencies_equal_base:USD"],
                        "counts": {"observed_currency_count": 1},
                    },
                ],
            }
    assert evidence["corporate_action_basis"] == {
                "status": "supported",
                "policy": {
                    "scope": "broker_native_statement_window",
                    "cash_dividend_coverage_status": "cash_dividend_coverage_proven_by_broker_native_evidence",
                    "cash_dividend_observation_status": "no_cash_dividend_observed_within_covered_broker_scope",
                    "non_dividend_status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                    "scope_start_date": "2026-04-10",
                    "scope_end_date": "2026-04-23",
                    "statement_window_count": 1,
                },
                "positive_evidence": [
                    "cash_dividend_coverage_proven_by_broker_native_evidence",
                    "no_cash_dividend_observed_within_covered_broker_scope",
                    "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                ],
                "negative_evidence": [],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "corporate_action_basis_policy",
                        "status": "cash_dividend_scope_only",
                        "evidence": [
                            "positive_proof_limited_to:cash_dividend",
                            "coverage_and_absence_semantics_require:broker_native_statement_window",
                            "positive_observation_requires:broker_dividend_section_line_within_statement_window",
                            "non_dividend_corporate_actions_remain_unproven_and_disqualifying",
                        ],
                        "counts": {"statement_window_count": 1},
                    },
                    {
                        "label": "cash_dividend_coverage_scope",
                        "status": "cash_dividend_coverage_proven_by_broker_native_evidence",
                        "evidence": ["broker_native_statement_windows:2026-04-10->2026-04-23"],
                        "counts": {"statement_window_count": 1},
                    },
                    {
                        "label": "cash_dividend_observation_scope",
                        "status": "no_cash_dividend_observed_within_covered_broker_scope",
                        "evidence": ["no_broker_native_dividend_rows_observed_within_statement_window_scope"],
                        "counts": {"broker_native_dividend_count": 0},
                    },
                    {
                        "label": "non_dividend_corporate_action_scope",
                        "status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                        "evidence": [
                            "supported_non_dividend_classes:none_observed_within_broker_native_statement_window",
                            "unresolved_non_dividend_classes_would_remain_blocking:splits,reverse_splits,spin_offs,mergers,rights,return_of_capital,symbol_changes",
                        ],
                        "counts": {},
                    },
                ],
            }
    assert evidence["terminal_reconciliation_basis"] == {
                "status": "supported",
                "positive_evidence": ["terminal_replay_state_available"],
                "negative_evidence": ["terminal_statement_totals_not_available_for_comparison"],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "terminal_reconciliation_basis",
                        "status": "terminal_statement_totals_missing",
                        "evidence": ["terminal_statement_totals_not_available_for_comparison"],
                        "counts": {"compared_field_count": 0},
                    }
                ],
            }
    assert evidence["calendar_coverage_basis"] == {
                "status": "supported",
                "positive_evidence": [
                    "valuation_window_dates_available",
                    "valuation_dates_are_sorted_and_unique",
                    "broker_statement_period_windows_available",
                    "broker_statement_calendar_continuity_observed",
                    "replay_window_within_broker_statement_boundaries",
                ],
                "negative_evidence": [
                    "valuation_calendar_is_derived_from_benchmark_history",
                ],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "first_covered_date_basis",
                        "status": "broker_statement_period_boundary",
                        "evidence": ["broker_statement_period_first_covered_date:2026-04-10"],
                        "counts": {},
                    },
                    {
                        "label": "last_covered_date_basis",
                        "status": "broker_statement_period_boundary",
                        "evidence": ["broker_statement_period_last_covered_date:2026-04-23"],
                        "counts": {},
                    },
                    {
                        "label": "replay_derived_window:2026-04-10:2026-04-23",
                        "status": "replay_derived_window",
                        "evidence": ["replay_window_dates:2026-04-10->2026-04-23"],
                        "counts": {"valuation_date_count": 10},
                    },
                    {
                        "label": "calendar_continuity_basis",
                        "status": "broker_statement_period_contiguous",
                        "evidence": ["broker_statement_calendar_window:2026-04-10->2026-04-23"],
                        "counts": {"statement_window_count": 1, "gap_count": 0},
                    },
                    {
                        "label": "broker_covered_window:2026-04-10:2026-04-23",
                        "status": "broker_covered_window",
                        "evidence": ["broker_statement_period_window:2026-04-10->2026-04-23"],
                        "counts": {"valuation_date_count": 10},
                    },
                ],
            }
    assert preparation["readiness_status"] == "exact_slice_prerequisites_incomplete"
    assert preparation["all_prerequisite_buckets_supported"] is False
    assert preparation["exact_slice_target"] == {
        "account_set": ["U123"],
        "base_currency": "USD",
        "valuation_window": {"start_date": "2026-04-10", "end_date": "2026-04-23", "count": 10},
        "statement_window": {"start_date": "2026-04-10", "end_date": "2026-04-23", "count": 1},
        "opening_state_anchor": {
            "required_anchor_date": "2026-04-10",
            "observed_anchor_date": "2026-04-10",
            "status": "disqualified",
        },
        "fx_scope": {
            "translation_case": "identity_base_currency_only",
            "base_currency": "USD",
            "observed_currencies": ["USD"],
            "required_pairs": [],
            "required_pair_dates": [],
        },
        "corporate_action_scope": {
            "scope": "broker_native_statement_window",
            "scope_start_date": "2026-04-10",
            "scope_end_date": "2026-04-23",
            "statement_window_count": 1,
            "positive_proof_classes": ["cash_dividend"],
            "unproven_disqualifying_classes": [
                "splits",
                "reverse_splits",
                "spin_offs",
                "mergers",
                "rights",
                "return_of_capital",
                "symbol_changes",
            ],
        },
    }
    assert [gap["code"] for gap in preparation["readiness_gaps"]] == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "opening_cash_state_missing",
        "opening_state_positive_support_missing_for_portfolio_slice",
        "opening_state_unverified_for_portfolio_slice",
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "valuation_basis_positive_support_missing_for_portfolio_slice",
    ]
    assert preparation["policy_blockers"] == []
    investor_proof = portfolio_proof["evidence"]["investor_economics_proof"]
    assert investor_proof["status"] == "disqualified"
    assert investor_proof["decision"] == "withheld"
    assert investor_proof["preparation_status"] == "exact_slice_prerequisites_incomplete"
    assert investor_proof["positive_evidence"] == []
    assert investor_proof["negative_evidence"] == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "opening_cash_state_missing",
        "opening_state_positive_support_missing_for_portfolio_slice",
        "opening_state_unverified_for_portfolio_slice",
        "portfolio_claim_not_inferred_from_benchmark_allowlist_verification",
        "portfolio_claim_not_inferred_from_replay_usability_or_history_availability",
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "valuation_basis_positive_support_missing_for_portfolio_slice",
    ]
    assert investor_proof["disqualifiers"] == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "opening_cash_state_missing",
        "opening_state_positive_support_missing_for_portfolio_slice",
        "opening_state_unverified_for_portfolio_slice",
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "valuation_basis_positive_support_missing_for_portfolio_slice",
    ]
    assert investor_proof["hard_disqualifiers"] == investor_proof["disqualifiers"]
    assert investor_proof["blocking_reasons"] == investor_proof["disqualifiers"]
    assert investor_proof["missing_proof_buckets"] == [
        "boundary_calendar_terminal_proof",
        "opening_state_proof",
        "valuation_basis_proof",
    ]
    assert investor_proof["scope_mismatches"] == []
    assert [witness["label"] for witness in investor_proof["witnesses"]] == [
        "prerequisite:capital_boundary_proof",
        "prerequisite:valuation_basis_proof",
        "prerequisite:boundary_calendar_terminal_proof",
        "prerequisite:opening_state_proof",
        "prerequisite:fx_proof",
        "prerequisite:corporate_action_proof",
        "scope:account_set",
        "scope:base_currency",
        "scope:valuation_window",
        "scope:statement_window",
        "scope:opening_state_anchor",
        "scope:fx_scope",
        "scope:corporate_action_scope",
        "exact_slice_admission_policy",
        "benchmark_scope_transfer_policy",
    ]
    assert result.run_metadata.section_trust.model_dump() == {
        "benchmark_relative_path": "degraded_unverified_return_basis",
        "factor_model_path": "degraded_unverified_return_basis",
        "risk_contribution_path": "degraded_unverified_return_basis",
    }
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert result.run_metadata.confidence == "low"
    assert result.statistical_factor_model.status == "insufficient_history"
    assert result.model_reliability.status == "insufficient_history"
    assert result.risk_contribution_breakdown.status == "insufficient_history"
    assert result.provenance.note.endswith(
        "Benchmark and factor return histories remain unverified for adjusted-close or total-return equivalence in this diagnostics slice."
    )
    assert result.drawdown_summary.current_drawdown_pct is None
    assert result.drawdown_summary.max_drawdown_pct is None
    assert result.volatility_regime.snapshot.current_drawdown_pct is None
    assert result.volatility_regime.snapshot.max_drawdown_pct is None
    assert result.relative_risk.active_return_pct is None
    assert result.relative_risk.information_ratio is None
    assert result.volatility_summary.portfolio_volatility_pct == result.risk_summary.portfolio_volatility_pct
    assert result.volatility_summary.benchmark_volatility_pct == result.risk_summary.benchmark_volatility_pct
    assert result.volatility_summary.downside_volatility_pct == result.volatility_regime.snapshot.downside_vol_60d
    assert result.volatility_summary.tracking_error_pct == result.relative_risk.tracking_error_pct
    assert result.risk_concentration_summary.top_1_factor_risk_share == result.risk_contribution_breakdown.concentration.top_1_factor_risk_share
    assert result.risk_concentration_summary.top_3_factor_risk_share == result.risk_contribution_breakdown.concentration.top_3_factor_risk_share
    assert result.risk_concentration_summary.top_1_position_risk_share == result.risk_contribution_breakdown.concentration.top_1_position_risk_share
    assert result.risk_concentration_summary.top_5_position_risk_share == result.risk_contribution_breakdown.concentration.top_5_position_risk_share
    assert result.risk_concentration_summary.factor_hhi == result.risk_contribution_breakdown.concentration.factor_hhi
    assert result.risk_concentration_summary.position_hhi == result.risk_contribution_breakdown.concentration.position_hhi
def test_run_imported_diagnostics_engine_marks_verified_adjusted_close_when_all_history_rows_have_adjusted_fields(mocker) -> None:
    market_data = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service = market_data.return_value
    service.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 99.5},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 100.4},
    ]
    service.get_historical_prices_for_symbols.side_effect = [
        {
            "AAPL": [
                {"date": "2026-04-10", "price": 100.0, "adjClose": 99.5},
                {"date": "2026-04-11", "price": 101.0, "adjClose": 100.4},
            ]
        },
        {
            "SPY": [
                {"date": "2026-04-10", "price": 100.0, "adjClose": 99.5},
                {"date": "2026-04-11", "price": 101.0, "adjClose": 100.4},
            ],
            "QQQ": [
                {"date": "2026-04-10", "price": 200.0, "adjusted_close": 198.0},
                {"date": "2026-04-11", "price": 202.0, "adjusted_close": 199.5},
            ],
        },
    ]
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_diagnostics_engine(snapshot, "SPY")

    assert result.run_metadata.source_status.model_dump() == {
        "portfolio_history": "imported_replay",
        "benchmark_history": "live_market_data_verified_adjusted_close",
        "factor_history": "live_market_data_verified_adjusted_close",
    }
    assert result.run_metadata.section_trust.model_dump() == {
        "benchmark_relative_path": "verified_adjusted_close",
        "factor_model_path": "verified_adjusted_close",
        "risk_contribution_path": "verified_adjusted_close",
    }
    assert result.drawdown_summary.current_drawdown_pct is None
    assert result.drawdown_summary.max_drawdown_pct is None
    assert result.volatility_regime.snapshot.current_drawdown_pct is None
    assert result.volatility_regime.snapshot.max_drawdown_pct is None
    assert result.relative_risk.active_return_pct is None
    assert result.relative_risk.information_ratio is None
    assert result.statistical_factor_model.status != "degraded_unverified_return_basis"
    assert result.model_reliability.status != "degraded_unverified_return_basis"
    assert result.risk_contribution_breakdown.status != "degraded_unverified_return_basis"


def test_run_imported_diagnostics_engine_keeps_unverified_status_when_any_factor_history_lacks_adjusted_fields(mocker) -> None:
    market_data = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service = market_data.return_value
    service.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 99.5},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 100.4},
    ]
    service.get_historical_prices_for_symbols.side_effect = [
        {
            "AAPL": [
                {"date": "2026-04-10", "price": 100.0, "adjClose": 99.5},
                {"date": "2026-04-11", "price": 101.0, "adjClose": 100.4},
            ]
        },
        {
            "QQQ": [
                {"date": "2026-04-10", "price": 200.0},
                {"date": "2026-04-11", "price": 202.0},
            ],
        },
    ]
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_diagnostics_engine(snapshot, "SPY")

    assert result.run_metadata.source_status.model_dump() == {
        "portfolio_history": "imported_replay",
        "benchmark_history": "live_market_data_verified_adjusted_close",
        "factor_history": "live_market_data_unverified_return_basis",
    }
    assert result.run_metadata.section_trust.model_dump() == {
        "benchmark_relative_path": "verified_adjusted_close",
        "factor_model_path": "degraded_unverified_return_basis",
        "risk_contribution_path": "degraded_unverified_return_basis",
    }
    assert result.drawdown_summary.current_drawdown_pct is None
    assert result.drawdown_summary.max_drawdown_pct is None
    assert result.volatility_regime.snapshot.current_drawdown_pct is None
    assert result.volatility_regime.snapshot.max_drawdown_pct is None
    assert result.relative_risk.active_return_pct is None
    assert result.relative_risk.information_ratio is None
    assert result.statistical_factor_model.status == "insufficient_history"
    assert result.model_reliability.status == "insufficient_history"
    assert result.risk_contribution_breakdown.status == "insufficient_history"


def test_run_imported_diagnostics_engine_refuses_drawdown_family_even_when_history_is_available(mocker) -> None:
    market_data = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service = market_data.return_value
    service.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 105.0},
        {"date": "2026-04-14", "price": 104.0},
    ]
    service.get_historical_prices_for_symbols.side_effect = [
        {
            "AAPL": [
                {"date": "2026-04-10", "price": 100.0},
                {"date": "2026-04-11", "price": 110.0},
                {"date": "2026-04-14", "price": 105.0},
            ]
        },
        {
            definition.us_proxy: [
                {"date": "2026-04-10", "price": 100.0},
                {"date": "2026-04-11", "price": 101.0},
                {"date": "2026-04-14", "price": 99.0},
            ]
            for definition in DEFAULT_FACTOR_DEFINITIONS
        },
    ]
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 14),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-14",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 14), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=105.0, market_value=1050.0, unrealized_pnl=50.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_diagnostics_engine(snapshot, "SPY")

    assert result.drawdown_summary.current_drawdown_pct is None
    assert result.drawdown_summary.max_drawdown_pct is None
    assert result.volatility_regime.snapshot.current_drawdown_pct is None
    assert result.volatility_regime.snapshot.max_drawdown_pct is None
    assert result.relative_risk.active_return_pct is None
    assert result.relative_risk.information_ratio is None
    assert all(point.drawdown_pct is None for point in result.volatility_regime.rolling_series)
    assert all(point.wealth_index is None for point in result.volatility_regime.rolling_series)


def test_run_imported_dashboard_history_returns_unavailable_without_imported_history_dates(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=1000.0)],
        positions=[],
        ledger_entries=[],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.source_status == {"performance_history": "unavailable", "monthly_returns": "unavailable"}
    assert result.run_metadata.source_status.model_dump() == {
        "performance_history": "unavailable",
        "monthly_returns": "unavailable",
        "benchmark_history": "unavailable",
    }
    assert result.run_metadata.return_basis_evidence.model_dump() == {
        "portfolio_path": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "benchmark_path": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
    }
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": None,
        "history_start_date": None,
        "history_end_date": None,
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }
    assert result.benchmark is None
    assert result.daily_states == []
    assert result.performance_series == []
    assert result.range_metrics is not None
    assert result.range_metrics["3M"].summary.start_value is None
    assert result.range_metrics["3M"].summary.end_value is None
    assert result.range_metrics["3M"].monthly_returns == []
    assert result.range_metrics["3M"].monthly_returns_reliable is False
    market_data.assert_not_called()


def test_run_imported_dashboard_history_uses_imported_snapshot_ledger_and_returns_live_result(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 120.0},
    ]
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0},
            {"date": "2026-04-11", "price": 115.0},
        ],
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    service.get_direct_verified_benchmark_history.assert_called_once_with("SPY", "2026-04-10", "2026-04-11")
    assert result.source_status == {"performance_history": "live", "monthly_returns": "live"}
    assert result.run_metadata.source_status.model_dump() == {
        "performance_history": "live",
        "monthly_returns": "live",
        "benchmark_history": "live_market_data_unverified_return_basis",
    }
    assert result.run_metadata.section_trust.model_dump() == {
        "portfolio_path": "imported_replay",
        "benchmark_path": "degraded_unverified_return_basis",
        "monthly_returns_path": "imported_replay",
    }
    assert result.run_metadata.return_basis_contract.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "price_return_only",
    }
    assert result.run_metadata.return_basis_evidence.model_dump() == {
        "portfolio_path": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
        "benchmark_path": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
    }
    portfolio_proof = result.run_metadata.portfolio_proof.model_dump()
    assert portfolio_proof["admission"]["status"] == "withheld"
    assert portfolio_proof["admission"]["readiness_status"] == "exact_slice_prerequisites_incomplete"
    assert portfolio_proof["admission"]["missing_proof_buckets"] == [
        "boundary_calendar_terminal_proof",
        "boundary_hardening",
        "investor_economics_proof",
        "opening_state_admission",
        "opening_state_proof",
        "return_basis_metadata",
        "valuation_basis_proof",
        "valuation_basis_separation",
    ]
    assert portfolio_proof["admission"]["bucket_decisions"][0]["blocking_reasons"] == [
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
    ]
    assert portfolio_proof["admission"]["bucket_decisions"][6]["blocking_reasons"] == []
    assert portfolio_proof["admission"]["bucket_decisions"][7]["blocking_reasons"] == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "opening_cash_state_missing",
        "opening_state_positive_support_missing_for_portfolio_slice",
        "opening_state_unverified_for_portfolio_slice",
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "valuation_basis_positive_support_missing_for_portfolio_slice",
    ]
    proof_without_admission = {key: value for key, value in portfolio_proof.items() if key != "admission"}
    preparation = proof_without_admission.pop("preparation")
    evidence = proof_without_admission.pop("evidence")
    assert proof_without_admission == {
        "proof_system": "portfolio_verified_total_return_v1",
        "portfolio_path": "withheld",
        "verification_status": "unverified",
        "output_status": "withheld",
        "replay_status": "replay_usable",
        "opening_state_status": "opening_state_unverified",
        "verified_total_return_emitted": False,
        "benchmark_proof_independent": True,
        "disqualifiers": [
            "opening_cash_state_missing",
            "portfolio_verified_total_return_withheld",
            "raw_price_used_for_valuation",
        ],
        "hard_disqualifiers": [
            "opening_cash_state_missing",
            "raw_price_used_for_valuation",
        ],
    }
    assert evidence["opening_state_basis"] == {
                "status": "disqualified",
                "positive_evidence": [
                    "broker_ledger_entries_available",
                    "broker_statement_account_id_available",
                    "broker_statement_base_currency_available",
                    "opening_holdings_covered_by_observed_trade_window",
                    "opening_quantities_covered_by_observed_trade_window",
                    "opening_timestamp_semantics_backed_by_broker_statement_period",
                ],
                "negative_evidence": ["opening_cash_state_missing_broker_evidence"],
                "disqualifiers": ["opening_cash_state_missing"],
                "hard_disqualifiers": ["opening_cash_state_missing"],
                "witnesses": [
                    {
                        "label": "opening_account_identity",
                        "status": "broker_proven",
                        "evidence": ["accepted_source:broker_statement_account_id"],
                        "counts": {},
                    },
                    {
                        "label": "opening_base_currency_state",
                        "status": "broker_proven",
                        "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                        "counts": {},
                    },
                    {
                        "label": "opening_cash_state",
                        "status": "missing_broker_evidence",
                        "evidence": ["accepted_source_missing:broker_cash_report_starting_cash"],
                        "counts": {},
                    },
                    {
                        "label": "opening_holdings_state",
                        "status": "trade_window_covered",
                        "evidence": ["accepted_source:broker_trade_window_opening_holdings"],
                        "counts": {"covered_symbol_count": 1},
                    },
                    {
                        "label": "opening_quantities_state",
                        "status": "trade_window_covered",
                        "evidence": ["accepted_source:broker_trade_window_opening_quantities"],
                        "counts": {"covered_symbol_count": 1},
                    },
                    {
                        "label": "opening_timestamp_semantics",
                        "status": "broker_statement_period_boundary",
                        "evidence": ["accepted_source:broker_statement_period_boundary:2026-04-10"],
                        "counts": {"statement_window_count": 1},
                    },
                    {
                        "label": "opening_state_admission",
                        "status": "opening_state_unverified",
                        "evidence": [
                            "replay_status:replay_usable",
                            "proof_eligibility_blocked_until_opening_state_verified",
                        ],
                        "counts": {},
                    },
                ],
            }
    assert evidence["valuation_basis"] == {
                "status": "disqualified",
                "positive_evidence": ["valuation_dates_available", "position_price_histories_loaded"],
                "negative_evidence": ["vendor_raw_price_used_for_valuation"],
                "disqualifiers": ["raw_price_used_for_valuation"],
                "hard_disqualifiers": ["raw_price_used_for_valuation"],
                "witnesses": [
                    {
                        "label": "valuation_input_policy",
                        "status": "explicit_withholding_contract",
                        "evidence": [
                            "proof_eligible:broker_proven_mark_to_market_inputs",
                            "replay_only:raw_vendor_price",
                            "replay_only:forward_fill",
                            "replay_only:synthetic_snapshot_history",
                            "replay_only:snapshot_fallback",
                            "replay_only:other_fallback_construction",
                            "replay_only:mixed_basis_construction",
                            "verified_total_return_withheld_when_any_replay_only_valuation_input_is_observed",
                        ],
                        "counts": {"proof_eligible_input_types": 1, "replay_only_input_types": 6},
                    },
                    {
                        "label": "valuation_history_construction",
                        "status": "imported_replay",
                        "evidence": ["valuation_states_replayed_from_imported_broker_activity"],
                        "counts": {"valuation_date_count": 2},
                    },
                    {
                        "label": "valuation_window_basis:2026-04-10:2026-04-11",
                        "status": "raw_vendor_price",
                        "evidence": [
                            "valuation_window_dates:2026-04-10->2026-04-11",
                            "valuation_window_uses:raw_vendor_price",
                        ],
                        "counts": {"valuation_date_count": 2, "valued_symbol_count": 2, "raw_vendor_price": 2},
                    },
                ],
            }
    assert evidence["cash_flow_basis"] == {
                "status": "supported",
                "positive_evidence": [
                    "broker_ledger_entries_available",
                    "cash_movement_entries_classified_with_broker_native_evidence",
                ],
                "negative_evidence": [],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "cash_flow_classification",
                        "status": "not_observed",
                        "evidence": ["no_broker_proven_external_capital_flow_entries_observed"],
                        "counts": {"external_capital_flow": 0},
                    },
                    {
                        "label": "internal_trading_flow_classification",
                        "status": "broker_proven",
                        "evidence": ["broker_trade_ledger_line"],
                        "counts": {"internal_trading_flow": 1},
                    },
                    {
                        "label": "broker_explicit_income_expense_classification",
                        "status": "not_observed",
                        "evidence": ["no_broker_explicit_income_or_expense_cash_flows_observed"],
                        "counts": {
                            "broker_explicit_dividend": 0,
                            "broker_explicit_interest": 0,
                            "broker_explicit_fee": 0,
                            "broker_explicit_tax": 0,
                        },
                    },
                    {
                        "label": "unknown_cash_flow_classification",
                        "status": "none_observed",
                        "evidence": ["no_unknown_cash_flow_entries_observed"],
                        "counts": {"unknown": 0},
                    },
                ],
            }
    assert evidence["fx_basis"] == {
                "status": "supported",
                "positive_evidence": ["all_observed_statement_currencies_match_base_currency"],
                "negative_evidence": [],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "fx_base_currency_state",
                        "status": "broker_proven",
                        "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                        "counts": {},
                    },
                    {
                        "label": "fx_currency_observation_scope",
                        "status": "observed_currency_scope",
                        "evidence": [
                            "observed_statement_currencies:USD",
                            "observed_cash_currencies:USD",
                            "observed_ledger_currencies:USD",
                            "observed_position_currencies:USD",
                        ],
                        "counts": {
                            "statement_currency_count": 1,
                            "cash_currency_count": 1,
                            "ledger_currency_count": 1,
                            "position_currency_count": 1,
                            "observed_currency_count": 1,
                        },
                    },
                    {
                        "label": "fx_translation_requirement",
                        "status": "identity_case_supported",
                        "evidence": ["all_observed_currencies_equal_base:USD"],
                        "counts": {"observed_currency_count": 1},
                    },
                ],
            }
    assert evidence["corporate_action_basis"] == {
                "status": "supported",
                "policy": {
                    "scope": "broker_native_statement_window",
                    "cash_dividend_coverage_status": "cash_dividend_coverage_proven_by_broker_native_evidence",
                    "cash_dividend_observation_status": "no_cash_dividend_observed_within_covered_broker_scope",
                    "non_dividend_status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                    "scope_start_date": "2026-04-10",
                    "scope_end_date": "2026-04-11",
                    "statement_window_count": 1,
                },
                "positive_evidence": [
                    "cash_dividend_coverage_proven_by_broker_native_evidence",
                    "no_cash_dividend_observed_within_covered_broker_scope",
                    "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                ],
                "negative_evidence": [],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "corporate_action_basis_policy",
                        "status": "cash_dividend_scope_only",
                        "evidence": [
                            "positive_proof_limited_to:cash_dividend",
                            "coverage_and_absence_semantics_require:broker_native_statement_window",
                            "positive_observation_requires:broker_dividend_section_line_within_statement_window",
                            "non_dividend_corporate_actions_remain_unproven_and_disqualifying",
                        ],
                        "counts": {"statement_window_count": 1},
                    },
                    {
                        "label": "cash_dividend_coverage_scope",
                        "status": "cash_dividend_coverage_proven_by_broker_native_evidence",
                        "evidence": ["broker_native_statement_windows:2026-04-10->2026-04-11"],
                        "counts": {"statement_window_count": 1},
                    },
                    {
                        "label": "cash_dividend_observation_scope",
                        "status": "no_cash_dividend_observed_within_covered_broker_scope",
                        "evidence": ["no_broker_native_dividend_rows_observed_within_statement_window_scope"],
                        "counts": {"broker_native_dividend_count": 0},
                    },
                    {
                        "label": "non_dividend_corporate_action_scope",
                        "status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                        "evidence": [
                            "supported_non_dividend_classes:none_observed_within_broker_native_statement_window",
                            "unresolved_non_dividend_classes_would_remain_blocking:splits,reverse_splits,spin_offs,mergers,rights,return_of_capital,symbol_changes",
                        ],
                        "counts": {},
                    },
                ],
            }
    assert evidence["terminal_reconciliation_basis"] == {
                "status": "supported",
                "positive_evidence": ["terminal_replay_state_available"],
                "negative_evidence": ["terminal_statement_totals_not_available_for_comparison"],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "terminal_reconciliation_basis",
                        "status": "terminal_statement_totals_missing",
                        "evidence": ["terminal_statement_totals_not_available_for_comparison"],
                        "counts": {"compared_field_count": 0},
                    }
                ],
            }
    assert evidence["calendar_coverage_basis"] == {
                "status": "supported",
                "positive_evidence": [
                    "valuation_window_dates_available",
                    "valuation_dates_are_sorted_and_unique",
                    "broker_statement_period_windows_available",
                    "broker_statement_calendar_continuity_observed",
                    "replay_window_within_broker_statement_boundaries",
                ],
                "negative_evidence": ["valuation_calendar_is_derived_from_benchmark_history"],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "first_covered_date_basis",
                        "status": "broker_statement_period_boundary",
                        "evidence": ["broker_statement_period_first_covered_date:2026-04-10"],
                        "counts": {},
                    },
                    {
                        "label": "last_covered_date_basis",
                        "status": "broker_statement_period_boundary",
                        "evidence": ["broker_statement_period_last_covered_date:2026-04-11"],
                        "counts": {},
                    },
                    {
                        "label": "replay_derived_window:2026-04-10:2026-04-11",
                        "status": "replay_derived_window",
                        "evidence": ["replay_window_dates:2026-04-10->2026-04-11"],
                        "counts": {"valuation_date_count": 2},
                    },
                    {
                        "label": "calendar_continuity_basis",
                        "status": "broker_statement_period_contiguous",
                        "evidence": ["broker_statement_calendar_window:2026-04-10->2026-04-11"],
                        "counts": {"statement_window_count": 1, "gap_count": 0},
                    },
                    {
                        "label": "broker_covered_window:2026-04-10:2026-04-11",
                        "status": "broker_covered_window",
                        "evidence": ["broker_statement_period_window:2026-04-10->2026-04-11"],
                        "counts": {"valuation_date_count": 2},
                    },
                ],
            }
    investor_proof = portfolio_proof["evidence"]["investor_economics_proof"]
    assert investor_proof["status"] == "disqualified"
    assert investor_proof["decision"] == "withheld"
    assert investor_proof["preparation_status"] == "exact_slice_prerequisites_incomplete"
    assert investor_proof["blocking_reasons"] == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "opening_cash_state_missing",
        "opening_state_positive_support_missing_for_portfolio_slice",
        "opening_state_unverified_for_portfolio_slice",
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "valuation_basis_positive_support_missing_for_portfolio_slice",
    ]
    assert investor_proof["missing_proof_buckets"] == [
        "boundary_calendar_terminal_proof",
        "opening_state_proof",
        "valuation_basis_proof",
    ]
    assert investor_proof["scope_mismatches"] == []
    assert preparation["readiness_status"] == "exact_slice_prerequisites_incomplete"
    assert preparation["all_prerequisite_buckets_supported"] is False
    assert preparation["exact_slice_target"] == {
        "account_set": ["U123"],
        "base_currency": "USD",
        "valuation_window": {"start_date": "2026-04-10", "end_date": "2026-04-11", "count": 2},
        "statement_window": {"start_date": "2026-04-10", "end_date": "2026-04-11", "count": 1},
        "opening_state_anchor": {
            "required_anchor_date": "2026-04-10",
            "observed_anchor_date": "2026-04-10",
            "status": "disqualified",
        },
        "fx_scope": {
            "translation_case": "identity_base_currency_only",
            "base_currency": "USD",
            "observed_currencies": ["USD"],
            "required_pairs": [],
            "required_pair_dates": [],
        },
        "corporate_action_scope": {
            "scope": "broker_native_statement_window",
            "scope_start_date": "2026-04-10",
            "scope_end_date": "2026-04-11",
            "statement_window_count": 1,
            "positive_proof_classes": ["cash_dividend"],
            "unproven_disqualifying_classes": [
                "splits",
                "reverse_splits",
                "spin_offs",
                "mergers",
                "rights",
                "return_of_capital",
                "symbol_changes",
            ],
        },
    }
    assert [gap["code"] for gap in preparation["readiness_gaps"]] == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "opening_cash_state_missing",
        "opening_state_positive_support_missing_for_portfolio_slice",
        "opening_state_unverified_for_portfolio_slice",
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "valuation_basis_positive_support_missing_for_portfolio_slice",
    ]
    assert [witness["label"] for witness in investor_proof["witnesses"]] == [
        "prerequisite:capital_boundary_proof",
        "prerequisite:valuation_basis_proof",
        "prerequisite:boundary_calendar_terminal_proof",
        "prerequisite:opening_state_proof",
        "prerequisite:fx_proof",
        "prerequisite:corporate_action_proof",
        "scope:account_set",
        "scope:base_currency",
        "scope:valuation_window",
        "scope:statement_window",
        "scope:opening_state_anchor",
        "scope:fx_scope",
        "scope:corporate_action_scope",
        "exact_slice_admission_policy",
        "benchmark_scope_transfer_policy",
    ]
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": "2026-04-11",
        "history_start_date": "2026-04-10",
        "history_end_date": "2026-04-11",
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }
    assert result.benchmark is not None
    assert result.benchmark.symbol == "SPY"
    assert len(result.daily_states) == 2
    assert len(result.performance_series) == 2
    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.time_weighted_return_pct is None
    assert result.range_metrics["All"].summary.end_value == result.daily_states[-1].total_portfolio_value
    assert result.range_metrics["All"].summary.benchmark_return_pct is None
    assert result.range_metrics["All"].summary.excess_return_pct is None
    assert result.range_metrics["All"].max_drawdown_pct is None
    assert result.benchmark is not None
    assert result.benchmark.return_pct is None
    assert result.benchmark.return_basis_contract == "price_return_only"


def test_run_imported_dashboard_history_enables_verified_benchmark_only_for_direct_spy_fmp_slice(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 101.5},
    ]
    service.get_last_fetch_meta.return_value = {
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
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0},
            {"date": "2026-04-11", "price": 115.0},
        ],
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    service.get_direct_verified_benchmark_history.assert_called_once_with("SPY", "2026-04-10", "2026-04-11")
    service.get_historical_prices.assert_not_called()
    assert result.run_metadata.return_basis_contract.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "verified_total_return",
    }
    assert result.run_metadata.return_basis_evidence.benchmark_path.model_dump() == {
        "verification_status": "verified",
        "economic_basis": "total_return",
        "construction_method": "vendor_adjusted_close",
        "disqualifiers": [],
        "fallbacks_used": [],
        "source_price_field": "adjClose",
        "scope": {
            "symbol": "SPY",
            "requested_symbol": "SPY",
            "resolved_symbol": "SPY",
            "vendor": "FMP",
            "endpoint": "historical-price-eod/light",
            "direct_path_only": True,
            "fallback_used": False,
            "symbol_override_used": False,
            "window_start": "2026-04-10",
            "window_end": "2026-04-11",
            "row_count": 2,
            "rows_ordered": True,
            "rows_unique_by_date": True,
            "adjclose_complete": True,
            "proxy_used": False,
            "mixed_source": False,
            "validation_version": "spy_fmp_light_adjclose_v1",
        },
    }
    assert result.range_metrics is not None
    assert result.performance_series[-1].benchmark_return_pct is None
    assert result.range_metrics["All"].summary.benchmark_return_pct is None
    assert result.benchmark is not None
    assert result.benchmark.return_basis_contract == "verified_total_return"
    assert result.benchmark.return_pct is None
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }


def test_run_imported_dashboard_history_keeps_adjusted_spy_unverified_when_direct_scope_evidence_is_missing(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 101.5},
    ]
    service.get_last_fetch_meta.return_value = {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": False,
        "fallback_used": True,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0},
            {"date": "2026-04-11", "price": 115.0},
        ],
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.run_metadata.return_basis_contract.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "unverified_adjusted_proxy",
    }
    assert result.run_metadata.return_basis_evidence.benchmark_path.verification_status == "proxy"
    assert result.run_metadata.return_basis_evidence.benchmark_path.scope == {}
    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.benchmark_return_pct is None
    assert result.benchmark is not None
    assert result.benchmark.return_pct is None


def test_run_imported_dashboard_history_enables_verified_benchmark_for_direct_qqq_fmp_slice(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 200.0, "adjClose": 200.0},
        {"date": "2026-04-11", "price": 202.0, "adjClose": 203.0},
    ]
    service.get_last_fetch_meta.return_value = {
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
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0},
            {"date": "2026-04-11", "price": 115.0},
        ],
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "QQQ")

    service.get_direct_verified_benchmark_history.assert_called_once_with("QQQ", "2026-04-10", "2026-04-11")
    service.get_historical_prices.assert_not_called()
    assert result.run_metadata.return_basis_contract.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "verified_total_return",
    }
    assert result.run_metadata.return_basis_evidence.benchmark_path.model_dump() == {
        "verification_status": "verified",
        "economic_basis": "total_return",
        "construction_method": "vendor_adjusted_close",
        "disqualifiers": [],
        "fallbacks_used": [],
        "source_price_field": "adjClose",
        "scope": {
            "symbol": "QQQ",
            "requested_symbol": "QQQ",
            "resolved_symbol": "QQQ",
            "vendor": "FMP",
            "endpoint": "historical-price-eod/light",
            "direct_path_only": True,
            "fallback_used": False,
            "proxy_used": False,
            "mixed_source": False,
            "symbol_override_used": False,
            "window_start": "2026-04-10",
            "window_end": "2026-04-11",
            "row_count": 2,
            "rows_ordered": True,
            "rows_unique_by_date": True,
            "adjclose_complete": True,
            "validation_version": "qqq_fmp_light_adjclose_v1",
        },
    }
    assert result.benchmark is not None
    assert result.benchmark.return_basis_contract == "verified_total_return"
    assert result.benchmark.return_pct is None


def test_run_imported_dashboard_history_keeps_qqq_unverified_when_direct_scope_evidence_is_broken(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 200.0, "adjClose": 200.0},
        {"date": "2026-04-11", "price": 202.0, "adjClose": 203.0},
    ]
    service.get_last_fetch_meta.return_value = {
        "type": "history",
        "requested_symbol": "QQQ",
        "resolved_symbol": "QQQ",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": True,
        "fallback_used": True,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0},
            {"date": "2026-04-11", "price": 115.0},
        ],
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "QQQ")

    assert result.run_metadata.return_basis_contract.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "unverified_adjusted_proxy",
    }
    assert result.run_metadata.return_basis_evidence.benchmark_path.verification_status == "proxy"
    assert result.run_metadata.return_basis_evidence.benchmark_path.scope == {}
    assert result.benchmark is not None
    assert result.benchmark.return_pct is None


def test_run_imported_dashboard_history_keeps_qqq_unverified_when_in_window_adjclose_coverage_is_incomplete(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 200.0, "adjClose": 200.0},
        {"date": "2026-04-11", "price": 202.0, "adjClose": None},
    ]
    service.get_last_fetch_meta.return_value = {
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
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0},
            {"date": "2026-04-11", "price": 115.0},
        ],
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "QQQ")

    assert result.run_metadata.return_basis_contract.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "price_return_only",
    }
    assert result.run_metadata.return_basis_evidence.benchmark_path.verification_status == "unverified"
    assert result.run_metadata.return_basis_evidence.benchmark_path.scope == {}
    assert result.benchmark is not None
    assert result.benchmark.return_pct is None


def test_run_imported_dashboard_history_keeps_non_allowlisted_benchmark_unverified_even_with_adjusted_rows(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 400.0, "adjClose": 400.0},
        {"date": "2026-04-11", "price": 404.0, "adjClose": 406.0},
    ]
    service.get_last_fetch_meta.return_value = {
        "type": "history",
        "requested_symbol": "VOO",
        "resolved_symbol": "VOO",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": True,
        "fallback_used": False,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0},
            {"date": "2026-04-11", "price": 115.0},
        ],
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "VOO")

    service.get_direct_verified_benchmark_history.assert_not_called()
    service.get_historical_prices.assert_called_once_with("VOO", "2026-04-10", "2026-04-11")
    assert result.run_metadata.return_basis_contract.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "unverified_adjusted_proxy",
    }
    assert result.run_metadata.return_basis_evidence.benchmark_path.scope == {}
    assert result.benchmark is not None
    assert result.benchmark.return_pct is None


def test_build_true_performance_series_prefers_adjusted_benchmark_prices_when_available() -> None:
    states = [
        DailyPortfolioState(date="2025-01-02", cash={"USD": 1000.0}, positions=[], total_market_value=0.0, total_portfolio_value=1000.0, external_cash_flow=0.0),
        DailyPortfolioState(date="2025-01-03", cash={"USD": 1100.0}, positions=[], total_market_value=0.0, total_portfolio_value=1100.0, external_cash_flow=100.0),
        DailyPortfolioState(date="2025-01-04", cash={"USD": 1210.0}, positions=[], total_market_value=0.0, total_portfolio_value=1210.0, external_cash_flow=0.0),
    ]

    series = build_true_performance_series(
        states,
        [
            {"date": "2025-01-02", "price": 100.0, "adjClose": 100.0},
            {"date": "2025-01-03", "price": 101.0, "adjClose": 99.0},
            {"date": "2025-01-04", "price": 103.0, "adjClose": 101.97},
        ],
    )

    assert series[2].benchmark_return_pct is None


def test_build_true_performance_series_refuses_unverified_adjusted_proxy_benchmark_return_pct() -> None:
    states = [
        DailyPortfolioState(date="2025-01-02", cash={"USD": 1000.0}, positions=[], total_market_value=0.0, total_portfolio_value=1000.0, external_cash_flow=0.0),
        DailyPortfolioState(date="2025-01-03", cash={"USD": 1100.0}, positions=[], total_market_value=0.0, total_portfolio_value=1100.0, external_cash_flow=100.0),
        DailyPortfolioState(date="2025-01-04", cash={"USD": 1210.0}, positions=[], total_market_value=0.0, total_portfolio_value=1210.0, external_cash_flow=0.0),
    ]

    series = build_true_performance_series(
        states,
        [
            {"date": "2025-01-02", "price": 100.0, "adjClose": 100.0},
            {"date": "2025-01-03", "price": 101.0, "adjClose": 99.0},
            {"date": "2025-01-04", "price": 103.0, "adjClose": 101.97},
        ],
    )

    assert series[1].portfolio_return_pct == 0.0
    assert series[2].portfolio_return_pct == 10.0
    assert series[2].benchmark_return_pct is None


def test_build_true_performance_series_refuses_compounded_portfolio_and_benchmark_returns_for_price_only_basis() -> None:
    states = [
        DailyPortfolioState(date="2025-01-02", cash={"USD": 1000.0}, positions=[], total_market_value=0.0, total_portfolio_value=1000.0, external_cash_flow=0.0),
        DailyPortfolioState(date="2025-01-03", cash={"USD": 1100.0}, positions=[], total_market_value=0.0, total_portfolio_value=1100.0, external_cash_flow=100.0),
        DailyPortfolioState(date="2025-01-04", cash={"USD": 1210.0}, positions=[], total_market_value=0.0, total_portfolio_value=1210.0, external_cash_flow=0.0),
    ]

    series = build_true_performance_series(
        states,
        [
            {"date": "2025-01-02", "price": 100.0},
            {"date": "2025-01-03", "price": 101.0},
            {"date": "2025-01-04", "price": 103.0},
        ],
        portfolio_return_basis_contract="price_return_only",
        benchmark_return_basis_contract="price_return_only",
    )

    assert series[1].portfolio_return_pct == 0.0
    assert series[2].portfolio_return_pct == 0.0
    assert series[2].benchmark_return_pct is None


def test_build_true_performance_series_refuses_compounded_portfolio_and_benchmark_returns_for_unverified_adjusted_proxy_basis() -> None:
    states = [
        DailyPortfolioState(date="2025-01-02", cash={"USD": 1000.0}, positions=[], total_market_value=0.0, total_portfolio_value=1000.0, external_cash_flow=0.0),
        DailyPortfolioState(date="2025-01-03", cash={"USD": 1100.0}, positions=[], total_market_value=0.0, total_portfolio_value=1100.0, external_cash_flow=100.0),
        DailyPortfolioState(date="2025-01-04", cash={"USD": 1210.0}, positions=[], total_market_value=0.0, total_portfolio_value=1210.0, external_cash_flow=0.0),
    ]

    series = build_true_performance_series(
        states,
        [
            {"date": "2025-01-02", "price": 100.0, "adjClose": 100.0},
            {"date": "2025-01-03", "price": 101.0, "adjClose": 99.0},
            {"date": "2025-01-04", "price": 103.0, "adjClose": 101.97},
        ],
        portfolio_return_basis_contract="unverified_adjusted_proxy",
        benchmark_return_basis_contract="unverified_adjusted_proxy",
    )

    assert series[1].portfolio_return_pct == 0.0
    assert series[2].portfolio_return_pct == 0.0
    assert series[2].benchmark_return_pct is None


def test_run_imported_dashboard_history_refuses_drawdown_loss_metrics_for_price_only_basis(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 101.0},
    ]
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0},
            {"date": "2026-04-11", "price": 115.0},
        ],
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.range_metrics is not None
    assert result.range_metrics["All"].max_drawdown_pct is None
    assert result.range_metrics["All"].summary.time_weighted_return_pct is None
    assert result.range_metrics["All"].summary.benchmark_return_pct is None
    assert result.range_metrics["All"].summary.excess_return_pct is None


def test_run_imported_dashboard_history_refuses_drawdown_loss_metrics_for_unverified_adjusted_proxy_basis(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 99.5},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 100.4},
    ]
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0, "adjClose": 109.5},
            {"date": "2026-04-11", "price": 115.0, "adjClose": 114.7},
        ],
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.run_metadata.return_basis_contract.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "unverified_adjusted_proxy",
    }
    assert result.run_metadata.return_basis_evidence.benchmark_path.model_dump() == {
        "verification_status": "proxy",
        "economic_basis": "adjusted_close_proxy",
        "construction_method": "vendor_adjusted_close",
        "disqualifiers": [
            "missing_dividend_coverage_proof",
            "missing_vendor_scope_proof",
            "adjusted_close_is_not_verified_total_return",
        ],
        "fallbacks_used": [],
        "source_price_field": "adjClose",
        "scope": {},
    }
    assert result.range_metrics is not None
    assert result.range_metrics["All"].max_drawdown_pct is None
    assert result.range_metrics["All"].summary.time_weighted_return_pct is None
    assert result.range_metrics["All"].summary.benchmark_return_pct is None
    assert result.range_metrics["All"].summary.excess_return_pct is None


def test_run_imported_dashboard_history_unlocks_exact_slice_excess_return_for_admitted_slice_pair(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 101.0},
    ]
    service.get_last_fetch_meta.return_value = {
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
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 100.0, "basis": "broker_proven_mark_to_market"},
            {"date": "2026-04-11", "price": 103.0, "basis": "broker_proven_mark_to_market"},
        ]
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1030.0,
            cash_total=0.0,
            stock_total=1030.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=1000.0, ending_cash=0.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=103.0, market_value=1030.0, unrealized_pnl=30.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=-1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.run_metadata.portfolio_proof.admission.status == "admitted"
    assert result.run_metadata.portfolio_proof.admission.readiness_status == "exact_slice_admitted"
    assert result.performance_series[-1].portfolio_return_pct == 3.0
    assert result.performance_series[-1].benchmark_return_pct is None
    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.time_weighted_return_pct == 3.0
    assert result.range_metrics["All"].summary.benchmark_return_pct == 1.0
    assert result.range_metrics["All"].summary.excess_return_pct == 2.0
    assert result.range_metrics["All"].max_drawdown_pct is None
    assert result.benchmark is not None
    assert result.benchmark.return_basis_contract == "verified_total_return"
    assert result.benchmark.return_pct is None
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }


def test_run_imported_dashboard_history_keeps_exact_slice_benchmark_return_withheld_without_independent_benchmark_proof(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 101.0},
    ]
    service.get_last_fetch_meta.return_value = {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": False,
        "fallback_used": True,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 100.0, "basis": "broker_proven_mark_to_market"},
            {"date": "2026-04-11", "price": 103.0, "basis": "broker_proven_mark_to_market"},
        ]
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1030.0,
            cash_total=0.0,
            stock_total=1030.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=1000.0, ending_cash=0.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=103.0, market_value=1030.0, unrealized_pnl=30.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=-1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.run_metadata.portfolio_proof.admission.status == "admitted"
    assert result.run_metadata.portfolio_proof.admission.readiness_status == "exact_slice_admitted"
    assert result.performance_series[-1].portfolio_return_pct == 3.0
    assert result.performance_series[-1].benchmark_return_pct is None
    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.time_weighted_return_pct == 3.0
    assert result.range_metrics["All"].summary.benchmark_return_pct is None
    assert result.range_metrics["All"].summary.excess_return_pct is None
    assert result.range_metrics["All"].max_drawdown_pct is None
    assert result.benchmark is not None
    assert result.benchmark.return_basis_contract == "unverified_adjusted_proxy"
    assert result.benchmark.return_pct is None
    assert result.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }


def test_run_imported_dashboard_history_keeps_partial_overlap_benchmark_return_withheld_for_non_exact_window(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    dates = [(date(2026, 1, 1) + timedelta(days=index)).isoformat() for index in range(22)]
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": day_str, "price": 100.0 + index, "adjClose": 100.0 + index}
        for index, day_str in enumerate(dates)
    ]
    service.get_last_fetch_meta.return_value = {
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
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": day_str, "price": 100.0 + index, "basis": "broker_proven_mark_to_market"}
            for index, day_str in enumerate(dates)
        ]
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 1, 1),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period=f"{dates[0]} - {dates[-1]}",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1210.0,
            cash_total=0.0,
            stock_total=1210.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=1000.0, ending_cash=0.0)],
        positions=[ImportedPosition(as_of_date=date.fromisoformat(dates[-1]), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=121.0, market_value=1210.0, unrealized_pnl=210.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date.fromisoformat(dates[0]), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=-1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.run_metadata.portfolio_proof.admission.status == "admitted"
    assert result.run_metadata.portfolio_proof.admission.readiness_status == "exact_slice_admitted"
    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.time_weighted_return_pct == 21.0
    assert result.range_metrics["All"].summary.benchmark_return_pct == 21.0
    assert result.range_metrics["All"].summary.excess_return_pct == 0.0
    assert result.range_metrics["1M"].summary.time_weighted_return_pct is None
    assert result.range_metrics["1M"].summary.benchmark_return_pct is None
    assert result.range_metrics["1M"].summary.excess_return_pct is None
    assert result.range_metrics["1M"].max_drawdown_pct is None
    assert result.benchmark is not None
    assert result.benchmark.return_pct is None
    assert all(metrics.max_drawdown_pct is None for metrics in result.range_metrics.values())


def test_run_imported_dashboard_history_unlocks_only_exact_slice_excess_return_and_keeps_broader_outputs_withheld(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 101.0},
    ]
    service.get_last_fetch_meta.return_value = {
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
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 100.0, "basis": "broker_proven_mark_to_market"},
            {"date": "2026-04-11", "price": 103.0, "basis": "broker_proven_mark_to_market"},
        ]
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1030.0,
            cash_total=0.0,
            stock_total=1030.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=1000.0, ending_cash=0.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=103.0, market_value=1030.0, unrealized_pnl=30.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=-1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.time_weighted_return_pct == 3.0
    assert result.range_metrics["All"].summary.benchmark_return_pct == 1.0
    assert result.range_metrics["All"].summary.excess_return_pct == 2.0
    assert result.performance_series[-1].benchmark_return_pct is None
    assert result.benchmark is not None
    assert result.benchmark.return_pct is None
    assert all(metrics.max_drawdown_pct is None for metrics in result.range_metrics.values())
    assert result.run_metadata.investor_economics_partial_unlock.exact_slice_scalar_allowlist[2].model_dump() == {
        "field": "range_metrics[*].summary.excess_return_pct",
        "unlock_condition": "identical_admitted_exact_slice_pair_only",
        "runtime_enabled": True,
    }
    assert result.run_metadata.investor_economics_partial_unlock.withheld_families == [
        "benchmark_relative_series",
        "benchmark_relative_path_derived_outputs",
        "drawdown_family",
        "rebucketed_window_summaries",
        "rewindowed_range_summaries",
        "diagnostics_benchmark_relative_outputs",
        "replay_benchmark_relative_outputs",
        "strategy_lab_benchmark_relative_outputs",
    ]


def test_future_exact_slice_excess_return_policy_requires_both_exact_leg_permissions() -> None:
    assert _allow_future_exact_slice_excess_return_output(
        performance_points=[],
        admitted_portfolio_twr_scope=("2026-04-10", "2026-04-11", 2),
        allow_portfolio_twr_outputs=False,
        allow_exact_slice_benchmark_return_output=True,
        time_weighted_return_pct=None,
        benchmark_return_pct=1.0,
    ) is False
    assert _allow_future_exact_slice_excess_return_output(
        performance_points=[],
        admitted_portfolio_twr_scope=("2026-04-10", "2026-04-11", 2),
        allow_portfolio_twr_outputs=True,
        allow_exact_slice_benchmark_return_output=False,
        time_weighted_return_pct=3.0,
        benchmark_return_pct=None,
    ) is False
    assert _compute_future_exact_slice_excess_return_pct(
        performance_points=[],
        admitted_portfolio_twr_scope=("2026-04-10", "2026-04-11", 2),
        allow_portfolio_twr_outputs=False,
        allow_exact_slice_benchmark_return_output=True,
        time_weighted_return_pct=None,
        benchmark_return_pct=1.0,
    ) is None
    assert _compute_future_exact_slice_excess_return_pct(
        performance_points=[],
        admitted_portfolio_twr_scope=("2026-04-10", "2026-04-11", 2),
        allow_portfolio_twr_outputs=True,
        allow_exact_slice_benchmark_return_output=False,
        time_weighted_return_pct=3.0,
        benchmark_return_pct=None,
    ) is None


def test_future_exact_slice_excess_return_policy_requires_verified_exact_same_scope_slice() -> None:
    performance_series = [
        PerformancePoint(
            date="2026-04-10",
            portfolio_value=1000.0,
            benchmark_price=100.0,
            portfolio_return_pct=0.0,
            benchmark_return_pct=0.0,
        ),
        PerformancePoint(
            date="2026-04-11",
            portfolio_value=1030.0,
            benchmark_price=101.0,
            portfolio_return_pct=3.0,
            benchmark_return_pct=1.0,
        ),
    ]

    assert _allow_future_exact_slice_excess_return_output(
        performance_points=performance_series,
        admitted_portfolio_twr_scope=("2026-04-10", "2026-04-11", 3),
        allow_portfolio_twr_outputs=True,
        allow_exact_slice_benchmark_return_output=True,
        time_weighted_return_pct=3.0,
        benchmark_return_pct=1.0,
        source_performance_series=performance_series,
    ) is False
    assert _compute_future_exact_slice_excess_return_pct(
        performance_points=performance_series,
        admitted_portfolio_twr_scope=("2026-04-10", "2026-04-11", 3),
        allow_portfolio_twr_outputs=True,
        allow_exact_slice_benchmark_return_output=True,
        time_weighted_return_pct=3.0,
        benchmark_return_pct=1.0,
        source_performance_series=performance_series,
    ) is None


def test_future_exact_slice_excess_return_policy_emits_only_for_exact_verified_same_response_pair() -> None:
    performance_series = [
        PerformancePoint(
            date="2026-04-10",
            portfolio_value=1000.0,
            benchmark_price=100.0,
            portfolio_return_pct=0.0,
            benchmark_return_pct=0.0,
        ),
        PerformancePoint(
            date="2026-04-11",
            portfolio_value=1030.0,
            benchmark_price=101.0,
            portfolio_return_pct=3.0,
            benchmark_return_pct=1.0,
        ),
    ]

    assert _allow_future_exact_slice_excess_return_output(
        performance_points=performance_series,
        admitted_portfolio_twr_scope=("2026-04-10", "2026-04-11", 2),
        allow_portfolio_twr_outputs=True,
        allow_exact_slice_benchmark_return_output=True,
        time_weighted_return_pct=3.0,
        benchmark_return_pct=1.0,
        source_performance_series=performance_series,
    ) is True
    assert _compute_future_exact_slice_excess_return_pct(
        performance_points=performance_series,
        admitted_portfolio_twr_scope=("2026-04-10", "2026-04-11", 2),
        allow_portfolio_twr_outputs=True,
        allow_exact_slice_benchmark_return_output=True,
        time_weighted_return_pct=3.0,
        benchmark_return_pct=1.0,
        source_performance_series=performance_series,
    ) == 2.0


def test_future_exact_slice_excess_return_policy_refuses_client_side_subtraction_equivalents() -> None:
    all_range = [
        PerformancePoint(
            date="2026-01-01",
            portfolio_value=1000.0,
            benchmark_price=100.0,
            portfolio_return_pct=0.0,
            benchmark_return_pct=0.0,
        ),
        PerformancePoint(
            date="2026-01-02",
            portfolio_value=1100.0,
            benchmark_price=110.0,
            portfolio_return_pct=10.0,
            benchmark_return_pct=10.0,
        ),
        PerformancePoint(
            date="2026-01-03",
            portfolio_value=1210.0,
            benchmark_price=121.0,
            portfolio_return_pct=21.0,
            benchmark_return_pct=21.0,
        ),
    ]
    rebucketed_slice = all_range[1:]

    assert _allow_future_exact_slice_excess_return_output(
        performance_points=rebucketed_slice,
        admitted_portfolio_twr_scope=("2026-01-01", "2026-01-03", 3),
        allow_portfolio_twr_outputs=True,
        allow_exact_slice_benchmark_return_output=True,
        time_weighted_return_pct=21.0,
        benchmark_return_pct=21.0,
        source_performance_series=all_range,
    ) is False
    assert _compute_future_exact_slice_excess_return_pct(
        performance_points=rebucketed_slice,
        admitted_portfolio_twr_scope=("2026-01-01", "2026-01-03", 3),
        allow_portfolio_twr_outputs=True,
        allow_exact_slice_benchmark_return_output=True,
        time_weighted_return_pct=21.0,
        benchmark_return_pct=21.0,
        source_performance_series=all_range,
    ) is None


def test_run_imported_dashboard_history_future_exact_slice_policy_keeps_rebucketed_and_non_identical_windows_withheld(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    dates = [(date(2026, 1, 1) + timedelta(days=index)).isoformat() for index in range(22)]
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": day_str, "price": 100.0 + index, "adjClose": 100.0 + index}
        for index, day_str in enumerate(dates)
    ]
    service.get_last_fetch_meta.return_value = {
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
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": day_str, "price": 100.0 + index, "basis": "broker_proven_mark_to_market"}
            for index, day_str in enumerate(dates)
        ]
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 1, 1),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period=f"{dates[0]} - {dates[-1]}",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1210.0,
            cash_total=0.0,
            stock_total=1210.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=1000.0, ending_cash=0.0)],
        positions=[ImportedPosition(as_of_date=date.fromisoformat(dates[-1]), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=121.0, market_value=1210.0, unrealized_pnl=210.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date.fromisoformat(dates[0]), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=-1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.time_weighted_return_pct == 21.0
    assert result.range_metrics["All"].summary.benchmark_return_pct == 21.0
    assert result.range_metrics["All"].summary.excess_return_pct == 0.0
    assert result.range_metrics["YTD"].summary.time_weighted_return_pct == 21.0
    assert result.range_metrics["YTD"].summary.benchmark_return_pct == 21.0
    assert result.range_metrics["YTD"].summary.excess_return_pct == 0.0
    assert result.range_metrics["1M"].summary.time_weighted_return_pct is None
    assert result.range_metrics["1M"].summary.benchmark_return_pct is None
    assert result.range_metrics["1M"].summary.excess_return_pct is None
    assert all(metrics.max_drawdown_pct is None for metrics in result.range_metrics.values())
def test_run_imported_diagnostics_engine_returns_unavailable_when_symbol_history_is_missing(mocker) -> None:
    market_data = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service = market_data.return_value
    service.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 101.0},
    ]
    service.get_historical_prices_for_symbols.side_effect = [
        {"AAPL": []},
        {},
    ]
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_diagnostics_engine(snapshot, "SPY")

    assert result.availability.historical_sections_available is False
    assert result.availability.history_context_required is False
    assert result.availability.note == "Historical diagnostics are unavailable because the required benchmark or symbol market data could not be loaded for the requested history window."
    assert result.provenance.snapshot_basis == "imported_snapshot"
    assert result.provenance.historical_basis == "unavailable"
    assert result.provenance.note == "Historical diagnostics are unavailable because the required benchmark or symbol market data could not be loaded for the requested history window."
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": "2026-04-11",
        "history_start_date": None,
        "history_end_date": None,
        "dataset_version": "market_data_service_v1",
    }
    assert result.run_metadata.factor_model_parameters.model_dump() == {
        "rolling_windows_days": [20, 60, 252],
        "current_reliability_window_days": 60,
        "minimum_window_observations": {"20": 25, "60": 75, "252": 275},
        "collinearity_warning_threshold": 0.85,
        "orthogonalization_basis": "factor_proxy_definition_order",
        "ridge_lambda": 1e-05,
    }
    assert result.run_metadata.source_status.model_dump() == {
        "portfolio_history": "unavailable",
        "benchmark_history": "unavailable",
        "factor_history": "unavailable",
    }
    assert result.risk_summary.benchmark_symbol == "SPY"
    assert result.risk_summary.observations == 0
    assert result.rolling_risk == []
    assert result.statistical_factor_model.status == "unavailable"


def test_run_imported_diagnostics_engine_returns_unavailable_when_benchmark_history_is_missing(mocker) -> None:
    market_data = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service = market_data.return_value
    service.get_historical_prices.return_value = []
    service.get_historical_prices_for_symbols.side_effect = [
        {"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]},
        {},
    ]
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_diagnostics_engine(snapshot, "SPY")

    assert result.availability.historical_sections_available is False
    assert result.availability.history_context_required is False
    assert result.availability.note == "Historical diagnostics are unavailable because the required benchmark or symbol market data could not be loaded for the requested history window."
    assert result.provenance.snapshot_basis == "imported_snapshot"
    assert result.provenance.historical_basis == "unavailable"
    assert result.provenance.note == "Historical diagnostics are unavailable because the required benchmark or symbol market data could not be loaded for the requested history window."
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": "2026-04-11",
        "history_start_date": None,
        "history_end_date": None,
        "dataset_version": "market_data_service_v1",
    }
    assert result.run_metadata.factor_model_parameters.model_dump() == {
        "rolling_windows_days": [20, 60, 252],
        "current_reliability_window_days": 60,
        "minimum_window_observations": {"20": 25, "60": 75, "252": 275},
        "collinearity_warning_threshold": 0.85,
        "orthogonalization_basis": "factor_proxy_definition_order",
        "ridge_lambda": 1e-05,
    }
    assert result.run_metadata.source_status.model_dump() == {
        "portfolio_history": "unavailable",
        "benchmark_history": "unavailable",
        "factor_history": "unavailable",
    }
    assert result.risk_summary.benchmark_symbol == "SPY"
    assert result.risk_summary.observations == 0
    assert result.rolling_risk == []
    assert result.statistical_factor_model.status == "unavailable"


def test_run_imported_dashboard_history_returns_unavailable_when_symbol_history_is_missing(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 101.0},
    ]
    service.get_historical_prices_for_symbols.return_value = {"AAPL": []}
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.source_status == {"performance_history": "unavailable", "monthly_returns": "unavailable"}
    assert result.run_metadata.source_status.model_dump() == {
        "performance_history": "unavailable",
        "monthly_returns": "unavailable",
        "benchmark_history": "unavailable",
    }
    assert result.run_metadata.section_trust.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "unavailable",
        "monthly_returns_path": "unavailable",
    }
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": "2026-04-11",
        "history_start_date": None,
        "history_end_date": None,
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }
    assert result.benchmark is None
    assert result.daily_states == []
    assert result.performance_series == []
    assert result.range_metrics is not None
    assert result.range_metrics["3M"].summary.start_value is None
    assert result.range_metrics["3M"].monthly_returns == []
    assert result.range_metrics["3M"].monthly_returns_reliable is False


def test_run_imported_dashboard_history_returns_unavailable_when_benchmark_history_is_missing(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = []
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 100.0},
            {"date": "2026-04-11", "price": 101.0},
        ]
    }
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="snapshot.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=115.0, market_value=1150.0, unrealized_pnl=150.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=1000.0, currency="USD", source_section="Trades")],
    )

    result = run_imported_dashboard_history(snapshot, "SPY")

    assert result.source_status == {"performance_history": "unavailable", "monthly_returns": "unavailable"}
    assert result.run_metadata.source_status.model_dump() == {
        "performance_history": "unavailable",
        "monthly_returns": "unavailable",
        "benchmark_history": "unavailable",
    }
    assert result.run_metadata.section_trust.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "unavailable",
        "monthly_returns_path": "unavailable",
    }
    assert result.run_metadata.reproducibility.model_dump() == {
        "input_imported_at": "2026-04-10T00:00:00",
        "snapshot_as_of_date": "2026-04-11",
        "history_start_date": None,
        "history_end_date": None,
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }
    assert result.benchmark is None
    assert result.daily_states == []
    assert result.performance_series == []
    assert result.range_metrics is not None
    assert result.range_metrics["3M"].summary.start_value is None
    assert result.range_metrics["3M"].monthly_returns == []
    assert result.range_metrics["3M"].monthly_returns_reliable is False


def test_build_portfolio_risk_summary_and_position_contributions() -> None:
    benchmark_rows = [
        {"date": "2025-01-02", "price": 100.0},
        {"date": "2025-01-03", "price": 101.0},
        {"date": "2025-01-04", "price": 102.0},
    ]
    daily_states = [
        DailyPortfolioState(date="2025-01-02", cash={"USD": 0.0}, positions=[], total_market_value=1000.0, total_portfolio_value=1000.0),
        DailyPortfolioState(date="2025-01-03", cash={"USD": 0.0}, positions=[], total_market_value=1010.0, total_portfolio_value=1010.0),
        DailyPortfolioState(date="2025-01-04", cash={"USD": 0.0}, positions=[], total_market_value=1030.2, total_portfolio_value=1030.2),
    ]

    summary = build_portfolio_risk_summary(daily_states, benchmark_rows, "SPY")
    rolling = build_rolling_risk_series(daily_states, benchmark_rows)
    relative = build_relative_risk_summary(daily_states, benchmark_rows, "SPY")

    assert summary.benchmark_symbol == "SPY"
    assert summary.methodology == "Historical regression using cash-flow-neutral daily portfolio returns and aligned benchmark daily returns."
    assert summary.observations == 2
    assert summary.portfolio_beta is not None
    assert summary.portfolio_correlation is not None
    assert len(rolling) == 2
    assert rolling[-1].beta_20d is None
    assert rolling[-1].beta_252d is None
    assert relative.tracking_error_pct is not None
    assert relative.active_return_pct is not None
    assert relative.information_ratio is not None


def test_build_rolling_risk_series_populates_252d_window_when_history_is_long_enough() -> None:
    start = date(2025, 1, 1)
    benchmark_rows = [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset)} for offset in range(255)]
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=float(1000 + (offset * 3)),
            total_portfolio_value=float(1000 + (offset * 3)),
        )
        for offset in range(255)
    ]

    rolling = build_rolling_risk_series(daily_states, benchmark_rows)

    assert rolling[-1].beta_252d is not None
    assert rolling[-1].correlation_252d is not None


def test_build_volatility_regime_payload_with_constant_returns_is_zero_and_normal() -> None:
    start = date(2025, 1, 1)
    daily_values = [1000.0 * (1.01**offset) for offset in range(80)]
    benchmark_values = [100.0 * (1.01**offset) for offset in range(80)]
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=value,
            total_portfolio_value=value,
        )
        for offset, value in enumerate(daily_values)
    ]
    benchmark_rows = [
        {"date": (start + timedelta(days=offset)).isoformat(), "price": value}
        for offset, value in enumerate(benchmark_values)
    ]

    payload = build_volatility_regime_payload(daily_states, benchmark_rows)

    assert payload.snapshot.realized_vol_20d == 0.0
    assert payload.snapshot.realized_vol_60d == 0.0
    assert payload.snapshot.benchmark_vol_20d == 0.0
    assert payload.snapshot.downside_vol_20d == 0.0
    assert payload.snapshot.tracking_error_20d == 0.0
    assert payload.snapshot.current_drawdown_pct == 0.0
    assert payload.snapshot.max_drawdown_pct == 0.0
    assert payload.regime.label == "normal"
    assert payload.regime.confidence == "high"
    assert payload.assumptions.return_basis == "time_weighted_daily_return"


def test_build_volatility_regime_payload_sets_downside_vol_to_zero_without_negative_returns() -> None:
    start = date(2025, 1, 1)
    values = [1000.0 * (1.005**offset) for offset in range(30)]
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=value,
            total_portfolio_value=value,
        )
        for offset, value in enumerate(values)
    ]

    payload = build_volatility_regime_payload(daily_states, [])

    assert payload.snapshot.realized_vol_20d == 0.0
    assert payload.snapshot.downside_vol_20d == 0.0
    assert payload.snapshot.tracking_error_20d is None
    assert payload.regime.confidence == "medium"


def test_build_volatility_regime_payload_tracking_error_is_zero_for_matching_returns() -> None:
    start = date(2025, 1, 1)
    portfolio_values = [100.0]
    benchmark_prices = [50.0]
    for step in range(1, 70):
        portfolio_values.append(portfolio_values[-1] * (1 + (0.001 * step)))
        benchmark_prices.append(benchmark_prices[-1] * (1 + (0.001 * step)))

    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=value,
            total_portfolio_value=value,
        )
        for offset, value in enumerate(portfolio_values)
    ]
    benchmark_rows = [
        {"date": (start + timedelta(days=offset)).isoformat(), "price": price}
        for offset, price in enumerate(benchmark_prices)
    ]

    payload = build_volatility_regime_payload(daily_states, benchmark_rows)

    assert payload.snapshot.tracking_error_20d == 0.0
    assert payload.snapshot.tracking_error_60d == 0.0


def test_build_volatility_regime_payload_computes_drawdown_series() -> None:
    start = date(2025, 1, 1)
    values = [100.0, 110.0, 105.0, 90.0, 95.0, 120.0]

    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=value,
            total_portfolio_value=value,
        )
        for offset, value in enumerate(values)
    ]

    payload = build_volatility_regime_payload(daily_states, [])

    assert payload.snapshot.current_drawdown_pct == 0.0
    assert payload.snapshot.max_drawdown_pct == -18.18


def test_build_volatility_regime_payload_classifies_stressed_regime_from_percentile() -> None:
    start = date(2025, 1, 1)
    returns = ([0.001] * 24) + ([0.03, -0.03] * 11)
    values = [100.0]
    for daily_return in returns:
        values.append(values[-1] * (1 + daily_return))

    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=value,
            total_portfolio_value=value,
        )
        for offset, value in enumerate(values)
    ]

    payload = build_volatility_regime_payload(daily_states, [])

    assert payload.snapshot.current_20d_vol_percentile is not None
    assert payload.snapshot.current_20d_vol_percentile > 0.8
    assert payload.regime.label == "stressed"
    assert payload.regime.confidence == "medium"


def test_build_volatility_regime_payload_handles_insufficient_history() -> None:
    daily_states = [
        DailyPortfolioState(date="2025-01-01", cash={"USD": 0.0}, positions=[], total_market_value=1000.0, total_portfolio_value=1000.0),
        DailyPortfolioState(date="2025-01-02", cash={"USD": 0.0}, positions=[], total_market_value=1010.0, total_portfolio_value=1010.0),
    ]

    payload = build_volatility_regime_payload(daily_states, [])

    assert len(payload.rolling_series) == 1
    assert payload.snapshot.realized_vol_20d is None
    assert payload.snapshot.current_20d_vol_percentile is None
    assert payload.regime.label == "normal"
    assert payload.regime.confidence == "low"


def test_cash_flow_neutral_returns_do_not_create_fake_volatility_spike() -> None:
    states = [
        DailyPortfolioState(date="2025-01-01", cash={"USD": 1000.0}, positions=[], total_market_value=0.0, total_portfolio_value=1000.0, external_cash_flow=0.0),
        DailyPortfolioState(date="2025-01-02", cash={"USD": 1200.0}, positions=[], total_market_value=0.0, total_portfolio_value=1200.0, external_cash_flow=200.0),
        DailyPortfolioState(date="2025-01-03", cash={"USD": 1212.0}, positions=[], total_market_value=0.0, total_portfolio_value=1212.0, external_cash_flow=0.0),
    ]

    payload = build_volatility_regime_payload(states, [])

    assert payload.rolling_series[0].portfolio_return == 0.0
    assert payload.rolling_series[1].portfolio_return == 0.01


def test_drawdown_ignores_external_cash_outflow_when_performance_is_flat() -> None:
    states = [
        DailyPortfolioState(date="2025-01-01", cash={"USD": 1000.0}, positions=[], total_market_value=0.0, total_portfolio_value=1000.0, external_cash_flow=0.0),
        DailyPortfolioState(date="2025-01-02", cash={"USD": 900.0}, positions=[], total_market_value=0.0, total_portfolio_value=900.0, external_cash_flow=-100.0),
        DailyPortfolioState(date="2025-01-03", cash={"USD": 900.0}, positions=[], total_market_value=0.0, total_portfolio_value=900.0, external_cash_flow=0.0),
    ]

    payload = build_volatility_regime_payload(states, [])

    assert payload.snapshot.current_drawdown_pct == 0.0
    assert payload.snapshot.max_drawdown_pct == 0.0


def test_benchmark_volatility_and_tracking_error_use_aligned_dates() -> None:
    start = date(2025, 1, 1)
    states = []
    portfolio_value = 100.0
    benchmark_price = 200.0
    for offset in range(25):
        if offset > 0:
            portfolio_value *= 1.01 if offset % 2 == 0 else 0.99
            benchmark_price *= 1.005 if offset % 2 == 0 else 0.995
        states.append(DailyPortfolioState(date=(start + timedelta(days=offset)).isoformat(), cash={"USD": 0.0}, positions=[], total_market_value=portfolio_value, total_portfolio_value=portfolio_value, external_cash_flow=0.0))

    benchmark_rows = [
        {"date": (start + timedelta(days=offset)).isoformat(), "price": (200.0 * (1.005**offset))}
        for offset in range(25)
    ]

    payload = build_volatility_regime_payload(states, benchmark_rows)

    assert payload.snapshot.benchmark_vol_20d is not None
    assert payload.snapshot.tracking_error_20d is not None


def test_downside_volatility_uses_negative_return_samples_only() -> None:
    start = date(2025, 1, 1)
    returns = [0.02, -0.01, 0.015, -0.03, 0.01, -0.02, 0.005, -0.01, 0.012, -0.015, 0.007, -0.005, 0.011, -0.009, 0.006, -0.004, 0.003, -0.002, 0.004, -0.001, 0.005]
    values = [100.0]
    for daily_return in returns:
        values.append(values[-1] * (1 + daily_return))

    states = [
        DailyPortfolioState(date=(start + timedelta(days=offset)).isoformat(), cash={"USD": 0.0}, positions=[], total_market_value=value, total_portfolio_value=value, external_cash_flow=0.0)
        for offset, value in enumerate(values)
    ]

    payload = build_volatility_regime_payload(states, [])

    assert payload.snapshot.downside_vol_20d is not None
    assert payload.snapshot.realized_vol_20d is not None
    assert payload.snapshot.downside_vol_20d <= payload.snapshot.realized_vol_20d


def test_regime_uses_corrected_volatility_series() -> None:
    start = date(2025, 1, 1)
    states = []
    value = 100.0
    for offset in range(45):
        if offset > 0:
            daily_return = 0.001 if offset < 24 else (0.03 if offset % 2 == 0 else -0.03)
            value *= 1 + daily_return
        states.append(DailyPortfolioState(date=(start + timedelta(days=offset)).isoformat(), cash={"USD": 0.0}, positions=[], total_market_value=value, total_portfolio_value=value, external_cash_flow=0.0))

    payload = build_volatility_regime_payload(states, [])

    assert payload.snapshot.current_20d_vol_percentile is not None
    assert payload.regime.label in {"normal", "stressed"}


def test_build_lookthrough_exposure_combines_direct_and_etf_holdings() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 1, 1),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2025",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(starting_nav=1000.0, ending_nav=2000.0),
        instruments=[ImportedInstrument(symbol="VUAA", description="Vanguard S&P 500 UCITS ETF", listing_exchange="LSEETF", instrument_type="ETF")],
        cash_balances=[],
        positions=[
            ImportedPosition(as_of_date=date(2025, 12, 31), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=100.0, market_value=100.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2025, 12, 31), symbol="VUAA", quantity=1.0, cost_basis=900.0, close_price=900.0, market_value=900.0, unrealized_pnl=0.0, currency="USD"),
        ],
        ledger_entries=[],
    )

    class StubMarketData:
        def get_etf_holdings(self, symbol: str, symbol_overrides=None):
            holdings = {
                "VUAA": ("SPY", [
                    {"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 6.0},
                    {"asset": "MSFT", "name": "MICROSOFT CORP", "weightPercentage": 5.0},
                ]),
            }
            return holdings[symbol]

        def get_company_profile(self, symbol: str, symbol_overrides=None):
            return None

    constituents, etf_resolution, uncovered_positions, covered_market_value = build_lookthrough_exposure(snapshot, StubMarketData())

    by_symbol = {item.symbol: item for item in constituents}
    assert etf_resolution == {"VUAA": "SPY"}
    assert uncovered_positions == []
    assert covered_market_value == 1000.0
    assert round(by_symbol["AAPL"].effective_market_value, 2) == 154.0
    assert round(by_symbol["MSFT"].effective_market_value, 2) == 45.0

    overlap = build_market_overlap_summary(
        constituents,
        "SPY",
        [
            {"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 6.0},
            {"asset": "MSFT", "name": "MICROSOFT CORP", "weightPercentage": 5.0},
            {"asset": "NVDA", "name": "NVIDIA CORP", "weightPercentage": 4.0},
        ],
    )

    assert overlap.benchmark_symbol == "SPY"
    assert overlap.overlap_weight is not None
    assert round(overlap.overlap_weight, 4) == 0.105
    sector_exposure = build_lookthrough_sector_exposure(constituents)
    factor_exposures = build_factor_exposures(
        PortfolioRiskSummary(
            benchmark_symbol="SPY",
            methodology="historical regression vs SPY daily returns",
            start_date="2025-01-02",
            end_date="2025-12-31",
            observations=10,
            portfolio_beta=1.1,
            portfolio_correlation=0.8,
            r_squared=0.64,
            portfolio_volatility_pct=12.0,
            benchmark_volatility_pct=10.0,
        ),
        overlap,
        sector_exposure,
    )
    benchmark_rows = [
        {"date": "2025-01-02", "price": 100.0},
        {"date": "2025-01-03", "price": 101.0},
        {"date": "2025-01-04", "price": 102.0},
        {"date": "2025-01-05", "price": 103.0},
        {"date": "2025-01-06", "price": 104.0},
        {"date": "2025-01-07", "price": 105.0},
        {"date": "2025-01-08", "price": 106.0},
        {"date": "2025-01-09", "price": 107.0},
        {"date": "2025-01-10", "price": 108.0},
        {"date": "2025-01-11", "price": 109.0},
        {"date": "2025-01-12", "price": 110.0},
    ]
    daily_states = [
        DailyPortfolioState(date="2025-01-02", cash={"USD": 0.0}, positions=[], total_market_value=1000.0, total_portfolio_value=1000.0),
        DailyPortfolioState(date="2025-01-03", cash={"USD": 0.0}, positions=[], total_market_value=1010.0, total_portfolio_value=1010.0),
        DailyPortfolioState(date="2025-01-04", cash={"USD": 0.0}, positions=[], total_market_value=1020.0, total_portfolio_value=1020.0),
        DailyPortfolioState(date="2025-01-05", cash={"USD": 0.0}, positions=[], total_market_value=1030.0, total_portfolio_value=1030.0),
        DailyPortfolioState(date="2025-01-06", cash={"USD": 0.0}, positions=[], total_market_value=1040.0, total_portfolio_value=1040.0),
        DailyPortfolioState(date="2025-01-07", cash={"USD": 0.0}, positions=[], total_market_value=1050.0, total_portfolio_value=1050.0),
        DailyPortfolioState(date="2025-01-08", cash={"USD": 0.0}, positions=[], total_market_value=1060.0, total_portfolio_value=1060.0),
        DailyPortfolioState(date="2025-01-09", cash={"USD": 0.0}, positions=[], total_market_value=1070.0, total_portfolio_value=1070.0),
        DailyPortfolioState(date="2025-01-10", cash={"USD": 0.0}, positions=[], total_market_value=1080.0, total_portfolio_value=1080.0),
        DailyPortfolioState(date="2025-01-11", cash={"USD": 0.0}, positions=[], total_market_value=1090.0, total_portfolio_value=1090.0),
        DailyPortfolioState(date="2025-01-12", cash={"USD": 0.0}, positions=[], total_market_value=1100.0, total_portfolio_value=1100.0),
    ]

    assert sector_exposure[0].sector in {"Technology", "Broad Market", "Other"}
    assert any(item.factor == "Market" for item in factor_exposures)
    assert any(item.factor == "Consumer Discretionary Tilt" for item in factor_exposures)
    assert any(item.factor == "Consumer Staples Tilt" for item in factor_exposures)
    assert any(item.factor == "Utilities Tilt" for item in factor_exposures)

    factor_model = build_statistical_factor_model(
        daily_states,
        {definition.us_proxy: benchmark_rows for definition in DEFAULT_FACTOR_DEFINITIONS},
        "SPY",
    )
    stress = build_stress_scenarios(factor_model)

    assert factor_model.benchmark_symbol == "SPY"
    assert factor_model.status in {"ok", "partial"}
    assert len(factor_model.current_factor_snapshot) == 16
    assert factor_model.current_factor_snapshot[0].label == "Market"
    assert stress


def test_build_statistical_factor_model_populates_multi_window_rolling_loadings() -> None:
    start = date(2025, 1, 1)
    benchmark_rows = [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset)} for offset in range(290)]
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=float(1000 + (offset * 4)),
            total_portfolio_value=float(1000 + (offset * 4)),
        )
        for offset in range(290)
    ]

    factor_model = build_statistical_factor_model(
        daily_states,
        {definition.us_proxy: benchmark_rows for definition in DEFAULT_FACTOR_DEFINITIONS},
        "SPY",
    )

    assert len(factor_model.rolling_loadings_20d) == len(factor_model.rolling_loadings_60d)
    assert len(factor_model.rolling_loadings_20d) == len(factor_model.rolling_loadings_252d)
    assert factor_model.rolling_loadings_60d[-1].market is not None
    assert factor_model.rolling_loadings_252d[-1].market is not None
    assert factor_model.rolling_loadings_60d[-1].technology is not None
    assert factor_model.rolling_loadings_60d[-1].credit is not None


def test_growth_loading_is_unit_when_portfolio_matches_growth_factor_returns() -> None:
    start = date(2025, 1, 1)
    growth_returns = [0.012, -0.008, 0.015, 0.004, -0.006] * 8

    def build_price_rows(base: float, returns: list[float]) -> list[dict[str, float | str]]:
        rows = [{"date": start.isoformat(), "price": base}]
        price = base
        for offset, daily_return in enumerate(returns, start=1):
            price *= 1 + daily_return
            rows.append({"date": (start + timedelta(days=offset)).isoformat(), "price": round(price, 6)})
        return rows

    growth_rows = build_price_rows(100.0, growth_returns)
    flat_rows = build_price_rows(100.0, [0.0] * len(growth_returns))

    portfolio_value = 1000.0
    daily_states = [{"date": start.isoformat(), "value": portfolio_value}]
    for offset, daily_return in enumerate(growth_returns, start=1):
        portfolio_value *= 1 + daily_return
        daily_states.append({"date": (start + timedelta(days=offset)).isoformat(), "value": round(portfolio_value, 6)})

    factor_model = build_statistical_factor_model(
        [
            DailyPortfolioState(
                date=item["date"],
                cash={"USD": 0.0},
                positions=[],
                total_market_value=item["value"],
                total_portfolio_value=item["value"],
            )
            for item in daily_states
        ],
        {
            definition.us_proxy: (growth_rows if definition.key == "growth" else flat_rows)
            for definition in DEFAULT_FACTOR_DEFINITIONS
        }
        | {"SPY": flat_rows},
        "SPY",
    )

    latest_20d = factor_model.rolling_loadings_20d[-1]

    assert latest_20d.growth == pytest.approx(1.0, abs=1e-2)
    assert latest_20d.market == pytest.approx(0.0, abs=1e-3)


def test_build_lookthrough_sector_exposure_uses_thematic_etf_source_sector() -> None:
    sector_exposure = build_lookthrough_sector_exposure(
        [
            LookThroughConstituent(
                symbol="MSFT",
                name="Microsoft Corp",
                effective_market_value=110.0,
                portfolio_weight=1.0,
                sources=[
                    LookThroughSource(source_symbol="DFND", source_market_value=100.0, source_weight=0.6, resolved_via="DFND"),
                    LookThroughSource(source_symbol="MSFT", source_market_value=50.0, source_weight=1.0, resolved_via="MSFT"),
                ],
            )
        ]
    )

    by_sector = {item.sector: item for item in sector_exposure}

    assert by_sector["Defense"].market_value == pytest.approx(60.0, abs=0.01)
    assert by_sector["Technology"].market_value == pytest.approx(50.0, abs=0.01)


def test_statistical_factor_model_r_squared_matches_sse_over_sst_formula() -> None:
    start = date(2025, 1, 1)
    growth_returns = [0.011, -0.007, 0.013, -0.004, 0.009, -0.006, 0.012, -0.005] * 5
    noise_returns = [0.0015, -0.0005, 0.001, -0.0015, 0.0005, -0.001, 0.0012, -0.0008] * 5

    def build_price_rows(base: float, returns: list[float]) -> list[dict[str, float | str]]:
        rows = [{"date": start.isoformat(), "price": base}]
        price = base
        for offset, daily_return in enumerate(returns, start=1):
            price *= 1 + daily_return
            rows.append({"date": (start + timedelta(days=offset)).isoformat(), "price": round(price, 6)})
        return rows

    portfolio_returns = [(0.75 * growth) + noise for growth, noise in zip(growth_returns, noise_returns, strict=False)]
    growth_rows = build_price_rows(100.0, growth_returns)
    flat_rows = build_price_rows(100.0, [0.0] * len(growth_returns))

    portfolio_value = 1000.0
    daily_states = [{"date": start.isoformat(), "value": portfolio_value}]
    for offset, daily_return in enumerate(portfolio_returns, start=1):
        portfolio_value *= 1 + daily_return
        daily_states.append({"date": (start + timedelta(days=offset)).isoformat(), "value": round(portfolio_value, 6)})

    factor_model = build_statistical_factor_model(
        [
            DailyPortfolioState(
                date=item["date"],
                cash={"USD": 0.0},
                positions=[],
                total_market_value=item["value"],
                total_portfolio_value=item["value"],
            )
            for item in daily_states
        ],
        {
            definition.us_proxy: (growth_rows if definition.key == "growth" else flat_rows)
            for definition in DEFAULT_FACTOR_DEFINITIONS
        }
        | {"SPY": flat_rows},
        "SPY",
    )

    y_window = portfolio_returns[-20:]
    x_window = growth_returns[-20:]
    mean_y = sum(y_window) / len(y_window)
    mean_x = sum(x_window) / len(x_window)
    ss_xx = sum((value - mean_x) ** 2 for value in x_window)
    beta = sum((x_value - mean_x) * (y_value - mean_y) for x_value, y_value in zip(x_window, y_window, strict=False)) / ss_xx
    alpha = mean_y - (beta * mean_x)
    fitted = [alpha + (beta * value) for value in x_window]
    sse = sum((actual - estimate) ** 2 for actual, estimate in zip(y_window, fitted, strict=False))
    sst = sum((actual - mean_y) ** 2 for actual in y_window)
    expected_r_squared = 1 - (sse / sst)

    assert factor_model.rolling_loadings_20d[-1].r_squared == pytest.approx(expected_r_squared, abs=1e-3)


def test_rolling_factor_loadings_matches_published_statsmodels_capm_checkpoints(monkeypatch) -> None:
    class MarketOnlyDefinition:
        def __init__(self) -> None:
            self.key = "market"
            self.label = "Market"
            self.us_proxy = "MKT"

    monkeypatch.setattr(risk_module, "DEFAULT_FACTOR_DEFINITIONS", [MarketOnlyDefinition()])
    monkeypatch.setattr(risk_module, "WINDOW_MIN_OBSERVATIONS", {20: 20, 60: 60, 252: 252})

    dates = [f"{index + 1:03d}" for index in range(62)]
    x = [
        0.20, -0.10, 0.30, 0.15, -0.05, 0.40, -0.20, 0.10, 0.35, -0.15,
        0.25, 0.05, -0.12, 0.18, 0.22, -0.08, 0.31, 0.27, -0.04, 0.16,
        0.29, -0.09, 0.24, 0.13, -0.02, 0.37, -0.18, 0.11, 0.33, -0.13,
        0.26, 0.07, -0.10, 0.19, 0.21, -0.06, 0.30, 0.28, -0.01, 0.17,
        0.32, -0.07, 0.23, 0.14, 0.00, 0.36, -0.16, 0.09, 0.34, -0.11,
        0.27, 0.08, -0.09, 0.20, 0.24, -0.05, 0.28, 0.26, -0.03, 0.18,
        0.22, 0.12,
    ]
    expected_intercept = 0.873061
    expected_beta = 1.401724

    y = [expected_intercept + expected_beta * value for value in x]

    points = risk_module._build_rolling_factor_loadings(  # type: ignore[attr-defined]
        dates,
        y,
        [("Market", "MKT", x)],
        window=60,
    )

    assert points[57].market is None
    assert points[58].market is None
    assert points[59].market == pytest.approx(expected_beta, abs=1e-3)
    assert points[60].market == pytest.approx(expected_beta, abs=1e-3)
    assert points[61].market == pytest.approx(expected_beta, abs=1e-3)


def test_build_factor_shift_diagnostics_flags_large_recent_shift() -> None:
    start = date(2025, 1, 1)

    def point(offset: int, market_20: float | None, market_60: float | None, market_252: float | None):
        return {
            "date": (start + timedelta(days=offset)).isoformat(),
            "market": market_20,
            "growth": 0.05,
            "value": 0.02,
            "small_cap": 0.01,
            "financials": 0.03,
            "health_care": 0.01,
            "energy": 0.0,
            "industrials": 0.01,
            "rates_ief": -0.02,
            "rates_tlt": -0.01,
            "credit": 0.01,
            "commodities": 0.0,
            "alpha": None,
            "r_squared": None,
            "residual_vol": None,
        }, market_60, market_252

    rolling_loadings_20d = []
    rolling_loadings_60d = []
    rolling_loadings_252d = []
    for offset in range(90):
        market_20 = 0.1 if offset < 70 else 0.55
        market_60 = 0.15 if offset < 29 else 0.18
        market_252 = 0.12 if offset >= 10 else None
        values, market_60_value, market_252_value = point(offset, market_20, market_60, market_252)
        rolling_loadings_20d.append(values)
        rolling_loadings_60d.append({**values, "market": market_60_value})
        rolling_loadings_252d.append({**values, "market": market_252_value})

    factor_model = build_statistical_factor_model(
        [
            DailyPortfolioState(
                date=(start + timedelta(days=offset)).isoformat(),
                cash={"USD": 0.0},
                positions=[],
                total_market_value=float(1000 + offset),
                total_portfolio_value=float(1000 + offset),
            )
            for offset in range(290)
        ],
        {definition.us_proxy: [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset)} for offset in range(290)] for definition in DEFAULT_FACTOR_DEFINITIONS},
        "SPY",
    )
    factor_model = factor_model.model_copy(
        update={
            "rolling_loadings_20d": [type(factor_model.rolling_loadings_20d[0]).model_validate(item) for item in rolling_loadings_20d],
            "rolling_loadings_60d": [type(factor_model.rolling_loadings_60d[0]).model_validate(item) for item in rolling_loadings_60d],
            "rolling_loadings_252d": [type(factor_model.rolling_loadings_252d[0]).model_validate(item) for item in rolling_loadings_252d],
        }
    )

    volatility_regime = build_volatility_regime_payload(
        [
            DailyPortfolioState(
                date=(start + timedelta(days=offset)).isoformat(),
                cash={"USD": 0.0},
                positions=[],
                total_market_value=100.0 * (1.002**offset),
                total_portfolio_value=100.0 * (1.002**offset),
            )
            for offset in range(90)
        ],
        [],
    )
    volatility_regime = volatility_regime.model_copy(
        update={
            "regime": volatility_regime.regime.model_copy(update={"label": "stressed", "confidence": "medium"}),
            "snapshot": volatility_regime.snapshot.model_copy(update={"vol_ratio_20_60": 1.25}),
        }
    )

    diagnostics = build_factor_shift_diagnostics(
        build_factor_registry(),
        factor_model,
        volatility_regime,
    )

    market_snapshot = next(item for item in diagnostics.snapshots if item.key == "market")
    assert market_snapshot.shift_flag_20d is True
    assert market_snapshot.volatility_flag is True
    assert market_snapshot.available_windows_count == 3
    assert diagnostics.largest_absolute_shifts_20d[0].key == "market"


def test_build_factor_shift_diagnostics_reports_stable_factor_without_flags() -> None:
    start = date(2025, 1, 1)
    benchmark_rows = [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset)} for offset in range(290)]
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=float(1000 + offset),
            total_portfolio_value=float(1000 + offset),
        )
        for offset in range(290)
    ]

    factor_model = build_statistical_factor_model(
        daily_states,
        {definition.us_proxy: benchmark_rows for definition in DEFAULT_FACTOR_DEFINITIONS},
        "SPY",
    )
    stable_20d = [point.model_copy(update={"market": 0.12}) for point in factor_model.rolling_loadings_20d]
    stable_60d = [point.model_copy(update={"market": 0.12}) for point in factor_model.rolling_loadings_60d]
    stable_252d = [point.model_copy(update={"market": 0.12}) for point in factor_model.rolling_loadings_252d]
    quiet_collinearity = [item.model_copy(update={"high_collinearity_pairs": []}) for item in factor_model.collinearity_diagnostics]
    factor_model = factor_model.model_copy(
        update={
            "rolling_loadings_20d": stable_20d,
            "rolling_loadings_60d": stable_60d,
            "rolling_loadings_252d": stable_252d,
            "collinearity_diagnostics": quiet_collinearity,
        }
    )

    volatility_regime = build_volatility_regime_payload(daily_states[:90], [])
    diagnostics = build_factor_shift_diagnostics(build_factor_registry(), factor_model, volatility_regime)

    market_snapshot = next(item for item in diagnostics.snapshots if item.key == "market")
    assert market_snapshot.shift_flag_20d is False
    assert market_snapshot.shift_flag_60d is False
    assert market_snapshot.stability_flag is False
    assert market_snapshot.collinearity_flag is False
    assert market_snapshot.confidence == "high"


def test_build_risk_contribution_breakdown_returns_factor_and_position_concentrations() -> None:
    start = date(2025, 1, 1)
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 1, 1),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2025",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(starting_nav=1000.0, ending_nav=2000.0),
        instruments=[],
        cash_balances=[],
        positions=[
            ImportedPosition(as_of_date=date(2025, 12, 31), symbol="AAPL", quantity=1.0, cost_basis=600.0, close_price=60.0, market_value=600.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2025, 12, 31), symbol="MSFT", quantity=1.0, cost_basis=400.0, close_price=40.0, market_value=400.0, unrealized_pnl=0.0, currency="USD"),
        ],
        ledger_entries=[],
    )
    # Portfolio with genuine daily-return variance (oscillating, not linear growth).
    # Linear growth (value = 1000 + offset*5) gives near-constant returns ≈ 0.005/day,
    # which means portfolio variance ≈ 0 and all factor variance_contributions underflow
    # to 0.0 after 8-decimal rounding — breaking the sum-equals-total consistency check.
    portfolio_value = 1000.0
    daily_states: list[DailyPortfolioState] = [
        DailyPortfolioState(date=start.isoformat(), cash={"USD": 0.0}, positions=[],
                            total_market_value=portfolio_value, total_portfolio_value=portfolio_value)
    ]
    for offset in range(1, 290):
        portfolio_value *= 1.005 if offset % 2 == 0 else 0.997
        daily_states.append(DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(), cash={"USD": 0.0}, positions=[],
            total_market_value=round(portfolio_value, 4), total_portfolio_value=round(portfolio_value, 4),
        ))

    # Distinct oscillating factor series so per-window Gram-Schmidt produces non-degenerate
    # orthogonalized factors and individual variance_contributions are large enough not to
    # underflow to 0.0 after 8-decimal rounding.
    factor_histories: dict[str, list[dict]] = {}
    for factor_idx, definition in enumerate(DEFAULT_FACTOR_DEFINITIONS):
        price = 100.0
        rows: list[dict] = [{"date": start.isoformat(), "price": price}]
        for offset in range(1, 290):
            r = (0.004 + factor_idx * 0.0002) if (offset + factor_idx) % 2 == 0 else -(0.003 + factor_idx * 0.0001)
            price *= 1 + r
            rows.append({"date": (start + timedelta(days=offset)).isoformat(), "price": round(price, 6)})
        factor_histories[definition.us_proxy] = rows

    price_histories = {
        "AAPL": [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset)} for offset in range(290)],
        "MSFT": [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(80 + (offset * 0.5))} for offset in range(290)],
    }
    factor_registry = build_factor_registry()
    factor_model = build_statistical_factor_model(daily_states, factor_histories, "SPY")

    breakdown = build_risk_contribution_breakdown(snapshot, daily_states, price_histories, factor_histories, factor_registry, factor_model)

    assert breakdown.window_days == 60
    assert breakdown.factor_contributions
    assert breakdown.position_contributions
    assert breakdown.factor_total_variance is not None
    assert breakdown.total_variance is not None
    assert breakdown.factor_risk_share_total is not None
    assert breakdown.concentration.top_1_factor_risk_share is not None
    assert breakdown.concentration.top_1_position_risk_share is not None
    assert breakdown.concentration.factor_hhi is not None
    assert breakdown.concentration.position_hhi is not None
    factor_share_sum = sum(item.risk_share or 0.0 for item in breakdown.factor_contributions)
    # Tolerance: 16 factors × max 0.00005 rounding error per term ≈ 0.0008 maximum accumulation.
    assert abs(round(factor_share_sum, 4) - (breakdown.factor_risk_share_total or 0.0)) <= 0.001
    assert round((breakdown.factor_total_variance or 0.0) + (breakdown.specific_variance or 0.0), 8) == breakdown.total_variance


def test_build_model_reliability_snapshot_uses_current_60d_window_metrics() -> None:
    start = date(2025, 1, 1)
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=float(1000 + (offset * 5)),
            total_portfolio_value=float(1000 + (offset * 5)),
        )
        for offset in range(290)
    ]
    benchmark_rows = [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset)} for offset in range(290)]
    factor_histories = {definition.us_proxy: benchmark_rows for definition in DEFAULT_FACTOR_DEFINITIONS}

    factor_model = build_statistical_factor_model(daily_states, factor_histories, "SPY")
    reliability = build_model_reliability_snapshot(factor_model)

    assert reliability.window_days == 60
    assert reliability.observation_count == 289
    assert reliability.r_squared is not None
    assert reliability.residual_volatility is not None
    assert reliability.factor_count_used >= 1
    assert reliability.missing_factor_count >= 0


def test_apply_return_basis_status_to_factor_model_degrades_status_when_adjusted_support_is_incomplete() -> None:
    start = date(2025, 1, 1)
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=float(1000 + offset),
            total_portfolio_value=float(1000 + offset),
        )
        for offset in range(290)
    ]
    benchmark_rows = [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset)} for offset in range(290)]
    factor_histories = {definition.us_proxy: benchmark_rows for definition in DEFAULT_FACTOR_DEFINITIONS}
    factor_model = build_statistical_factor_model(daily_states, factor_histories, "SPY")

    degraded = apply_return_basis_status_to_factor_model(
        factor_model,
        benchmark_rows=benchmark_rows,
        factor_histories=factor_histories,
    )

    assert degraded.status == "degraded_unverified_return_basis"
    assert any(window.status == "degraded_unverified_return_basis" for window in degraded.windows if window.status in {"degraded_unverified_return_basis", "ok", "partial"})


def test_apply_return_basis_status_to_model_reliability_degrades_status_and_confidence_when_adjusted_support_is_incomplete() -> None:
    start = date(2025, 1, 1)
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=float(1000 + offset),
            total_portfolio_value=float(1000 + offset),
        )
        for offset in range(290)
    ]
    benchmark_rows = [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset)} for offset in range(290)]
    factor_histories = {definition.us_proxy: benchmark_rows for definition in DEFAULT_FACTOR_DEFINITIONS}
    factor_model = build_statistical_factor_model(daily_states, factor_histories, "SPY")
    reliability = build_model_reliability_snapshot(factor_model)

    degraded = apply_return_basis_status_to_model_reliability(
        reliability,
        benchmark_rows=benchmark_rows,
        factor_histories=factor_histories,
    )

    assert degraded.status == "degraded_unverified_return_basis"
    assert degraded.confidence == "low"


def test_select_history_price_series_prefers_adjusted_close_when_fully_available() -> None:
    selected = select_history_price_series([
        {"date": "2026-01-02", "price": 100.0, "adjClose": 98.0},
        {"date": "2026-01-03", "price": 101.0, "adjusted_close": 99.0},
    ])

    assert selected.selected_field == "adjusted_close"
    assert selected.return_basis_status == "verified_adjusted_close"
    assert selected.points == [("2026-01-02", 98.0), ("2026-01-03", 99.0)]


def test_select_history_price_series_falls_back_to_price_with_unverified_status() -> None:
    selected = select_history_price_series([
        {"date": "2026-01-02", "price": 100.0, "adjClose": 98.0},
        {"date": "2026-01-03", "price": 101.0},
    ])

    assert selected.selected_field == "price"
    assert selected.return_basis_status == "unverified_close_only"
    assert selected.points == [("2026-01-02", 100.0), ("2026-01-03", 101.0)]


def test_selected_history_price_map_returns_selected_points_and_status() -> None:
    selected_map, status = selected_history_price_map([
        {"date": "2026-01-02", "price": 100.0, "adjClose": 98.0},
        {"date": "2026-01-03", "price": 101.0, "adjClose": 99.0},
    ])

    assert status == "verified_adjusted_close"
    assert selected_map == {"2026-01-02": 98.0, "2026-01-03": 99.0}


def test_build_history_return_basis_evidence_marks_adjusted_close_as_proxy_not_verified() -> None:
    evidence = build_history_return_basis_evidence([
        {"date": "2026-01-02", "price": 100.0, "adjClose": 98.0},
        {"date": "2026-01-03", "price": 101.0, "adjClose": 99.0},
    ])

    assert evidence.model_dump() == {
        "verification_status": "proxy",
        "economic_basis": "adjusted_close_proxy",
        "construction_method": "vendor_adjusted_close",
        "disqualifiers": [
            "missing_dividend_coverage_proof",
            "missing_vendor_scope_proof",
            "adjusted_close_is_not_verified_total_return",
        ],
        "fallbacks_used": [],
        "source_price_field": "adjClose",
        "scope": {},
    }


def test_build_history_return_basis_evidence_marks_price_only_history_as_unverified() -> None:
    evidence = build_history_return_basis_evidence([
        {"date": "2026-01-02", "price": 100.0},
        {"date": "2026-01-03", "price": 101.0},
    ])

    assert evidence.model_dump() == {
        "verification_status": "unverified",
        "economic_basis": "price_return_only",
        "construction_method": "raw_close",
        "disqualifiers": [
            "missing_adjusted_close_series",
            "missing_total_return_reconstruction",
        ],
        "fallbacks_used": [],
        "source_price_field": "price",
        "scope": {},
    }


def test_build_histories_return_basis_evidence_marks_synthetic_snapshot_history_explicitly() -> None:
    evidence = build_histories_return_basis_evidence(
        {"AAPL": [{"date": "2026-01-02", "price": 100.0}]},
        construction_method_hint="synthetic_snapshot_history",
    )

    assert evidence.model_dump() == {
        "verification_status": "unverified",
        "economic_basis": "price_return_only",
        "construction_method": "synthetic_snapshot_history",
        "disqualifiers": [
            "missing_dividend_coverage_proof",
            "missing_total_return_reconstruction",
            "synthetic_snapshot_history",
        ],
        "fallbacks_used": ["synthetic_snapshot_history"],
        "source_price_field": "price",
        "scope": {},
    }


def test_is_history_series_verified_adjusted_reports_false_for_price_fallback() -> None:
    assert is_history_series_verified_adjusted([
        {"date": "2026-01-02", "price": 100.0},
        {"date": "2026-01-03", "price": 101.0},
    ]) is False


def test_build_position_risk_contributions_uses_adjusted_series_when_available() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 1, 1),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2025",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[],
        positions=[ImportedPosition(as_of_date=date(2025, 1, 3), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=105.0, market_value=105.0, unrealized_pnl=5.0, currency="USD")],
        ledger_entries=[],
    )

    contributions = risk_module.build_position_risk_contributions(
        snapshot,
        price_histories={
            "AAPL": [
                {"date": "2025-01-01", "price": 100.0, "adjClose": 100.0},
                {"date": "2025-01-02", "price": 110.0, "adjClose": 103.0},
                {"date": "2025-01-03", "price": 121.0, "adjClose": 101.0},
            ]
        },
        benchmark_rows=[
            {"date": "2025-01-01", "price": 200.0, "adjClose": 200.0},
            {"date": "2025-01-02", "price": 210.0, "adjClose": 198.0},
            {"date": "2025-01-03", "price": 220.5, "adjClose": 201.0},
        ],
    )

    assert contributions[0].beta is not None
    assert contributions[0].correlation is not None


def test_build_portfolio_risk_summary_prefers_adjusted_benchmark_series_when_available() -> None:
    daily_states = [
        DailyPortfolioState(date="2025-01-01", cash={"USD": 0.0}, positions=[], total_market_value=1000.0, total_portfolio_value=1000.0),
        DailyPortfolioState(date="2025-01-02", cash={"USD": 0.0}, positions=[], total_market_value=1050.0, total_portfolio_value=1050.0),
        DailyPortfolioState(date="2025-01-03", cash={"USD": 0.0}, positions=[], total_market_value=1029.0, total_portfolio_value=1029.0),
    ]

    summary = build_portfolio_risk_summary(
        daily_states,
        [
            {"date": "2025-01-01", "price": 100.0, "adjClose": 100.0},
            {"date": "2025-01-02", "price": 110.0, "adjClose": 102.0},
            {"date": "2025-01-03", "price": 121.0, "adjClose": 99.96},
        ],
        "SPY",
    )

    assert summary.observations == 2
    assert summary.portfolio_beta is not None
    assert summary.portfolio_correlation is not None


def test_build_volatility_regime_payload_prefers_adjusted_benchmark_series_when_available() -> None:
    start = date(2025, 1, 1)
    daily_values = [1000.0, 1020.0, 999.6, 1019.592, 999.20016] * 16
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=value,
            total_portfolio_value=value,
        )
        for offset, value in enumerate(daily_values)
    ]
    benchmark_rows = [
        {"date": (start + timedelta(days=offset)).isoformat(), "price": 100.0 + offset, "adjClose": value}
        for offset, value in enumerate([100.0, 101.0, 98.98, 100.9596, 98.940408] * 16)
    ]

    payload = build_volatility_regime_payload(daily_states, benchmark_rows)

    assert payload.snapshot.benchmark_vol_20d is not None
    assert payload.snapshot.tracking_error_20d is not None


def test_build_statistical_factor_model_prefers_adjusted_factor_series_when_available() -> None:
    start = date(2025, 1, 1)
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=float(1000 + (offset * 2)),
            total_portfolio_value=float(1000 + (offset * 2)),
        )
        for offset in range(290)
    ]
    factor_histories = {
        definition.us_proxy: [
            {
                "date": (start + timedelta(days=offset)).isoformat(),
                "price": float(100 + offset),
                "adjClose": float(100 + (offset * 0.5) + (1 if definition.key == "market" else 0)),
            }
            for offset in range(290)
        ]
        for definition in DEFAULT_FACTOR_DEFINITIONS
    }

    factor_model = build_statistical_factor_model(daily_states, factor_histories, "SPY")

    assert factor_model.status in {"ok", "partial", "insufficient_history"}


def test_build_risk_contribution_breakdown_prefers_adjusted_factor_and_position_series_when_available() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 1, 1),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2025",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[],
        positions=[
            ImportedPosition(as_of_date=date(2025, 10, 17), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=100.0, market_value=600.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2025, 10, 17), symbol="MSFT", quantity=1.0, cost_basis=100.0, close_price=100.0, market_value=400.0, unrealized_pnl=0.0, currency="USD"),
        ],
        ledger_entries=[],
    )
    start = date(2025, 1, 1)
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=float(1000 + (offset * 5)),
            total_portfolio_value=float(1000 + (offset * 5)),
        )
        for offset in range(290)
    ]
    factor_histories = {
        definition.us_proxy: [
            {
                "date": (start + timedelta(days=offset)).isoformat(),
                "price": float(100 + offset),
                "adjClose": float(100 + (offset * 0.3) + ((offset % 7) * 0.2)),
            }
            for offset in range(290)
        ]
        for definition in DEFAULT_FACTOR_DEFINITIONS
    }
    price_histories = {
        "AAPL": [
            {"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset), "adjClose": float(100 + (offset * 0.4) + ((offset % 5) * 0.3))}
            for offset in range(290)
        ],
        "MSFT": [
            {"date": (start + timedelta(days=offset)).isoformat(), "price": float(80 + (offset * 0.5)), "adjClose": float(80 + (offset * 0.2) + ((offset % 3) * 0.25))}
            for offset in range(290)
        ],
    }
    factor_registry = build_factor_registry()
    factor_model = build_statistical_factor_model(daily_states, factor_histories, "SPY")

    breakdown = build_risk_contribution_breakdown(snapshot, daily_states, price_histories, factor_histories, factor_registry, factor_model)

    assert breakdown.factor_contributions
    assert breakdown.position_contributions
    assert breakdown.factor_total_variance is not None
    assert breakdown.total_variance is not None


def test_build_model_reliability_snapshot_uses_current_window_collinearity() -> None:
    start = date(2025, 1, 1)
    rows = [{"date": (start + timedelta(days=offset)).isoformat(), "price": float(100 + offset)} for offset in range(290)]
    factor_histories = {definition.us_proxy: rows for definition in DEFAULT_FACTOR_DEFINITIONS}
    daily_states = [
        DailyPortfolioState(
            date=(start + timedelta(days=offset)).isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=float(1000 + offset),
            total_portfolio_value=float(1000 + offset),
        )
        for offset in range(290)
    ]

    factor_model = build_statistical_factor_model(daily_states, factor_histories, "SPY")
    reliability = build_model_reliability_snapshot(factor_model)

    assert reliability.collinearity_pair_count >= 1
    assert reliability.max_abs_factor_correlation is not None
    assert reliability.max_abs_factor_correlation >= 0.85
def test_factor_registry_metadata_only_match_score_is_high_for_exact_equity_mapping() -> None:
    registry = build_factor_registry()
    market = next(item for item in registry if item.key == "market")

    assert market.primary_mapping is not None
    assert market.primary_mapping.match_summary is not None
    assert market.primary_mapping.match_summary.score_basis == "metadata_only"
    assert market.primary_mapping.match_summary.score_pct is not None
    assert market.primary_mapping.match_summary.score_pct >= 80


def test_factor_registry_bond_mapping_cap_metadata_is_exposed() -> None:
    registry = build_factor_registry()
    long_rates = next(item for item in registry if item.key == "rates_tlt")

    assert long_rates.primary_mapping is not None
    assert long_rates.primary_mapping.match_summary is not None
    assert long_rates.primary_mapping.match_summary.score_pct is not None
    assert long_rates.primary_mapping.match_summary.hard_cap_reason in {None, "bond_duration_bucket_mismatch", "hedge_status_mismatch"}


def test_factor_registry_distributing_mapping_is_degraded_in_metadata_mode() -> None:
    registry = build_factor_registry()
    growth = next(item for item in registry if item.key == "growth")

    assert growth.primary_mapping is not None
    assert growth.primary_mapping.match_summary is not None
    assert growth.primary_mapping.match_summary.score_status == "degraded"
def test_build_etf_overlap_pairs_returns_shared_holdings() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(importer="interactive_brokers", imported_at=datetime(2026, 1, 1), source_path="sample.pdf", detected_format="pdf", account_id="U123", base_currency="USD", statement_period="2025", page_count=1),
        statements=[],
        statement_totals=ImportedStatementTotals(starting_nav=1000.0, ending_nav=2000.0),
        instruments=[
            ImportedInstrument(symbol="VUAA", description="Vanguard S&P 500 UCITS ETF", listing_exchange="LSEETF", instrument_type="ETF"),
            ImportedInstrument(symbol="DFND", description="Defense ETF", listing_exchange="LSEETF", instrument_type="ETF"),
        ],
        cash_balances=[],
        positions=[
            ImportedPosition(as_of_date=date(2025, 12, 31), symbol="VUAA", quantity=1.0, cost_basis=900.0, close_price=900.0, market_value=900.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2025, 12, 31), symbol="DFND", quantity=1.0, cost_basis=100.0, close_price=100.0, market_value=100.0, unrealized_pnl=0.0, currency="USD"),
        ],
        ledger_entries=[],
    )

    class StubMarketData:
        def get_etf_holdings(self, symbol: str, symbol_overrides=None):
            holdings = {
                "VUAA": ("SPY", [
                    {"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 6.0},
                    {"asset": "MSFT", "name": "MICROSOFT CORP", "weightPercentage": 5.0},
                ]),
                "DFND": ("ITA", [
                    {"asset": "MSFT", "name": "MICROSOFT CORP", "weightPercentage": 2.0},
                    {"asset": "LMT", "name": "LOCKHEED MARTIN", "weightPercentage": 10.0},
                ]),
            }
            return holdings[symbol]

        def get_company_profile(self, symbol: str, symbol_overrides=None):
            return {"sector": "Technology" if symbol == "MSFT" else "Industrials"}

    overlaps = build_etf_overlap_pairs(snapshot, StubMarketData())

    assert len(overlaps) == 1
    assert overlaps[0].left_symbol == "VUAA"
    assert overlaps[0].right_symbol == "DFND"
    assert overlaps[0].shared_constituent_count == 1
    assert overlaps[0].top_shared_constituents[0].symbol == "MSFT"


def test_build_reconciliation_summary_passes_matching_totals() -> None:
    summary = build_reconciliation_summary(_sample_snapshot())

    assert summary.passed is True
    assert all(check.passed for check in summary.checks)


def _ledger_only_snapshot(
    ledger_entries: list[ImportedLedgerEntry],
    *,
    statement_period: str = "2026",
    statement_totals: ImportedStatementTotals | None = None,
) -> ImportedPortfolioSnapshot:
    """Minimal snapshot carrying just the ledger (+ optional totals) to exercise
    build_activity_series / build_reconciliation_summary (US-24.1 regressions)."""
    return ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 1, 1),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period=statement_period,
            page_count=1,
        ),
        statements=[],
        statement_totals=statement_totals,
        instruments=[],
        cash_balances=[],
        positions=[],
        ledger_entries=ledger_entries,
    )


def test_build_activity_series_includes_non_2025_entries() -> None:
    # US-24.1 regression: a 2026 statement previously returned [] because of a
    # hardcoded `entry.date.year != 2025` filter.
    snapshot = _ledger_only_snapshot([
        ImportedLedgerEntry(entry_type="DIVIDEND", trade_date=date(2026, 5, 1), symbol="AAPL", gross_amount=40.0, net_amount=40.0, currency="USD", source_section="Dividends"),
        ImportedLedgerEntry(entry_type="WITHHOLDING_TAX", trade_date=date(2026, 5, 1), symbol="AAPL", gross_amount=-8.0, net_amount=-8.0, currency="USD", source_section="Withholding Tax"),
    ])

    points = build_activity_series(snapshot)

    assert [point.month for point in points] == ["2026-05"]
    assert points[0].dividends == 40.0
    assert points[0].withholding_tax == 8.0


def test_build_activity_series_unchanged_for_2025_sample() -> None:
    # Behaviour-neutral pin: the existing 2025 fixture produces the same buckets
    # with or without the removed year filter.
    by_month = {point.month: point for point in build_activity_series(_sample_snapshot())}

    assert set(by_month) == {"2025-01", "2025-06", "2025-07", "2025-08"}
    assert by_month["2025-06"].dividends == 50.0
    assert by_month["2025-06"].withholding_tax == 10.0
    assert by_month["2025-07"].interest == 5.0
    assert by_month["2025-08"].fees == 2.0
    assert by_month["2025-01"].deposits == 100.0


def test_reconciliation_withholding_total_for_non_2025_statement() -> None:
    # US-24.1 regression: the withholding-tax actual previously summed only 2025
    # entries, so a 2026 statement reconciled against 0.
    snapshot = _ledger_only_snapshot(
        [ImportedLedgerEntry(entry_type="WITHHOLDING_TAX", trade_date=date(2026, 6, 1), symbol="AAPL", gross_amount=-12.0, net_amount=-12.0, currency="USD", source_section="Withholding Tax")],
        statement_totals=ImportedStatementTotals(withholding_tax_total=12.0),
    )

    summary = build_reconciliation_summary(snapshot)
    withholding_check = next(check for check in summary.checks if check.name == "withholding_tax_total")

    assert withholding_check.actual == 12.0
    assert withholding_check.passed is True


def test_build_activity_series_spans_multiple_years() -> None:
    # A stacked statement spanning 2025-2026: every year's months are represented.
    snapshot = _ledger_only_snapshot([
        ImportedLedgerEntry(entry_type="DEPOSIT", trade_date=date(2025, 12, 1), gross_amount=100.0, net_amount=100.0, currency="USD", source_section="Deposits & Withdrawals"),
        ImportedLedgerEntry(entry_type="DEPOSIT", trade_date=date(2026, 1, 5), gross_amount=200.0, net_amount=200.0, currency="USD", source_section="Deposits & Withdrawals"),
    ])

    points = build_activity_series(snapshot)

    assert [point.month for point in points] == ["2025-12", "2026-01"]
    assert points[0].deposits == 100.0
    assert points[1].deposits == 200.0


def test_rebalance_trade_application_updates_state() -> None:
    state = DailyPortfolioState(
        date="2025-12-31",
        cash={"USD": 100.0},
        positions=[DailyStatePosition(symbol="AAPL", quantity=10.0, market_price=100.0, market_value=1000.0)],
        total_market_value=1000.0,
        total_portfolio_value=1100.0,
    )
    trades = build_simulated_rebalance_trades([state], target_equity_weight=0.95, tolerance=0.01)
    updated = apply_simulated_trades_to_state(state, trades)

    assert updated is not None
    assert updated.total_portfolio_value != state.total_portfolio_value or updated.cash != state.cash


def test_build_rebalance_preview_flags_underinvested_state() -> None:
    state = DailyPortfolioState(
        date="2025-12-31",
        cash={"USD": 500.0},
        positions=[DailyStatePosition(symbol="AAPL", quantity=5.0, market_price=100.0, market_value=500.0)],
        total_market_value=500.0,
        total_portfolio_value=1000.0,
    )

    preview = build_rebalance_preview([state], [{"date": "2025-12-31", "price": 600.0}], target_equity_weight=0.9)

    assert preview[0].action == "buy_equities"


def test_snapshot_to_ledger_preserves_trade_and_cash_fields() -> None:
    ledger = snapshot_to_ledger(_sample_snapshot())

    assert len(ledger) == 5
    assert ledger[0].date.isoformat() == "2025-01-02"
    assert ledger[0].entry_type == "DEPOSIT"
    assert ledger[0].cash_effect == 100.0
    assert ledger[0].cash_movement_classification == "external_capital_flow"
    assert "broker_transfer_section_line" in ledger[0].broker_evidence
    assert ledger[-1].entry_type == "FEE"
    assert ledger[-1].cash_effect == -2.0
    assert ledger[-1].cash_movement_classification == "broker_explicit_fee"


def test_portfolio_proof_cash_flow_witnesses_narrow_to_unknown_cash_movements() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-23",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=500.0, ending_cash=620.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 23), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=120.0, market_value=120.0, unrealized_pnl=20.0, currency="USD")],
        ledger_entries=[
            ImportedLedgerEntry(entry_type="DEPOSIT", trade_date=date(2026, 4, 10), gross_amount=200.0, net_amount=200.0, currency="USD", source_section="Deposits & Withdrawals", source_line="2026-04-10 ACH 200.00"),
            ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 11), symbol="AAPL", quantity=1.0, price=100.0, gross_amount=-100.0, net_amount=-101.0, fee=1.0, currency="USD", source_section="Trades", source_line="AAPL 2026-04-11 1 100"),
            ImportedLedgerEntry(entry_type="DIVIDEND", trade_date=date(2026, 4, 15), symbol="AAPL", gross_amount=10.0, net_amount=10.0, currency="USD", source_section="Unknown Income", source_line="mystery dividend line"),
        ],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-23", "price": 120.0}]},
        valuation_dates=["2026-04-10", "2026-04-23"],
        fx_history={},
        history_source="imported_replay",
    )

    assert proof.verified_total_return_emitted is False
    assert proof.replay_status == "replay_usable"
    assert proof.opening_state_status == "opening_state_verified"
    assert proof.evidence.cash_flow_basis.disqualifiers == ["unknown_cash_movements"]
    assert proof.evidence.cash_flow_basis.witnesses[0].counts == {"external_capital_flow": 1}
    assert proof.evidence.cash_flow_basis.witnesses[1].counts == {"internal_trading_flow": 1}
    assert proof.evidence.cash_flow_basis.witnesses[3].counts == {"unknown": 1}
    assert proof.evidence.cash_flow_basis.witnesses[3].evidence == ["unknown_cash_flow_entry_types:dividend"]
    assert proof.evidence.opening_state_basis.witnesses[0].status == "broker_proven"
    assert proof.evidence.opening_state_basis.witnesses[2].status == "broker_proven"
    assert proof.evidence.opening_state_basis.witnesses[3].status == "trade_window_covered"
    assert proof.evidence.opening_state_basis.witnesses[4].status == "trade_window_covered"
    assert proof.evidence.opening_state_basis.witnesses[5].status == "broker_statement_period_boundary"
    assert proof.evidence.opening_state_basis.witnesses[6].status == "opening_state_verified"


def test_portfolio_proof_corporate_action_policy_tracks_broker_native_cash_dividend_scope() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-23",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=100.0, ending_cash=115.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 23), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=120.0, market_value=120.0, unrealized_pnl=20.0, currency="USD")],
        ledger_entries=[
            ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=1.0, price=100.0, gross_amount=100.0, net_amount=-100.0, currency="USD", source_section="Trades", source_line="AAPL 2026-04-10 1 100"),
            ImportedLedgerEntry(entry_type="DIVIDEND", trade_date=date(2026, 4, 15), symbol="AAPL", gross_amount=15.0, net_amount=15.0, currency="USD", source_section="Dividends", source_line="AAPL CASH DIVIDEND 15.00"),
        ],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-23", "price": 120.0}]},
        valuation_dates=["2026-04-10", "2026-04-23"],
        fx_history={},
        history_source="imported_replay",
    )

    assert proof.portfolio_path == "withheld"
    assert proof.verified_total_return_emitted is False
    assert proof.evidence.corporate_action_basis.policy.model_dump() == {
        "scope": "broker_native_statement_window",
        "cash_dividend_coverage_status": "cash_dividend_coverage_proven_by_broker_native_evidence",
        "cash_dividend_observation_status": "cash_dividend_observed_by_broker_native_evidence",
        "non_dividend_status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
        "scope_start_date": "2026-04-10",
        "scope_end_date": "2026-04-23",
        "statement_window_count": 1,
    }
    assert proof.evidence.corporate_action_basis.positive_evidence == [
        "cash_dividend_coverage_proven_by_broker_native_evidence",
        "cash_dividend_observed_by_broker_native_evidence",
        "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
    ]
    assert proof.evidence.corporate_action_basis.negative_evidence == []
    assert [witness.model_dump() for witness in proof.evidence.corporate_action_basis.witnesses] == [
        {
            "label": "corporate_action_basis_policy",
            "status": "cash_dividend_scope_only",
            "evidence": [
                "positive_proof_limited_to:cash_dividend",
                "coverage_and_absence_semantics_require:broker_native_statement_window",
                "positive_observation_requires:broker_dividend_section_line_within_statement_window",
                "non_dividend_corporate_actions_remain_unproven_and_disqualifying",
            ],
            "counts": {"statement_window_count": 1},
        },
        {
            "label": "cash_dividend_coverage_scope",
            "status": "cash_dividend_coverage_proven_by_broker_native_evidence",
            "evidence": ["broker_native_statement_windows:2026-04-10->2026-04-23"],
            "counts": {"statement_window_count": 1},
        },
        {
            "label": "cash_dividend_observation_scope",
            "status": "cash_dividend_observed_by_broker_native_evidence",
            "evidence": ["broker_native_dividend_dates:2026-04-15"],
            "counts": {"broker_native_dividend_count": 1},
        },
        {
            "label": "non_dividend_corporate_action_scope",
            "status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
            "evidence": [
                "supported_non_dividend_classes:none_observed_within_broker_native_statement_window",
                "unresolved_non_dividend_classes_would_remain_blocking:splits,reverse_splits,spin_offs,mergers,rights,return_of_capital,symbol_changes",
            ],
            "counts": {},
        },
    ]


def test_portfolio_proof_corporate_action_policy_does_not_claim_absence_without_broker_scope() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="snapshot.json",
            detected_format="snapshot",
            account_id="U123",
            base_currency="USD",
            statement_period=None,
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 23), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=110.0, market_value=110.0, unrealized_pnl=10.0, currency="USD")],
        ledger_entries=[],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-23", "price": 110.0}]},
        valuation_dates=["2026-04-10", "2026-04-23"],
        fx_history={},
        history_source="synthetic_snapshot_history",
    )

    assert proof.portfolio_path == "withheld"
    assert proof.verified_total_return_emitted is False
    assert proof.evidence.corporate_action_basis.policy.model_dump() == {
        "scope": "broker_scope_unproven",
        "cash_dividend_coverage_status": "cash_dividend_coverage_unproven",
        "cash_dividend_observation_status": "cash_dividend_observation_unproven",
        "non_dividend_status": "non_dividend_corporate_actions_unproven_and_disqualifying",
        "scope_start_date": None,
        "scope_end_date": None,
        "statement_window_count": 0,
    }
    assert proof.evidence.corporate_action_basis.positive_evidence == []
    assert proof.evidence.corporate_action_basis.negative_evidence == [
        "cash_dividend_coverage_unproven_without_broker_native_statement_window",
        "cash_dividend_observation_unproven_without_covered_broker_scope",
        "non_dividend_corporate_actions_unproven_and_disqualifying",
    ]
    assert proof.evidence.corporate_action_basis.witnesses[1].status == "cash_dividend_coverage_unproven"
    assert proof.evidence.corporate_action_basis.witnesses[2].status == "cash_dividend_observation_unproven"


def test_portfolio_proof_valuation_witnesses_capture_mixed_forward_fill_and_snapshot_fallback() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=300.0,
            ending_nav=325.0,
            stock_total=275.0,
            cash_total=50.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=50.0, ending_cash=50.0)],
        positions=[
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=110.0, market_value=110.0, unrealized_pnl=10.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="MSFT", quantity=1.0, cost_basis=200.0, close_price=215.0, market_value=215.0, unrealized_pnl=15.0, currency="USD"),
        ],
        ledger_entries=[],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}]},
        valuation_dates=["2026-04-10", "2026-04-11"],
        fx_history={},
        history_source="imported_replay",
    )

    assert proof.portfolio_path == "withheld"
    assert proof.verified_total_return_emitted is False
    assert proof.replay_status == "replay_usable"
    assert proof.opening_state_status == "opening_state_unverified"
    assert proof.evidence.valuation_basis.disqualifiers == [
        "forward_filled_prices",
        "mixed_basis_valuation",
        "raw_price_used_for_valuation",
        "snapshot_close_price_fallback",
    ]
    assert proof.evidence.valuation_basis.negative_evidence == [
        "vendor_raw_price_used_for_valuation",
        "position_prices_forward_filled",
        "snapshot_close_price_fallback_used",
        "mixed_basis_valuation_construction_used",
    ]
    assert proof.evidence.valuation_basis.witnesses[0].label == "valuation_input_policy"
    assert proof.evidence.valuation_basis.witnesses[1].status == "imported_replay"
    assert proof.evidence.valuation_basis.witnesses[2].label == "valuation_window_basis:2026-04-10:2026-04-11"
    assert proof.evidence.valuation_basis.witnesses[2].status == "mixed_basis_construction"
    assert proof.evidence.valuation_basis.witnesses[2].evidence == [
        "valuation_window_dates:2026-04-10->2026-04-11",
        "mixed_basis_inputs:forward_fill,raw_vendor_price,snapshot_fallback",
    ]
    assert proof.evidence.valuation_basis.witnesses[2].counts == {
        "valuation_date_count": 2,
        "valued_symbol_count": 4,
        "forward_fill": 1,
        "raw_vendor_price": 1,
        "snapshot_fallback": 2,
    }


def test_portfolio_proof_boundary_witnesses_separate_broker_replay_and_disqualified_windows() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=110.0, market_value=110.0, unrealized_pnl=10.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=1.0, price=100.0, gross_amount=100.0, net_amount=100.0, currency="USD", source_section="Trades")],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 110.0}, {"date": "2026-04-12", "price": 111.0}]},
        valuation_dates=["2026-04-10", "2026-04-11", "2026-04-12"],
        fx_history={},
        history_source="imported_replay",
    )

    assert proof.portfolio_path == "withheld"
    assert proof.verified_total_return_emitted is False
    assert proof.replay_status == "replay_usable"
    assert proof.opening_state_status == "opening_state_unverified"
    assert proof.hard_disqualifiers == [
        "opening_cash_state_missing",
        "raw_price_used_for_valuation",
        "replay_window_outside_broker_coverage",
    ]
    assert proof.evidence.calendar_coverage_basis.hard_disqualifiers == [
        "replay_window_outside_broker_coverage",
    ]
    assert proof.evidence.calendar_coverage_basis.positive_evidence == [
        "valuation_window_dates_available",
        "valuation_dates_are_sorted_and_unique",
        "broker_statement_period_windows_available",
        "broker_statement_calendar_continuity_observed",
    ]
    assert proof.evidence.calendar_coverage_basis.negative_evidence == [
        "valuation_calendar_is_derived_from_benchmark_history",
        "replay_window_extends_outside_broker_statement_coverage",
    ]
    assert proof.evidence.calendar_coverage_basis.disqualifiers == [
        "replay_window_outside_broker_coverage",
    ]
    assert [witness.model_dump() for witness in proof.evidence.calendar_coverage_basis.witnesses] == [
        {
            "label": "first_covered_date_basis",
            "status": "broker_statement_period_boundary",
            "evidence": ["broker_statement_period_first_covered_date:2026-04-10"],
            "counts": {},
        },
        {
            "label": "last_covered_date_basis",
            "status": "broker_statement_period_boundary",
            "evidence": ["broker_statement_period_last_covered_date:2026-04-11"],
            "counts": {},
        },
        {
            "label": "replay_derived_window:2026-04-10:2026-04-12",
            "status": "replay_derived_window",
            "evidence": ["replay_window_dates:2026-04-10->2026-04-12"],
            "counts": {"valuation_date_count": 3},
        },
        {
            "label": "calendar_continuity_basis",
            "status": "broker_statement_period_contiguous",
            "evidence": ["broker_statement_calendar_window:2026-04-10->2026-04-11"],
            "counts": {"statement_window_count": 1, "gap_count": 0},
        },
        {
            "label": "broker_covered_window:2026-04-10:2026-04-11",
            "status": "broker_covered_window",
            "evidence": ["broker_statement_period_window:2026-04-10->2026-04-11"],
            "counts": {"valuation_date_count": 2},
        },
        {
            "label": "disqualified_window:2026-04-12",
            "status": "disqualified_window",
            "evidence": ["replay_window_outside_broker_statement_coverage:2026-04-12->2026-04-12"],
            "counts": {"valuation_date_count": 1},
        },
    ]


def test_portfolio_proof_terminal_reconciliation_witness_distinguishes_natural_vs_force_reconciled() -> None:
    force_snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1300.0,
            cash_total=300.0,
            stock_total=1000.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=300.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=100.0, market_value=1000.0, unrealized_pnl=0.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=-1000.0, currency="USD", source_section="Trades")],
    )
    natural_snapshot = force_snapshot.model_copy(
        update={
            "statement_totals": ImportedStatementTotals(
                starting_nav=1000.0,
                ending_nav=1000.0,
                cash_total=0.0,
                stock_total=1000.0,
                fx_rates={"USDUSD": 1.0},
            )
        }
    )

    force_proof = build_portfolio_proof_metadata(
        snapshot=force_snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 100.0}]},
        valuation_dates=["2026-04-10", "2026-04-11"],
        fx_history={},
        history_source="imported_replay",
    )
    natural_proof = build_portfolio_proof_metadata(
        snapshot=natural_snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 100.0}]},
        valuation_dates=["2026-04-10", "2026-04-11"],
        fx_history={},
        history_source="imported_replay",
    )

    assert force_proof.portfolio_path == "withheld"
    assert force_proof.verified_total_return_emitted is False
    assert force_proof.replay_status == "replay_usable"
    assert force_proof.opening_state_status == "opening_state_unverified"
    assert force_proof.evidence.terminal_reconciliation_basis.positive_evidence == []
    assert force_proof.evidence.terminal_reconciliation_basis.negative_evidence == [
        "terminal_state_requires_force_reconciliation_to_statement_totals"
    ]
    assert force_proof.evidence.terminal_reconciliation_basis.disqualifiers == ["terminal_force_reconciliation_present"]
    assert force_proof.evidence.terminal_reconciliation_basis.hard_disqualifiers == ["terminal_force_reconciliation_present"]
    assert force_proof.evidence.terminal_reconciliation_basis.witnesses[0].model_dump() == {
        "label": "terminal_reconciliation_basis",
        "status": "force_reconciled_terminal_state",
        "evidence": [
            "terminal_nav_match:false",
            "terminal_cash_match:false",
            "force_matching_statement_totals_do_not_count_as_terminal_proof",
        ],
        "counts": {"compared_field_count": 2},
    }

    assert natural_proof.evidence.terminal_reconciliation_basis.positive_evidence == [
        "terminal_state_naturally_reconciles_to_statement_totals"
    ]
    assert natural_proof.opening_state_status == "opening_state_unverified"
    assert natural_proof.evidence.terminal_reconciliation_basis.negative_evidence == []
    assert natural_proof.evidence.terminal_reconciliation_basis.disqualifiers == []
    assert natural_proof.evidence.terminal_reconciliation_basis.hard_disqualifiers == []
    assert natural_proof.evidence.terminal_reconciliation_basis.witnesses[0].model_dump() == {
        "label": "terminal_reconciliation_basis",
        "status": "naturally_reconciled_terminal_state",
        "evidence": ["terminal_nav_match:true", "terminal_cash_match:true"],
        "counts": {"compared_field_count": 2},
    }


def test_portfolio_proof_inferred_opening_boundary_is_replay_usable_but_not_opening_verified() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-23",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1200.0,
            cash_total=100.0,
            stock_total=1100.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=100.0, ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 23), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=110.0, market_value=1100.0, unrealized_pnl=100.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 20), symbol="AAPL", quantity=2.0, price=100.0, gross_amount=200.0, net_amount=-200.0, currency="USD", source_section="Trades")],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-23", "price": 110.0}]},
        valuation_dates=["2026-04-10", "2026-04-23"],
        fx_history={},
        history_source="imported_replay",
    )

    assert proof.replay_status == "replay_usable"
    assert proof.opening_state_status == "opening_state_unverified"
    assert "inferred_opening_holdings" in proof.disqualifiers
    assert "inferred_opening_quantities" in proof.hard_disqualifiers
    assert proof.evidence.opening_state_basis.disqualifiers == [
        "inferred_opening_holdings",
        "inferred_opening_quantities",
    ]
    assert proof.evidence.opening_state_basis.witnesses[3].model_dump() == {
        "label": "opening_holdings_state",
        "status": "unknown_inferred",
        "evidence": [
            "accepted_source_missing:broker_trade_window_opening_holdings",
            "opening_holdings_require_inference_from_ending_positions_and_trades",
        ],
        "counts": {"inferred_symbol_count": 1},
    }
    assert proof.evidence.opening_state_basis.witnesses[4].model_dump() == {
        "label": "opening_quantities_state",
        "status": "unknown_inferred",
        "evidence": [
            "accepted_source_missing:broker_trade_window_opening_quantities",
            "opening_quantities_require_inference_from_ending_positions_and_trades",
        ],
        "counts": {"inferred_symbol_count": 1},
    }
    assert proof.evidence.opening_state_basis.witnesses[6].model_dump() == {
        "label": "opening_state_admission",
        "status": "opening_state_unverified",
        "evidence": [
            "replay_status:replay_usable",
            "proof_eligibility_blocked_until_opening_state_verified",
        ],
        "counts": {},
    }


def test_portfolio_proof_fx_identity_case_is_machine_readable() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-23",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=100.0, ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 23), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=110.0, market_value=110.0, unrealized_pnl=10.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=1.0, price=100.0, gross_amount=100.0, net_amount=-100.0, currency="USD", source_section="Trades")],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-23", "price": 110.0}]},
        valuation_dates=["2026-04-10", "2026-04-23"],
        fx_history={},
        history_source="imported_replay",
    )

    assert proof.evidence.fx_basis.status == "supported"
    assert proof.evidence.fx_basis.positive_evidence == ["all_observed_statement_currencies_match_base_currency"]
    assert proof.evidence.fx_basis.disqualifiers == []
    assert [witness.model_dump() for witness in proof.evidence.fx_basis.witnesses] == [
        {
            "label": "fx_base_currency_state",
            "status": "broker_proven",
            "evidence": ["accepted_source:broker_statement_base_currency:USD"],
            "counts": {},
        },
        {
            "label": "fx_currency_observation_scope",
            "status": "observed_currency_scope",
            "evidence": [
                "observed_statement_currencies:USD",
                "observed_cash_currencies:USD",
                "observed_ledger_currencies:USD",
                "observed_position_currencies:USD",
            ],
            "counts": {
                "statement_currency_count": 1,
                "cash_currency_count": 1,
                "ledger_currency_count": 1,
                "position_currency_count": 1,
                "observed_currency_count": 1,
            },
        },
        {
            "label": "fx_translation_requirement",
            "status": "identity_case_supported",
            "evidence": ["all_observed_currencies_equal_base:USD"],
            "counts": {"observed_currency_count": 1},
        },
    ]


def test_portfolio_proof_fx_requires_broker_proven_base_currency() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency=None,
            statement_period="2026-04-10 - 2026-04-23",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 23), symbol="AAPL", quantity=1.0, cost_basis=100.0, close_price=110.0, market_value=110.0, unrealized_pnl=10.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=1.0, price=100.0, gross_amount=100.0, net_amount=-100.0, currency="USD", source_section="Trades")],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-23", "price": 110.0}]},
        valuation_dates=["2026-04-10", "2026-04-23"],
        fx_history={},
        history_source="imported_replay",
    )

    assert "missing_base_currency" in proof.disqualifiers
    assert proof.evidence.fx_basis.status == "disqualified"
    assert proof.evidence.fx_basis.negative_evidence == ["broker_statement_base_currency_missing"]
    assert proof.evidence.fx_basis.disqualifiers == ["missing_base_currency"]
    assert proof.evidence.fx_basis.hard_disqualifiers == ["missing_base_currency"]
    assert proof.evidence.fx_basis.witnesses[0].model_dump() == {
        "label": "fx_base_currency_state",
        "status": "missing_broker_evidence",
        "evidence": ["accepted_source_missing:broker_statement_base_currency"],
        "counts": {},
    }


def test_portfolio_proof_fx_disqualifies_missing_pair_date_coverage() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-23",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=0.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 23), symbol="SAP", quantity=1.0, cost_basis=100.0, close_price=110.0, market_value=110.0, unrealized_pnl=10.0, currency="EUR")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="SAP", quantity=1.0, price=100.0, gross_amount=100.0, net_amount=-100.0, currency="EUR", source_section="Trades")],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"SAP": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-23", "price": 110.0}]},
        valuation_dates=["2026-04-10", "2026-04-23"],
        fx_history={
            "series": {
                "EURUSD": [
                    {
                        "date": "2026-04-10",
                        "rate": 1.1,
                        "provenance": "broker_fx_feed",
                    }
                ]
            }
        },
        history_source="imported_replay",
    )

    assert proof.evidence.fx_basis.status == "disqualified"
    assert proof.evidence.fx_basis.positive_evidence == ["non_base_currency_exposure_observed"]
    assert proof.evidence.fx_basis.negative_evidence == ["historical_fx_series_missing_required_pair_dates"]
    assert proof.evidence.fx_basis.disqualifiers == ["missing_pair_date_coverage"]
    assert proof.evidence.fx_basis.hard_disqualifiers == ["missing_pair_date_coverage"]
    assert proof.evidence.fx_basis.witnesses[2].model_dump() == {
        "label": "fx_translation_requirement",
        "status": "dated_fx_series_required",
        "evidence": [
            "non_base_currency_conversion_required_for_portfolio_replay",
            "required_non_base_pairs:EURUSD",
        ],
        "counts": {"required_pair_count": 1, "required_pair_date_count": 2},
    }
    assert proof.evidence.fx_basis.witnesses[3].model_dump() == {
        "label": "fx_pair_date_coverage",
        "status": "missing_pair_date_coverage",
        "evidence": ["missing_pair_dates:EURUSD@2026-04-23"],
        "counts": {"missing_pair_date_count": 1},
    }


def test_portfolio_proof_admits_one_exact_slice_when_full_proof_bar_is_explicitly_met() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1030.0,
            cash_total=0.0,
            stock_total=1030.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=1000.0, ending_cash=0.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=103.0, market_value=1030.0, unrealized_pnl=30.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=-1000.0, currency="USD", source_section="Trades")],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={
            "AAPL": [
                {"date": "2026-04-10", "price": 100.0, "basis": "broker_proven_mark_to_market"},
                {"date": "2026-04-11", "price": 103.0, "basis": "broker_proven_mark_to_market"},
            ]
        },
        valuation_dates=["2026-04-10", "2026-04-11"],
        fx_history={},
        history_source="imported_replay",
    )

    assert proof.portfolio_path == "verified"
    assert proof.verification_status == "verified"
    assert proof.output_status == "available"
    assert proof.verified_total_return_emitted is True
    assert proof.opening_state_status == "opening_state_verified"
    assert proof.disqualifiers == []
    assert proof.hard_disqualifiers == []
    assert proof.preparation.readiness_status == "exact_slice_admitted"
    assert proof.preparation.all_prerequisite_buckets_supported is True
    assert proof.preparation.policy_blockers == []
    assert proof.admission.status == "admitted"
    assert proof.admission.readiness_status == "exact_slice_admitted"
    assert proof.admission.blocking_reasons == []
    assert proof.admission.missing_proof_buckets == []
    assert all(bucket.status == "admitted" and bucket.blocks_admission is False for bucket in proof.admission.bucket_decisions)
    assert proof.evidence.valuation_basis.status == "supported"
    assert proof.evidence.valuation_basis.positive_evidence == [
        "valuation_dates_available",
        "position_price_histories_loaded",
        "broker_proven_mark_to_market_inputs_observed",
    ]
    assert proof.evidence.valuation_basis.negative_evidence == []
    assert proof.evidence.valuation_basis.disqualifiers == []
    assert proof.evidence.calendar_coverage_basis.status == "supported"
    assert proof.evidence.calendar_coverage_basis.disqualifiers == []
    assert proof.evidence.terminal_reconciliation_basis.status == "supported"
    assert proof.evidence.terminal_reconciliation_basis.positive_evidence == ["terminal_state_naturally_reconciles_to_statement_totals"]
    assert proof.evidence.corporate_action_basis.status == "supported"
    assert proof.evidence.corporate_action_basis.policy.non_dividend_status == "no_non_dividend_corporate_actions_observed_within_covered_broker_scope"
    assert proof.evidence.corporate_action_basis.positive_evidence == [
        "cash_dividend_coverage_proven_by_broker_native_evidence",
        "no_cash_dividend_observed_within_covered_broker_scope",
        "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
    ]
    assert proof.evidence.corporate_action_basis.negative_evidence == []
    assert proof.evidence.corporate_action_basis.disqualifiers == []
    assert proof.evidence.investor_economics_proof.status == "supported"
    assert proof.evidence.investor_economics_proof.decision == "admitted"
    assert proof.evidence.investor_economics_proof.preparation_status == "exact_slice_admitted"
    assert proof.evidence.investor_economics_proof.blocking_reasons == []
    assert proof.evidence.investor_economics_proof.missing_proof_buckets == []
    assert proof.evidence.investor_economics_proof.scope_mismatches == []
    assert "policy_id:portfolio_exact_slice_admission_policy_v1" in proof.evidence.investor_economics_proof.positive_evidence


def test_portfolio_proof_rejects_exact_slice_when_non_dividend_corporate_action_scope_is_unresolved() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1030.0,
            cash_total=0.0,
            stock_total=1030.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=1000.0, ending_cash=0.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=103.0, market_value=1030.0, unrealized_pnl=30.0, currency="USD")],
        ledger_entries=[
            ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=-1000.0, currency="USD", source_section="Trades"),
            ImportedLedgerEntry(entry_type="DIVIDEND", trade_date=date(2026, 4, 11), symbol="AAPL", gross_amount=5.0, net_amount=5.0, currency="USD", source_section="Unknown Income", source_line="unresolved cash event"),
        ],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={
            "AAPL": [
                {"date": "2026-04-10", "price": 100.0, "basis": "broker_proven_mark_to_market"},
                {"date": "2026-04-11", "price": 103.0, "basis": "broker_proven_mark_to_market"},
            ]
        },
        valuation_dates=["2026-04-10", "2026-04-11"],
        fx_history={},
        history_source="imported_replay",
    )

    assert proof.portfolio_path == "withheld"
    assert proof.verified_total_return_emitted is False
    assert proof.admission.status == "withheld"
    assert proof.preparation.readiness_status == "exact_slice_prerequisites_incomplete"
    assert proof.admission.missing_proof_buckets == [
        "boundary_calendar_terminal_proof",
        "boundary_hardening",
        "capital_boundary_proof",
        "investor_economics_proof",
    ]
    assert proof.evidence.cash_flow_basis.disqualifiers == ["unknown_cash_movements"]
    assert proof.evidence.corporate_action_basis.disqualifiers == []
    assert proof.evidence.investor_economics_proof.blocking_reasons == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "capital_boundary_positive_support_missing_for_portfolio_slice",
        "terminal_force_reconciliation_present",
        "unknown_cash_movements",
    ]


def test_portfolio_proof_fx_disqualifies_inferred_fallback_forward_fill_and_mixed_source_fx() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 23),
            source_path="IB2026.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-23",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=0.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 23), symbol="SAP", quantity=1.0, cost_basis=100.0, close_price=110.0, market_value=110.0, unrealized_pnl=10.0, currency="EUR")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="SAP", quantity=1.0, price=100.0, gross_amount=100.0, net_amount=-100.0, currency="EUR", source_section="Trades")],
    )

    proof = build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories={"SAP": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-23", "price": 110.0}]},
        valuation_dates=["2026-04-10", "2026-04-23"],
        fx_history={
            "series": {
                "EURUSD": [
                    {
                        "date": "2026-04-10",
                        "rate": 1.1,
                        "provenance": "broker_fx_feed",
                        "fallback_used": True,
                    },
                    {
                        "date": "2026-04-23",
                        "rate": 1.2,
                        "vendor": "FMP",
                        "endpoint": "fx/light",
                        "inferred": True,
                        "forward_filled": True,
                        "mixed_source": True,
                    },
                ]
            }
        },
        history_source="imported_replay",
    )

    assert proof.evidence.fx_basis.status == "disqualified"
    assert proof.evidence.fx_basis.positive_evidence == [
        "non_base_currency_exposure_observed",
        "dated_provenance_backed_fx_series_cover_all_required_conversions",
    ]
    assert proof.evidence.fx_basis.negative_evidence == [
        "inferred_translation_present",
        "fallback_fx_used",
        "forward_filled_fx_used",
        "mixed_source_fx_present",
    ]
    assert proof.evidence.fx_basis.disqualifiers == [
        "fallback_fx_used",
        "forward_filled_fx_used",
        "inferred_translation",
        "mixed_source_fx",
    ]
    assert proof.evidence.fx_basis.hard_disqualifiers == [
        "fallback_fx_used",
        "forward_filled_fx_used",
        "inferred_translation",
        "mixed_source_fx",
    ]
    assert proof.evidence.fx_basis.witnesses[3].model_dump() == {
        "label": "fx_pair_date_coverage",
        "status": "full_pair_date_coverage",
        "evidence": ["covered_pair_dates:EURUSD@2026-04-10,EURUSD@2026-04-23"],
        "counts": {"covered_pair_date_count": 2},
    }
    assert proof.evidence.fx_basis.witnesses[4].model_dump() == {
        "label": "fx_translation_provenance",
        "status": "inferred_translation",
        "evidence": ["inferred_pair_dates:EURUSD@2026-04-23"],
        "counts": {"inferred_pair_date_count": 1},
    }
    assert proof.evidence.fx_basis.witnesses[5].model_dump() == {
        "label": "fx_fallback_policy",
        "status": "fallback_fx_used",
        "evidence": ["affected_pair_dates:EURUSD@2026-04-10"],
        "counts": {"affected_pair_date_count": 1},
    }
    assert proof.evidence.fx_basis.witnesses[6].model_dump() == {
        "label": "fx_forward_fill_policy",
        "status": "forward_filled_fx_used",
        "evidence": ["affected_pair_dates:EURUSD@2026-04-23"],
        "counts": {"affected_pair_date_count": 1},
    }
    assert proof.evidence.fx_basis.witnesses[7].model_dump() == {
        "label": "fx_source_consistency",
        "status": "mixed_source_fx",
        "evidence": ["mixed_source_pair_dates:EURUSD@2026-04-23"],
        "counts": {"mixed_pair_date_count": 1, "provenance_signature_count": 1},
    }


def test_reconstruct_position_lots_creates_opening_balance_lot() -> None:
    lots = reconstruct_position_lots(_sample_snapshot())

    assert len(lots) == 1
    assert lots[0].symbol == "AAPL"
    assert lots[0].source == "opening_balance"
    assert lots[0].remaining_quantity == 10.0
    assert lots[0].remaining_cost_basis == 800.0


def test_portfolio_state_engine_replays_multi_day_ledger_activity() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 1, 1),
            source_path="sample.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2025",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1348.0,
            stock_total=510.0,
            cash_total=838.0,
            fx_rates={"USDUSD": 1.0},
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", starting_cash=1000.0, ending_cash=838.0)],
        positions=[
            ImportedPosition(
                as_of_date=date(2025, 1, 3),
                symbol="AAPL",
                quantity=3.0,
                cost_basis=310.0,
                close_price=170.0,
                market_value=510.0,
                unrealized_pnl=200.0,
                currency="USD",
            )
        ],
        ledger_entries=[
            ImportedLedgerEntry(
                entry_type="BUY",
                trade_date=date(2025, 1, 2),
                symbol="AAPL",
                quantity=5.0,
                price=100.0,
                gross_amount=-500.0,
                net_amount=-501.0,
                fee=1.0,
                currency="USD",
                source_section="Trades",
            ),
            ImportedLedgerEntry(
                entry_type="DIVIDEND",
                trade_date=date(2025, 1, 2),
                symbol="AAPL",
                gross_amount=20.0,
                net_amount=20.0,
                currency="USD",
                source_section="Dividends",
            ),
            ImportedLedgerEntry(
                entry_type="SELL",
                trade_date=date(2025, 1, 3),
                symbol="AAPL",
                quantity=2.0,
                price=160.0,
                gross_amount=320.0,
                net_amount=319.0,
                fee=1.0,
                currency="USD",
                source_section="Trades",
            ),
        ],
    )

    engine = PortfolioStateEngine(snapshot=snapshot, base_currency="USD", fx_history={})
    states = engine.build_daily_states(
        price_histories={"AAPL": [{"date": "2025-01-02", "price": 150.0}, {"date": "2025-01-03", "price": 170.0}]},
        valuation_dates=["2025-01-02", "2025-01-03"],
    )

    assert len(states) == 2
    assert states[0].cash["USD"] == 519.0
    assert states[0].positions[0].quantity == 5.0
    assert states[0].total_portfolio_value == 1269.0
    assert states[1].cash["USD"] == 838.0
    assert states[1].positions[0].quantity == 3.0
    assert states[1].total_market_value == 510.0
    assert states[1].total_portfolio_value == 1348.0


def test_performance_series_excludes_external_cash_contributions_from_returns() -> None:
    states = [
        DailyPortfolioState(
            date="2025-01-02",
            cash={"USD": 1000.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1000.0,
            external_cash_flow=0.0,
        ),
        DailyPortfolioState(
            date="2025-01-03",
            cash={"USD": 1100.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1100.0,
            external_cash_flow=100.0,
        ),
        DailyPortfolioState(
            date="2025-01-04",
            cash={"USD": 1155.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1155.0,
            external_cash_flow=0.0,
        ),
    ]

    series = build_true_performance_series(
        states,
        [
            {"date": "2025-01-02", "price": 100.0},
            {"date": "2025-01-03", "price": 101.0},
            {"date": "2025-01-04", "price": 102.0},
        ],
    )

    assert series[0].portfolio_return_pct == 0.0
    assert series[1].portfolio_return_pct == 0.0
    assert series[2].portfolio_return_pct == 5.0


def test_portfolio_state_engine_reconciles_terminal_state_to_statement_totals() -> None:
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 10),
            source_path="statement.pdf",
            detected_format="pdf",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-10 - 2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=ImportedStatementTotals(
            starting_nav=1000.0,
            ending_nav=1200.0,
            cash_total=200.0,
            stock_total=1000.0,
        ),
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=200.0)],
        positions=[ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=10.0, cost_basis=1000.0, close_price=100.0, market_value=1000.0, unrealized_pnl=0.0, currency="USD")],
        ledger_entries=[ImportedLedgerEntry(entry_type="BUY", trade_date=date(2026, 4, 10), symbol="AAPL", quantity=10.0, price=100.0, gross_amount=1000.0, net_amount=-1000.0, currency="USD", source_section="Trades")],
    )

    engine = PortfolioStateEngine(snapshot=snapshot, base_currency="USD", fx_history={})
    states = engine.build_daily_states(
        price_histories={"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 100.0}]},
        valuation_dates=["2026-04-10", "2026-04-11"],
    )

    assert states[-1].cash["USD"] == 200.0
    assert states[-1].total_market_value == 1000.0
    assert states[-1].total_portfolio_value == 1200.0


def test_run_imported_dashboard_history_matches_ib2026_statement_ending_value(mocker) -> None:
    snapshot = import_statement(STATEMENT_2026_PATH)
    _mock_ib2026_dashboard_market_data(mocker, snapshot)
    result = run_imported_dashboard_history(snapshot, "SPY")

    assert snapshot.statement_totals is not None
    ending_nav = round(snapshot.statement_totals.ending_nav or 0, 2)
    assert result.daily_states
    assert round(result.daily_states[-1].total_portfolio_value, 2) == ending_nav
    assert round(result.performance_series[-1].portfolio_value, 2) == ending_nav


def test_ib2026_dashboard_contract_stays_self_consistent_for_real_statement(mocker) -> None:
    snapshot = import_statement(STATEMENT_2026_PATH)
    _mock_ib2026_dashboard_market_data(mocker, snapshot)
    history = run_imported_dashboard_history(snapshot, "SPY")
    overview = build_portfolio_overview(snapshot)
    visible_summary = _compute_dashboard_visible_summary(history.daily_states, history.performance_series)
    monthly_returns = _compute_dashboard_monthly_returns(history.daily_states)
    max_drawdown = _compute_dashboard_max_drawdown(history.performance_series)

    assert snapshot.statement.account_id == "U8516450"
    assert snapshot.statement.statement_period is not None
    assert snapshot.statement.statement_period.startswith("January 1, 2026 - ")
    assert snapshot.statement_totals is not None
    assert visible_summary["end_value"] == round(snapshot.statement_totals.ending_nav or 0, 2)
    assert visible_summary["end_value"] == round(history.daily_states[-1].total_portfolio_value, 2)
    assert visible_summary["end_value"] == round(history.performance_series[-1].portfolio_value, 2)
    assert visible_summary["start_value"] is not None
    assert visible_summary["start_value"] > 0
    assert max_drawdown is not None
    assert max_drawdown <= 0
    assert history.range_metrics is not None
    assert history.range_metrics["3M"].summary.end_value is not None
    assert round(history.range_metrics["3M"].summary.end_value or 0, 2) == visible_summary["end_value"]
    assert monthly_returns
    assert [(item.month, round(item.return_pct, 2)) for item in history.range_metrics["3M"].monthly_returns]
    assert history.range_metrics["3M"].monthly_returns_reliable is True
    assert history.source_status == {"performance_history": "live", "monthly_returns": "live"}

    assert overview.total_market_value > 0
    assert overview.cash_by_currency
    assert overview.sector_allocation
    assert set(overview.sector_position_breakdown).issubset({item["sector"] for item in overview.sector_allocation})


def test_ff2026_dashboard_truth_values_match_imported_history_and_overview(mocker) -> None:
    ff_2026_path = FREEDOM24_FIXTURE_PATH

    snapshot = import_statements([str(ff_2026_path)])

    # Provide deterministic VTI prices that reproduce the FF2026 golden values.
    # Key prices were back-solved from the statement's starting_nav (2900.12),
    # the VTI closing price (335.44 on 2026-04-11), and the expected monthly
    # returns.  The benchmark (SPY) rows just need to be non-empty and without
    # adjClose so benchmark_path = "price_return_only".
    import datetime as _dt

    _FF2026_VTI_KEY_PRICES: dict[str, float] = {
        "2025-12-01": 334.66,
        "2025-12-31": 335.29,
        "2026-01-02": 341.09,
        "2026-01-30": 345.42,
        "2026-02-02": 345.42,
        "2026-02-27": 341.71,
        "2026-03-02": 341.71,
        "2026-03-31": 323.27,
        "2026-04-01": 323.22,
        "2026-04-10": 335.44,
    }
    _FF2026_HOLIDAYS: frozenset[str] = frozenset({
        "2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    })

    def _ff2026_vti_price(date_str: str) -> float:
        if date_str in _FF2026_VTI_KEY_PRICES:
            return _FF2026_VTI_KEY_PRICES[date_str]
        key_dates = sorted(_FF2026_VTI_KEY_PRICES)
        prev_d = prev_p = next_d = next_p = None
        for kd in key_dates:
            if kd <= date_str:
                prev_d, prev_p = kd, _FF2026_VTI_KEY_PRICES[kd]
            else:
                next_d, next_p = kd, _FF2026_VTI_KEY_PRICES[kd]
                break
        if prev_d is None:
            return next_p  # type: ignore[return-value]
        if next_d is None:
            return prev_p  # type: ignore[return-value]
        d0 = _dt.date.fromisoformat(prev_d)
        d1 = _dt.date.fromisoformat(next_d)
        d = _dt.date.fromisoformat(date_str)
        t = (d - d0).days / (d1 - d0).days
        return round(prev_p + t * (next_p - prev_p), 2)  # type: ignore[operator]

    def _ff2026_trading_dates(from_date: str, to_date: str) -> list[str]:
        dates: list[str] = []
        day = _dt.date.fromisoformat(from_date)
        end = _dt.date.fromisoformat(to_date)
        while day <= end:
            if day.weekday() < 5 and day.isoformat() not in _FF2026_HOLIDAYS:
                dates.append(day.isoformat())
            day += _dt.timedelta(days=1)
        return dates

    def _spy_rows(symbol: str, from_date: str, to_date: str) -> list[dict]:
        return [{"date": d, "price": 500.0} for d in _ff2026_trading_dates(from_date, to_date)]

    def _vti_rows_by_symbol(symbols: list[str], from_date: str, to_date: str) -> dict[str, list[dict]]:
        dates = _ff2026_trading_dates(from_date, to_date)
        return {sym: [{"date": d, "price": _ff2026_vti_price(d)} for d in dates] for sym in symbols if sym}

    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    inst = market_data.return_value
    inst.get_direct_verified_benchmark_history.side_effect = _spy_rows
    inst.get_historical_prices_for_symbols.side_effect = _vti_rows_by_symbol
    inst.get_last_fetch_meta.return_value = {
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

    history = run_imported_dashboard_history(snapshot, "SPY")
    overview = build_portfolio_overview(snapshot)
    assert history.range_metrics is not None
    assert history.run_metadata.return_basis_contract.model_dump() == {
        "portfolio_path": "unavailable",
        "benchmark_path": "price_return_only",
    }
    assert history.run_metadata.investor_economics_status.model_dump() == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }

    visible_summary = _compute_dashboard_visible_summary(
        history.daily_states,
        history.performance_series,
        allow_compounded_return_outputs=history.range_metrics["All"].summary.time_weighted_return_pct is not None,
    )
    monthly_returns = _compute_dashboard_monthly_returns(history.daily_states)
    max_drawdown = _compute_dashboard_max_drawdown(
        history.performance_series,
        allow_drawdown_outputs=history.range_metrics["All"].max_drawdown_pct is not None,
    )

    assert snapshot.statement.account_id == FF2026_DASHBOARD_GOLDEN["account_id"]
    assert snapshot.statement.statement_period == FF2026_DASHBOARD_GOLDEN["statement_period"]

    expected_summary = FF2026_DASHBOARD_GOLDEN["summary"]
    assert visible_summary["start_value"] == expected_summary["start_value"]
    assert visible_summary["end_value"] == expected_summary["end_value"]
    assert visible_summary["net_contributions"] == expected_summary["net_contributions"]
    assert visible_summary["time_weighted_return_pct"] == expected_summary["time_weighted_return_pct"]
    assert visible_summary["money_weighted_return_pct"] == expected_summary["money_weighted_return_pct"]
    assert max_drawdown == expected_summary["max_drawdown_pct"]
    assert round(history.range_metrics["3M"].summary.start_value or 0, 2) == expected_summary["start_value"]
    assert round(history.range_metrics["3M"].summary.end_value or 0, 2) == expected_summary["end_value"]
    assert history.range_metrics["3M"].summary.time_weighted_return_pct == expected_summary["time_weighted_return_pct"]
    assert round(history.range_metrics["3M"].summary.money_weighted_return_pct or 0, 2) == expected_summary["money_weighted_return_pct"]
    assert history.range_metrics["3M"].max_drawdown_pct == expected_summary["max_drawdown_pct"]

    assert monthly_returns == FF2026_DASHBOARD_GOLDEN["monthly_returns"]
    assert [(item.month, round(item.return_pct, 2)) for item in history.range_metrics["All"].monthly_returns] == FF2026_DASHBOARD_GOLDEN["monthly_returns"]
    assert history.range_metrics["All"].monthly_returns_reliable is True
    assert history.source_status == {"performance_history": "live", "monthly_returns": "live"}

    expected_overview = FF2026_DASHBOARD_GOLDEN["overview"]
    assert overview.total_market_value == expected_overview["total_market_value"]
    assert overview.cash_by_currency == expected_overview["cash_by_currency"]
    assert any(item["sector"] == expected_overview["broad_market_sector"] and item["market_value"] == expected_overview["vti_market_value"] for item in overview.sector_allocation)
    assert any(item["symbol"] == "VTI" and item["market_value"] == expected_overview["vti_market_value"] and item["weight"] == expected_overview["vti_weight"] for item in overview.sector_position_breakdown["Broad Market"])


def test_performance_series_chain_links_across_deposit_and_withdrawal() -> None:
    states = [
        DailyPortfolioState(
            date="2025-01-02",
            cash={"USD": 1000.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1000.0,
            external_cash_flow=0.0,
        ),
        DailyPortfolioState(
            date="2025-01-03",
            cash={"USD": 1100.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1100.0,
            external_cash_flow=100.0,
        ),
        DailyPortfolioState(
            date="2025-01-04",
            cash={"USD": 1210.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1210.0,
            external_cash_flow=0.0,
        ),
        DailyPortfolioState(
            date="2025-01-05",
            cash={"USD": 1160.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1160.0,
            external_cash_flow=-100.0,
        ),
        DailyPortfolioState(
            date="2025-01-06",
            cash={"USD": 1218.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1218.0,
            external_cash_flow=0.0,
        ),
    ]

    series = build_true_performance_series(
        states,
        [
            {"date": "2025-01-02", "price": 100.0},
            {"date": "2025-01-03", "price": 101.0},
            {"date": "2025-01-04", "price": 103.0},
            {"date": "2025-01-05", "price": 102.0},
            {"date": "2025-01-06", "price": 104.0},
        ],
    )

    assert series[0].portfolio_return_pct == 0.0
    assert series[1].portfolio_return_pct == 0.0
    assert series[2].portfolio_return_pct == 10.0
    assert series[3].portfolio_return_pct == 14.55
    assert series[4].portfolio_return_pct == 20.27


def test_performance_summary_reports_twr_mwr_and_excess_return() -> None:
    states = [
        DailyPortfolioState(
            date="2025-01-02",
            cash={"USD": 1000.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1000.0,
            external_cash_flow=0.0,
        ),
        DailyPortfolioState(
            date="2025-01-03",
            cash={"USD": 1100.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1100.0,
            external_cash_flow=100.0,
        ),
        DailyPortfolioState(
            date="2025-01-04",
            cash={"USD": 1210.0},
            positions=[],
            total_market_value=0.0,
            total_portfolio_value=1210.0,
            external_cash_flow=0.0,
        ),
    ]

    series = build_true_performance_series(
        states,
        [
            {"date": "2025-01-02", "price": 100.0},
            {"date": "2025-01-03", "price": 101.0},
            {"date": "2025-01-04", "price": 103.0},
        ],
    )
    summary = build_performance_summary(states, series)

    assert summary.start_value == 1000.0
    assert summary.end_value == 1210.0
    assert summary.net_contributions == 100.0
    assert summary.investment_gain == 110.0
    assert summary.time_weighted_return_pct == 10.0
    assert summary.money_weighted_return_pct == 10.48
    assert summary.benchmark_return_pct is None
    assert summary.excess_return_pct is None


# ---------------------------------------------------------------------------
# US-9.4 — Rolling factor loadings stability tests
# ---------------------------------------------------------------------------


def test_rolling_factor_loadings_market_beta_in_range() -> None:
    """AC1: Market (SPY) loading stays within [-2, +4] for a long-only equity portfolio.

    Pre-fix, global Gram-Schmidt + ridge_lambda=1e-5 produced Market loadings as
    extreme as -4.60 on the 20d window (25 obs, 17 params → 8 df, near-singular).
    Per-window Gram-Schmidt + ridge floor λ=0.01 must prevent this blowup.
    """
    start = date(2025, 1, 1)
    n = 60  # enough for 20d rolling (min_obs=25 → first valid point at index 24)

    # Deterministic oscillating returns for a long-only equity portfolio
    portfolio_returns = [0.004 if i % 2 == 0 else -0.002 for i in range(n)]
    portfolio_value = 1000.0
    daily_states: list[DailyPortfolioState] = [
        DailyPortfolioState(
            date=start.isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=portfolio_value,
            total_portfolio_value=portfolio_value,
        )
    ]
    for offset, r in enumerate(portfolio_returns, start=1):
        portfolio_value *= 1 + r
        daily_states.append(
            DailyPortfolioState(
                date=(start + timedelta(days=offset)).isoformat(),
                cash={"USD": 0.0},
                positions=[],
                total_market_value=round(portfolio_value, 6),
                total_portfolio_value=round(portfolio_value, 6),
            )
        )

    # Build distinct factor price series: each proxy has a different amplitude and
    # phase so that the per-window Gram-Schmidt has non-degenerate factors to work with.
    factor_histories: dict[str, list[dict]] = {}
    for idx, definition in enumerate(DEFAULT_FACTOR_DEFINITIONS):
        price = 100.0
        rows: list[dict] = [{"date": start.isoformat(), "price": price}]
        for offset in range(1, n + 1):
            r = (0.003 + idx * 0.0005) if (offset + idx) % 2 == 0 else -(0.002 + idx * 0.0003)
            price *= 1 + r
            rows.append({"date": (start + timedelta(days=offset)).isoformat(), "price": round(price, 6)})
        factor_histories[definition.us_proxy] = rows

    factor_model = build_statistical_factor_model(daily_states, factor_histories, "SPY")

    valid_20d = [p for p in factor_model.rolling_loadings_20d if p.market is not None]
    assert len(valid_20d) > 0, "Expected at least one valid 20d rolling point with a Market loading"
    for point in valid_20d:
        assert -2.0 <= point.market <= 4.0, (
            f"Market (SPY) loading {point.market} on {point.date} is outside the plausible range "
            "[-2, +4] for a long-only equity portfolio — numerical instability in rolling OLS."
        )


def test_rolling_factor_loadings_20d_no_blowup() -> None:
    """AC2: No 20d rolling coefficient exceeds ±5 in absolute value.

    With 25 min-observations and 16 factors, the pre-fix OLS condition number was
    dangerously high (n/K ≈ 1.56) and ridge_lambda=1e-5 provided no real
    regularisation. The window-proportional ridge floor (λ=0.01 for the 20d window)
    must cap every coefficient within a plausible range.
    """
    start = date(2025, 1, 1)
    n = 60

    # Portfolio with mild positive drift and occasional down days
    portfolio_value = 1000.0
    daily_states: list[DailyPortfolioState] = [
        DailyPortfolioState(
            date=start.isoformat(),
            cash={"USD": 0.0},
            positions=[],
            total_market_value=portfolio_value,
            total_portfolio_value=portfolio_value,
        )
    ]
    for offset in range(1, n + 1):
        r = 0.003 if offset % 3 != 0 else -0.001
        portfolio_value *= 1 + r
        daily_states.append(
            DailyPortfolioState(
                date=(start + timedelta(days=offset)).isoformat(),
                cash={"USD": 0.0},
                positions=[],
                total_market_value=round(portfolio_value, 6),
                total_portfolio_value=round(portfolio_value, 6),
            )
        )

    # Correlated but distinct factor series (simulate typical equity ETF co-movement)
    factor_histories: dict[str, list[dict]] = {}
    for idx, definition in enumerate(DEFAULT_FACTOR_DEFINITIONS):
        price = 100.0
        rows: list[dict] = [{"date": start.isoformat(), "price": price}]
        for offset in range(1, n + 1):
            r = (0.002 + idx * 0.0004) if (offset * (idx + 1)) % 3 != 0 else -(0.0015 + idx * 0.0002)
            price *= 1 + r
            rows.append({"date": (start + timedelta(days=offset)).isoformat(), "price": round(price, 6)})
        factor_histories[definition.us_proxy] = rows

    factor_model = build_statistical_factor_model(daily_states, factor_histories, "SPY")

    blowup_threshold = 5.0
    factor_fields = [
        "market", "growth", "value", "small_cap", "technology", "financials",
        "health_care", "energy", "industrials", "consumer_staples", "utilities",
        "consumer_discretionary", "rates_ief", "rates_tlt", "credit", "commodities",
    ]
    for point in factor_model.rolling_loadings_20d:
        for field in factor_fields:
            loading = getattr(point, field, None)
            if loading is not None:
                assert abs(loading) <= blowup_threshold, (
                    f"Factor '{field}' loading {loading} exceeds ±{blowup_threshold} on {point.date} "
                    "(20d window) — ridge floor not preventing coefficient blowup."
                )


def test_rolling_factor_loadings_never_emit_nonfinite_values(monkeypatch) -> None:
    """US-21.3: a degenerate window can make the OLS solve return non-finite
    values; NaN passes `is not None` and round(), then breaks JSON serialization
    downstream (the attribution/correlation 500 bug class). Degenerate windows
    must yield None — never NaN."""
    import math as _math

    class MarketOnlyDefinition:
        def __init__(self) -> None:
            self.key = "market"
            self.label = "Market"
            self.us_proxy = "MKT"

    monkeypatch.setattr(risk_module, "DEFAULT_FACTOR_DEFINITIONS", [MarketOnlyDefinition()])
    monkeypatch.setattr(risk_module, "WINDOW_MIN_OBSERVATIONS", {20: 20})

    dates = [f"{index + 1:03d}" for index in range(25)]
    x = [0.01 * ((index % 7) - 3) for index in range(25)]
    y = [0.5 + 1.2 * value for value in x]

    real_fit = risk_module._fit_factor_model
    calls = {"n": 0}

    def nan_first_fit(y_window, orth_window, ridge_lambda=1e-5):
        calls["n"] += 1
        coeffs, residuals, r2 = real_fit(y_window, orth_window, ridge_lambda=ridge_lambda)
        if calls["n"] == 1:  # simulate one degenerate window
            return [float("nan")] * len(coeffs), [float("nan")] * len(residuals), float("nan")
        return coeffs, residuals, r2

    monkeypatch.setattr(risk_module, "_fit_factor_model", nan_first_fit)

    points = risk_module._build_rolling_factor_loadings(dates, y, [("Market", "MKT", x)], window=20)

    for point in points:
        for field in ("market", "r_squared", "residual_vol"):
            value = getattr(point, field, None)
            assert value is None or _math.isfinite(value), f"{point.date}.{field} = {value}"
    # The degenerate window's date produced None (fail-closed), not a number.
    assert points[19].market is None
    # Later (healthy) windows still produce finite loadings.
    assert points[24].market is not None

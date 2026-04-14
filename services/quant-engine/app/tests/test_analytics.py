from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.analytics import risk as risk_module
from app.analytics.portfolio_imports import (
    apply_simulated_trades_to_state,
    build_performance_summary,
    build_portfolio_overview,
    build_rebalance_preview,
    build_reconciliation_summary,
    build_simulated_rebalance_trades,
    build_true_performance_series,
)
from app.analytics.risk import DEFAULT_FACTOR_DEFINITIONS, build_etf_overlap_pairs, build_factor_exposures, build_factor_registry, build_factor_shift_diagnostics, build_lookthrough_exposure, build_lookthrough_sector_exposure, build_market_overlap_summary, build_model_reliability_snapshot, build_portfolio_risk_summary, build_relative_risk_summary, build_risk_contribution_breakdown, build_rolling_risk_series, build_statistical_factor_model, build_stress_scenarios, build_volatility_regime_payload
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
from app.schemas.exposure import ExposureResult
from app.schemas.portfolio_engine import PortfolioCashBalanceSnapshot, PortfolioHistoryContext, PortfolioPositionSnapshot
from app.schemas.reconciliation import DailyPortfolioState, DailyStatePosition, PortfolioRiskSummary
from app.schemas.reconciliation import LookThroughConstituent, LookThroughOverview, LookThroughSource, MarketOverlapSummary, PortfolioOverview
from app.services.dashboard_history_engine import run_dashboard_history_engine, run_imported_dashboard_history
from app.services.diagnostics_engine import run_diagnostics_engine
from app.services.import_engine import build_import_bootstrap_from_snapshot
from app.services.statement_importer import import_statements


STATEMENT_2026_PATH = Path(r"C:\projects\investments\portfolio\docs\2026.pdf")
if not STATEMENT_2026_PATH.exists():
    STATEMENT_2026_PATH = Path(r"C:\projects\investments\portfolio\docs\IB2026.pdf")


IB2026_DASHBOARD_GOLDEN = {
    "account_id": "U8516450",
    "statement_period": "January 1, 2026 - April 13, 2026",
    "summary": {
        "start_value": 52386.10,
        "end_value": 62023.98,
        "net_contributions": 9963.00,
        "time_weighted_return_pct": 4.78,
        "money_weighted_return_pct": -0.62,
        "max_drawdown_pct": -28.40,
    },
    "monthly_returns": [
        ("2026-01", 5.23),
        ("2026-02", -6.91),
        ("2026-03", -3.49),
        ("2026-04", 10.87),
    ],
    "overview": {
        "total_market_value": 50368.17,
        "cash_by_currency": {"EUR": 0.0, "GBP": 0.0, "USD": 8896.43},
        "technology_sector_market_value": 5156.87,
        "sxrv_market_value": 2466.00,
        "sxrv_weight": 0.0490,
        "broad_market_sector": "Broad Market",
    },
}


def _compute_dashboard_visible_summary(daily_states: list[DailyPortfolioState], performance_series: list) -> dict[str, float | None]:
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
    time_weighted_return_pct = anchored_perf[-1].portfolio_return_pct if anchored_perf else None

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


def _compute_dashboard_max_drawdown(performance_series: list) -> float:
    peak = 0.0
    max_drawdown = 0.0
    for point in performance_series:
        peak = max(peak, point.portfolio_value)
        if peak > 0:
            max_drawdown = min(max_drawdown, ((point.portfolio_value - peak) / peak) * 100)
    return round(max_drawdown, 2)


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
    )


def test_build_portfolio_overview_returns_expected_totals() -> None:
    overview = build_portfolio_overview(_sample_snapshot())

    assert overview.total_market_value == 1000.0
    assert overview.total_unrealized_pnl == 200.0
    assert overview.positions_count == 1
    assert overview.cash_by_currency["USD"] == 200.0


def test_build_portfolio_overview_classifies_2026_ucits_and_thematic_holdings() -> None:
    if not STATEMENT_2026_PATH.exists():
        return
    snapshot = import_statement(STATEMENT_2026_PATH)

    overview = build_portfolio_overview(snapshot)

    assert any(item["symbol"] == "HOOD" for item in overview.sector_position_breakdown["Financials"])
    assert any(item["symbol"] == "IUFS" for item in overview.sector_position_breakdown["Financials"])
    assert any(item["symbol"] == "IUHC" for item in overview.sector_position_breakdown["Health Care"])
    assert any(item["symbol"] == "DFND" for item in overview.sector_position_breakdown["Defense"])
    assert any(item["symbol"] == "SXRV" for item in overview.sector_position_breakdown["Technology"])
    assert any(item["symbol"] == "VUAA" for item in overview.sector_position_breakdown["Broad Market"])
    assert any(item["symbol"] == "VDST" for item in overview.sector_position_breakdown["Fixed Income"])


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
    assert metadata["SXRV"].category == "Thematic ETF"


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
    assert result.benchmark is None
    assert result.daily_states == []
    assert result.performance_series == []
    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.start_value is None
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
    assert result.risk_summary.observations > 0
    assert result.statistical_factor_model.windows


def test_variant_snapshot_diagnostics_history_stays_in_plausible_bounds() -> None:
    docs_dir = Path(r"C:\projects\investments\portfolio\docs")
    ib_2026_path = docs_dir / "IB2026.pdf"
    ff_2026_path = docs_dir / "FF2026.pdf"
    espp_2026_path = docs_dir / "ESPP2026.pdf"

    if not (ib_2026_path.exists() and ff_2026_path.exists() and espp_2026_path.exists()):
        return

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


def test_run_imported_dashboard_history_uses_imported_snapshot_ledger_and_returns_live_result(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_historical_prices.return_value = [
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

    service.get_historical_prices.assert_called_once_with("SPY", "2026-04-10", "2026-04-11")
    assert result.source_status == {"performance_history": "live", "monthly_returns": "live"}
    assert result.benchmark is not None
    assert result.benchmark.symbol == "SPY"
    assert len(result.daily_states) == 2
    assert len(result.performance_series) == 2
    assert result.range_metrics is not None
    assert result.range_metrics["All"].summary.end_value == result.daily_states[-1].total_portfolio_value


def test_build_portfolio_risk_summary_and_position_contributions() -> None:
    snapshot = _sample_snapshot()
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
    price_histories = {
        "AAPL": [
            {"date": "2025-01-02", "price": 100.0},
            {"date": "2025-01-03", "price": 101.0},
            {"date": "2025-01-04", "price": 103.02},
        ]
    }

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

    factor_model = build_statistical_factor_model(
        daily_states,
        {definition.us_proxy: benchmark_rows for definition in DEFAULT_FACTOR_DEFINITIONS},
        "SPY",
    )
    stress = build_stress_scenarios(factor_model)

    assert factor_model.benchmark_symbol == "SPY"
    assert factor_model.status in {"ok", "partial"}
    assert len(factor_model.current_factor_snapshot) == 13
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
    assert abs(round(factor_share_sum, 4) - (breakdown.factor_risk_share_total or 0.0)) <= 0.0001
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
    assert reliability.status in {"ok", "partial", "insufficient_history"}
    assert reliability.confidence in {"high", "medium", "low"}


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
    assert ledger[-1].entry_type == "FEE"
    assert ledger[-1].cash_effect == -2.0


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


def test_run_imported_dashboard_history_matches_ib2026_statement_ending_value() -> None:
    if not STATEMENT_2026_PATH.exists():
        return

    snapshot = import_statement(STATEMENT_2026_PATH)
    result = run_imported_dashboard_history(snapshot, "SPY")

    assert snapshot.statement_totals is not None
    assert round(snapshot.statement_totals.ending_nav or 0, 2) == 62023.98
    assert result.daily_states
    assert round(result.daily_states[-1].total_portfolio_value, 2) == 62023.98
    assert round(result.performance_series[-1].portfolio_value, 2) == 62023.98


def test_ib2026_dashboard_golden_values_match_imported_history_and_overview() -> None:
    if not STATEMENT_2026_PATH.exists():
        return

    snapshot = import_statement(STATEMENT_2026_PATH)
    history = run_imported_dashboard_history(snapshot, "SPY")
    overview = build_portfolio_overview(snapshot)
    visible_summary = _compute_dashboard_visible_summary(history.daily_states, history.performance_series)
    monthly_returns = _compute_dashboard_monthly_returns(history.daily_states)
    max_drawdown = _compute_dashboard_max_drawdown(history.performance_series)

    assert snapshot.statement.account_id == IB2026_DASHBOARD_GOLDEN["account_id"]
    assert snapshot.statement.statement_period == IB2026_DASHBOARD_GOLDEN["statement_period"]

    expected_summary = IB2026_DASHBOARD_GOLDEN["summary"]
    assert visible_summary["start_value"] == expected_summary["start_value"]
    assert visible_summary["end_value"] == expected_summary["end_value"]
    assert visible_summary["net_contributions"] == expected_summary["net_contributions"]
    assert visible_summary["time_weighted_return_pct"] == expected_summary["time_weighted_return_pct"]
    assert visible_summary["money_weighted_return_pct"] == expected_summary["money_weighted_return_pct"]
    assert max_drawdown == expected_summary["max_drawdown_pct"]
    assert history.range_metrics is not None
    assert round(history.range_metrics["3M"].summary.start_value or 0, 2) == expected_summary["start_value"]
    assert round(history.range_metrics["3M"].summary.money_weighted_return_pct or 0, 2) == expected_summary["money_weighted_return_pct"]
    assert round(history.range_metrics["3M"].max_drawdown_pct or 0, 2) == expected_summary["max_drawdown_pct"]

    assert monthly_returns == IB2026_DASHBOARD_GOLDEN["monthly_returns"]
    assert [(item.month, round(item.return_pct, 2)) for item in history.range_metrics["3M"].monthly_returns] == IB2026_DASHBOARD_GOLDEN["monthly_returns"]
    assert history.range_metrics["3M"].monthly_returns_reliable is True
    assert history.source_status == {"performance_history": "live", "monthly_returns": "live"}

    expected_overview = IB2026_DASHBOARD_GOLDEN["overview"]
    assert overview.total_market_value == expected_overview["total_market_value"]
    assert overview.cash_by_currency == expected_overview["cash_by_currency"]
    assert any(item["sector"] == "Technology" and item["market_value"] == expected_overview["technology_sector_market_value"] for item in overview.sector_allocation)
    assert any(item["sector"] == expected_overview["broad_market_sector"] for item in overview.sector_allocation)
    assert any(item["symbol"] == "SXRV" and item["market_value"] == expected_overview["sxrv_market_value"] and item["weight"] == expected_overview["sxrv_weight"] for item in overview.sector_position_breakdown["Technology"])
    assert not any(item["symbol"] == "SXRV" for item in overview.sector_position_breakdown.get("Broad Market", []))


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
    assert summary.benchmark_return_pct == 3.0
    assert summary.excess_return_pct == 7.0

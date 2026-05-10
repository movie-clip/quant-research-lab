from __future__ import annotations

from datetime import date, datetime

from app.schemas.imports import ImportedCashBalance, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement
from app.services.exposure_engine import build_exposure_result
from app.services.diagnostics_engine import run_imported_diagnostics_engine
from app.services.statement_importer import import_statements
from app.tests._statement_fixtures import ESPP_PATH, FREEDOM24_PATH, STATEMENT_2026_PATH


class StubMarketDataService:
    def __init__(self) -> None:
        self.holdings_calls: list[str] = []

    def get_etf_holdings(self, symbol: str, symbol_overrides=None):
        self.holdings_calls.append(symbol)
        holdings = {
            "SPY": (
                "SPY",
                [
                    {"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 7.0},
                    {"asset": "MSFT", "name": "MICROSOFT CORP", "weightPercentage": 6.0},
                    {"asset": "GOOG", "name": "ALPHABET INC", "weightPercentage": 4.0},
                    {"asset": "AMZN", "name": "AMAZON COM INC", "weightPercentage": 3.0},
                ],
            ),
            "VUAA": (
                "SPY",
                [
                    {"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 7.0},
                    {"asset": "MSFT", "name": "MICROSOFT CORP", "weightPercentage": 6.0},
                    {"asset": "GOOG", "name": "ALPHABET INC", "weightPercentage": 4.0},
                ],
            ),
            "VDST": (
                "BIL",
                [
                    {"asset": "BIL", "name": "SPDR BLOOMBERG 1-3 MONTH T-BILL ETF", "weightPercentage": 100.0},
                ],
            ),
            "DFND": (
                "DFND",
                [
                    {"asset": "LMT", "name": "LOCKHEED MARTIN", "weightPercentage": 8.0},
                    {"asset": "NOC", "name": "NORTHROP GRUMMAN", "weightPercentage": 6.0},
                ],
            ),
            "IUFS": (
                "XLF",
                [
                    {"asset": "JPM", "name": "JPMORGAN CHASE", "weightPercentage": 9.0},
                    {"asset": "BRK.B", "name": "BERKSHIRE HATHAWAY", "weightPercentage": 8.0},
                ],
            ),
            "IUHC": (
                "XLV",
                [
                    {"asset": "UNH", "name": "UNITEDHEALTH", "weightPercentage": 8.0},
                    {"asset": "LLY", "name": "ELI LILLY", "weightPercentage": 7.0},
                ],
            ),
            "ICOM": (
                "DBC",
                [
                    {"asset": "GLD", "name": "GOLD", "weightPercentage": 20.0},
                    {"asset": "USO", "name": "OIL", "weightPercentage": 15.0},
                ],
            ),
            "SGLD": (
                "GLD",
                [
                    {"asset": "GLD", "name": "GOLD", "weightPercentage": 100.0},
                ],
            ),
            "ISLN": (
                "SLV",
                [
                    {"asset": "SLV", "name": "SILVER", "weightPercentage": 100.0},
                ],
            ),
        }
        return holdings.get(symbol, (None, []))


class UnresolvedEtfMarketDataService(StubMarketDataService):
    def get_etf_holdings(self, symbol: str, symbol_overrides=None):
        self.holdings_calls.append(symbol)
        if symbol in {"SPY", "VUAA"}:
            return (None, [])
        return super().get_etf_holdings(symbol, symbol_overrides)


def _build_snapshot(positions: list[ImportedPosition], cash_balances: list[ImportedCashBalance] | None = None) -> ImportedPortfolioSnapshot:
    return ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2026, 4, 11),
            source_path="snapshot.json",
            detected_format="snapshot",
            account_id="U123",
            base_currency="USD",
            statement_period="2026-04-11",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=cash_balances or [ImportedCashBalance(currency="USD", ending_cash=0.0)],
        positions=positions,
        ledger_entries=[],
    )

    def get_company_profile(self, symbol: str, symbol_overrides=None):
        return None


def test_exposure_engine_builds_expected_shape_for_ib2026(mocker) -> None:
    snapshot = import_statements([str(STATEMENT_2026_PATH)])
    stub = StubMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.snapshot.statement.account_id == "U8516450"
    assert result.overview.positions_count == len(snapshot.positions)
    assert result.lookthrough.portfolio_market_value > 0
    assert result.lookthrough.covered_market_value > 0
    assert 0 <= result.lookthrough.coverage_ratio <= 1
    assert result.market_overlap.benchmark_symbol == "SPY"
    assert result.market_overlap.overlap_weight is not None
    assert result.market_overlap.active_share is not None
    assert 0 <= result.market_overlap.overlap_weight <= 1
    assert 0 <= result.market_overlap.active_share <= 1
    assert result.current_state_concentration.top_positions
    assert result.current_state_concentration.top_1_position_weight is not None
    assert result.current_state_concentration.position_hhi is not None
    assert result.current_state_concentration.effective_holdings is not None
    assert result.provenance.price_basis == "not_applicable"
    assert result.run_metadata.engine_id == "exposure_engine_v1"
    assert result.availability.lookthrough_status in {"live", "partial"}
    assert result.availability.lookthrough_confidence in {"high", "medium"}
    assert result.availability.benchmark_overlap_status in {"live", "partial"}
    assert result.availability.benchmark_overlap_confidence in {"high", "medium"}
    assert result.run_metadata.source_status.benchmark_holdings in {"verified", "degraded"}
    assert isinstance(result.market_overlap.top_overweights, list)
    assert isinstance(result.market_overlap.top_underweights, list)
    assert len(result.lookthrough.top_constituents) > 0
    assert len(result.lookthrough_sector_exposure) > 0
    assert "SPY" in stub.holdings_calls


def test_exposure_engine_builds_expected_shape_for_freedom24_2026(mocker) -> None:
    snapshot = import_statements([str(FREEDOM24_PATH)])
    stub = StubMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.snapshot.statement.importer == "freedom24"
    assert result.overview.positions_count == len(snapshot.positions)
    assert result.lookthrough.portfolio_market_value >= result.lookthrough.covered_market_value
    assert 0 <= result.lookthrough.coverage_ratio <= 1
    assert result.market_overlap.benchmark_symbol == "SPY"
    assert result.availability.lookthrough_status in {"live", "partial"}
    assert result.availability.lookthrough_confidence in {"high", "medium"}
    assert result.current_state_concentration.top_positions
    assert result.current_state_concentration.top_sectors
    assert result.lookthrough.top_constituents is not None


def test_exposure_engine_builds_expected_shape_for_espp2026(mocker) -> None:
    snapshot = import_statements([str(ESPP_PATH)])
    stub = StubMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.snapshot.statement.account_id is not None
    assert result.overview.positions_count == len(snapshot.positions)
    assert result.lookthrough.portfolio_market_value > 0
    assert result.market_overlap.benchmark_symbol == "SPY"
    assert len(result.lookthrough.top_constituents) >= 1
    assert result.current_state_concentration.top_positions


def test_exposure_engine_marks_zero_market_value_snapshot_as_unavailable(mocker) -> None:
    snapshot = _build_snapshot(
        positions=[
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="AAPL",
                quantity=0.0,
                cost_basis=0.0,
                close_price=0.0,
                market_value=0.0,
                unrealized_pnl=0.0,
                currency="USD",
            )
        ]
    )
    stub = StubMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.lookthrough.portfolio_market_value == 0.0
    assert result.lookthrough.covered_market_value == 0.0
    assert result.lookthrough.coverage_ratio == 0.0
    assert len(result.lookthrough.top_constituents) == 1
    assert result.lookthrough.top_constituents[0].effective_market_value == 0.0
    assert result.current_state_concentration.top_1_position_weight is None
    assert result.current_state_concentration.position_hhi is None
    assert result.current_state_concentration.effective_holdings is None
    assert result.availability.lookthrough_status == "unavailable"
    assert result.availability.lookthrough_confidence == "low"
    assert result.availability.benchmark_overlap_status == "unavailable"
    assert result.availability.benchmark_overlap_confidence == "low"


def test_exposure_engine_marks_all_unresolved_etf_snapshot_as_partial_and_zero_coverage(mocker) -> None:
    snapshot = _build_snapshot(
        positions=[
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="VUAA",
                quantity=10.0,
                cost_basis=1000.0,
                close_price=100.0,
                market_value=1000.0,
                unrealized_pnl=0.0,
                currency="USD",
            )
        ]
    )
    stub = UnresolvedEtfMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.lookthrough.portfolio_market_value == 1000.0
    assert result.lookthrough.covered_market_value == 0.0
    assert result.lookthrough.coverage_ratio == 0.0
    assert result.lookthrough.uncovered_positions == ["VUAA"]
    assert result.lookthrough.top_constituents[0].symbol == "VUAA"
    assert result.lookthrough_sector_exposure[0].sector == "Broad Market"
    assert result.current_state_concentration.top_1_position_weight == 1.0
    assert result.current_state_concentration.top_sector_weight == 1.0
    assert result.current_state_concentration.position_hhi == 1.0
    assert result.current_state_concentration.effective_holdings == 1.0
    assert result.availability.lookthrough_status == "partial"
    assert result.availability.lookthrough_confidence == "medium"
    assert result.availability.benchmark_overlap_status == "unavailable"
    assert result.availability.benchmark_overlap_confidence == "low"
    assert result.run_metadata.source_status.benchmark_holdings == "unavailable"
    assert result.market_overlap.top_overweights == []
    assert result.market_overlap.top_underweights == []


def test_exposure_engine_marks_cash_only_snapshot_as_unavailable(mocker) -> None:
    snapshot = _build_snapshot(
        positions=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=2500.0)],
    )
    stub = StubMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.overview.total_market_value == 0.0
    assert result.lookthrough.portfolio_market_value == 0.0
    assert result.lookthrough.covered_market_value == 0.0
    assert result.lookthrough.coverage_ratio == 0.0
    assert result.lookthrough.top_constituents == []
    assert result.lookthrough_sector_exposure == []
    assert result.current_state_concentration.top_positions == []
    assert result.current_state_concentration.top_sectors == []
    assert result.current_state_concentration.top_1_position_weight is None
    assert result.current_state_concentration.position_hhi is None
    assert result.current_state_concentration.effective_holdings is None
    assert result.market_overlap.overlap_weight is None
    assert result.market_overlap.active_share is None
    assert result.availability.lookthrough_status == "unavailable"
    assert result.availability.lookthrough_confidence == "low"
    assert result.availability.benchmark_overlap_status == "unavailable"
    assert result.availability.benchmark_overlap_confidence == "low"
    assert result.market_overlap.top_overweights == []
    assert result.market_overlap.top_underweights == []


def test_exposure_engine_partial_lookthrough_keeps_holdings_based_concentration_truth(mocker) -> None:
    snapshot = _build_snapshot(
        positions=[
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="AAPL",
                quantity=1.0,
                cost_basis=100.0,
                close_price=100.0,
                market_value=100.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="VUAA",
                quantity=9.0,
                cost_basis=900.0,
                close_price=100.0,
                market_value=900.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
        ]
    )
    stub = UnresolvedEtfMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.availability.lookthrough_status == "partial"
    assert result.lookthrough.covered_market_value == 100.0
    assert result.current_state_concentration.top_positions[0].name == "VUAA"
    assert result.current_state_concentration.top_positions[0].weight == 0.9
    assert result.current_state_concentration.top_sectors[0].name == "Broad Market"
    assert result.current_state_concentration.top_sector_weight == 0.9


def test_exposure_engine_handles_mixed_resolved_unresolved_and_cash_snapshot(mocker) -> None:
    snapshot = _build_snapshot(
        positions=[
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="AAPL",
                quantity=1.0,
                cost_basis=100.0,
                close_price=100.0,
                market_value=100.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="VUAA",
                quantity=9.0,
                cost_basis=900.0,
                close_price=100.0,
                market_value=900.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
        ],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=500.0)],
    )
    stub = UnresolvedEtfMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.overview.total_market_value == 1000.0
    assert result.lookthrough.portfolio_market_value == 1000.0
    assert result.lookthrough.covered_market_value == 100.0
    assert result.lookthrough.coverage_ratio == 0.1
    assert result.lookthrough.uncovered_positions == ["VUAA"]
    assert [item.symbol for item in result.lookthrough.top_constituents[:2]] == ["VUAA", "AAPL"]
    assert result.current_state_concentration.top_1_position_weight == 0.9
    assert result.current_state_concentration.top_3_position_weight == 1.0
    assert result.current_state_concentration.position_hhi == 0.82
    assert result.current_state_concentration.effective_holdings == 1.22
    assert result.availability.lookthrough_status == "partial"
    assert result.availability.lookthrough_confidence == "medium"
    assert result.availability.benchmark_overlap_status == "unavailable"
    assert result.availability.benchmark_overlap_confidence == "low"
    assert result.market_overlap.overlap_weight is None
    assert result.market_overlap.active_share is None
    assert result.market_overlap.top_overweights == []
    assert result.market_overlap.top_underweights == []


def test_exposure_engine_builds_deterministic_benchmark_positioning_cues(mocker) -> None:
    snapshot = _build_snapshot(
        positions=[
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="AAPL",
                quantity=7.0,
                cost_basis=700.0,
                close_price=100.0,
                market_value=700.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="MSFT",
                quantity=10.0,
                cost_basis=1000.0,
                close_price=100.0,
                market_value=1000.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="GOOG",
                quantity=2.0,
                cost_basis=200.0,
                close_price=100.0,
                market_value=200.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="AMZN",
                quantity=1.0,
                cost_basis=100.0,
                close_price=100.0,
                market_value=100.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
        ]
    )
    stub = StubMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.market_overlap.portfolio_in_benchmark_weight == 1.0
    assert result.market_overlap.active_share == 0.4
    assert [item.symbol for item in result.market_overlap.top_overweights] == ["MSFT", "AAPL", "GOOG", "AMZN"]
    assert [item.symbol for item in result.market_overlap.top_underweights] == []
    assert result.market_overlap.top_overweights[0].active_weight == 0.44
    assert result.market_overlap.top_overweights[1].active_weight == 0.28


def test_exposure_engine_benchmark_positioning_uses_shared_symbols_only_and_caps_each_side(mocker) -> None:
    class SharedSymbolsBenchmarkMarketDataService(StubMarketDataService):
        def get_etf_holdings(self, symbol: str, symbol_overrides=None):
            self.holdings_calls.append(symbol)
            if symbol == "SPY":
                return (
                    "SPY",
                    [
                        {"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 15.0},
                        {"asset": "MSFT", "name": "MICROSOFT CORP", "weightPercentage": 12.0},
                        {"asset": "GOOG", "name": "ALPHABET INC", "weightPercentage": 10.0},
                        {"asset": "AMZN", "name": "AMAZON COM INC", "weightPercentage": 7.0},
                        {"asset": "META", "name": "META PLATFORMS", "weightPercentage": 6.0},
                        {"asset": "NVDA", "name": "NVIDIA CORP", "weightPercentage": 5.0},
                        {"asset": "TSLA", "name": "TESLA INC", "weightPercentage": 4.0},
                        {"asset": "BRK.B", "name": "BERKSHIRE HATHAWAY", "weightPercentage": 3.0},
                        {"asset": "JPM", "name": "JPMORGAN CHASE", "weightPercentage": 2.0},
                        {"asset": "XOM", "name": "EXXON MOBIL", "weightPercentage": 1.0},
                        {"asset": "UNH", "name": "UNITEDHEALTH", "weightPercentage": 1.0},
                        {"asset": "PG", "name": "PROCTER & GAMBLE", "weightPercentage": 1.0},
                        {"asset": "HD", "name": "HOME DEPOT", "weightPercentage": 1.0},
                        {"asset": "V", "name": "VISA", "weightPercentage": 1.0},
                        {"asset": "MA", "name": "MASTERCARD", "weightPercentage": 1.0},
                        {"asset": "COST", "name": "COSTCO", "weightPercentage": 1.0},
                        {"asset": "ABBV", "name": "ABBVIE", "weightPercentage": 1.0},
                        {"asset": "KO", "name": "COCA-COLA", "weightPercentage": 1.0},
                        {"asset": "PEP", "name": "PEPSICO", "weightPercentage": 1.0},
                        {"asset": "AVGO", "name": "BROADCOM", "weightPercentage": 1.0},
                        {"asset": "ORCL", "name": "ORACLE", "weightPercentage": 1.0},
                        {"asset": "NFLX", "name": "NETFLIX", "weightPercentage": 1.0},
                        {"asset": "CRM", "name": "SALESFORCE", "weightPercentage": 1.0},
                        {"asset": "ADBE", "name": "ADOBE", "weightPercentage": 1.0},
                        {"asset": "TMO", "name": "THERMO FISHER", "weightPercentage": 14.0},
                    ],
                )
            return super().get_etf_holdings(symbol, symbol_overrides)

    snapshot = _build_snapshot(
        positions=[
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AAPL", quantity=14.0, cost_basis=1400.0, close_price=100.0, market_value=1400.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="MSFT", quantity=14.0, cost_basis=1400.0, close_price=100.0, market_value=1400.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="GOOG", quantity=14.0, cost_basis=1400.0, close_price=100.0, market_value=1400.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="AMZN", quantity=13.0, cost_basis=1300.0, close_price=100.0, market_value=1300.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="META", quantity=12.0, cost_basis=1200.0, close_price=100.0, market_value=1200.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="NVDA", quantity=11.0, cost_basis=1100.0, close_price=100.0, market_value=1100.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="TSLA", quantity=1.0, cost_basis=100.0, close_price=100.0, market_value=100.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="BRK.B", quantity=1.0, cost_basis=100.0, close_price=100.0, market_value=100.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="JPM", quantity=1.0, cost_basis=100.0, close_price=100.0, market_value=100.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=date(2026, 4, 11), symbol="SHOP", quantity=1.0, cost_basis=100.0, close_price=100.0, market_value=100.0, unrealized_pnl=0.0, currency="USD"),
        ]
    )
    stub = SharedSymbolsBenchmarkMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert [item.symbol for item in result.market_overlap.top_overweights] == ["AMZN", "META", "NVDA", "GOOG", "MSFT"]
    assert [item.symbol for item in result.market_overlap.top_underweights] == ["TSLA", "BRK.B", "JPM"]
    assert len(result.market_overlap.top_overweights) == 5
    assert len(result.market_overlap.top_underweights) <= 5
    assert all(item.symbol != "SHOP" for item in result.market_overlap.top_overweights)
    assert all(item.symbol != "SHOP" for item in result.market_overlap.top_underweights)


def test_exposure_engine_marks_incomplete_benchmark_holdings_as_degraded(mocker) -> None:
    class PartialBenchmarkHoldingsMarketDataService(StubMarketDataService):
        def get_etf_holdings(self, symbol: str, symbol_overrides=None):
            self.holdings_calls.append(symbol)
            if symbol == "SPY":
                return (
                    "SPY",
                    [
                        {"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 7.0},
                        {"asset": "MSFT", "name": "MICROSOFT CORP", "weightPercentage": 6.0},
                    ],
                )
            return super().get_etf_holdings(symbol, symbol_overrides)

    snapshot = _build_snapshot(
        positions=[
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="AAPL",
                quantity=1.0,
                cost_basis=100.0,
                close_price=100.0,
                market_value=100.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
            ImportedPosition(
                as_of_date=date(2026, 4, 11),
                symbol="MSFT",
                quantity=1.0,
                cost_basis=100.0,
                close_price=100.0,
                market_value=100.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
        ]
    )
    stub = PartialBenchmarkHoldingsMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.availability.benchmark_overlap_status == "live"
    assert result.availability.benchmark_overlap_confidence == "medium"
    assert result.run_metadata.source_status.benchmark_holdings == "degraded"
    assert [item.symbol for item in result.market_overlap.top_overweights] == ["MSFT", "AAPL"]


def test_exposure_engine_is_deterministic_for_repeated_ib2026_requests(mocker) -> None:
    snapshot = import_statements([str(STATEMENT_2026_PATH)])

    def run_once():
        stub = StubMarketDataService()
        mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)
        return build_exposure_result(snapshot, "SPY").model_dump()

    first = run_once()
    second = run_once()

    assert first == second


def test_exposure_engine_handles_many_varied_requests_with_deterministic_stubbed_market_data(mocker) -> None:
    snapshots = [
        import_statements([str(STATEMENT_2026_PATH)]),
        import_statements([str(FREEDOM24_PATH)]),
        import_statements([str(ESPP_PATH)]),
    ]

    results = []
    for _ in range(5):
        for snapshot in snapshots:
            stub = StubMarketDataService()
            mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)
            result = build_exposure_result(snapshot, "SPY")
            results.append(
                {
                    "importer": result.snapshot.statement.importer,
                    "positions_count": result.overview.positions_count,
                    "coverage_ratio": result.lookthrough.coverage_ratio,
                    "top_constituents_count": len(result.lookthrough.top_constituents),
                    "sector_count": len(result.lookthrough_sector_exposure),
                    "overlap_weight": result.market_overlap.overlap_weight,
                }
            )

    assert len(results) == 15
    assert all(item["positions_count"] >= 1 for item in results)
    assert all(0 <= item["coverage_ratio"] <= 1 for item in results)
    assert all(0 <= item["overlap_weight"] <= 1 for item in results)


def test_full_portfolio_imported_diagnostics_produces_deterministic_growth_factor_outputs() -> None:
    snapshot = import_statements([str(ESPP_PATH), str(FREEDOM24_PATH), str(STATEMENT_2026_PATH)])

    first = run_imported_diagnostics_engine(snapshot, "SPY")
    second = run_imported_diagnostics_engine(snapshot, "SPY")

    first_growth = next((item for item in first.statistical_factor_model.current_factor_snapshot if item.key == "growth"), None)
    second_growth = next((item for item in second.statistical_factor_model.current_factor_snapshot if item.key == "growth"), None)
    first_window_20 = next((item for item in first.statistical_factor_model.windows if item.window_days == 20), None)
    second_window_20 = next((item for item in second.statistical_factor_model.windows if item.window_days == 20), None)

    assert first.availability.historical_sections_available is True
    assert first.risk_summary.observations > 100
    assert first_window_20 is not None
    assert first_growth is not None
    assert second_growth is not None
    assert second_window_20 is not None
    assert first_growth.us_proxy == "QQQ"
    assert second_growth.us_proxy == "QQQ"
    assert first_growth.latest_loading is not None
    assert first_growth.latest_loading == second_growth.latest_loading
    assert first_window_20.status == "degraded_unverified_return_basis"
    assert second_window_20.status == "degraded_unverified_return_basis"
    assert first_window_20.model_dump() == second_window_20.model_dump()

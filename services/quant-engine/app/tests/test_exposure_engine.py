from __future__ import annotations

from pathlib import Path

import pytest

from app.services.exposure_engine import build_exposure_result
from app.services.diagnostics_engine import run_imported_diagnostics_engine
from app.services.statement_importer import import_statements


DOCS_DIR = Path(r"C:\projects\investments\portfolio\docs")
IB_2026_PATH = DOCS_DIR / "IB2026.pdf"
FF_2026_PATH = DOCS_DIR / "FF2026.pdf"
ESPP_2026_PATH = DOCS_DIR / "ESPP2026.pdf"


def _require_paths(*paths: Path) -> None:
    for path in paths:
        if not path.exists():
            pytest.skip(f"Missing local test fixture: {path}")


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

    def get_company_profile(self, symbol: str, symbol_overrides=None):
        return None


def test_exposure_engine_builds_expected_shape_for_ib2026(mocker) -> None:
    _require_paths(IB_2026_PATH)
    snapshot = import_statements([str(IB_2026_PATH)])
    stub = StubMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.snapshot.statement.account_id == "U8516450"
    assert result.overview.positions_count == len(snapshot.positions)
    assert result.lookthrough.portfolio_market_value > 0
    assert result.lookthrough.covered_market_value > 0
    assert 0 <= result.lookthrough.coverage_ratio <= 1
    assert result.market_overlap.benchmark_symbol == "SPY"
    assert 0 <= result.market_overlap.overlap_weight <= 1
    assert 0 <= result.market_overlap.active_share <= 1
    assert len(result.lookthrough.top_constituents) > 0
    assert len(result.lookthrough_sector_exposure) > 0
    assert "SPY" in stub.holdings_calls


def test_exposure_engine_builds_expected_shape_for_freedom24_2026(mocker) -> None:
    _require_paths(FF_2026_PATH)
    snapshot = import_statements([str(FF_2026_PATH)])
    stub = StubMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.snapshot.statement.importer == "freedom24"
    assert result.overview.positions_count == len(snapshot.positions)
    assert result.lookthrough.portfolio_market_value >= result.lookthrough.covered_market_value
    assert result.market_overlap.benchmark_symbol == "SPY"
    assert result.lookthrough.top_constituents is not None


def test_exposure_engine_builds_expected_shape_for_espp2026(mocker) -> None:
    _require_paths(ESPP_2026_PATH)
    snapshot = import_statements([str(ESPP_2026_PATH)])
    stub = StubMarketDataService()
    mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)

    result = build_exposure_result(snapshot, "SPY")

    assert result.snapshot.statement.account_id is not None
    assert result.overview.positions_count == len(snapshot.positions)
    assert result.lookthrough.portfolio_market_value > 0
    assert result.market_overlap.benchmark_symbol == "SPY"
    assert len(result.lookthrough.top_constituents) >= 1


def test_exposure_engine_is_deterministic_for_repeated_ib2026_requests(mocker) -> None:
    _require_paths(IB_2026_PATH)
    snapshot = import_statements([str(IB_2026_PATH)])

    def run_once():
        stub = StubMarketDataService()
        mocker.patch("app.services.exposure_engine.MarketDataService", return_value=stub)
        return build_exposure_result(snapshot, "SPY").model_dump()

    first = run_once()
    second = run_once()

    assert first == second


def test_exposure_engine_handles_many_varied_requests_with_deterministic_stubbed_market_data(mocker) -> None:
    _require_paths(IB_2026_PATH, FF_2026_PATH, ESPP_2026_PATH)
    snapshots = [
        import_statements([str(IB_2026_PATH)]),
        import_statements([str(FF_2026_PATH)]),
        import_statements([str(ESPP_2026_PATH)]),
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
    _require_paths(IB_2026_PATH, FF_2026_PATH, ESPP_2026_PATH)
    snapshot = import_statements([str(ESPP_2026_PATH), str(FF_2026_PATH), str(IB_2026_PATH)])

    first = run_imported_diagnostics_engine(snapshot, "SPY")
    second = run_imported_diagnostics_engine(snapshot, "SPY")

    first_growth = next((item for item in first.statistical_factor_model.current_factor_snapshot if item.key == "growth"), None)
    second_growth = next((item for item in second.statistical_factor_model.current_factor_snapshot if item.key == "growth"), None)
    first_window_20 = next((item for item in first.statistical_factor_model.windows if item.window_days == 20), None)
    second_window_20 = next((item for item in second.statistical_factor_model.windows if item.window_days == 20), None)

    assert first.availability.historical_sections_available is True
    assert first.risk_summary.observations > 100
    assert first_window_20 is not None
    assert first_window_20.status == "ok"
    assert first_growth is not None
    assert second_growth is not None
    assert second_window_20 is not None
    assert first_growth.us_proxy == "QQQ"
    assert first_growth.latest_loading is not None
    assert first_growth.latest_loading == second_growth.latest_loading
    assert first_window_20.model_dump() == second_window_20.model_dump()

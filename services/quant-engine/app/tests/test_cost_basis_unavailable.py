"""A position with no stated cost basis is unavailable, never invented (US-46.4, finding F4).

Broker truth: `ImportedPosition.cost_basis` / `unrealized_pnl` are statement-stated
values. When the statement states none they are None - never derived from market
value, close price, quantity x price or partial trade history, never zero-filled.
Aggregates are None when ANY contributing position is None (never a partial sum),
and `PortfolioOverview.cost_basis_trust` is "unavailable" exactly then (not
"withheld", not "degraded").

Expected values: IB2026 totals are statement truths (statement_truths.py); the
FF2026 nulls and the null-propagation table are the research brief (02-quant.md
§ F4) and the methodology's merge precedent, not engine output.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.schemas.reconciliation as reconciliation_schemas
from app.analytics import performance
from app.analytics.overview import build_portfolio_overview
from app.api.main import app
from app.domain.ledger import reconstruct_position_lots
from app.schemas.imports import ImportedPortfolioSnapshot, ImportedPosition, SnapshotAnalysisRequest
from app.schemas.reconciliation import PortfolioOverview
from app.scripts.frozen_market_data import FrozenMarketData
from app.services.dashboard_history_engine import run_imported_dashboard_history
from app.services.import_engine import build_import_bootstrap
from app.services.portfolio_snapshot_builder import build_imported_snapshot_from_request
from app.services.statement_importer import combine_imported_snapshots, import_statements
from app.tests._statement_fixtures import ESPP_PATH, FREEDOM24_PATH, STATEMENT_2026_CSV_PATH as IB_PATH
from app.tests.fixtures import account_snapshot, imported_snapshot, position
from app.tests.statement_truths import IB_TOTAL_COST_BASIS_2DP, IB_TOTAL_UNREALIZED_PNL_2DP

APP_DIR = Path(__file__).resolve().parents[1]

FF_VTI_MARKET_VALUE = 3018.96  # the statement's own Ending-balance value for 9 VTI


@pytest.fixture(scope="module")
def ib() -> ImportedPortfolioSnapshot:
    return import_statements([str(IB_PATH)])


@pytest.fixture(scope="module")
def espp() -> ImportedPortfolioSnapshot:
    return import_statements([str(ESPP_PATH)])


@pytest.fixture(scope="module")
def ff() -> ImportedPortfolioSnapshot:
    return import_statements([str(FREEDOM24_PATH)])


def _vti(snapshot: ImportedPortfolioSnapshot) -> ImportedPosition:
    return next(p for p in snapshot.positions if p.symbol == "VTI")


def _ib_like_request(ib: ImportedPortfolioSnapshot) -> SnapshotAnalysisRequest:
    """The snapshot-workspace shape the request path (Exposure of an added node,
    stress, drawdown, ...) receives: symbols and market values, no cost basis."""
    return SnapshotAnalysisRequest.model_validate(
        {
            "base_currency": "USD",
            "statement_period": ib.statement.statement_period,
            "imported_at": "2026-08-29T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["IB2026.csv"],
            "positions": [
                {"symbol": p.symbol, "market_value": p.market_value, "quantity": p.quantity, "currency": p.currency}
                for p in ib.positions
            ],
            "cash_balances": [{"currency": b.currency, "amount": b.ending_cash or 0.0} for b in ib.cash_balances],
        }
    )


# ── AC 1-2: Freedom24 states neither value ──────────────────────────────────


def test_freedom24_vti_has_no_cost_basis_and_no_unrealized_pnl(ff) -> None:
    vti = _vti(ff)

    assert vti.cost_basis is None
    assert vti.unrealized_pnl is None
    # the fields the statement DOES state are untouched
    assert (vti.quantity, round(vti.market_value, 2)) == (9, FF_VTI_MARKET_VALUE)
    # ... and absence survives serialisation as null, not 0
    dumped = vti.model_dump(mode="json")
    assert dumped["cost_basis"] is None and dumped["unrealized_pnl"] is None


def test_position_schema_accepts_absent_cost_basis_and_pnl_and_defaults_them_to_none() -> None:
    absent = ImportedPosition.model_validate(
        {"as_of_date": "2026-04-11", "symbol": "VTI", "quantity": 9, "close_price": 335.44, "market_value": 3018.96, "currency": "USD"}
    )

    assert absent.cost_basis is None and absent.unrealized_pnl is None


def test_ib_and_espp_still_state_cost_basis_for_every_position(ib, espp) -> None:
    """AC 6 (positions): the nulling is per statement - stated broker values are not dropped."""
    for snapshot in (ib, espp):
        assert all(p.cost_basis is not None and p.unrealized_pnl is not None for p in snapshot.positions)


# ── AC 2-6: overview totals, trust, top positions ───────────────────────────


def test_ff_overview_totals_are_unavailable_with_trust_unavailable(ff) -> None:
    overview = build_portfolio_overview(ff)

    assert overview.total_cost_basis is None
    assert overview.total_unrealized_pnl is None
    assert overview.cost_basis_trust == "unavailable"
    # unavailable is its own rung - not the withheld/degraded neighbours (trust ladder)
    assert overview.cost_basis_trust not in {"withheld", "degraded", "stated"}
    assert round(overview.total_market_value, 2) == FF_VTI_MARKET_VALUE


def test_ff_top_positions_report_vti_pnl_as_unavailable_not_zero(ff) -> None:
    top = build_portfolio_overview(ff).top_positions

    vti = next(item for item in top if item["symbol"] == "VTI")
    assert "unrealized_pnl" in vti and vti["unrealized_pnl"] is None
    assert vti["unrealized_pnl"] != 0.0


def test_ib_overview_totals_are_the_statement_stated_values(ib) -> None:
    overview = build_portfolio_overview(ib)

    assert overview.total_cost_basis == IB_TOTAL_COST_BASIS_2DP
    assert overview.total_unrealized_pnl == IB_TOTAL_UNREALIZED_PNL_2DP
    assert overview.cost_basis_trust == "stated"
    assert all(item["unrealized_pnl"] is not None for item in overview.top_positions)


def test_ib_plus_freedom24_totals_are_unavailable_not_a_silent_ib_only_sum(ib, ff) -> None:
    """AC 5: previously 65,274.10 / 3,491.53 - the P&L silently IB-only."""
    overview = build_portfolio_overview(combine_imported_snapshots([ib, ff]))

    assert overview.total_cost_basis is None
    assert overview.total_unrealized_pnl is None
    assert overview.cost_basis_trust == "unavailable"
    assert overview.total_unrealized_pnl != IB_TOTAL_UNREALIZED_PNL_2DP


def test_ib_plus_espp_totals_stay_stated_and_are_the_sum_of_the_stated_parts(ib, espp) -> None:
    """Null-propagation only fires on a null: two statements that both state stay stated."""
    ib_overview, espp_overview = build_portfolio_overview(ib), build_portfolio_overview(espp)

    combined = build_portfolio_overview(combine_imported_snapshots([ib, espp]))

    assert combined.cost_basis_trust == "stated"
    assert combined.total_cost_basis == round(ib_overview.total_cost_basis + espp_overview.total_cost_basis, 2)
    assert combined.total_unrealized_pnl == round(ib_overview.total_unrealized_pnl + espp_overview.total_unrealized_pnl, 2)


def test_one_null_position_makes_the_total_none_not_a_partial_sum() -> None:
    stated = position("AAA", 1000.0, cost_basis=800.0, unrealized_pnl=200.0)
    missing_basis = position("BBB", 500.0, cost_basis=None, unrealized_pnl=None)
    snapshot = ImportedPortfolioSnapshot.model_validate(imported_snapshot(positions=[stated, missing_basis]))

    overview = build_portfolio_overview(snapshot)

    assert overview.total_cost_basis is None and overview.total_unrealized_pnl is None
    assert overview.cost_basis_trust == "unavailable"
    by_symbol = {item["symbol"]: item["unrealized_pnl"] for item in overview.top_positions}
    assert by_symbol == {"AAA": 200.0, "BBB": None}


def test_cost_basis_and_pnl_can_be_unavailable_independently() -> None:
    """Either total being None is enough for 'unavailable'; the other total is still its own truth."""
    only_pnl_missing = position("AAA", 1000.0, cost_basis=800.0, unrealized_pnl=None)
    snapshot = ImportedPortfolioSnapshot.model_validate(imported_snapshot(positions=[only_pnl_missing]))

    overview = build_portfolio_overview(snapshot)

    assert overview.total_cost_basis == 800.0
    assert overview.total_unrealized_pnl is None
    assert overview.cost_basis_trust == "unavailable"


def test_no_positions_sums_to_zero_and_stays_stated() -> None:
    """Design C2: 'no positions gives 0.0 as today' - an empty portfolio is not 'unavailable'."""
    overview = build_portfolio_overview(ImportedPortfolioSnapshot.model_validate(imported_snapshot()))

    assert (overview.total_cost_basis, overview.total_unrealized_pnl) == (0.0, 0.0)
    assert overview.cost_basis_trust == "stated"


def test_overview_schema_rejects_stated_over_a_null_total_and_rejects_other_trust_words(ib) -> None:
    valid = build_portfolio_overview(ib).model_dump()

    with pytest.raises(ValidationError):
        PortfolioOverview.model_validate({**valid, "total_cost_basis": None})
    with pytest.raises(ValidationError):
        PortfolioOverview.model_validate({**valid, "total_unrealized_pnl": None})
    # 'unavailable' is the only honest word for a null total
    accepted = PortfolioOverview.model_validate({**valid, "total_cost_basis": None, "total_unrealized_pnl": None, "cost_basis_trust": "unavailable"})
    assert accepted.cost_basis_trust == "unavailable"
    for wrong in ("withheld", "degraded"):
        with pytest.raises(ValidationError):
            PortfolioOverview.model_validate({**valid, "total_cost_basis": None, "total_unrealized_pnl": None, "cost_basis_trust": wrong})


def test_overview_persisted_before_the_trust_field_existed_reads_as_stated(ib) -> None:
    """The one test that pins this default: overrides saved by earlier builds omit the key."""
    legacy = build_portfolio_overview(ib).model_dump()
    legacy.pop("cost_basis_trust")

    assert PortfolioOverview.model_validate(legacy).cost_basis_trust == "stated"


def test_ff_bootstrap_overview_is_unavailable_end_to_end() -> None:
    """AC 3 through the statement-path bootstrap the desktop calls."""
    overview = build_import_bootstrap([str(FREEDOM24_PATH)], "SPY", {}).overview

    assert (overview.total_cost_basis, overview.total_unrealized_pnl, overview.cost_basis_trust) == (None, None, "unavailable")


# ── AC 7: the request path states no cost basis ─────────────────────────────


def test_request_path_builder_yields_unavailable_cost_basis_for_every_position(ib) -> None:
    snapshot = build_imported_snapshot_from_request(_ib_like_request(ib))

    assert len(snapshot.positions) == len(ib.positions)
    assert {p.cost_basis for p in snapshot.positions} == {None}
    assert {p.unrealized_pnl for p in snapshot.positions} == {None}


def test_request_path_overview_is_unavailable_not_market_value_and_zero(ib) -> None:
    """AC 7: was total_cost_basis 62,843.22 (= market value) and total_unrealized_pnl 0.00."""
    overview = build_portfolio_overview(build_imported_snapshot_from_request(_ib_like_request(ib)))

    assert (overview.total_cost_basis, overview.total_unrealized_pnl, overview.cost_basis_trust) == (None, None, "unavailable")


def test_exposure_engine_route_serialises_cost_basis_as_null_not_zero(ib) -> None:
    body = _ib_like_request(ib).model_dump(mode="json")

    response = TestClient(app).post("/engines/exposure/run", json=body)

    assert response.status_code == 200
    overview = response.json()["overview"]
    assert overview["total_cost_basis"] is None
    assert overview["total_unrealized_pnl"] is None
    assert overview["cost_basis_trust"] == "unavailable"
    assert all(item["unrealized_pnl"] is None for item in overview["top_positions"])


def test_analyze_snapshot_route_added_node_path_is_unavailable(ib) -> None:
    body = _ib_like_request(ib).model_dump(mode="json")

    response = TestClient(app).post("/portfolios/import/interactive-brokers/analyze-snapshot", json=body)

    assert response.status_code == 200
    payload = response.json()
    assert {p["cost_basis"] for p in payload["snapshot"]["positions"]} == {None}
    assert {p["unrealized_pnl"] for p in payload["snapshot"]["positions"]} == {None}
    assert payload["overview"]["cost_basis_trust"] == "unavailable"


# ── grep-style guard: no fabrication site remains (both sites, by computation) ─

# Each pattern is a way the value has been (or could be) fabricated. They are
# applied to every production module, and the guard itself is proved capable of
# failing by the parametrised "catches" test below. A quantity-times-price
# pattern is deliberately absent: ledger lot arithmetic legitimately multiplies
# a STATED trade price by a quantity; the AST check below covers the position sites.
FABRICATION_PATTERNS = {
    "cost basis set from market value or close price": r"cost_basis\s*=\s*[^=\n#]*\b(market_value|close_price)\b",
    "unrealized P&L zero-filled": r"unrealized_pnl\s*=\s*0(\.0+)?\s*[,)\n]",
    "P&L derived as market value minus a cost": r"market_value\s*-\s*\w*cost",
}


def _production_modules() -> list[Path]:
    return [p for p in APP_DIR.rglob("*.py") if "tests" not in p.relative_to(APP_DIR).parts]


@pytest.mark.parametrize(
    "snippet",
    [
        "cost_basis=item.market_value,",
        "cost_basis = position.close_price",
        "unrealized_pnl=0,",
        "unrealized_pnl = 0.0)",
        "pnl = market_value - total_cost",
    ],
)
def test_the_fabrication_guard_catches_each_known_fabrication_shape(snippet) -> None:
    assert any(re.search(pattern, snippet) for pattern in FABRICATION_PATTERNS.values())


def test_no_production_module_derives_cost_basis_or_zero_fills_pnl() -> None:
    offences = [
        f"{path.relative_to(APP_DIR)}:{lineno}: {label}: {line.strip()}"
        for path in _production_modules()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        for label, pattern in FABRICATION_PATTERNS.items()
        if re.search(pattern, line)
    ]

    assert offences == []


@pytest.mark.parametrize("module", ["importers/freedom24.py", "services/portfolio_snapshot_builder.py"])
def test_the_two_fabrication_sites_construct_positions_with_literal_none(module) -> None:
    """The two sites F4 found: every ImportedPosition built there passes cost_basis and
    unrealized_pnl as the literal None - a derived expression would fail this."""
    tree = ast.parse((APP_DIR / module).read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "ImportedPosition"
    ]

    assert calls, f"{module} no longer constructs ImportedPosition - update this guard"
    for call in calls:
        keywords = {kw.arg: kw.value for kw in call.keywords}
        for field in ("cost_basis", "unrealized_pnl"):
            value = keywords.get(field)
            assert isinstance(value, ast.Constant) and value.value is None, f"{module}: {field} is not literal None"


def test_enriched_position_and_its_builder_are_removed() -> None:
    """Design: no production caller, so it was removed rather than made nullable."""
    assert not hasattr(reconciliation_schemas, "EnrichedPosition")
    assert not hasattr(performance, "build_enriched_positions")


# ── AC 8: merge sums only when both statements state ────────────────────────


def _merged(first: dict, second: dict) -> ImportedPosition:
    a = ImportedPortfolioSnapshot.model_validate(account_snapshot("U1", positions=[position("AAA", 200.0, **first)]))
    b = ImportedPortfolioSnapshot.model_validate(account_snapshot("U2", positions=[position("AAA", 300.0, **second)]))
    (merged,) = combine_imported_snapshots([a, b]).positions
    return merged


def test_merge_sums_cost_basis_and_pnl_when_both_inputs_state_them() -> None:
    merged = _merged({"cost_basis": 100.0, "unrealized_pnl": 20.0}, {"cost_basis": 250.0, "unrealized_pnl": 50.0})

    assert (merged.cost_basis, merged.unrealized_pnl) == (350.0, 70.0)


@pytest.mark.parametrize(
    "first, second",
    [
        ({"cost_basis": None, "unrealized_pnl": None}, {"cost_basis": 250.0, "unrealized_pnl": 50.0}),
        ({"cost_basis": 100.0, "unrealized_pnl": 20.0}, {"cost_basis": None, "unrealized_pnl": None}),
        ({"cost_basis": None, "unrealized_pnl": None}, {"cost_basis": None, "unrealized_pnl": None}),
    ],
    ids=["first-null", "second-null", "both-null"],
)
def test_merge_of_a_null_with_anything_is_none_never_the_stated_side_alone(first, second) -> None:
    merged = _merged(first, second)

    assert merged.cost_basis is None and merged.unrealized_pnl is None


def test_merge_treats_cost_basis_and_pnl_independently() -> None:
    merged = _merged({"cost_basis": 100.0, "unrealized_pnl": None}, {"cost_basis": 250.0, "unrealized_pnl": 50.0})

    assert merged.cost_basis == 350.0
    assert merged.unrealized_pnl is None
    # market value and quantity are broker truth that always sums
    assert (merged.market_value, merged.quantity) == (500.0, 20.0)


# ── AC 10: no opening-lot cost estimate without a stated basis ────────────────


def test_ff_opening_vti_lot_carries_no_estimated_unit_cost(ff) -> None:
    lots = [lot for lot in reconstruct_position_lots(ff) if lot.symbol == "VTI"]

    opening = next(lot for lot in lots if lot.source == "opening_balance")
    assert opening.remaining_quantity == 3.0
    assert opening.unit_cost is None
    assert opening.remaining_cost_basis is None
    assert opening.cost_basis_is_estimated is False
    # the in-period BUY is statement-stated and is not touched by the null
    bought = next(lot for lot in lots if lot.source == "statement_trade")
    assert (bought.remaining_quantity, bought.unit_cost, bought.cost_basis_is_estimated) == (6.0, 322.426, False)


# ── AC 12: no performance number moves ────────────────────────────────────────


def test_ib_dashboard_history_is_independent_of_cost_basis_and_pnl(ib) -> None:
    """Nothing in the replay reads cost basis: stated, null and fabricated give identical output.

    Uses the committed frozen market data (the conftest dashboard mock returns an
    empty history for IB, which would make this comparison vacuous).
    """
    market_data = FrozenMarketData.from_file()

    def dashboard(positions: list[ImportedPosition]) -> str:
        snapshot = ib.model_copy(update={"positions": positions})
        return run_imported_dashboard_history(snapshot, "SPY", market_data=market_data).model_dump_json()

    nulled = [p.model_copy(update={"cost_basis": None, "unrealized_pnl": None}) for p in ib.positions]
    fabricated = [p.model_copy(update={"cost_basis": p.market_value, "unrealized_pnl": 0.0}) for p in ib.positions]

    stated_output = dashboard(list(ib.positions))
    assert len(run_imported_dashboard_history(ib, "SPY", market_data=market_data).daily_states) > 20  # non-vacuous
    assert dashboard(nulled) == stated_output
    assert dashboard(fabricated) == stated_output

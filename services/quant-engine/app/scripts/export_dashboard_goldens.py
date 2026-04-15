from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from app.analytics.overview import build_portfolio_overview
from app.services.dashboard_history_engine import run_imported_dashboard_history
from app.services.statement_importer import import_statements


FIXTURE_IMPORTED_AT = "2026-04-14T00:00:00Z"
IB_RANGE_KEY = "3M"
FF_RANGE_KEY = "3M"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _dashboard_golden_output_path(repo_root: Path) -> Path:
    return repo_root / "apps" / "desktop" / "src" / "test" / "dashboardGoldens.ts"


def _docs_statement_path(repo_root: Path, filename: str, fallback: str | None = None) -> Path:
    docs_dir = repo_root / "docs"
    primary = docs_dir / filename
    if primary.exists():
        return primary
    if fallback is None:
        return primary
    return docs_dir / fallback


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _serialize(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: _serialize(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _format_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def _format_money(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.2f}"


def _format_plain_number(value: float | int) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric}"


def _format_multiple(value: float | None, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value:.2f}{suffix}"


def _format_broker_label(importer: str) -> str:
    if importer == "multi_broker":
        return "Multi-Broker"
    return "Freedom24" if importer == "freedom24" else "Interactive Brokers"


def _dashboard_source_label(status: str | None) -> str:
    if status == "live":
        return "Live market history"
    if status == "suppressed":
        return "Suppressed unstable series"
    return "Sample or reconstructed history"


def _build_sector_snapshot(snapshot: dict[str, Any], overview: dict[str, Any]) -> dict[str, str]:
    sector_by_symbol = {
        position["symbol"].upper(): sector
        for sector, positions in overview["sector_position_breakdown"].items()
        for position in positions
    }
    totals: dict[str, float] = {}
    portfolio_total = 0.0
    for position in snapshot["positions"]:
        sector = sector_by_symbol.get(position["symbol"].upper(), "Unassigned")
        totals[sector] = totals.get(sector, 0.0) + position["market_value"]
        portfolio_total += position["market_value"]
    ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return {sector: f"{((market_value / portfolio_total) * 100):.1f}%" for sector, market_value in ordered} if portfolio_total > 0 else {}


def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(snapshot))
    statement = normalized.get("statement")
    if isinstance(statement, dict):
        statement["imported_at"] = FIXTURE_IMPORTED_AT

    statements = normalized.get("statements")
    if isinstance(statements, list):
        for item in statements:
            if isinstance(item, dict):
                item["imported_at"] = FIXTURE_IMPORTED_AT

    return normalized


def _build_expected_values(snapshot: dict[str, Any], overview: dict[str, Any], history: dict[str, Any], *, range_key: str) -> dict[str, Any]:
    source_status = cast(dict[str, Any] | None, history.get("source_status"))
    range_metrics = cast(dict[str, Any], history.get("range_metrics") or {})
    selected_range_metrics = cast(dict[str, Any], range_metrics.get(range_key) or {})
    selected_summary = cast(dict[str, Any], selected_range_metrics.get("summary") or {})
    loaded_files = [Path(statement["source_path"]).name for statement in snapshot["statements"]]
    sectors = _build_sector_snapshot(snapshot, overview)
    broad_market_positions = cast(list[dict[str, Any]], overview["sector_position_breakdown"].get("Broad Market", []))
    tech_positions = cast(list[dict[str, Any]], overview["sector_position_breakdown"].get("Technology", []))
    selected_monthly_returns = cast(list[dict[str, Any]], selected_range_metrics.get("monthly_returns") or [])
    base_capital = sum(position["market_value"] for position in snapshot["positions"])
    gross_exposure = sum(abs(position["market_value"]) for position in snapshot["positions"])
    leverage_ratio = (gross_exposure / base_capital) if base_capital > 0 else None
    technology_holding_weights = {
        position["symbol"]: _format_pct((position["market_value"] / base_capital) * 100 if base_capital > 0 else None)
        for position in tech_positions
    }

    expected: dict[str, Any] = {
        "accountId": snapshot["statement"]["account_id"],
        "brokerLabel": _format_broker_label(snapshot["statement"]["importer"]),
        "sourceLabel": _dashboard_source_label(source_status["performance_history"] if source_status else None),
        "statementPeriod": snapshot["statement"]["statement_period"],
        "accountSummary": f"{_format_broker_label(snapshot['statement']['importer'])} · {snapshot['statement']['statement_period']}",
        "performanceTitle": "Portfolio vs SPY path for the selected range",
        "loadedFileLabel": f"Loaded file: {loaded_files[0]}" if len(loaded_files) == 1 else f"Loaded statements: {', '.join(loaded_files)}",
        "monthlyStatusLabel": f"Monthly-return status: {_dashboard_source_label(source_status['monthly_returns'])}" if source_status else None,
        "portfolioValue": _format_money(selected_summary.get("end_value")),
        "startValue": _format_money(selected_summary.get("start_value")),
        "timeWeightedReturn": _format_pct(selected_summary.get("time_weighted_return_pct")),
        "netContributions": _format_money(selected_summary.get("net_contributions")),
        "moneyWeightedReturn": _format_pct(selected_summary.get("money_weighted_return_pct")),
        "drawdown": _format_pct(selected_range_metrics.get("max_drawdown_pct")),
        "loadedFiles": loaded_files,
        "monthlyReturns": [
            {"month": item["month"], "returnPct": _format_pct(item.get("return_pct"))}
            for item in selected_monthly_returns
        ],
        "sectors": sectors,
        "draftCapitalCheck": _format_money(0.0),
        "draftCapitalHelper": f"Remaining capital after edits · Leverage {_format_multiple(leverage_ratio, 'x')}",
    }

    if tech_positions:
        expected["technologyHoldings"] = [position["symbol"] for position in tech_positions]
        expected["technologyHoldingWeights"] = technology_holding_weights
        sxrv_position = next((position for position in tech_positions if position["symbol"] == "SXRV"), None)
        if sxrv_position is not None:
            expected["sxrvValue"] = _format_plain_number(sxrv_position["market_value"])

    if broad_market_positions:
        expected["broadMarketHoldings"] = [position["symbol"] for position in broad_market_positions]
        expected["broadMarketHoldingWeights"] = {
            position["symbol"]: _format_pct((position["market_value"] / base_capital) * 100 if base_capital > 0 else None)
            for position in broad_market_positions
        }
        vti_position = next((position for position in broad_market_positions if position["symbol"] == "VTI"), None)
        if vti_position is not None:
            expected["vtiValue"] = _format_plain_number(vti_position["market_value"])

    return expected


def _build_fixture(snapshot_model: Any, *, range_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    overview_model = build_portfolio_overview(snapshot_model)
    history_model = run_imported_dashboard_history(snapshot_model, "SPY")

    snapshot = _normalize_snapshot(_serialize(snapshot_model))
    overview = _serialize(overview_model)
    history = _serialize(history_model)

    fixture = {
        "snapshot": snapshot,
        "overview": overview,
        "risk_summary": {
            "benchmark_symbol": "SPY",
            "methodology": "imported dashboard history",
            "start_date": history["daily_states"][0]["date"] if history["daily_states"] else None,
            "end_date": history["daily_states"][-1]["date"] if history["daily_states"] else None,
            "observations": len(history["daily_states"]),
            "portfolio_beta": None,
            "portfolio_correlation": None,
            "r_squared": None,
            "portfolio_volatility_pct": None,
            "benchmark_volatility_pct": None,
        },
        "benchmark": history["benchmark"],
        "daily_states": history["daily_states"],
        "performance_series": history["performance_series"],
        "source_status": history["source_status"],
        "range_metrics": history.get("range_metrics"),
    }
    expected = _build_expected_values(snapshot, overview, history, range_key=range_key)
    return expected, fixture


def _render_typescript(ib_expected: dict[str, Any], ib_fixture: dict[str, Any], ff_expected: dict[str, Any], ff_fixture: dict[str, Any]) -> str:
    ib_expected_json = json.dumps(ib_expected, indent=2)
    ib_fixture_json = json.dumps(ib_fixture, indent=2)
    ff_expected_json = json.dumps(ff_expected, indent=2)
    ff_fixture_json = json.dumps(ff_fixture, indent=2)
    return (
        "import type { ImportedDashboardSource, ImportedPortfolioSnapshotSource } from '../features/portfolio/types'\n\n"
        "// Generated by `python -m app.scripts.export_dashboard_goldens`\n"
        f"export const ib2026DashboardGolden = {ib_expected_json} as const\n\n"
        "// Generated by `python -m app.scripts.export_dashboard_goldens`\n"
        f"export const ib2026ImportedDashboardGoldenFixture = {ib_fixture_json} satisfies ImportedDashboardSource & ImportedPortfolioSnapshotSource\n\n"
        "// Generated by `python -m app.scripts.export_dashboard_goldens`\n"
        f"export const ff2026DashboardGolden = {ff_expected_json} as const\n\n"
        "// Generated by `python -m app.scripts.export_dashboard_goldens`\n"
        f"export const ff2026ImportedDashboardGoldenFixture = {ff_fixture_json} satisfies ImportedDashboardSource & ImportedPortfolioSnapshotSource\n"
    )


def main() -> None:
    repo_root = _repo_root()
    output_path = _dashboard_golden_output_path(repo_root)

    ib_statement_path = _docs_statement_path(repo_root, "IB2026.pdf", fallback="2026.pdf")
    ff_statement_path = _docs_statement_path(repo_root, "FF2026.pdf")

    ib_snapshot_model = import_statements([str(ib_statement_path)])
    ff_snapshot_model = import_statements([str(ff_statement_path)])

    ib_expected, ib_fixture = _build_fixture(ib_snapshot_model, range_key=IB_RANGE_KEY)
    ff_expected, ff_fixture = _build_fixture(ff_snapshot_model, range_key=FF_RANGE_KEY)

    output_path.write_text(_render_typescript(ib_expected, ib_fixture, ff_expected, ff_fixture), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.analytics.overview import build_portfolio_overview
from app.importers.interactive_brokers import import_statement
from app.services.dashboard_history_engine import run_imported_dashboard_history


RANGE_3M_LENGTH = 63


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _docs_statement_path(repo_root: Path) -> Path:
    docs_dir = repo_root / "docs"
    primary = docs_dir / "IB2026.pdf"
    fallback = docs_dir / "2026.pdf"
    return primary if primary.exists() else fallback


def _dashboard_golden_output_path(repo_root: Path) -> Path:
    return repo_root / "apps" / "desktop" / "src" / "test" / "ib2026DashboardGolden.ts"


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
    return {sector: f"{((market_value / portfolio_total) * 100):.1f}%" for sector, market_value in ordered}


def _build_expected_values(snapshot: dict[str, Any], overview: dict[str, Any], history: dict[str, Any]) -> dict[str, Any]:
    source_status = history.get("source_status")
    range_metrics = history.get("range_metrics") or {}
    selected_range_metrics = range_metrics.get("3M") or {}
    selected_summary = selected_range_metrics.get("summary") or {}
    loaded_files = [Path(statement["source_path"]).name for statement in snapshot["statements"]]
    sectors = _build_sector_snapshot(snapshot, overview)
    tech_positions = overview["sector_position_breakdown"].get("Technology", [])
    selected_monthly_returns = selected_range_metrics.get("monthly_returns") or []
    base_capital = sum(position["market_value"] for position in snapshot["positions"])
    gross_exposure = sum(abs(position["market_value"]) for position in snapshot["positions"])
    leverage_ratio = (gross_exposure / base_capital) if base_capital > 0 else None
    technology_holding_weights = {
        position["symbol"]: _format_pct((position["market_value"] / base_capital) * 100 if base_capital > 0 else None)
        for position in tech_positions
    }

    return {
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
        "technologyHoldings": [position["symbol"] for position in tech_positions],
        "technologyHoldingWeights": technology_holding_weights,
        "sxrvValue": _format_plain_number(next(position["market_value"] for position in tech_positions if position["symbol"] == "SXRV")),
    }


def _render_typescript(expected: dict[str, Any], fixture: dict[str, Any]) -> str:
    expected_json = json.dumps(expected, indent=2)
    fixture_json = json.dumps(fixture, indent=2)
    return f"import type {{ ImportedDashboardSource, ImportedPortfolioSnapshotSource }} from '../features/portfolio/types'\n\n// Generated by `python -m app.scripts.export_ib2026_dashboard_golden`\nexport const ib2026DashboardGolden = {expected_json} as const\n\n// Generated by `python -m app.scripts.export_ib2026_dashboard_golden`\nexport const ib2026ImportedDashboardGoldenFixture = {fixture_json} satisfies ImportedDashboardSource & ImportedPortfolioSnapshotSource\n"


def main() -> None:
    repo_root = _repo_root()
    statement_path = _docs_statement_path(repo_root)
    output_path = _dashboard_golden_output_path(repo_root)

    snapshot_model = import_statement(statement_path)
    overview_model = build_portfolio_overview(snapshot_model)
    history_model = run_imported_dashboard_history(snapshot_model, "SPY")

    snapshot = _serialize(snapshot_model)
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
    expected = _build_expected_values(snapshot, overview, history)

    output_path.write_text(_render_typescript(expected, fixture), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

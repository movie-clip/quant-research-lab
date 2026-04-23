from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from hashlib import sha256
from math import sqrt
from typing import cast

from app.schemas.optimizer import (
    OptimizationIssue,
    OptimizerAlphaCoverageFlags,
    OptimizerAlphaDiagnostics,
    OptimizerAlphaInputContract,
    OptimizerAlphaInputDescriptor,
    OptimizerAlphaFundamentalSnapshot,
    OptimizerAlphaLagPolicy,
    OptimizerAlphaMetadata,
    OptimizerAlphaMeasureId,
    OptimizerAlphaPackage,
    OptimizerAlphaPitFundamentalRecord,
    OptimizerAlphaPitFundamentalsInput,
    OptimizerAlphaPitProvenance,
    OptimizerAlphaPitTrustReport,
    OptimizerAlphaSecurityRow,
    OptimizerAlphaSignalId,
    OptimizerAlphaSubSignal,
)
from app.services.optimizer_alpha_fundamentals import AlphaQualityPitIngestionService, AlphaQualityPitTrustGate


ALPHA_PACKAGE_VERSION = "alpha_quality_v1"
ALPHA_METHODOLOGY_ID = "alpha_quality_v1_methodology"
SUPPORTED_ALPHA_PACKAGE_VERSIONS = {ALPHA_PACKAGE_VERSION}
COMPONENT_IDS: tuple[OptimizerAlphaSignalId, ...] = (
    "profitability",
    "cash_generation",
    "accrual_quality",
    "leverage_discipline",
)
DEFAULT_COMPONENT_WEIGHTS: dict[OptimizerAlphaSignalId, float] = {
    "profitability": 0.35,
    "cash_generation": 0.30,
    "accrual_quality": 0.20,
    "leverage_discipline": 0.15,
}
DEFAULT_COMPONENT_DEFINITIONS: dict[OptimizerAlphaSignalId, str] = {
    "profitability": "Profitability prefers stronger gross profitability and falls back to EBIT over assets when gross profit inputs are unavailable.",
    "cash_generation": "Cash generation prefers operating cash flow over assets and falls back to free cash flow over assets when CFO inputs are unavailable.",
    "accrual_quality": "Accrual quality prefers earnings backed by cash by penalizing net income minus operating cash flow, scaled by assets.",
    "leverage_discipline": "Leverage discipline prefers lower net debt relative to assets using total debt less cash and equivalents.",
}


@dataclass(frozen=True)
class OptimizerAlphaPackageConfig:
    lag_policy: OptimizerAlphaLagPolicy = field(default_factory=OptimizerAlphaLagPolicy)
    winsor_lower_quantile: float = 0.10
    winsor_upper_quantile: float = 0.90
    zscore_cap: float = 3.0
    conservative_fallback_score: float = -1.0
    component_weights: dict[OptimizerAlphaSignalId, float] = field(default_factory=lambda: dict(DEFAULT_COMPONENT_WEIGHTS))


@dataclass(frozen=True)
class OptimizerAlphaPreferenceConfig:
    l1_active_tilt_budget: float = 0.04


def build_alpha_quality_package(
    *,
    rebalance_date: str,
    universe_symbols: list[str],
    fundamental_snapshots: list[OptimizerAlphaFundamentalSnapshot],
    as_of_date: str | None = None,
    source_name: str = "direct_snapshot_input",
    replay_id: str | None = None,
    config: OptimizerAlphaPackageConfig | None = None,
) -> OptimizerAlphaPackage:
    config = config or OptimizerAlphaPackageConfig()
    effective_as_of_date = as_of_date or rebalance_date
    normalized_snapshots = [_normalized_snapshot(snapshot) for snapshot in fundamental_snapshots]
    input_descriptor = _build_legacy_input_descriptor(
        as_of_date=effective_as_of_date,
        source_name=source_name,
        replay_id=replay_id,
        snapshots=normalized_snapshots,
        lag_policy=config.lag_policy,
    )
    return _build_alpha_quality_package_from_snapshots(
        rebalance_date=rebalance_date,
        as_of_date=effective_as_of_date,
        universe_symbols=universe_symbols,
        normalized_snapshots=normalized_snapshots,
        input_descriptor=input_descriptor,
        config=config,
    )


def build_alpha_quality_package_from_pit_input(
    *,
    rebalance_date: str,
    pit_input: OptimizerAlphaPitFundamentalsInput,
    trust_report: OptimizerAlphaPitTrustReport | None = None,
    config: OptimizerAlphaPackageConfig | None = None,
) -> OptimizerAlphaPackage:
    config = config or OptimizerAlphaPackageConfig()
    normalized_records = _normalized_pit_records(pit_input.records)
    input_digest = _build_pit_input_digest(
        decision_date=pit_input.decision_date,
        as_of_date=pit_input.as_of_date,
        source_name=pit_input.source_name,
        replay_id=pit_input.replay_id,
        universe_symbols=pit_input.universe_symbols,
        records=normalized_records,
    )
    normalized_snapshots = [_pit_record_to_snapshot(record) for record in normalized_records]
    input_descriptor = OptimizerAlphaInputDescriptor(
        contract=_build_input_contract(config.lag_policy),
        as_of_date=pit_input.as_of_date,
        source_name=pit_input.source_name,
        replay_id=pit_input.replay_id,
        input_record_count=len(normalized_records),
        input_digest=input_digest,
        pit_provenance=_build_pit_provenance(
            pit_input=pit_input,
            trust_report=trust_report,
            input_digest=input_digest,
        ),
    )
    return _build_alpha_quality_package_from_snapshots(
        rebalance_date=rebalance_date,
        as_of_date=pit_input.as_of_date,
        universe_symbols=pit_input.universe_symbols,
        normalized_snapshots=normalized_snapshots,
        input_descriptor=input_descriptor,
        config=config,
    )


def build_alpha_quality_package_from_live_pit_universe(
    *,
    rebalance_date: str,
    as_of_date: str,
    universe_symbols: list[str],
    config: OptimizerAlphaPackageConfig | None = None,
    ingestion_service: AlphaQualityPitIngestionService | None = None,
    trust_gate: AlphaQualityPitTrustGate | None = None,
) -> OptimizerAlphaPackage:
    service = ingestion_service or AlphaQualityPitIngestionService()
    service.load_or_ingest_for_universe(
        as_of_date=as_of_date,
        decision_date=rebalance_date,
        universe_symbols=universe_symbols,
    )
    gate = trust_gate or AlphaQualityPitTrustGate(
        snapshot_store=service.snapshot_store,
        instrument_registry=service.instrument_registry,
    )
    trusted_pit_input = gate.assert_trusted_snapshot(
        as_of_date=as_of_date,
        decision_date=rebalance_date,
        universe_symbols=universe_symbols,
    )
    trust_report = service.snapshot_store.load_trust_report(as_of_date)
    if trust_report is None or trust_report.status != "trusted":
        raise ValueError(f"trusted PIT trust report missing for {as_of_date}")
    return build_alpha_quality_package_from_pit_input(
        rebalance_date=rebalance_date,
        pit_input=trusted_pit_input,
        trust_report=trust_report,
        config=config,
    )


def _build_alpha_quality_package_from_snapshots(
    *,
    rebalance_date: str,
    as_of_date: str,
    universe_symbols: list[str],
    normalized_snapshots: list[OptimizerAlphaFundamentalSnapshot],
    input_descriptor: OptimizerAlphaInputDescriptor,
    config: OptimizerAlphaPackageConfig,
) -> OptimizerAlphaPackage:
    ordered_symbols = sorted({symbol.upper() for symbol in universe_symbols})
    rebalance_dt = date.fromisoformat(rebalance_date)
    as_of_dt = date.fromisoformat(as_of_date)
    snapshots_by_symbol: dict[str, list[OptimizerAlphaFundamentalSnapshot]] = {symbol: [] for symbol in ordered_symbols}
    for snapshot in normalized_snapshots:
        symbol = snapshot.symbol.upper()
        if symbol in snapshots_by_symbol:
            snapshots_by_symbol[symbol].append(snapshot)

    preliminary_rows: list[OptimizerAlphaSecurityRow] = []
    selected_effective_date_by_symbol: dict[str, str | None] = {}
    missing_snapshot_symbols: list[str] = []
    stale_symbols: list[str] = []
    lag_blocked_symbols: list[str] = []

    for symbol in ordered_symbols:
        selected_snapshot, lag_blocked = _select_point_in_time_snapshot(
            as_of_dt=as_of_dt,
            snapshots=snapshots_by_symbol.get(symbol, []),
            lag_policy=config.lag_policy,
        )
        effective_date = _snapshot_effective_date(selected_snapshot, config.lag_policy) if selected_snapshot is not None else None
        stale_snapshot = False
        if effective_date is not None:
            stale_snapshot = (rebalance_dt - date.fromisoformat(effective_date)).days > config.lag_policy.stale_after_days

        row = OptimizerAlphaSecurityRow(
            symbol=symbol,
            selected_snapshot=selected_snapshot,
            effective_date=effective_date,
            coverage_flags=OptimizerAlphaCoverageFlags(
                has_eligible_snapshot=selected_snapshot is not None,
                has_fresh_snapshot=selected_snapshot is not None and not stale_snapshot,
                has_any_signal_coverage=False,
                has_complete_signal_set=False,
                used_conservative_fallback=False,
                stale_snapshot=stale_snapshot,
                lag_blocked=lag_blocked,
                missing_snapshot=selected_snapshot is None,
            ),
            sub_signals=[
                OptimizerAlphaSubSignal(component_id="profitability", weight=config.component_weights["profitability"], higher_is_better=True, normalized_score=0.0, available=False, fallback_applied=False),
                OptimizerAlphaSubSignal(component_id="cash_generation", weight=config.component_weights["cash_generation"], higher_is_better=True, normalized_score=0.0, available=False, fallback_applied=False),
                OptimizerAlphaSubSignal(component_id="accrual_quality", weight=config.component_weights["accrual_quality"], higher_is_better=False, normalized_score=0.0, available=False, fallback_applied=False),
                OptimizerAlphaSubSignal(component_id="leverage_discipline", weight=config.component_weights["leverage_discipline"], higher_is_better=False, normalized_score=0.0, available=False, fallback_applied=False),
            ],
            final_score=0.0,
        )
        selected_effective_date_by_symbol[symbol] = effective_date
        if selected_snapshot is None:
            missing_snapshot_symbols.append(symbol)
        if stale_snapshot:
            stale_symbols.append(symbol)
        if lag_blocked:
            lag_blocked_symbols.append(symbol)
        preliminary_rows.append(row)

    component_values: dict[OptimizerAlphaSignalId, list[tuple[int, float]]] = {component: [] for component in COMPONENT_IDS}
    rows: list[OptimizerAlphaSecurityRow] = []
    for index, row in enumerate(preliminary_rows):
        component_rows = [_build_component_signal(snapshot=row.selected_snapshot, coverage_flags=row.coverage_flags, component_id=component_id, config=config) for component_id in COMPONENT_IDS]
        for component in component_rows:
            if component.available and component.raw_value is not None:
                component_values[component.component_id].append((index, component.raw_value))
        rows.append(row.model_copy(update={"sub_signals": component_rows}))

    rows = _apply_cross_sectional_normalization(rows, component_values, config)
    component_coverage_counts: dict[OptimizerAlphaSignalId, int] = {component: 0 for component in COMPONENT_IDS}
    covered_symbol_count = 0
    fresh_snapshot_count = 0
    complete_signal_symbol_count = 0
    fallback_symbols: list[str] = []
    final_rows: list[OptimizerAlphaSecurityRow] = []
    for row in rows:
        has_any_signal_coverage = any(item.available for item in row.sub_signals)
        has_complete_signal_set = all(item.available for item in row.sub_signals)
        used_conservative_fallback = any(item.fallback_applied for item in row.sub_signals)
        for item in row.sub_signals:
            if item.available:
                component_coverage_counts[item.component_id] += 1
        if has_any_signal_coverage:
            covered_symbol_count += 1
        if has_complete_signal_set:
            complete_signal_symbol_count += 1
        if row.coverage_flags.has_fresh_snapshot:
            fresh_snapshot_count += 1
        if used_conservative_fallback:
            fallback_symbols.append(row.symbol)
        final_score = round(sum(item.weight * item.normalized_score for item in row.sub_signals), 8)
        final_rows.append(
            row.model_copy(
                update={
                    "coverage_flags": row.coverage_flags.model_copy(
                        update={
                            "has_any_signal_coverage": has_any_signal_coverage,
                            "has_complete_signal_set": has_complete_signal_set,
                            "used_conservative_fallback": used_conservative_fallback,
                        }
                    ),
                    "final_score": final_score,
                }
            )
        )

    coverage_ratio = (covered_symbol_count / len(ordered_symbols)) if ordered_symbols else 0.0
    complete_coverage_ratio = (complete_signal_symbol_count / len(ordered_symbols)) if ordered_symbols else 0.0
    diagnostics_status = "invalid" if missing_snapshot_symbols or stale_symbols or lag_blocked_symbols or fallback_symbols else "ok"
    metadata = OptimizerAlphaMetadata(
        methodology_id=ALPHA_METHODOLOGY_ID,
        winsor_lower_quantile=config.winsor_lower_quantile,
        winsor_upper_quantile=config.winsor_upper_quantile,
        zscore_cap=config.zscore_cap,
        conservative_fallback_score=config.conservative_fallback_score,
        lag_policy=config.lag_policy,
        input_descriptor=input_descriptor,
        component_weights=cast(dict[OptimizerAlphaSignalId, float], dict(config.component_weights)),
        component_definitions=cast(dict[OptimizerAlphaSignalId, str], dict(DEFAULT_COMPONENT_DEFINITIONS)),
    )
    package_id = _build_alpha_package_id(rebalance_date=rebalance_date, ordered_symbols=ordered_symbols, rows=final_rows, metadata=metadata)
    return OptimizerAlphaPackage(
        package_id=package_id,
        version=ALPHA_PACKAGE_VERSION,
        rebalance_date=rebalance_date,
        ordered_symbols=ordered_symbols,
        securities=final_rows,
        metadata=metadata,
        diagnostics=OptimizerAlphaDiagnostics(
            status=diagnostics_status,
            universe_symbol_count=len(ordered_symbols),
            covered_symbol_count=covered_symbol_count,
            fresh_snapshot_count=fresh_snapshot_count,
            coverage_ratio=round(coverage_ratio, 8),
            complete_coverage_ratio=round(complete_coverage_ratio, 8),
            component_coverage_counts=cast(dict[OptimizerAlphaSignalId, int], dict(component_coverage_counts)),
            selected_effective_date_by_symbol=selected_effective_date_by_symbol,
            missing_snapshot_symbols=missing_snapshot_symbols,
            stale_symbols=stale_symbols,
            lag_blocked_symbols=lag_blocked_symbols,
            fallback_symbols=fallback_symbols,
        ),
    )


def validate_optimizer_alpha_package(alpha_package: OptimizerAlphaPackage, *, expected_symbols: list[str]) -> list[OptimizationIssue]:
    issues: list[OptimizationIssue] = []
    expected_order = sorted({symbol.upper() for symbol in expected_symbols})
    package_order = [symbol.upper() for symbol in alpha_package.ordered_symbols]
    security_symbols = [item.symbol.upper() for item in alpha_package.securities]

    if alpha_package.version not in SUPPORTED_ALPHA_PACKAGE_VERSIONS:
        issues.append(
            OptimizationIssue(
                code="unsupported_alpha_package_version",
                message="Optimizer alpha package version is not supported by this optimizer baseline.",
                actual_value=alpha_package.version,
                required_value=",".join(sorted(SUPPORTED_ALPHA_PACKAGE_VERSIONS)),
            )
        )

    if package_order != expected_order:
        issues.append(
            OptimizationIssue(
                code="alpha_package_universe_misaligned",
                message="Optimizer alpha package symbol order must match the normalized optimizer universe deterministically.",
                actual_value=",".join(package_order),
                required_value=",".join(expected_order),
            )
        )

    if alpha_package.metadata.input_descriptor.as_of_date > alpha_package.rebalance_date:
        issues.append(
            OptimizationIssue(
                code="alpha_package_as_of_after_rebalance",
                message="Alpha package as_of_date cannot be later than the rebalance date used for the optimizer decision.",
                actual_value=alpha_package.metadata.input_descriptor.as_of_date,
                required_value=alpha_package.rebalance_date,
            )
        )

    if alpha_package.metadata.input_descriptor.contract.contract_id != "alpha_quality_v1_pit_fundamentals_v1":
        issues.append(
            OptimizationIssue(
                code="alpha_package_input_contract_invalid",
                message="Alpha package must declare the locked PIT fundamentals input contract used by alpha_quality_v1.",
                actual_value=alpha_package.metadata.input_descriptor.contract.contract_id,
                required_value="alpha_quality_v1_pit_fundamentals_v1",
            )
        )

    if alpha_package.metadata.input_descriptor.input_record_count < 0:
        issues.append(
            OptimizationIssue(
                code="alpha_package_input_descriptor_invalid",
                message="Alpha package input descriptor must expose a non-negative PIT input record count.",
                actual_value=alpha_package.metadata.input_descriptor.input_record_count,
                required_value=0.0,
            )
        )

    if security_symbols != package_order:
        issues.append(
            OptimizationIssue(
                code="alpha_package_security_rows_misaligned",
                message="Optimizer alpha package security rows must align one-for-one with ordered_symbols.",
                actual_value=",".join(security_symbols),
                required_value=",".join(package_order),
            )
        )

    weight_sum = sum(alpha_package.metadata.component_weights.values())
    if abs(weight_sum - 1.0) > 1e-8:
        issues.append(
            OptimizationIssue(
                code="alpha_package_component_weights_invalid",
                message="Optimizer alpha package component weights must sum to 1.0.",
                actual_value=round(weight_sum, 8),
                required_value=1.0,
                gap=round(abs(weight_sum - 1.0), 8),
            )
        )

    expected_components = set(COMPONENT_IDS)
    for row in alpha_package.securities:
        actual_components = {item.component_id for item in row.sub_signals}
        if actual_components != expected_components:
            issues.append(
                OptimizationIssue(
                    code="alpha_package_subsignal_shape_invalid",
                    message="Each alpha package security row must include the full fixed sub-signal set.",
                    actual_value=",".join(sorted(actual_components)),
                    required_value=",".join(sorted(expected_components)),
                    symbols=[row.symbol],
                )
            )
            break

    if alpha_package.diagnostics.fallback_symbols and alpha_package.diagnostics.status != "invalid":
        issues.append(
            OptimizationIssue(
                code="alpha_package_status_inconsistent",
                message="Alpha package diagnostics must be invalid when conservative fallback changes signal coverage for any symbol.",
                actual_value=alpha_package.diagnostics.status,
                required_value="invalid",
                symbols=alpha_package.diagnostics.fallback_symbols,
            )
        )

    return issues


def build_alpha_preference_vector(
    *,
    ordered_symbols: list[str],
    benchmark_weights: list[float],
    eligible_mask: list[bool],
    alpha_package: OptimizerAlphaPackage | None,
    benchmark_active_limit: float,
    config: OptimizerAlphaPreferenceConfig | None = None,
) -> tuple[list[float], float]:
    if alpha_package is None:
        return [0.0 for _ in ordered_symbols], 0.0
    config = config or OptimizerAlphaPreferenceConfig()
    score_map = {item.symbol.upper(): item.final_score for item in alpha_package.securities}
    scores = [score_map.get(symbol.upper(), 0.0) if eligible else 0.0 for symbol, eligible in zip(ordered_symbols, eligible_mask)]
    eligible_scores = [score for score, eligible in zip(scores, eligible_mask) if eligible]
    if not eligible_scores:
        return [0.0 for _ in ordered_symbols], 0.0
    mean_score = sum(eligible_scores) / len(eligible_scores)
    centered = [(score - mean_score) if eligible else 0.0 for score, eligible in zip(scores, eligible_mask)]
    scale = sum(abs(value) for value in centered)
    budget = min(config.l1_active_tilt_budget, max(benchmark_active_limit * 0.5, 0.0))
    if scale <= 0 or budget <= 0:
        return [0.0 for _ in ordered_symbols], 0.0
    preference_vector = [round((budget * value / scale), 12) for value in centered]
    total_shift = sum(preference_vector)
    if abs(total_shift) > 1e-12:
        eligible_indices = [index for index, eligible in enumerate(eligible_mask) if eligible]
        if eligible_indices:
            adjustment_index = eligible_indices[-1]
            preference_vector[adjustment_index] = round(preference_vector[adjustment_index] - total_shift, 12)
    return preference_vector, budget


def _normalized_snapshot(snapshot: OptimizerAlphaFundamentalSnapshot) -> OptimizerAlphaFundamentalSnapshot:
    return snapshot.model_copy(update={"symbol": snapshot.symbol.upper()})


def _select_point_in_time_snapshot(
    *,
    as_of_dt: date,
    snapshots: list[OptimizerAlphaFundamentalSnapshot],
    lag_policy: OptimizerAlphaLagPolicy,
) -> tuple[OptimizerAlphaFundamentalSnapshot | None, bool]:
    eligible: list[tuple[str, str, OptimizerAlphaFundamentalSnapshot]] = []
    lag_blocked = False
    for snapshot in snapshots:
        effective_date = _snapshot_effective_date(snapshot, lag_policy)
        if effective_date is None:
            lag_blocked = True
            continue
        if effective_date <= as_of_dt.isoformat():
            eligible.append((effective_date, snapshot.statement_date, snapshot))
        else:
            lag_blocked = True
    if not eligible:
        return None, lag_blocked
    eligible.sort(key=lambda item: (item[0], item[1], item[2].period_type))
    return eligible[-1][2], False


def _snapshot_effective_date(snapshot: OptimizerAlphaFundamentalSnapshot | None, lag_policy: OptimizerAlphaLagPolicy) -> str | None:
    if snapshot is None:
        return None
    if snapshot.availability_semantics == "available_date":
        return snapshot.available_date
    if snapshot.availability_semantics == "publication_date":
        return snapshot.publication_date
    if snapshot.availability_semantics == "filing_date":
        return snapshot.filing_date
    if snapshot.availability_semantics == "derived_reporting_lag":
        lag_days = lag_policy.quarterly_reporting_lag_days if snapshot.period_type == "quarterly" else lag_policy.annual_reporting_lag_days
        return (date.fromisoformat(snapshot.statement_date) + timedelta(days=lag_days)).isoformat()
    if snapshot.available_date is not None:
        return snapshot.available_date
    if snapshot.publication_date is not None:
        return snapshot.publication_date
    if snapshot.filing_date is not None:
        return snapshot.filing_date
    lag_days = lag_policy.quarterly_reporting_lag_days if snapshot.period_type == "quarterly" else lag_policy.annual_reporting_lag_days
    return (date.fromisoformat(snapshot.statement_date) + timedelta(days=lag_days)).isoformat()


def _normalized_pit_records(records: list[OptimizerAlphaPitFundamentalRecord]) -> list[OptimizerAlphaPitFundamentalRecord]:
    normalized = [
        record.model_copy(
            update={
                "symbol": record.symbol.upper(),
                "issuer_id": record.issuer_id.upper(),
                "source_dataset": record.source_dataset.strip(),
                "source_record_id": record.source_record_id.strip(),
                "currency": record.currency.upper() if record.currency is not None else None,
            }
        )
        for record in records
    ]
    return sorted(
        normalized,
        key=lambda item: (
            item.symbol,
            item.statement_date,
            item.period_type,
            _pit_record_effective_date(item),
            item.source_dataset,
            item.source_record_id,
        ),
    )


def _pit_record_to_snapshot(record: OptimizerAlphaPitFundamentalRecord) -> OptimizerAlphaFundamentalSnapshot:
    return OptimizerAlphaFundamentalSnapshot(
        source_dataset=record.source_dataset,
        source_record_id=record.source_record_id,
        symbol=record.symbol,
        issuer_id=record.issuer_id,
        statement_date=record.statement_date,
        period_type=record.period_type,
        publication_date=record.publication_date,
        filing_date=record.filing_date,
        available_date=record.available_date,
        availability_semantics=record.availability_semantics,
        currency=record.currency,
        total_revenue=record.total_revenue,
        cost_of_revenue=record.cost_of_revenue,
        ebit=record.ebit,
        total_assets=record.total_assets,
        operating_cash_flow=record.operating_cash_flow,
        free_cash_flow=record.free_cash_flow,
        net_income=record.net_income,
        total_debt=record.total_debt,
        cash_and_equivalents=record.cash_and_equivalents,
    )


def _build_input_contract(lag_policy: OptimizerAlphaLagPolicy) -> OptimizerAlphaInputContract:
    return OptimizerAlphaInputContract(reporting_lag_policy=lag_policy)


def _build_legacy_input_descriptor(
    *,
    as_of_date: str,
    source_name: str,
    replay_id: str | None,
    snapshots: list[OptimizerAlphaFundamentalSnapshot],
    lag_policy: OptimizerAlphaLagPolicy,
) -> OptimizerAlphaInputDescriptor:
    normalized_payload = [snapshot.model_dump(mode="json") for snapshot in sorted(snapshots, key=_snapshot_digest_sort_key)]
    digest = sha256(json.dumps(normalized_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return OptimizerAlphaInputDescriptor(
        contract=_build_input_contract(lag_policy),
        as_of_date=as_of_date,
        source_name=source_name,
        replay_id=replay_id,
        input_record_count=len(snapshots),
        input_digest=f"legacy_{digest}",
    )


def _build_pit_input_digest(
    *,
    decision_date: str,
    as_of_date: str,
    source_name: str,
    replay_id: str | None,
    universe_symbols: list[str],
    records: list[OptimizerAlphaPitFundamentalRecord],
) -> str:
    payload = {
        "decision_date": decision_date,
        "as_of_date": as_of_date,
        "source_name": source_name,
        "replay_id": replay_id,
        "universe_symbols": sorted({symbol.upper() for symbol in universe_symbols}),
        "records": [record.model_dump(mode="json") for record in records],
    }
    return f"pit_{sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()[:16]}"


def _build_pit_provenance(
    *,
    pit_input: OptimizerAlphaPitFundamentalsInput,
    trust_report: OptimizerAlphaPitTrustReport | None,
    input_digest: str,
) -> OptimizerAlphaPitProvenance | None:
    if trust_report is None:
        return None
    if trust_report.status != "trusted":
        raise ValueError("trust_report must be trusted for optimizer PIT assembly")
    if trust_report.as_of_date != pit_input.as_of_date:
        raise ValueError("trust_report as_of_date must match pit_input as_of_date")
    if trust_report.decision_date != pit_input.decision_date:
        raise ValueError("trust_report decision_date must match pit_input decision_date")
    persisted_digest = trust_report.persisted_input_digest or input_digest
    if persisted_digest != input_digest:
        raise ValueError("trust_report persisted_input_digest must match assembled PIT input digest")
    return OptimizerAlphaPitProvenance(
        trust_status=trust_report.status,
        as_of_date=trust_report.as_of_date,
        decision_date=pit_input.decision_date,
        snapshot_digest=persisted_digest,
        replay_digest=trust_report.replay_input_digest,
    )


def _pit_record_effective_date(record: OptimizerAlphaPitFundamentalRecord) -> str:
    if record.availability_semantics == "available_date":
        return cast(str, record.available_date)
    if record.availability_semantics == "publication_date":
        return cast(str, record.publication_date)
    if record.availability_semantics == "filing_date":
        return cast(str, record.filing_date)
    return record.statement_date


def _snapshot_digest_sort_key(snapshot: OptimizerAlphaFundamentalSnapshot) -> tuple[str, str, str, str, str, str]:
    return (
        snapshot.symbol,
        snapshot.statement_date,
        snapshot.period_type,
        _snapshot_effective_date(snapshot, OptimizerAlphaLagPolicy()) or "",
        snapshot.source_dataset or "",
        snapshot.source_record_id or "",
    )


def _build_component_signal(
    snapshot: OptimizerAlphaFundamentalSnapshot | None,
    coverage_flags: OptimizerAlphaCoverageFlags,
    component_id: OptimizerAlphaSignalId,
    config: OptimizerAlphaPackageConfig,
) -> OptimizerAlphaSubSignal:
    higher_is_better = component_id in {"profitability", "cash_generation"}
    component_weight = config.component_weights[component_id]
    if snapshot is None or coverage_flags.stale_snapshot:
        return OptimizerAlphaSubSignal(
            component_id=component_id,
            weight=component_weight,
            higher_is_better=higher_is_better,
            normalized_score=config.conservative_fallback_score,
            available=False,
            fallback_applied=True,
            stale_input=coverage_flags.stale_snapshot,
            note="No fresh point-in-time snapshot available; conservative fallback applied.",
        )

    measure_id, raw_value, missing_fields = _extract_raw_component_value(snapshot, component_id)
    typed_measure_id = cast(OptimizerAlphaMeasureId | None, measure_id)
    if raw_value is None:
        note = "Required raw fields are unavailable for this component; conservative fallback applied."
        if coverage_flags.lag_blocked:
            note = "Snapshot exists but is blocked by reporting lag; conservative fallback applied."
        return OptimizerAlphaSubSignal(
            component_id=component_id,
            weight=component_weight,
            measure_id=typed_measure_id,
            higher_is_better=higher_is_better,
            normalized_score=config.conservative_fallback_score,
            available=False,
            fallback_applied=True,
            missing_fields=missing_fields,
            note=note,
        )

    return OptimizerAlphaSubSignal(
        component_id=component_id,
        weight=component_weight,
        measure_id=typed_measure_id,
        higher_is_better=higher_is_better,
        raw_value=round(raw_value, 8),
        normalized_score=0.0,
        available=True,
        fallback_applied=False,
        missing_fields=[],
    )


def _extract_raw_component_value(
    snapshot: OptimizerAlphaFundamentalSnapshot,
    component_id: OptimizerAlphaSignalId,
) -> tuple[OptimizerAlphaMeasureId | None, float | None, list[str]]:
    assets = snapshot.total_assets
    if assets is None or assets <= 0:
        return None, None, ["total_assets"]

    if component_id == "profitability":
        if snapshot.total_revenue is not None and snapshot.cost_of_revenue is not None:
            return "gross_profitability", (snapshot.total_revenue - snapshot.cost_of_revenue) / assets, []
        if snapshot.ebit is not None:
            missing = [] if snapshot.total_assets is not None else ["total_assets"]
            return "ebit_to_assets", snapshot.ebit / assets, missing
        return None, None, ["total_revenue", "cost_of_revenue", "ebit"]

    if component_id == "cash_generation":
        if snapshot.operating_cash_flow is not None:
            return "cfo_to_assets", snapshot.operating_cash_flow / assets, []
        if snapshot.free_cash_flow is not None:
            return "fcf_to_assets", snapshot.free_cash_flow / assets, []
        return None, None, ["operating_cash_flow", "free_cash_flow"]

    if component_id == "accrual_quality":
        if snapshot.net_income is not None and snapshot.operating_cash_flow is not None:
            return "accruals_to_assets", (snapshot.net_income - snapshot.operating_cash_flow) / assets, []
        return None, None, ["net_income", "operating_cash_flow"]

    if component_id == "leverage_discipline":
        if snapshot.total_debt is not None and snapshot.cash_and_equivalents is not None:
            return "net_leverage_to_assets", (snapshot.total_debt - snapshot.cash_and_equivalents) / assets, []
        return None, None, ["total_debt", "cash_and_equivalents"]

    return None, None, []


def _apply_cross_sectional_normalization(
    rows: list[OptimizerAlphaSecurityRow],
    component_values: dict[OptimizerAlphaSignalId, list[tuple[int, float]]],
    config: OptimizerAlphaPackageConfig,
) -> list[OptimizerAlphaSecurityRow]:
    updated_rows = list(rows)
    for component_id, indexed_values in component_values.items():
        raw_values = [value for _, value in indexed_values]
        lower = _quantile(raw_values, config.winsor_lower_quantile)
        upper = _quantile(raw_values, config.winsor_upper_quantile)
        winsorized_values = [min(max(value, lower), upper) for value in raw_values]
        mean_value = sum(winsorized_values) / len(winsorized_values) if winsorized_values else 0.0
        std_dev = _sample_std_dev(winsorized_values)
        for (row_index, raw_value), winsorized_value in zip(indexed_values, winsorized_values):
            zscore = 0.0 if std_dev <= 1e-12 else (winsorized_value - mean_value) / std_dev
            signal = next(item for item in updated_rows[row_index].sub_signals if item.component_id == component_id)
            normalized_score = zscore if signal.higher_is_better else -zscore
            normalized_score = max(-config.zscore_cap, min(config.zscore_cap, normalized_score))
            replacement = signal.model_copy(
                update={
                    "winsorized_value": round(winsorized_value, 8),
                    "normalized_score": round(normalized_score, 8),
                }
            )
            updated_rows[row_index] = _replace_signal(updated_rows[row_index], replacement)
    final_rows: list[OptimizerAlphaSecurityRow] = []
    for row in updated_rows:
        final_rows.append(
            row.model_copy(
                update={
                    "sub_signals": [
                        signal if signal.available else signal.model_copy(update={"normalized_score": config.conservative_fallback_score})
                        for signal in row.sub_signals
                    ]
                }
            )
        )
    return final_rows


def _replace_signal(row: OptimizerAlphaSecurityRow, replacement: OptimizerAlphaSubSignal) -> OptimizerAlphaSecurityRow:
    updated_signals = [replacement if item.component_id == replacement.component_id else item for item in row.sub_signals]
    return row.model_copy(update={"sub_signals": updated_signals})


def _quantile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return ordered[lower_index] + ((ordered[upper_index] - ordered[lower_index]) * fraction)


def _sample_std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    return sqrt(max(variance, 0.0))


def _build_alpha_package_id(
    *,
    rebalance_date: str,
    ordered_symbols: list[str],
    rows: list[OptimizerAlphaSecurityRow],
    metadata: OptimizerAlphaMetadata,
) -> str:
    digest = sha256()
    digest.update(ALPHA_PACKAGE_VERSION.encode("ascii"))
    digest.update(rebalance_date.encode("ascii"))
    for symbol in ordered_symbols:
        digest.update(symbol.encode("ascii"))
    digest.update(json.dumps([row.model_dump(mode="json") for row in rows], sort_keys=True).encode("utf-8"))
    digest.update(json.dumps(metadata.model_dump(mode="json"), sort_keys=True).encode("utf-8"))
    return f"aqv1_{digest.hexdigest()[:16]}"

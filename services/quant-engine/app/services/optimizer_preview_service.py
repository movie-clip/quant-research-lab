from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Literal

from app.analytics.risk import build_factor_registry
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.optimizer import (
    OptimizationRequest,
    OptimizerReturnBasisAttestation,
    OptimizerReturnBasisEvidenceBundle,
    OptimizerReturnBasisSectionTrust,
    OptimizerPreviewProvenance,
    OptimizerPreviewReplayHandoff,
    OptimizerPreviewRequest,
    OptimizerPreviewResponse,
    OptimizerPreviewSnapshotReference,
    OptimizerUniverseAsset,
    OptimizerWeight,
)
from app.services.optimizer_alpha_fundamentals import AlphaQualityPitIngestionService, AlphaQualityPitTrustGate
from app.services.optimizer_artifact_service import OptimizerHandoffStore
from app.services.market_data import (
    MarketDataService,
    build_histories_return_basis_evidence,
    build_history_return_basis_evidence,
    return_basis_contract_from_evidence,
    return_basis_path_trust_from_evidence,
)
from app.services.optimizer_service import assemble_optimizer_request_with_trusted_pit_alpha, run_optimizer


WORKFLOW_ID = "optimizer_preview_workflow_v1"


def build_optimizer_preview(
    request: OptimizerPreviewRequest,
    *,
    ingestion_service: AlphaQualityPitIngestionService | None = None,
    trust_gate: AlphaQualityPitTrustGate | None = None,
    handoff_store: OptimizerHandoffStore | None = None,
) -> OptimizerPreviewResponse:
    if request.benchmark.trust_status != "trusted":
        raise ValueError("benchmark preview input must be trusted")

    optimization_request = _build_optimization_request(request)
    return_basis_attestation = _build_return_basis_attestation(request)
    risk_input_status: Literal["not_requested", "provided", "required_but_missing", "invalid"] = _risk_input_status(request)
    alpha_input_status: Literal["not_requested", "trusted_pit_attached", "trusted_pit_degraded"] = "not_requested"
    if request.pit_alpha is not None:
        optimization_request = assemble_optimizer_request_with_trusted_pit_alpha(
            optimization_request,
            alpha_as_of_date=request.pit_alpha.as_of_date,
            ingestion_service=ingestion_service,
            trust_gate=trust_gate,
        )
        alpha_input_status = (
            "trusted_pit_attached"
            if optimization_request.alpha_package is not None and optimization_request.alpha_package.diagnostics.status == "ok"
            else "trusted_pit_degraded"
        )

    result = run_optimizer(optimization_request)
    if result.artifact is None:
        raise ValueError("optimizer preview artifact was not produced")

    snapshot_reference = _snapshot_reference(request.snapshot)
    handoff_reference = None
    persisted_benchmark_symbol = None
    if result.feasibility.status == "feasible":
        persisted_handoff = (handoff_store or OptimizerHandoffStore()).persist_handoff_record(
            artifact=result.artifact,
            snapshot_reference=snapshot_reference,
            benchmark=request.benchmark,
            return_basis_attestation=return_basis_attestation,
        )
        handoff_reference = persisted_handoff.reference
        persisted_benchmark_symbol = persisted_handoff.manifest.benchmark.benchmark_symbol
    return OptimizerPreviewResponse(
        optimizer_status=result.feasibility.status,
        provenance=OptimizerPreviewProvenance(
            snapshot_reference=snapshot_reference,
            benchmark_source_name=request.benchmark.source_name,
            benchmark_trust_status="trusted",
            return_basis_attestation=return_basis_attestation,
            risk_input_status=risk_input_status,
            alpha_input_status=alpha_input_status,
        ),
        persisted_handoff=handoff_reference,
        feasibility=result.feasibility,
        run_metadata=result.run_metadata,
        ex_ante_diagnostics=result.ex_ante_diagnostics,
        constraint_evaluations=result.constraint_evaluations,
        optimizer_artifact=result.artifact,
        replay_handoff=_build_replay_handoff(
            request,
            result,
            snapshot_reference,
            handoff_reference,
            persisted_benchmark_symbol,
        ),
    )


def _build_optimization_request(request: OptimizerPreviewRequest) -> OptimizationRequest:
    as_of_timestamp = _snapshot_timestamp(request.snapshot)
    current_weights = _snapshot_current_weights(request.snapshot)
    if not current_weights:
        raise ValueError("snapshot must include at least one positive market value position for optimizer preview")
    universe = request.universe or _build_default_universe(request.snapshot, request.benchmark.weights)
    if not universe:
        raise ValueError("optimizer preview universe must not be empty")

    return OptimizationRequest(
        request_id=request.request_id,
        as_of_timestamp=as_of_timestamp,
        effective_timestamp=as_of_timestamp,
        universe_id=request.universe_id or f"snapshot::{request.snapshot.statement.account_id or 'unknown'}::{as_of_timestamp}",
        benchmark_id=request.benchmark.benchmark_id,
        current_portfolio_weights=current_weights,
        benchmark_weights=request.benchmark.weights,
        universe=universe,
        hard_constraints=request.hard_constraints,
        penalties=request.penalties,
        risk_package=request.risk_package,
        alpha_package=None,
    )


def _build_return_basis_attestation(request: OptimizerPreviewRequest) -> OptimizerReturnBasisAttestation:
    market_data = MarketDataService()
    factor_proxy_symbols = sorted({item.us_proxy.upper() for item in build_factor_registry()})
    benchmark_symbol = (request.benchmark.benchmark_symbol or "").strip().upper()
    as_of_date = datetime.fromisoformat(request.benchmark.as_of_timestamp).date().isoformat()
    history_start_date = min(
        [position.as_of_date.isoformat() for position in request.snapshot.positions if position.as_of_date is not None] or [as_of_date]
    )
    history_end_date = as_of_date

    try:
        benchmark_rows = market_data.get_historical_prices(
            benchmark_symbol,
            history_start_date,
            history_end_date,
        )
    except Exception:  # noqa: BLE001
        benchmark_rows = []
    try:
        factor_histories = market_data.get_historical_prices_for_symbols(
            factor_proxy_symbols,
            history_start_date,
            history_end_date,
        )
    except Exception:  # noqa: BLE001
        factor_histories = {}

    benchmark_evidence = build_history_return_basis_evidence(benchmark_rows)
    factor_evidence = build_histories_return_basis_evidence(factor_histories)
    benchmark_path = return_basis_path_trust_from_evidence(benchmark_evidence)
    factor_evidence_trust = return_basis_path_trust_from_evidence(factor_evidence)
    factor_path = (
        "verified_adjusted_close"
        if benchmark_path == "verified_adjusted_close" and factor_evidence_trust == "verified_adjusted_close"
        else "degraded_unverified_return_basis"
        if benchmark_path != "unavailable" or factor_evidence_trust != "unavailable"
        else "unavailable"
    )

    return OptimizerReturnBasisAttestation(
        benchmark_symbol=benchmark_symbol,
        as_of_date=as_of_date,
        history_start_date=history_start_date,
        history_end_date=history_end_date,
        factor_proxy_symbols=factor_proxy_symbols,
        benchmark_return_basis_contract=return_basis_contract_from_evidence(benchmark_evidence),
        factor_return_basis_contract=return_basis_contract_from_evidence(factor_evidence),
        factor_basis_path=factor_path,
        section_trust=OptimizerReturnBasisSectionTrust(
            benchmark_relative_path=benchmark_path,
            factor_model_path=factor_path,
            risk_contribution_path=factor_path,
        ),
        evidence=OptimizerReturnBasisEvidenceBundle(
            benchmark_history=benchmark_evidence,
            factor_history=factor_evidence,
        ),
    )


def _snapshot_current_weights(snapshot: ImportedPortfolioSnapshot) -> list[OptimizerWeight]:
    positions = [position for position in snapshot.positions if position.symbol and position.market_value > 0]
    total_market_value = sum(position.market_value for position in positions)
    if total_market_value <= 0:
        return []
    raw_weights = [position.market_value / total_market_value for position in positions]
    rounded_weights = [round(weight, 8) for weight in raw_weights]
    rounding_gap = round(1.0 - sum(rounded_weights), 8)
    if rounded_weights:
        rounded_weights[-1] = round(rounded_weights[-1] + rounding_gap, 8)
    return [
        OptimizerWeight(symbol=position.symbol.upper(), weight=weight)
        for position, weight in zip(positions, rounded_weights)
    ]


def _build_default_universe(
    snapshot: ImportedPortfolioSnapshot,
    benchmark_weights: list[OptimizerWeight],
) -> list[OptimizerUniverseAsset]:
    sector_by_symbol: dict[str, str] = {}
    for position in snapshot.positions:
        symbol = position.symbol.upper()
        instrument = next((item for item in snapshot.instruments if item.symbol.upper() == symbol), None)
        if instrument is not None and instrument.instrument_type:
            continue
        sector = None
        if hasattr(position, "sector"):
            sector = getattr(position, "sector")
        if sector:
            sector_by_symbol[symbol] = sector

    symbols = sorted({position.symbol.upper() for position in snapshot.positions if position.market_value > 0} | {item.symbol.upper() for item in benchmark_weights})
    return [
        OptimizerUniverseAsset(
            symbol=symbol,
            eligible=True,
            taxonomy_labels={"sector": sector_by_symbol[symbol]} if symbol in sector_by_symbol else {},
        )
        for symbol in symbols
    ]


def _snapshot_reference(snapshot: ImportedPortfolioSnapshot) -> OptimizerPreviewSnapshotReference:
    imported_at = _to_iso(snapshot.statement.imported_at)
    source_files = [statement.source_path for statement in snapshot.statements] or [snapshot.statement.source_path]
    return OptimizerPreviewSnapshotReference(
        snapshot_id=_snapshot_id(snapshot),
        account_id=snapshot.statement.account_id,
        importer=snapshot.statement.importer,
        imported_at=imported_at,
        statement_period=snapshot.statement.statement_period,
        source_files=source_files,
    )


def _build_replay_handoff(
    request: OptimizerPreviewRequest,
    result,
    snapshot_reference: OptimizerPreviewSnapshotReference,
    handoff_reference,
    persisted_benchmark_symbol: str | None,
) -> OptimizerPreviewReplayHandoff | None:
    if result.feasibility.status != "feasible" or result.artifact is None or handoff_reference is None:
        return None
    return OptimizerPreviewReplayHandoff(
        source_artifact_id=result.artifact.artifact_id,
        source_portfolio_snapshot_id=snapshot_reference.snapshot_id,
        benchmark_id=request.benchmark.benchmark_id,
        benchmark_version=request.benchmark.benchmark_version,
        benchmark_symbol=persisted_benchmark_symbol,
        handoff_reference=handoff_reference,
        current_snapshot_reference=snapshot_reference,
    )


def _risk_input_status(request: OptimizerPreviewRequest) -> Literal["not_requested", "provided", "required_but_missing", "invalid"]:
    if request.hard_constraints.risk.max_active_risk is None:
        return "provided" if request.risk_package is not None else "not_requested"
    if request.risk_package is None:
        return "required_but_missing"
    if request.risk_package.diagnostics.status != "ok":
        return "invalid"
    return "provided"


def _snapshot_timestamp(snapshot: ImportedPortfolioSnapshot) -> str:
    return _to_iso(snapshot.statement.imported_at)


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat()


def _snapshot_id(snapshot: ImportedPortfolioSnapshot) -> str:
    payload = {
        "account_id": snapshot.statement.account_id,
        "importer": snapshot.statement.importer,
        "imported_at": _to_iso(snapshot.statement.imported_at),
        "statement_period": snapshot.statement.statement_period,
        "source_files": sorted([statement.source_path for statement in snapshot.statements] or [snapshot.statement.source_path]),
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()[:16]
    return f"portfolio_snapshot_{digest}"

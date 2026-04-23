from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.core.settings import get_settings
from app.schemas.optimizer import (
    OptimizationArtifact,
    OptimizationArtifactStateSummary,
    OptimizationBenchmarkRelativeAttestation,
    OptimizationInputFingerprint,
    OptimizationPackageStamp,
    OptimizationRequest,
    OptimizationResult,
    OptimizationTradeIntent,
    OptimizerHandoffBenchmarkReference,
    OptimizerHandoffConstraintSet,
    OptimizerHandoffManifest,
    OptimizerPersistedArtifactReference,
    OptimizerPreviewBenchmarkInput,
    OptimizerPreviewSnapshotReference,
    OptimizerReturnBasisAttestation,
    canonicalize_benchmark_symbol,
)
from app.schemas.return_basis import ReturnBasisPathTrust


REQUEST_FINGERPRINT_VERSION = "optimization_request_v1"
UNIVERSE_FINGERPRINT_VERSION = "optimizer_universe_v1"
BENCHMARK_FINGERPRINT_VERSION = "optimizer_benchmark_v1"
CONSTRAINT_FINGERPRINT_VERSION = "optimizer_constraints_v1"
SOLVER_FINGERPRINT_VERSION = "optimizer_solver_settings_v1"
ALPHA_PACKAGE_FINGERPRINT_VERSION = "optimizer_alpha_package_v1"
RISK_PACKAGE_FINGERPRINT_VERSION = "optimizer_risk_package_v1"
TRADE_EPSILON = 1e-8
HANDOFF_CONSTRAINT_SET_VERSION = "optimizer_constraint_set_v1"


class OptimizationArtifactPersistenceError(ValueError):
    pass


def _normalized_handoff_manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    attestation = payload.get("return_basis_attestation")
    if not isinstance(attestation, dict):
        return payload
    normalized_attestation = _normalized_return_basis_attestation_payload(attestation)
    if normalized_attestation == attestation:
        return payload
    normalized_payload = dict(payload)
    normalized_payload["return_basis_attestation"] = normalized_attestation
    return normalized_payload


def _normalized_handoff_manifest(manifest: OptimizerHandoffManifest) -> OptimizerHandoffManifest:
    normalized_attestation = normalize_optimizer_return_basis_attestation(manifest.return_basis_attestation)
    if normalized_attestation == manifest.return_basis_attestation:
        return manifest
    return manifest.model_copy(update={"return_basis_attestation": normalized_attestation})


def normalize_optimizer_return_basis_attestation(
    attestation: OptimizerReturnBasisAttestation,
) -> OptimizerReturnBasisAttestation:
    factor_basis_path: ReturnBasisPathTrust | None = attestation.factor_basis_path
    if factor_basis_path is None:
        factor_basis_path = _resolved_factor_basis_path_from_section_trust_values(
            attestation.section_trust.factor_model_path,
            attestation.section_trust.risk_contribution_path,
        )

    normalized_section_trust = attestation.section_trust.model_copy(
        update={
            "factor_model_path": factor_basis_path,
            "risk_contribution_path": factor_basis_path,
        }
    )
    if factor_basis_path == attestation.factor_basis_path and normalized_section_trust == attestation.section_trust:
        return attestation
    return attestation.model_copy(
        update={
            "factor_basis_path": factor_basis_path,
            "section_trust": normalized_section_trust,
        }
    )


def _normalized_return_basis_attestation_payload(attestation: dict[str, Any]) -> dict[str, Any]:
    factor_basis_path = attestation.get("factor_basis_path")
    if factor_basis_path is None:
        factor_basis_path = _resolved_factor_basis_path_from_section_trust_payload(attestation.get("section_trust"))
    elif not isinstance(factor_basis_path, str):
        return attestation

    if factor_basis_path is None:
        return attestation

    normalized_attestation = dict(attestation)
    normalized_attestation["factor_basis_path"] = factor_basis_path

    section_trust = attestation.get("section_trust")
    if isinstance(section_trust, dict):
        factor_model_path = section_trust.get("factor_model_path")
        risk_contribution_path = section_trust.get("risk_contribution_path")
        if isinstance(factor_model_path, str) and isinstance(risk_contribution_path, str):
            normalized_section_trust = dict(section_trust)
            normalized_section_trust["factor_model_path"] = factor_basis_path
            normalized_section_trust["risk_contribution_path"] = factor_basis_path
            normalized_attestation["section_trust"] = normalized_section_trust

    return normalized_attestation


def _resolved_factor_basis_path_from_section_trust_payload(section_trust: Any) -> ReturnBasisPathTrust | None:
    if not isinstance(section_trust, dict):
        return None
    factor_model_path = section_trust.get("factor_model_path")
    risk_contribution_path = section_trust.get("risk_contribution_path")
    if not isinstance(factor_model_path, str) and not isinstance(risk_contribution_path, str):
        return None
    return _resolved_factor_basis_path_from_section_trust_values(factor_model_path, risk_contribution_path)


def _resolved_factor_basis_path_from_section_trust_values(
    factor_model_path: str | None,
    risk_contribution_path: str | None,
) -> ReturnBasisPathTrust:
    factor_paths = [factor_model_path, risk_contribution_path]
    if "unavailable" in factor_paths:
        return "unavailable"
    if "degraded_unverified_return_basis" in factor_paths:
        return "degraded_unverified_return_basis"
    return "verified_adjusted_close"


@dataclass(frozen=True)
class PersistedOptimizerHandoff:
    manifest: OptimizerHandoffManifest
    artifact: OptimizationArtifact


@dataclass(frozen=True)
class PersistedOptimizerHandoffRecord:
    reference: OptimizerPersistedArtifactReference
    manifest: OptimizerHandoffManifest


@dataclass(frozen=True)
class RawPersistedOptimizerHandoff:
    manifest_path: Path
    artifact_path: Path
    manifest_payload: dict[str, Any]
    artifact_payload: dict[str, Any]


@dataclass(frozen=True)
class CanonicalOptimizerHandoffPaths:
    manifest_path: Path
    artifact_path: Path


class OptimizerHandoffStore:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.optimizer_handoff_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def handoff_dir(self, handoff_id: str) -> Path:
        return self.base_dir / handoff_id

    def manifest_path(self, handoff_id: str) -> Path:
        return self.handoff_dir(handoff_id) / "manifest.json"

    def artifact_path(self, handoff_id: str) -> Path:
        return self.handoff_dir(handoff_id) / "artifact.json"

    def canonical_paths(self, handoff_id: str) -> CanonicalOptimizerHandoffPaths:
        return CanonicalOptimizerHandoffPaths(
            manifest_path=self.manifest_path(handoff_id),
            artifact_path=self.artifact_path(handoff_id),
        )

    def guarded_canonical_paths(self, reference: OptimizerPersistedArtifactReference) -> CanonicalOptimizerHandoffPaths:
        canonical_paths = self.canonical_paths(reference.handoff_id)
        if reference.manifest_path != str(canonical_paths.manifest_path):
            raise OptimizationArtifactPersistenceError("handoff reference manifest_path is not the canonical persisted path")
        if reference.artifact_path != str(canonical_paths.artifact_path):
            raise OptimizationArtifactPersistenceError("handoff reference artifact_path is not the canonical persisted path")
        return canonical_paths

    def persist_handoff(
        self,
        *,
        artifact: OptimizationArtifact,
        snapshot_reference: OptimizerPreviewSnapshotReference,
        benchmark: OptimizerPreviewBenchmarkInput,
        return_basis_attestation: OptimizerReturnBasisAttestation,
    ) -> OptimizerPersistedArtifactReference:
        return self.persist_handoff_record(
            artifact=artifact,
            snapshot_reference=snapshot_reference,
            benchmark=benchmark,
            return_basis_attestation=return_basis_attestation,
        ).reference

    def persist_handoff_record(
        self,
        *,
        artifact: OptimizationArtifact,
        snapshot_reference: OptimizerPreviewSnapshotReference,
        benchmark: OptimizerPreviewBenchmarkInput,
        return_basis_attestation: OptimizerReturnBasisAttestation,
    ) -> PersistedOptimizerHandoffRecord:
        validated_artifact = validate_optimization_artifact(artifact)
        manifest = build_optimizer_handoff_manifest(
            artifact=validated_artifact,
            snapshot_reference=snapshot_reference,
            benchmark=benchmark,
            return_basis_attestation=return_basis_attestation,
        )
        canonical_paths = self.canonical_paths(manifest.handoff_id)
        handoff_dir = canonical_paths.manifest_path.parent
        handoff_dir.mkdir(parents=True, exist_ok=True)
        self._write_once(canonical_paths.manifest_path, manifest.model_dump(mode="json"))
        self._write_once(canonical_paths.artifact_path, validated_artifact.model_dump(mode="json"))
        return PersistedOptimizerHandoffRecord(
            reference=OptimizerPersistedArtifactReference(
                handoff_id=manifest.handoff_id,
                artifact_id=validated_artifact.artifact_id,
                manifest_path=str(canonical_paths.manifest_path),
                artifact_path=str(canonical_paths.artifact_path),
            ),
            manifest=manifest,
        )

    def load_handoff(self, reference: OptimizerPersistedArtifactReference) -> PersistedOptimizerHandoff:
        raw = self.load_raw_handoff(reference)
        manifest_path = raw.manifest_path
        artifact_path = raw.artifact_path
        manifest = OptimizerHandoffManifest.model_validate(raw.manifest_payload)
        artifact = OptimizationArtifact.model_validate(raw.artifact_payload)
        manifest = validate_optimizer_handoff_manifest(manifest, artifact)
        if reference.handoff_id != manifest.handoff_id:
            raise OptimizationArtifactPersistenceError("handoff reference does not match persisted manifest handoff_id")
        if reference.artifact_id != artifact.artifact_id:
            raise OptimizationArtifactPersistenceError("handoff reference does not match persisted artifact artifact_id")
        if manifest_path != self.manifest_path(reference.handoff_id):
            raise OptimizationArtifactPersistenceError("handoff reference manifest_path is not the canonical persisted path")
        if artifact_path != self.artifact_path(reference.handoff_id):
            raise OptimizationArtifactPersistenceError("handoff reference artifact_path is not the canonical persisted path")
        return PersistedOptimizerHandoff(manifest=manifest, artifact=artifact)

    def load_raw_handoff(self, reference: OptimizerPersistedArtifactReference) -> RawPersistedOptimizerHandoff:
        canonical_paths = self.guarded_canonical_paths(reference)
        manifest_payload = _normalized_handoff_manifest_payload(_read_json_object(canonical_paths.manifest_path))
        artifact_payload = _read_json_object(canonical_paths.artifact_path)
        return RawPersistedOptimizerHandoff(
            manifest_path=canonical_paths.manifest_path,
            artifact_path=canonical_paths.artifact_path,
            manifest_payload=manifest_payload,
            artifact_payload=artifact_payload,
        )

    def _write_once(self, path: Path, payload: object) -> None:
        serialized = _canonical_json(payload)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != serialized:
                raise OptimizationArtifactPersistenceError(f"immutable handoff conflict at {path}")
            return
        path.write_text(serialized, encoding="utf-8")


class InMemoryOptimizationArtifactStore:
    def __init__(self) -> None:
        self._payload_by_id: dict[str, str] = {}

    def save(self, artifact: OptimizationArtifact) -> str:
        payload = serialize_optimization_artifact(artifact)
        self._payload_by_id[artifact.artifact_id] = payload
        return artifact.artifact_id

    def load(self, artifact_id: str) -> OptimizationArtifact | None:
        payload = self._payload_by_id.get(artifact_id)
        if payload is None:
            return None
        return deserialize_optimization_artifact(payload)

    def ids(self) -> list[str]:
        return sorted(self._payload_by_id)


def build_optimization_artifact(request: OptimizationRequest, result: OptimizationResult) -> OptimizationArtifact:
    artifact = OptimizationArtifact(
        artifact_id="pending",
        request_id=result.request_id,
        as_of_timestamp=request.as_of_timestamp,
        effective_timestamp=request.effective_timestamp,
        universe_id=request.universe_id,
        benchmark_id=request.benchmark_id,
        input_fingerprints=_build_input_fingerprints(request, result),
        package_stamps=_build_package_stamps(request),
        artifact_state=_build_artifact_state(request, result),
        objective=result.objective,
        hard_constraints=result.hard_constraints,
        penalties=result.penalties,
        run_metadata=result.run_metadata,
        feasibility=result.feasibility,
        benchmark_relative_attestations=_build_benchmark_relative_attestations(request, result),
        key_diagnostics=result.ex_ante_diagnostics,
        constraint_evaluations=result.constraint_evaluations,
        proposed_weights=result.proposed_weights,
        active_weights=result.active_weights,
        trade_intents=_build_trade_intents(result),
        failure_reasons=result.feasibility.issues,
        replay=result.replay,
    )
    artifact_id = _fingerprint(artifact.model_dump(mode="json", exclude={"artifact_id"}))
    return artifact.model_copy(update={"artifact_id": f"opt_artifact_{artifact_id[:16]}"})


def build_optimizer_handoff_manifest(
    *,
    artifact: OptimizationArtifact,
    snapshot_reference: OptimizerPreviewSnapshotReference,
    benchmark: OptimizerPreviewBenchmarkInput,
    return_basis_attestation: OptimizerReturnBasisAttestation,
) -> OptimizerHandoffManifest:
    validated_artifact = validate_optimization_artifact(artifact)
    benchmark_symbol = _validated_handoff_benchmark_symbol(benchmark.benchmark_symbol)
    handoff_id = _handoff_id_for_payload(validated_artifact, return_basis_attestation)
    manifest = OptimizerHandoffManifest(
        handoff_id=handoff_id,
        artifact_id=validated_artifact.artifact_id,
        artifact_schema_version=validated_artifact.schema_version,
        artifact_as_of_timestamp=validated_artifact.as_of_timestamp,
        artifact_effective_timestamp=validated_artifact.effective_timestamp,
        source_portfolio_snapshot=snapshot_reference,
        benchmark=OptimizerHandoffBenchmarkReference(
            benchmark_id=benchmark.benchmark_id,
            benchmark_version=benchmark.benchmark_version,
            benchmark_symbol=benchmark_symbol,
            source_name=benchmark.source_name,
            as_of_timestamp=benchmark.as_of_timestamp,
        ),
        return_basis_attestation=return_basis_attestation,
        optimizer_input_provenance=validated_artifact.input_fingerprints,
        constraint_set=OptimizerHandoffConstraintSet(
            constraint_set_version=HANDOFF_CONSTRAINT_SET_VERSION,
            constraint_set_fingerprint=_constraint_set_fingerprint(validated_artifact),
            hard_constraint_count=_hard_constraint_count(validated_artifact),
            penalty_count=len(validated_artifact.penalties),
            package_versions={stamp.package_name: stamp.package_version for stamp in validated_artifact.package_stamps},
        ),
        package_stamps=validated_artifact.package_stamps,
        optimizer_output_target_weights=validated_artifact.proposed_weights,
        artifact_state=validated_artifact.artifact_state.artifact_state,
    )
    return validate_optimizer_handoff_manifest(manifest, validated_artifact)


def serialize_optimization_artifact(artifact: OptimizationArtifact) -> str:
    return _canonical_json(artifact.model_dump(mode="json"))


def deserialize_optimization_artifact(payload: str) -> OptimizationArtifact:
    return OptimizationArtifact.model_validate_json(payload)


def load_optimizer_handoff_by_reference(
    reference: OptimizerPersistedArtifactReference,
    *,
    store: OptimizerHandoffStore | None = None,
) -> PersistedOptimizerHandoff:
    return (store or OptimizerHandoffStore()).load_handoff(reference)


def load_raw_optimizer_handoff_by_reference(
    reference: OptimizerPersistedArtifactReference,
    *,
    store: OptimizerHandoffStore | None = None,
) -> RawPersistedOptimizerHandoff:
    return (store or OptimizerHandoffStore()).load_raw_handoff(reference)


def replay_optimization_result_from_artifact(artifact: OptimizationArtifact) -> OptimizationResult:
    validated_artifact = validate_optimization_artifact(artifact)
    return OptimizationResult(
        request_id=validated_artifact.request_id,
        objective=validated_artifact.objective,
        hard_constraints=validated_artifact.hard_constraints,
        penalties=validated_artifact.penalties,
        proposed_weights=validated_artifact.proposed_weights,
        active_weights=validated_artifact.active_weights,
        feasibility=validated_artifact.feasibility,
        constraint_evaluations=validated_artifact.constraint_evaluations,
        ex_ante_diagnostics=validated_artifact.key_diagnostics,
        run_metadata=validated_artifact.run_metadata,
        replay=validated_artifact.replay,
        artifact=validated_artifact,
    )


def validate_optimization_artifact(artifact: OptimizationArtifact) -> OptimizationArtifact:
    if artifact.schema_version != "optimizer_artifact_v1":
        raise OptimizationArtifactPersistenceError("unsupported optimizer artifact schema_version")
    required_input_kinds = {"request", "universe", "benchmark", "constraints", "solver"}
    seen_input_kinds: set[str] = set()
    for fingerprint in artifact.input_fingerprints:
        if fingerprint.input_kind in seen_input_kinds:
            raise OptimizationArtifactPersistenceError("optimizer artifact contains ambiguous duplicate input fingerprints")
        seen_input_kinds.add(fingerprint.input_kind)
        if not fingerprint.version or not fingerprint.fingerprint or not fingerprint.provenance:
            raise OptimizationArtifactPersistenceError("optimizer artifact contains incomplete input provenance")
    if required_input_kinds - seen_input_kinds:
        raise OptimizationArtifactPersistenceError("optimizer artifact is missing required input provenance")
    if not artifact.artifact_id.startswith("opt_artifact_"):
        raise OptimizationArtifactPersistenceError("optimizer artifact_id must use the stable opt_artifact_ prefix")
    expected_artifact_id = _canonical_artifact_id(artifact)
    if artifact.artifact_id != expected_artifact_id:
        raise OptimizationArtifactPersistenceError("optimizer artifact_id does not match canonical artifact content")
    if artifact.feasibility.status == "feasible":
        if not artifact.proposed_weights:
            raise OptimizationArtifactPersistenceError("feasible optimizer artifact requires proposed_weights")
        if artifact.proposed_weights != artifact.replay.target_weights:
            raise OptimizationArtifactPersistenceError("optimizer artifact replay target_weights must match proposed_weights")
    if not artifact.run_metadata.deterministic_symbol_order:
        raise OptimizationArtifactPersistenceError("optimizer artifact requires deterministic_symbol_order")
    return artifact


def validate_optimizer_handoff_manifest(
    manifest: OptimizerHandoffManifest,
    artifact: OptimizationArtifact,
) -> OptimizerHandoffManifest:
    manifest = _normalized_handoff_manifest(manifest)
    validate_optimization_artifact(artifact)
    if manifest.schema_version != "optimizer_handoff_manifest_v1":
        raise OptimizationArtifactPersistenceError("unsupported optimizer handoff manifest schema_version")
    if manifest.artifact_id != artifact.artifact_id:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest artifact_id does not match artifact")
    if manifest.artifact_schema_version != artifact.schema_version:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest artifact_schema_version does not match artifact")
    if manifest.artifact_as_of_timestamp != artifact.as_of_timestamp:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest artifact_as_of_timestamp does not match artifact")
    if manifest.artifact_effective_timestamp != artifact.effective_timestamp:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest artifact_effective_timestamp does not match artifact")
    _validated_handoff_benchmark_symbol(manifest.benchmark.benchmark_symbol)
    if not manifest.return_basis_attestation.history_start_date or not manifest.return_basis_attestation.history_end_date:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest requires persisted return_basis_attestation history window metadata")
    if manifest.return_basis_attestation.benchmark_symbol != manifest.benchmark.benchmark_symbol:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest return_basis_attestation benchmark_symbol does not match manifest benchmark")
    if manifest.handoff_id != _handoff_id_for_payload(artifact, manifest.return_basis_attestation):
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest handoff_id does not match artifact")
    if manifest.optimizer_input_provenance != artifact.input_fingerprints:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest optimizer_input_provenance does not match artifact")
    if manifest.package_stamps != artifact.package_stamps:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest package_stamps do not match artifact")
    if manifest.optimizer_output_target_weights != artifact.proposed_weights:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest optimizer_output_target_weights do not match artifact")
    if manifest.artifact_state != artifact.artifact_state.artifact_state:
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest artifact_state does not match artifact")
    if manifest.replay_consumption_mode != "explicit_reference_only":
        raise OptimizationArtifactPersistenceError("optimizer handoff manifest must require explicit_reference_only consumption")
    return manifest


def replay_optimization_result_from_artifact_unchecked(artifact: OptimizationArtifact) -> OptimizationResult:
    return OptimizationResult(
        request_id=artifact.request_id,
        objective=artifact.objective,
        hard_constraints=artifact.hard_constraints,
        penalties=artifact.penalties,
        proposed_weights=artifact.proposed_weights,
        active_weights=artifact.active_weights,
        feasibility=artifact.feasibility,
        constraint_evaluations=artifact.constraint_evaluations,
        ex_ante_diagnostics=artifact.key_diagnostics,
        run_metadata=artifact.run_metadata,
        replay=artifact.replay,
        artifact=artifact,
    )


def _canonical_artifact_id(artifact: OptimizationArtifact) -> str:
    payload = artifact.model_dump(mode="json", exclude={"artifact_id"})
    return f"opt_artifact_{_fingerprint(payload)[:16]}"


def _handoff_id_for_artifact(artifact: OptimizationArtifact) -> str:
    return f"optimizer_handoff_{artifact.artifact_id.removeprefix('opt_artifact_')}"


def _handoff_id_for_payload(
    artifact: OptimizationArtifact,
    return_basis_attestation: OptimizerReturnBasisAttestation,
) -> str:
    normalized_attestation = normalize_optimizer_return_basis_attestation(return_basis_attestation)
    digest = _fingerprint(
        {
            "artifact_id": artifact.artifact_id,
            "return_basis_attestation": normalized_attestation.model_dump(mode="json"),
        }
    )
    return f"optimizer_handoff_{digest[:16]}"


def _constraint_set_fingerprint(artifact: OptimizationArtifact) -> str:
    return _fingerprint(
        {
            "objective": artifact.objective.model_dump(mode="json"),
            "hard_constraints": artifact.hard_constraints.model_dump(mode="json"),
            "penalties": [penalty.model_dump(mode="json") for penalty in artifact.penalties],
            "package_versions": {stamp.package_name: stamp.package_version for stamp in artifact.package_stamps},
        }
    )


def _hard_constraint_count(artifact: OptimizationArtifact) -> int:
    count = 4
    if artifact.hard_constraints.position_limits.default_max_weight is not None:
        count += 1
    if artifact.hard_constraints.turnover.max_turnover is not None:
        count += 1
    if artifact.hard_constraints.risk.max_active_risk is not None:
        count += 1
    count += len(artifact.hard_constraints.active_group_exposures)
    return count


def _build_input_fingerprints(request: OptimizationRequest, result: OptimizationResult) -> list[OptimizationInputFingerprint]:
    fingerprints = [
        OptimizationInputFingerprint(
            input_kind="request",
            version=REQUEST_FINGERPRINT_VERSION,
            fingerprint=_fingerprint(
                {
                    "request_id": request.request_id,
                    "as_of_timestamp": request.as_of_timestamp,
                    "effective_timestamp": request.effective_timestamp,
                    "current_portfolio_weights": _weights_payload(request.current_portfolio_weights),
                }
            ),
            provenance="optimization_request_payload",
            as_of_timestamp=request.as_of_timestamp,
            effective_timestamp=request.effective_timestamp,
        ),
        OptimizationInputFingerprint(
            input_kind="universe",
            version=UNIVERSE_FINGERPRINT_VERSION,
            fingerprint=_fingerprint(
                [
                    {
                        "symbol": asset.symbol.upper(),
                        "eligible": asset.eligible,
                        "min_weight": asset.min_weight,
                        "max_weight": asset.max_weight,
                        "taxonomy_labels": dict(sorted((key, value) for key, value in asset.taxonomy_labels.items())),
                    }
                    for asset in sorted(request.universe, key=lambda item: item.symbol.upper())
                ]
            ),
            provenance="optimizer_universe_contract",
            as_of_timestamp=request.as_of_timestamp,
            effective_timestamp=request.effective_timestamp,
        ),
        OptimizationInputFingerprint(
            input_kind="benchmark",
            version=BENCHMARK_FINGERPRINT_VERSION,
            fingerprint=_fingerprint(_weights_payload(request.benchmark_weights)),
            provenance="optimizer_benchmark_weights",
            as_of_timestamp=request.as_of_timestamp,
            effective_timestamp=request.effective_timestamp,
        ),
        OptimizationInputFingerprint(
            input_kind="constraints",
            version=CONSTRAINT_FINGERPRINT_VERSION,
            fingerprint=_fingerprint(
                {
                    "objective": request.objective.model_dump(mode="json"),
                    "hard_constraints": request.hard_constraints.model_dump(mode="json"),
                    "penalties": [penalty.model_dump(mode="json") for penalty in request.penalties],
                }
            ),
            provenance="optimizer_constraints_payload",
            as_of_timestamp=request.as_of_timestamp,
            effective_timestamp=request.effective_timestamp,
        ),
        OptimizationInputFingerprint(
            input_kind="solver",
            version=SOLVER_FINGERPRINT_VERSION,
            fingerprint=_fingerprint(
                {
                    "engine_id": result.run_metadata.engine_id,
                    "methodology_id": result.run_metadata.methodology_id,
                    "solver_id": result.run_metadata.solver_id,
                    "tolerance": result.run_metadata.tolerance,
                    "max_iterations": result.run_metadata.max_iterations,
                }
            ),
            provenance="optimizer_solver_settings",
            as_of_timestamp=request.as_of_timestamp,
            effective_timestamp=request.effective_timestamp,
        ),
    ]

    if request.alpha_package is not None:
        fingerprints.append(
            OptimizationInputFingerprint(
                input_kind="alpha_package",
                version=ALPHA_PACKAGE_FINGERPRINT_VERSION,
                fingerprint=_fingerprint(request.alpha_package.model_dump(mode="json")),
                provenance=request.alpha_package.metadata.input_descriptor.source_name,
                as_of_timestamp=request.alpha_package.metadata.input_descriptor.as_of_date,
                effective_timestamp=request.alpha_package.rebalance_date,
            )
        )
    if request.risk_package is not None:
        fingerprints.append(
            OptimizationInputFingerprint(
                input_kind="risk_package",
                version=RISK_PACKAGE_FINGERPRINT_VERSION,
                fingerprint=_fingerprint(request.risk_package.model_dump(mode="json")),
                provenance="optimizer_risk_package_builder",
                as_of_timestamp=request.risk_package.rebalance_date,
                effective_timestamp=request.risk_package.rebalance_date,
            )
        )
    return fingerprints


def _build_package_stamps(request: OptimizationRequest) -> list[OptimizationPackageStamp]:
    package_stamps = [
        OptimizationPackageStamp(
            package_name="constraint_package",
            package_version="optimizer_constraints_v1",
            package_status="configured",
            provenance="optimizer_request_constraints",
            as_of_timestamp=request.as_of_timestamp,
            effective_timestamp=request.effective_timestamp,
        ),
        OptimizationPackageStamp(
            package_name="solver_package",
            package_version="deterministic_projected_dykstra_v1",
            package_status="configured",
            provenance="optimizer_service_solver",
            as_of_timestamp=request.as_of_timestamp,
            effective_timestamp=request.effective_timestamp,
        ),
    ]
    if request.alpha_package is not None:
        package_stamps.append(
            OptimizationPackageStamp(
                package_name="alpha_package",
                package_id=request.alpha_package.package_id,
                package_version=request.alpha_package.version,
                package_status=request.alpha_package.diagnostics.status,
                provenance=request.alpha_package.metadata.input_descriptor.source_name,
                as_of_timestamp=request.alpha_package.metadata.input_descriptor.as_of_date,
                effective_timestamp=request.alpha_package.rebalance_date,
            )
        )
    if request.risk_package is not None:
        package_stamps.append(
            OptimizationPackageStamp(
                package_name="risk_package",
                package_id=request.risk_package.package_id,
                package_version=request.risk_package.version,
                package_status=request.risk_package.diagnostics.status,
                provenance="optimizer_risk_package_builder",
                as_of_timestamp=request.risk_package.rebalance_date,
                effective_timestamp=request.risk_package.rebalance_date,
            )
        )
    return package_stamps


def _build_artifact_state(request: OptimizationRequest, result: OptimizationResult) -> OptimizationArtifactStateSummary:
    stale_inputs: list[str] = []
    degraded_inputs: list[str] = []
    reasons: list[str] = []

    if request.alpha_package is not None:
        if request.alpha_package.diagnostics.stale_symbols:
            stale_inputs.append("alpha_package")
            reasons.append(
                f"alpha_package_stale:{','.join(sorted(request.alpha_package.diagnostics.stale_symbols))}"
            )
        if request.alpha_package.diagnostics.lag_blocked_symbols:
            degraded_inputs.append("alpha_package")
            reasons.append(
                f"alpha_package_lag_blocked:{','.join(sorted(request.alpha_package.diagnostics.lag_blocked_symbols))}"
            )
        if request.alpha_package.diagnostics.fallback_symbols:
            degraded_inputs.append("alpha_package")
            reasons.append(
                f"alpha_package_fallback:{','.join(sorted(request.alpha_package.diagnostics.fallback_symbols))}"
            )
        if request.alpha_package.diagnostics.missing_snapshot_symbols:
            degraded_inputs.append("alpha_package")
            reasons.append(
                f"alpha_package_missing_snapshot:{','.join(sorted(request.alpha_package.diagnostics.missing_snapshot_symbols))}"
            )

    if request.risk_package is not None:
        if request.risk_package.diagnostics.stale_symbols:
            stale_inputs.append("risk_package")
            reasons.append(f"risk_package_stale:{','.join(sorted(request.risk_package.diagnostics.stale_symbols))}")
        if request.risk_package.diagnostics.missing_symbols or request.risk_package.diagnostics.low_observation_symbols:
            degraded_inputs.append("risk_package")
            symbols = sorted(set(request.risk_package.diagnostics.missing_symbols + request.risk_package.diagnostics.low_observation_symbols))
            reasons.append(f"risk_package_degraded:{','.join(symbols)}")

    for issue in result.feasibility.issues:
        reasons.append(issue.code)

    normalized_stale_inputs = sorted(set(stale_inputs))
    normalized_degraded_inputs = sorted(set(degraded_inputs))
    normalized_reasons = list(dict.fromkeys(reasons))
    if result.feasibility.status == "rejected":
        artifact_state = "rejected"
    elif result.feasibility.status == "infeasible":
        artifact_state = "infeasible"
    elif normalized_stale_inputs:
        artifact_state = "stale"
    elif normalized_degraded_inputs:
        artifact_state = "degraded"
    else:
        artifact_state = "complete"

    return OptimizationArtifactStateSummary(
        artifact_state=artifact_state,
        feasibility_status=result.feasibility.status,
        stale_inputs=normalized_stale_inputs,
        degraded_inputs=normalized_degraded_inputs,
        reasons=normalized_reasons,
    )


def _build_benchmark_relative_attestations(
    request: OptimizationRequest,
    result: OptimizationResult,
) -> list[OptimizationBenchmarkRelativeAttestation]:
    attestations: list[OptimizationBenchmarkRelativeAttestation] = []
    for evaluation in result.constraint_evaluations:
        if evaluation.constraint_id == "benchmark_relative_max_abs_active_weight":
            attestations.append(
                OptimizationBenchmarkRelativeAttestation(
                    attestation_id="benchmark_relative_max_abs_active_weight",
                    attestation_type="max_abs_active_weight",
                    constraint_id=evaluation.constraint_id,
                    benchmark_id=request.benchmark_id,
                    status=evaluation.status,
                    actual_value=evaluation.actual_value,
                    limit_value=evaluation.limit_value,
                    slack=evaluation.slack,
                    binding_symbols=evaluation.binding_symbols,
                    details={"benchmark_relative": True},
                    message=evaluation.message,
                )
            )
        if evaluation.constraint_id.startswith("active_group_exposure_"):
            attestations.append(
                OptimizationBenchmarkRelativeAttestation(
                    attestation_id=evaluation.constraint_id,
                    attestation_type="active_group_exposure",
                    constraint_id=evaluation.constraint_id,
                    benchmark_id=request.benchmark_id,
                    status=evaluation.status,
                    actual_value=evaluation.actual_value,
                    limit_value=evaluation.limit_value,
                    slack=evaluation.slack,
                    binding_symbols=evaluation.binding_symbols,
                    details={"benchmark_relative": True},
                    message=evaluation.message,
                )
            )

    if request.risk_package is None:
        attestations.append(
            OptimizationBenchmarkRelativeAttestation(
                attestation_id="benchmark_alignment",
                attestation_type="benchmark_alignment",
                constraint_id="benchmark_alignment",
                benchmark_id=request.benchmark_id,
                status="not_applicable",
                message="No risk package provided, so benchmark-alignment attestation is not applicable.",
            )
        )
    else:
        aligned = request.risk_package.benchmark_alignment.aligned
        coverage = request.risk_package.benchmark_alignment.benchmark_weight_coverage
        attestations.append(
            OptimizationBenchmarkRelativeAttestation(
                attestation_id="benchmark_alignment",
                attestation_type="benchmark_alignment",
                constraint_id="benchmark_alignment",
                benchmark_id=request.benchmark_id,
                status="aligned" if aligned else "misaligned",
                actual_value=coverage,
                limit_value=1.0,
                slack=round(1.0 - coverage, 8),
                binding_symbols=request.risk_package.benchmark_alignment.benchmark_symbols_missing_from_package,
                details={"aligned": aligned},
                message="Risk package benchmark alignment remains machine-checkable against the optimizer benchmark.",
            )
        )
    return attestations


def _build_trade_intents(result: OptimizationResult) -> list[OptimizationTradeIntent]:
    current_map = {item.symbol.upper(): item.weight for item in result.replay.current_weights}
    active_map = {item.symbol.upper(): item.weight for item in result.active_weights}
    trade_intents: list[OptimizationTradeIntent] = []
    for proposed in result.proposed_weights:
        symbol = proposed.symbol.upper()
        current_weight = current_map.get(symbol, 0.0)
        trade_weight = round(proposed.weight - current_weight, 8)
        action = "hold"
        if proposed.weight <= TRADE_EPSILON and current_weight > TRADE_EPSILON:
            action = "exit"
        elif current_weight <= TRADE_EPSILON and proposed.weight > TRADE_EPSILON:
            action = "initiate"
        elif trade_weight > TRADE_EPSILON:
            action = "buy"
        elif trade_weight < -TRADE_EPSILON:
            action = "sell"
        trade_intents.append(
            OptimizationTradeIntent(
                symbol=symbol,
                action=action,
                current_weight=round(current_weight, 8),
                proposed_weight=proposed.weight,
                active_weight=round(active_map.get(symbol, 0.0), 8),
                trade_weight=trade_weight,
            )
        )
    return trade_intents


def _weights_payload(weights: list) -> list[dict[str, float | str]]:
    return [
        {"symbol": item.symbol.upper(), "weight": item.weight}
        for item in sorted(weights, key=lambda row: row.symbol.upper())
    ]


def _fingerprint(payload: object) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OptimizationArtifactPersistenceError(f"missing persisted handoff file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise OptimizationArtifactPersistenceError(f"invalid persisted handoff json: {path}") from exc
    if not isinstance(payload, dict):
        raise OptimizationArtifactPersistenceError(f"persisted handoff payload must be a json object: {path}")
    return payload


def _validated_handoff_benchmark_symbol(value: str | None) -> str:
    normalized = canonicalize_benchmark_symbol(value)
    if normalized is None:
        raise OptimizationArtifactPersistenceError(
            "optimizer handoff manifest requires a non-blank benchmark_symbol"
        )
    return normalized

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from pydantic import ValidationError

from app.schemas.backtest_engine import (
    OptimizerHandoffReplayEffectiveParams,
    OptimizerHandoffEligibleReplayWindow,
    OptimizerHandoffReplayAnalyticsFamily,
    OptimizerHandoffReplayHandoff,
    OptimizerHandoffReplayOutputPolicy,
    OptimizerHandoffValidationEvaluation,
    OptimizerHandoffValidationPhase,
    OptimizerHandoffValidationProvenance,
    OptimizerHandoffValidationReasonFamily,
    OptimizerHandoffValidationRequest,
    OptimizerHandoffValidationResponse,
)
from app.schemas.optimizer import (
    OptimizationArtifact,
    OptimizerHandoffManifest,
    OptimizerReturnBasisAttestation,
    canonicalize_benchmark_symbol,
)
from app.services.optimizer_artifact_service import (
    OptimizationArtifactPersistenceError,
    PersistedOptimizerHandoff,
    RawPersistedOptimizerHandoff,
    load_raw_optimizer_handoff_by_reference,
    normalize_optimizer_return_basis_attestation,
    validate_optimizer_handoff_manifest,
)


ALLOWED_REPLAY_ARTIFACT_STATES = {"complete", "degraded", "stale"}
BENCHMARK_RELATIVE_MAX_ABS_ACTIVE_WEIGHT_ID = "benchmark_relative_max_abs_active_weight"
BENCHMARK_ALIGNMENT_ATTESTATION_ID = "benchmark_alignment"
BENCHMARK_RELATIVE_PHASE: OptimizerHandoffValidationPhase = "benchmark_relative_checks"
RAW_PAYLOAD_PHASE: OptimizerHandoffValidationPhase = "raw_persisted_payload"
MODEL_VALIDATION_PHASE: OptimizerHandoffValidationPhase = "model_validation"
CROSS_FILE_PHASE: OptimizerHandoffValidationPhase = "cross_file_invariants"
TRUTH_SEPARATION_PHASE: OptimizerHandoffValidationPhase = "truth_separation_checks"

BENCHMARK_RELATIVE_VOLATILITY_OUTPUTS: Final[OptimizerHandoffReplayAnalyticsFamily] = "benchmark_relative_volatility_outputs"
FACTOR_EXPOSURE_OUTPUTS: Final[OptimizerHandoffReplayAnalyticsFamily] = "factor_exposure_outputs"
STRESS_SCENARIO_OUTPUTS: Final[OptimizerHandoffReplayAnalyticsFamily] = "stress_scenario_outputs"
RISK_CONTRIBUTION_OUTPUTS: Final[OptimizerHandoffReplayAnalyticsFamily] = "risk_contribution_outputs"
CONCENTRATION_OUTPUTS: Final[OptimizerHandoffReplayAnalyticsFamily] = "concentration_outputs"


class OptimizerHandoffValidationBlockedError(ValueError):
    def __init__(self, response: OptimizerHandoffValidationResponse) -> None:
        self.response = response
        super().__init__(self._build_message(response))

    @staticmethod
    def _build_message(response: OptimizerHandoffValidationResponse) -> str:
        first_failure = next((item for item in response.evaluations if item.status == "fail"), None)
        if first_failure is not None:
            return first_failure.message
        return "optimizer handoff validation blocked"


@dataclass(frozen=True)
class ValidatedOptimizerHandoffGate:
    validation: OptimizerHandoffValidationResponse
    persisted_handoff: PersistedOptimizerHandoff
    benchmark_symbol: str


@dataclass
class _ValidationState:
    request: OptimizerHandoffValidationRequest
    evaluations: list[OptimizerHandoffValidationEvaluation]
    handoff_store: object | None = None
    requested_replay_start_date: date | None = None
    requested_replay_end_date: date | None = None
    manifest: OptimizerHandoffManifest | None = None
    artifact: OptimizationArtifact | None = None
    persisted_handoff: PersistedOptimizerHandoff | None = None
    benchmark_symbol: str | None = None


def validate_optimizer_handoff_constraints(
    request: OptimizerHandoffValidationRequest,
    *,
    handoff_store=None,
) -> OptimizerHandoffValidationResponse:
    return _run_validation(
        request,
        handoff_store=handoff_store,
        requested_replay_start_date=request.start_date,
        requested_replay_end_date=request.end_date,
    ).validation


def load_validated_optimizer_handoff_for_replay(
    request,
    *,
    handoff_store=None,
) -> ValidatedOptimizerHandoffGate:
    gate = _run_validation(
        OptimizerHandoffValidationRequest(handoff_reference=request.handoff_reference),
        handoff_store=handoff_store,
        requested_replay_start_date=request.start_date,
        requested_replay_end_date=request.end_date,
    )
    if gate.validation.validation_status != "ok" or gate.persisted_handoff is None or gate.benchmark_symbol is None:
        raise OptimizerHandoffValidationBlockedError(gate.validation)
    return ValidatedOptimizerHandoffGate(
        validation=gate.validation,
        persisted_handoff=gate.persisted_handoff,
        benchmark_symbol=gate.benchmark_symbol,
    )


@dataclass(frozen=True)
class _ValidationGateResult:
    validation: OptimizerHandoffValidationResponse
    persisted_handoff: PersistedOptimizerHandoff | None
    benchmark_symbol: str | None


def _run_validation(
    request: OptimizerHandoffValidationRequest,
    *,
    handoff_store=None,
    requested_replay_start_date: date | None = None,
    requested_replay_end_date: date | None = None,
) -> _ValidationGateResult:
    state = _ValidationState(
        request=request,
        evaluations=[],
        handoff_store=handoff_store,
        requested_replay_start_date=requested_replay_start_date,
        requested_replay_end_date=requested_replay_end_date,
    )
    raw_handoff = _load_raw_persisted_handoff(state, handoff_store=handoff_store)
    if raw_handoff is not None:
        _validate_models(state, raw_handoff)
    if state.manifest is not None and state.artifact is not None:
        state.persisted_handoff = PersistedOptimizerHandoff(manifest=state.manifest, artifact=state.artifact)
        _validate_cross_file_invariants(state)
        _validate_benchmark_relative_checks(state)
        _validate_truth_separation_checks(state)
    validation = _build_response(state)
    return _ValidationGateResult(
        validation=validation,
        persisted_handoff=state.persisted_handoff,
        benchmark_symbol=state.benchmark_symbol,
    )


def _load_raw_persisted_handoff(state: _ValidationState, *, handoff_store=None) -> RawPersistedOptimizerHandoff | None:
    try:
        raw_handoff = load_raw_optimizer_handoff_by_reference(state.request.handoff_reference, store=handoff_store)
    except OptimizationArtifactPersistenceError as exc:
        state.evaluations.append(
            _evaluation(
                "persisted_payload_accessible",
                phase=RAW_PAYLOAD_PHASE,
                reason_family=_raw_load_reason_family(str(exc)),
                passed=False,
                message_pass="Persisted optimizer handoff payloads are readable.",
                message_fail=str(exc),
            )
        )
        return None

    state.evaluations.append(
        _evaluation(
            "persisted_payload_accessible",
            phase=RAW_PAYLOAD_PHASE,
            reason_family="schema",
            passed=True,
            message_pass="Persisted optimizer handoff payloads loaded successfully.",
            message_fail="Persisted optimizer handoff payloads could not be loaded.",
        )
    )
    return raw_handoff


def _validate_models(state: _ValidationState, raw_handoff: RawPersistedOptimizerHandoff) -> None:
    state.manifest = _model_validate_or_record(
        state,
        rule_id="manifest_model_valid",
        model=OptimizerHandoffManifest,
        payload=raw_handoff.manifest_payload,
    )
    state.artifact = _model_validate_or_record(
        state,
        rule_id="artifact_model_valid",
        model=OptimizationArtifact,
        payload=raw_handoff.artifact_payload,
    )


def _model_validate_or_record(state: _ValidationState, *, rule_id: str, model, payload: dict):
    try:
        validated = model.model_validate(payload)
    except ValidationError as exc:
        state.evaluations.append(
            _evaluation(
                rule_id,
                phase=MODEL_VALIDATION_PHASE,
                reason_family="schema",
                passed=False,
                message_pass="Persisted optimizer handoff model validated successfully.",
                message_fail=_first_validation_error(exc),
            )
        )
        return None

    state.evaluations.append(
        _evaluation(
            rule_id,
            phase=MODEL_VALIDATION_PHASE,
            reason_family="schema",
            passed=True,
            message_pass="Persisted optimizer handoff model validated successfully.",
            message_fail="Persisted optimizer handoff model validation failed.",
        )
    )
    return validated


def _validate_cross_file_invariants(state: _ValidationState) -> None:
    manifest = _required_model(state.manifest)
    artifact = _required_model(state.artifact)
    reference = state.request.handoff_reference

    try:
        validate_optimizer_handoff_manifest(manifest, artifact)
        cross_file_valid = True
        cross_file_message = "Persisted manifest and artifact remain internally consistent."
    except OptimizationArtifactPersistenceError as exc:
        cross_file_valid = False
        cross_file_message = str(exc)
    state.evaluations.append(
        _evaluation(
            "manifest_artifact_consistent",
            phase=CROSS_FILE_PHASE,
            reason_family="provenance",
            passed=cross_file_valid,
            message_pass="Persisted manifest and artifact remain internally consistent.",
            message_fail=cross_file_message,
        )
    )

    state.evaluations.extend(
        [
            _evaluation(
                "handoff_reference_matches_manifest",
                phase=CROSS_FILE_PHASE,
                reason_family="provenance",
                passed=reference.handoff_id == manifest.handoff_id,
                message_pass="Requested handoff reference matches persisted manifest identity.",
                message_fail="handoff reference does not match persisted manifest handoff_id",
                actual_value=reference.handoff_id,
                expected_value=manifest.handoff_id,
                operator="==",
            ),
            _evaluation(
                "artifact_reference_matches_artifact",
                phase=CROSS_FILE_PHASE,
                reason_family="provenance",
                passed=reference.artifact_id == artifact.artifact_id,
                message_pass="Requested artifact reference matches persisted artifact identity.",
                message_fail="handoff reference does not match persisted artifact artifact_id",
                actual_value=reference.artifact_id,
                expected_value=artifact.artifact_id,
                operator="==",
            ),
            _evaluation(
                "manifest_path_canonical",
                phase=CROSS_FILE_PHASE,
                reason_family="provenance",
                passed=reference.manifest_path == str(_store_path_for_manifest(reference, handoff_store=state.handoff_store)),
                message_pass="Manifest reference path is canonical for the persisted handoff.",
                message_fail="handoff reference manifest_path is not the canonical persisted path",
                actual_value=reference.manifest_path,
                expected_value=str(_store_path_for_manifest(reference, handoff_store=state.handoff_store)),
                operator="==",
            ),
            _evaluation(
                "artifact_path_canonical",
                phase=CROSS_FILE_PHASE,
                reason_family="provenance",
                passed=reference.artifact_path == str(_store_path_for_artifact(reference, handoff_store=state.handoff_store)),
                message_pass="Artifact reference path is canonical for the persisted handoff.",
                message_fail="handoff reference artifact_path is not the canonical persisted path",
                actual_value=reference.artifact_path,
                expected_value=str(_store_path_for_artifact(reference, handoff_store=state.handoff_store)),
                operator="==",
            ),
            _evaluation(
                "artifact_feasible",
                phase=CROSS_FILE_PHASE,
                reason_family="constraint_violation",
                passed=artifact.feasibility.status == "feasible",
                message_pass="Optimizer artifact is feasible for downstream replay research.",
                message_fail="Optimizer handoff replay requires a feasible optimizer artifact.",
                actual_value=artifact.feasibility.status,
                expected_value="feasible",
                operator="==",
            ),
            _evaluation(
                "artifact_state_allowed_for_replay",
                phase=CROSS_FILE_PHASE,
                reason_family="constraint_violation",
                passed=artifact.artifact_state.artifact_state in ALLOWED_REPLAY_ARTIFACT_STATES,
                message_pass="Optimizer artifact state is allowed for replay research consumption.",
                message_fail="Optimizer handoff replay requires a complete, degraded, or stale optimizer artifact.",
                actual_value=artifact.artifact_state.artifact_state,
                expected_value="complete|degraded|stale",
                operator="in",
            ),
        ]
    )


def _validate_benchmark_relative_checks(state: _ValidationState) -> None:
    manifest = _required_model(state.manifest)
    artifact = _required_model(state.artifact)
    persisted_benchmark_symbol = _normalized_symbol(manifest.benchmark.benchmark_symbol)
    state.benchmark_symbol = persisted_benchmark_symbol

    state.evaluations.extend(
        [
            _evaluation(
                "persisted_benchmark_id_present",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=bool(manifest.benchmark.benchmark_id.strip()),
                message_pass="Persisted handoff carries benchmark_id metadata.",
                message_fail="Optimizer handoff validation requires persisted benchmark_id metadata.",
                actual_value=manifest.benchmark.benchmark_id,
                expected_value="non_empty_string",
                operator="!=",
            ),
            _evaluation(
                "persisted_benchmark_version_present",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=bool(manifest.benchmark.benchmark_version.strip()),
                message_pass="Persisted handoff carries benchmark_version metadata.",
                message_fail="Optimizer handoff validation requires persisted benchmark_version metadata.",
                actual_value=manifest.benchmark.benchmark_version,
                expected_value="non_empty_string",
                operator="!=",
            ),
            _evaluation(
                "persisted_benchmark_symbol_present",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=persisted_benchmark_symbol is not None,
                message_pass="Persisted handoff carries benchmark_symbol metadata.",
                message_fail="Optimizer handoff validation requires persisted benchmark_symbol metadata in the handoff itself.",
                actual_value=manifest.benchmark.benchmark_symbol,
                expected_value="non_empty_symbol",
                operator="!=",
            ),
            _evaluation(
                "persisted_return_basis_attestation_present",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=manifest.return_basis_attestation is not None,
                message_pass="Persisted handoff carries return-basis attestation metadata.",
                message_fail="Optimizer handoff validation requires persisted return-basis attestation metadata in the handoff itself.",
            ),
            _evaluation(
                "benchmark_relative_objective_attested",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=artifact.objective.benchmark_relative is True,
                message_pass="Persisted optimizer objective remains benchmark-relative.",
                message_fail="Optimizer handoff replay requires a benchmark-relative optimizer objective.",
                actual_value=artifact.objective.benchmark_relative,
                expected_value=True,
                operator="==",
            ),
            _evaluation(
                "benchmark_relative_constraint_complete",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=artifact.hard_constraints.benchmark_relative.max_abs_active_weight is not None,
                message_pass="Benchmark-relative max active weight hard constraint is persisted.",
                message_fail="Optimizer handoff validation requires persisted benchmark-relative hard-constraint metadata.",
            ),
        ]
    )

    benchmark_attestations = {item.attestation_id: item for item in artifact.benchmark_relative_attestations}
    benchmark_constraint_evaluations = {
        item.constraint_id: item
        for item in artifact.constraint_evaluations
        if item.constraint_id == BENCHMARK_RELATIVE_MAX_ABS_ACTIVE_WEIGHT_ID or item.constraint_id.startswith("active_group_exposure_")
    }
    expected_benchmark_constraint_ids = {BENCHMARK_RELATIVE_MAX_ABS_ACTIVE_WEIGHT_ID}
    expected_benchmark_constraint_ids.update(item.constraint_id for item in artifact.key_diagnostics.active_group_exposures)
    missing_constraint_evaluations = sorted(expected_benchmark_constraint_ids - set(benchmark_constraint_evaluations))
    missing_attestations = sorted(expected_benchmark_constraint_ids - set(benchmark_attestations))

    state.evaluations.extend(
        [
            _evaluation(
                "benchmark_relative_attestations_complete",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=not missing_attestations,
                message_pass="Persisted benchmark-relative attestations cover all configured benchmark-relative hard constraints.",
                message_fail="Persisted benchmark-relative attestations are incomplete for the configured benchmark-relative hard constraints.",
                actual_value=",".join(missing_attestations) or None,
            ),
            _evaluation(
                "benchmark_relative_constraint_evaluations_complete",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=not missing_constraint_evaluations,
                message_pass="Persisted benchmark-relative constraint evaluations cover all configured benchmark-relative hard constraints.",
                message_fail="Persisted benchmark-relative constraint evaluations are incomplete for the configured benchmark-relative hard constraints.",
                actual_value=",".join(missing_constraint_evaluations) or None,
            ),
            _evaluation(
                "benchmark_relative_attestation_consistency",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=_attestation_consistency_ok(artifact, manifest.benchmark.benchmark_id),
                message_pass="Benchmark-relative attestations remain consistent with persisted constraint evaluations and benchmark provenance.",
                message_fail="Persisted benchmark-relative attestation metadata is inconsistent with persisted constraint evaluations or benchmark provenance.",
            ),
            _evaluation(
                "return_basis_attestation_consistent",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=manifest.return_basis_attestation.benchmark_symbol == persisted_benchmark_symbol,
                message_pass="Persisted return-basis attestation remains aligned with persisted benchmark provenance.",
                message_fail="Persisted return-basis attestation is inconsistent with persisted benchmark provenance.",
            ),
            _evaluation(
                "benchmark_alignment_attestation_consistent",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="benchmark_context",
                passed=_benchmark_alignment_attestation_consistent(artifact),
                message_pass="Benchmark-alignment attestation is consistent with persisted optimizer provenance.",
                message_fail="Persisted benchmark-alignment attestation is inconsistent with persisted optimizer provenance.",
            ),
            _evaluation(
                "benchmark_relative_constraints_clear",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="constraint_violation",
                passed=all(item.status != "violated" for item in benchmark_constraint_evaluations.values()),
                message_pass="Persisted benchmark-relative constraint evaluations do not report violations.",
                message_fail="Optimizer handoff replay is blocked by persisted benchmark-relative hard-constraint violations.",
            ),
            _evaluation(
                "benchmark_relative_attestations_clear",
                phase=BENCHMARK_RELATIVE_PHASE,
                reason_family="constraint_violation",
                passed=all(item.status not in {"violated", "misaligned"} for item in artifact.benchmark_relative_attestations),
                message_pass="Persisted benchmark-relative attestations remain aligned for replay validation.",
                message_fail="Optimizer handoff replay is blocked by persisted benchmark-relative attestation failures.",
            ),
        ]
    )
    _validate_requested_replay_window_within_attested_coverage(state)


def _validate_requested_replay_window_within_attested_coverage(state: _ValidationState) -> None:
    requested_start = state.requested_replay_start_date
    requested_end = state.requested_replay_end_date
    if requested_start is None or requested_end is None:
        return

    attestation = _required_model(state.manifest).return_basis_attestation
    requested_window = f"{requested_start.isoformat()}..{requested_end.isoformat()}"
    attested_window = f"{attestation.history_start_date}..{attestation.history_end_date}"
    passed = False
    message_fail = "Optimizer handoff replay requires the requested replay window to stay within the persisted attested return-basis coverage window."

    try:
        attested_start = date.fromisoformat(attestation.history_start_date)
        attested_end = date.fromisoformat(attestation.history_end_date)
    except ValueError:
        message_fail = "Optimizer handoff replay requires a valid persisted attested return-basis coverage window."
    else:
        passed = attested_start <= requested_start <= requested_end <= attested_end

    state.evaluations.append(
        _evaluation(
            "requested_replay_window_within_attested_return_basis_coverage",
            phase=BENCHMARK_RELATIVE_PHASE,
            reason_family="constraint_violation",
            passed=passed,
            message_pass="Requested replay window stays within the persisted attested return-basis coverage window.",
            message_fail=message_fail,
            actual_value=requested_window,
            expected_value=attested_window,
            operator="in",
        )
    )


def _validate_truth_separation_checks(state: _ValidationState) -> None:
    manifest = _required_model(state.manifest)
    artifact = _required_model(state.artifact)
    deterministic_order = [symbol.upper() for symbol in artifact.run_metadata.deterministic_symbol_order]

    state.evaluations.extend(
        [
            _evaluation(
                "manifest_hypothetical_true",
                phase=TRUTH_SEPARATION_PHASE,
                reason_family="truth_separation",
                passed=manifest.hypothetical is True,
                message_pass="Persisted optimizer handoff remains explicitly hypothetical.",
                message_fail="Optimizer handoff must remain hypothetical before downstream replay.",
                actual_value=manifest.hypothetical,
                expected_value=True,
                operator="==",
            ),
            _evaluation(
                "manifest_preview_only_true",
                phase=TRUTH_SEPARATION_PHASE,
                reason_family="truth_separation",
                passed=manifest.preview_only is True,
                message_pass="Persisted optimizer handoff remains preview-only.",
                message_fail="Optimizer handoff must remain preview-only before downstream replay.",
                actual_value=manifest.preview_only,
                expected_value=True,
                operator="==",
            ),
            _evaluation(
                "manifest_explicit_reference_only",
                phase=TRUTH_SEPARATION_PHASE,
                reason_family="truth_separation",
                passed=manifest.replay_consumption_mode == "explicit_reference_only",
                message_pass="Persisted optimizer handoff requires explicit-reference-only replay consumption.",
                message_fail="Optimizer handoff replay consumption mode must remain explicit_reference_only.",
                actual_value=manifest.replay_consumption_mode,
                expected_value="explicit_reference_only",
                operator="==",
            ),
            _evaluation(
                "baseline_current_weights_present",
                phase=TRUTH_SEPARATION_PHASE,
                reason_family="truth_separation",
                passed=bool(artifact.replay.current_weights),
                message_pass="Baseline current-holdings slot is populated from persisted current weights.",
                message_fail="Optimizer handoff replay requires persisted current_weights for the baseline holdings truth slot.",
            ),
            _evaluation(
                "candidate_target_weights_present",
                phase=TRUTH_SEPARATION_PHASE,
                reason_family="truth_separation",
                passed=bool(artifact.replay.target_weights),
                message_pass="Candidate hypothetical-output slot is populated from persisted target weights.",
                message_fail="Optimizer handoff replay requires persisted target_weights for the hypothetical candidate truth slot.",
            ),
            _evaluation(
                "candidate_target_matches_optimizer_output",
                phase=TRUTH_SEPARATION_PHASE,
                reason_family="truth_separation",
                passed=artifact.replay.target_weights == artifact.proposed_weights == manifest.optimizer_output_target_weights,
                message_pass="Persisted hypothetical target slots remain aligned across replay, artifact, and manifest payloads.",
                message_fail="Persisted hypothetical target slots disagree across replay, artifact, or manifest payloads.",
            ),
            _evaluation(
                "baseline_weights_deterministic_ordered",
                phase=TRUTH_SEPARATION_PHASE,
                reason_family="truth_separation",
                passed=_weights_follow_deterministic_order(artifact.replay.current_weights, deterministic_order),
                message_pass="Persisted baseline current weights preserve deterministic symbol ordering.",
                message_fail="Persisted baseline current weights must preserve deterministic symbol ordering.",
            ),
            _evaluation(
                "candidate_weights_deterministic_ordered",
                phase=TRUTH_SEPARATION_PHASE,
                reason_family="truth_separation",
                passed=_weights_follow_deterministic_order(artifact.replay.target_weights, deterministic_order),
                message_pass="Persisted hypothetical target weights preserve deterministic symbol ordering.",
                message_fail="Persisted hypothetical target weights must preserve deterministic symbol ordering.",
            ),
        ]
    )


def _build_response(state: _ValidationState) -> OptimizerHandoffValidationResponse:
    manifest = state.manifest
    artifact = state.artifact
    blocking_rule_ids = [item.rule_id for item in state.evaluations if item.severity == "hard_block" and item.status == "fail"]
    warnings: list[str] = []
    if artifact is not None and artifact.artifact_state.artifact_state == "degraded":
        warnings.append("Optimizer handoff artifact is degraded; replay remains hypothetical research output only.")
    if artifact is not None and artifact.artifact_state.artifact_state == "stale":
        warnings.append("Optimizer handoff artifact is stale; replay remains hypothetical research output only.")

    return OptimizerHandoffValidationResponse(
        handoff_id=manifest.handoff_id if manifest is not None else None,
        artifact_id=artifact.artifact_id if artifact is not None else None,
        source_portfolio_snapshot_id=manifest.source_portfolio_snapshot.snapshot_id if manifest is not None else None,
        eligible_replay_window=_eligible_replay_window(manifest, state.benchmark_symbol),
        replay_handoff=_replay_handoff(state) if not blocking_rule_ids else None,
        provenance=OptimizerHandoffValidationProvenance(
            benchmark_id=manifest.benchmark.benchmark_id if manifest is not None else None,
            benchmark_version=manifest.benchmark.benchmark_version if manifest is not None else None,
            benchmark_symbol=state.benchmark_symbol,
            objective=manifest.objective if manifest is not None else None,
            replay_output_policy=build_optimizer_handoff_replay_output_policy(manifest.return_basis_attestation) if manifest is not None else None,
            artifact_state=artifact.artifact_state.artifact_state if artifact is not None else None,
            constraint_set_fingerprint=manifest.constraint_set.constraint_set_fingerprint if manifest is not None else None,
        ),
        validation_status="blocked" if blocking_rule_ids else "ok",
        evaluations=state.evaluations,
        blocking_rule_ids=blocking_rule_ids,
        warnings=warnings,
    )


def _replay_handoff(state: _ValidationState) -> OptimizerHandoffReplayHandoff | None:
    manifest = state.manifest
    if manifest is None or state.requested_replay_start_date is None or state.requested_replay_end_date is None:
        return None
    return OptimizerHandoffReplayHandoff(
        handoff_reference=state.request.handoff_reference,
        effective_replay_params=OptimizerHandoffReplayEffectiveParams(
            start_date=state.requested_replay_start_date,
            end_date=state.requested_replay_end_date,
        ),
    )


def _eligible_replay_window(
    manifest: OptimizerHandoffManifest | None,
    benchmark_symbol: str | None,
) -> OptimizerHandoffEligibleReplayWindow | None:
    if manifest is None:
        return None
    attestation = manifest.return_basis_attestation
    return OptimizerHandoffEligibleReplayWindow(
        benchmark_symbol=benchmark_symbol,
        as_of_date=attestation.as_of_date,
        start_date=attestation.history_start_date,
        end_date=attestation.history_end_date,
    )


def build_optimizer_handoff_replay_output_policy(attestation: OptimizerReturnBasisAttestation) -> OptimizerHandoffReplayOutputPolicy:
    section_trust = normalize_optimizer_return_basis_attestation(attestation).section_trust
    eligible_families: list[OptimizerHandoffReplayAnalyticsFamily] = []
    withheld_families: list[OptimizerHandoffReplayAnalyticsFamily] = []
    family_trust_pairs: list[tuple[OptimizerHandoffReplayAnalyticsFamily, bool]] = [
        (BENCHMARK_RELATIVE_VOLATILITY_OUTPUTS, section_trust.benchmark_relative_path == "verified_adjusted_close"),
        (FACTOR_EXPOSURE_OUTPUTS, section_trust.factor_model_path == "verified_adjusted_close"),
        (STRESS_SCENARIO_OUTPUTS, section_trust.factor_model_path == "verified_adjusted_close"),
        (RISK_CONTRIBUTION_OUTPUTS, section_trust.risk_contribution_path == "verified_adjusted_close"),
        (CONCENTRATION_OUTPUTS, section_trust.risk_contribution_path == "verified_adjusted_close"),
    ]
    for family_id, is_eligible in family_trust_pairs:
        if is_eligible:
            eligible_families.append(family_id)
        else:
            withheld_families.append(family_id)
    return OptimizerHandoffReplayOutputPolicy(
        section_trust=section_trust,
        eligible_families=eligible_families,
        withheld_families=withheld_families,
    )


def _weights_follow_deterministic_order(weights, deterministic_order: list[str]) -> bool:
    if not weights:
        return False
    order_index = {symbol: index for index, symbol in enumerate(deterministic_order)}
    filtered_symbols = [item.symbol.upper() for item in weights if item.weight > 0]
    if not filtered_symbols:
        return False
    if any(symbol not in order_index for symbol in filtered_symbols):
        return False
    expected = sorted(filtered_symbols, key=lambda symbol: order_index[symbol])
    return filtered_symbols == expected and len(filtered_symbols) == len(set(filtered_symbols))


def _attestation_consistency_ok(artifact: OptimizationArtifact, benchmark_id: str) -> bool:
    benchmark_constraint_evaluations = {
        item.constraint_id: item
        for item in artifact.constraint_evaluations
        if item.constraint_id == BENCHMARK_RELATIVE_MAX_ABS_ACTIVE_WEIGHT_ID or item.constraint_id.startswith("active_group_exposure_")
    }
    for attestation in artifact.benchmark_relative_attestations:
        if attestation.attestation_id == BENCHMARK_ALIGNMENT_ATTESTATION_ID:
            continue
        evaluation = benchmark_constraint_evaluations.get(attestation.constraint_id)
        if evaluation is None:
            return False
        if attestation.benchmark_id != benchmark_id:
            return False
        if attestation.status != evaluation.status:
            return False
        if attestation.actual_value != evaluation.actual_value:
            return False
        if attestation.limit_value != evaluation.limit_value:
            return False
        if attestation.message != evaluation.message:
            return False
        if attestation.details.get("benchmark_relative") is not True:
            return False
    return BENCHMARK_RELATIVE_MAX_ABS_ACTIVE_WEIGHT_ID in {item.attestation_id for item in artifact.benchmark_relative_attestations}


def _benchmark_alignment_attestation_consistent(artifact: OptimizationArtifact) -> bool:
    alignment_attestations = [item for item in artifact.benchmark_relative_attestations if item.attestation_id == BENCHMARK_ALIGNMENT_ATTESTATION_ID]
    if len(alignment_attestations) != 1:
        return False
    attestation = alignment_attestations[0]
    risk_input_present = any(item.input_kind == "risk_package" for item in artifact.input_fingerprints)
    if risk_input_present:
        aligned_detail = attestation.details.get("aligned")
        if attestation.status == "aligned":
            return aligned_detail is True
        if attestation.status == "misaligned":
            return aligned_detail is False
        return False
    return attestation.status == "not_applicable"


def _store_path_for_manifest(reference, *, handoff_store=None):
    from app.services.optimizer_artifact_service import OptimizerHandoffStore

    return (handoff_store or OptimizerHandoffStore()).canonical_paths(reference.handoff_id).manifest_path


def _store_path_for_artifact(reference, *, handoff_store=None):
    from app.services.optimizer_artifact_service import OptimizerHandoffStore

    return (handoff_store or OptimizerHandoffStore()).canonical_paths(reference.handoff_id).artifact_path


def _raw_load_reason_family(message: str) -> OptimizerHandoffValidationReasonFamily:
    if message.startswith("missing persisted handoff file") or message.endswith("is not the canonical persisted path"):
        return "provenance"
    return "schema"


def _first_validation_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error.get("loc", ()))
    message = error.get("msg", "validation error")
    return f"{location}: {message}" if location else message


def _normalized_symbol(value: str | None) -> str | None:
    return canonicalize_benchmark_symbol(value)


def _required_model(value):
    if value is None:
        raise AssertionError("expected validated model")
    return value


def _evaluation(
    rule_id: str,
    *,
    phase: OptimizerHandoffValidationPhase,
    reason_family: OptimizerHandoffValidationReasonFamily,
    passed: bool,
    message_pass: str,
    message_fail: str,
    actual_value=None,
    expected_value=None,
    operator=None,
) -> OptimizerHandoffValidationEvaluation:
    return OptimizerHandoffValidationEvaluation(
        rule_id=rule_id,
        phase=phase,
        reason_family=reason_family,
        severity="hard_block",
        status="pass" if passed else "fail",
        message=message_pass if passed else message_fail,
        actual_value=actual_value,
        expected_value=expected_value,
        operator=operator,
    )

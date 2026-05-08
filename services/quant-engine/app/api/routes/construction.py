from typing import get_args

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.construction import (
    ConstructionArtifact,
    ConstructionRankingArtifactPreflightResponse,
    ConstructionPolicyCatalogEntry,
    ConstructionPolicyConstraints,
    ConstructionPolicyDeterminism,
    ConstructionPolicyFamily,
    ConstructionPolicyInputs,
    ConstructionPolicyLaunchTopN,
    ConstructionPolicyOptionalConstraintSupport,
    ConstructionPolicyRankingSupport,
    ConstructionPolicyRequiredConstraintSupport,
    ConstructionPolicyRequiredInputSupport,
    ConstructionRunRequest,
)
from app.schemas.ranking import infer_ranking_artifact_kind_from_artifact_id
from app.services.construction_ranking_handoff_service import (
    preflight_etf_ranking_artifact_for_construction,
    preflight_intent_bound_etf_replacement_ranking_artifact_for_construction,
)
from app.services.construction_artifact_service import (
    ConstructionArtifactIntegrityValidationError,
    ConstructionArtifactInvalidJsonError,
    ConstructionArtifactMissingFileError,
    ConstructionArtifactNonObjectPayloadError,
    ConstructionArtifactPersistenceError,
    ConstructionArtifactSchemaValidationError,
    load_construction_artifact,
)
from app.services.construction_policy_catalog import list_construction_policies
from app.services.construction_run_service import (
    build_construction_run,
    build_construction_run_request_from_ranking_artifact_handoff,
)
from app.services.etf_ranking_artifact_service import (
    EtfRankingArtifactIntegrityValidationError,
    EtfRankingArtifactInvalidJsonError,
    EtfRankingArtifactMissingFileError,
    EtfRankingArtifactNonObjectPayloadError,
    EtfRankingArtifactPersistenceError,
    EtfRankingArtifactSchemaValidationError,
    load_etf_ranking_artifact,
)
from app.services.replacement_ranking_artifact_service import (
    ReplacementRankingArtifactIntegrityValidationError,
    ReplacementRankingArtifactInvalidJsonError,
    ReplacementRankingArtifactMissingFileError,
    ReplacementRankingArtifactNonObjectPayloadError,
    ReplacementRankingArtifactPersistenceError,
    ReplacementRankingArtifactSchemaValidationError,
    load_replacement_ranking_artifact,
)


router = APIRouter(prefix="/construction", tags=["construction"])
_CROSS_SECTIONAL_RESEARCH_ARTIFACT_ID_PREFIX = "cross_sectional_research_artifact_"

_CONSTRUCTION_POLICY_FILTER_ALLOWLIST = frozenset(
    {
        "family",
        "constraints",
        "inputs",
        "determinism",
        "ranking_support",
        "full_investment_constraint",
        "long_only_constraint",
        "eligible_ranked_universe_constraint",
        "max_position_weight_constraint",
        "min_position_weight_constraint",
        "max_turnover_weight_constraint",
        "max_trade_intent_count_constraint",
        "ranked_universe_input",
        "current_portfolio_input",
        "launch_top_n",
    }
)

_CONSTRUCTION_POLICY_FILTER_ALLOWED_VALUES = {
    "family": frozenset(get_args(ConstructionPolicyFamily)),
    "constraints": frozenset(get_args(ConstructionPolicyConstraints)),
    "inputs": frozenset(get_args(ConstructionPolicyInputs)),
    "determinism": frozenset(get_args(ConstructionPolicyDeterminism)),
    "ranking_support": frozenset(get_args(ConstructionPolicyRankingSupport)),
    "full_investment_constraint": frozenset(get_args(ConstructionPolicyRequiredConstraintSupport)),
    "long_only_constraint": frozenset(get_args(ConstructionPolicyRequiredConstraintSupport)),
    "eligible_ranked_universe_constraint": frozenset(get_args(ConstructionPolicyRequiredConstraintSupport)),
    "max_position_weight_constraint": frozenset(get_args(ConstructionPolicyRequiredConstraintSupport)),
    "min_position_weight_constraint": frozenset(get_args(ConstructionPolicyOptionalConstraintSupport)),
    "max_turnover_weight_constraint": frozenset(get_args(ConstructionPolicyOptionalConstraintSupport)),
    "max_trade_intent_count_constraint": frozenset(get_args(ConstructionPolicyOptionalConstraintSupport)),
    "ranked_universe_input": frozenset(get_args(ConstructionPolicyRequiredInputSupport)),
    "current_portfolio_input": frozenset(get_args(ConstructionPolicyRequiredInputSupport)),
    "launch_top_n": frozenset(str(value) for value in get_args(ConstructionPolicyLaunchTopN)),
}


def _validate_construction_policy_filters(request: Request) -> None:
    unsupported_keys = sorted(set(request.query_params.keys()) - _CONSTRUCTION_POLICY_FILTER_ALLOWLIST)
    if unsupported_keys:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported construction policy filter key(s): {', '.join(unsupported_keys)}",
        )
    repeated_keys: list[str] = []
    for filter_name, allowed_values in _CONSTRUCTION_POLICY_FILTER_ALLOWED_VALUES.items():
        raw_values = request.query_params.getlist(filter_name)
        if not raw_values:
            continue
        for raw_value in raw_values:
            if raw_value == "" or raw_value not in allowed_values:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"invalid construction policy filter value for '{filter_name}': {raw_value!r}; "
                        f"supported values: {', '.join(sorted(allowed_values))}"
                    ),
                )
        if len(raw_values) > 1:
            repeated_keys.append(filter_name)
    if repeated_keys:
        raise HTTPException(
            status_code=422,
            detail=f"repeated construction policy filter key(s): {', '.join(repeated_keys)}",
        )


@router.post(
    "/ranking-artifacts/preflight/{artifact_id}",
    response_model=ConstructionRankingArtifactPreflightResponse,
)
def preflight_construction_ranking_artifact(artifact_id: str) -> ConstructionRankingArtifactPreflightResponse:
    try:
        if artifact_id.startswith(_CROSS_SECTIONAL_RESEARCH_ARTIFACT_ID_PREFIX):
            raise ValueError(
                "unsupported ranking artifact family for construction preflight: cross_sectional_research_run"
            )
        artifact_kind = infer_ranking_artifact_kind_from_artifact_id(artifact_id)
        if artifact_kind == "etf_ranking":
            return preflight_etf_ranking_artifact_for_construction(artifact_id)
        if artifact_kind == "intent_bound_etf_replacement_ranking":
            return preflight_intent_bound_etf_replacement_ranking_artifact_for_construction(artifact_id)
        raise ValueError("unsupported ranking artifact kind")
    except EtfRankingArtifactMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReplacementRankingArtifactMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        EtfRankingArtifactInvalidJsonError,
        EtfRankingArtifactNonObjectPayloadError,
        EtfRankingArtifactSchemaValidationError,
        EtfRankingArtifactIntegrityValidationError,
        EtfRankingArtifactPersistenceError,
        ReplacementRankingArtifactInvalidJsonError,
        ReplacementRankingArtifactNonObjectPayloadError,
        ReplacementRankingArtifactSchemaValidationError,
        ReplacementRankingArtifactIntegrityValidationError,
        ReplacementRankingArtifactPersistenceError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run", response_model=ConstructionArtifact)
def run_construction(request: ConstructionRunRequest) -> ConstructionArtifact:
    try:
        resolved_request = request
        if request.ranking_artifact_handoff is not None:
            if request.ranking_artifact_handoff.artifact_kind == "etf_ranking":
                artifact = load_etf_ranking_artifact(request.ranking_artifact_handoff.artifact_id)
            elif request.ranking_artifact_handoff.artifact_kind == "intent_bound_etf_replacement_ranking":
                artifact = load_replacement_ranking_artifact(request.ranking_artifact_handoff.artifact_id)
            else:
                raise ValueError("unsupported ranking artifact kind")
            resolved_request = build_construction_run_request_from_ranking_artifact_handoff(
                request_id=request.request_id,
                handoff=request.ranking_artifact_handoff,
                artifact=artifact,
                current_portfolio=request.current_portfolio,
                policy=request.policy,
                hard_constraints=request.hard_constraints,
            )
        return build_construction_run(resolved_request)
    except EtfRankingArtifactMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReplacementRankingArtifactMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        EtfRankingArtifactInvalidJsonError,
        EtfRankingArtifactNonObjectPayloadError,
        EtfRankingArtifactSchemaValidationError,
        EtfRankingArtifactIntegrityValidationError,
        EtfRankingArtifactPersistenceError,
        ReplacementRankingArtifactInvalidJsonError,
        ReplacementRankingArtifactNonObjectPayloadError,
        ReplacementRankingArtifactSchemaValidationError,
        ReplacementRankingArtifactIntegrityValidationError,
        ReplacementRankingArtifactPersistenceError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/policies", response_model=list[ConstructionPolicyCatalogEntry])
def get_construction_policies(
    request: Request,
    family: str | None = Query(default=None),
    constraints: str | None = Query(default=None),
    inputs: str | None = Query(default=None),
    determinism: str | None = Query(default=None),
    ranking_support: str | None = Query(default=None),
    full_investment_constraint: str | None = Query(default=None),
    long_only_constraint: str | None = Query(default=None),
    eligible_ranked_universe_constraint: str | None = Query(default=None),
    max_position_weight_constraint: str | None = Query(default=None),
    min_position_weight_constraint: str | None = Query(default=None),
    max_turnover_weight_constraint: str | None = Query(default=None),
    max_trade_intent_count_constraint: str | None = Query(default=None),
    ranked_universe_input: str | None = Query(default=None),
    current_portfolio_input: str | None = Query(default=None),
    launch_top_n: str | None = Query(default=None),
) -> list[ConstructionPolicyCatalogEntry]:
    _validate_construction_policy_filters(request)
    return list_construction_policies(
        family=family,
        constraints=constraints,
        inputs=inputs,
        determinism=determinism,
        ranking_support=ranking_support,
        full_investment_constraint=full_investment_constraint,
        long_only_constraint=long_only_constraint,
        eligible_ranked_universe_constraint=eligible_ranked_universe_constraint,
        max_position_weight_constraint=max_position_weight_constraint,
        min_position_weight_constraint=min_position_weight_constraint,
        max_turnover_weight_constraint=max_turnover_weight_constraint,
        max_trade_intent_count_constraint=max_trade_intent_count_constraint,
        ranked_universe_input=ranked_universe_input,
        current_portfolio_input=current_portfolio_input,
        launch_top_n=int(launch_top_n) if launch_top_n is not None else None,
    )


@router.get("/artifacts/{artifact_id}", response_model=ConstructionArtifact)
def get_construction_artifact(artifact_id: str) -> ConstructionArtifact:
    try:
        return load_construction_artifact(artifact_id)
    except ConstructionArtifactMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        ConstructionArtifactInvalidJsonError,
        ConstructionArtifactNonObjectPayloadError,
        ConstructionArtifactSchemaValidationError,
        ConstructionArtifactIntegrityValidationError,
        ConstructionArtifactPersistenceError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

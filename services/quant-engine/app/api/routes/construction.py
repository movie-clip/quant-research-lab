from fastapi import APIRouter, HTTPException

from app.schemas.construction import ConstructionArtifact, ConstructionPolicyCatalogEntry, ConstructionRunRequest
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
from app.services.construction_run_service import build_construction_run


router = APIRouter(prefix="/construction", tags=["construction"])


@router.post("/run", response_model=ConstructionArtifact)
def run_construction(request: ConstructionRunRequest) -> ConstructionArtifact:
    try:
        return build_construction_run(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/policies", response_model=list[ConstructionPolicyCatalogEntry])
def get_construction_policies() -> list[ConstructionPolicyCatalogEntry]:
    return list_construction_policies()


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

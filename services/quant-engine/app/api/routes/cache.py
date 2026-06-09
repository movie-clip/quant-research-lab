from fastapi import APIRouter, HTTPException

from app.schemas.cache import CacheClearRequest, CacheClearResult, CacheStats
from app.services.cache_admin import clear_cache, get_cache_stats

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats", response_model=CacheStats)
def cache_stats() -> CacheStats:
    try:
        return get_cache_stats()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/clear", response_model=CacheClearResult)
def cache_clear(request: CacheClearRequest | None = None) -> CacheClearResult:
    try:
        namespace = request.namespace if request is not None else None
        return clear_cache(namespace)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

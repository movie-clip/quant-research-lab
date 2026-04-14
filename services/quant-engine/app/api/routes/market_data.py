from fastapi import APIRouter, HTTPException, Query

from app.services.market_data import MarketDataService


router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.get("/quote-short")
def get_quote_short(symbol: str = Query(..., min_length=1)) -> dict:
    service = MarketDataService()
    try:
        quote = service.get_latest_quotes([symbol]).get(symbol)
        return {"rows": [quote] if quote else [], "meta": service.get_last_fetch_meta(symbol)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/historical-price-light")
def get_historical_price_light(
    symbol: str = Query(..., min_length=1),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
) -> dict:
    service = MarketDataService()
    try:
        rows = service.get_historical_prices(symbol, from_date, to_date)
        return {"rows": rows, "meta": service.get_last_fetch_meta(symbol)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

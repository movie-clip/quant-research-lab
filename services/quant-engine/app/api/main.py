from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import attribution, cache, correlation, currency_risk, dashboard_history, diagnostics, distribution, drawdown, drift, exposure, health, imports, market_data, provenance, stress
from app.core.logging import configure_logging


configure_logging()

app = FastAPI(title="Portfolio Quant Engine", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(imports.router)
app.include_router(exposure.router)
app.include_router(currency_risk.router)
app.include_router(diagnostics.router)
app.include_router(dashboard_history.router)
app.include_router(market_data.router)
app.include_router(drift.router)
app.include_router(attribution.router)
app.include_router(correlation.router)
app.include_router(stress.router)
app.include_router(drawdown.router)
app.include_router(distribution.router)
app.include_router(provenance.router)
app.include_router(cache.router)

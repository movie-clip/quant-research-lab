from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import backtests, construction, dashboard_history, diagnostics, exposure, health, imports, market_data, optimizer, strategy_lab
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
app.include_router(diagnostics.router)
app.include_router(dashboard_history.router)
app.include_router(market_data.router)
app.include_router(backtests.router)
app.include_router(construction.router)
app.include_router(optimizer.router)
app.include_router(strategy_lab.router)

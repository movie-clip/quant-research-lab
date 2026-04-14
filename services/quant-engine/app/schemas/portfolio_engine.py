from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.imports import StatementImporter


class PortfolioPositionSnapshot(BaseModel):
    symbol: str
    market_value: float
    quantity: float | None = None
    currency: str | None = None
    sector: str | None = None
    name: str | None = None
    source_type: str | None = None


class PortfolioCashBalanceSnapshot(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    amount: float


class PortfolioSnapshotMetadata(BaseModel):
    benchmark_symbol: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class PortfolioImportedMeta(BaseModel):
    importer: StatementImporter | None = None
    statement_period: str | None = None
    imported_at: datetime | None = None
    source_file_names: list[str] = Field(default_factory=list)


class PortfolioSnapshot(BaseModel):
    snapshot_version: int = 1
    base_currency: str | None = None
    imported_meta: PortfolioImportedMeta = Field(default_factory=PortfolioImportedMeta)
    positions: list[PortfolioPositionSnapshot] = Field(default_factory=list)
    cash_balances: list[PortfolioCashBalanceSnapshot] = Field(default_factory=list)
    metadata: PortfolioSnapshotMetadata = Field(default_factory=PortfolioSnapshotMetadata)


class PortfolioHistoryContext(BaseModel):
    benchmark_symbol: str = 'SPY'
    statement_period: str | None = None
    imported_at: datetime | None = None
    importer: StatementImporter | None = None
    source_file_names: list[str] = Field(default_factory=list)
    history_start_date: str | None = None
    history_end_date: str | None = None


class PortfolioEngineRequest(BaseModel):
    benchmark_symbol: str = 'SPY'
    base_currency: str | None = None
    statement_period: str | None = None
    imported_at: datetime | None = None
    importer: StatementImporter | None = None
    source_file_names: list[str] = Field(default_factory=list)
    positions: list[PortfolioPositionSnapshot] = Field(default_factory=list)
    cash_balances: list[PortfolioCashBalanceSnapshot] = Field(default_factory=list)

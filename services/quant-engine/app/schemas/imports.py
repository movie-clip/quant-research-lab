from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.constants import DEFAULT_BENCHMARK_SYMBOL


LedgerEntryType = Literal[
    "BUY",
    "SELL",
    "DIVIDEND",
    "WITHHOLDING_TAX",
    "INTEREST",
    "FEE",
    "DEPOSIT",
    "WITHDRAWAL",
]


StatementImporter = Literal["interactive_brokers", "freedom24", "espp", "multi_broker"]


class ImportedStatement(BaseModel):
    importer: StatementImporter
    imported_at: datetime
    source_path: str
    detected_format: str
    account_id: str | None = None
    base_currency: str | None = None
    statement_period: str | None = None
    page_count: int | None = None


class ImportedStatementTotals(BaseModel):
    starting_nav: float | None = None
    ending_nav: float | None = None
    cash_total: float | None = None
    stock_total: float | None = None
    dividends_total: float | None = None
    withholding_tax_total: float | None = None
    interest_total: float | None = None
    other_fees_total: float | None = None
    commissions_total: float | None = None
    deposits_total: float | None = None
    time_weighted_return_pct: float | None = None
    fx_rates: dict[str, float] = Field(default_factory=dict)


class ImportedInstrument(BaseModel):
    symbol: str
    description: str | None = None
    isin: str | None = None
    listing_exchange: str | None = None
    instrument_type: str | None = None
    currency: str | None = None


class ImportedPosition(BaseModel):
    as_of_date: date
    symbol: str
    quantity: float
    cost_basis: float
    close_price: float
    market_value: float
    unrealized_pnl: float
    currency: str = Field(min_length=3, max_length=3)


class ImportedCashBalance(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    starting_cash: float | None = None
    ending_cash: float | None = None
    ending_settled_cash: float | None = None


class ImportedLedgerEntry(BaseModel):
    entry_type: LedgerEntryType
    trade_date: date
    symbol: str | None = None
    description: str | None = None
    quantity: float | None = None
    price: float | None = None
    gross_amount: float | None = None
    net_amount: float | None = None
    fee: float | None = None
    tax: float | None = None
    currency: str = Field(min_length=3, max_length=3)
    source_section: str
    source_line: str | None = None


class ImportedPortfolioSnapshot(BaseModel):
    statement: ImportedStatement
    statements: list[ImportedStatement] = Field(default_factory=list)
    statement_totals: ImportedStatementTotals | None = None
    instruments: list[ImportedInstrument]
    cash_balances: list[ImportedCashBalance]
    positions: list[ImportedPosition]
    ledger_entries: list[ImportedLedgerEntry]

    def model_post_init(self, __context) -> None:
        if not self.statements:
            self.statements = [self.statement.model_copy(deep=True)]


class SnapshotAnalysisPosition(BaseModel):
    symbol: str
    market_value: float
    quantity: float | None = None
    currency: str | None = None
    sector: str | None = None


class SnapshotAnalysisCashBalance(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    amount: float


class CombineImportedSnapshotsRequest(BaseModel):
    snapshots: list[ImportedPortfolioSnapshot]


class SnapshotAnalysisRequest(BaseModel):
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL
    base_currency: str | None = None
    statement_period: str | None = None
    imported_at: datetime | None = None
    importer: StatementImporter | None = None
    source_file_names: list[str] = Field(default_factory=list)
    positions: list[SnapshotAnalysisPosition] = Field(default_factory=list)
    cash_balances: list[SnapshotAnalysisCashBalance] = Field(default_factory=list)

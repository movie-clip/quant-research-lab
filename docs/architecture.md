# Architecture Notes

## System Boundaries

The project is split into a desktop application and a local quant service.

- `apps/desktop`
  - user interface, local settings, charts, portfolio views, assistant UX
- `services/quant-engine`
  - market data ingestion, normalization, portfolio import, backtests, analytics

The desktop app should treat the quant engine as the source of truth for portfolio calculations.

## API Boundary

The frontend should not calculate portfolio state from raw transactions on its own. It should request normalized results from the quant engine.

Current direction:

- local workspace persistence is snapshot-first
- engine outputs are derived runtime artifacts
- the frontend may persist `PortfolioSnapshot` and workspace metadata locally, but it should not persist derived financial analytics as truth
- historical diagnostics must come from engine responses with appropriate history context, not from frontend approximation

Suggested API groups:

- `GET /health`
- `POST /market-data/sync/fmp`
- `GET /market-data/prices`
- `GET /market-data/fundamentals`
- `POST /portfolios`
- `GET /portfolios/{portfolio_id}`
- `POST /portfolios/{portfolio_id}/transactions`
- `POST /portfolios/import/interactive-brokers`
- `POST /backtests`
- `GET /backtests/{backtest_id}`
- `POST /assistant/portfolio-review`

## Interactive Brokers Import

Interactive Brokers import should be implemented as a dedicated importer pipeline, not mixed into general portfolio logic.

Pipeline:

1. upload statement file from UI
2. detect statement type and format
3. parse raw statement rows into normalized records
4. map records into portfolio entities:
   - accounts
   - positions
   - cash balances
   - transactions
   - fees
   - dividends
5. run validation and reconciliation
6. create or update a portfolio snapshot

Keep raw imported rows for debugging. Statement formats change over time.

For PDF statements like `docs/U8516450_2025_2025.pdf`, the importer should initially extract and normalize these sections:

- account metadata
- cash report
- open positions
- trades
- dividends
- withholding tax
- fees
- instrument reference data

This gives enough coverage to build an imported portfolio, a transaction ledger, current holdings, and cash balances.

## Core Domain Objects

- `Portfolio`
- `Account`
- `Holding`
- `Transaction`
- `CashLedgerEntry`
- `CorporateAction`
- `Benchmark`
- `BacktestRun`
- `ImportedStatement`

## Data Flow

### FMP market data

1. request sync from UI or background job
2. fetch FMP endpoints
3. store raw payloads optionally for troubleshooting
4. normalize into parquet datasets
5. expose queryable views through DuckDB
6. serve UI and backtest requests from local normalized datasets

### Portfolio import and analytics

1. import manual transactions or IB statement
2. normalize into domain transactions and balances
3. build `PortfolioSnapshot` plus optional history context
4. persist snapshot as local truth in the desktop workspace model
5. call dedicated engines for exposure, diagnostics, and backtests
6. send derived engine outputs to UI

### Desktop workspace model

The desktop app now follows a local-first workspace structure:

- `PortfolioWorkspace`
- `PortfolioNode`
- `WorkingDraft`
- `PortfolioSnapshot`

Saved portfolio variants are immutable child nodes. The visible lineage contract is:

- `base` for the imported root snapshot
- `base -> child` for saved immutable variants derived from that root or another variant
- `Working Draft · <active lineage>` for the editable draft created from the active node

Engine outputs are recalculated or restored as derived views and are not the persisted truth of the workspace. When the active node or selected exposure snapshot changes, the app refreshes exposure/diagnostics for that selection without replacing the rich dashboard history state already loaded for the workspace. For stability during development and recovery from stale persisted state, the desktop also exposes a hard local IndexedDB reset action.

## MVP Boundary Rules

- UI owns presentation and workflow state
- quant engine owns calculations and imported portfolio truth
- LLM owns explanation and suggestion only
- deterministic code validates any LLM-generated allocation ideas before use

## Rapid Development Rule

During early development, imported portfolio analysis should remain in memory.

- API endpoints may parse, normalize, reconcile, and derive portfolio views on demand
- schema and service boundaries should anticipate future storage integration
- avoid coupling importer logic to a concrete database until the domain model stabilizes

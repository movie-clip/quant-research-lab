# Strategy Research Architecture

## Goal

Evolve the project from a portfolio import and analytics tool into a local multi-engine workstation that supports:

- real imported portfolio accounting
- deterministic futures and multi-asset strategy research
- overlay analysis between live holdings and hypothetical strategy sleeves

The target product is not just a portfolio tracker and not just a backtester. It is a local-first investment workstation for both real capital and systematic research.

## Top-Level Engines

### 1. Portfolio Engine

Owns real-world imported portfolio truth.

Responsibilities:

- broker imports
- canonical ledger construction
- holdings and cash reconstruction
- reconciliation and audit trails
- imported-portfolio analytics

Current foundation already exists in:

- `services/quant-engine/app/importers/`
- `services/quant-engine/app/domain/ledger.py`
- `services/quant-engine/app/engine/portfolio_state.py`
- `services/quant-engine/app/analytics/`

### 2. Research Engine

Owns systematic strategy development and testing.

Responsibilities:

- instrument master and contract metadata
- historical bar datasets
- continuous futures construction
- deterministic strategy definitions
- signal generation
- backtest simulation
- parameter research and comparison

This engine should be separate from imported-portfolio analytics. Do not overload `analytics/` or `optimization/` with full strategy research responsibilities.

### 3. Overlay Engine

Owns combination analysis between imported portfolios and hypothetical strategy sleeves.

Responsibilities:

- allocate capital between live portfolio and strategy sleeves
- compare drawdown, volatility, return, and exposure effects
- estimate diversification benefits
- report combined equity curves and risk summaries

This is likely the product-level bridge between your real investing workflow and the book strategies you want to test.

## Recommended Backend Boundaries

Add or grow these backend modules over time:

### `services/quant-engine/app/instruments/`

Purpose:

- canonical instrument identity
- futures contract metadata
- exchange, currency, tick size, point value, expiry, root symbol

Needed because futures strategies rely on contract-level rules that are not represented by current equity-style symbols alone.

### `services/quant-engine/app/datasets/`

Purpose:

- OHLCV storage and access
- local bar queries
- continuous futures series building
- roll metadata and adjusted-series construction

Research should eventually run from local normalized datasets rather than live market API calls.

### `services/quant-engine/app/strategies/`

Purpose:

- deterministic strategy definitions
- parameter schemas
- signal builders
- strategy family organization

Examples:

- trend-following
- breakout
- moving-average filter
- mean reversion

### `services/quant-engine/app/backtests/`

Purpose:

- backtest runner
- fills and execution assumptions
- fees and slippage
- contract multipliers
- position sizing
- roll handling
- margin / notional exposure accounting

This should become a first-class service boundary, not an extension of imported portfolio analytics.

### `services/quant-engine/app/research/`

Purpose:

- parameter sweeps
- ranking / comparison of backtests
- portfolio-of-strategies analysis
- walk-forward and validation workflows later

### `services/quant-engine/app/overlay/`

Purpose:

- combine imported portfolios with research outputs
- evaluate a strategy sleeve inside the broader portfolio
- compare baseline portfolio vs overlay portfolio

Starter skeleton modules now exist for these boundaries so future work can fill in details without redefining the structure:

- `services/quant-engine/app/instruments/`
- `services/quant-engine/app/datasets/`
- `services/quant-engine/app/strategies/`
- `services/quant-engine/app/backtests/`
- `services/quant-engine/app/overlay/`
- `services/quant-engine/app/services/backtest_engine_service.py`
- `services/quant-engine/app/api/routes/backtests.py`

The starter research path now also includes:

- local sample daily futures bars in `services/quant-engine/app/datasets/sample_data.py`
- a strategy interface in `services/quant-engine/app/strategies/base.py`
- first implementation slots in:
  - `services/quant-engine/app/strategies/book_trend_breakout.py`
  - `services/quant-engine/app/strategies/book_ma_filter.py`

This is still a lightweight foundation, but it now exercises real bars, strategy signals, backtest orchestration, and overlay preview generation through one connected path.

## Recommended Domain Objects

The current schema set should expand with first-class research entities.

Portfolio-side entities remain important:

- `ImportedPortfolioSnapshot`
- `LedgerRecord`
- `PositionLot`
- `DailyPortfolioState`

Add research-side entities:

- `Instrument`
- `FuturesContract`
- `ContinuousSeriesSpec`
- `BarRecord`
- `StrategyDefinition`
- `StrategyParameter`
- `StrategySignal`
- `BacktestConfig`
- `BacktestTrade`
- `BacktestPosition`
- `BacktestEquityPoint`
- `BacktestRun`
- `StrategyAllocation`
- `OverlayRun`

## Data Model Direction

### Imported Portfolio Data

Keep the imported portfolio flow deterministic and audit-friendly:

- broker input
- importer normalization
- canonical ledger
- holdings / cash / lots reconstruction
- imported-portfolio analytics

### Research Data

Strategy research needs a different dataset layer:

- bar series, ideally local and queryable
- futures contract metadata
- continuous contract logic
- explicit roll assumptions
- persistent result outputs for comparison and reproducibility

DuckDB + Parquet remains a strong fit for this phase.

## Futures-Specific Requirements

To support strategies from futures trading books, the platform will need explicit futures features:

- contract root and expiry
- tick size
- multiplier / point value
- exchange calendar awareness later
- continuous series construction
- roll logic
- notional sizing
- margin-aware reporting

The current market-data service is still mainly symbol-price oriented and should not be treated as sufficient for serious futures research.

## Execution Model Recommendation

Use two layers for research execution:

### 1. Fast Research Prototype Layer

Optional, temporary:

- use `vectorbt` or similarly lightweight vectorized tools for quick strategy translation and parameter checks

Benefits:

- faster first implementation of book ideas
- easier parameter sweeps during discovery

Constraint:

- do not let this become the permanent domain model for futures backtesting

### 2. Deterministic Core Backtest Layer

Build a thin custom engine for the project’s actual product logic:

- contract handling
- rolling logic
- fees and slippage
- notional exposure
- margin-aware reporting
- combined overlay analysis

This should become the long-term core once strategy requirements stabilize.

## UI Workspaces Direction

The desktop app should eventually separate these workspaces more clearly:

- `Import`
  - broker ingestion, reconciliation, canonical ledger inspection
- `Portfolio`
  - imported holdings, allocation, performance, audit views
- `Research`
  - strategy catalog, parameter editing, dataset selection
- `Backtests`
  - runs, comparisons, equity curves, trade stats
- `Overlay`
  - combine real portfolio with one or more strategy sleeves

## Recommended Near-Term Build Order

1. instrument resolution layer
2. local market data cache
3. strategy and backtest domain schemas
4. instrument master with futures contract metadata
5. daily-bar dataset pipeline
6. continuous futures series builder
7. first strategy from the book on daily bars
8. backtest result API and UI
9. overlay analysis between imported portfolio and strategy results

## Guardrails

- keep the app local-first
- keep the frontend thin on finance logic
- keep imported portfolio truth separate from hypothetical backtests
- keep LLM features explanatory, never authoritative for calculations
- prefer deterministic and auditable strategy implementations over opaque convenience logic

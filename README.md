# Portfolio Tracker and Research Workbench

Standalone investments portfolio tracker, backtester, and portfolio research app with local analytics and LLM-assisted workflows.

## Recommended Repo Structure

This repo should stay as a monorepo, but only split where responsibilities are clearly different.

```text
portfolio/
  README.md
  apps/
    desktop/                # Tauri shell + React UI
  services/
    quant-engine/           # Python API for ingestion, factors, analytics, backtests
  packages/
    ui/                     # Shared UI components, charts, tables, tokens
    shared-types/           # TS schemas for portfolios, backtests, API payloads
    prompts/                # Versioned system prompts / templates for LLM features
  data/
    raw/                    # FMP cache, original API payload snapshots if needed
    curated/                # Cleaned parquet datasets
    duckdb/                 # Local analytics database files
    exports/                # User exports, reports, backtest outputs
  docs/                     # Keep light; add only stable docs
  scripts/                  # Bootstrap, sync, migration, maintenance scripts
  tests/
    e2e/                    # App-level tests
    fixtures/               # Sample market data and portfolios
```

## Folder Responsibilities

- `apps/desktop`
  - portfolio dashboard, holdings, rebalancing UI, charts, LLM chat
  - stack: `Tauri`, `React`, `TypeScript`, `Vite`
- `services/quant-engine`
  - FMP ingestion, caching, normalization, signals, analytics, backtesting
  - stack: `FastAPI`, `Polars`, `DuckDB`, `NumPy`, `cvxpy`
- `packages/shared-types`
  - keep the frontend and Python service aligned through shared schemas
- `packages/prompts`
  - useful once LLM features exist; keeps prompts versioned and testable
- `data/`
  - local-first storage, no cloud dependency required for normal use

## Suggested Internal Layout

### `apps/desktop`

```text
apps/desktop/
  src/
    app/
    features/
      portfolio/
      backtest/
      market-data/
      llm/
      settings/
    components/
    lib/
    hooks/
    stores/
    routes/
```

Use feature-first organization so holdings and backtest logic do not get mixed into generic folders too early.

### `services/quant-engine`

```text
services/quant-engine/
  app/
    api/                    # FastAPI routes
    core/                   # settings, logging, config
    clients/                # FMP client, LLM provider adapters
    ingestion/              # fetch + cache + normalize market data
    datasets/               # parquet/duckdb dataset builders
    factors/                # momentum, value, quality, volatility, etc.
    models/                 # portfolio construction models
    backtests/              # simulation engine and metrics
    analytics/              # attribution, drawdown, exposures, reports
    schemas/                # Pydantic request/response models
    importers/              # broker statement importers
    tests/
```

Keep `models/` separate from `backtests/` so portfolio construction and simulation do not become tightly coupled.

## Portfolio Import Direction

Portfolio data should support both manual entry and broker imports from the start.

The first broker import should be `Interactive Brokers` statement files.

- import should normalize statements into the same transaction ledger used by manual entries
- keep imported raw records for auditability and parser debugging
- treat broker-specific parsing as an adapter layer, not core portfolio logic
- support extending later for other brokers without changing the portfolio domain model

## Backtesting Engine Options

### `vectorbt`

- best fit for fast research and portfolio-level simulations
- great with pandas/NumPy style vectorized workflows
- strong for parameter sweeps, signals research, factor experiments, ranking systems
- easier to connect with `PyPortfolioOpt`, `cvxpy`, `Polars`-to-pandas bridges, and custom analytics
- weaker when you need highly realistic event-driven order handling or broker simulation

### `backtrader`

- stronger for event-driven strategy simulation and order lifecycle modeling
- useful for classic trading-system workflows with bars, orders, fills, commissions, slippage
- older ecosystem and heavier framework feel
- less attractive for modern portfolio research across many assets and repeated allocation replay runs
- slower and more rigid for large-scale cross-sectional screening work

### Custom Engine

- best long-term control if you need exact portfolio rules, tax logic, cash flows, rebalancing schedules, and explainable accounting
- higher upfront cost and more validation burden
- ideal once your product rules become more important than generic strategy framework features

## Recommendation

Use a phased approach:

1. Start with `vectorbt` for research speed and faster MVP delivery.
2. Build your own thin domain layer around portfolios, constraints, transactions, and reports.
3. Add a custom backtest core for portfolio accounting only when product rules outgrow `vectorbt`.
4. Do not start with `backtrader` unless realistic trade execution simulation is the main product.

For this project, the likely path is:

- portfolio tracker + factor research + fast replay workflows -> `vectorbt` first
- institutional-grade accounting / tax lots / complex rebalance rules -> custom engine later
- intraday execution simulator / broker-style order events -> consider `backtrader` or custom event engine

## Recommended Model Stack

Early models to support in `services/quant-engine/app/models/`:

- equal weight
- minimum volatility
- risk parity
- Black-Litterman
- momentum ranking
- quality/value composite ranking

Keep these deterministic. Let the LLM explain, filter, and propose constraints, but not directly own allocations.

## Practical MVP Direction

Build in this order:

1. FMP ingestion + local cache
2. portfolio tracker and transaction ledger
3. historical performance and benchmark comparison
4. `vectorbt`-based backtests
5. allocation replay and backtest workflows
6. LLM assistant for explanation and portfolio change proposals

## Current Starter Implementation

- desktop frontend scaffolded in `apps/desktop`
- local quant API scaffolded in `services/quant-engine/app/api/main.py`
- first Interactive Brokers PDF import endpoint available at `POST /portfolios/import/interactive-brokers`
- first parser implemented against `docs/U8516450_2025_2025.pdf`
- FMP API configuration now loads from `services/quant-engine/.env`
- the import endpoint can now return reconciliation, holdings timeline, and benchmark comparison without DB persistence
- FMP responses now use a local file cache in `data/raw/fmp-cache` with TTLs tuned for quotes vs historical prices

## Current Architecture Direction

The repo is in an active refactor away from one monolithic import-time analysis payload toward narrower engine and UI contracts.

- `PortfolioSnapshot` is the persisted truth for local portfolio workspaces and immutable saved variants
- exposure, diagnostics, dashboard, and backtest baseline views are being split into narrower concern-specific contracts
- the desktop app should project import bootstrap results into these narrower contracts immediately rather than passing a broad upload-time payload through the UI
- historical diagnostics must require history context; if it is missing, the UI should show unavailable rather than approximate from a static snapshot
- financially meaningful formulas must be documented with both the methodology used and the code location that implements them, so financial-accuracy review can trace every calculation quickly

Canonical roadmap for this refactor lives in `docs/roadmap.md`.

## Run Frontend And Backend Together

Use the repo helper to run both dev servers with prefixed logs in one terminal:

```bash
python scripts/run_dev.py
```

Checks only:

```bash
python scripts/run_dev.py --check
```

This starts:

- backend on `127.0.0.1:8000`
- frontend on `127.0.0.1:5173`

Why this is useful:

- one command for daily development
- backend and frontend logs stay visible together
- easier to stop both services with one `Ctrl+C`

## Manage FMP Cache

List cached FMP entries:

```bash
python scripts/manage_cache.py list
```

Clear all cached FMP entries:

```bash
python scripts/manage_cache.py clear
```

Clear one cache namespace only:

```bash
python scripts/manage_cache.py clear --namespace quote
```

Namespaces:

- `quote`
- `history`
- `fx`

## OpenCode Handoff Workflow

Use the repo-root handoff files to coordinate across OpenCode sessions without external services.

- `opencode-status.md`
  - current session state
  - what changed
  - what remains
  - how the work was validated
- `opencode-next-ticket.md`
  - the single best next ticket for the next session to pick up
- `scripts/opencode_handoff.py`
  - optional validator for required headings

### Session Workflow

1. Start a session by reading `opencode-status.md` and `opencode-next-ticket.md`.
2. If `opencode-status.md` shows `done`, `ready for review`, or an outdated task, treat `opencode-next-ticket.md` as the next unit of work.
3. Change `opencode-status.md` to reflect the active task, owner/session name, status, files changed, and risks as work progresses.
4. When implementation is complete, update:
   - `Status`
   - `What Was Completed`
   - `Remaining Work`
   - `Validation Run`
   - `Recommended Next Step`
   - `Last Updated Timestamp`
5. Replace `opencode-next-ticket.md` with the next best ticket before ending the session.

### Monitoring / Review Flow

A monitoring OpenCode session can determine completion quickly by checking:

- `opencode-status.md`
  - `Status` is `ready for review` or `done`
  - `Validation Run` shows passing checks
  - `Remaining Work` is empty or explicitly non-blocking
- `opencode-next-ticket.md`
  - contains a fresh next task rather than the just-finished task

If the work is complete, the monitoring session should:

1. review the changed files noted in `Files Changed`
2. rerun the listed validation steps if needed
3. update `Status` to `done` if the result is acceptable
4. start the next ticket from `opencode-next-ticket.md`

### Optional Validation Command

Run this from the repo root to confirm the handoff files still contain all required headings:

```bash
python scripts/opencode_handoff.py validate
```

This script is intentionally minimal and adds no dependencies.

## OpenCode Skills

This repo also keeps local reusable OpenCode skill definitions in `.opencode/skills/`.

- Current skill library index: `.opencode/skills/README.md`
- Current analytics guard skill: `.opencode/skills/portfolio-analytics-guard.md`

Use case:

- recurring repo-specific workflows that should be applied consistently across sessions
- especially useful for analytics, schema-sync, import workflows, and frontend polish rules

Current note:

- the repo stores these as local skill-definition files
- if runtime skill registration is not available in the current OpenCode environment, ask the agent to follow the relevant file explicitly

## Decision Snapshot

- desktop shell: `Tauri`
- frontend: `React` + `TypeScript`
- analytics engine: `Python`
- local analytics store: `DuckDB` + `Parquet`
- first backtest engine: `vectorbt`
- later extension path: custom portfolio engine

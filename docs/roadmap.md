# Engine Refactor Roadmap

This roadmap replaces the older generic roadmap and becomes the working plan for the portfolio-engine refactor.

The target architecture is:

- `ImportEngine` produces `PortfolioSnapshot` plus optional `PortfolioHistoryContext`
- `ExposureEngine` accepts `PortfolioSnapshot` and returns exposure data for UI rendering
- `DiagnosticsEngine` accepts `PortfolioSnapshot` plus optional `PortfolioHistoryContext`
- `BacktestEngine` accepts explicit portfolio or strategy inputs and returns backtest results
- the UI consumes engine outputs and does not synthesize financial analytics locally

## Principles

1. `PortfolioSnapshot` is the persisted truth for saved portfolio variants.
2. Historical diagnostics must require `PortfolioHistoryContext`.
3. If required history is missing, engines return `unavailable` rather than approximate silently.
4. Engine outputs are derived artifacts, not persisted truth.
5. Routes stay thin and delegate to engine services.
6. UI should never patch financial outputs by hand.

## Current Problem Summary

The project currently has a mixed architecture:

- import, exposure, diagnostics, and parts of backtest behavior were historically concentrated around one broad import-time analysis service before the engine split
- the frontend is moving toward `PortfolioSnapshot`, but backend engine boundaries are still blurred
- static-snapshot reanalysis is not equivalent to historically faithful imported analysis for rolling diagnostics
- this caused real accuracy bugs, including mismatched 20d `QQQ`/Growth values between broad import-time analysis and snapshot analysis

## Target Backend Modules

### 1. Import Engine

Purpose:

- read broker statements
- normalize imported records
- build canonical snapshot
- build optional history context

Target files:

- `services/quant-engine/app/services/import_engine.py`
- `services/quant-engine/app/services/import_engine_composer.py`
- `services/quant-engine/app/services/benchmark_service.py`
- `services/quant-engine/app/services/statement_importer.py`
- `services/quant-engine/app/services/history_context_builder.py`

Primary outputs:

- `PortfolioSnapshot`
- `PortfolioHistoryContext`
- `ImportMetadata`

### 2. Exposure Engine

Purpose:

- current holdings-based exposure only
- look-through constituent exposure
- sector exposure
- overlap
- current factor snapshot
- current concentration and current-state risk decomposition if supported

Target files:

- `services/quant-engine/app/services/exposure_engine.py`
- `services/quant-engine/app/schemas/exposure.py`

Allowed input:

- `PortfolioSnapshot`
- optional engine context such as benchmark or symbol overrides

Must not depend on:

- imported statement history for basic current exposure

### 3. Diagnostics Engine

Purpose:

- rolling risk
- rolling factor loadings
- volatility regime
- historical benchmark sensitivity
- risk path and other history-based diagnostics

Target files:

- `services/quant-engine/app/services/diagnostics_engine.py`
- `services/quant-engine/app/schemas/diagnostics.py`

Required rule:

- historical sections require `PortfolioHistoryContext`
- if absent, return `unavailable`

### 4. Backtest Engine

Purpose:

- strategy backtests
- portfolio allocation replay
- future portfolio-variant replay or compare workflows

Target files:

- `services/quant-engine/app/services/backtest_engine.py`
- `services/quant-engine/app/schemas/backtest_engine.py`

Important:

- do not couple this engine to a broad import-time analysis response object

## Target API Shape

### Import

- `POST /portfolio/import/upload`
- `POST /portfolio/import/path`

Response:

- `snapshot`
- `history_context_ref` or inline `history_context` for local mode
- `import_metadata`

### Exposure

- `POST /engines/exposure/run`

Request:

- `snapshot`
- `engine_context`

Response:

- `ExposureResult`

### Diagnostics

- `POST /engines/diagnostics/run`

Request:

- `snapshot`
- optional `history_context_ref`
- `engine_context`

Response:

- `DiagnosticsResult`

### Backtest

- `POST /engines/backtest/run`

Request:

- explicit strategy or replay request
- optional `snapshot`
- optional benchmark and date context

Response:

- `BacktestResult`

## Frontend Target Shape

### Portfolio Workspace

The workspace model remains the correct direction:

- `PortfolioWorkspace`
- `PortfolioNode`
- `WorkingDraft`
- `PortfolioSnapshot`

### Frontend Responsibilities

Frontend should do only these things:

- persist local snapshot variants
- select active snapshot or draft
- call engine endpoints
- render engine responses

Frontend must not:

- synthesize financial risk or exposure outputs
- patch broad upload-time analysis objects locally
- infer historical diagnostics from a static snapshot

### Current Frontend Status

The desktop app has now made meaningful progress on the contract split:

- `ExposurePanel` consumes a dedicated `ExposureAnalysis` contract derived from exposure and diagnostics engine outputs
- `DiagnosticsPanel` consumes `DiagnosticsEngineResponse` directly and renders an unavailable state when historical sections require missing history context
- `DashboardPanel` consumes `DashboardAnalysis` instead of a broad import-time analysis payload
- backtest baseline seeding consumes `PortfolioBaselineView`
- import-upload flows are projected immediately into narrower imported contracts for dashboard, exposure, diagnostics, baseline, snapshot, and factor-model concerns
- local workspace persistence keeps `PortfolioSnapshot` as truth while engine outputs remain derived runtime artifacts

This means the remaining frontend work is no longer the original exposure/diagnostics split. The remaining work is concentrated in:

- finishing backend import/exposure/diagnostics engine extraction
- replacing the remaining broad upload-time response decode with dedicated import-engine contracts
- continuing to shrink large test fixtures and any residual monolithic-type coupling

## Execution Plan

### Stage 1. Canonical Engine Contracts

Goal:

- define explicit request/response schemas for each engine

Tasks:

- create `PortfolioSnapshot` backend schema to match frontend canonical shape
- create `PortfolioHistoryContext` backend schema
- create `ExposureResult`, `DiagnosticsResult`, and `BacktestResult`
- stop using one oversized import-time analysis payload as the shared contract for everything

Exit criteria:

- engine contracts exist in dedicated schema files
- no new feature work extends the monolithic import-time analysis response

### Stage 2. Exposure Engine Extraction

Goal:

- make Exposure a true snapshot-in/service-out flow

Tasks:

- move look-through, overlap, sector exposure, factor exposure, and current factor snapshot logic into `exposure_engine.py`
- add `/engines/exposure/run`
- update frontend `ExposurePanel` path to call the new exposure engine adapter
- remove remaining exposure-specific dependence on broad import-time analysis contracts

Exit criteria:

- Exposure tab uses `ExposureResult`
- fresh import, saved node, and draft all use the same exposure engine contract

Status note:

- `ExposurePanel` is already running through the dedicated exposure route and `ExposureAnalysis` bridge
- `services/quant-engine/app/services/exposure_engine.py` and `/engines/exposure/run` are in place
- remaining work is contract hardening, route/engine coverage expansion, and removal of residual monolithic import-time analysis assumptions

### Stage 3. Diagnostics Engine Extraction

Goal:

- separate current snapshot exposure from historical diagnostics

Tasks:

- move rolling risk, rolling factor loadings, volatility regime, and related diagnostics into `diagnostics_engine.py`
- require `PortfolioHistoryContext` for historical sections
- return structured `unavailable` sections when no history context exists
- update `DiagnosticsPanel` and history-heavy parts of `ExposurePanel` to consume diagnostics-engine responses

Exit criteria:

- historical metrics are never silently approximated from a static snapshot
- current and historical analytics are clearly separated

Status note:

- `DiagnosticsPanel` is already running through dedicated diagnostics contracts
- unavailable-state handling is already in place for missing history context
- backend-side dedicated diagnostics contracts are in place
- import/history-context plumbing is now present on both backend and desktop persistence
- dashboard historical restore now has a dedicated `dashboard-history` engine path
- remaining work is coverage expansion plus cleanup of remaining approximation boundaries and contract edges

### Stage 4. Import Engine Extraction

Goal:

- reduce import to import-only concerns

Tasks:

- keep import orchestration in a dedicated `import_engine.py` module with import-only responsibilities
- make import routes return snapshot plus history context metadata
- keep statement importer and broker-specific parsing behind import-engine boundaries
- preserve upload-path accuracy for imported base portfolios

Exit criteria:

- import route no longer acts as the master analytics route
- imported base workflow has explicit historical context available for diagnostics

Status note:

- frontend import handling now consumes a bootstrap-only import response and immediately hands off analytics recomputation to engine routes
- persistence and workspace creation now depend on import bootstrap data plus persisted history context rather than any broad upload-time analytics payload
- import upload responses now return only the imported base bootstrap needed for workspace creation
- fresh import and restore both recompute dashboard history via the dedicated dashboard-history engine path
- workspace persistence now keeps the imported snapshot needed for accurate dashboard-history replay on restore
- imported dashboard-history replay now reconciles its terminal state to broker statement totals so ending value matches the statement
- snapshot-only dashboard-history requests degrade to `unavailable` rather than fabricating historical values from end-state holdings
- snapshot-only exposure still renders current-state look-through data, while the frontend now explicitly labels historical diagnostics as unavailable instead of showing a confusing near-empty view
- exposure engine coverage now includes deterministic tests against real `IB2026.pdf`, `FF2026.pdf`, and `ESPP2026.pdf` snapshots plus a rolling-regression calibration test for the core loading math
- workspace lineage is now surfaced consistently in Dashboard and Exposure as `base`, `base -> variant`, and `Working Draft · <active lineage>`
- Dashboard `Add Statement` now creates an immutable imported child snapshot under `base` instead of mutating the existing imported workspace; imported child nodes are named `{short broker} {statement end date}` such as `IB 2026-04-08`
- diagnostics now supports a history-aware snapshot path, so saved variants and working drafts can render rolling factor/risk sections when workspace history context is available
- variant/draft historical diagnostics currently use a stable snapshot-history approximation rather than broker-truth replay, which is sufficient for usable rolling factor/risk views but still distinct from imported-base history
- opening or selecting nodes from Dashboard/Exposure no longer overwrites the rich dashboard analysis state with an exposure-only shell
- the desktop now exposes a hard `Reset Local DB` action that deletes the IndexedDB workspace database for maximum local-state recovery
- backend import bootstrap orchestration now lives in `import_engine.py`, with bootstrap response assembly in `import_engine_composer.py`
- shared benchmark summary assembly used by dashboard history now lives in neutral `benchmark_service.py`
- import-side history window and `PortfolioHistoryContext` derivation now live in dedicated `history_context_builder.py`
- dashboard sector classification now maps `SXRV` / Nasdaq-100 style holdings to `Technology` instead of `Broad Market`, so Dashboard better reflects concentration risk
- the repository now has a single Python test runner at `scripts/run_all_tests.py` that regenerates dashboard goldens for both `IB2026.pdf` and `FF2026.pdf`, runs the full backend suite, and runs the full desktop suite
- Dashboard now has generated desktop golden-data paths for both `IB2026.pdf` and `FF2026.pdf`: backend tests validate imported overview/history against broker-truth expectations, desktop tests consume generated TypeScript golden fixtures derived from live backend outputs, and App-level restore/open-node regressions verify the same canonical values survive orchestration flows for both brokers
- the current Dashboard accuracy contract is now explicit: imported nodes may show broker-truth history, while snapshot-only/variant flows must be correct or render `unavailable` rather than plausible fabricated history
- Dashboard range-derived financial values now flow from backend `range_metrics` rather than parallel UI recomputation, so `start value`, `MWR`, `drawdown`, and monthly returns render from engine output or `n/a` when the backend does not provide trustworthy metrics
- desktop Dashboard coverage now includes account/statement fallback states, empty draft allocation states, imported-base restore, imported child-snapshot open, variant-to-base switching, and imported-child-variant restore with unavailable history enforcement
- generated dashboard goldens are now deterministic across runs, with stable normalized import timestamps to avoid timestamp-only diffs
- diagnostics `availability.history_context_required` is now treated as a requirement flag, not a presence flag: it stays `true` for both available and unavailable historical diagnostics because those sections fundamentally depend on history context
- backend route coverage now explicitly includes mixed-broker import bootstrap history-context merging plus mixed-broker imported `dashboard-history` and `diagnostics` engine paths under mocked market data
- backend route coverage now explicitly checks malformed or incomplete imported-history payloads degrade to `unavailable` for both `dashboard-history` and `diagnostics` instead of fabricating history from empty imported inputs
- imported engine routes now also degrade to `unavailable` when benchmark history or symbol market-data support is effectively missing, rather than returning plausible-looking but unsupported historical outputs

### Stage 5. Backtest Engine Refactor

Goal:

- make backtests consume explicit inputs instead of mixed UI/import blobs

Tasks:

- split current strategy backtests and allocation replay into explicit engine requests
- allow future portfolio variant replay against a given snapshot
- keep backtest outputs separate from exposure and diagnostics outputs

Exit criteria:

- backtest routes consume dedicated requests only
- no backtest logic depends on the monolithic import-time analysis response

Status note:

- backtest contracts now live in dedicated `services/quant-engine/app/schemas/backtest_engine.py`
- the route-owned `BacktestRequest` has been retired into engine-owned schemas
- portfolio-allocation replay now builds explicit synthetic imported snapshots directly in `portfolio_backtest_engine.py` rather than routing through the shared snapshot builder
- portfolio-allocation diagnostics now assemble explicit replay-derived inputs (`synthetic_snapshot`, `replay_daily_states`) separately from historical market-data inputs (`benchmark_price_history`, `factor_price_histories`)
- backtest diagnostics snapshots now carry typed provenance so the UI can distinguish synthetic replay snapshot basis from external historical market-data basis

### Stage 6. Local Derived Result Cache

Goal:

- preserve accuracy while keeping snapshot as truth

Tasks:

- add optional local cache keyed by:
  - `engine_name`
  - `snapshot_hash`
  - `history_context_hash`
  - `engine_context_hash`
- cache imported base-node diagnostics that require history context
- keep cache invalidation explicit and safe

Exit criteria:

- imported root nodes can reopen with accurate historical diagnostics without redefining persisted truth

## Immediate Refactor Order

1. expand route-level and engine-level coverage for `dashboard-history`, `diagnostics`, and `exposure`, especially unavailable-state behavior and imported-history replay correctness
2. remove the remaining residual monolithic import-time analysis assumptions and stale wording across code/docs
3. proceed with backtest engine cleanup against explicit snapshot/history inputs
4. add a local derived-result cache only after correctness contracts are locked

## Documentation Cleanup Plan

Do not aggressively delete docs before replacement exists. Instead:

### Keep and update

- `docs/roadmap.md`
- `docs/dashboard-field-inventory.md`
- `README.md`
- `services/quant-engine/README.md`
- `apps/desktop/src/features/portfolio/README.md`

### Review for rewrite or retirement after Stage 2-4

- `docs/architecture.md`
- `docs/mvp-data-flow.md`
- `docs/strategy-research-architecture.md`
- any README that still describes broad import-time analysis as the primary architecture

### Cleanup rules

- remove docs that describe flows that no longer exist
- prefer one current architecture doc over many partially stale docs
- keep historical design notes only if explicitly labeled as archived

## Implementation Guardrails

- no more frontend financial patching for exposure or diagnostics
- no more hidden historical approximations from snapshot-only inputs
- routes remain thin
- every engine gets direct unit tests plus one route-level integration test
- any metric shown in UI must be traceable to one engine response field
- every Dashboard value should be traceable further: UI field -> app state -> adapter/engine response -> snapshot/import source -> statement truth or explicit `unavailable`
- financially meaningful formulas must be documented with their methodology and implementation location; if a formula changes, update both code-level methodology text and the relevant accuracy docs/tests
- `docs/exposure-field-inventory.md` should stay aligned with actual Exposure formulas, truth classes, and degraded/unavailable semantics
- `docs/backtest-field-inventory.md` should stay aligned with actual replay metrics, diagnostics provenance, comparison semantics, and implementation assumptions
- `docs/IB2026.pdf` is the current canonical broker-truth fixture for Dashboard financial accuracy work
- `docs/FF2026.pdf` is the current Freedom24 broker-truth fixture for 2026 YTD validation and mixed-broker coverage; longer Freedom24 history exists beyond 2026, but `FF2026.pdf` is the main local fixture in active test use today

## Current Known Accuracy Rule

Until the refactor is complete:

- imported nodes can render historically accurate broker-truth outputs through dedicated imported engine routes
- snapshot-only reanalysis is valid for current exposure
- snapshot-only or variant historical outputs are not valid unless they are explicitly trustworthy, explicitly approximate, or marked unavailable

## Current Frontend Contract Inventory

Current desktop contracts in active use:

- `DashboardAnalysis`
- `ExposureAnalysis`
- `DiagnosticsEngineResponse`
- `PortfolioBaselineView`
- import-only source projections for dashboard, exposure, diagnostics, baseline, snapshot, and factor-model flows

This is the intended direction. New frontend work should extend these narrow contracts rather than reintroducing broad upload-time analysis dependencies.

Current imported-upload contract status:

- import routes now return a bootstrap-only response containing:
  - `snapshot`
  - `overview`
  - `risk_summary`
  - `history_context`
- desktop import mapping uses that bootstrap payload only for workspace creation and initial snapshot normalization
- exposure, diagnostics, and dashboard history are recomputed through dedicated engine routes for both fresh import and restore
- restore/open-node flows follow the same recomputation model rather than reviving a broad upload-time analysis blob

## What To Implement Next

When implementation resumes, start here:

1. continue route-level and engine-level coverage for `dashboard-history`, `exposure`, and `diagnostics`, especially around unavailable-state behavior for snapshot/history-context flows and imported-history replay correctness
2. remove any remaining residual monolithic import-time analysis assumptions in contracts, adapters, and docs
3. proceed with backtest engine cleanup against explicit snapshot/history inputs after Dashboard correctness contracts are locked
4. add a local derived-result cache keyed by snapshot and history context only after correctness contracts are locked

Current backend naming status:

- legacy `import_analysis.py` and `import_analysis_composer.py` names have been retired
- import-side bootstrap code now uses import-engine naming consistently

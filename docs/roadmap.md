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

- import, exposure, diagnostics, and parts of backtest behavior were historically concentrated around one import-analysis service before the engine split
- the frontend is moving toward `PortfolioSnapshot`, but backend engine boundaries are still blurred
- static-snapshot reanalysis is not equivalent to historically faithful imported analysis for rolling diagnostics
- this caused real accuracy bugs, including mismatched 20d `QQQ`/Growth values between import analysis and snapshot analysis

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

- do not couple this engine to the import-analysis response object

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
- patch `AnalysisResponse` objects locally
- infer historical diagnostics from a static snapshot

### Current Frontend Status

The desktop app has now made meaningful progress on the contract split:

- `ExposurePanel` consumes a dedicated `ExposureAnalysis` contract derived from exposure and diagnostics engine outputs
- `DiagnosticsPanel` consumes `DiagnosticsEngineResponse` directly and renders an unavailable state when historical sections require missing history context
- `DashboardPanel` consumes `DashboardAnalysis` instead of a full import-analysis payload
- backtest baseline seeding consumes `PortfolioBaselineAnalysis`
- import-upload flows are projected immediately into narrower imported contracts for dashboard, exposure, diagnostics, baseline, snapshot, and factor-model concerns
- local workspace persistence keeps `PortfolioSnapshot` as truth while engine outputs remain derived runtime artifacts

This means the remaining frontend work is no longer the original exposure/diagnostics split. The remaining work is concentrated in:

- finishing backend import/exposure/diagnostics engine extraction
- replacing the remaining upload-time `AnalysisResponse` decode with dedicated import-engine contracts
- continuing to shrink large test fixtures and any residual monolithic-type coupling

## Execution Plan

### Stage 1. Canonical Engine Contracts

Goal:

- define explicit request/response schemas for each engine

Tasks:

- create `PortfolioSnapshot` backend schema to match frontend canonical shape
- create `PortfolioHistoryContext` backend schema
- create `ExposureResult`, `DiagnosticsResult`, and `BacktestResult`
- stop using one oversized import-analysis payload as the shared contract for everything

Exit criteria:

- engine contracts exist in dedicated schema files
- no new feature work extends the monolithic import-analysis response

### Stage 2. Exposure Engine Extraction

Goal:

- make Exposure a true snapshot-in/service-out flow

Tasks:

- move look-through, overlap, sector exposure, factor exposure, and current factor snapshot logic into `exposure_engine.py`
- add `/engines/exposure/run`
- update frontend `ExposurePanel` path to call the new exposure engine adapter
- remove remaining exposure-specific dependence on `ImportAnalysisResponse`

Exit criteria:

- Exposure tab uses `ExposureResult`
- fresh import, saved node, and draft all use the same exposure engine contract

Status note:

- frontend bridge largely complete
- backend extraction and canonical import contract are still pending

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

- frontend bridge largely complete
- unavailable-state handling is already in place for missing history context
- backend-side dedicated diagnostics contracts are in place
- import/history-context plumbing is now present on both backend and desktop persistence
- dashboard historical restore now has a dedicated `dashboard-history` engine path

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
- diagnostics now supports a history-aware snapshot path, so saved variants and working drafts can render rolling factor/risk sections when workspace history context is available
- variant/draft historical diagnostics currently use a stable snapshot-history approximation rather than broker-truth replay, which is sufficient for usable rolling factor/risk views but still distinct from imported-base history
- opening or selecting nodes from Dashboard/Exposure no longer overwrites the rich dashboard analysis state with an exposure-only shell
- the desktop now exposes a hard `Reset Local DB` action that deletes the IndexedDB workspace database for maximum local-state recovery
- backend import bootstrap orchestration now lives in `import_engine.py`, with bootstrap response assembly in `import_engine_composer.py`
- shared benchmark summary assembly used by dashboard history now lives in neutral `benchmark_service.py`
- import-side history window and `PortfolioHistoryContext` derivation now live in dedicated `history_context_builder.py`

### Stage 5. Backtest Engine Refactor

Goal:

- make backtests consume explicit inputs instead of mixed UI/import blobs

Tasks:

- split current strategy backtests and allocation replay into explicit engine requests
- allow future portfolio variant replay against a given snapshot
- keep backtest outputs separate from exposure and diagnostics outputs

Exit criteria:

- backtest routes consume dedicated requests only
- no backtest logic depends on the monolithic import-analysis response

Status note:

- backtest contracts now live in dedicated `services/quant-engine/app/schemas/backtest_engine.py`
- the route-owned `BacktestRequest` has been retired into engine-owned schemas
- portfolio-allocation replay now builds synthetic portfolios through the shared snapshot builder instead of hand-building import-shaped snapshots inline

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

1. engine schemas
2. exposure engine extraction
3. diagnostics engine extraction
4. import engine extraction
5. frontend adapters per engine
6. backtest engine cleanup
7. local derived-result cache

## Documentation Cleanup Plan

Do not aggressively delete docs before replacement exists. Instead:

### Keep and update

- `docs/roadmap.md`
- `README.md`
- `services/quant-engine/README.md`
- `apps/desktop/src/features/portfolio/README.md`

### Review for rewrite or retirement after Stage 2-4

- `docs/architecture.md`
- `docs/mvp-data-flow.md`
- `docs/strategy-research-architecture.md`
- any README that still describes import-analysis as the primary architecture

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

## Current Known Accuracy Rule

Until the refactor is complete:

- imported upload analysis can be historically accurate
- snapshot-only reanalysis is valid for current exposure
- snapshot-only reanalysis is not valid for full historical diagnostics unless explicitly marked as unavailable or approximation

## Current Frontend Contract Inventory

Current desktop contracts in active use:

- `DashboardAnalysis`
- `ExposureAnalysis`
- `DiagnosticsEngineResponse`
- `PortfolioBaselineAnalysis`
- import-only source projections for dashboard, exposure, diagnostics, baseline, snapshot, and factor-model flows

This is the intended direction. New frontend work should extend these narrow contracts rather than reintroducing broad `AnalysisResponse` dependencies.

Current imported-upload contract status:

- import routes now return a bootstrap-only response containing:
  - `snapshot`
  - `overview`
  - `risk_summary`
  - `history_context`
- desktop import mapping uses that bootstrap payload only for workspace creation and initial snapshot normalization
- exposure, diagnostics, and dashboard history are recomputed through dedicated engine routes for both fresh import and restore

## What To Implement Next

When implementation resumes, start here:

1. continue route-level and engine-level test coverage for `dashboard-history`, `exposure`, and `diagnostics`
2. proceed with backtest engine cleanup against explicit snapshot/history inputs
3. add a local derived-result cache keyed by snapshot and history context
4. keep trimming legacy-shaped test fixtures so they reflect engine-based runtime contracts

Current backend naming status:

- legacy `import_analysis.py` and `import_analysis_composer.py` names have been retired
- import-side bootstrap code now uses import-engine naming consistently

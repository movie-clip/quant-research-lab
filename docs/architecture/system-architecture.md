# Quant Research Lab Architecture

This document explains the current architectural seams and the future normalized direction.

For the canonical shipped-scope inventory, use `docs/product/current-product-state.md`.

## System Boundaries

The project is split into a desktop application and a local quant engine.

- `apps/desktop`
  - workflow UI, workspace state, charts, review flows, and research interaction
- `services/quant-engine`
  - deterministic finance and quant engines: imports, datasets, ranking, analytics, replay, monitoring

The desktop app should treat the quant engine as the source of truth for portfolio calculations.

## Product Architecture Direction

The target product is a local-first quant research lab.

Core engine families:
- truth and import engines
- portfolio intelligence engines
- quant ranking engines
- portfolio construction and replay engines
- overlay and monitoring engines

The system should prioritize:
- deterministic outputs
- explicit methodology
- truth-class clarity
- financial auditability

## Current Implemented Backend Seams

The backend already exposes several concrete engine seams that matter more than the older aspirational route sketch.

Documentation rule:
- treat this section as the current architectural seam map
- treat `docs/product/current-product-state.md` as the canonical shipped-state boundary
- keep future normalized API sketches clearly separate from current route reality

Current portfolio-improvement and replay seams:
- `POST /backtests/portfolio-allocation`
  - canonical allocation replay route for candidate-vs-reference comparison
- `POST /backtests/portfolio-allocation/replacement-intent-preview`
  - hypothetical replacement replay from draft snapshot plus replacement intent
- `POST /backtests/portfolio-allocation/replacement-intent-overlay-preview`
  - overlay-aware hypothetical replay for the narrow benchmark-trend overlay path
- `POST /backtests/candidate-formation/replacement-intent`
  - review-only same-weight single-replacement candidate formation
- `POST /backtests/candidate-construction/replacement-intent`
  - review-only single-replacement candidate construction with explicit rule selection

Current ranking seams:
- `POST /strategy-lab/etf-ranking`
  - generic ETF ranking
- `POST /ranking/etf-replacements`
  - intent-bound seeded ETF replacement ranking

Current diagnostics and exposure seams remain separately authoritative for current-state portfolio understanding.

Important implementation reality:
- `services/quant-engine/app/services/portfolio_backtest_engine.py` currently owns several related responsibilities: generic replay, hypothetical replay, overlay-aware replay, synthetic cash injection, and diagnostics comparison assembly
- this file is a real current seam, not just an implementation detail, and it should be documented as such until responsibilities are split more cleanly
- a legacy generic overlay preview path still exists in `services/quant-engine/app/services/backtest_engine_service.py` and `services/quant-engine/app/overlay/`; treat it as older infrastructure, not the canonical forward product seam
- candidate formation remains a narrow review-oriented seam layered on top of current single-replacement construction semantics, not a generalized construction platform boundary

## API Boundary

The frontend should not calculate portfolio state from raw transactions on its own. It should request normalized results from the quant engine.

Current direction:

- local workspace persistence is snapshot-first
- engine outputs are derived runtime artifacts
- the frontend may persist `PortfolioSnapshot` and workspace metadata locally, but it should not persist derived financial analytics as truth
- historical diagnostics must come from engine responses with appropriate history context, not from frontend approximation
- formed candidates, constructed candidates, hypothetical replays, overlay-aware replays, and saved proposals are review artifacts only and must not be treated as portfolio truth

Current implemented API groups:

- health and market-data sync/query routes
- import, reconciliation, and portfolio state routes
- exposure and diagnostics routes for current-state analytics
- backtest/replay routes for portfolio-improvement workflows
- strategy-lab and ranking routes for ETF research workflows

Future normalized API groups:

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
- `POST /strategy-lab/etf-ranking`

Architecture rule:

- docs should distinguish between current implemented route groups and future normalized route groups
- a future API sketch should not hide already-shipping seams like candidate construction, intent-bound replacement ranking, or overlay-aware replay

## Broker Import and Source-of-Truth Files

The project already has source-of-truth broker statement examples from:
- `IB2026.pdf`
- `FF2026.pdf`
- `ESPP2026.pdf`

These should be used as parser-layout and accounting-shape references.

Important rule:
- tests should rely on normalized extracted data shape and accounting semantics rather than exact binary file identity, because source PDFs may be re-exported over time

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

Recommended research-side and construction-side domain entities:
- `UniverseDefinition`
- `RankingSpec`
- `RankingRun`
- `ConstructionSpec`
- `ConstraintSet`
- `CandidatePortfolio`
- `AllocationReplayRun`
- `ImprovementRun`
- `OverlaySpec`
- `MonitorDefinition`

## Truth Classes

The project uses explicit truth classes when reasoning about financial outputs:

- `broker-truth historical diagnostics`
- `snapshot current-state analytics`
- `synthetic snapshot-history diagnostics`
- `replay-derived hypothetical outputs`

These must remain visibly distinct in both payloads and UI.

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
5. call dedicated engines for exposure, diagnostics, ranking, construction, replay, and monitoring as appropriate
6. send derived engine outputs to UI

### Ranking and construction

1. define investable universe
2. compute component scores
3. build ranked universe output
4. apply construction rules and constraints
5. produce candidate portfolio
6. replay candidate vs baseline
7. emit before/after diagnostics

Current narrow implemented path:

1. record draft-scoped replacement intent
2. optionally rank ETF replacements within the explicit peer group / seed context
3. derive candidate formation or candidate construction in the backend
4. replay baseline vs hypothetical candidate
5. optionally apply the narrow benchmark-trend overlay to the candidate only
6. emit replay metrics plus synthetic replay diagnostics comparison

## Backtest Diagnostics Provenance

Portfolio-allocation backtests now expose diagnostics provenance explicitly.

Current contract:

- synthetic replay snapshot basis: `synthetic_replay_snapshot`
- historical diagnostics basis: `market_data_history`

This means portfolio-improvement diagnostics are not imported broker-truth diagnostics. They are built from:

- a synthetic snapshot generated from the replay ending weights
- replay-derived daily states from the backtest equity curve
- external historical benchmark and factor market data

Implementation locations:

- typed provenance schema: `services/quant-engine/app/schemas/backtest_engine.py` in `PortfolioDiagnosticsProvenance`
- diagnostics input assembly: `services/quant-engine/app/services/portfolio_backtest_engine.py` in `BacktestDiagnosticsInputs` and `_build_backtest_diagnostics_inputs(...)`
- synthetic snapshot builder: `services/quant-engine/app/services/portfolio_backtest_engine.py` in `_build_synthetic_snapshot_from_weights(...)`

UI rule:

- backtest diagnostics should present this provenance explicitly so users do not confuse synthetic replay diagnostics with imported history-backed portfolio diagnostics

Known contract limitation:

- hypothetical replay can consume candidate construction outputs built with either `same_weight_substitution_v1` or `fixed_split_50_50_substitution_v2`
- the replay response derivation payload still reports the older generic `single_symbol_weight_substitution` value rather than the exact construction rule consumed
- treat candidate construction as the current authoritative source for exact single-replacement derivation semantics until replay provenance is tightened

Overlay-specific current-state rule:

- the current shipped overlay-aware replay path is intentionally narrow
- it supports only `benchmark_trend_overlay_v1`
- it applies only to the hypothetical candidate side
- in `risk_reduced` state it scales risky candidate weights by `0.35` and allocates the residual to synthetic replay cash `__CASH__`
- this synthetic cash sleeve is a replay artifact, not imported cash truth

## Exposure Coverage Methodology

Exposure currently reports `lookthrough.coverage_ratio` with this formula:

- `coverage_ratio = covered_market_value / portfolio_market_value`

Where:

- `portfolio_market_value` is the sum of current position market values
- `covered_market_value` includes:
  - direct single-name positions at 100% of their market value
  - ETF positions only when their constituent holdings are successfully resolved
- unresolved ETF positions may still appear as direct placeholders in current-state exposure lists, but they do not count toward `covered_market_value`

Implementation locations:

- constituent-resolution logic: `services/quant-engine/app/analytics/risk.py` in `build_lookthrough_exposure(...)`
- response assembly and exposure availability semantics: `services/quant-engine/app/services/exposure_engine.py` in `build_exposure_result(...)`

This means `coverage_ratio` is a constituent-resolution metric, not a generic “we can display the current holdings” metric.

Benchmark overlap currently reports these formulas when benchmark holdings are available:

- `overlap_weight = sum(min(portfolio_weight_i, benchmark_weight_i))` over shared symbols
- `active_share = 0.5 * sum(abs(portfolio_weight_i - benchmark_weight_i))` over the union of symbols
- `portfolio_in_benchmark_weight = sum(portfolio_weight_i)` over shared symbols
- `benchmark_covered_weight = sum(benchmark_weight_i)` over benchmark constituents loaded into the comparison set

Degraded/unavailable rule:

- if benchmark holdings are unavailable, overlap fields return `null` rather than `0.0`
- this prevents a missing-benchmark case from looking like true zero overlap or true zero benchmark coverage

Implementation locations:

- overlap calculation: `services/quant-engine/app/analytics/risk.py` in `build_market_overlap_summary(...)`
- exposure availability / degraded-state messaging: `services/quant-engine/app/services/exposure_engine.py` in `build_exposure_result(...)`

Exposure availability/confidence semantics currently use these meanings:

- `lookthrough_status`
  - `live`: no unresolved ETF holdings remain in current look-through resolution
  - `partial`: some ETF holdings are unresolved, but usable current-state exposure still exists
  - `unavailable`: no resolvable look-through holdings were produced
- `lookthrough_confidence`
  - `high`: current look-through resolution is fully available
  - `medium`: current look-through is usable but partial
  - `low`: current look-through is not trustworthy enough to treat as resolved exposure
- `benchmark_overlap_status`
  - `live`: benchmark-relative overlap is computed from available benchmark holdings
  - `partial`: benchmark-relative overlap exists but inherits partial look-through resolution
  - `unavailable`: benchmark holdings are missing or overlap cannot be trusted
- `benchmark_overlap_confidence`
  - `high`: benchmark-relative overlap is fully available
  - `medium`: benchmark-relative overlap is usable but depends on partial look-through resolution
  - `low`: benchmark-relative overlap is unavailable or not trustworthy
- `historical_diagnostics_confidence`
  - `high`: history-aware diagnostics are available
  - `low`: history-aware diagnostics are unavailable

Implementation locations:

- backend exposure availability: `services/quant-engine/app/services/exposure_engine.py` in `_build_exposure_availability(...)`
- desktop-composed historical diagnostics confidence: `apps/desktop/src/features/portfolio/portfolioAnalysisAdapter.ts` in `composeExposureView(...)`

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

Persisted imported-history metadata now writes a single `historySource` shape in workspace source metadata. Runtime restore/open-node flow is `historySource`-only; local IndexedDB schema upgrades reset prior workspace caches rather than attempting compatibility reconstruction across removed source shapes. The restore/open-node contract is explicit:

- direct imported nodes may restore broker-truth replay via `historySource.kind = imported_replay`
- inherited ancestors contribute only `history_context`, not imported replay payloads
- variants and drafts may reuse historical context for diagnostics/dashboard-history approximation, but must not inherit direct imported replay from an ancestor imported node

The current steady state is a clean `historySource`-only runtime and persistence model. Old local caches are invalidated by the database version/reset path rather than carried forward inside runtime code.

### Current desktop panel ownership

Use `docs/product/current-product-state.md` as the canonical shipped-state source when this ownership map changes.

Current top-level ownership in the desktop app:

- `Dashboard`
  - import/session controls, current workspace summary, and variant access
- `Exposure`
  - current-state exposure review with snapshot selection across draft and saved nodes
- `Diagnostics`
  - current-state overlays plus current-state diagnostics review
- `Workspace`
  - portfolio-improvement workflow shell, replay diagnostics review, replay-scoped Monitoring, and the lower-level allocation replay builder
- `Backtest`
  - generic strategy backtests only
- `Strategy Lab`
  - separate prototype strategy-research surface
- `ETF Ranking`
  - shipped candidate-seeding entry point into Research

Important current ownership rule:

- current-state diagnostics and replay-diagnostics review are no longer the same product surface
- `Diagnostics` owns current-state portfolio diagnostics
- `Workspace` owns portfolio-improvement review, replay-derived diagnostics deltas, and replay-scoped Monitoring

## Documentation Rule

If a financially meaningful formula, methodology, or truth-class assumption changes, update:
- `docs/finance/financial-methodology.md`
- the relevant field inventory document
- tests that lock the behavior

## MVP Boundary Rules

- UI owns presentation and workflow state
- quant engine owns calculations and imported portfolio truth
- LLM owns explanation and suggestion only
- deterministic code validates any LLM-generated allocation ideas before use

## Development-State Note

Older docs described imported portfolio analysis as primarily in-memory during early development. That is no longer an accurate description of the shipped desktop workflow.

Current desktop reality:

- local workspace state restores on launch when persisted state exists
- IndexedDB-backed workspace persistence is part of normal product behavior, not just a temporary prototype aid
- imported portfolio truth, workspace lineage, and review artifacts have an active local persistence model even though derived analytics remain non-truth runtime views

Future refactors may still normalize storage boundaries further, but docs should not describe the shipped desktop app as an in-memory-only workflow anymore.

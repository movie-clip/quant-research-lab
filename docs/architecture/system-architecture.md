# Quant Research Lab Architecture

This document explains the current architectural seams and the normalized direction.

For the canonical shipped-state inventory, use `docs/product/current-product-state.md`.

## System Boundaries

The project is split into a desktop application and a local quant engine.

- `apps/desktop`
  - workflow UI, workspace state, review flows, visualization, and local artifact persistence
- `services/quant-engine`
  - deterministic finance and quant engines for imports, diagnostics, ranking, construction, optimizer preview, and replay

The desktop app should treat the quant engine as the source of truth for portfolio calculations.

## Core Architecture Rules

- deterministic outputs over hidden heuristics
- explicit methodology and policy ids
- explicit truth separation across imported truth, synthetic analytics, persisted artifacts, and hypothetical outputs
- fail-closed loading for malformed or contradictory persisted artifacts
- thin frontend; no duplicate finance engine in UI code

## Current Implemented Backend Seams

### Replay and portfolio-improvement seams

- `POST /backtests/portfolio-allocation`
  - canonical allocation replay route for candidate-vs-reference comparison
- `POST /backtests/portfolio-allocation/replacement-intent-preview`
  - hypothetical replacement replay from draft snapshot plus replacement intent
- `POST /backtests/portfolio-allocation/replacement-intent-overlay-preview`
  - overlay-aware hypothetical replay for the current benchmark-trend overlay slice
- `POST /backtests/portfolio-allocation/construction-artifact-preview`
  - replay from an explicit persisted construction artifact reference
- `POST /backtests/portfolio-allocation/optimizer-handoff-preview`
  - replay from an explicit persisted optimizer handoff reference
- `POST /backtests/portfolio-allocation/optimizer-handoff/constraints`
  - validation and policy surface for persisted optimizer handoff references

### Construction seams

- `POST /construction/run`
  - first-class persisted backend construction run
- `GET /construction/artifacts/{artifact_id}`
  - immutable construction artifact load with validation on read
- `POST /backtests/candidate-formation/replacement-intent`
  - narrow review-oriented candidate formation seam
- `POST /backtests/candidate-construction/replacement-intent`
  - narrow review-oriented single-replacement construction seam
- `POST /backtests/candidate-construction/replacement-intent/constraints`
  - narrow review-oriented validation seam for replacement construction

### Ranking and optimizer seams

- `POST /strategy-lab/etf-ranking`
  - narrow shipped ETF-specific ranking seam that persists an immutable artifact before returning it
- `GET /strategy-lab/etf-ranking/artifacts/{artifact_id}`
  - narrow ETF-specific persisted artifact load by stable `artifact_id`
- `GET /strategy-lab/etf-ranking/artifacts/recent`
  - narrow ETF-specific recent persisted artifact discovery seam with newest-first listing and optional `effective_peer_group` filtering
- `GET /strategy-lab/etf-ranking/artifacts/recent/metadata`
  - narrow ETF-specific recent discovery metadata seam for current consumers
- `POST /strategy-lab/etf-ranking/replacements`
  - additive strategy-lab route that persists and returns the immutable intent-bound ETF replacement ranking artifact envelope
- `GET /strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}`
  - additive strategy-lab artifact load route for the same persisted intent-bound ETF replacement ranking artifact
- `POST /ranking/etf-replacements`
  - compatibility route for the same persisted intent-bound ETF replacement ranking flow that returns the legacy non-artifact POST contract
- `GET /ranking/etf-replacements/artifacts/{artifact_id}`
  - compatibility alias for immutable intent-bound ETF replacement ranking artifact load by stable `artifact_id`
- `POST /optimizer/preview`
  - hypothetical optimizer preview that can persist an explicit replay handoff reference

Ranking remains intentionally narrow in current architecture docs: this shipped seam is ETF-specific persisted artifact creation and reuse, not yet a generalized ranking platform across broader universes or methodologies.

### Important implementation reality

- `services/quant-engine/app/services/portfolio_backtest_engine.py` is the current integration seam for replay, replay diagnostics, construction-artifact replay, optimizer-handoff replay, and overlay-aware replay
- `services/quant-engine/app/services/construction_run_service.py` and `services/quant-engine/app/services/construction_artifact_service.py` are the current persisted construction seams
- `services/quant-engine/app/services/strategy_lab.py` is the current narrow shipped ETF ranking seam for persisted artifact creation, artifact reload, and recent discovery metadata
- `services/quant-engine/app/services/replacement_ranking.py` and `services/quant-engine/app/services/replacement_ranking_artifact_service.py` are the current intent-bound ETF replacement ranking build and persisted-artifact seams
- `services/quant-engine/app/services/optimizer_preview_service.py` and `services/quant-engine/app/services/optimizer_handoff_constraints.py` are the current optimizer preview and persisted-handoff seams
- docs should describe these as real current boundaries until they are split further

## Truth Classes and Trust Semantics

The project uses explicit truth classes when reasoning about financial outputs:

- `broker-truth historical diagnostics`
- `snapshot current-state analytics`
- `synthetic snapshot-history diagnostics`
- `persisted construction artifacts`
- `hypothetical optimizer previews and handoffs`
- `replay-derived hypothetical outputs`

These must remain visibly distinct in both payloads and UI.

Architecture-level trust rule:

- `verified_*` states mean the contract can claim the documented trust level for that path
- `degraded_*` states mean the engine may still compute useful outputs, but the contract must explicitly downgrade trust and suppress stronger claims
- `withheld` means broader evidence exists but investor-economics output is intentionally suppressed pending stronger return-basis justification
- `unavailable` means the required source inputs or trustworthy path do not exist at all

Docs and UI must not collapse `withheld` into generic `unavailable`.

## API Boundary

Current API direction:

- local workspace persistence is snapshot-first
- engine outputs are derived runtime artifacts or persisted immutable research artifacts
- the frontend may persist `PortfolioSnapshot` and workspace metadata locally, but it must not persist derived analytics as portfolio truth
- formed candidates, constructed candidates, persisted construction artifacts, optimizer previews, optimizer handoffs, hypothetical replays, and saved proposals are not applied portfolio truth

Future normalized API groups should preserve, not hide, the current artifact seams around construction, optimizer handoff, and replay.

## Data Flow

### Portfolio import and analytics

1. import broker statements or transactions
2. normalize into domain transactions, balances, and positions
3. build `PortfolioSnapshot` plus optional history context
4. persist snapshot as local truth in the desktop workspace model
5. call dedicated engines for diagnostics, ranking, construction, replay, optimizer preview, and monitoring as appropriate
6. send derived outputs to the UI with explicit provenance and trust metadata

### Ranking, construction, optimizer, and replay

1. define universe or review intent
2. compute ETF ranking output and persist an immutable ranking artifact, or accept explicit candidate inputs through other narrow review seams
3. construct candidate weights through either review-oriented construction or persisted construction policies
4. optionally produce a hypothetical optimizer preview and persist a handoff reference
5. replay baseline vs candidate through explicit artifact or handoff references
6. emit replay metrics, diagnostics comparison, and provenance

### Persisted ETF ranking artifact rule

- ETF ranking persists an immutable artifact before return on the shipped `POST /strategy-lab/etf-ranking` seam
- downstream ETF consumers can reopen one artifact by `artifact_id`, browse recent artifacts, and discover current `effective_peer_group` metadata from the recent index
- docs must describe this as a current ETF-specific artifact seam only; they must not overstate it as a generalized ranking-run platform

### Persisted intent-bound ETF replacement ranking artifact rule

- intent-bound ETF replacement ranking now persists an immutable artifact before return on both `POST /strategy-lab/etf-ranking/replacements` and `POST /ranking/etf-replacements`
- the persisted artifact is the authoritative internal handoff after execution on both routes
- `POST /ranking/etf-replacements` maps that canonical persisted result back to the legacy response shape instead of exposing the artifact envelope
- artifact-backed response access remains additive on `POST /strategy-lab/etf-ranking/replacements` and the artifact GET routes
- downstream consumers can reload that artifact only by explicit `artifact_id` on either route family
- persistence is the authoritative downstream truth for this slice
- reload remains an artifact-id load boundary only; it does not reconstruct request state or perform validation/preflight side effects
- validation/open/review semantics remain unchanged in this slice; persistence does not widen those boundaries
- load semantics fail closed on missing file (`404`), invalid json (`400`), non-object payload (`400`), schema failure (`400`), lineage contradiction (`400`), or canonical identity mismatch (`400`)

### Persisted construction artifact rule

- construction artifacts persist immutable policy outputs before replay consumption
- artifacts capture `selection_rule_trace` during policy execution and keep it as provenance
- replay echoes the persisted trace; replay must not reconstruct or reinterpret that trace

### Optimizer handoff rule

- optimizer previews can persist an immutable handoff reference only when the preview is feasible
- downstream replay and constraint validation consume the explicit persisted reference only
- optimizer handoff outputs remain hypothetical and must not be treated as applied portfolio truth

## Desktop Workspace Model

The desktop app follows a local-first workspace structure:

- `PortfolioWorkspace`
- `PortfolioNode`
- `WorkingDraft`
- `PortfolioSnapshot`

Saved portfolio variants are immutable child nodes. Engine outputs are recalculated or restored as derived views and are not the persisted truth of the workspace.

Review artifacts and persisted references should remain lineage-aware and fail closed when internal contradictions are provable.

## Documentation Rule

If a financially meaningful formula, methodology, truth-class assumption, trust semantic, or persisted-artifact provenance rule changes, update:
- `docs/finance/financial-methodology.md`
- the relevant field inventory document
- tests that lock the behavior

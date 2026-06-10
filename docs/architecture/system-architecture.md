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

Import admission has a narrower split: the quant engine emits read-only `ImportAdmissionSummaryV1` evidence in imported bootstrap responses, while optional `ImportAdmissionReviewDispositionV1` reviewer dispositions remain desktop-local metadata only. There is no backend persistence endpoint for those dispositions, and neither the summary nor local dispositions mutate broker truth, admission state, trust level, imported values, derived portfolio truth, or workspace creation.

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

ETF-specific ranking (original shipped path):
- `POST /strategy-lab/etf-ranking`
  - ETF-specific ranking seam that persists an immutable artifact before returning it
- `GET /strategy-lab/etf-ranking/artifacts/{artifact_id}`
  - ETF-specific persisted artifact load by stable `artifact_id`
- `GET /strategy-lab/etf-ranking/artifacts/recent`
  - ETF-specific recent persisted artifact discovery seam with newest-first listing and optional `effective_peer_group` filtering
- `GET /strategy-lab/etf-ranking/artifacts/recent/metadata`
  - ETF-specific recent discovery metadata seam for current consumers

Generic ranking platform (newer cross-universe ranking path):
- `POST /strategy-lab/ranking/run`
  - first-class generalized ranking run that accepts a `UniverseSpec` (etf_peer_group, custom_list, broad_equity_screen, sector_screen, index_constituent) plus a versioned `ScoreConfig` and persists an immutable `generic_ranking` artifact before returning it
- `GET /strategy-lab/ranking/artifacts/{artifact_id}`
  - generic ranking artifact load by stable `artifact_id`
- `GET /strategy-lab/ranking/artifacts/recent`
  - generic ranking recent persisted artifact discovery (newest-first)

Cross-kind discovery:
- `GET /strategy-lab/ranking-artifacts/catalog`
  - generalized persisted ranking artifact catalog across all supported kinds (`etf_ranking`, `intent_bound_etf_replacement_ranking`, `generic_ranking`)
- `GET /strategy-lab/ranking-artifacts/recent`
  - generalized recent discovery across the same kinds

Intent-bound ETF replacement ranking:
- `POST /strategy-lab/etf-ranking/replacements`
  - additive strategy-lab route that persists and returns the immutable intent-bound ETF replacement ranking artifact envelope
- `GET /strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}`
  - additive strategy-lab artifact load route for the same persisted intent-bound ETF replacement ranking artifact
- `POST /ranking/etf-replacements`
  - compatibility route for the same persisted intent-bound ETF replacement ranking flow that returns the legacy non-artifact POST contract
- `GET /ranking/etf-replacements/artifacts/{artifact_id}`
  - compatibility alias for immutable intent-bound ETF replacement ranking artifact load by stable `artifact_id`

Optimizer:
- `POST /optimizer/preview`
  - hypothetical optimizer preview that can persist an explicit replay handoff reference

Ranking is now a generalized platform with three artifact kinds: `etf_ranking`, `intent_bound_etf_replacement_ranking`, and `generic_ranking`. All three are construction-eligible through the canonical `POST /construction/ranking-artifacts/preflight/{artifact_id}` + `POST /construction/run` boundary. ETF replacement is still an intent-scoped review family rather than a freeform ranking entry point. Generic ranking covers the broader cross-universe path with versioned `ScoreConfig`, `UniverseSpec` snapshotting, and per-instrument `EligibilityRecord` truth.

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

### Market-data providers and data provenance

Market data is served behind a single seam, `MarketDataService`
(`app/services/market_data.py`), which resolves each symbol to ordered
candidates and tries providers in priority order:

1. **FMP (primary)** — `FmpClient`. Covers US-listed equities/ETFs. Returns
   HTTP 402 for European exchange-listed symbols (`.L`, `.DE`, …).
2. **Yahoo Finance (secondary/fallback)** — `YFinanceClient`, tried only when
   FMP returns nothing for a candidate (US-18.1). Recovers European UCITS ETFs
   (`VUAA.L`, `SXRV.DE`, …) with adjusted-close history.

`MarketDataService.last_fetch_meta[symbol]['vendor']` records which provider
satisfied each symbol (`'fmp'` | `'yfinance'`). The FMP-first path is unchanged
when FMP has data; yfinance is never a proxy substitute (it fetches the *real*
holding from a second source).

**Row sanitization rule (US-18.4):** rows with an absent or non-finite `price`
(NaN/inf — e.g. a Yahoo/pandas missing bar) never leave the seam:
`MarketDataService` filters them on every history return path, and the yfinance
client additionally skips non-finite bars at the source. A non-finite bar is
"no data for that date" — dropped, never zero-filled or interpolated. This also
neutralizes already-cached poisoned entries.

**Data provenance is a distinct dimension from return-basis trust.** Yahoo data
carries adjusted close, so its return-basis is `verified_adjusted_close` — the
same class as FMP — but the *source* differs. Per the traceability guardrail,
provenance must be **surfaced, never hidden**: engine responses that include
yfinance-sourced holdings carry that fact (e.g. `IntraCorrelationResult.yahoo_sourced_symbols`)
and the UI shows a visible "via Yahoo Finance (secondary source)" marker.
(The `.claude/skills/fmp-data` skill is the multi-provider reference.)

A dedicated `POST /engines/provenance/run` engine (`provenance_engine.py`,
US-18.2) reports per-holding provenance for the whole portfolio (FMP / yfinance
/ unavailable) by a short probe of `last_fetch_meta` vendor; the Exposure tab's
"Data sources" panel renders it once at the portfolio level rather than
repeating a marker on every card. Provenance is a **source label, not a
return-basis trust claim** — it never asserts `verified`/`synthetic` for the
analytics.

Instrument identity (Epic 19 / US-19.1): `app/services/instrument_identity.py`
cross-checks each registry-known holding's broker-statement description against
the registry fund name and flags identity-disjoint mismatches (possible
ticker→fund mislabels). It is emitted both as the
`instrument_description_registry_consistency` Import Admission check and (for
visibility) in the provenance result rendered by the Data Sources panel.
Flag only — never auto-corrects the registry or remaps the symbol.

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

Import admission evidence is finite-only for numeric observed, comparison, and delta fields. Non-finite imported numeric inputs degrade to unavailable evidence rather than serializing `NaN` or `Infinity`. Desktop read/build paths may return sanitized clones of local review metadata without rewriting IndexedDB; save paths must match captured evidence against the current non-pass check evidence.

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
- generalized discovery may also surface ETF artifacts through additive backend-only catalog/recent routes
- docs must describe generation as a current ETF-specific artifact seam only; they must not overstate it as a generalized ranking-run platform

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

### Generalized ranking artifact discovery rule

- generalized ranking discovery reads only persisted authoritative artifacts and persisted authoritative indexes
- ETF discovery reuses the ETF recent index where present, but only as an internal ETF discovery aid for recent-list ordering
- ETF same-day recent ties preserve persisted `recent.jsonl` sequence as the authoritative order; generalized discovery must not re-sort those ETF ties by `artifact_id`
- supported kinds without a recent index derive deterministic recent ordering from persisted authoritative metadata only, never by recomputing rankings
- malformed json, non-object payloads, unsupported schema versions, and provable identity or integrity contradictions fail closed instead of being skipped or repaired
- unsupported artifact kinds or unsupported persisted schema states fail closed instead of silently widening support
- the ETF `recent.jsonl` file is not a reusable artifact payload or external contract surface; it remains internal operational state for ETF discovery only
- additive generalized discovery does not change current ETF-native or replacement execution and load routes

### Persisted generic ranking artifact rule

- generic ranking persists an immutable artifact on `POST /strategy-lab/ranking/run` before return
- artifacts carry `UniverseSpecSnapshot` (resolved member list with `spec_digest`), `ScoreConfigRef` (with content-addressed `score_config_digest`), per-instrument `EligibilityRecord` (with explicit `hard_filter_failures` + `soft_filter_flags`), and optional `CompositeScoreTrace` (per-factor cross-sectional mean/std for offline normalization replay)
- artifact identity is content-addressed: `generic_ranking_artifact_<sha256(canonical_json_without_artifact_id)[:16]>`
- supported factor families: price-bar (momentum, volatility, drawdown, liquidity) and fundamental (quality via Novy-Marx/Sloan/AQR formulas, value via FMP TTM ratios — Greenblatt/Fama-French)
- when fundamental factors are requested without an FMP API key, the service emits a warning and returns the artifact with those factor values as null; confidence drops to `partial` rather than failing the request
- supported universe kinds: `etf_peer_group`, `custom_list`, `broad_equity_screen`, `sector_screen` (FMP screener), `index_constituent` with two index families:
  - `index_id="sp500"` — live FMP `/stable/sp500-constituent` (current snapshot only; PIT historical reconstruction deferred)
  - `index_id="russell1000"` — static JSON snapshot under `data/universe/index_snapshots/russell1000.json`, sourced from iShares IWB ETF holdings (no FMP endpoint exists for Russell 1000); fail-closed on missing/malformed snapshot file; bundled snapshot is a representative sample, scripted ingestion of the full membership is deferred
- generic ranking artifacts are construction-eligible through the same canonical preflight + run boundary used by ETF and replacement ranking; the construction allowlist is now a three-kind set
- load fails closed on missing file (`404`), invalid json (`400`), non-object payload (`400`), schema failure (`400`), or canonical identity mismatch (`400`)

### Persisted construction artifact rule

- construction artifacts persist immutable policy outputs before replay consumption
- artifacts capture `selection_rule_trace` during policy execution and keep it as provenance
- replay echoes the persisted trace; replay must not reconstruct or reinterpret that trace
- construction preflight + run accept three ranking artifact handoff kinds: `etf_ranking_artifact_construction_handoff_v1`, `intent_bound_etf_replacement_ranking_artifact_construction_handoff_v1`, `generic_ranking_artifact_construction_handoff_v1` — explicit allowlist; unsupported families fail closed
- for `generic_ranking` handoffs, `EligibilityRecord.hard_filter_failures` flow through to `ConstructionRankedCandidateInput.exclusion_reason` rather than being silently dropped

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

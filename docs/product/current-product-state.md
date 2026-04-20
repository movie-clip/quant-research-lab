# Current Product State

This document is the canonical source for what is actually shipped today, what is intentionally narrow, and what remains future work.

Use this file when updating `README.md`, roadmap docs, architecture docs, and contract docs. Do not repeat the same current-state summary across multiple docs unless a shorter pointer is enough.

## Current product shape

- local-first product with a desktop workflow UI in `apps/desktop` and a deterministic Python engine in `services/quant-engine`
- desktop owns workflow state and review surfaces; the quant engine owns finance calculations, ranking outputs, construction outputs, and replay outputs
- the platform is already usable as a portfolio analysis and review workspace, but the quant-research-lab pivot is still partial rather than complete

## Shipped today

### Desktop app ownership and navigation

- top-level desktop tabs are `Dashboard`, `Exposure`, `Diagnostics`, `Workspace`, `Backtest`, `Strategy Lab`, and `ETF Ranking`
- `Dashboard` owns import/session controls, current workspace summary, and variant access
- `Exposure` owns current-state exposure review with snapshot selection across draft and saved nodes
- `Diagnostics` owns current-state overlays plus current-state diagnostics review
- `Workspace` owns the portfolio-improvement workflow shell, replay diagnostics review, replay-scoped monitoring, and the allocation replay builder for portfolio-improvement flows
- `Backtest` owns generic strategy backtests and is separate from the portfolio-improvement Workspace workflow
- `ETF Ranking` owns the current shipped candidate-seeding entry point into Workspace

### Portfolio truth and current-state analysis

- local workspace model built around `PortfolioSnapshot`, immutable saved nodes, and working drafts
- broker import and portfolio snapshot workflows exist as part of the current desktop-plus-engine architecture
- current-state exposure and diagnostics flows exist for portfolio understanding, including look-through, overlap, factor/risk, and related diagnostics surfaces
- financial outputs are expected to stay traceable to engine responses rather than frontend-created finance logic
- exposure contracts now carry explicit grouped run metadata for structured source-status and reproducibility fields
- diagnostics contracts now carry explicit grouped run metadata for source-status, factor-model assumptions, and reproducibility time-basis fields
- diagnostics unavailable paths are now reason-specific: snapshot-request history-context gaps, imported-history reconstruction failures, and market-data failures no longer share the same note/flag wording
- dashboard-history contracts now carry explicit grouped run metadata for structured source-status and reproducibility fields
- hypothetical replay outputs now carry explicit replay provenance for direct preview vs constructed-candidate replay lineage, actual construction rule used, upstream draft/workspace/base-node lineage, echoed constraint-validation lineage, and basic lineage-integrity enforcement for provable artifact mismatches

### Replay and portfolio-improvement workflow

- canonical portfolio allocation replay route exists at `POST /backtests/portfolio-allocation`
- explicit hypothetical replacement replay exists at `POST /backtests/portfolio-allocation/replacement-intent-preview`
- replacement-intent candidate formation exists at `POST /backtests/candidate-formation/replacement-intent`
- replacement-intent candidate construction exists at `POST /backtests/candidate-construction/replacement-intent`
- desktop supports explicit replacement-intent review, replay review, diagnostics delta review, and immutable local proposal artifact persistence/readout
- Workspace replay preview now surfaces artifact-specific backend replay failures directly in the existing replay error line, rather than collapsing lineage-integrity failures into generic copy
- immutable saved proposal artifacts now fail on provable internal lineage contradictions between saved replay-basis provenance and saved review-snapshot provenance

Current Workspace workflow order is explicit and shell-owned:
1. current portfolio
2. candidate idea
3. candidate formation
4. construction rule
5. hypothetical replay
6. diagnostics change
7. saved proposal

Current Workspace composition is also explicit:
- the workflow shell appears first
- replay-scoped Monitoring appears after the shell
- the lower-level allocation replay builder appears after Monitoring
- Monitoring can hand off back into the shell with a narrow `Review In Workspace` action and a session-scoped banner

### Ranking and research workflow

- generic ETF ranking exists at `POST /strategy-lab/etf-ranking`
- intent-bound ETF replacement ranking exists at `POST /ranking/etf-replacements`
- desktop can seed a draft-scoped ETF replacement review flow from ranking output without mutating portfolio truth

### Overlay support

- overlay-aware hypothetical replay exists at `POST /backtests/portfolio-allocation/replacement-intent-overlay-preview`
- current shipped overlay behavior is a narrow review path, not a general overlay platform

## Narrow boundaries that docs should state explicitly

- ranking is shipped only in narrow ETF-focused slices; it is not yet a generalized ranking-run platform across universes
- construction is shipped only for explicit single-replacement review flows; it is not yet a generalized portfolio construction engine
- current construction rules are limited to `same_weight_substitution_v1` and `fixed_split_50_50_substitution_v2`
- formed candidates, constructed candidates, hypothetical replays, and saved proposals are review artifacts only; they do not mutate `PortfolioSnapshot` or apply a holdings change
- overlay support is limited to `benchmark_trend_overlay_v1`, one overlay at a time, candidate-side application only, and replay preview only
- monitoring is currently a replay-scoped Workspace surface only; it is not yet a broad continuous monitoring and alerting system
- current Monitoring-to-Workspace continuity is narrow: explicit user-initiated handoff, versioned handoff payload, session-scoped dismiss state, and no persistent alert/review history
- optimization is not yet a shipped product capability
- replay provenance is now explicit for the current hypothetical replay slice, including echoed constraint-validation lineage; replay now rejects provable artifact mismatches but still does not enforce validation status in-engine

## Local workspace and artifact behavior that matters to product docs

- workspace state restores on launch from local persistence when available
- the editable `WorkingDraft` is recreated from the active node when opening a node or discarding draft changes
- saved nodes are immutable portfolio truth snapshots; review artifacts are separate from those snapshots
- seeded candidate metadata, replacement intent, formed candidate artifact, constructed candidate artifact, selected construction rule, hypothetical replay draft, and saved proposal artifacts all persist locally
- review artifacts are draft-scoped unless explicitly saved as immutable workspace-scoped proposal artifacts
- active thesis restore now uses the same saved-proposal integrity checks and fails closed on contradictory embedded proposal lineage
- recreating a draft from a node clears dependent draft-scoped review artifacts so stale review state does not silently carry across lineage changes

## What is future, not current

- generalized ranking engine with persisted ranking runs across broader universes
- generalized rule-based construction with richer constraint models
- broader overlay engine families beyond the narrow benchmark-trend replay path
- continuous monitoring, alerts, and review history as first-class product capabilities
- constrained optimization as a bounded refinement layer
- a fully unified end-to-end quant-research workflow that makes ranking, construction, replay, and monitoring all first-class and generalized

## Documentation use rules

- use this document for shipped-scope truth
- keep `docs/product/roadmap.md` focused on future product direction and sequencing
- keep `docs/product/technical-roadmap.md` focused on target architecture, delivery plan, and technical future state
- keep `docs/architecture/system-architecture.md` explicit about current seams vs future normalized seams
- keep `docs/contracts/*.md` and `docs/finance/financial-methodology.md` aligned with any financially meaningful change

## Update trigger

Update this file when any of the following changes:

- a route or workflow becomes user-usable and should count as shipped
- a currently narrow slice becomes generalized enough that docs should stop calling it narrow
- a current workflow is deprecated or replaced as the canonical path
- a truth-class, replay-provenance, or finance-accuracy constraint materially changes what can be claimed as current behavior

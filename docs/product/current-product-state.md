# Current Product State

This document is the canonical source for what is actually shipped today, what is intentionally narrow, and what remains future work.

## Current product shape

- local-first desktop workflow in `apps/desktop` backed by deterministic engine services in `services/quant-engine`
- desktop owns workflow state and review surfaces; the quant engine owns portfolio math, ranking, construction, optimizer preview, and replay outputs
- the platform is already usable for portfolio analysis, candidate review, persisted construction, and hypothetical optimizer evaluation

## Shipped today

### Portfolio truth and current-state analysis

- broker import, workspace snapshots, immutable saved nodes, and working drafts are shipped product behavior
- exposure, diagnostics, dashboard-history, and replay contracts now use explicit trust semantics instead of generic missing-data language
- shipped trust states distinguish verified paths, degraded unverified return-basis paths, explicit investor-economics withholding, and true unavailability
- `investor_economics_status = withheld` is baseline shipped behavior when broader evidence exists but total-return-equivalent claims are not justified
- diagnostics and dashboard-history expose grouped `section_trust` so benchmark-relative, factor-model, risk-contribution, portfolio, benchmark, and monthly-return paths do not overclaim trust

### Replay and portfolio-improvement workflow

- canonical allocation replay exists at `POST /backtests/portfolio-allocation`
- hypothetical replacement replay exists at `POST /backtests/portfolio-allocation/replacement-intent-preview`
- overlay-aware hypothetical replay exists at `POST /backtests/portfolio-allocation/replacement-intent-overlay-preview`
- replacement-intent candidate formation exists at `POST /backtests/candidate-formation/replacement-intent`
- replacement-intent candidate construction exists at `POST /backtests/candidate-construction/replacement-intent`
- replacement-intent constraint validation exists at `POST /backtests/candidate-construction/replacement-intent/constraints`
- replay provenance is explicit for direct preview vs constructed-candidate replay, actual construction rule used, upstream draft/workspace lineage, ranking seed lineage, and echoed validation lineage
- replay rejects provable lineage mismatches across persisted or supplied artifacts; validation lineage is descriptive, not execution approval
- immutable saved proposal artifacts and active thesis restore fail closed on provable internal lineage contradictions

### Persisted construction engine

- construction is now a first-class persisted backend capability, not just an inline review helper
- `POST /construction/run` persists canonical construction artifacts before returning them
- `GET /construction/policies` exposes deterministic backend-owned read-only discovery for the shipped persisted policy catalog
- `GET /construction/artifacts/{artifact_id}` reloads persisted artifacts, validates them on read, and fails closed on corruption or malformed payloads
- `POST /backtests/portfolio-allocation/construction-artifact-preview` replays persisted construction artifacts through an explicit artifact-reference boundary
- current persisted construction policies are `top_n_equal_weight_v1` and `top_n_inverse_rank_weight_v1`
- persisted construction execution is deterministic and records an ordered `selection_rule_trace` as provenance
- replay echoes the persisted `selection_rule_trace`; it is descriptive lineage only and must not drive replay math

### ETF ranking artifacts and discovery

- `POST /strategy-lab/etf-ranking` persists immutable ETF ranking artifacts as shipped backend behavior
- `GET /strategy-lab/etf-ranking/artifacts/{artifact_id}` reloads persisted ETF ranking artifacts through an explicit artifact boundary
- `GET /strategy-lab/etf-ranking/artifacts/recent` exposes newest-first recent artifact discovery with optional `effective_peer_group` filtering
- `GET /strategy-lab/etf-ranking/artifacts/recent/metadata` exposes discovered recent-run filter metadata for current consumers
- shipped ETF ranking artifacts already carry persisted artifact identity, grouped request/effective-inputs metadata, and run-basis metadata for audit and reuse
- the desktop `ETF Ranking` flow can reopen recent persisted runs and carry a selected ranking artifact into draft review as a current shipped workflow

### Optimizer preview, handoff, and replay workflow

- optimizer preview is shipped as a hypothetical workflow at `POST /optimizer/preview`
- feasible previews can persist an immutable explicit handoff reference with benchmark, snapshot, optimizer artifact, and return-basis attestation lineage
- persisted optimizer handoff review reopens by persisted `handoffReference`; `handoffReference.handoff_id` is the canonical identity and `handoffReference.artifact_id` remains persisted lineage and integrity metadata only
- persisted handoffs replay through `POST /backtests/portfolio-allocation/optimizer-handoff-preview`
- persisted handoffs validate through `POST /backtests/portfolio-allocation/optimizer-handoff/constraints`, which remains a validation/preflight boundary rather than a replay-open route
- optimizer replay truth is explicit: hypothetical output only, not applied portfolio truth
- optimizer handoff replay uses persisted lineage and return-basis attestation to control benchmark-relative output suppression
- trusted PIT alpha attachment is shipped for the narrow `alpha_quality_v1` path when requested by optimizer preview
- optimizer objective selection is now additive: default benchmark-distance remains backward compatible, and hypothetical artifact-backed preview/replay can also persist and replay `maximize_alpha_quality_v1`

### Desktop workflow ownership

- top-level desktop tabs are `Dashboard`, `Exposure`, `Diagnostics`, `Workspace`, `Backtest`, `Strategy Lab`, and `ETF Ranking`
- `Workspace` owns the portfolio-improvement shell, replay review, replay-scoped Monitoring, and proposal review
- Workspace workflow order is explicit: current portfolio -> candidate idea -> candidate formation -> construction rule -> hypothetical replay -> diagnostics change -> saved proposal
- Monitoring can hand off back into Workspace through an explicit review action; it is still review-scoped rather than continuous monitoring infrastructure

## Narrow boundaries docs should still state explicitly

- ranking is still narrow and ETF-heavy; it is not yet a generalized persisted ranking-run platform across broader universes
- recent-run discovery and artifact reuse are shipped for ETF ranking specifically; what remains future is generalization beyond that narrow scope
- persisted construction is shipped and now has read-only policy discovery, but the persisted policy set is still narrow; today it supports only `top_n_equal_weight_v1` and `top_n_inverse_rank_weight_v1`
- single-replacement construction and overlay-aware replay remain narrow review workflows layered alongside the broader persisted construction seam
- optimizer is shipped only as hypothetical preview, persisted handoff, validation, and replay; it does not apply trades or mutate `PortfolioSnapshot`
- optimizer alpha-objective support remains narrow: one additive `alpha_quality_v1` objective only, artifact-backed only, fail-closed on missing, malformed, quarantined, unsupported, stale, or degraded alpha inputs
- overlays remain limited to `benchmark_trend_overlay_v1`, one overlay at a time, candidate-side application only, and replay preview only
- monitoring remains a replay-scoped Workspace review surface, not a continuous alerting and review-history system

## Local workspace and artifact behavior that matters to docs

- workspace state restores on launch from local persistence when available
- saved nodes are immutable portfolio-truth snapshots; review artifacts are separate from those snapshots
- seeded candidate metadata, replacement intent, formed candidates, constructed candidates, selected construction rules, hypothetical replays, persisted construction references, optimizer handoffs, and saved proposals all preserve explicit lineage boundaries
- desktop persisted optimizer handoff review state now writes canonical `handoffReference` reopen state only; any legacy cache repair is limited to load-time normalization
- recreating a draft from a node clears dependent draft-scoped review artifacts so stale review state does not silently cross lineage changes

## What is future, not current

- broader ranking engines across wider universes and non-ETF scopes, using generalized ranking-platform contracts rather than the current ETF-specific path
- more persisted construction policies, richer constraints, turnover models, and broader ranking-to-construction integration
- broader overlay families beyond the current benchmark-trend replay path
- continuous monitoring, alerts, and review history as first-class product capabilities
- optimizer expansion beyond the current hypothetical preview and handoff workflow
- fuller end-to-end quant research workflows that unify ranking, construction, replay, monitoring, and execution planning

## Documentation rules

- use this file for shipped-scope truth
- keep `docs/product/roadmap.md` focused on remaining product work only
- keep `docs/product/technical-roadmap.md` focused on remaining technical work only
- keep `docs/architecture/system-architecture.md`, `docs/finance/financial-methodology.md`, and `docs/contracts/*.md` aligned with any materially meaningful change in trust, withholding, provenance, or financial methodology

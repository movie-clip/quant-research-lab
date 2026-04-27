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
- hypothetical replacement replay and saved proposal review now carry explicit proposal-source labels for review-only proposal truth and draft-portfolio non-application semantics
- replay rejects provable lineage mismatches across persisted or supplied artifacts; validation lineage is descriptive, not execution approval
- immutable saved proposal artifacts and active thesis restore fail closed on provable internal lineage contradictions

### Persisted construction engine

- construction is now a first-class persisted backend capability, not just an inline review helper
- `POST /construction/run` persists canonical construction artifacts before returning them
- `GET /construction/policies` exposes deterministic backend-owned read-only discovery for the shipped persisted policy catalog, including additive catalog metadata, explicit constraint/input capability flags such as optional `min_position_weight`, optional `max_turnover_weight`, and optional `max_trade_intent_count` support, and single-value exact-match server-side filters over that metadata only; undocumented filter keys, repeated supported scalar filter keys, and malformed present filter values are rejected rather than ignored
- `GET /construction/artifacts/{artifact_id}` reloads persisted artifacts, validates them on read, and fails closed on corruption or malformed payloads
- `POST /backtests/portfolio-allocation/construction-artifact-preview` replays persisted construction artifacts through an explicit artifact-reference boundary
- persisted construction review restore now uses the canonical backend `review_basis` block or typed `preview_handoff` semantics only; desktop does not reconstruct review basis from loose replay fields when canonical basis is present
- current persisted construction policies are `top_n_equal_weight_v1`, `top_n_inverse_rank_weight_v1`, and `top_n_linear_rank_weight_v1`
- persisted construction execution is deterministic and records an ordered `selection_rule_trace` as provenance
- persisted construction artifacts now also persist additive normalized `min_position_weight` and additive normalized `max_trade_intent_count` hard-constraint truth when requested, and downstream load/validation/preview/replay consume that persisted artifact state unchanged
- persisted construction artifacts now also carry additive `weighting_trace_v1` diagnostics with explicit `weighting_trace_status`; this remains hypothetical construction diagnostics sourced only from the persisted artifact and does not change construction outputs or replay math
- persisted construction artifacts now also carry additive `turnover_diagnostics_v1` diagnostics with explicit `turnover_diagnostics_status`; this remains hypothetical construction diagnostics sourced only from the persisted artifact and does not change construction outputs or replay math
- persisted construction turnover diagnostics now also include additive per-symbol turnover contribution rows that reconcile exactly to the existing reported aggregate turnover and remain explanatory-only artifact diagnostics
- replay echoes the persisted `selection_rule_trace`; it is descriptive lineage only and must not drive replay math
- replay/open echoes persisted turnover diagnostics from the artifact only and fails closed on malformed or unsupported present turnover-diagnostics states; exact legacy compatibility remains load-only when those fields are wholly absent
- replay/open also echo persisted construction hard constraints, including additive `min_position_weight` and additive `max_trade_intent_count`, from artifact truth only; replay outputs and analytics methodology remain unchanged when the field is absent
- persisted construction artifacts remain hypothetical candidate truth consumed through the existing validation-to-preview and preview/replay handoff boundary; replay uses persisted `final_target_weights` plus normalized inputs rather than re-resolving catalog math
- replay/open now also echo additive canonical `review_basis` and additive replay `methodology_provenance` fields for review restore and explicit provenance labeling; these remain review-only semantics and do not change replay analytics or construction methodology

### ETF ranking artifacts and discovery

- `POST /strategy-lab/etf-ranking` persists immutable ETF ranking artifacts as shipped backend behavior
- shipped ETF ranking request defaults still allow omitted `benchmark_symbol` -> `SPY` and omitted `lookback_months` -> `3` on existing ETF ranking routes
- `GET /strategy-lab/etf-ranking/artifacts/{artifact_id}` reloads persisted ETF ranking artifacts through an explicit artifact boundary
- `POST /strategy-lab/etf-ranking/replacements` persists intent-bound ETF replacement ranking artifacts on the additive strategy-lab route surface and returns the artifact envelope
- `GET /strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}` reloads persisted intent-bound ETF replacement ranking artifacts through the same explicit artifact boundary
- `POST /ranking/etf-replacements` preserves the legacy non-artifact response shape while still persisting the canonical replacement-ranking artifact internally
- `GET /ranking/etf-replacements/artifacts/{artifact_id}` remains a shipped compatibility alias for artifact reload by id
- `GET /strategy-lab/ranking-artifacts/catalog` exposes additive backend-only generalized catalog discovery across the supported persisted ETF ranking and intent-bound ETF replacement artifact kinds
- `GET /strategy-lab/ranking-artifacts/recent` exposes additive backend-only generalized recent discovery across the same supported persisted artifact kinds
- `GET /strategy-lab/etf-ranking/artifacts/recent` exposes newest-first recent artifact discovery with optional `effective_peer_group` filtering
- `GET /strategy-lab/etf-ranking/artifacts/recent/metadata` exposes discovered recent-run filter metadata for current consumers
- shipped ETF ranking artifacts already carry persisted artifact identity, grouped request/effective-inputs metadata, and run-basis metadata for audit and reuse
- the desktop `ETF Ranking` flow can reopen recent persisted runs and carry a selected ranking artifact into draft review as a current shipped workflow
- persisted intent-bound ETF replacement ranking artifacts are the authoritative downstream truth for replacement review and reload in the shipped slice
- generalized ranking-artifact preflight now returns only typed `open_handoff` plus truthful eligibility, and ranking-artifact open accepts only that typed handoff; replacement `open_supported`/`replay_eligible` semantics are derived from the same canonical consumer-handoff validation path used during open
- generalized discovery is additive only; existing ETF-native and replacement routes stay unchanged
- generalized recent discovery is now fail-closed on malformed ETF recent-index state, malformed artifact payloads, unsupported artifact kinds, unsupported schema versions, and provable identity contradictions
- ETF `recent.jsonl` remains internal operational state for ETF discovery ordering only; it is not a shipped artifact output or generalized reusable contract payload

### Cross-sectional research artifacts

- `POST /strategy-lab/cross-sectional-research/validate` is shipped as a validation-only backend boundary for one persisted cross-sectional research family slice
- `POST /strategy-lab/cross-sectional-research/run` persists immutable cross-sectional research artifacts before returning them
- `GET /strategy-lab/cross-sectional-research/artifacts/{artifact_id}` reloads persisted research artifacts, validates them on read, and fails closed on missing file, invalid json, non-object payload, schema mismatch, and integrity mismatch
- `GET /strategy-lab/cross-sectional-research/catalog` and `GET /strategy-lab/cross-sectional-research/recent` are sourced from persisted artifacts only; validate does not populate discovery state
- backend schema and serialization are the contract root for this research family; shipped output is a hypothetical research artifact and not portfolio or execution truth
- the first shipped family is narrow: one canonical `cross_sectional_research_run` artifact kind and `cross_sectional_research_artifact_v1` schema with `alpha_quality_v1` represented as a methodology inside that family plus compact provenance-rich `walk_forward_summary` and `holdout_summary` only

### Optimizer preview, handoff, and replay workflow

- optimizer preview is shipped as a hypothetical workflow at `POST /optimizer/preview`
- feasible previews can persist an immutable explicit handoff reference with benchmark, snapshot, optimizer artifact, and return-basis attestation lineage
- persisted optimizer handoff review reopens by persisted `handoffReference`; `handoffReference.handoff_id` is the canonical identity and `handoffReference.artifact_id` remains persisted lineage and integrity metadata only
- persisted handoffs replay through `POST /backtests/portfolio-allocation/optimizer-handoff-preview`
- persisted handoffs validate through `POST /backtests/portfolio-allocation/optimizer-handoff/constraints`, which remains a validation/preflight boundary rather than a replay-open route
- persisted optimizer handoff review restore now uses the canonical backend `review_basis` block only; desktop reopen identity remains `handoffReference` and restore fails closed on missing or conflicting canonical review basis
- optimizer replay truth is explicit: hypothetical output only, not applied portfolio truth
- optimizer handoff replay uses persisted lineage and return-basis attestation to control benchmark-relative output suppression
- optimizer replay also exposes additive replay `methodology_provenance` so review surfaces can label methodology, assumptions, and analytics provenance explicitly without changing calculations
- trusted PIT alpha attachment is shipped for the narrow `alpha_quality_v1` path when requested by optimizer preview
- optimizer objective selection is now additive: default benchmark-distance remains backward compatible, and hypothetical artifact-backed preview/replay can also persist and replay `maximize_alpha_quality_v1`

### Desktop workflow ownership

- top-level desktop tabs are `Dashboard`, `Exposure`, `Diagnostics`, `Workspace`, `Backtest`, `Strategy Lab`, and `ETF Ranking`
- `Workspace` owns the portfolio-improvement shell, replay review, replay-scoped Monitoring, and proposal review
- Workspace workflow order is explicit: current portfolio -> candidate idea -> candidate formation -> construction rule -> hypothetical replay -> diagnostics change -> saved proposal
- Monitoring can hand off back into Workspace through an explicit review action; it is still review-scoped rather than continuous monitoring infrastructure
- persisted monitor definitions now exist for the narrow `benchmark_trend_overlay_v1` path, with a shipped create/get/list/catalog/recent/evaluate contract family plus additive read-only evaluation-history inspection routes, low-cardinality discovery filters, explicit lifecycle/review-support status metadata, optional definition-scoped latest-evaluation snapshot summary metadata only from the canonical persisted latest-snapshot sidecar that validates structurally and by monitor-definition identity, and append-only canonical persisted evaluation-history entries for successful evaluations

## Narrow boundaries docs should still state explicitly

- ranking is still narrow and ETF-heavy; it is not yet a generalized persisted ranking-run platform across broader universes
- generalized persisted artifact discovery is now shipped only for the supported ETF ranking and intent-bound ETF replacement artifact kinds; broader ranking engines and broader artifact-kind support remain future work
- generalized discovery support remains strict: it does not silently widen to malformed, partially valid, or undocumented artifact states
- persisted construction is shipped and now has read-only policy discovery with backend-owned additive metadata (`family`, `constraints`, `inputs`, `determinism`, `ranking_support`, explicit constraint capability flags including optional `min_position_weight`, optional `max_turnover_weight`, and optional `max_trade_intent_count`, explicit required input flags) plus exact-match server-side filters over those fields only, but the persisted policy set is still narrow; today it supports only `top_n_equal_weight_v1`, `top_n_inverse_rank_weight_v1`, and `top_n_linear_rank_weight_v1`
- single-replacement construction and overlay-aware replay remain narrow review workflows layered alongside the broader persisted construction seam
- optimizer is shipped only as hypothetical preview, persisted handoff, validation, and replay; it does not apply trades or mutate `PortfolioSnapshot`
- optimizer alpha-objective support remains narrow: one additive `alpha_quality_v1` objective only, artifact-backed only, fail-closed on missing, malformed, quarantined, unsupported, stale, or degraded alpha inputs
- cross-sectional research remains narrow: one backend-first persisted research family slice only, one methodology (`alpha_quality_v1`) only, compact summary outputs only, and no portfolio, execution, or realized-performance truth claims
- overlays remain limited to `benchmark_trend_overlay_v1`, one overlay at a time, candidate-side application only, and replay preview only
- monitoring remains a replay-scoped Workspace review surface, not a continuous alerting and review-history system
- monitoring persistence is still narrow: only canonical monitor-definition artifacts for `benchmark_trend_overlay_v1` are shipped, list remains the narrow artifact inventory view, catalog/recent discovery is read-only and additive on top of the create/get/evaluate surface, discovery reads latest status only from the canonical latest-snapshot sidecar and never reconstructs it from history, evaluation-history inspection is read-only and newest-first only, history reads only append-only persisted entries, discovery filters remain limited to low-cardinality persisted metadata, latest-evaluation snapshot metadata is surfaced only when a canonical persisted snapshot sidecar is present and valid, recency is derived strictly from persisted `evaluated_at`, successful evaluation appends one canonical persisted history entry while preserving the latest-snapshot sidecar, and evaluation is review-only with explicit `ok` / `threshold_breach` / `degraded` / `unavailable` outcomes

## Local workspace and artifact behavior that matters to docs

- workspace state restores on launch from local persistence when available
- saved nodes are immutable portfolio-truth snapshots; review artifacts are separate from those snapshots
- seeded candidate metadata, replacement intent, formed candidates, constructed candidates, selected construction rules, hypothetical replays, persisted construction references, optimizer handoffs, and saved proposals all preserve explicit lineage boundaries
- desktop persisted optimizer handoff review state now writes canonical `handoffReference` reopen state only; any legacy cache repair is limited to load-time normalization
- desktop persisted construction and optimizer review state now persists canonical backend `reviewBasisSource` blocks for restore, and saved proposals persist canonical `proposalSource` labels when present
- recreating a draft from a node clears dependent draft-scoped review artifacts so stale review state does not silently cross lineage changes

## What is future, not current

- broader ranking engines across wider universes and non-ETF scopes, using generalized ranking-platform contracts rather than the current ETF-specific path
- more persisted construction policies, richer constraints, turnover models, and broader ranking-to-construction integration
- broader overlay families beyond the current benchmark-trend replay path
- continuous monitoring, alerts, and review history as first-class product capabilities
- persisted monitoring observations, alerts, and review history beyond the current read-only monitor-definition evaluation seam
- optimizer expansion beyond the current hypothetical preview and handoff workflow
- fuller end-to-end quant research workflows that unify ranking, construction, replay, monitoring, and execution planning

## Documentation rules

- use this file for shipped-scope truth
- keep `docs/product/roadmap.md` focused on remaining product work only
- keep `docs/product/technical-roadmap.md` focused on remaining technical work only
- keep `docs/architecture/system-architecture.md`, `docs/finance/financial-methodology.md`, and `docs/contracts/*.md` aligned with any materially meaningful change in trust, withholding, provenance, or financial methodology

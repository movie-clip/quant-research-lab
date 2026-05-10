# Current Product State

This document is the canonical source for what is actually shipped today, what is intentionally narrow, and what remains future work.
Forward-looking epic execution status belongs in `docs/product/epic-roadmap.md`.

## Current product shape

- local-first desktop workflow in `apps/desktop` backed by deterministic engine services in `services/quant-engine`
- desktop owns workflow state and review surfaces; the quant engine owns portfolio math, ranking, construction, optimizer preview, and replay outputs
- the platform is already usable for portfolio analysis, candidate review, persisted construction, and hypothetical optimizer evaluation

## Shipped today

### Portfolio truth and current-state analysis

- broker import, workspace snapshots, immutable saved nodes, and working drafts are shipped product behavior
- imported bootstrap responses include a read-only `ImportAdmissionSummaryV1`, and the desktop Dashboard renders an `Import Admission` card for residual cash, symbol/security identity, parsed position market-value, and NAV/market-value checks
- admission evidence is finite-only: non-finite imported numeric inputs degrade to unavailable evidence instead of emitting `NaN`/`Infinity` in observed, comparison, or delta fields
- desktop-local `ImportAdmissionReviewDispositionV1` metadata is shipped for reviewer rationale and disposition on non-pass checks; it stays outside imported snapshot/admission-summary payloads and has no backend persistence endpoint
- local admission review metadata is sanitized at runtime load/build boundaries without read-time IndexedDB rewrite; valid stale fingerprints are preserved for labels, while malformed records, pass-status evidence, unknown extras, and non-finite captured numeric evidence are dropped from returned clones
- saving local admission review metadata requires captured evidence to match the current non-pass check evidence after null/default normalization; stale or mismatched fingerprints remain stale-labeling evidence only and do not block saving when current evidence matches
- import admission and local review metadata never mutate broker truth, admission state, trust level, workspace creation, imported values, derived portfolio truth, silent fixes, reconstructed trades, tax lots, or corporate actions
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
- immutable persisted review-snapshot artifacts now back saved proposal reopen, a PM-first saved-proposal family inbox, desktop Workspace proposal-family PM review, the desktop Workspace active-thesis cross-family PM review queue, and read-only same-family sibling comparison; backend ships an additive canonical review-only `pm_summary` envelope on the artifact root, both inbox/queue discovery surfaces stay backend-rooted and metadata-only, the active-thesis cross-family queue consumes persisted review-snapshot artifacts plus the active-thesis typed open reference only, desktop treats persisted `pm_summary` as authoritative once the artifact exists, local cached summary state may only mirror it, and the workflow fails closed on missing, malformed, contradictory, mismatched, same-family leakage, cross-family contamination, ambiguous-latest, duplicate-row, or otherwise incompatible persisted snapshot state
- replay rejects provable lineage mismatches across persisted or supplied artifacts; validation lineage is descriptive, not execution approval
- immutable saved proposal artifacts and active thesis restore fail closed on provable internal lineage contradictions

### Persisted construction engine

- construction is now a first-class persisted backend capability, not just an inline review helper
- `POST /construction/run` persists canonical construction artifacts before returning them
- `GET /construction/policies` exposes deterministic backend-owned read-only discovery for the shipped persisted policy catalog, including additive catalog metadata, explicit constraint/input capability flags such as optional `min_position_weight`, optional `max_turnover_weight`, and optional `max_trade_intent_count` support, and single-value exact-match server-side filters over that metadata only; undocumented filter keys, repeated supported scalar filter keys, and malformed present filter values are rejected rather than ignored
- `GET /construction/artifacts/{artifact_id}` reloads persisted artifacts, validates them on read, and fails closed on corruption or malformed payloads
- `POST /backtests/portfolio-allocation/construction-artifact-preview` replays persisted construction artifacts through an explicit artifact-reference boundary
- persisted construction review restore now uses the canonical backend `review_basis` block or typed `preview_handoff` semantics only; desktop does not reconstruct review basis from loose replay fields when canonical basis is present
- persisted construction review reopen now also requires canonical launch-context agreement across `review_basis.launch_context`, `review_basis.preview_handoff`, and `replay_provenance`; desktop and backend fail closed on mismatched ranking artifact id/schema/ranking lineage, current portfolio identity/timestamp, policy id/definition, or fixed `top_n`
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
- `GET /strategy-lab/ranking-artifacts/catalog` exposes additive backend-only generalized catalog discovery metadata across supported persisted ranking artifact kinds, including `etf_ranking`, `intent_bound_etf_replacement_ranking`, and `generic_ranking`
- `GET /strategy-lab/ranking-artifacts/recent` exposes additive backend-only generalized recent discovery metadata across the same supported persisted artifact kinds
- `GET /strategy-lab/etf-ranking/artifacts/recent` exposes newest-first recent artifact discovery with optional `effective_peer_group` filtering
- `GET /strategy-lab/etf-ranking/artifacts/recent/metadata` exposes discovered recent-run filter metadata for current consumers
- shipped ETF ranking artifacts already carry persisted artifact identity, grouped request/effective-inputs metadata, and run-basis metadata for audit and reuse
- the desktop `ETF Ranking` flow can reopen recent persisted runs and carry a selected ranking artifact into draft review as a current shipped workflow
- persisted ETF ranking artifacts can now hand off into persisted construction review through canonical `preflight -> typed handoff -> /construction/run -> persisted construction artifact review`, exposed from both `ETF Ranking` and Workspace `Candidate Idea`; this remains part of a narrow review-only construction bridge limited to persisted ETF ranking artifacts and persisted intent-bound ETF replacement ranking artifacts, and it reuses the existing persisted construction artifact review path rather than widening into optimizer or execution workflow
- persisted intent-bound ETF replacement ranking artifacts are the authoritative downstream truth for replacement review and reload in the shipped slice
- persisted intent-bound ETF replacement ranking artifacts can now also hand off into persisted construction review through the same canonical `preflight -> typed handoff -> /construction/run -> persisted construction artifact review` launch path; the replacement artifact itself stays read-only review context until the user explicitly launches `Review In Construction`, and the same narrow two-family review-only bridge still applies
- construction preflight for those two supported ranking families now returns typed eligibility/readiness semantics before construction launch, so desktop can distinguish supported-but-ineligible artifacts from malformed or unsupported artifact states; the typed gate is advisory review readiness only, and construction run still revalidates persisted artifact truth fail-closed
- desktop `Review In Construction` now consumes authoritative backend `GET /construction/policies` discovery for policy identity on the shipped ranking-to-construction bridge; desktop no longer silently falls back to a hardcoded construction policy id, derives launch compatibility/default status from backend `launch_profile` metadata, auto-selects `top_n_equal_weight_v1` only when discovery truthfully marks it as the single `default`, surfaces only launch-compatible `top_n_equal_weight_v1` and explicit opt-in `top_n_linear_rank_weight_v1`, requires the catalog to truthfully advertise the fixed `launch_top_n = 2` boundary in both row metadata and `launch_profile`, keeps `top_n_inverse_rank_weight_v1` excluded from the desktop launch profile, and otherwise fails closed before construction launch
- the shipped artifact-backed ranking-to-construction launch browsers in Workspace now expose a required decimal `Max Position Weight` field with a shipped default of `0.60` plus optional `Min Position Weight`, optional `Max Turnover Weight`, and optional `Max Trade Intent Count`; desktop validates `0.5 <= max_position_weight <= 1`, treats blank optional fields as omitted, requires `0 < min_position_weight <= 0.5` and `min_position_weight <= max_position_weight` when populated, requires `0 <= max_turnover_weight <= 1` when populated, requires integer `max_trade_intent_count >= 0` when populated, keeps `top_n = 2`, and preserves the same narrow review-only handoff request shape
- ETF Ranking and Workspace persisted ranking construction launch surfaces now also show compact readback text for the selected launch policy, whether it is the shipped default or opt-in path, the fixed `top_n = 2` boundary, required `max_position_weight`, and optional `min_position_weight`, `max_turnover_weight`, and `max_trade_intent_count`
- generalized ranking-artifact preflight now returns only typed `open_handoff` plus truthful eligibility, and ranking-artifact open accepts only that typed handoff; replacement `open_supported`/`replay_eligible` semantics are derived from the same canonical consumer-handoff validation path used during open
- Workspace `Candidate Idea` can now browse recent persisted intent-bound ETF replacement ranking artifacts through generalized recent discovery and reopen them read-only through generalized preflight/open; this persisted replacement reopen path is authoritative artifact context only, keeps state ephemeral in component memory, and does not create intent, mutate workflow state, or launch replay
- generalized discovery is additive only; existing ETF-native and replacement routes stay unchanged
- generalized recent discovery is now fail-closed on malformed ETF recent-index state, malformed artifact payloads, unsupported artifact kinds, unsupported schema versions, and provable identity contradictions
- ETF `recent.jsonl` remains internal operational state for ETF discovery ordering only; it is not a shipped artifact output or generalized reusable contract payload

### Generic ranking artifacts

- `POST /strategy-lab/ranking/run` persists immutable `generic_ranking` artifacts and returns the artifact envelope; this is the first non-ETF ranking family on the generalized ranking platform
- `GET /strategy-lab/ranking/artifacts/recent` and `GET /strategy-lab/ranking/artifacts/{artifact_id}` reload persisted generic ranking artifacts; reload validates schema, identity, and integrity fail-closed
- the generalized cross-kind catalog at `GET /strategy-lab/ranking-artifacts/catalog` and `GET /strategy-lab/ranking-artifacts/recent` now surfaces `generic_ranking` artifacts alongside `etf_ranking` and `intent_bound_etf_replacement_ranking` rows; filter by `artifact_kind=generic_ranking` returns only generic rows
- supported universe kinds: `etf_peer_group`, `custom_list`, `broad_equity_screen`/`sector_screen` (FMP `/stock-screener`), `index_constituent` (FMP `/stable/sp500-constituent` for `index_id="sp500"`)
- supported factor IDs: 11 price-bar factors (momentum 1m/3m/6m/12m/blended, realized_volatility 126d/252d, downside_volatility_126d, max_drawdown 126d/252d, liquidity_60d) plus 8 fundamental factors (4 quality from Novy-Marx/Sloan/AQR formulas reusing existing `optimizer_alpha_service` measures: quality_profitability, quality_cash_generation, quality_accrual, quality_leverage; 4 value via FMP TTM ratios: value_earnings_yield, value_book_to_market, value_fcf_yield, value_ev_ebitda_inverse)
- `ScoreConfig` is versioned with content-addressed `score_config_digest`; `UniverseSpec` snapshots resolved members at run-time as `UniverseSpecSnapshot`; both are persisted in the artifact for audit and reuse
- `EligibilityRecord` per instrument carries explicit `hard_filter_failures` and `soft_filter_flags`; `CompositeScoreTrace` records cross-sectional mean/std per factor for offline normalization replay
- when fundamental factors are requested without an FMP API key, the service emits an explicit warning, returns the artifact with those factor values as null, and confidence drops to `partial` rather than failing the request
- generic ranking artifacts are now construction-eligible: `POST /construction/ranking-artifacts/preflight/{artifact_id}` dispatches `generic_ranking_artifact_*` ids to the same canonical preflight + run boundary used by ETF and replacement artifacts, returning a typed `GenericRankingArtifactConstructionHandoff` for eligible artifacts; excluded rows surface `hard_filter_failures` joined as `exclusion_reason` rather than being silently dropped
- the desktop UI exposes generic ranking construction handoff through Workspace → Candidate Idea → `Persisted Generic Ranking Construction` browser; the standalone `Generic Ranking` tab now shows an informational hand-off note pointing users to the Workspace browser with the artifact id surfaced for cross-tab reference

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

- top-level desktop tabs are `Dashboard`, `Exposure`, `Diagnostics`, `Workspace`, `Backtest`, `Strategy Lab`, `ETF Ranking`, and `Generic Ranking`
- `Workspace` owns the portfolio-improvement shell, replay review, replay-scoped Monitoring, and proposal review
- Workspace workflow order is explicit: current portfolio -> candidate idea -> candidate formation -> construction rule -> hypothetical replay -> diagnostics change -> latest observation alerts -> saved proposal
- Workspace Compare now includes an `Active Alert Review Inbox` for backend-rooted persisted open alert episodes and a definition-scoped `Alert Episode History` drill-in for bounded persisted episode records; both are review-only, fail-closed on malformed payloads, and open the existing definition-scoped timeline review using only persisted episode timeline handoff ids.
- Monitoring now includes a read-only `Monitoring Discipline Overview` for existing `benchmark_trend_overlay_v1` persisted monitor definitions, sourced only from backend-rooted catalog metadata and rendering coverage, freshness, lifecycle, review-readiness, latest-state counts, and a compact persisted definitions table after fail-closed contract/provenance/family validation.
- Monitoring now also includes a read-only `Monitor Family Readiness Overview` that keeps persisted benchmark-trend and data-quality readiness separate from replay-derived signals, shows desktop readiness decision/reason codes, gate breakdowns, evidence summaries, and provenance summaries, and keeps factor drift, concentration drift, benchmark-relative drift, and volatility as non-persisted signal readouts with blocked persistence gates; if replay diagnostics/watch-group evidence is unavailable, signal rows say evidence unavailable rather than readiness.
- Monitoring can hand off back into Workspace through an explicit review action; it is still review-scoped rather than continuous monitoring infrastructure
- persisted `data_quality_monitor_v1` is shipped as a distinct `data_quality` monitor family, not an overlay; it persists definition, latest observation, latest evaluation snapshot, append-only history, alert episode records, catalog/recent discovery, timeline, and inbox evidence for review-only input reliability monitoring with `ok`, `degraded`, and `unavailable` outcomes only, and rejects `threshold_breach` / `action_required` semantics.
- persisted monitor definitions now exist for the narrow `benchmark_trend_overlay_v1` path, with a shipped create/get/list/catalog/recent/latest-observation-alert-inbox/alert-history-queue/recovered-alert-review-queue/evaluate/observation contract family plus additive read-only evaluation-history inspection routes, an additive definition-scoped persisted alert-episode history index route, and an additive definition-scoped alert-review timeline route, low-cardinality discovery filters including latest-observation presence/status/classification/cause-code/recency filters plus latest-snapshot cause-code filters, explicit lifecycle/review-support status metadata, a latest-observation alert inbox sourced only from canonical persisted observation artifacts, an alert-history queue sourced only from canonical persisted evaluation-history entries plus the canonical latest-snapshot sidecar and excluding informational significance states, a recovered alert review queue sourced only from canonical persisted latest observation plus latest-snapshot plus append-only history lineage when the latest persisted state and latest persisted history state are informational but prior persisted alert history exists, a definition-scoped persisted alert-episode history index sourced only from canonical persisted alert-episode records for one persisted definition with explicit ordering/windowing and lifecycle labels, a definition-scoped alert-review timeline sourced only from the canonical latest observation artifact plus append-only canonical evaluation-history entries while preserving distinct observation-rooted vs history-entry-rooted event semantics, authoritative reopen ids, and additive definition-scoped latest-alert-episode semantics, optional definition-scoped latest-observation summary metadata only from the canonical persisted observation artifact that validates structurally and by monitor-definition lineage, optional latest-evaluation snapshot summary metadata only from the canonical persisted latest-snapshot sidecar, and append-only canonical persisted evaluation-history entries for successful evaluations

- active alert-episode inbox sourced only from authoritative persisted alert-episode records is now shipped for monitor definitions; it remains discovery-only, returns open latest episode rows only, and hands back persisted episode-rooted timeline reopen ids without reconstructing from latest observations or history queues. The definition-scoped alert-episode history drill-in is also shipped in Workspace as a bounded, read-only persisted episode history view with explicit truth/provenance/order/window metadata and no execution, trading, remediation, or complete chronology claim.

## Narrow boundaries docs should still state explicitly

- ranking is still narrow and ETF-heavy; it is not yet a generalized persisted ranking-run platform across broader universes
- ranking-to-construction handoff review is now shipped only for two ranking artifact families: persisted ETF ranking artifacts and persisted intent-bound ETF replacement ranking artifacts; broader ranking-family construction eligibility remains future work
- cross-sectional research artifacts remain research-only and are explicitly not construction-eligible in the shipped desktop workflow
- generalized persisted artifact discovery is now shipped only for the supported ETF ranking and intent-bound ETF replacement artifact kinds; broader ranking engines and broader artifact-kind support remain future work
- generalized discovery support remains strict: it does not silently widen to malformed, partially valid, or undocumented artifact states
- persisted construction is shipped and now has read-only policy discovery with backend-owned additive metadata (`family`, `constraints`, `inputs`, `determinism`, `ranking_support`, explicit constraint capability flags including optional `min_position_weight`, optional `max_turnover_weight`, and optional `max_trade_intent_count`, explicit required input flags, and canonical `launch_profile` metadata for the ranking-artifact review/handoff bridge) plus exact-match server-side filters over those fields only, but the persisted policy set is still narrow; today it supports only `top_n_equal_weight_v1`, `top_n_inverse_rank_weight_v1`, and `top_n_linear_rank_weight_v1`
- desktop policy authority is now stronger, but the visible ranking-to-construction bridge remains intentionally parameter-light: policy identity and launch compatibility/default status are backend-authoritative while `top_n` stays fixed at `2` and is now explicit in backend discovery plus launch-profile metadata plus handoff-path validation, desktop launch pickers surface only `top_n_equal_weight_v1` plus explicit opt-in `top_n_linear_rank_weight_v1`, only `max_position_weight` plus optional `min_position_weight`, optional `max_turnover_weight`, and optional `max_trade_intent_count` are desktop-editable, no new ranking families are exposed, and some ranking-entry portfolio lineage assumptions remain narrow review-only defaults
- single-replacement construction and overlay-aware replay remain narrow review workflows layered alongside the broader persisted construction seam
- optimizer is shipped only as hypothetical preview, persisted handoff, validation, and replay; it does not apply trades or mutate `PortfolioSnapshot`
- optimizer alpha-objective support remains narrow: one additive `alpha_quality_v1` objective only, artifact-backed only, fail-closed on missing, malformed, quarantined, unsupported, stale, or degraded alpha inputs
- cross-sectional research remains narrow: one backend-first persisted research family slice only, one methodology (`alpha_quality_v1`) only, compact summary outputs only, and no portfolio, execution, or realized-performance truth claims
- overlays remain limited to `benchmark_trend_overlay_v1`, one overlay at a time, candidate-side application only, and replay preview only
- monitoring remains a replay-scoped Workspace review surface plus persisted discipline and family-readiness metadata overviews, not a continuous alerting, scheduling, remediation, promotion, threshold-management, or review-history system
- monitoring persistence is still narrow: only canonical monitor-definition artifacts, one canonical latest observation artifact per definition, one canonical latest-evaluation snapshot sidecar per definition, and append-only canonical evaluation-history entries are shipped for `benchmark_trend_overlay_v1` and `data_quality_monitor_v1`; list remains the narrow artifact inventory view, catalog/recent discovery is read-only and additive on top of the create/get/evaluate surface, discovery reads latest observation state only from the canonical persisted observation artifact and never reconstructs it from latest-snapshot sidecars or history, evaluation-history inspection is read-only and newest-first only, definition-scoped alert-review timeline is read-only and newest-first only, recovered alert review queue remains discovery-only and newest-first only, history reads only append-only persisted entries, discovery filters remain limited to low-cardinality persisted metadata including `monitor_family`, latest-observation presence/status/classification/cause-code/recency, and latest-snapshot cause-code, latest-observation metadata is surfaced only when a canonical persisted observation artifact is present and valid, latest-evaluation snapshot metadata remains additive, recency is derived strictly from persisted `evaluated_at`, successful evaluation overwrites the canonical observation and latest-snapshot sidecars while appending one canonical persisted history entry, degraded and unavailable outcomes persist explicit non-null cause codes, and data-quality persistence remains evidence-only input reliability monitoring rather than remediation, scheduling, or portfolio advice.

- monitoring persistence also now exposes authoritative persisted alert-episode records through a newest-first active alert-episode inbox; that inbox excludes recovered, closed, and informational-only states and stays distinct from latest-observation, recovered-review, history, and definition-scoped timeline surfaces

## Local workspace and artifact behavior that matters to docs

- latest definition-scoped alert-episode metadata is additive and backend-rooted: one latest episode per persisted `monitor_definition_id`, boundaries derive only from canonical persisted observation plus append-only persisted evaluation-history lineage, active/recovered state stays definition-scoped only, recovery semantics remain review-only rather than execution truth, and the additive definition-scoped alert-episode history index now exposes authoritative persisted `open` / `recovered` / `closed` episode records for bounded discovery and drill-in only
- active alert-episode discovery is now also backend-rooted: the shipped active inbox wraps authoritative persisted open episode records only, preserves explicit lifecycle/provenance/order semantics, and uses only persisted episode and timeline ids to reopen the existing definition-scoped review surfaces

- workspace state restores on launch from local persistence when available
- import admission review dispositions are desktop-local metadata anchored to the imported source node; derived nodes may display inherited admission evidence, but saving dispositions updates only the imported-source local metadata anchor
- saved nodes are immutable portfolio-truth snapshots; review artifacts are separate from those snapshots
- seeded candidate metadata, replacement intent, formed candidates, constructed candidates, selected construction rules, hypothetical replays, persisted construction references, optimizer handoffs, and saved proposals all preserve explicit lineage boundaries
- desktop persisted optimizer handoff review state now writes canonical `handoffReference` reopen state only; any legacy cache repair is limited to load-time normalization
- desktop persisted construction and optimizer review state now persists canonical backend `reviewBasisSource` blocks for restore, and saved proposals persist canonical top-level `proposalSource` labels for restore/readout with load-only dual-omission legacy hydration
- desktop definition-scoped monitor review in `Workspace` now launches from the monitoring-to-workspace handoff using `monitor_definition_id` only as the entrypoint, then reloads `GET /backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline` as the sole authoritative review-state source and persists only timeline-backed restore state locally
- recreating a draft from a node clears dependent draft-scoped review artifacts so stale review state does not silently cross lineage changes

## What is future, not current

- broader ranking engines across wider universes and non-ETF scopes, using generalized ranking-platform contracts rather than the current ETF-specific path
- more persisted construction policies, richer constraints, turnover models, and broader ranking-to-construction integration
- broader overlay families beyond the current benchmark-trend replay path
- continuous monitoring, alerts, and review history as first-class product capabilities
- broader persisted monitor families beyond current narrow `benchmark_trend_overlay_v1` and `data_quality_monitor_v1` review-only seams
- optimizer expansion beyond the current hypothetical preview and handoff workflow
- fuller end-to-end quant research workflows that unify ranking, construction, replay, monitoring, and execution planning

## Documentation rules

- use this file for shipped-scope truth
- keep `docs/product/roadmap.md` focused on remaining product work only
- keep `docs/product/technical-roadmap.md` focused on remaining technical work only
- keep `docs/architecture/system-architecture.md`, `docs/finance/financial-methodology.md`, and `docs/contracts/*.md` aligned with any materially meaningful change in trust, withholding, provenance, or financial methodology

# Backtest Field Inventory

This document inventories financially meaningful fields shown in the desktop portfolio-allocation workflow and the adjacent backend replay-preview and shipped monitor-definition review/discovery contracts that feed or bound it today.

For shipped workflow boundaries, use `docs/product/current-product-state.md`.

## Purpose

For each visible backtest value, we want a traceable chain:
- UI field
- app state source
- engine source
- replay or market-data source
- truth class and trust semantics

## Current Root Sources

The portfolio-allocation workflow currently renders from, reopens through, or remains contract-bound to these root inputs:

1. `result: PortfolioAllocationBacktestResponse | null`
   - returned by `POST /backtests/portfolio-allocation`
   - canonical baseline-vs-candidate replay response

2. `hypotheticalReplayResult: HypotheticalReplacementReplayResponse | null`
   - returned by `POST /backtests/portfolio-allocation/replacement-intent-preview`
   - replacement-intent replay plus derivation and lineage metadata

3. `overlayAwareReplayResult: OverlayAwareHypotheticalReplayResponse | null`
   - returned by `POST /backtests/portfolio-allocation/replacement-intent-overlay-preview`
   - overlay-aware hypothetical replay plus overlay application metadata

4. `constructedCandidate: SingleReplacementCandidateConstructionResponse | null`
   - returned by `POST /backtests/candidate-construction/replacement-intent`
   - backend review-oriented candidate construction for single-replacement flows

5. `constructionArtifactReplay: ConstructionArtifactReplayResponse | null`
    - returned by `POST /backtests/portfolio-allocation/construction-artifact-preview`
    - replay from the typed validation-produced `preview_handoff` for an explicit persisted construction artifact reference

6. `optimizerPreview: OptimizerPreviewResponse | null`
   - returned by `POST /optimizer/preview`
   - hypothetical optimizer output plus persisted handoff reference when feasible

7. `optimizerHandoffReplay: OptimizerHandoffReplayResponse | null`
   - returned by `POST /backtests/portfolio-allocation/optimizer-handoff-preview`
   - replay from an explicit persisted optimizer handoff reference

8. `optimizerHandoffValidation: OptimizerHandoffValidationResponse | null`
   - returned by `POST /backtests/portfolio-allocation/optimizer-handoff/constraints`
   - validation and replay-output policy surface for persisted optimizer handoffs

9. `monitorDefinitionCreateRequest: CreateMonitorDefinitionRequest`
   - posted to `POST /backtests/monitor-definitions`
   - canonical write contract for creating immutable `benchmark_trend_overlay_v1` and `data_quality_monitor_v1` monitor-definition artifacts

10. `monitorDefinition: MonitorDefinitionArtifact | null`
   - returned by `POST /backtests/monitor-definitions` and `GET /backtests/monitor-definitions/{monitor_definition_id}`
   - canonical persisted review-only monitor definition artifact for `benchmark_trend_overlay_v1` or `data_quality_monitor_v1`

11. `monitorDefinitionList: MonitorDefinitionArtifactListResponse | null`
   - returned by `GET /backtests/monitor-definitions`
   - additive read-only artifact inventory with narrow identity fields only

12. `monitorDefinitionCatalog: MonitorDefinitionCatalogResponse | null`
    - returned by `GET /backtests/monitor-definitions/catalog`
    - additive read-only discovery catalog for persisted `benchmark_trend_overlay_v1` and `data_quality_monitor_v1` monitor-definition artifacts, including typed row provenance, lifecycle/review-support status metadata, and optional latest-evaluation snapshot summary only when the canonical persisted latest-snapshot sidecar exists, is structurally complete, and validates against the persisted monitor definition

13. `monitorDefinitionRecent: MonitorDefinitionRecentResponse | null`
    - returned by `GET /backtests/monitor-definitions/recent`
    - additive read-only newest-first discovery for persisted `benchmark_trend_overlay_v1` and `data_quality_monitor_v1` monitor-definition artifacts, derived from authoritative persisted artifact metadata plus the canonical persisted latest-snapshot sidecar only, carrying typed recent-order provenance, and exposing optional persisted latest-evaluation snapshot summary metadata without synthesizing history when absent

14. `monitorDefinitionLatestObservationAlertInbox: MonitorDefinitionLatestObservationAlertInboxResponse | null`
     - returned by `GET /backtests/monitor-definitions/latest-observation-alert-inbox`
     - additive read-only newest-first discovery inbox rooted in authoritative persisted `monitor_definition_observation_artifact_v1` rows only; rows stay review-only, exclude informational latest observations, and carry authoritative persisted observation handoff identity for definition-scoped review reopening only

15. `monitorDefinitionAlertHistoryQueue: MonitorDefinitionAlertHistoryQueueResponse | null`
     - returned by `GET /backtests/monitor-definitions/alert-history-queue`
     - additive read-only newest-first review queue of canonical persisted monitor-definition evaluation-history entries whose persisted `significance_status` is alert-eligible (`degraded` or `action_required`) only; each row is history-entry rooted, the latest row for a monitor definition must align with the canonical latest-snapshot sidecar, and informational history entries are excluded

16. `monitorDefinitionRecoveredAlertReviewQueue: MonitorDefinitionRecoveredAlertReviewQueueResponse | null`
     - returned by `GET /backtests/monitor-definitions/recovered-alert-review-queue`
     - additive read-only newest-first recovered review discovery queue sourced only from authoritative persisted latest observation plus latest snapshot plus append-only history lineage; rows exist only when the latest persisted state is informational and aligned while an older persisted history entry for the same definition remains alert-eligible, and rows reopen the existing definition-scoped alert-review timeline by authoritative persisted observation id only

17. `monitorDefinitionActiveAlertEpisodeInbox: MonitorDefinitionActiveAlertEpisodeInboxResponse | null`
     - returned by `GET /backtests/monitor-definitions/active-alert-episode-inbox`
     - additive read-only newest-first discovery inbox rooted in authoritative persisted `monitor_definition_alert_episode_record_v1` rows only; rows stay open-episode-rooted, preserve explicit persisted lifecycle/windowing provenance, and hand off to reopen the existing definition-scoped alert-review timeline by authoritative persisted ids only

18. `monitorEvaluationRequest: EvaluateMonitorDefinitionObservationRequest`
    - posted to `POST /backtests/monitor-definitions/{monitor_definition_id}/evaluations`
    - canonical read-only evaluation input combining current imported portfolio truth with explicit benchmark observation lineage for benchmark-trend definitions or explicit market-data reliability evidence for data-quality definitions

19. `monitorEvaluation: MonitorDefinitionObservationEvaluationResponse | null`
       - returned by `POST /backtests/monitor-definitions/{monitor_definition_id}/evaluations`
       - review-only evaluation of a persisted monitor definition against current portfolio truth and required benchmark observation input; on success it overwrites the one canonical latest-evaluation snapshot sidecar for discovery and appends one canonical persisted evaluation-history entry for append-only inspection

20. `monitorDefinitionObservation: MonitorDefinitionObservationArtifact | null`
      - returned by `GET /backtests/monitor-definitions/{monitor_definition_id}/observation`
      - definition-scoped read-only open surface for exactly one authoritative persisted `monitor_definition_observation_artifact_v1`; review-only inspection stays observation-rooted, never reconstructs from snapshots/history/inbox rows, and fails closed when the persisted observation is absent or invalid

21. `monitorEvaluationHistory: MonitorDefinitionEvaluationHistoryResponse | null`
      - returned by `GET /backtests/monitor-definitions/{monitor_definition_id}/evaluation-history`
      - additive read-only newest-first inspection list for canonical persisted monitor-definition evaluation-history entries only; no rollups, analytics, or synthesized history

22. `monitorEvaluationHistoryEntry: MonitorDefinitionEvaluationHistoryEntryResponse | null`
      - returned by `GET /backtests/monitor-definitions/{monitor_definition_id}/evaluation-history/{history_entry_id}`
      - additive read-only inspection payload for one canonical persisted evaluation-history entry scoped to the persisted monitor definition

23. `monitorAlertEpisodeHistory: MonitorDefinitionAlertEpisodeHistoryResponse | null`
      - returned by `GET /backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history`
      - additive read-only newest-first persisted alert-episode index for one persisted `monitor_definition_id` only; rows are authoritative persisted episode records with explicit lifecycle labels, explicit windowing metadata, and timeline handoffs for drill-in only

24. `monitorAlertReviewTimeline: MonitorDefinitionAlertReviewTimelineResponse | null`
      - returned by `GET /backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline`
      - additive read-only definition-scoped review timeline that merges at most one canonical latest observation artifact plus append-only canonical evaluation-history entries while keeping observation-rooted and history-entry-rooted event semantics distinct

Important rules:
- imported holdings may seed workflows, but replay outputs remain hypothetical and must never be confused with imported broker-truth history
- replacement-intent, construction-artifact, and optimizer-handoff replay weights are backend-owned; desktop must not synthesize candidate weights locally for those workflows
- backtest diagnostics are synthetic replay diagnostics with explicit provenance, not imported portfolio diagnostics
- persisted construction artifacts and optimizer handoffs are lineage-bearing hypothetical artifacts, not applied portfolio truth
- persisted construction artifacts remain the authoritative hypothetical candidate truth at the validation-to-preview handoff boundary, regardless of whether the catalog policy is `top_n_equal_weight_v1`, `top_n_inverse_rank_weight_v1`, or `top_n_linear_rank_weight_v1`
- persisted monitor definitions are immutable review artifacts; evaluation is read-only and consumes current imported portfolio truth plus either explicit benchmark observation lineage or explicit data-quality evidence lineage, depending on monitor family
- monitor-definition catalog/recent discovery is additive and read-only; it does not change create/get/evaluate responsibilities and it must surface typed provenance/status metadata from persisted backend sources rather than desktop-reconstructed metadata or evaluation-history reconstruction
- monitor-definition latest-observation and active-alert-episode inboxes are additive and read-only discovery surfaces only; clients preserve observation-rooted vs alert-episode-rooted semantics, keep their explicit review-only truth labels, and reopen definition-scoped review only by authoritative persisted ids already carried on the route payloads
- monitor-definition evaluation history is additive and read-only; clients inspect canonical persisted history entries by `monitor_definition_id` and `history_entry_id` rather than reconstructing history from the latest-snapshot sidecar
- monitor-definition alert-episode history is additive and read-only; clients inspect canonical persisted episode rows by `monitor_definition_id` and explicit `episode_id` windowing only, and they must preserve explicit `lifecycle_status`, `latest_for_monitor_definition`, `ordering`, and `windowing` metadata rather than inferring lifecycle from mixed sources
- monitor-definition alert review timeline is additive and read-only; clients consume the backend timeline payload directly, preserve explicit `event_kind` / `event_semantics`, and reopen existing observation or history review surfaces by authoritative persisted ids only
- desktop monitoring-to-workspace handoff may carry `monitor_definition_id` only as a navigation entrypoint into definition-scoped review, but once that handoff occurs the desktop must reload the definition-scoped alert-review timeline route and must not retain latest-observation inbox, active-alert-episode inbox, or other inbox/queue payloads as authoritative definition review state

## Truth and Trust Semantics

- `replay-derived`
  - produced directly from allocation replay using candidate/reference weights and aligned price histories
- `diagnostics-derived`
  - produced from replay-derived states plus historical benchmark/factor market data
- `synthetic-derived`
  - produced from synthetic replay snapshots created to support diagnostics calculations
- `persisted-artifact-provenance`
  - produced from immutable persisted artifact lineage such as construction selection traces or optimizer handoff references
- `unavailable-required`
  - must render `n/a`, hidden state, or explicit error when required replay or provenance inputs are missing

Status rule:
- `withheld` means user-facing investor-economics output is intentionally suppressed even when broader replay evidence exists
- `unavailable` means the underlying trustworthy path does not exist

## Provenance Rules

### Replay diagnostics provenance

Portfolio-allocation diagnostics currently expose typed provenance:
- `snapshot_basis = synthetic_replay_snapshot`
- `historical_basis = market_data_history`

This means replay diagnostics are built from:
- a synthetic snapshot from replay ending weights
- replay-derived daily states from the equity curve
- historical benchmark/factor market data

### Investor-economics withholding

- replay responses carry explicit `investor_economics_status`
- when status is `withheld`, user-facing investor-economics metrics and any derived comparative views from that basis must stay suppressed or `null`
- current withholding reason is explicit trust policy, not a generic market-data failure

### Construction artifact replay provenance

- `POST /backtests/portfolio-allocation/construction-artifact-validation` is the canonical producer of `preview_handoff`
- `preview_handoff` is the authoritative validation-to-preview boundary; desktop persisted open posts it verbatim to `POST /backtests/portfolio-allocation/construction-artifact-preview`
- `constructionArtifactReplay.review_basis` is the shipped canonical persisted review-basis contract for desktop restore/open; after persistence, desktop restore must consume this artifact-backed basis block and must not reconstruct review basis from loose replay fields or local defaults
- `constructionArtifactReplay.review_basis.preview_handoff` is the canonical typed handoff payload carried into persisted review state; missing, malformed, mismatched, or unsupported review-basis identity fails closed
- `constructionArtifactReplay.review_basis.launch_context` is the canonical persisted reopen lineage block for the shipped ranking-to-construction bridge; it must match echoed `replay_provenance` for `construction_artifact_id`, ranked-universe artifact id/schema, `ranking_id`, `ranking_methodology_id`, `ranking_as_of_date`, `current_portfolio_artifact_id`, `current_portfolio_as_of_timestamp`, `policy_id`, `policy_definition_id`, and fixed `top_n`
- `constructionArtifactReplay.replay.methodology_provenance` is shipped additive review-context provenance for methodology, assumptions, and analytics text; it remains descriptive only and does not change replay math
- the preview route may accept the legacy request shape for compatibility, but handoff-shaped payloads must be complete, supported handoffs and mixed handoff-plus-legacy payloads are rejected
- handoff consumption fails closed on missing or unsupported `handoff_kind` and on persisted artifact integrity mismatches, including construction artifact id mismatch
- `POST /backtests/portfolio-allocation/construction-artifact-preview` echoes lineage from the persisted construction artifact
- `constructionArtifactReplay.replay_provenance` now explicitly carries additive launch-lineage fields for ranked-universe schema version, ranking as-of date, current-portfolio as-of timestamp, and launch `top_n`; desktop persisted open must fail closed if these disagree with canonical review basis
- persisted construction artifacts carry both resolved `normalized_inputs.policy_definition_id` and full normalized replay inputs, while preview/replay still consumes persisted `final_target_weights` and normalized baseline inputs rather than recalculating from catalog state
- for the shipped desktop ranking-to-construction bridge, policy identity is now sourced from backend `GET /construction/policies` discovery rather than a silent desktop fallback; the bridge remains limited to persisted ETF ranking and persisted intent-bound ETF replacement ranking artifacts, desktop launch compatibility/default status is derived from backend `launch_profile`, desktop launch pickers surface only launch-compatible `top_n_equal_weight_v1` and explicit opt-in `top_n_linear_rank_weight_v1`, equal-weight remains the only auto-selected default only when discovery truthfully marks it as the single `default`, inverse-rank stays explicitly excluded from the desktop launch profile, desktop launch must pass an explicitly selected discovered `policy_id`, desktop must fail closed if discovery does not truthfully advertise canonical `launch_profile` metadata, `launch_top_n = 2`, or consistent `policy_id` / `policy_definition_id` / `ranking_support` launch semantics, persisted construction run lineage must echo both requested `policy_id`, non-empty `policy_definition_id`, and `normalized_inputs.top_n = 2`, decimal `max_position_weight` remains required, optional decimal `min_position_weight` may be supplied or omitted, and optional decimal `max_turnover_weight` plus optional integer `max_trade_intent_count` may now also be supplied or omitted from the same review-only bridge without widening ranking-family or policy scope
- `replay_provenance.hard_constraints` is required and is echoed from persisted artifact contract truth only; preview/open must not omit it, widen it, or reconstruct it from desktop defaults
- the echoed `replay_provenance.hard_constraints` shape is exact and fail-closed: `full_investment`, `long_only`, `eligible_ranked_universe_only`, `max_position_weight`, `min_position_weight`, `max_turnover_weight`, and `max_trade_intent_count`; nullable fields stay explicit `null` when the persisted artifact carries no value
- `replay_provenance.selection_rule_trace` must be echoed from persisted artifact provenance only
- `replay_provenance.turnover_diagnostics_status` and `replay_provenance.turnover_diagnostics_v1` must also be echoed from the persisted artifact only; replay/open must not reconstruct, repair, or mutate turnover provenance
- `replay_provenance.weighting_trace_status` and `replay_provenance.weighting_trace_v1` must also be echoed from the persisted artifact only; replay/open must not reconstruct, repair, or mutate weighting-trace provenance
- the only legacy compatibility fallback is the exact dual-missing case where both persisted weighting-trace fields are absent; that case loads as `weighting_trace_status = unavailable_legacy_artifact` with `weighting_trace_v1 = null`
- the only legacy compatibility fallback for turnover provenance is the exact dual-missing case where both persisted turnover-diagnostics fields are absent; that case loads as `turnover_diagnostics_status = unavailable_legacy_artifact` with `turnover_diagnostics_v1 = null`
- any other present malformed, partial, unsupported, or contradictory turnover-diagnostics state fails closed, including unsupported `diagnostics_version`, missing required subfields, requested/limit/evaluation contradictions, and feasibility links that disagree with persisted artifact outputs
- any other present malformed, partial, unsupported, or contradictory weighting-trace state fails closed, including missing required populated fields, unsupported `trace_version`, partial stage payloads, and status/value contradictions
- the trace is descriptive provenance and must not drive replay math
- legacy empty traces normalize only at artifact-load time; replay does not invent trace content later

### Optimizer handoff provenance

- `POST /optimizer/preview` can persist an immutable handoff reference for feasible hypothetical previews
- the persisted optimizer handoff reopen identity is `handoffReference`; `handoffReference.handoff_id` remains the canonical identity and `handoffReference.artifact_id` remains lineage and integrity metadata only
- `POST /backtests/portfolio-allocation/optimizer-handoff-preview` consumes that explicit persisted reference only
- `POST /backtests/portfolio-allocation/optimizer-handoff/constraints` remains validation/preflight only; it does not open replay by itself
- when `POST /backtests/portfolio-allocation/optimizer-handoff/constraints` receives an explicit candidate replay window, it may emit additive typed `replay_handoff`; that handoff is validation output only and desktop open may post it verbatim to `POST /backtests/portfolio-allocation/optimizer-handoff-preview`
- `optimizerHandoffValidation.replay_handoff` is the canonical typed validation-to-open boundary for the shipped desktop optimizer reopen path; mixed handoff-plus-legacy replay request fields, missing handoffs, unsupported handoff kinds, or handoff-reference mismatches fail closed
- desktop persisted review writes persist `handoffReference` as the only reopen identity object, and any repair of older cache rows is load-only
- `optimizerHandoffReplay.review_basis` is the shipped canonical persisted review-basis contract for desktop restore/open; after persistence, desktop restore must consume this artifact-backed basis block and must not rebuild review basis from replay result fields or validation payloads
- `optimizerHandoffReplay.review_basis.handoff_reference` is the canonical persisted reopen identity echoed inside the replay payload and must match replay `handoff_id` and `artifact_id`
- desktop persisted construction review writes persist `review_basis.preview_handoff` inside cached review basis and fail closed on missing, malformed, unsupported, or replay-param-conflicting preview handoff state
- optimizer handoff replay carries persisted `return_basis_attestation` and `replay_output_policy`
- optimizer handoff replay also carries additive `replay.methodology_provenance` so review surfaces keep explicit methodological provenance without changing analytics semantics
- benchmark-relative replay fields may be suppressed from the top-level replay payload when attested trust is narrower than the computed engine surface

## Key Methodology Notes

### Replay methodology

The current backtest methodology string is:
- `Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions.`

Implementation:
- `services/quant-engine/app/services/portfolio_backtest_engine.py` -> `METHODOLOGY`
- `services/quant-engine/app/backtests/portfolio_engine.py` -> `PortfolioAllocationBacktestEngine`

### Comparison deltas

Comparison rows in the UI are built as:

```text
delta = candidate - baseline
```

Implementation:
- `services/quant-engine/app/services/portfolio_backtest_engine.py` -> `_diff(...)`

## Field Notes By Workflow

### Hypothetical replacement replay

- `hypotheticalReplayResult.derivation`
  - authoritative derivation metadata, including the actual construction rule consumed by replay
- `hypotheticalReplayResult.proposal.proposal_source`
  - additive shipped proposal-source label describing review-only proposal truth, draft portfolio non-application, and proposal review scope; saved proposal artifacts persist the same semantics in top-level desktop storage as authoritative `proposalSource`, desktop validates any nested saved copy only as a load-boundary compatibility fallback, and desktop may derive that exact label only for the documented legacy local-artifact dual-omission case when both persisted locations are absent
- `hypotheticalReplayResult.replay_provenance`
  - authoritative lineage block for direct preview vs constructed-candidate replay, upstream lineage, ranking seed lineage, and echoed validation lineage
- `hypotheticalReplayResult.baseline_weights` / `candidate_weights`
  - backend-derived replay inputs; desktop must not construct these locally
- replay rejects provable lineage mismatches between `constraint_validation` and `constructed_candidate`
- validation lineage is descriptive; replay does not currently require approval status to run

### Review snapshot artifacts

- `POST /backtests/review-snapshots` persists the canonical immutable review-snapshot artifact used for saved proposal reopen and comparison
- persisted review-snapshot identity is `identity.artifact_id`; desktop persists that id as `reviewSnapshotArtifactId` on the saved proposal record and uses it as the authoritative downstream reopen/comparison input
- review-snapshot artifacts also persist canonical `proposal_capture`; this additive block is the authoritative saved-proposal capture contract for reopen/readout and carries the typed `open_handoff`, canonical proposal identity/lineage, replay provenance, and review-basis metadata without rebuilding canonical input from loose workspace fields
- desktop saved-proposal storage also persists `reviewSnapshotPMSummary` only as a strict local mirror of artifact `pm_summary`; once the artifact exists, artifact `pm_summary` remains the sole authoritative PM summary input for reopen/readout/comparison
- review-snapshot artifacts carry authoritative `identity`, `lineage`, `review_basis`, `truth_labels`, additive `compact_summary`, additive canonical `pm_summary`, and `source_payload`
- `proposal_capture.open_handoff` is the canonical typed artifact-backed reopen input; open/readout must consume that typed boundary, validation/preflight remains separate, and desktop must fail closed on missing or contradictory persisted `proposal_capture`
- review-snapshot `pm_summary` is the canonical review-only PM summary envelope for saved proposal reopen/readout and comparison; backend schema is the contract root, desktop consumes the persisted envelope or typed handoff/open path only, and the same envelope shape is reused for saved proposal (`role=saved_proposal`) and comparison (`role=baseline` / `role=candidate`) without changing replay math or portfolio truth
- review-snapshot `pm_summary` inventory is explicit: provenance, truth_labels, replay_type, replay_status, investor_economics_status, review_basis, methodology, assumptions, analytics_summary, and diagnostics_summary
- review-snapshot `compact_summary` remains additive and descriptive only; it continues to hold the compact analytics/diagnostics summary mirrored into `pm_summary` for the canonical review-only readout envelope
- if analytics fields are surfaced, they preserve benchmark separation, cash-flow-neutral replay basis, neutral methodology text, and stable methodology/assumptions fields copied from the authoritative replay payload
- `POST /backtests/review-snapshots/open` accepts only typed `review_snapshot_open_handoff_v1` and returns the persisted artifact, the persisted canonical `pm_summary`, and the authoritative replay payload carried in the artifact; desktop must not reconstruct canonical input from loose saved-proposal fields
- `POST /backtests/review-snapshots/family-review` accepts only typed `review_snapshot_open_handoff_v1`, keys the PM review slice by the full persisted `family_key` bundle (`workspace_id`, `source_draft_id`, `source_base_node_id`, `proposal_family_id`, `source_kind`), and returns only persisted same-family sibling artifacts with canonical `pm_summary`, typed open handoff, lineage, and compare-eligibility metadata
- `POST /backtests/review-snapshots/family-inbox` is an additive read-only PM-first saved-proposal family inbox rooted in backend serialization; it keys rows by the full persisted `family_key` bundle, returns persisted-family rows only, orders families newest-first by authoritative persisted artifact file mtime, and surfaces one authoritative latest/anchor identity plus canonical `proposal_capture`, canonical `pm_summary`, sibling count, compare-readiness metadata, lineage, proposal-source labels, truth labels, and compact PM-facing summary fields copied from persisted `pm_summary` only
- `POST /backtests/review-snapshots/active-thesis-cross-family-queue` is an additive backend-rooted active-thesis cross-family discovery queue that the desktop Workspace shell consumes directly; it uses only the active-thesis typed open handoff plus persisted review-snapshot artifacts, filters to the same persisted workspace/draft/base/source-kind lineage under one active thesis while requiring explicit family separation by distinct `proposal_family_id`, returns queue metadata only, and never opens replay payloads or becomes family review implicitly
- active-thesis cross-family queue rows are keyed by canonical persisted latest artifact identity plus full persisted lineage and family key, carry explicit `family_separation`, proposal-source labels, truth labels, trust/withholding visibility, and PM-facing summary fields copied from persisted `pm_summary` only, and exclude replay/open payloads, draft-state reconstruction, imported-portfolio-state reconstruction, and replay-cache reconstruction
- active-thesis cross-family queue ordering is deterministic and fail-closed: rows sort by authoritative persisted latest-saved timestamp descending then canonical artifact id descending; discovery rejects ambiguous latest selection inside a family, duplicate canonical rows, ordering contradictions, identity mismatches, lineage contradictions, same-family leakage, cross-family contamination, missing/malformed artifacts, and unsupported present payload versions
- family inbox/open responsibilities stay distinct: inbox discovery never opens replay payloads, never becomes family review implicitly, and never reconstructs rows from draft workspace state, imported portfolio state, replay cache, or loose saved-proposal fields
- family inbox fails closed on missing or malformed persisted artifacts, unsupported or malformed `pm_summary`, any missing/malformed/mismatched `family_key` component, lineage contradictions, identity mismatches, cross-family contamination, duplicate family keys, and ambiguous latest-anchor selection
- review-snapshot open fails closed on missing artifact, missing `pm_summary`, malformed present payloads, unsupported `pm_summary` version or role, schema/version mismatch, artifact identity mismatch, local-vs-persisted `pm_summary` mismatch, and lineage contradictions inside the persisted artifact
- `POST /backtests/review-snapshots/compare` accepts exactly one baseline and one candidate artifact reference or typed handoff and compares only compatible persisted same-family review snapshots
- comparison compatibility is strict and fail-closed on identical artifact reuse, `proposal_family_id` mismatch, lineage contradiction across workspace/draft/base/source-kind keys, mismatched replay type, mismatched replay window, mismatched benchmark symbol, mismatched derivation basis, mismatched replay assumptions, schema/version mismatch, identity mismatch, and malformed present fields
- comparison response keeps explicit baseline/candidate roles, `family_key`, provenance, benchmark separation, methodology, assumptions, analytics comparison fields, and `baseline_pm_summary` / `candidate_pm_summary` distinct
- any PM-summary analytics surfaced in the active-thesis cross-family queue remain copied from authoritative persisted `pm_summary` only and preserve explicit benchmark separation, cash-flow-neutral replay-basis semantics, neutral methodology text, stable methodology/assumptions fields, and explicit investor-economics withholding/trust visibility semantics

### Construction artifact replay

- `constructionArtifactReplay.replay_provenance.selection_rule_trace`
  - authoritative persisted selection trace for the artifact replayed
- `constructionArtifactReplay.replay_provenance.hard_constraints`
  - authoritative persisted hard-constraint block for the replayed artifact; this is replay provenance describing the persisted hypothetical construction contract, not imported portfolio truth or desktop-computed settings
- `constructionArtifactReplay.replay_provenance.hard_constraints.max_trade_intent_count`
  - authoritative persisted hard cap on canonical construction `trade_intents`; when present it is evaluated from the persisted artifact `trade_intents` length, not from `turnover_diagnostics_v1.trade_intent_context.intent_count` or desktop-reconstructed state
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_status`
  - authoritative persisted turnover-diagnostics availability label; `available` requires a present valid persisted `turnover_diagnostics_v1`, and `unavailable_legacy_artifact` is reserved only for the exact dual-missing legacy artifact case
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_v1`
  - authoritative persisted turnover diagnostics echoed verbatim from the artifact when present and valid; this is artifact-backed hypothetical construction diagnostics only and never replay math input
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_v1.symbol_contributions`
  - authoritative persisted per-symbol turnover contribution diagnostics echoed verbatim from the artifact; rows are ordered by symbol ascending and provide the stable reconciliation bridge from `current_weight` and `target_weight` through signed `delta_weight`, `absolute_delta_weight`, and `turnover_contribution_weight` back to `reported_turnover_weight`
- `constructionArtifactReplay.replay_provenance.weighting_trace_status`
  - authoritative persisted weighting-trace availability label; `available` requires a present valid persisted `weighting_trace_v1`, and `unavailable_legacy_artifact` is reserved only for the exact dual-missing legacy artifact case
- `constructionArtifactReplay.replay_provenance.weighting_trace_v1`
  - authoritative persisted weighting derivation trace echoed verbatim from the artifact when present and valid; this is hypothetical construction diagnostics only and never replay math input
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_v1.reported_turnover_weight`
  - persisted reported turnover weight from the construction artifact; it stays `null` only when `reported_value_status` says turnover was not computed
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_v1.trade_intent_context.intent_count`
  - persisted count of trade intents used as turnover-context diagnostics; it is diagnostic context only and does not imply executed trades
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_v1.constraint_context`
  - persisted turnover-cap diagnostic context already emitted by the backend: `requested` tells whether `max_turnover_weight` was requested in persisted hard constraints, `limit_weight` carries the persisted cap when requested, and `evaluation_status` records whether the cap passed, bound, failed, or was not evaluated
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_v1.feasibility_context`
  - persisted link to artifact feasibility diagnostics: `artifact_status` is the persisted construction outcome, `failure_reasons_field` identifies the persisted field carrying failure reasons, and `turnover_failure_reason_present` tells whether a turnover-specific failure reason was emitted there
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_v1.symbol_contributions[].delta_weight`
  - signed `target_weight - current_weight`; positive values are net buys/initiation, negative values are net sells/exits, and zero means hold
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_v1.symbol_contributions[].turnover_contribution_weight`
  - per-symbol contribution in weight units under the existing turnover formula `0.5 * abs(delta_weight)`; reported rows reconcile within artifact tolerance back to `reported_turnover_weight`
- `constructionArtifactReplay.replay_provenance.turnover_diagnostics_v1.symbol_contributions[].contribution_fraction_of_reported_turnover`
  - unitless share of reported aggregate turnover in `[0,1]`; unchanged names carry `0.0` when aggregate turnover is positive and `null` when aggregate turnover is zero
- `constructionArtifactReplay.truth_separation`
  - makes explicit that persisted construction artifacts are hypothetical candidate inputs, not applied truth
- artifact loading fails closed on corruption, malformed payloads, or integrity contradictions

### Optimizer preview and handoff replay

- `optimizerPreview.truth_separation`
  - makes explicit that preview output is hypothetical optimizer output only
- `optimizerPreview.persisted_handoff`
   - immutable explicit reference for downstream replay and validation when preview is feasible; `handoffReference` is the canonical desktop reopen identity object, `handoffReference.handoff_id` is its canonical identity field, and `handoffReference.artifact_id` is lineage only
- `optimizerPreview.replay_handoff`
   - downstream hypothetical replay handoff metadata; still not applied portfolio truth
- `optimizerPreview.objective` / persisted handoff `objective`
     - canonical optimizer objective metadata now persists across preview, artifact, validation, and replay; replay reads persisted objective truth rather than reconstructing client request state
- `optimizerHandoffValidation.provenance.objective`
     - canonical persisted objective metadata for validation/preflight semantics only; validation does not supply the live review/display contract
- `optimizerHandoffReplay.truth_separation`
      - explicit baseline-vs-hypothetical optimizer candidate separation
- `optimizerHandoffReplay.handoff_id`
     - echoed canonical identity field inside the persisted `handoffReference` object used for desktop reopen
- `optimizerHandoffReplay.artifact_id`
    - deprecated reopen input; still echoed for lineage and integrity cross-checks only
- `optimizerHandoffReplay.replay_provenance.return_basis_attestation`
    - persisted benchmark and factor trust evidence used for replay-output suppression policy
- `optimizerHandoffReplay.optimizer_context.objective`
     - live review/display contract for replay surfaces; desktop review reads this nested object only and does not fall back to validation provenance or scalar replay ids
- `optimizerHandoffValidation.replay_output_policy`
      - validation-time mapping of attested trust into allowed vs withheld replay output families

### Monitor definition provenance

- the shipped monitor-definition contract family is `create -> get/list -> catalog/recent -> latest-observation-alert-inbox -> alert-history-queue -> recovered-alert-review-queue -> active-alert-episode-inbox -> evaluate -> observation -> evaluation-history -> evaluation-history/{history_entry_id} -> alert-episode-history -> alert-review-timeline`
- `POST /backtests/monitor-definitions` persists canonical monitor-definition artifacts for `benchmark_trend_overlay_v1` and the distinct persisted family `data_quality_monitor_v1`; data quality is a `data_quality` monitor family, not an overlay
- monitor-definition create rules are family-specific: `benchmark_trend_overlay_v1` requires a non-null market benchmark and rejects the reserved `DATA_QUALITY` sentinel, while `data_quality_monitor_v1` accepts omitted/null `benchmark_symbol` or the exact explicit sentinel `DATA_QUALITY` only
- persisted monitor definitions are the authoritative downstream input for monitor review; clients reopen by `monitor_definition_id`, not by reconstructing thresholds locally
- `GET /backtests/monitor-definitions` returns the shipped narrow artifact inventory view with identity-only list items
- `GET /backtests/monitor-definitions/catalog` returns an additive read-only catalog discovery slice and each row carries typed provenance `persisted_monitor_definition_artifact`
- `GET /backtests/monitor-definitions/catalog` and `GET /backtests/monitor-definitions/recent` accept additive low-cardinality filters only: `overlay_family`, `monitor_family`, `monitor_id`, `review_support_status`, `lifecycle_status`, `latest_observation_status`, `latest_observation_observation_status`, `latest_observation_alert_classification`, `latest_observation_cause_code`, `latest_observation_recency`, `latest_evaluation_snapshot_status`, `latest_evaluation_snapshot_cause_code`, and `latest_evaluation_snapshot_recency`
- `GET /backtests/monitor-definitions/recent` returns an additive read-only newest-first discovery slice and each row carries typed provenance `persisted_monitor_definition_artifact` plus typed recent-order provenance `persisted_artifact_file_mtime`
- `POST /backtests/monitor-definitions/{monitor_definition_id}/evaluations` persists exactly one authoritative latest-snapshot sidecar per monitor definition at `{monitor_definition_id}.latest_evaluation.json`; this sidecar is the only shipped discovery source for latest evaluation status
- `POST /backtests/monitor-definitions/{monitor_definition_id}/evaluations` also overwrites exactly one canonical persisted observation artifact per monitor definition at `{monitor_definition_id}.observation.json`; this persisted observation is the authoritative downstream review/discovery input for latest observation state, degraded/unavailable cause code, and alert classification
- `GET /backtests/monitor-definitions/latest-observation-alert-inbox` returns newest-first latest-observation inbox rows from canonical persisted observation artifacts only; rows exclude `informational` observations, carry authoritative `monitor_definition_id` + `observation_id` open handoff fields, and never reconstruct observation state from snapshots, history, or client-side logic
- `GET /backtests/monitor-definitions/alert-history-queue` returns newest-first alert-history queue rows from canonical persisted evaluation-history entries plus the canonical latest-snapshot sidecar only; rows exclude `informational` significance states, carry authoritative `monitor_definition_id` + `history_entry_id` review handoff fields, preserve history-entry semantics rather than observation semantics, and fail closed when the latest snapshot conflicts with the latest persisted history entry for a monitor definition
- `GET /backtests/monitor-definitions/recovered-alert-review-queue` returns newest-first recovered review discovery rows from canonical persisted latest observation plus latest-snapshot plus append-only history lineage only; rows remain discovery-only, require an informational latest observation/latest snapshot/latest informational history alignment, require `latest_observation.hysteresis_transition = recover`, require at least one older alert-eligible persisted history entry for the same definition, exclude informational `no_op` lineages, carry one recovered `alert_episode` contract rooted to that same persisted definition lineage only, and reopen the existing definition-scoped alert-review timeline by authoritative `monitor_definition_id` + latest-observation `observation_id` only
- `GET /backtests/monitor-definitions/active-alert-episode-inbox` returns newest-first active alert-episode discovery rows from authoritative persisted `monitor_definition_alert_episode_record_v1` rows only; each row is rooted in one persisted open episode record, excludes recovered/closed/informational-only states, preserves explicit alert-episode lifecycle/order/provenance fields under `alert_episode`, carries explicit review-only `review_scope` and `evaluation_mode`, supports additive `before_episode_id` windowing, and only hands off to reopen the existing definition-scoped alert-review timeline by authoritative persisted ids already stored on that episode record
- `GET /backtests/monitor-definitions/{monitor_definition_id}/observation` returns exactly one canonical persisted observation artifact scoped to the persisted monitor definition and fails closed when the authoritative observation is absent or invalid
- `POST /backtests/monitor-definitions/{monitor_definition_id}/evaluations` also appends exactly one canonical persisted history entry per successful evaluation under `{monitor_definition_id}.history/*.json`; history is append-only and the latest-snapshot sidecar remains the authoritative latest-status sidecar for discovery surfaces
- `GET /backtests/monitor-definitions/{monitor_definition_id}/evaluation-history` returns newest-first persisted history entries only and its response metadata echoes authoritative monitor-definition identity, fingerprint, schema version, inspection order, returned limit, and total persisted entry count
- `GET /backtests/monitor-definitions/{monitor_definition_id}/evaluation-history/{history_entry_id}` returns exactly one persisted history entry plus inspection metadata; it does not accept alternate lookup semantics or synthesize fallback rows
- `GET /backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history` returns newest-first persisted alert-episode records only for that one persisted definition; response metadata keeps explicit `ordering = newest_first_latest_event_at_then_episode_id`, explicit `windowing = before_episode_id_exclusive`, `returned_limit`, `requested_before_episode_id`, `next_before_episode_id`, and authoritative total persisted episode count
- persisted alert-episode history rows are strict `monitor_definition_alert_episode_record_v1` records and carry only authoritative persisted episode metadata for bounded history discovery: episode identity, definition identity plus fingerprint/schema lineage, explicit `lifecycle_status` (`open`, `recovered`, `closed`), explicit `latest_for_monitor_definition`, explicit `started_at` / `ended_at` / `latest_event_at`, explicit `latest_contributing_observation`, explicit `recovery_basis` when present, explicit `terminal_history_entry_id`, and an explicit timeline handoff to reopen the shipped review timeline by authoritative ids only
- active alert-episode inbox rows stay distinct from latest-observation inbox rows, evaluation-history queue rows, recovered review rows, and alert-episode history rows: the inbox wraps one authoritative persisted open `alert_episode` row without collapsing it into observation-rooted or history-entry-rooted semantics, and desktop/open callers must treat the nested persisted episode record as the sole authoritative handoff basis
- alert-episode history stays separate from evaluation-history and alert-review timeline retrieval; it does not mutate evaluation behavior, does not widen latest lifecycle semantics, does not synthesize rows from client cache or queue ordering, and fails closed on unknown definitions, malformed persisted episode records, persisted episode-to-definition identity mismatch, unsupported lifecycle states, contradictory handoffs, or disagreement with canonical persisted evaluation lineage
- `GET /backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline` returns newest-first definition-scoped review rows from canonical persisted sources only: one latest observation artifact when present plus append-only evaluation-history entries; observation rows carry authoritative `observation_id` open handoff fields and observation-rooted semantics, history rows carry authoritative `history_entry_id` review handoff fields and history-entry-rooted semantics, response metadata may carry one authoritative `latest_alert_episode` contract for that same persisted `monitor_definition_id`, recovered-queue handoffs reopen this same review surface by authoritative persisted ids only, and the route fails closed on missing, malformed, lineage-mismatched, fingerprint-mismatched, schema-mismatched, unsupported episode state, or contradictory persisted state
- the alert-review timeline row payload is review-only and inventory-exact: `benchmark_observation`, `portfolio_observation`, and `active_observation` remain separate persisted blocks, and no analytics methodology, benchmark math, or interpretation prose is introduced into those fields
- alert episodes are definition-scoped only: one `episode_id` identifies one backend-rooted alert lineage for one persisted `monitor_definition_id`, `episode_status = active` means the latest persisted history state is still alert-eligible, and `episode_status = recovered` means the latest persisted history state and latest persisted observation are informational after at least one earlier alert-eligible persisted history entry in the same definition lineage
- alert episode boundaries derive only from persisted observation plus persisted evaluation-history outputs, never from client reconstruction, inbox ordering, or latest-snapshot-only inference; `started_at` is the first alert-eligible persisted history entry in the latest contiguous alert lineage, `ended_at` is null while active and equals the latest contributing persisted observation `evaluated_at` after recovery, `latest_contributing_observation` names the canonical persisted observation that currently closes the lineage, and `recovery_basis` names the last alert-eligible persisted history entry that the recovered observation clears
- monitor discovery/review surfaces now carry explicit precedence metadata and transition semantics from persisted backend truth: discovery `metadata.status.status_source_precedence`, latest-observation `source_precedence`, latest-snapshot `source_precedence`, recovered-queue `source_precedence`, alert-review-timeline `source_precedence`, and alert-episode `source_precedence`; desktop must preserve these authoritative fields and must not replace them with client-authored precedence inference
- hysteresis remains explicit and additive across persisted observation, latest-snapshot, history-entry, timeline-row, recovered-queue-row, and latest-alert-episode contracts: `open` means the latest state newly entered an alert-eligible lineage, `remain_open` means the latest state stays within an already alert-eligible lineage, `recover` means the latest informational state closed a prior alert-eligible lineage, and `no_op` means the latest informational state remained informational with no reopening or recovery event
- `degraded` and `unavailable` remain alert-eligible persisted states for monitor review semantics, `ok` remains informational, and ambiguous or contradictory combinations of significance/alert classification vs hysteresis vs cause code fail closed rather than being normalized client-side
- discovery `metadata.status.lifecycle` is authoritative persisted backend status metadata for review support and lifecycle and is distinct from latest evaluation outcome
- discovery `metadata.status.latest_observation_status` is explicit `present` or `absent`; if the canonical persisted observation is absent, discovery returns `absent` plus `latest_observation = null` rather than reconstructing state from latest-snapshot sidecars or history entries
- discovery latest-observation filters match only canonical persisted observation metadata: `latest_observation_status` matches explicit presence vs absence, `latest_observation_observation_status` matches persisted observation `observation_status`, `latest_observation_alert_classification` matches persisted observation `alert_classification`, `latest_observation_cause_code` matches persisted observation `cause_code`, and `latest_observation_recency` matches backend-derived recency from persisted observation `evaluated_at`
- the canonical persisted observation artifact is strict `monitor_definition_observation_artifact_v1` and carries explicit observation identity, monitor-definition identity plus fingerprint/schema lineage, evaluated timestamp, observation status, degraded/unavailable cause code, alert classification, and either separate benchmark/current-portfolio/active observation blocks for benchmark-trend inspection or an explicit `data_quality_evidence` block for data-quality inspection
- when persisted observation metadata is present, discovery returns `observation_id`, `evaluated_at`, `observation_status`, `cause_code`, `alert_classification`, and backend-derived `recency_status`; `observation_status`, `cause_code`, `alert_classification`, degradation, and provenance remain separate fields and do not imply applied portfolio state
- discovery `metadata.status.latest_evaluation_snapshot_status` is explicit `present` or `absent`; if the canonical sidecar is absent, discovery returns `absent` plus `latest_evaluation_snapshot = null` rather than inferring prior evaluations
- the persisted latest-snapshot sidecar is strict `monitor_definition_latest_evaluation_snapshot_v1` and carries only monitor-definition identity, benchmark symbol, evaluated timestamp, outcome status, degraded/unavailable cause code, significance status, explicit benchmark-observation lineage plus imported portfolio truth-basis fields for benchmark trend, or explicit data-quality evidence lineage plus `data_quality_basis` for data quality
- when persisted latest evaluation snapshot metadata is present, discovery returns `evaluated_at`, `outcome_status`, `cause_code`, `significance_status`, and backend-derived `recency_status`; `recency_status` is computed strictly from the persisted sidecar `evaluated_at`, never from sidecar file mtime, route time, lifecycle metadata, or review-support metadata; `outcome_status`, `cause_code`, and `significance_status` remain separate fields and are not overloaded into lifecycle metadata
- malformed, schema-invalid, structurally incomplete, or monitor-definition-mismatched present latest-evaluation snapshot sidecars fail closed for discovery routes; absent snapshot metadata remains a valid explicit absence state
- malformed, schema-invalid, structurally incomplete, identity-mismatched, fingerprint-mismatched, schema-version-mismatched, benchmark-mismatched, partial, unsupported, contradictory, or lineage-mismatched present observation artifacts fail closed for observation retrieval and discovery routes; discovery does not synthesize latest observation state from history or latest-evaluation snapshots when the canonical observation is absent or invalid
- malformed, schema-invalid, structurally incomplete, identity-mismatched, fingerprint-mismatched, schema-version-mismatched, or benchmark-mismatched present evaluation-history entries fail closed for history retrieval and inspection routes; history does not auto-repair malformed present payloads and does not fall back to latest-snapshot reconstruction
- monitor definition writes are strict and canonical; compatibility is load-only and limited to documented persisted omissions of `monitor_family`, `observation_statuses`, and `source_lineage_requirements` on legacy benchmark-trend artifacts
- load-boundary compatibility does not hydrate missing `cause_code`; legacy persisted observation, latest-snapshot, and history artifacts that predate `cause_code` fail closed when present on read surfaces
- monitor definition load integrity validates raw persisted `fingerprint` and `monitor_definition_id` against stored payload content before any legacy hydration runs
- present-but-noncanonical or partially conflicting legacy-shaped values are rejected; load does not auto-repair malformed, ambiguous, or mismatched persisted fields
- `POST /backtests/monitor-definitions/{monitor_definition_id}/evaluations` is evaluation-only with respect to portfolio truth and review history; it persists the canonical observation artifact plus the canonical latest-snapshot sidecar plus one append-only history entry, and it does not infer benchmark observations or fabricate missing data-quality evidence
- list, catalog, recent, retrieval, and evaluation accept only the documented legacy omissions and otherwise fail closed on missing persisted artifacts, malformed JSON, non-object or schema-invalid payloads, non-canonical artifact identity, contradictory benchmark lineage states, blank benchmark symbols, missing required imported-portfolio statement lineage, missing required degraded/unavailable `cause_code`, unknown `cause_code` enum values, and cause-code mismatches across canonical observation, latest snapshot, and history artifacts
- monitor evaluation surfaces `benchmark_observation`, `portfolio_observation`, and `active_observation` separately so benchmark truth, current portfolio truth, and threshold application do not collapse into one field bundle

### Monitor observation statuses

- `ok`
  - current portfolio truth is consistent with the persisted monitor thresholds for the supplied benchmark overlay observation
- `threshold_breach`
  - current portfolio truth is available and benchmark observation is valid, but one or more canonical thresholds are breached
- `degraded`
  - evaluation remained read-only but benchmark observation is not fully actionable, such as `unconfirmed`
- `unavailable`
  - required benchmark observation or current portfolio truth basis is unavailable, so threshold evaluation does not run

### Monitor cause codes

- canonical serialized observation, latest-snapshot, and history payloads always carry `cause_code`
- canonical mapping is authoritative on the backend: evaluation conditions -> `observation_status` -> `cause_code` -> `alert_classification` / `significance_status`
- `ok` and `threshold_breach` use explicit `null` for `cause_code`
- `benchmark observation status = unconfirmed` -> `degraded` -> `benchmark_observation_unconfirmed` -> `degraded`
- `benchmark observation status = unavailable` -> `unavailable` -> `benchmark_observation_unavailable` -> `unavailable`
- `current portfolio total_portfolio_value <= 0` -> `unavailable` -> `portfolio_truth_non_positive_total_value` -> `unavailable`
- `degraded` and `unavailable` require the mapped canonical non-null `cause_code` across observation, latest snapshot, and history entry payloads

### Data quality monitor family

- `data_quality_monitor_v1` is persisted as `monitor_family = data_quality`; it is not an overlay and does not use benchmark-trend threshold-breach semantics.
- `DATA_QUALITY` is the canonical sentinel reliability label for `data_quality_monitor_v1`; it is not a market benchmark, must not be interpreted as a tradable symbol, is rejected for `benchmark_trend_overlay_v1`, and alternate explicit data-quality values such as `SPY`, lowercase, whitespace-padded, or blank labels are invalid on create.
- Data-quality definitions use canonical observation statuses `ok`, `degraded`, and `unavailable` only; `threshold_breach` and `action_required` are invalid for this family.
- Data-quality policy fields are `minimum_coverage_ratio`, `max_stale_age_days`, `required_trust_floor`, and `provenance_requirements`; source-lineage requirements use `evidence_source_kind = market_data_reliability_evidence`, `portfolio_truth_basis = imported_portfolio_snapshot`, and explicit required evidence fields.
- Data-quality persisted observations and history entries carry `data_quality_evidence` with coverage counts, coverage ratio, trust statuses, stale/missing symbols, withheld/unavailable inputs, and source lineage; they do not carry benchmark/current-portfolio/active threshold observation blocks.
- Canonical data-quality cause mapping is review-only: missing source lineage -> `unavailable/provenance_incomplete`, unavailable inputs -> `unavailable/input_unavailable`, all covered market data unavailable -> `unavailable/market_data_unavailable`, withheld inputs -> `degraded/input_withheld`, insufficient coverage -> `degraded/market_data_coverage_degraded`, stale symbols -> `degraded/market_data_freshness_degraded`, otherwise `ok/null`.

### Replay summary metrics

For replay responses, these rules apply:
- total return, annualized return, drawdown, Sharpe, Sortino, and benchmark-relative investor-economics rows must render as suppressed when the contract says `withheld`
- benchmark-relative metrics and diffs may also be suppressed by attested replay-output policy even when replay itself succeeded
- turnover, cost, holdings, weights, rebalance events, and trade logs remain replay-derived implementation outputs rather than investor-economics unlock signals

### Diagnostics comparison

- diagnostics comparison remains `candidate - baseline`
- top callouts are backend-selected and carry stable `selection_rule` and `rationale` fields
- desktop must render backend callouts directly and must not infer salience from array order
- withheld families must not be backfilled through diagnostics comparison rows or callouts

## Current Accuracy Rules

1. Replay outputs are hypothetical and must not be presented as imported broker-truth performance.
2. Backtest diagnostics are synthetic replay diagnostics with explicit provenance.
3. Comparison deltas are always `candidate - baseline`.
4. If aligned replay windows do not share enough common dates, the route must fail explicitly.
5. Replacement-intent replay, construction-artifact replay, and optimizer-handoff replay all require backend-owned candidate weights and explicit provenance.
6. Persisted artifact lineage must be echoed, not reconstructed heuristically in the UI.
7. `withheld` is distinct from `unavailable`; when investor-economics output is withheld, comparative views from that basis must stay suppressed or `null`.
8. Persisted construction and optimizer review restore is artifact-backed only: canonical `review_basis` or typed handoff identity is authoritative after persistence, and missing or ambiguous persisted review-basis state fails closed.

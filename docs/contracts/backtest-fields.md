# Backtest Field Inventory

This document inventories financially meaningful fields shown in the desktop portfolio-allocation workflow and the adjacent backend replay-preview contracts that feed it today.

For shipped workflow boundaries, use `docs/product/current-product-state.md`.

## Purpose

For each visible backtest value, we want a traceable chain:
- UI field
- app state source
- engine source
- replay or market-data source
- truth class and trust semantics

## Current Root Sources

The portfolio-allocation workflow currently renders from these root inputs:

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

Important rules:
- imported holdings may seed workflows, but replay outputs remain hypothetical and must never be confused with imported broker-truth history
- replacement-intent, construction-artifact, and optimizer-handoff replay weights are backend-owned; desktop must not synthesize candidate weights locally for those workflows
- backtest diagnostics are synthetic replay diagnostics with explicit provenance, not imported portfolio diagnostics
- persisted construction artifacts and optimizer handoffs are lineage-bearing hypothetical artifacts, not applied portfolio truth

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
- the preview route may accept the legacy request shape for compatibility, but handoff-shaped payloads must be complete, supported handoffs and mixed handoff-plus-legacy payloads are rejected
- handoff consumption fails closed on missing or unsupported `handoff_kind` and on persisted artifact integrity mismatches, including construction artifact id mismatch
- `POST /backtests/portfolio-allocation/construction-artifact-preview` echoes lineage from the persisted construction artifact
- `replay_provenance.selection_rule_trace` must be echoed from persisted artifact provenance only
- the trace is descriptive provenance and must not drive replay math
- legacy empty traces normalize only at artifact-load time; replay does not invent trace content later

### Optimizer handoff provenance

- `POST /optimizer/preview` can persist an immutable handoff reference for feasible hypothetical previews
- the persisted optimizer handoff reopen identity is `handoffReference`; `handoffReference.handoff_id` remains the canonical identity and `handoffReference.artifact_id` remains lineage and integrity metadata only
- `POST /backtests/portfolio-allocation/optimizer-handoff-preview` consumes that explicit persisted reference only
- `POST /backtests/portfolio-allocation/optimizer-handoff/constraints` remains validation/preflight only; it does not open replay by itself
- desktop persisted review writes persist `handoffReference` as the only reopen identity object, and any repair of older cache rows is load-only
- optimizer handoff replay carries persisted `return_basis_attestation` and `replay_output_policy`
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
- `hypotheticalReplayResult.replay_provenance`
  - authoritative lineage block for direct preview vs constructed-candidate replay, upstream lineage, ranking seed lineage, and echoed validation lineage
- `hypotheticalReplayResult.baseline_weights` / `candidate_weights`
  - backend-derived replay inputs; desktop must not construct these locally
- replay rejects provable lineage mismatches between `constraint_validation` and `constructed_candidate`
- validation lineage is descriptive; replay does not currently require approval status to run

### Construction artifact replay

- `constructionArtifactReplay.replay_provenance.selection_rule_trace`
  - authoritative persisted selection trace for the artifact replayed
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

# Core Portfolio Diagnostics Implementation Plan

This plan turns the `Core Portfolio Diagnostics` research direction into an implementation sequence adapted to the current repository.

## Goal

Strengthen the project's core portfolio diagnostics so they become a stable foundation for:
- current portfolio review
- candidate-vs-current comparison
- portfolio construction constraints
- allocation replay improvement analysis

The feature should remain:
- deterministic
- financially explicit
- truth-class aware
- thin on UI finance logic

Current shipped-state anchor:
- use `docs/product/current-product-state.md` as the canonical source for current desktop workflow ownership, shipped panel structure, and local artifact behavior
- this document should stay focused on diagnostics implementation planning rather than restating the whole app workflow

## Current Baseline

Already in place:
- current-state look-through and benchmark overlap in `services/quant-engine/app/services/exposure_engine.py`
- history-aware risk, factor, volatility, and decomposition analytics in `services/quant-engine/app/services/diagnostics_engine.py`
- daily-state and historical path support in `services/quant-engine/app/services/dashboard_history_engine.py`
- explicit unavailable handling for missing history context
- methodology documentation in `docs/finance/financial-methodology.md`
- contract docs in `docs/contracts/exposure-fields.md`, `docs/contracts/dashboard-fields.md`, and `docs/contracts/backtest-fields.md`

Current desktop consumption context that matters for this plan:
- current-state diagnostics are primarily consumed in the `Diagnostics` tab for current portfolio review
- replay-derived diagnostics deltas are consumed in `Workspace`, inside the portfolio-improvement workflow shell and adjacent replay review surfaces
- Monitoring is also currently a `Workspace` surface, but it is replay-scoped and review-oriented rather than a broad current-state monitoring system
- docs should not describe diagnostics ownership as one monolithic panel anymore; current-state diagnostics and replay-diagnostics review now have different panel ownership in the desktop app

Main gap:
- diagnostics are functionally present, but not yet organized as one explicit "core portfolio diagnostics" layer with a tighter contract, provenance, and implementation roadmap for reuse by future ranking / construction / replay features

## Target Scope

The core diagnostics program should cover these six areas while preserving the current engine boundaries:
1. factor exposure
2. benchmark overlap
3. drawdown
4. volatility
5. concentration
6. risk decomposition

## Engine Boundary Plan

### Exposure engine

Keep in `services/quant-engine/app/services/exposure_engine.py`:
- current-state look-through
- benchmark overlap
- name / sector concentration that depends only on current holdings

Recommended additions:
- explicit concentration block for current-state diagnostics
- section-level availability/confidence for overlap + concentration

### Diagnostics engine

Keep in `services/quant-engine/app/services/diagnostics_engine.py`:
- historical drawdown
- realized volatility and regime
- beta / correlation / tracking error / relative risk
- rolling factor loadings
- factor-risk decomposition
- factor/systematic vs specific risk summary

Recommended additions:
- explicit diagnostics provenance/truth-class block
- dedicated summary sections for drawdown, volatility, and history-derived risk concentration outputs reused by future construction/replay reviews

### Dashboard history engine

Keep in `services/quant-engine/app/services/dashboard_history_engine.py`:
- canonical daily states
- performance series
- historical path and range metrics

Recommended role:
- remain the canonical source for daily-state-based drawdown and performance-path inputs
- do not absorb concentration or overlap logic

## Schema Plan

### Phase 1: add explicit diagnostics provenance

Extend `services/quant-engine/app/schemas/diagnostics.py` with a small provenance model aligned with the existing provenance style already used by backtest diagnostics in `services/quant-engine/app/schemas/backtest_engine.py`, for example:
- `truth_class`
  - `broker_truth_historical`
  - `synthetic_snapshot_history`
  - `snapshot_only_unavailable`
- `history_basis`
- `market_data_basis`
- `note`

Purpose:
- let desktop and future replay/construction features distinguish broker-truth diagnostics from synthetic diagnostics without guessing
- separate provenance from availability, since `historical_sections_available` only says whether diagnostics were computed, not whether they are broker-truth historical results

### Phase 2: add focused diagnostics summary sections

Add summary blocks in the diagnostics contract only for fields whose basis is explicit and history-derived:
- `drawdown_summary`
  - current drawdown
  - max drawdown
  - optional drawdown start/end if already available
- `volatility_summary`
  - realized volatility
  - downside volatility
  - tracking error
- `risk_concentration_summary`
  - top factor risk share
  - top position risk share
  - factor HHI / position HHI if these remain risk-derived

Purpose:
- prevent future ranking/construction/replay features from scraping these values out of deeper nested payloads
- avoid mixing current-state holdings concentration with history-derived risk concentration in one undifferentiated summary object

### Phase 3: add concentration to the exposure-side contract

Extend `services/quant-engine/app/schemas/exposure.py` with a current-state concentration block sourced only from snapshot holdings, for example:
- top name weights
- HHI
- effective holdings
- top sector weights

Purpose:
- separate current-state concentration truth from historical diagnostics concentration

## Implementation Sequence

### Slice 1: diagnostics provenance

Files:
- `services/quant-engine/app/schemas/diagnostics.py`
- `services/quant-engine/app/services/diagnostics_engine.py`
- `docs/finance/financial-methodology.md`
- possibly a new `docs/contracts/diagnostics-fields.md`

Work:
- add provenance model
- populate it in imported-history, synthetic snapshot-history, and unavailable diagnostics paths
- expose explicit truth class in the response

Why first:
- smallest, highest-value contract improvement
- immediately useful for future replay and construction features
- low UI risk because it adds fields rather than changing current sections
- it fixes the repo's highest-risk correctness issue: synthetic snapshot-history and broker-truth history are currently indistinguishable in the diagnostics contract

### Slice 2: current-state concentration block in exposure

Files:
- `services/quant-engine/app/schemas/exposure.py`
- `services/quant-engine/app/services/exposure_engine.py`
- `services/quant-engine/app/analytics/risk.py` if helper extraction is needed
- `docs/contracts/exposure-fields.md`

Work:
- add name/sector concentration summary derived from snapshot holdings
- keep this explicitly current-state
- document difference between current-state concentration and historical risk concentration

Why second:
- construction rules need concentration constraints early
- current-state concentration should not depend on historical diagnostics availability

### Slice 3: desktop contract surfacing

Files:
- `apps/desktop/src/features/portfolio/types.ts`
- `apps/desktop/src/features/portfolio/portfolioAnalysisAdapter.ts`
- `apps/desktop/src/features/portfolio/ExposurePanel.tsx`
- `apps/desktop/src/features/portfolio/DiagnosticsPanel.tsx`

Work:
- surface provenance and summary fields in the desktop contract
- render truth-class / degraded-state badges from backend outputs
- avoid any local recomputation of diagnostic summaries

Why third:
- only after backend fields are stable

## Desktop workflow accuracy guardrails

- keep current-state diagnostics docs aligned with `Diagnostics` tab ownership, not `Research`
- keep replay diagnostics delta docs aligned with `Workspace` workflow ownership, not the current-state diagnostics tab
- keep current Monitoring references narrow and honest: it is a replay-scoped Workspace review surface with explicit handoff into workflow sections, not a general alerting layer
- when documenting diagnostics reuse for construction/replay flows, be explicit that draft-scoped review artifacts do not mutate `PortfolioSnapshot`

## Testing Plan

### Backend

Add or extend tests for:
- provenance fields on historical diagnostics vs unavailable diagnostics
- summary-field reconciliation with existing deeper payload fields
- missing history context -> unavailable truth class
- synthetic snapshot-history path for variant/draft style inputs
- missing benchmark holdings -> overlap remains unavailable / null

Likely files:
- `services/quant-engine/app/tests/test_analytics.py`
- `services/quant-engine/app/tests/test_routes.py`
- `services/quant-engine/app/tests/test_mocked_flows.py`

### Desktop

Add or extend tests for:
- truth-class rendering and degraded-state labels
- summary cards reading engine outputs directly
- no leakage of broker-truth diagnostics into variants/drafts
- current-state diagnostics remaining owned by current-state desktop surfaces while replay-diagnostics review remains owned by `Workspace`

Likely files:
- `apps/desktop/src/features/portfolio/ExposurePanel.test.tsx`
- `apps/desktop/src/features/portfolio/DiagnosticsPanel.test.tsx`
- `apps/desktop/src/app/App.test.tsx`

## Documentation Plan

Update together whenever formulas or visible fields change:
- `docs/finance/financial-methodology.md`
- `docs/contracts/exposure-fields.md`
- `docs/contracts/dashboard-fields.md`
- add `docs/contracts/diagnostics-fields.md` once diagnostics summary/provenance becomes a first-class visible contract
- `docs/product/current-product-state.md` when a diagnostics surface changes current panel ownership or workflow role in the shipped desktop app

## Recommended First Build Slice

Build first:
- diagnostics provenance

Reason:
- it gives immediate reuse value to future features
- it does not require changing the exposure engine first
- it tightens the truth-class contract exactly where future ranking/construction/replay work will depend on it

## Definition Of Done For This Planning Thread

The core portfolio diagnostics layer is ready for downstream quant features when:
- current-state overlap and concentration are explicit and documented
- historical diagnostics carry explicit provenance/truth class
- summary fields needed by future construction/replay flows exist in backend contracts
- desktop renders status from engine outputs instead of inferring it locally

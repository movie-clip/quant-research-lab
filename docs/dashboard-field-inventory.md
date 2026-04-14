# Dashboard Field Inventory

This document inventories every financially meaningful field shown in the desktop Dashboard and traces where it comes from today.

It is the working contract for Dashboard accuracy work.

## Purpose

For each visible Dashboard value, we want a traceable chain:

- UI field
- UI/provider function
- App state source
- engine or adapter source
- snapshot or imported statement source
- truth class: broker-truth, engine-derived, draft-derived, or unavailable

## Current Root Sources

Dashboard currently renders from two root inputs:

1. `result: DashboardAnalysis`
   - produced in `apps/desktop/src/app/App.tsx`
   - cards, performance chart, drawdown, MWR, monthly returns, and imported metadata are sourced from this path
   - for imported nodes, history may come from `runImportedDashboardHistory(...)`
   - for snapshot-only or variant paths, history may come from `runDashboardHistoryEngine(...)` or degrade to unavailable

2. `draftSnapshot: PortfolioSnapshot | null`
   - sourced from the active working draft or opened node snapshot in `apps/desktop/src/app/App.tsx`
   - Allocation Overview, sector pie, sector drilldown, draft capital check, and editable holdings come from this path

Important rule:

- imported direct-source history is allowed for imported nodes
- changed variants or snapshot-only paths must be correct or unavailable
- Dashboard must not inherit imported broker-truth history for a changed snapshot if that would make numbers look plausible but wrong

## Truth Classes

- `broker-truth`
  - directly tied to imported statement facts or imported-history replay from the imported snapshot
- `engine-derived`
  - derived from engine output, but not a raw statement field
- `draft-derived`
  - derived from the editable local draft snapshot, not broker-truth history
- `unavailable-required`
  - must show `n/a`, hidden state, or an unavailable panel when the required history/source is missing or unreliable

## Field Inventory

### Header and account metadata

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Broker badge | `formatBrokerLabel(result.snapshot.statement.importer)` in `apps/desktop/src/features/portfolio/DashboardPanel.tsx` | `analysis.snapshot.statement.importer` | `broker-truth` | if importer missing, current code still falls back to Interactive Brokers label logic; should eventually render explicit unknown | covered by IB2026 golden tests |
| Dashboard source badge | `dashboardSourceLabel(result.source_status?.performance_history)` | `analysis.source_status.performance_history` | `engine-derived` | if missing, badge may be absent | covered by IB2026 golden tests |
| Loaded file(s) | `formatLoadedStatements(result, lastImportedFileNames)` | `analysis.snapshot.statements` first, fallback `lastImportedFileNames` | `broker-truth` | if no statements and no fallback files, omit | covered by IB2026 golden tests |
| Restored on launch | `restoredSession` | App local state | not financial | n/a | session/UI state only |
| Account id | `result.snapshot.statement.account_id` | `analysis.snapshot.statement.account_id` | `broker-truth` | if null, UI shows `Unknown` | covered by IB2026 golden tests |
| Statement period | `result.snapshot.statement.statement_period` | `analysis.snapshot.statement.statement_period` | `broker-truth` | if null, UI shows `Statement period unavailable` | covered by IB2026 golden tests |
| Combined statement count | `result.snapshot.statements.length` | `analysis.snapshot.statements` | `broker-truth` | if one statement, suffix hidden | imported multi-statement metadata |

### Summary cards

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Portfolio Value | `resolveDisplayedPortfolioValue(result, visibleSummary.endValue, latestPerf?.portfolio_value)` | `analysis.snapshot.statement_totals.ending_nav`, `analysis.daily_states`, `analysis.performance_series` | `broker-truth` for imported snapshots when statement ending NAV exists, otherwise `engine-derived` | if no history and no statement ending NAV, render `n/a` | covered by IB2026 golden tests and ending-NAV override regression |
| Start value | `visibleSummary.startValue` from `computeVisibleSummary(...)` | filtered `analysis.daily_states` + `analysis.performance_series` for selected range | `engine-derived` | if no visible states, render `n/a` | covered by IB2026 golden tests; this is the visible-range anchor, not always statement starting NAV |
| Time-Weighted Return | `visibleSummary.timeWeightedReturnPct` | filtered `analysis.performance_series` | `engine-derived` | if no anchored performance points, render `n/a` | covered by IB2026 golden tests |
| Net Contributions | `visibleSummary.netContributions` | filtered `analysis.daily_states` | `engine-derived` | if no states, current code falls back to `0`; should stay traceable to visible states | covered by IB2026 golden tests |

### Performance section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Performance title | selected by `performanceView` | local UI state + available performance path | not financial | n/a | presentational |
| Monthly-return status | `dashboardSourceLabel(result.source_status?.monthly_returns)` | `analysis.source_status.monthly_returns` | `engine-derived` | hide label if status missing | covered by IB2026 golden tests |
| TWR chart path | `normalizedPerf` / `performancePathData` | `analysis.performance_series` | `engine-derived` | if no visible performance path, show empty state panel | current display transform from engine points |
| Benchmark chart path | `normalizedPerf` / `performancePathData` | `analysis.performance_series` | `engine-derived` | if no visible performance path, show empty state panel | benchmark is currently SPY for imported dashboard history |
| MWR chart path | `capitalChartData` and visible states used when `performanceView === 'mwr'` | `analysis.daily_states` | `engine-derived` | if no visible states, show empty state panel | portfolio growth path for selected range |
| Capital Path chart | `capitalChartData` | `analysis.daily_states` | `engine-derived` | if no visible states, show empty state panel | contribution base vs portfolio value |
| Empty-state message | `!hasPerformance` | absence of `analysis.performance_series` or `analysis.daily_states` | `unavailable-required` | must show empty/unavailable rather than fake chart | current behavior is correct direction |

### Allocation Overview and editable draft section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Sector allocation pie | `buildSectorAllocationFromSnapshot(nextDraftSnapshot)` | `draftSnapshot` and local `sectorDraft` edits | `draft-derived` | if no positions, show empty state | visible, but IB2026 tests currently assert labels/state rather than SVG geometry |
| Sector allocation percentages | `sectorAllocation[].weight` | `draftSnapshot` and `sectorDraft` | `draft-derived` | if no positions, omit/list empty | covered by IB2026 golden tests for key sector labels |
| Sector drilldown holdings | `selectedSectorPositions` | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if no sector selected or no positions, show empty state | covered by IB2026 golden tests for Technology drilldown |
| Holding market values | `position.market_value` in draft rows | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if missing, should remain explicit editable value | editable draft only |
| Holding weights inside selected sector | `(position.market_value / editedNetCapital) * 100` | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if edited capital is zero, current code shows `0.00%` | covered by IB2026 golden tests for Technology holdings |
| Draft Capital Check | `remainingCapital` | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if no draft snapshot, currently derives from zero | covered by IB2026 golden tests |
| Leverage ratio | `leverageRatio` | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if base capital is zero, current code shows `0.00x` | covered by IB2026 golden tests via Draft Capital Check helper |
| Locked-on sector helper | `lockedSector` | local UI state | not financial | n/a | covered by IB2026 interaction tests |

### Lower summary cards

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Drawdown | `maxDrawdown` from local calculation over visible `perf` | filtered `analysis.performance_series` | `engine-derived` | if no visible perf, should render `n/a` instead of a misleading `0.00%` | covered by IB2026 golden tests; current imported path now prefers backend `range_metrics` |
| Money-Weighted Return | `visibleSummary.moneyWeightedReturnPct` from `computeVisibleSummary(...)` | filtered `analysis.daily_states` | `engine-derived` | if denominator is zero or history missing, render `n/a` | covered by IB2026 golden tests; current imported path now prefers backend `range_metrics` |

### Monthly Returns section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Monthly return month labels | `computeContributionAdjustedMonthlyReturns(visibleStates)` | filtered `analysis.daily_states` | `engine-derived` | hide whole grid when unreliable | covered by IB2026 golden tests |
| Monthly return percentages | `item.returnPct.toFixed(2)` | filtered `analysis.daily_states` | `engine-derived` | hide whole grid when `monthlyReturnsAreReliable(...)` is false | covered by IB2026 golden tests |
| Monthly returns hidden-state panel | `!monthlyReturnsReliable` | filtered `analysis.daily_states` + local reliability rule | `unavailable-required` | must hide unstable monthly cards rather than show plausible garbage | covered by unstable-history regression tests |

## Current Provider Chain By Section

### Imported metadata and statement facts

- UI: `DashboardPanel.tsx`
- App state: `analysis.snapshot`
- Adapter: `buildImportedDashboardView(...)` or `composeDashboardAnalysisWithHistory(...)`
- Engine source:
  - imported nodes: import bootstrap snapshot plus `runImportedDashboardHistory(...)`
  - snapshot-only nodes: `runDashboardHistoryEngine(...)` when supported
- origin truth: imported statement snapshot, ultimately from broker statement parsing

### Performance cards and chart values

- UI: `computeVisibleSummary(...)`, `normalizePerformanceSeries(...)`, local drawdown/monthly-return helpers in `DashboardPanel.tsx`
- App state: `analysis.daily_states`, `analysis.performance_series`, `analysis.source_status`
- Adapter: `composeDashboardAnalysisWithHistory(...)`
- Engine source:
  - imported nodes: `runImportedDashboardHistory(...)`
  - snapshot-only nodes: `runDashboardHistoryEngine(...)` or unavailable
- origin truth:
  - imported path: broker-truth replay plus engine-derived path math
  - snapshot path: currently limited; must be unavailable when not trustworthy

### Allocation Overview and draft editing

- UI: `buildSectorAllocationFromSnapshot(...)`, `buildEditableSectorDraftFromSnapshot(...)`, `buildSnapshotFromSectorDraft(...)`
- App state: `draftSnapshot`, `sectorDraft`
- Adapter: local snapshot builder only
- Engine source: none at render time; this is local draft state
- origin truth: persisted `PortfolioSnapshot`, optionally modified in memory by the user before saving

## Current Accuracy Rules

1. Imported nodes may render broker-truth history.
2. Variants and snapshot-only paths must be correct or unavailable.
3. Allocation Overview is a draft editor and should be treated as draft-derived, not historical truth.
4. If cards/chart/history come from one snapshot and allocation comes from another snapshot, Dashboard is internally inconsistent and that is a bug.
5. If a history-based field cannot be supported faithfully, the UI must render `n/a`, hide the unstable cards, or show an unavailable panel.

## Immediate Follow-up Targets

1. Add explicit test coverage for the remaining gaps, especially statement-period/account fallbacks, empty draft states, and sector-pie empty states.
2. Decide which current UI derivations should move into backend/dashboard contracts:
   - start value
   - MWR
   - drawdown
   - monthly returns
3. Tighten the remaining unavailable behavior so missing history never falls back to misleading zero-like values.

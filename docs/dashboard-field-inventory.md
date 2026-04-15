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

Broker-truth fixtures in active use today:

- `docs/IB2026.pdf` is the canonical Interactive Brokers fixture for Dashboard golden-value coverage
- `docs/FF2026.pdf` is the active Freedom24 fixture for 2026 YTD validation, mixed-broker coverage, and desktop golden-value coverage
- generated desktop fixtures now live in `apps/desktop/src/test/dashboardGoldens.ts`, with broker-specific re-export shims at `apps/desktop/src/test/ib2026DashboardGolden.ts` and `apps/desktop/src/test/ff2026DashboardGolden.ts`

Important rule:

- imported direct-source history is allowed for imported nodes
- changed variants or snapshot-only paths must be correct or unavailable
- Dashboard must not inherit imported broker-truth history for a changed snapshot if that would make numbers look plausible but wrong
- imported engine routes must also degrade to unavailable when broker-truth replay cannot be supported by benchmark history or usable symbol price history

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
| Broker badge | `formatBrokerLabel(result.snapshot.statement.importer)` in `apps/desktop/src/features/portfolio/DashboardPanel.tsx` | `analysis.snapshot.statement.importer` | `broker-truth` | if importer missing, current code still falls back to Interactive Brokers label logic; should eventually render explicit unknown | covered by IB2026 and FF2026 golden tests |
| Dashboard source badge | `dashboardSourceLabel(result.source_status?.performance_history)` | `analysis.source_status.performance_history` | `engine-derived` | if missing, badge may be absent | covered by IB2026 and FF2026 golden tests |
| Loaded file(s) | `formatLoadedStatements(result, lastImportedFileNames)` | `analysis.snapshot.statements` first, fallback `lastImportedFileNames` | `broker-truth` | if no statements and no fallback files, omit | covered by IB2026 and FF2026 golden tests |
| Restored on launch | `restoredSession` | App local state | not financial | n/a | session/UI state only |
| Account id | `result.snapshot.statement.account_id` | `analysis.snapshot.statement.account_id` | `broker-truth` | if null, UI shows `Unknown` | covered by IB2026 and FF2026 golden tests |
| Statement period | `result.snapshot.statement.statement_period` | `analysis.snapshot.statement.statement_period` | `broker-truth` | if null, UI shows `Statement period unavailable` | covered by IB2026 and FF2026 golden tests |
| Combined statement count | `result.snapshot.statements.length` | `analysis.snapshot.statements` | `broker-truth` | if one statement, suffix hidden | imported multi-statement metadata |

### Summary cards

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Portfolio Value | `resolveDisplayedPortfolioValue(result, selectedRangeMetrics.summary.end_value, latestPerf?.portfolio_value)` | `analysis.snapshot.statement_totals.ending_nav`, `analysis.range_metrics`, `analysis.daily_states`, `analysis.performance_series` | `broker-truth` for imported snapshots when statement ending NAV exists, otherwise `engine-derived` | if no history and no statement ending NAV, render `n/a` | covered by IB2026 and FF2026 golden tests plus ending-NAV override regression |
| Start value | `selectedRangeMetrics.summary.start_value` | `analysis.range_metrics[selectedRange].summary.start_value` | `engine-derived` | if backend range metrics are unavailable, render `n/a` | covered by IB2026 and FF2026 golden tests; this is the visible-range anchor, not always statement starting NAV |
| Time-Weighted Return | `selectedRangeMetrics.summary.time_weighted_return_pct` | `analysis.range_metrics[selectedRange].summary.time_weighted_return_pct` | `engine-derived` | if backend range metrics are unavailable, render `n/a` | covered by IB2026 and FF2026 golden tests |
| Net Contributions | `selectedRangeMetrics.summary.net_contributions` | `analysis.range_metrics[selectedRange].summary.net_contributions` | `engine-derived` | if backend range metrics are unavailable, render `n/a` | covered by IB2026 and FF2026 golden tests |

### Performance section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Performance title | selected by `performanceView` | local UI state + available performance path | not financial | n/a | presentational |
| Monthly-return status | `dashboardSourceLabel(result.source_status?.monthly_returns)` | `analysis.source_status.monthly_returns` | `engine-derived` | hide label if status missing | covered by IB2026 and FF2026 golden tests |
| TWR chart path | `normalizedPerf` / `performancePathData` | `analysis.performance_series` | `engine-derived` | if no visible performance path, show empty state panel | current display transform from engine points |
| Benchmark chart path | `normalizedPerf` / `performancePathData` | `analysis.performance_series` | `engine-derived` | if no visible performance path, show empty state panel | benchmark is currently SPY for imported dashboard history |
| MWR chart path | `capitalChartData` and visible states used when `performanceView === 'mwr'` | `analysis.daily_states` | `engine-derived` | if no visible states, show empty state panel | portfolio growth path for selected range |
| Capital Path chart | `capitalChartData` | `analysis.daily_states` | `engine-derived` | if no visible states, show empty state panel | contribution base vs portfolio value |
| Empty-state message | `!hasPerformance` | absence of `analysis.performance_series` or `analysis.daily_states` | `unavailable-required` | must show empty/unavailable rather than fake chart | current behavior is correct direction |

### Allocation Overview and editable draft section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Sector allocation pie | `buildSectorAllocationFromSnapshot(nextDraftSnapshot)` | `draftSnapshot` and local `sectorDraft` edits | `draft-derived` | if no positions, show empty state | visible, but IB2026 tests currently assert labels/state rather than SVG geometry |
| Sector allocation percentages | `sectorAllocation[].weight` | `draftSnapshot` and `sectorDraft` | `draft-derived` | if no positions, omit/list empty | covered by IB2026 and FF2026 golden tests for key sector labels |
| Sector drilldown holdings | `selectedSectorPositions` | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if no sector selected or no positions, show empty state | covered by IB2026 and FF2026 golden tests for broker-specific drilldowns |
| Holding market values | `position.market_value` in draft rows | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if missing, should remain explicit editable value | editable draft only |
| Holding weights inside selected sector | `(position.market_value / editedNetCapital) * 100` | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if edited capital is zero, current code shows `0.00%` | covered by IB2026 and FF2026 golden tests for broker-specific holdings |
| Draft Capital Check | `remainingCapital` | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if no draft snapshot, currently derives from zero | covered by IB2026 and FF2026 golden tests |
| Leverage ratio | `leverageRatio` | `draftSnapshot` and local `sectorDraft` | `draft-derived` | if base capital is zero, current code shows `0.00x` | covered by IB2026 golden tests via Draft Capital Check helper |
| Locked-on sector helper | `lockedSector` | local UI state | not financial | n/a | covered by IB2026 interaction tests |

### Lower summary cards

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Drawdown | `selectedRangeMetrics.max_drawdown_pct` | `analysis.range_metrics[selectedRange].max_drawdown_pct` | `engine-derived` | if backend range metrics are unavailable, render `n/a` | covered by IB2026 and FF2026 golden tests |
| Money-Weighted Return | `selectedRangeMetrics.summary.money_weighted_return_pct` | `analysis.range_metrics[selectedRange].summary.money_weighted_return_pct` | `engine-derived` | if backend range metrics are unavailable, render `n/a` | covered by IB2026 and FF2026 golden tests |

### Monthly Returns section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Monthly return month labels | `selectedRangeMetrics.monthly_returns[].month` | `analysis.range_metrics[selectedRange].monthly_returns` | `engine-derived` | hide whole grid when backend range metrics are absent or marked unreliable | covered by IB2026 and FF2026 golden tests |
| Monthly return percentages | `item.returnPct.toFixed(2)` from `selectedRangeMetrics.monthly_returns` | `analysis.range_metrics[selectedRange].monthly_returns` | `engine-derived` | hide whole grid when backend range metrics are absent or marked unreliable | covered by IB2026 and FF2026 golden tests |
| Monthly returns hidden-state panel | `!selectedRangeMetrics.monthly_returns_reliable` | `analysis.range_metrics[selectedRange].monthly_returns_reliable` | `unavailable-required` | must hide unstable monthly cards rather than show plausible garbage | covered by unstable-history regression tests |

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

- UI: `normalizePerformanceSeries(...)`, `resolveDisplayedPortfolioValue(...)`, and backend-driven `range_metrics` selection in `DashboardPanel.tsx`
- App state: `analysis.range_metrics`, `analysis.daily_states`, `analysis.performance_series`, `analysis.source_status`
- Adapter: `composeDashboardAnalysisWithHistory(...)`
- Engine source:
  - imported nodes: `runImportedDashboardHistory(...)`
  - snapshot-only nodes: `runDashboardHistoryEngine(...)` or unavailable
- origin truth:
  - imported path: broker-truth replay plus engine-derived path math
  - imported path becomes `unavailable` if benchmark history or usable symbol price history is missing
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
6. Imported history replay is only trustworthy when the broker snapshot and required market-data support are both present; otherwise the result must degrade to `unavailable`.

## Immediate Follow-up Targets

1. Keep App-level regressions in place for imported base/imported child snapshot/child variant transitions so broker-truth history is only shown on direct imported nodes.
2. Add any remaining visual-state coverage gaps that are still untested, such as sector-pie empty-state presentation details rather than just labels and fallback text.
3. Tighten the remaining unavailable behavior so missing history never falls back to misleading zero-like values.

## Current Coverage Status

- `apps/desktop/src/features/portfolio/DashboardPanel.test.tsx` now covers both IB2026 and FF2026 imported golden values, plus account metadata fallbacks, statement period fallbacks, draft capital helper values, broker-specific sector drilldowns, unstable-history states, empty draft allocation states, and the contract that missing backend `range_metrics` renders `n/a` instead of triggering local financial recomputation.
- `apps/desktop/src/app/App.test.tsx` now covers imported-base restore for both IB2026 and FF2026, imported child-snapshot open, variant-to-imported-base switching, and imported-child-variant restore where history cards must remain unavailable instead of reusing imported broker-truth dashboard history; restore regressions also assert that missing backend `range_metrics` stays unavailable in the UI.
- persisted restore/open-node flows are now `historySource`-only, and App-level regressions verify that direct imported nodes can still use imported replay while descendant variants inherit only history context and therefore keep unavailable history cards when replay would be untrustworthy.
- new workspace/node persistence is `historySource`-only; older local workspace caches are invalidated by the IndexedDB version/reset path rather than being reconstructed into dashboard history state.
- `apps/desktop/src/test/dashboardGoldens.ts` is generated from backend output for both brokers and uses normalized import timestamps so fixture regeneration does not create timestamp-only diffs; broker-specific desktop imports flow through `apps/desktop/src/test/ib2026DashboardGolden.ts` and `apps/desktop/src/test/ff2026DashboardGolden.ts`.
- diagnostics/exposure availability semantics remain requirement-oriented: `history_context_required` describes whether the historical sections fundamentally depend on history context, so it can remain `true` even when those sections are successfully available.
- backend route coverage now includes mixed-broker `IB2026.pdf` + `FF2026.pdf` bootstrap/history-context validation plus imported-route unavailable regressions for empty or unsupported benchmark/symbol market-data conditions.
- backend analytics coverage now includes direct `FF2026.pdf` imported dashboard truth assertions for summary metrics, monthly returns, and overview composition, similar in spirit to the stronger `IB2026` truth path.

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

Broker source-of-truth statement formats in active use today:

- `docs/IB2026.pdf` is the canonical Interactive Brokers layout reference for Dashboard golden-value coverage
- `docs/FF2026.pdf` is the active Freedom24 layout reference for 2026 YTD validation, mixed-broker coverage, and desktop golden-value coverage
- `docs/ESPP2026.pdf` is the ESPP layout reference for simplified equity-compensation import coverage
- generated desktop fixtures now live in `apps/desktop/src/test/dashboardGoldens.ts`, with broker-specific re-export shims at `apps/desktop/src/test/ib2026DashboardGolden.ts` and `apps/desktop/src/test/ff2026DashboardGolden.ts`

Important fixture rule:

- these broker PDFs should be treated as statement-format and data-layout references
- durable tests should lock normalized extracted values and accounting semantics rather than assuming identical binary exports over time

Important rule:

- imported direct-source history is allowed for imported nodes
- changed variants or snapshot-only paths must be correct or unavailable
- Dashboard must not inherit imported broker-truth history for a changed snapshot if that would make numbers look plausible but wrong
- imported engine routes must also degrade to unavailable when broker-truth replay cannot be supported by benchmark history or usable symbol price history

## Dashboard-History Run Metadata

Dashboard-history now exposes an explicit run-metadata slice alongside the lighter history payload:

- `run_metadata.history_id`
- `run_metadata.methodology_id`
- `run_metadata.source_status.performance_history`
- `run_metadata.source_status.monthly_returns`
- `run_metadata.source_status.benchmark_history`
- `run_metadata.return_basis_contract.portfolio_path`
- `run_metadata.return_basis_contract.benchmark_path`
- `run_metadata.investor_economics_status`
- `run_metadata.investor_economics_partial_unlock`
- `run_metadata.return_basis_evidence.portfolio_path`
- `run_metadata.return_basis_evidence.benchmark_path`
- `run_metadata.reproducibility.input_imported_at`
- `run_metadata.reproducibility.snapshot_as_of_date`
- `run_metadata.reproducibility.history_start_date`
- `run_metadata.reproducibility.history_end_date`
- `run_metadata.reproducibility.benchmark_symbol`
- `run_metadata.reproducibility.dataset_version`

Current dashboard-history run-metadata semantics:

- `run_metadata.source_status.performance_history`
  - `live`: daily portfolio states and performance series were successfully built
  - `unavailable`: history could not be built and the dashboard must stay unavailable rather than imply a usable path
- `run_metadata.source_status.monthly_returns`
  - `live`: monthly returns are usable from the current reconstructed path
  - `suppressed`: daily history exists, but monthly-return display should be hidden because the reconstructed series is unstable
  - `unavailable`: history is unavailable, so monthly returns are unavailable too
- `run_metadata.source_status.benchmark_history`
  - `live_market_data_verified_adjusted_close`: benchmark rows loaded successfully on a verified adjusted-close basis
  - `live_market_data_unverified_return_basis`: benchmark rows loaded, but only on an unverified return basis
  - `unavailable`: no benchmark history was available for a valid dashboard-history run
- `run_metadata.return_basis_contract.portfolio_path`
  - current contract values are `verified_total_return`, `price_return_only`, `unverified_adjusted_proxy`, or `unavailable`
  - consumers must use the returned enum as-is and must not infer `verified_total_return` when the payload does not explicitly say so
- `run_metadata.return_basis_contract.benchmark_path`
  - current contract values are `verified_total_return`, `price_return_only`, `unverified_adjusted_proxy`, or `unavailable`
  - this is the authoritative benchmark return-basis classification for dashboard-history outputs
  - current fenced pilot: `verified_total_return` is only allowed for imported dashboard-history benchmark `SPY` when provenance also proves direct FMP `historical-price-eod/light`, no fallback, and ordered unique in-window `adjClose` coverage
- `run_metadata.return_basis_evidence.benchmark_path`
  - authoritative positive evidence for the benchmark slice
  - consumers must not infer verification from `adjClose` field presence alone; use `verification_status`, `economic_basis`, and explicit `scope` evidence together
- `run_metadata.investor_economics_status`
  - current dashboard-history policy is always `withheld`
  - this is deliberate policy codification, not a transient data-quality fallback
  - `withheld` remains the overall investor-economics state even when a narrow exact-slice scalar allowlist admits one or more individual fields
  - use the explicit reason together with the partial-unlock metadata rather than treating the values as merely missing
- `run_metadata.investor_economics_partial_unlock`
  - explicit contract for the only currently allowlisted dashboard-history exception path while overall investor-economics status stays `withheld`
  - `mode = allowlisted_exact_slice_scalars_only` means consumers must not generalize from any admitted scalar to broader benchmark-relative or path-derived families
  - `exact_slice_scalar_allowlist` is authoritative per-field policy:
    - `range_metrics[*].summary.time_weighted_return_pct`: only for the identical admitted exact portfolio slice
    - `range_metrics[*].summary.benchmark_return_pct`: only for that same identical admitted exact slice and only with independently verified benchmark `verified_total_return`
    - `range_metrics[*].summary.excess_return_pct`: only for that same identical admitted slice pair, only when both already-allowlisted exact-slice legs are present in the same server response, and only from the server-side scalar runtime path
  - `client_derivation_rule = server_side_scalar_only_no_daily_series_subtraction_equivalence` means consumers must not treat daily-series subtraction, benchmark-path reconstruction, or any local derivation as equivalent to a future server-emitted exact-slice scalar
  - `withheld_families` explicitly fences the broader withheld families that remain off-limits even if one of the allowlisted scalars is present
- `run_metadata.reproducibility.*`
  - records the import timestamp, latest snapshot as-of date, effective history window, requested benchmark symbol, and current market-data dataset version used by the dashboard-history engine

Investor-economics withholding rule:

- daily history and performance-series rows may still exist while `run_metadata.investor_economics_status.status = withheld`
- in that state, dashboard-history now publishes an explicit partial-unlock contract for the only allowlisted exception path
- under that contract, dashboard-history only allows three live exact-slice scalar outputs today: portfolio-only `time_weighted_return_pct`, exact-slice `benchmark_return_pct` only when the benchmark basis is independently `verified_total_return`, and exact-slice `excess_return_pct` only when both admitted exact-slice legs are present in the same server response
- exact-slice `excess_return_pct` is admitted only as same-slice subtraction of those two already-admitted exact-slice scalars; if either leg is withheld, null, unverified, or scope-mismatched, `excess_return_pct` must remain `null`
- current runtime now emits only that exact-slice `excess_return_pct` scalar exception; `max_drawdown_pct` and all other investor-economics outputs still remain withheld even when one or both exact-slice scalar outputs are present
- monthly/rebucketed/rolling/non-identical-window outputs must not be inferred or reconstructed from those two scalars
- daily-series subtraction or client-side derivation must not be treated as equivalent to the server-emitted exact-slice scalar
- downstream consumers must treat those `null` values as deliberate withholding tied to the run metadata, not as a generic history failure

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
| Time-Weighted Return | `selectedRangeMetrics.summary.time_weighted_return_pct` | `analysis.range_metrics[selectedRange].summary.time_weighted_return_pct` | `engine-derived` | if backend range metrics are unavailable, or investor-economics outputs are intentionally withheld for the run, render `n/a` | this value may be `null` even when daily history exists; covered by IB2026 and FF2026 golden tests |
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
| Drawdown | `selectedRangeMetrics.max_drawdown_pct` | `analysis.range_metrics[selectedRange].max_drawdown_pct` | `engine-derived` | if backend range metrics are unavailable, or investor-economics outputs are intentionally withheld for the run, render `n/a` | this value may be `null` even when daily history exists; covered by IB2026 and FF2026 golden tests |
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
7. Dashboard-history withholding is distinct from unavailability: when `run_metadata.investor_economics_status` is `withheld`, history may still be present, but only the explicit allowlisted exact-slice scalars described in `run_metadata.investor_economics_partial_unlock` may appear; only exact-slice `range_metrics[*].summary.excess_return_pct` joins `time_weighted_return_pct` and exact-slice `benchmark_return_pct`, while `max_drawdown_pct` and other non-allowlisted investor-economics outputs must stay `null`/hidden.

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

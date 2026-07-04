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

*Rewritten 2026-07-04 (Epic 25 / US-25.4) to match the shipped `DashboardPanel.tsx` — the
prior version of this section described an "Allocation Overview" draft editor and
capital-path/MWR-chart helpers that no longer exist anywhere in the codebase
(grep-verified). Epic 25 was created specifically because this doc had drifted
from the shipped component; see `docs/product/prd/epic-25-dashboard-performance-risk-summary.md`.*

Dashboard currently renders from three root inputs, all passed as props to
`DashboardPanel` from `apps/desktop/src/app/App.tsx`:

1. `result: DashboardAnalysis`
   - imported metadata (statement/account/loaded-file labels), `performance_series`,
     and `range_metrics` are sourced from this path
   - for imported nodes, history comes from `runImportedDashboardHistory(...)`
   - for snapshot-only or variant paths, history may come from
     `runDashboardHistoryEngine(...)` or degrade to unavailable
2. `exposureResult: ExposureAnalysis | null` and `factorModel: ExposureFactorModelResponse | null`
   - power `RollingFactorLoadingsCard`, `SectorPieCard`, and `BenchmarkPositioningCard`
3. `diagnosticsAnalysis: DiagnosticsEngineResponse | null` (Epic 25 / US-25.3)
   - powers `RiskSummaryCard` (`volatility_summary`, `drawdown_summary`,
     `risk_concentration_summary`) — a separate fetch/state from `result`,
     threaded into `DashboardPanel` alongside `exposureResult`/`factorModel`

There is no longer a draft-editing surface on the Dashboard tab (no
`draftSnapshot`, no editable Allocation Overview) — sector composition is a
read-only donut (`SectorPieCard`), and holdings editing does not exist on this
tab today.

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

## Import Admission

Dashboard may display import-admission evidence attached to imported bootstrap responses, but `docs/contracts/import-admission-fields.md` remains the detailed contract.

| Dashboard display | Source field | Boundary |
| --- | --- | --- |
| Admission decision | `admission_summary.decision` | read-only evidence for imported broker-truth; never mutates imported values or derived portfolio truth |
| Trust level | `admission_summary.trust_level` | follows platform trust semantics and may only communicate verification/degradation/withholding/unavailability |
| Check rows | `admission_summary.checks[*]` | observed/comparison/delta evidence must be finite numeric values when present; missing or non-finite evidence is unavailable/degraded, not fabricated |

Import admission is informational on Dashboard: workspace creation is non-blocking and the read-only summary cannot upgrade trust or change broker truth. (The never-wired `ImportAdmissionReviewDispositionV1` reviewer-disposition plumbing was removed in US-23.9 — no producer, no consumer.)

## Field Inventory

### Header and account metadata

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Broker badge | `formatBrokerLabel(result.snapshot.statement.importer)` in `apps/desktop/src/features/portfolio/DashboardPanel.tsx` | `analysis.snapshot.statement.importer` | `broker-truth` | if importer missing, current code still falls back to Interactive Brokers label logic; should eventually render explicit unknown | covered by IB2026 and FF2026 golden tests |
| Loaded file(s) | `formatLoadedStatements(result, lastImportedFileNames)` | `analysis.snapshot.statements` first, fallback `lastImportedFileNames` | `broker-truth` | if no statements and no fallback files, omit | covered by IB2026 and FF2026 golden tests |
| Restored on launch | `restoredSession` | App local state | not financial | n/a | session/UI state only |

### Performance & Benchmark card (Epic 25 / US-25.1)

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Indexed chart (portfolio vs benchmark) | `PerformanceBenchmarkCard.tsx` `buildIndexedSeries(result.performance_series)` | `analysis.performance_series` | `engine-derived` | if no non-null series points, render `EmptyState` | base-100 rebasing per §Indexed Return Series |
| Return-basis label | `returnBasisLabel(run_metadata.return_basis_contract.{portfolio_path,benchmark_path})` | `analysis.run_metadata.return_basis_contract` | `engine-derived` | falls back to "Unavailable" for any contract value outside the known enum | plain-text label, not the Exposure-tab `TrustBadge` primitive (different vocabulary — see US-25.1 story Notes) |
| Portfolio Value | `range_metrics[activeRange].summary.end_value` | `analysis.range_metrics` | `engine-derived` | `n/a` if `range_metrics` absent or the field is `null` | |
| Time-Weighted Return | `range_metrics[activeRange].summary.time_weighted_return_pct` | `analysis.range_metrics` | `engine-derived` | `n/a` if `range_metrics` absent or the field is `null`, incl. when investor-economics is withheld and this scalar isn't in the allowlist | see §Money-Weighted Return / dashboard-history withholding rule below |
| Money-Weighted Return | `range_metrics[activeRange].summary.money_weighted_return_pct` | `analysis.range_metrics` | `engine-derived` | `n/a` if `range_metrics` absent or the field is `null` | Modified Dietz method, §Money-Weighted Return |
| Net Contributions | `range_metrics[activeRange].summary.net_contributions` | `analysis.range_metrics` | `engine-derived` | `n/a` if `range_metrics` absent | |
| Range selector | `WindowSelector` in `DashboardPanel.tsx`, state lifted there (US-25.2) | keys of `analysis.range_metrics` | not financial | selector hidden when fewer than 2 ranges | shared with `MonthlyReturnsGrid` so both cards always show the same range |

### Monthly Returns Grid (Epic 25 / US-25.2)

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Monthly return cells | `MonthlyReturnsGrid.tsx`, one cell per `range_metrics[activeRange].monthly_returns[]` | `analysis.range_metrics` | `engine-derived` | whole-card `EmptyState` when `range_metrics` absent | signed `+X.XX%`/`−X.XX%` (color + sign, not color alone) |
| Monthly returns hidden-state | `!metrics.monthly_returns_reliable` | `analysis.range_metrics[activeRange].monthly_returns_reliable` | `unavailable-required` | whole-card `EmptyState`, never individually-suppressed cells | must hide unstable monthly data rather than show plausible garbage |

### Risk Summary card (Epic 25 / US-25.3)

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Portfolio / Benchmark / Downside Volatility, Tracking Error | `RiskSummaryCard.tsx` from `diagnosticsAnalysis.volatility_summary` | `diagnosticsAnalysis` (separate App.tsx state, not `analysis`) | `engine-derived`, synthetic-history basis | `n/a` per null field; whole-card `EmptyState` if `diagnosticsAnalysis` or any of its three summary sub-objects is absent | §Volatility and Relative Risk |
| Current / Max Drawdown | `diagnosticsAnalysis.drawdown_summary` | `diagnosticsAnalysis` | `engine-derived`, synthetic-history basis | same as above | **Deliberately not** `DashboardHistoryResult.max_drawdown_pct` (that field stays withheld under the investor-economics policy below); diagnostics' drawdown is a separate, unwithheld path — see US-25.3 story Context |
| Factor HHI / Position HHI | `diagnosticsAnalysis.risk_concentration_summary.{factor_hhi,position_hhi}` | `diagnosticsAnalysis` | `engine-derived`, synthetic-history basis | same as above | §Risk Contribution and Concentration; rendered as a raw ratio, no `%` |
| Top-N Factor/Position Risk Share | `diagnosticsAnalysis.risk_concentration_summary.top_{1,3,5}_*_risk_share` | `diagnosticsAnalysis` | `engine-derived`, synthetic-history basis | same as above | **fields are 0-1 fractions** — the card multiplies by 100 before display (`formatShareAsPct`); do not append `%` to the raw value |
| Risk contribution basis label | `run_metadata.section_trust.risk_contribution_path` | `diagnosticsAnalysis.run_metadata` | `engine-derived` | falls back to "Unavailable" | plain-text label distinct from the Exposure-tab `TrustBadge` primitive |
| Information Ratio / Active Return (vs benchmark) | `diagnosticsAnalysis.relative_risk.{information_ratio,active_return_pct}` (Epic 25 / US-25.5) | `diagnosticsAnalysis` | `engine-derived`, synthetic-history basis | rows omitted entirely (not `n/a`) when `volatility_summary.tracking_error_pct` is `null` — mathematically dependent, per `financial-methodology.md` §Information Ratio; `n/a` per individually-null field otherwise | already computed in `risk.py` prior to this epic; this story only added the methodology section + UI row |

### Factor / Composition cards (pre-Epic-25, unchanged)

| UI field | Current UI/provider source | App state source | Truth class | Notes |
| --- | --- | --- | --- | --- |
| Rolling Factor Analysis | `RollingFactorLoadingsCard.tsx` | `exposureResult`, `factorModel` | `engine-derived`, synthetic-history basis | unchanged by Epic 25 |
| Sector composition donut | `SectorPieCard.tsx` | `result`, `exposureResult` | `engine-derived` | unchanged by Epic 25; replaced the earlier editable Allocation Overview draft (no longer present anywhere in the codebase) |
| Benchmark Positioning | `BenchmarkPositioningCard.tsx` | `exposureResult` | `engine-derived` | unchanged by Epic 25 |

## Current Provider Chain By Section

### Imported metadata and statement facts

- UI: `DashboardPanel.tsx`
- App state: `analysis.snapshot`
- Adapter: `composeDashboardAnalysisWithHistory(...)`
- Engine source:
  - imported nodes: import bootstrap snapshot plus `runImportedDashboardHistory(...)`
  - snapshot-only nodes: `runDashboardHistoryEngine(...)` when supported
- origin truth: imported statement snapshot, ultimately from broker statement parsing

### Performance & Monthly Returns (Epic 25 / US-25.1, US-25.2)

- UI: `PerformanceBenchmarkCard.tsx`, `MonthlyReturnsGrid.tsx`, shared range state in `DashboardPanel.tsx`
- App state: `analysis.range_metrics`, `analysis.performance_series`, `analysis.run_metadata`
- Adapter: `composeDashboardAnalysisWithHistory(...)`
- Engine source: `runImportedDashboardHistory(...)` or `runDashboardHistoryEngine(...)`
- origin truth: imported path is broker-truth replay plus engine-derived path math; becomes `unavailable` if benchmark history or usable symbol price history is missing

### Risk Summary (Epic 25 / US-25.3)

- UI: `RiskSummaryCard.tsx`
- App state: `diagnosticsAnalysis` (separate state from `analysis`, threaded into `DashboardPanel` as its own prop)
- Adapter: none — reads `DiagnosticsEngineResponse` fields directly
- Engine source: `runDiagnosticsEngine(...)` or `runImportedDiagnosticsEngine(...)`
- origin truth: synthetic-history (current holdings applied to historical prices), independent of the dashboard-history investor-economics withholding policy

## Current Accuracy Rules

1. Imported nodes may render broker-truth history.
2. Variants and snapshot-only paths must be correct or unavailable.
3. If cards/chart/history come from one snapshot and composition cards come from another snapshot, Dashboard is internally inconsistent and that is a bug.
4. If a history-based field cannot be supported faithfully, the UI must render `n/a`, hide the unstable cards, or show an unavailable panel.
5. Imported history replay is only trustworthy when the broker snapshot and required market-data support are both present; otherwise the result must degrade to `unavailable`.
6. Dashboard-history withholding is distinct from unavailability: when `run_metadata.investor_economics_status` is `withheld`, history may still be present, but only the explicit allowlisted exact-slice scalars described in `run_metadata.investor_economics_partial_unlock` may appear; only exact-slice `range_metrics[*].summary.excess_return_pct` joins `time_weighted_return_pct` and exact-slice `benchmark_return_pct`, while `max_drawdown_pct` and other non-allowlisted investor-economics outputs must stay `null`/hidden on the Performance card. `RiskSummaryCard` sidesteps this by sourcing drawdown from the separate, unwithheld diagnostics path instead.
7. `risk_concentration_summary.top_*_risk_share` fields are 0-1 fractions, not percentages — a consumer that renders them with a bare `%` suffix without multiplying by 100 is wrong by a factor of ~100 (this exact bug was caught and fixed during US-25.4).

## Current Coverage Status

- `apps/desktop/src/features/portfolio/DashboardPanel.test.tsx` covers both IB2026/FF2026 imported golden values, account metadata fallbacks, statement period fallbacks, the Epic-25 Performance/Monthly-Returns/Risk-Summary cards (chart + summary strip, `n/a` rendering, EmptyStates, shared range-selector sync, investor-economics withholding, diagnostics-sourced drawdown vs the withheld dashboard-history value, defensive handling of partially-absent diagnostics sub-objects), and the contract that missing backend `range_metrics` renders `n/a` instead of triggering local financial recomputation.
- `apps/desktop/src/app/App.test.tsx` covers imported-base restore for both IB2026 and FF2026, imported child-snapshot open, variant-to-imported-base switching, and imported-child-variant restore where history cards must remain unavailable instead of reusing imported broker-truth dashboard history; restore regressions also assert that missing backend `range_metrics` stays unavailable in the UI.
- persisted restore/open-node flows are `historySource`-only, and App-level regressions verify that direct imported nodes can still use imported replay while descendant variants inherit only history context and therefore keep unavailable history cards when replay would be untrustworthy.
- new workspace/node persistence is `historySource`-only; older local workspace caches are invalidated by the IndexedDB version/reset path rather than being reconstructed into dashboard history state.
- `apps/desktop/src/test/dashboardGoldens.ts` is generated from backend output for both brokers and uses normalized import timestamps so fixture regeneration does not create timestamp-only diffs; broker-specific desktop imports flow through `apps/desktop/src/test/ib2026DashboardGolden.ts` and `apps/desktop/src/test/ff2026DashboardGolden.ts`.
- diagnostics/exposure availability semantics remain requirement-oriented: `history_context_required` describes whether the historical sections fundamentally depend on history context, so it can remain `true` even when those sections are successfully available.
- backend route coverage includes mixed-broker `IB2026.pdf` + `FF2026.pdf` bootstrap/history-context validation plus imported-route unavailable regressions for empty or unsupported benchmark/symbol market-data conditions.
- backend analytics coverage includes direct `FF2026.pdf` imported dashboard truth assertions for summary metrics, monthly returns, and overview composition, similar in spirit to the stronger `IB2026` truth path.

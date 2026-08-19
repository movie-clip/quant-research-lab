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

- `docs/IB2026.csv` is the canonical Interactive Brokers statement for Dashboard golden-value coverage (US-28.2 — the Activity-Statement CSV export; the golden pipeline prefers it, PDF names remain fallbacks). Statement provenance on golden snapshots reads `source_path: "IB2026.csv"`, `detected_format: "csv"`, `statement_period: "2026-01-01 - 2026-06-30"` (normalized ISO), `page_count: null`
- `docs/IB2026.pdf` remains the Interactive Brokers PDF layout reference (legacy 2022–2025 statements import through the PDF chain with `detected_format: "pdf"`)
- `docs/FF2026.pdf` is the active Freedom24 layout reference for 2026 YTD validation, mixed-broker coverage, and desktop golden-value coverage
- `docs/ESPP2026.pdf` is the ESPP layout reference for simplified equity-compensation import coverage
- generated desktop fixtures now live in `apps/desktop/src/test/dashboardGoldens.ts`, with broker-specific re-export shims at `apps/desktop/src/test/ib2026DashboardGolden.ts` and `apps/desktop/src/test/ff2026DashboardGolden.ts`

Important fixture rule:

- these broker statements should be treated as statement-format and data-layout references
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
- `run_metadata.fx_fallback_currencies` (US-27.8)
- `run_metadata.unpriced_replay_symbols` (US-31.2)
- `run_metadata.replay_cash_anchor` (US-31.3)
- `run_metadata.withheld_return_dates` / `run_metadata.withheld_return_reason` (US-31.3)
- `run_metadata.quantity_withheld_symbols` (US-33.2)
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
  - current contract values are `verified_total_return`, `replay_derived`, `price_return_only`, `unverified_adjusted_proxy`, or `unavailable`
  - consumers must use the returned enum as-is and must not infer `verified_total_return` when the payload does not explicitly say so
  - **`replay_derived` (US-34.2 / Epic 34 F-1)** — the return was chained from the imported ledger replay's own daily states. A real measurement, on **reconstructed** inputs: opening positions rolled back through the ledger, a mixed valuation basis (market history / statement close / trade price), and a terminal reconciliation to the statement's ending NAV. Those are precisely the conditions the strict proof admission refuses to certify (`inferred_opening_quantities`, `mixed_basis_valuation`, `terminal_force_reconciliation_present`, `forward_filled_prices`), so this is a rung **below** `verified_total_return`, never a substitute for it. It is **portfolio-path only** — a benchmark is priced from market data and can never be replayed. Before US-34.2 this field was a hardcoded literal `"unavailable"`, which suppressed the entire cumulative return series (`performance.py` computes `portfolio_return_pct` only for a publishing basis) and every headline scalar on the Dashboard, on every run.
  - the value is **classified from the run**: `verified_total_return` when the proof admission grants an exact slice, `replay_derived` when the imported replay produced daily states, `unavailable` when it produced none
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
    - `range_metrics[*].summary.benchmark_return_pct` (`unlock_condition = publishing_benchmark_return_basis_only`, US-34.5): published whenever the **benchmark's own** basis supports a return — `verified_total_return` or `price_return_only` — re-based to each range's own start. It does **not** depend on the portfolio's exact-slice admission: the two legs are measured from different data, and one leg's proof status is not evidence about the other's. `unverified_adjusted_proxy` and `unavailable` still publish nothing.
    - `range_metrics[*].summary.excess_return_pct` (`unlock_condition = both_published_legs_present_only`, US-34.5): strictly the difference of the two **published** figures, rounded to 2dp. If either leg is null the excess is null — never a figure computed against a null read as zero.
  - `client_derivation_rule = labelled_scalars_published_daily_series_withheld` (US-34.5, owner decision 2026-08-17) means the per-range scalars are published **with their basis label**, while the daily benchmark return chain stays withheld. This replaced `server_side_scalar_only_no_daily_series_subtraction_equivalence`, which withheld figures the same response already made derivable from its own published prices — removing the label rather than the information, and making a price return more likely to be misread as a total return.
  - `withheld_families` explicitly fences the broader withheld families that remain off-limits even if one of the allowlisted scalars is present
- `run_metadata.reproducibility.*`
  - records the import timestamp, latest snapshot as-of date, effective history window, requested benchmark symbol, and current market-data dataset version used by the dashboard-history engine

Investor-economics withholding rule:

- daily history and performance-series rows may still exist while `run_metadata.investor_economics_status.status = withheld`
- in that state, dashboard-history now publishes an explicit partial-unlock contract for the only allowlisted exception path
- under that contract, dashboard-history allows three live scalar outputs today: `time_weighted_return_pct` (portfolio, on the exact-slice or `replay_derived` rung), `benchmark_return_pct` (on any publishing benchmark basis), and `excess_return_pct` (when both of those are present)
- `excess_return_pct` is admitted only as the subtraction of those two published scalars; if either leg is withheld, null, unverified, or scope-mismatched, `excess_return_pct` must remain `null`
- `max_drawdown_pct` and all other investor-economics outputs still remain withheld even when the scalar outputs are present
- monthly/rebucketed/rolling/non-identical-window outputs must not be inferred or reconstructed from those scalars
- the **daily** `performance_series[*].benchmark_return_pct` chain remains withheld (`benchmark_relative_series`); the chart indexes `benchmark_price` itself, so the chain is not needed to draw it
- the benchmark's adjusted series is fetched from `historical-price-eod/dividend-adjusted` and used for the **return only** (US-34.9); position and FX valuation stay on `historical-price-eod/light`, because a dividend-adjusted series is a return series and would put `total_market_value` at odds with the broker's statement
- **publishing is not promotion**: a published `benchmark_return_pct` on `price_return_only` is a price return, not a total return. `run_metadata.return_basis_contract.benchmark_path` states which, `investor_economics_status` stays `withheld`, and the UI must render the basis marker rather than presenting the figure bare
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
| Monthly return cells | `MonthlyReturnsGrid.tsx`, one cell per `range_metrics[activeRange].monthly_returns[]` | `analysis.range_metrics` | `engine-derived` | whole-card `EmptyState` when `range_metrics` absent | signed `+X.XX%`/`−X.XX%` (color + sign, not color alone). Cash-flow-neutral daily returns bucketed by their **end date's** month, baseline carried across month boundaries so Π(1+mᵢ) chains to the range's compounded return (US-27.2); a month with no computable return emits no cell (never a fabricated 0.00%) — see `financial-methodology.md` §Monthly Returns |
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
6. Dashboard-history withholding is distinct from unavailability: when `run_metadata.investor_economics_status` is `withheld`, history may still be present, but only the allowlisted scalars described in `run_metadata.investor_economics_partial_unlock` may appear — `time_weighted_return_pct`, `benchmark_return_pct` and `excess_return_pct`, each on its own stated condition (US-34.5) — while `max_drawdown_pct` and other non-allowlisted investor-economics outputs must stay `null`/hidden on the Performance card. `RiskSummaryCard` sidesteps this by sourcing drawdown from the separate, unwithheld diagnostics path instead.
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

- `run_metadata.fx_fallback_currencies` (US-27.8 / audit F9): currencies that required base-currency conversion during the ledger replay but had no FX rate — the affected values are carried **unconverted** and this field discloses it (never a silent 1:1 conversion claim); see `financial-methodology.md` §FX Conversion Fallback Disclosure. Currently every non-base position appears here because no engine wires real FX rates yet (Epic 26 scope).

- `run_metadata.unpriced_replay_symbols` (US-31.2 / Epic 31 F-1): symbols the ledger replay reconstructed as held during the window (opening positions, or bought-and-sold entirely inside it) for which **no** price history was fetchable **and** no statement close-price anchor exists — they contributed **0** to that day's market value. Since-sold symbols are the common case: they are absent from the current snapshot, so they are absent from the engine's `fallback_prices` map. Empty list = full replay coverage; the field is never `null` and never absent. Distinct from the statement-anchored disclosure (a *held* symbol valued flat at its statement close, US-30.2), which is a weaker degradation than no valuation at all. See `financial-methodology.md` §Synthetic History Coverage Rule.

- `run_metadata.replay_cash_anchor` (US-31.3 / Epic 31 F-2): provenance + trust of the replay's **opening cash**. `base_cash = starting_nav − opening_positions_value` is only sound when both terms share an as-of date; on IB2026 they do not (`nav_as_of` 2026-01-01 = statement-period start, `window_start` 2026-01-08 = replay window start), so five trading days of market movement are absorbed into cash as a plug. Fields: `basis` (`statement_starting_cash` | `statement_nav_at_window_start` | `statement_nav_date_mismatch` | `snapshot_cash_balances` | `unavailable`), `nav_as_of`, `window_start`, `residual` (measured against the statement-implied opening cash, computed from **FX-converted** ledger flows — the raw per-currency sum is currency-mixed and gives a wrong figure), and `trust` (`verified` only when dates align and the residual is within `REPLAY_RECONCILIATION_TOLERANCE`; otherwise `degraded`). Never `verified` on a date mismatch.

  **`statement_starting_cash` (US-34.3 / Epic 34 F-2) is the preferred basis and the precedence head:** statement's reported `starting_cash` → the derived `starting_nav − opening_positions_value` identity → the snapshot's own cash balances. The derived identity mixes two differently-dated terms (period-start NAV against window-start position values), so it absorbed five trading days of market movement as a plug and could **never** report `verified` — the warning fired on every run of every statement, which is a disclosure carrying no information. The broker reports the figure directly: on IB2026 $4,672.04 against the derived $3,252.74, cutting the residual from −$1,377.59 to **+$46.69** and the terminal reconciliation from +$1,366.17 to **−$53.13**.

  **Trust follows the anchor's source, not its residual.** A directly observed figure is `verified`; the residual is published alongside it as a *separate* reconciliation fact — how well the ledger's flows explain the statement's own two cash endpoints — rather than as evidence the opening cash is wrong. It degrades above `REPLAY_OPENING_CASH_RESIDUAL_SHARE` (2% of opening cash), where the ledger has genuinely failed to explain its own statement. The derived bases keep the old absolute rule (`REPLAY_RECONCILIATION_TOLERANCE`), because for them a residual *does* mean the derivation is absorbing something.

- `run_metadata.withheld_return_dates` / `withheld_return_reason` (US-31.3 / Epic 31 F-3): dates whose replayed return was **withheld** because the state carried a material `reconciliation_adjustment` — an accounting correction snapped onto the terminal state to match the statement's ending NAV. Publishing it as a return would present a bookkeeping entry as a market move (guardrail #3), so the point is null with a stated reason. Empty list = nothing withheld; the fields are never `null` in place of an empty list. Pairs with `DailyPortfolioState.reconciliation_adjustment`, which carries the signed amount on the affected state.

- `DailyPortfolioState.trade_flow` (US-24.9): net **base-currency market value moved into the holdings** by BUY/SELL entries settled on that day — positive for a net buy, negative for a net sell. It is the negation of those entries' `cash_effect`, each **FX-converted before summing** (the raw currency-mixed sum is meaningless — the US-31.3 measurement trap). Deliberately distinct from `external_cash_flow`, which stays DEPOSIT/WITHDRAWAL-only: a trade is an internal transfer between the cash and holdings sleeves, not investor money entering or leaving. Recorded on every replayed state by `PortfolioStateEngine` (so every caller — dashboard history, diagnostics, drift, proof — carries it); `0.0` on a day with no trades, never `null`. Consumed by the `market_value_trade_neutral` return basis, which the **imported ledger-replay** path uses for its risk statistics: `r_t = (MV_t − trade_flow_t)/MV_{t−1} − 1` excludes the cash sleeve without reading a BUY as a gain. The TS mirror (`types.ts` → `DailyPortfolioState.trade_flow`) is optional for backward compatibility with persisted snapshots written before this field existed. See `financial-methodology.md` §Rolling Pearson Correlation → return basis.

- `DailyPortfolioState.unbacked_cash_flow` (US-33.2 / Epic 33 F-1, F-2): base-currency cash moved on that day by BUY/SELL entries in a symbol whose reconstructed **quantity was withheld**. The cash is broker truth and is applied, but the position behind it is in **no** market value, so `total_portfolio_value` steps with nothing offsetting it — the US-24.9 fabrication class, re-opened by withholding. A state carrying a material amount has `return_is_publishable == False`. **Materiality is a share of that day's portfolio value** (`REPLAY_UNBACKED_CASH_MATERIAL_SHARE`, 0.1%), not a flat dollar amount (US-34.4 / Epic 34 F-4): US-33.2 originally reused `REPLAY_RECONCILIATION_TOLERANCE` ($1.00, calibrated for cent-level rounding across daily states), which discarded real return days for flows that distort nothing. On IB2026 the six unbacked days are bimodal — 0.0085% and 0.0400% against 2.77%–3.71%, a 69× gap — so two days are published again and four stay withheld, so **no return is published for that day** on any basis, and the date appears in `withheld_return_dates` with a reason naming this cause. `0.0` on every ordinary day, never `null`. On IB2026 this withholds six days (LQQ's trade dates), which removes a fabricated **+3.08%** on 2026-04-17 — the window's largest cash-inclusive TWR move. Pairs with `run_metadata.quantity_withheld_symbols`.

- `run_metadata.trade_price_anchored_symbols` (US-24.10): symbols valued at the **broker's own execution price**, carried forward from the trade — the **third and last valuation tier**, below market history and the statement close. Precedence, never inverted: fetchable price history → statement close price (US-27.7/US-30.2) → last trade price at or before the day. **Forward-carry only:** before a symbol's first observed trade it stays unvalued and is reported in `unpriced_replay_symbols` instead — reaching backwards would fabricate a price for a date the broker never produced one (the US-27.7 no-back-fill rule). Values are converted from the **trade's settle currency** (`ImportedLedgerEntry.currency`), not the fund currency the US-31.5 rule selects for market-priced holdings, because a trade price is quoted in the currency it executed in; with no rate available it is carried unconverted and disclosed via `fx_fallback_currencies`. The carried segment is **flat** — it contains no market movement — so it is disclosed rather than passed off as a priced series. **Exclusivity is per (symbol, day), not per symbol** (US-33.3 / Epic 33 F-3, correcting US-24.10's original wording): exactly one tier values a symbol on any given day, but these lists are **unions over the window**, so the same symbol may appear in more than one — a holding that predates its own first trade is `unpriced` on those days and `trade_price_anchored` afterwards, and both lists are correct about different days. This tier replaces a `$0` valuation that let a BUY/SELL move cash with no offsetting market value, which the cash-inclusive TWR then published as performance (IB2026: −7.90% on 2026-04-08, +9.61% on 2026-04-27). See `financial-methodology.md` §Synthetic History Coverage Rule.

- `range_metrics[*].summary.money_weighted_return_pct` / `investment_gain` (US-34.6 / Epic 34 F-7): both are **performance** figures and are computed from the **market-derived terminal value** — the terminal `total_portfolio_value` less its `reconciliation_adjustment` — so neither republishes the statement reconciliation that US-31.3 withholds from the time-weighted return. On IB2026 the money-weighted return is 2.95% (it was 5.30%, of which 2.35pp was the accounting entry) and the gain is $1,714.71 (was $3,080.88). **`end_value`, `start_value`, `net_contributions` and every daily state keep the reconciled value** — the statement's ending NAV is broker truth and is the correct *level*. The consequence is that `end_value − start_value − net_contributions ≠ investment_gain` on a reconciled run, which the Dashboard must explain on screen rather than leave looking like an arithmetic error.

- `range_metrics[*].portfolio_return_trust` (US-34.2 / Epic 34 F-1): trust of that range's `time_weighted_return_pct` **and** `max_drawdown_pct` — `verified` only when the proof admission granted an exact slice, `degraded` when the basis is `replay_derived`, `unavailable` when no return was published for the range. Carried per range rather than only on `run_metadata` so a card rendering one window does not have to cross-reference the run contract. The UI **must** render a visible marker for `degraded`: publishing a reconstructed-basis return that reads like a verified one is the failure this rung exists to prevent. `degraded` is never collapsed into `unavailable` — a published-but-degraded number and an absent one are different facts.

- `run_metadata.quantity_withheld_symbols` (US-33.2 / Epic 33 F-1, F-2): reconstructed quantities the replay **refused to publish**. The opening roll-back `opening = ending + Σ SELL − Σ BUY` (`PortfolioStateEngine`) presumes a single share unit across the window; a split breaks the identity and yields a position size the broker never held (IB2026: **199 phantom LQQ units**, which the US-24.10 anchor then valued at the stale pre-split EUR 1,457.78 — peak replayed market value **$518,078.75** against a `stock_total` of **$64,922.99**). Detected from the symbol's **own execution prices** spanning a ratio ≥ `REPLAY_SHARE_UNIT_DISCONTINUITY_RATIO` (5.0), measured **within a single currency** so an FX difference can never be mistaken for a unit change. Each entry carries `symbol`, `reason` (`share_unit_discontinuity`), `currency`, `price_low`, `price_high`, `price_ratio` and `withheld_opening_quantity` — the evidence, so the researcher can judge the call rather than take it. **Withheld is not unpriced:** `unpriced_replay_symbols` means the quantity is trusted and no price exists, this means the *quantity itself* is not publishable, so a withheld symbol emits **no position line on any day** and appears in **none** of the three valuation tiers. Its cash movements are unaffected (broker truth), and because it is priced on no day the US-24.9 trade-leg gate keeps its legs out of `trade_flow`. Empty list = no detectable discontinuity; never `null`. **Documented limitation:** a small split (2:1, 3:1) falls below the threshold and is not detected — see `financial-methodology.md` §Share-Unit Discontinuity Withholding.

  **How much was withheld (US-34.4 / Epic 34 F-3).** Each entry also carries `peak_net_cash_invested` (base currency), `peak_share_of_portfolio_pct` and `exposure_day_count`, so the researcher can size the gap rather than only learn it exists. On IB2026: **$2,130.62**, **3.52%** of the portfolio, across **66** of the window's 148 days.

  `exposure_day_count` is the span of valuation dates from the symbol's first trade to its last — deliberately **not** "days held", which would need a running quantity, the very thing that is untrusted. Cumulative cash cannot substitute: a round trip closing at a loss leaves a positive cash residual, so days after the position closed would keep counting (44 by that measure against a ~26-day true holding). Derived from the broker's own cash effects alone — no price, no quantity, no market data — because the quantity is the untrusted thing; each trade is FX-converted before it enters the running total (the US-31.3 currency-mixed trap). The figure is the largest **end-of-day** net investment: a same-day buy-then-sell drives the within-day gross to $4,410.08 on 2026-06-23, which overstates what was ever held overnight. It is a **lower bound, not a valuation** — what the broker paid, not what the position was worth — so surfaces must word it as "at least", and it must never enter `total_market_value`.

- **Rendering surface for the six replay disclosures** (US-24.11, extended by US-33.2): `fx_fallback_currencies`, `unpriced_replay_symbols`, `replay_cash_anchor`, `withheld_return_dates` / `withheld_return_reason`, `trade_price_anchored_symbols` and `quantity_withheld_symbols` are rendered on the Dashboard by `ReplayDisclosuresCard.tsx`, one prose note per present degradation. The card renders **nothing** when the run is clean, and shows the cash anchor only when its `trust` is not `verified`. It carries **no** `Synthetic` TrustBadge: the imported replay is broker truth that has been degraded, a different truth class from synthetic history. `withheld_return_dates` renders with the engine's own `withheld_return_reason`, never collapsed into "unavailable" — and that reason names **which** cause fired (terminal reconciliation, an unbacked cash flow from a withheld holding, or both), because they are different degradations. `quantity_withheld_symbols` renders **first** — a withheld position outranks a degraded valuation — and states the evidence (price range, ratio) alongside the consequence (excluded from market value, cash unaffected).

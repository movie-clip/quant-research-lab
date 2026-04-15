# Exposure Field Inventory

This document inventories financially meaningful fields shown in the desktop Exposure view and traces where they come from today.

It is the working contract for Exposure accuracy work.

## Purpose

For each visible Exposure value, we want a traceable chain:

- UI field
- UI/provider function
- App state source
- engine or adapter source
- snapshot/imported statement source
- truth class: current-state truth, engine-derived, scenario-derived, or unavailable

## Current Root Sources

Exposure currently renders from two root inputs:

1. `result: ExposureAnalysis`
   - produced in `apps/desktop/src/app/App.tsx`
   - current-state look-through, benchmark overlap, factor tilts, historical diagnostics, and degraded-availability messaging all render from this path
   - current-state sections come from `runExposureEngine(...)` or imported exposure payloads
   - historical sections come from diagnostics payloads and may degrade to unavailable

2. `factorModel: ExposureFactorModelResponse | null`
   - built in `apps/desktop/src/features/portfolio/portfolioAnalysisAdapter.ts`
   - used for factor-registry and rolling-loading presentation details

Important rules:

- current-state exposure may render from a snapshot-only path
- benchmark-relative or historical sections must be correct, explicitly degraded, or unavailable
- missing benchmark holdings must not render as plausible `0.0` overlap
- financially meaningful formulas must be documented with both methodology and implementation location

## Truth Classes

- `current-state-truth`
  - derived from current imported/snapshot positions and cash, without requiring historical replay
- `engine-derived`
  - derived by the engine from current-state inputs or history-aware diagnostics inputs
- `scenario-derived`
  - derived from edited draft scenario inputs and explicitly not broker-truth history
- `unavailable-required`
  - must render `n/a`, hidden state, or explicit degraded messaging when required inputs are missing

## Key Formula Definitions

### Constituent coverage

- `coverage_ratio = covered_market_value / portfolio_market_value`
- `portfolio_market_value` = sum of current position market values
- `covered_market_value` includes:
  - direct single-name positions at 100% of market value
  - ETF positions only when constituent holdings resolve successfully
- unresolved ETFs may still appear as direct placeholders in current-state lists, but they do not count as covered

Implementation:

- `services/quant-engine/app/analytics/risk.py` -> `build_lookthrough_exposure(...)`
- `services/quant-engine/app/services/exposure_engine.py` -> `build_exposure_result(...)`

### Benchmark overlap

When benchmark holdings are available:

- `overlap_weight = sum(min(portfolio_weight_i, benchmark_weight_i))` over shared symbols
- `active_share = 0.5 * sum(abs(portfolio_weight_i - benchmark_weight_i))` over the union of symbols
- `portfolio_in_benchmark_weight = sum(portfolio_weight_i)` over shared symbols
- `benchmark_covered_weight = sum(benchmark_weight_i)` over benchmark constituents loaded into the comparison set

When benchmark holdings are unavailable:

- overlap fields return `null`
- UI must render `n/a` / unavailable messaging rather than implied zero overlap

Implementation:

- `services/quant-engine/app/analytics/risk.py` -> `build_market_overlap_summary(...)`
- `services/quant-engine/app/services/exposure_engine.py` -> `build_exposure_result(...)`

## Field Inventory

### Availability and degraded-state messaging

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Historical diagnostics unavailable panel | `result.availability?.historical_sections_available === false` in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | `analysis.availability.historical_sections_available` | `unavailable-required` | must render instead of pretending history exists | diagnostics-side availability contract |
| Exposure availability summary panel | `result.exposure_availability?.note` plus structured confidence fields | `analysis.exposure_availability` | `engine-derived` | hide when no degradation note exists | now distinguishes look-through, benchmark-overlap, and historical-diagnostics confidence separately |
| Look-through status | `result.exposure_availability.lookthrough_status` | `analysis.exposure_availability.lookthrough_status` | `engine-derived` | if unavailable, current-state constituent resolution is not trustworthy | currently surfaced through helper text rather than raw badge |
| Look-through confidence | `result.exposure_availability.lookthrough_confidence` | `analysis.exposure_availability.lookthrough_confidence` | `engine-derived` | low/medium/high must reflect constituent-resolution trust | structured current-state confidence dimension |
| Benchmark overlap status | `result.exposure_availability.benchmark_overlap_status` | `analysis.exposure_availability.benchmark_overlap_status` | `engine-derived` | if unavailable, overlap metrics must render `n/a` | prevents missing benchmark from reading as true zero overlap |
| Benchmark overlap confidence | `result.exposure_availability.benchmark_overlap_confidence` | `analysis.exposure_availability.benchmark_overlap_confidence` | `engine-derived` | low/medium/high must reflect benchmark-holdings trust | structured benchmark-relative confidence dimension |
| Historical diagnostics confidence | `result.exposure_availability.historical_diagnostics_confidence` | composed Exposure view availability state | `engine-derived` | low when diagnostics historical sections are unavailable | desktop-composed confidence dimension from diagnostics availability |

Confidence semantics currently mean:

- `lookthrough_confidence`
  - `high`: full constituent-resolution coverage for current look-through
  - `medium`: current look-through is partial but still usable
  - `low`: current look-through is unavailable / not trustworthy enough to treat as resolved exposure
- `benchmark_overlap_confidence`
  - `high`: benchmark-relative overlap is fully available
  - `medium`: overlap is usable but inherits partial look-through resolution
  - `low`: benchmark-relative overlap is unavailable or not trustworthy
- `historical_diagnostics_confidence`
  - `high`: persisted history supports diagnostics sections
  - `low`: history-aware diagnostics are unavailable

### Current-state look-through section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Top look-through constituents | `topLookthrough` in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | `analysis.lookthrough.top_constituents` | `current-state-truth` when resolved, otherwise `engine-derived` placeholders | if no constituents, should render empty state rather than fake rows | unresolved ETFs may appear as placeholders |
| Constituent market value | `item.effective_market_value` | `analysis.lookthrough.top_constituents[].effective_market_value` | `engine-derived` | if constituent unavailable, omit row | built from direct positions or ETF constituent expansion |
| Constituent portfolio weight | `item.portfolio_weight` | `analysis.lookthrough.top_constituents[].portfolio_weight` | `engine-derived` | if constituent unavailable, omit row | derived from effective market value / portfolio market value |
| Constituent coverage | `result.lookthrough.coverage_ratio` | `analysis.lookthrough.coverage_ratio` | `engine-derived` | if no portfolio market value, render `0.00%` today; should stay explicit | means constituent-resolution coverage, not generic current-holdings display coverage |
| Unresolved positions list | `result.lookthrough.uncovered_positions` | `analysis.lookthrough.uncovered_positions` | `engine-derived` | if none, keep empty | key degraded-state indicator |
| ETF resolution map | `result.lookthrough.etf_resolution` | `analysis.lookthrough.etf_resolution` | `engine-derived` | if unresolved, omit those entries | maps local ETF symbol to resolved benchmark/holdings symbol |

### Look-through sector section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Sector labels | `topLookthroughSectors` in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | `analysis.lookthrough_sector_exposure` | `engine-derived` | if no constituent exposure, show empty/near-empty state | current-state economic exposure after ETF unpacking |
| Sector market value | `item.market_value` | `analysis.lookthrough_sector_exposure[].market_value` | `engine-derived` | if unavailable, omit row | derived from constituent-level sources |
| Sector weight | `item.weight` | `analysis.lookthrough_sector_exposure[].weight` | `engine-derived` | if unavailable, omit row | weight of total current look-through market value |

### Benchmark overlap section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Portfolio in benchmark names | `result.market_overlap.portfolio_in_benchmark_weight` | `analysis.market_overlap.portfolio_in_benchmark_weight` | `engine-derived` | if benchmark holdings unavailable, render `n/a` | share of portfolio weight that overlaps benchmark constituents |
| Active share | `result.market_overlap.active_share` | `analysis.market_overlap.active_share` | `engine-derived` | if benchmark holdings unavailable, render `n/a` | must not fall back to fake zero or fake low/high active share |
| Current-state overlap section label | `Broad Market Risk` helper copy and `Current-State Overlap` card in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | overlap + exposure availability state | `unavailable-required` | must keep current-state overlap semantics visually distinct from historical benchmark diagnostics | separation reduces current-state vs historical ambiguity |
| Overlap helper state | `overlapUnavailable ? 'Benchmark overlap unavailable' : ...` | `analysis.exposure_availability.benchmark_overlap_status` | `unavailable-required` | explicit unavailable helper required when benchmark holdings missing | currently one of the main financial correctness guardrails |
| Benchmark covered weight | not directly surfaced in cards today | `analysis.market_overlap.benchmark_covered_weight` | `engine-derived` | if benchmark holdings unavailable, keep `null` | useful for future explicit overlap diagnostics |
| Raw overlap weight | not directly surfaced in cards today | `analysis.market_overlap.overlap_weight` | `engine-derived` | if benchmark holdings unavailable, keep `null` | separate from portfolio-in-benchmark share |

### Historical benchmark/risk path section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Beta vs benchmark | `result.risk_summary.portfolio_beta` | `analysis.risk_summary.portfolio_beta` | `engine-derived` | if diagnostics unavailable, render `n/a` / unavailable panel | diagnostics contract, not exposure-only contract |
| Risk Path section label | `Risk Path` helper copy in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | diagnostics state | `unavailable-required` | must read as historical benchmark-relative diagnostics, not current-state exposure | clarifies that this path is history-aware |
| Tracking Error | `result.relative_risk.tracking_error_pct` | `analysis.relative_risk.tracking_error_pct` | `engine-derived` | if diagnostics unavailable, render `n/a` | historical benchmark-relative metric |
| Information Ratio | `result.relative_risk.information_ratio` | `analysis.relative_risk.information_ratio` | `engine-derived` | if diagnostics unavailable, render `n/a` | historical benchmark-relative metric |
| Historical benchmark-risk section label | `Historical Benchmark Risk` card in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | diagnostics state | `unavailable-required` | must stay visually distinct from current-state overlap cards | indicates these cards depend on history-aware diagnostics |
| Benchmark Sensitivity section label | `Benchmark Sensitivity` helper copy in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | diagnostics state | `unavailable-required` | must read as historical broad-market sensitivity, not current-state overlap | clarifies this section remains history-aware |
| Risk methodology text | `result.risk_summary.methodology` | `analysis.risk_summary.methodology` | `engine-derived` | if missing, should remain explicit | methodology should stay aligned with implemented formulas |

### Factor and tilt section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Market factor card | `factorExposures` from `result.factor_exposures` | `analysis.factor_exposures` | `engine-derived` | if historical diagnostics unavailable, render `n/a` and explanatory helper text | basis is now explicitly `historical_benchmark_relative` |
| SPY Overlap factor card | `factorExposures` from `result.factor_exposures` | `analysis.factor_exposures` | `engine-derived` | if benchmark overlap unavailable, render `n/a` and explanatory helper text | basis is now explicitly `benchmark_holdings_required`; mirrors `portfolio_in_benchmark_weight` semantics |
| Growth / sector / macro tilt cards | `factorExposures` from `result.factor_exposures` | `analysis.factor_exposures` | `engine-derived` | if unavailable, render `n/a` | basis is now explicitly `current_state`, separate from benchmark-dependent cards |

### Rolling factor diagnostics and snapshot section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Rolling Factor Loadings section label | helper copy in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | rolling factor diagnostics state | `unavailable-required` | must read as historical rolling diagnostics, not current-state exposure | scenario edits must not imply rerun rolling-history analytics |
| Current Snapshot Loading column | `factor.latest_loading` in `Current Factor Snapshot` table | `analysis.factor_snapshot[].latest_loading` | `engine-derived` or `scenario-derived` when scenario-aware | if unavailable, render `n/a` | current-state/snapshot value; may be scenario-aware in draft mode |
| Historical rolling-window loading column | `getSelectedWindowFactorLoading(...)` | rolling factor model summaries | `engine-derived` | if unavailable, render `n/a` | stays baseline historical even when scenario preview is active |
| Snapshot-vs-historical helper text | factor snapshot meta row in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | mixed snapshot + rolling diagnostics state | `unavailable-required` | must explicitly distinguish current snapshot values from historical rolling-window values | key guardrail against mixing scenario-aware values with baseline historical windows |

### Volatility and regime section

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Volatility & Regime section label | helper copy in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | volatility diagnostics state | `unavailable-required` | must read as historical volatility/regime diagnostics, not current-state-only exposure | scenario edits must not imply rerun historical regime analytics |
| Volatility/regime snapshot cards | `result.volatility_regime.snapshot` and `result.volatility_regime.regime` | volatility diagnostics payload | `engine-derived` | if diagnostics unavailable, render `n/a` / unavailable panel | historical diagnostics section, not a local current-state approximation |

### Scenario-only sections

| UI field | Current UI/provider source | App state source | Truth class | Unavailable rule | Notes |
| --- | --- | --- | --- | --- | --- |
| Scenario preview leverage / capital | `scenarioPreview` in `apps/desktop/src/features/portfolio/ExposurePanel.tsx` | `analysis.scenario_preview` | `scenario-derived` | hide whole section when absent | explicitly labeled as a scenario-only current-state approximation, not broker-truth history |
| Scenario drift sections | `sectorDrifts`, `positionDrifts`, `factorDrifts` | `analysis.scenario_preview` | `scenario-derived` | hide when absent | explicitly labeled that historical sections remain baseline and are not recomputed from scenario trades |
| Scenario stress / risk contribution sections | scenario-derived helper builders in `ExposurePanel.tsx` | current `analysis` plus `scenario_preview` | `scenario-derived` | should stay explicitly labeled as approximation | must not be confused with rerun historical engine outputs |

## Current Provider Chain By Section

### Current-state look-through and overlap

- UI: `apps/desktop/src/features/portfolio/ExposurePanel.tsx`
- App state: `analysis.lookthrough`, `analysis.lookthrough_sector_exposure`, `analysis.market_overlap`, `analysis.exposure_availability`
- Adapter: `composeExposureView(...)` / `buildImportedExposureView(...)`
- Engine source: `services/quant-engine/app/services/exposure_engine.py`
- analytics source:
  - `services/quant-engine/app/analytics/risk.py` -> `build_lookthrough_exposure(...)`
  - `services/quant-engine/app/analytics/risk.py` -> `build_lookthrough_sector_exposure(...)`
  - `services/quant-engine/app/analytics/risk.py` -> `build_market_overlap_summary(...)`

### Historical diagnostics sections

- UI: `apps/desktop/src/features/portfolio/ExposurePanel.tsx`
- App state: diagnostics fields inside `ExposureAnalysis`
- Adapter: `composeExposureView(...)`
- Engine source: diagnostics engine responses
- accuracy rule: these sections must be available from history-aware diagnostics inputs or explicitly unavailable

### Scenario preview sections

- UI: `apps/desktop/src/features/portfolio/ExposurePanel.tsx`
- App state: `analysis.scenario_preview`
- Adapter: local scenario projection path
- Engine source: none for historical rerun; current-state approximation only
- accuracy rule: must stay clearly labeled as scenario/current-state approximation

## Current Accuracy Rules

1. Current-state exposure may render from snapshot-only inputs.
2. Historical benchmark/risk sections must be correct or unavailable.
3. `coverage_ratio` means constituent-resolution coverage, not generic current-holdings display coverage.
4. Missing benchmark holdings must render overlap values as unavailable, not `0.0`.
5. Scenario sections must remain explicitly labeled as scenario/current-state approximations.
6. If a financially meaningful formula changes, methodology text and this inventory should be updated together.

## Immediate Follow-up Targets

1. Add field-level inventory for any remaining overlap-adjacent metrics surfaced indirectly through factor tilts or scenario approximations.
2. Expand the `Sector` factor group in the Exposure panel so the sector-correlation / sector-factor list explicitly includes `XLK`, `XLI`, `XLF`, `XLE`, `XLV`, `XLP`, `XLU`, and `XLY`.
2. Tighten any remaining Exposure fields that still collapse degraded and unavailable states together.
3. Add App-level regression coverage for degraded exposure availability messaging if that becomes restore-critical.

## Current Coverage Status

- backend exposure coverage now includes deterministic real-fixture tests for `IB2026.pdf`, `FF2026.pdf`, and `ESPP2026.pdf`
- backend mocked-flow coverage now includes explicit degraded states for unresolved ETF holdings and missing benchmark holdings
- Exposure now has explicit `exposure_availability` semantics for look-through status/confidence, benchmark-overlap status/confidence, and desktop-composed historical diagnostics confidence
- desktop `ExposurePanel` coverage includes degraded messaging for partial look-through, unavailable benchmark overlap, and `n/a` rendering instead of false zero overlap

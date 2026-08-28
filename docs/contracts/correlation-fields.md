# Correlation Fields Contract

**Feature:** Portfolio Correlation & Co-movement Analysis (Epic 9)
**Last updated:** 2026-05-28

---

## Trust class preamble

All fields in this contract are **synthetic history** trust class unless noted otherwise.
- The correlation engines apply current holdings backwards over historical
  prices. The drift engine's basis is **per-request** (US-30.1 / audit F-1):
  when the snapshot carries ledger entries it is a broker-ledger replay
  measured as a cash-flow-neutral time-weighted return (US-27.8); the
  request path (positions + cash, no ledger — today's only caller) uses the
  **market-value chain of current holdings** (the synthetic convention). The
  per-window `note` field states which basis produced the number; a window
  whose chain hits an impossible (≤ −100%) daily return fails closed
  (`trust="unavailable"`, degradation note) instead of compounding it.
- No field is ever `verified`. Every nullable field returns `null` when insufficient data is available — never a fabricated zero.
- The UI must display a "Synthetic" badge wherever these fields are shown.

---

## US-9.1 — Indexed return time-series chart

Data source: `DriftResult.daily_series` (from `POST /api/engines/drift/run`)

### `DriftDailyPoint`

**Backend schema:** `services/quant-engine/app/schemas/drift.py`
**Frontend type:** `apps/desktop/src/features/portfolio/types.ts` — `DriftDailyPoint`
**UI component:** `IndexedReturnChart` inside `DriftBenchmarkPanel`

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable | Notes |
|---|---|---|---|---|---|---|
| `date` | `str` | `string` | X-axis date | synthetic | No | ISO 8601 (YYYY-MM-DD) |
| `portfolio_indexed` | `float \| None` | `number \| null` | Portfolio (rebased) | synthetic | Yes | **Indexed on the same chain as the window cards** (US-30.1 AC4, one `_compound_chain` code path): cash-flow-neutral TWR on the ledger path (US-27.8 — deposits are not chart moves); market-value chain of current holdings on the no-ledger path. A degraded chain withholds the whole line (nulls). See methodology §Indexed Return Series. Rebased to 100 at sub-window start in `IndexedReturnChart` via `sliceAndRebase()`. |
| `benchmark_indexed` | `float \| None` | `number \| null` | Benchmark (rebased) | synthetic | Yes | Same index basis as `portfolio_indexed`. Rebased to 100 at sub-window start. |

### `DriftResult` (envelope)

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable | Notes |
|---|---|---|---|---|---|---|
| `windows` | `list[DriftWindow]` | `DriftWindow[]` | Window selector | synthetic | No | One entry per window (1m, 3m, 6m, 12m, since-import). The **since-import** window anchors at the statement-period START (US-30.3 / F-5 — not the import timestamp, which left it always `unavailable`), fallback `imported_at`. The panel **self-fetches** drift from the workspace snapshot on mount and on benchmark change (US-30.3 / F-4), so the chart renders without dropdown interaction. Each window's `note` states the basis that produced it (US-30.1): `"Synthetic: current holdings × historical prices (market-value chain)"` on the no-ledger path, the US-27.8 ledger-replay wording when a ledger drove it, or the ≤ −100% degradation note on a failed-closed window. The panel TrustBadge tooltip repeats the engine note verbatim. |
| `benchmark_symbol` | `str` | `string` | Benchmark label | — | No | E.g. `"SPY"` |
| `daily_series` | `list[DriftDailyPoint]` | `DriftDailyPoint[]` | Chart data | synthetic | No (empty when unavailable) | |
| `availability` | `Literal["available", "partial", "unavailable"]` | `'available' \| 'partial' \| 'unavailable'` | Availability state | synthetic | No | |
| `fx_fallback_currencies` | `list[str]` (default `[]`) | `string[] \| undefined` | Drift panel helper note when non-empty | — | No (empty when none) | US-27.8 (audit F9): currencies that required base conversion with no FX rate — values carried unconverted, never a silent 1:1 claim. See methodology §FX Conversion Fallback Disclosure. |
| `fx_static_rate_currencies` | `list[str]` (default `[]`) | `string[] \| undefined` | Drift panel helper note when non-empty | — | No (empty when none) | US-30.2 (audit F-6): currencies converted at the statement's implied period-end rate (US-28.1 `statement_totals.fx_rates`, supplied via `DriftEngineRequest.fx_rates`) — a STATIC rate across the window; levels are broker truth as of period end, FX return dynamics absent. Disclosed separately from the fallback tier; a currency appears in exactly one tier. |
| `statement_anchored_symbols` | `list[str]` (default `[]`) | `string[] \| undefined` | Drift panel helper note when non-empty | — | No (empty when none) | US-30.2 (audit F-3): held symbols valued FLAT at the statement close for the whole window (zero in-window price coverage) — zero return contribution, dampens returns/volatility. |

### `DriftWindow` (one entry per drift window)

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable | Notes |
|---|---|---|---|---|---|---|
| `label` | `str` | `string` | Window selector label | — | No | `"1M"`, `"3M"`, `"6M"`, `"12M"`, `"Since Import"` |
| `start_date` | `str \| None` (default `None`) | `string \| null` | — | synthetic | Yes | ISO 8601; window lower bound |
| `end_date` | `str \| None` (default `None`) | `string \| null` | — | synthetic | Yes | ISO 8601; window upper bound |
| `portfolio_return_pct` | `float \| None` (default `None`) | `number \| null` | Portfolio return cell | synthetic | Yes | Null on an unavailable / failed-closed window |
| `benchmark_return_pct` | `float \| None` (default `None`) | `number \| null` | Benchmark return cell | synthetic | Yes | Null on an unavailable / failed-closed window |
| `spread_pct` | `float \| None` (default `None`) | `number \| null` | Spread cell | synthetic | Yes | `portfolio_return_pct − benchmark_return_pct` |
| `trust` | `Literal["synthetic", "unavailable"]` (default `"unavailable"`) | `'synthetic' \| 'unavailable'` | Per-window TrustBadge | — | No | `"unavailable"` when the window's chain could not be built or hit a ≤ −100% daily return |
| `note` | `str \| None` (default `None`) | `string \| null` | TrustBadge tooltip (verbatim) | — | Yes | States the basis that produced the window (US-30.1) or the degradation reason |

### Rebasing contract

`IndexedReturnChart` rebases indexed series to 100 at the first non-null value within the selected sub-window:

```
rebased_t = (indexed_t / indexed_start) × 100
```

where `indexed_start` is `portfolio_indexed` / `benchmark_indexed` at the first non-null date within the window. This computation is frontend-only and must never be performed in backend schemas.

---

## US-9.2 — Rolling correlation & beta chart

Data source: `ExposureAnalysis.rolling_risk` (from `POST /api/engines/exposure/run`)

### `RollingRiskPoint` (correlation/beta columns only)

**Backend schema:** `services/quant-engine/app/schemas/reconciliation.py` — `RollingRiskPoint` (series assembled by `services/quant-engine/app/analytics/risk.py` — `build_rolling_risk_series`)
**Frontend type:** `apps/desktop/src/features/portfolio/types.ts` — `RollingRiskPoint`
**UI component:** `RollingCorrelationChart`

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable | Notes |
|---|---|---|---|---|---|---|
| `date` | `str` | `string` | X-axis date | synthetic | No | ISO 8601 (YYYY-MM-DD) |
| `correlation_20d` | `float \| None` | `number \| null` | ρ (20d) | synthetic | Yes | Pearson ρ vs primary benchmark over trailing 20 trading days. Null when window not yet filled. |
| `correlation_60d` | `float \| None` | `number \| null` | ρ (60d) | synthetic | Yes | Pearson ρ over trailing 60 trading days. |
| `correlation_252d` | `float \| None` | `number \| null` | ρ (252d) | synthetic | Yes | Pearson ρ over trailing 252 trading days. |
| `beta_20d` | `float \| None` | `number \| null` | β (20d) | synthetic | Yes | Beta vs primary benchmark over trailing 20 trading days. Null when window < 20. |
| `beta_60d` | `float \| None` | `number \| null` | β (60d) | synthetic | Yes | Beta over trailing 60 trading days. |
| `beta_252d` | `float \| None` | `number \| null` | β (252d) | synthetic | Yes | Beta over trailing 252 trading days. |

### Chart axes contract

- **Left axis (correlation):** domain `[-1, 1]`; reference line at y=0.
- **Right axis (beta):** domain auto; reference line at y=1.
- `connectNulls={false}` — null gaps must render as visible breaks, not interpolated zero.
- Window selector maps to the appropriate column suffix: `20d`, `60d`, `252d`.

---

## US-9.3 — Multi-benchmark correlation matrix

Data source: `POST /api/engines/correlation/multi`

**Backend schema:** `services/quant-engine/app/schemas/correlation.py`
**Frontend type:** `apps/desktop/src/features/portfolio/types.ts` — `MultiBenchmarkCorrelationResult`
**UI component:** `BenchmarkCorrelationTable`

### `MultiBenchmarkCorrelationRequest`

| Field | Backend type (Python) | TS type | Description |
|---|---|---|---|
| `snapshot` | `ImportedPortfolioSnapshot` | `ImportedSnapshot` | Full imported portfolio snapshot |
| `lookback_days` | `int` (default 252, min 1) | `number` | Lookback window in trading days. Default: `252`. |

### `MultiBenchmarkCorrelationResult`

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable | Notes |
|---|---|---|---|---|---|---|
| `benchmarks` | `list[BenchmarkStats]` | `BenchmarkStats[]` | Table rows | synthetic | No (empty when unavailable) | Sorted by `\|correlation\|` descending; unavailable rows last. |
| `lookback_days` | `int` | `number` | Lookback (header) | — | No | Echoed from request. Displayed as "Nd lookback". |
| `coverage` | `SyntheticHistoryCoverage \| None` | `SyntheticHistoryCoverage \| null \| undefined` | `helper` note when the window was truncated or holdings excluded | synthetic | Yes | US-27.7 coverage disclosure — see `financial-methodology.md` §Synthetic History Coverage Rule |

### `BenchmarkStats` (one row per benchmark)

| Field | Backend type (Python) | TS type | UI label (column) | Trust class | Nullable | Notes |
|---|---|---|---|---|---|---|
| `symbol` | `str` | `string` | — (secondary label) | — | No | One of `SPY`, `QQQ`, `GLD`, `IEF`, `VT` |
| `label` | `str` | `string` | Benchmark column | — | No | Human label: "S&P 500", "Nasdaq-100", "Gold", "US 7-10yr Bonds", "Global Equity" |
| `correlation` | `float \| None` | `number \| null` | ρ (Correlation) | synthetic | Yes | Pearson ρ ∈ [-1, 1]. Null when < 20 overlapping trading days. |
| `beta` | `float \| None` | `number \| null` | β (Beta) | synthetic | Yes | cov(r_p, r_b) / var(r_b). Null when < 20 overlapping days or var=0. |
| `r_squared` | `float \| None` | `number \| null` | R² | synthetic | Yes | ρ². Null when ρ is null. |
| `trust` | `Literal["synthetic", "unavailable"]` | `'synthetic' \| 'unavailable'` | Per-row dim (no column) | — | No | `"unavailable"` when all three metrics are null. **UI rendering:** trust is shown as row opacity (`0.55` for `unavailable`, `1` for `synthetic`) plus a single table-header `Synthetic` badge — *not* as a dedicated table column. There are 4 columns: Benchmark, ρ, β, R². |

### Unavailable state rules

| Condition | `BenchmarkStats.trust` | `correlation` | `beta` | `r_squared` | Notes |
|---|---|---|---|---|---|
| No positions in snapshot | `"unavailable"` | `null` | `null` | `null` | Full response still has 5 rows. |
| Benchmark price history not available | `"unavailable"` | `null` | `null` | `null` | Individual benchmark row only. |
| < 20 overlapping trading-day returns | `"unavailable"` | `null` | `null` | `null` | |
| ≥ 20 overlapping returns, all data present | `"synthetic"` | non-null | non-null | non-null | Normal case. |

### Null display rule

Null metric fields must render as `"—"` in the UI. Never render as `0`, `""`, or `"N/A"`.

### Sorting contract

The backend sorts `benchmarks` by `abs(correlation)` descending before returning.
Rows where `correlation` is `null` sort last. The frontend preserves this order — no client-side re-sorting.

---

## Five hardcoded benchmarks

| Symbol | Label | Market proxy |
|---|---|---|
| SPY | S&P 500 | US Large-Cap / Broad Market |
| QQQ | Nasdaq-100 | US Large-Cap Growth / Technology |
| GLD | Gold | Commodities / Inflation Hedge |
| IEF | US 7-10yr Bonds | Intermediate US Government Bonds |
| VT | Global Equity | Total World Equity |

These symbols are defined in `BENCHMARK_UNIVERSE` in
`services/quant-engine/app/services/correlation_engine.py` and are not
configurable by the client.

## UI rendering (Epic 12 / US-12.1)

The correlation-color palette is sourced from CSS variables in
`apps/desktop/src/app/styles.css` under the `:root` block, **not** from
hex literals in component code:

| Magnitude | Token | Component reference |
|---|---|---|
| ρ ≥ 0.7  | `--color-corr-strong-positive` | `correlationColor()` in `BenchmarkCorrelationTable.tsx` |
| 0.3 ≤ ρ < 0.7 | `--color-corr-positive` | same |
| \|ρ\| < 0.3 | `--color-corr-neutral` | same |
| -0.7 < ρ ≤ -0.3 | `--color-corr-negative` | same |
| ρ ≤ -0.7 | `--color-corr-strong-negative` | same |
| `null` / unavailable | `--color-text-disabled` | same |

When changing the palette, edit the tokens in `styles.css`; do not edit the
component. The `designSystem.audit.test.ts` regression test enforces this.

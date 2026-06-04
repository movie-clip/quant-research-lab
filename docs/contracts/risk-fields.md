# Risk Fields Contract

**Feature:** Risk Analytics Tab (Epic 13)
**Last updated:** 2026-06-01

---

## Trust class preamble

All fields in this contract are **synthetic history** trust class.

- The stress engine applies *current* factor loadings to *hypothetical*
  per-factor shock vectors.
- The drawdown and distribution engines apply *current* holdings backwards
  over *historical* prices.
- No Risk-tab field is ever `verified`. Every nullable field returns `null`
  when insufficient data is available — never a fabricated zero.
- The `var_*` and `cvar_*` fields may be **negative**: this is a meaningful
  signal that the lookback window contained no loss days at the requested
  confidence. The UI must surface negative VaR muted (not red) and never
  clip to zero. See methodology §Value-at-Risk and Distribution Contract
  rule.
- The UI displays a "Synthetic" badge on each card (via the `TrustBadge`
  primitive). When trust is `unavailable`, the card renders an EmptyState
  in place of the chart / table content.

---

## US-13.1 — Stress Scenarios (`POST /api/engines/stress/run`)

Data source: `StressEngineResponse`

**Backend schema:** `services/quant-engine/app/schemas/stress.py`
**Backend analytics:** `services/quant-engine/app/analytics/risk.py` —
  `build_stress_scenarios(model)` + `STRESS_SCENARIOS` constant
**Backend service:** `services/quant-engine/app/services/stress_engine.py`
  — `run_stress_engine(request)`
**Per-row schema** (reused, NOT modified in Epic 13):
  `services/quant-engine/app/schemas/reconciliation.py` —
  `StressScenarioResult`
**Frontend types:** `apps/desktop/src/features/portfolio/types.ts` —
  `StressScenarioResult`, `StressEngineResponse`, `StressTrustLevel`
**UI component:** `apps/desktop/src/features/portfolio/StressScenariosCard.tsx`
**Methodology:** §Stress Scenarios

### Request: `StressEngineRequest`

Inherits all fields from `PortfolioEngineRequest` — no additional fields.

| Field | Backend type (Python) | TS type | Description |
|---|---|---|---|
| `benchmark_symbol` | `str` (default `"SPY"`) | `string` | Inherited |
| `positions` | `list[PortfolioPositionSnapshot]` | `Position[]` | Inherited; empty list short-circuits to `trust='unavailable'` |
| `cash_balances` | `list[PortfolioCashBalanceSnapshot]` | `CashBalance[]` | Inherited |
| `imported_at` | `datetime \| None` | `string \| null` | Inherited |
| `base_currency` | `str \| None` | `string \| null` | Inherited |

### Response: `StressEngineResponse`

| Field | Backend type (Python) | TS type | UI surface | Trust class | Nullable | Methodology ref |
|---|---|---|---|---|---|---|
| `scenarios` | `list[StressScenarioResult]` | `StressScenarioResult[]` | Vertical row list in `StressScenariosCard` | synthetic | No (always 3 rows from canonical `STRESS_SCENARIOS`) | §Stress Scenarios |
| `trust` | `Literal["synthetic", "unavailable"]` | `'synthetic' \| 'unavailable'` | `TrustBadge` in card header | — | No | §Trust, Degradation, Withholding, and Unavailability |

### `StressScenarioResult` (one entry per canonical scenario)

| Field | Backend type (Python) | TS type | UI surface | Trust class | Nullable | Notes |
|---|---|---|---|---|---|---|
| `name` | `str` | `string` | Row title (bold) | — | No | One of: `"Broad Market Selloff"`, `"Rates Down Risk-On"`, `"Inflation Reacceleration"` |
| `estimated_return_pct` | `float \| None` | `number \| null` | Right-aligned pct cell + horizontal magnitude bar | synthetic | Yes | `Σᵢ βᵢ × sᵢ × 100` per §Stress Scenarios. `null` when factor model is empty. |
| `description` | `str` | `string` | Helper text below row title | — | No | Static per scenario (canonical) |
| `status` | `Literal["ok", "unavailable"]` (default `"ok"`) | `'ok' \| 'unavailable'` | Drives null formatting | — | No | `"unavailable"` ⇔ `estimated_return_pct is None` |

### Trust state semantics

| Condition | `trust` (wrapper) | Per-row `estimated_return_pct` | Per-row `status` |
|---|---|---|---|
| No positions in request | `"unavailable"` | `null` for all 3 | `"unavailable"` for all 3 |
| Factor model fits (≥ 1 non-null `latest_loading` in `current_factor_snapshot`) | `"synthetic"` | non-null for all 3 | `"ok"` for all 3 |
| Factor model returned with empty `current_factor_snapshot` | `"unavailable"` | `null` for all 3 | `"unavailable"` for all 3 |

### Edge cases

- The scenario list always has length 3 (the canonical `STRESS_SCENARIOS`
  tuple in `analytics/risk.py`). The UI never has to handle "scenarios is
  empty".
- Front-end sorts rows by `Math.abs(estimated_return_pct ?? 0)` descending;
  null pcts sort last and render `'—'` (never `0` / `n/a` / blank).
- No window selector — stress is point-in-time.

### Example response (synthetic, populated)

```json
{
  "scenarios": [
    { "name": "Broad Market Selloff", "estimated_return_pct": -8.42, "description": "Risk-off equity drawdown led by broad market and cyclicals.", "status": "ok" },
    { "name": "Rates Down Risk-On",  "estimated_return_pct":  3.10, "description": "Falling yields supporting duration and growth assets.",      "status": "ok" },
    { "name": "Inflation Reacceleration", "estimated_return_pct": -1.55, "description": "Sticky inflation with commodity strength and duration pressure.", "status": "ok" }
  ],
  "trust": "synthetic"
}
```

### Example response (unavailable — empty portfolio or empty factor model)

```json
{
  "scenarios": [
    { "name": "Broad Market Selloff",      "estimated_return_pct": null, "description": "Risk-off equity drawdown led by broad market and cyclicals.",        "status": "unavailable" },
    { "name": "Rates Down Risk-On",        "estimated_return_pct": null, "description": "Falling yields supporting duration and growth assets.",              "status": "unavailable" },
    { "name": "Inflation Reacceleration",  "estimated_return_pct": null, "description": "Sticky inflation with commodity strength and duration pressure.",   "status": "unavailable" }
  ],
  "trust": "unavailable"
}
```

---

## US-13.2 — Drawdown Analytics (`POST /api/engines/drawdown/run`)

Data source: `DrawdownEngineResponse`

**Backend schema:** `services/quant-engine/app/schemas/drawdown.py`
**Backend analytics:** `services/quant-engine/app/analytics/drawdown.py` —
  `build_underwater_series`, `identify_drawdown_episodes`,
  `current_drawdown_pct`, `max_drawdown_pct`
**Backend service:** `services/quant-engine/app/services/drawdown_engine.py`
  — `run_drawdown_engine(request)`
**Frontend types:** `apps/desktop/src/features/portfolio/types.ts` —
  `DrawdownDailyPoint`, `DrawdownEpisode`, `DrawdownEngineResponse`,
  `DrawdownTrustLevel`, `DrawdownWindow`
**UI component:** `apps/desktop/src/features/portfolio/DrawdownAnalyticsCard.tsx`
**Methodology:** §Wealth Index and Drawdown + §Drawdown episode identification

### Request: `DrawdownEngineRequest`

Inherits from `PortfolioEngineRequest`. Adds one field:

| Field | Backend type (Python) | TS type | Description |
|---|---|---|---|
| `window_trading_days` | `Literal[252, 756, 1260] \| None` (default `None`) | `252 \| 756 \| 1260 \| null` | Lookback window. `None` = max available (engine cap: 3000 calendar days ≈ 8.2 years). |

### Response: `DrawdownEngineResponse`

| Field | Backend type (Python) | TS type | UI surface | Trust class | Nullable | Methodology ref |
|---|---|---|---|---|---|---|
| `window_trading_days` | `int \| None` | `number \| null` | Echoed for header label | — | Yes (null = max window) | — |
| `underwater_series` | `list[DrawdownDailyPoint]` | `DrawdownDailyPoint[]` | Recharts AreaChart (top half of card) | synthetic | No (empty when unavailable) | §Wealth Index and Drawdown |
| `current_drawdown_pct` | `float \| None` | `number \| null` | (Computed, not yet surfaced in v1 UI) | synthetic | Yes | `current_drawdown_pct()` helper |
| `max_drawdown_pct` | `float \| None` | `number \| null` | (Computed, not yet surfaced in v1 UI) | synthetic | Yes | `max_drawdown_pct()` helper |
| `episodes` | `list[DrawdownEpisode]` | `DrawdownEpisode[]` | Top-5 episodes table (bottom half of card) | synthetic | No (empty when unavailable) | §Drawdown episode identification |
| `trust` | `Literal["synthetic", "unavailable"]` | `'synthetic' \| 'unavailable'` | `TrustBadge` in card header | — | No | §Trust |

### `DrawdownDailyPoint`

| Field | Backend type (Python) | TS type | UI surface | Nullable | Notes |
|---|---|---|---|---|---|
| `date` | `str` | `string` | X-axis (MM/YY tick format) | No | ISO 8601 |
| `drawdown_pct` | `float \| None` | `number \| null` | Y-axis (signed percent, 0 = peak) | Yes | `((wealth_t / running_peak_t) - 1) * 100` |

### `DrawdownEpisode`

| Field | Backend type (Python) | TS type | UI surface (column) | Nullable | Notes |
|---|---|---|---|---|---|
| `peak_date` | `str` | `string` | Peak | No | ISO 8601; date immediately before the dip |
| `trough_date` | `str` | `string` | Trough | No | ISO 8601; deepest point in the episode |
| `recovery_date` | `str \| None` | `string \| null` | Recovery | Yes | `null` ⇒ still underwater; UI renders italic `"Still underwater"` |
| `magnitude_pct` | `float` | `number` | Magnitude | No | Always ≤ 0; "deepest" = most negative |
| `duration_days` | `int` | `number` | Duration | No | `trough_date − peak_date` (calendar days); 0 for single-day dips |
| `underwater_days` | `int` | `number` | Underwater | No | `(recovery_date or last_date) − peak_date` (calendar days) |
| `top_contributors` | `list[EpisodeContributor] \| None` | `EpisodeContributor[] \| null` | Drawer rows (`Symbol` / `Weight @ Peak` / `Return` / `Contribution`) | Yes | Top-N by `abs(contribution_pct)` desc; `null` when decomposition unavailable. See §Drawdown episode decomposition. (Epic 15 / US-15.1) |
| `other_contribution_pct` | `float \| None` | `number \| null` | Drawer "Other" aggregate row | Yes | Σ contribution over positions ranked N+1 and beyond; UI hides row when `\|value\| < 0.01%`. (Epic 15 / US-15.1) |
| `decomposition_residual_pct` | `float \| None` | `number \| null` | Drawer "Residual (unexplained)" row + partial-trust caption | Yes | `magnitude_pct − Σ contribution_pct_non_null`. Near-zero under `'synthetic'` trust; material under `'partial'`. UI hides row when `\|value\| ≤ 0.05%`. (Epic 15 / US-15.1) |
| `decomposition_trust` | `Literal['synthetic', 'partial', 'unavailable']` | `'synthetic' \| 'partial' \| 'unavailable'` | Drives drawer visibility (toggle disabled if `'unavailable'`) + partial-trust caption | No | Default `'unavailable'` for backward compatibility. (Epic 15 / US-15.1) |

### `EpisodeContributor`

One position's contribution to a drawdown episode (Epic 15 / US-15.1).
`contribution_pct` is signed: negative = position dragged the portfolio
down during the episode; positive = position rallied while the portfolio
overall sank.

| Field | Backend type (Python) | TS type | UI surface (drawer column) | Nullable | Notes |
|---|---|---|---|---|---|
| `symbol` | `str` | `string` | Symbol | No | The position's ticker (matches `DailyStatePosition.symbol`) |
| `weight_at_peak_pct` | `float \| None` | `number \| null` | Weight @ Peak | Yes | `(V_i(t_peak) / V_p(t_peak)) × 100`; null when `p_i(t_peak)` missing |
| `return_pct` | `float \| None` | `number \| null` | Return | Yes | `(p_i(t_trough) / p_i(t_peak) − 1) × 100`; null when either price missing |
| `contribution_pct` | `float \| None` | `number \| null` | Contribution (bold, sign-coloured) | Yes | `weight × return × 100`; null when either component null |
| `trust` | `Literal['synthetic', 'unavailable']` | `'synthetic' \| 'unavailable'` | (Drives null-cell rendering) | No | Per-row: `'synthetic'` ⇔ all three pcts non-null; `'unavailable'` when any is null |

### Decomposition trust state semantics

| Condition | `decomposition_trust` | `top_contributors` | `other_contribution_pct` | `decomposition_residual_pct` |
|---|---|---|---|---|
| Peak state missing from `daily_states` | `"unavailable"` | `[]` | `null` | `null` |
| `V_p(t_peak) == 0` | `"unavailable"` | `[]` | `null` | `null` |
| No positions yield non-null contribution | `"unavailable"` | `[]` | `null` | `null` |
| At least one position decomposable; at least one has null contribution (data gap) | `"partial"` | populated (mix of synthetic + unavailable rows) | populated when > top_n decomposable positions | non-zero (captures missing-data share) |
| Every position decomposable AND `\|residual_pct\| < 0.001` | `"synthetic"` | populated (all `trust='synthetic'`) | populated when > top_n positions | near-zero (floating-point noise only) |

### Decomposition edge cases

- **Data gaps surface as null contribution + per-row `trust='unavailable'`.**
  When `p_i(t_peak)` or `p_i(t_trough)` is missing, the position's
  `weight_at_peak_pct` / `return_pct` / `contribution_pct` are all
  `null` and the per-row `trust='unavailable'`. The engine never
  fabricates a zero contribution to fill the gap — that would mask
  the data quality issue.
- **Cash contributes 0 by construction.** Cash isn't iterated in the
  decomposition (engine walks `state.positions` only, not
  `state.cash`); with `r_cash = 0` the contribution would be 0
  anyway. Cash weight IS in the `V_p(t_peak)` denominator only
  insofar as the engine uses `total_market_value` (positions-only,
  excluding cash) — keeping numerator and denominator consistent.
- **Reconciliation invariant**:
  `|magnitude_pct − (Σ top_contributors.contribution_pct + (other_contribution_pct or 0) + decomposition_residual_pct)| < 1e-9`.
  The engine raises `ValueError` (HTTP 400 at the route boundary)
  when violated. By construction `residual_pct` is defined as the
  remainder, so violation indicates a floating-point edge case or
  implementation bug.
- **Top-N selection sort order**: backend sorts decomposable
  positions by `abs(contribution_pct)` descending; null contributors
  sort last. UI does NOT re-sort.
- **`other_contribution_pct` excludes nulls**: positions ranked N+1
  and beyond contribute to `other_contribution_pct` only if their
  `contribution_pct` is non-null. Null contributions are absorbed
  by `decomposition_residual_pct` (which is what makes residual
  material on the `'partial'` path).

### Trust state semantics

| Condition | `trust` | `underwater_series` | scalars | `episodes` |
|---|---|---|---|---|
| No positions in request | `"unavailable"` | `[]` | all `null` | `[]` |
| Market data unavailable for lookback | `"unavailable"` | `[]` | all `null` | `[]` |
| `len(underwater_series) < 20` | `"unavailable"` | `[]` | all `null` | `[]` |
| ≥ 20 daily observations | `"synthetic"` | populated | non-null | up to 5 rows (deepest first) |

### Edge cases

- **Still-underwater episode**: when the series ends below a prior peak,
  the final episode is emitted with `recovery_date=null` and
  `underwater_days = (last_date − peak_date)`. Contract rule: `null`
  recovery is distinct from "no episode" and the UI must surface it
  explicitly (renders `"Still underwater"`, not `'—'`).
- **Single-day dip**: emitted with `duration_days = 0`.
- **Top-N selection**: backend returns up to 5 episodes sorted by
  `magnitude_pct` ascending (deepest first). Frontend does a defensive
  re-sort to honour the same contract regardless of input order.

### Window selector

UI window options (decimal trading days; `null` = "Max"):

| Option | Lookback calendar-day fetch |
|---|---|
| 252d  | `ceil(252 × 1.6) + 30` = 434 calendar days |
| 756d  | `ceil(756 × 1.6) + 30` = 1240 calendar days |
| 1260d | `ceil(1260 × 1.6) + 30` = 2046 calendar days |
| Max   | `_MAX_LOOKBACK_CALENDAR_DAYS` = 3000 calendar days |

Default selected window in the UI is `1260` (≈ 5 years).

### Example response (synthetic, populated)

```json
{
  "window_trading_days": 1260,
  "underwater_series": [
    { "date": "2024-01-02", "drawdown_pct": 0.0 },
    { "date": "2024-01-03", "drawdown_pct": -0.4 },
    { "date": "2024-01-04", "drawdown_pct": -1.8 }
  ],
  "current_drawdown_pct": -1.8,
  "max_drawdown_pct": -12.4,
  "episodes": [
    { "peak_date": "2022-01-03", "trough_date": "2022-10-12", "recovery_date": "2024-01-19", "magnitude_pct": -24.5, "duration_days": 282, "underwater_days": 747 },
    { "peak_date": "2020-02-19", "trough_date": "2020-03-23", "recovery_date": "2020-08-18", "magnitude_pct": -33.9, "duration_days": 33,  "underwater_days": 180 }
  ],
  "trust": "synthetic"
}
```

### Example response (unavailable)

```json
{
  "window_trading_days": 1260,
  "underwater_series": [],
  "current_drawdown_pct": null,
  "max_drawdown_pct": null,
  "episodes": [],
  "trust": "unavailable"
}
```

### Example response (with decomposition — Epic 15)

Two episodes showing the per-position decomposition: the first with
`decomposition_trust='synthetic'` (clean — every position decomposed,
residual is floating-point noise) and the second with `'partial'`
(one position had missing price data at the trough, so the residual
is material and captures the missing-data share). Per
methodology §Drawdown episode decomposition.

```json
{
  "window_trading_days": 1260,
  "underwater_series": [
    { "date": "2024-01-02", "drawdown_pct": 0.0 },
    { "date": "2024-01-03", "drawdown_pct": -0.4 }
  ],
  "current_drawdown_pct": -0.4,
  "max_drawdown_pct": -24.5,
  "episodes": [
    {
      "peak_date": "2022-01-03",
      "trough_date": "2022-10-12",
      "recovery_date": "2024-01-19",
      "magnitude_pct": -24.5,
      "duration_days": 282,
      "underwater_days": 747,
      "top_contributors": [
        { "symbol": "TSLA", "weight_at_peak_pct": 14.2, "return_pct": -65.0, "contribution_pct": -9.23, "trust": "synthetic" },
        { "symbol": "NVDA", "weight_at_peak_pct": 8.6,  "return_pct": -50.3, "contribution_pct": -4.33, "trust": "synthetic" },
        { "symbol": "AAPL", "weight_at_peak_pct": 12.0, "return_pct": -27.0, "contribution_pct": -3.24, "trust": "synthetic" },
        { "symbol": "MSFT", "weight_at_peak_pct": 10.5, "return_pct": -28.0, "contribution_pct": -2.94, "trust": "synthetic" },
        { "symbol": "GOOGL","weight_at_peak_pct": 6.8,  "return_pct": -39.0, "contribution_pct": -2.65, "trust": "synthetic" }
      ],
      "other_contribution_pct": -2.10,
      "decomposition_residual_pct": 0.0,
      "decomposition_trust": "synthetic"
    },
    {
      "peak_date": "2023-07-31",
      "trough_date": "2023-10-27",
      "recovery_date": "2023-12-14",
      "magnitude_pct": -10.0,
      "duration_days": 88,
      "underwater_days": 136,
      "top_contributors": [
        { "symbol": "AAPL",  "weight_at_peak_pct": 12.5, "return_pct": -16.0, "contribution_pct": -2.00, "trust": "synthetic" },
        { "symbol": "MSFT",  "weight_at_peak_pct": 10.8, "return_pct": -12.0, "contribution_pct": -1.30, "trust": "synthetic" },
        { "symbol": "ESPP_X","weight_at_peak_pct": null, "return_pct": null,  "contribution_pct": null,  "trust": "unavailable" }
      ],
      "other_contribution_pct": -1.20,
      "decomposition_residual_pct": -5.50,
      "decomposition_trust": "partial"
    }
  ],
  "trust": "synthetic"
}
```

In the second episode, `decomposition_residual_pct: -5.50` captures
the contribution that ESPP_X *would have* made if its prices were
available — the UI surfaces this via a "Partial: -5.5% unexplained
(some positions missing price history)." caption above the Contributors
drawer and a "Residual (unexplained)" row in the table.

---

## US-13.3 — VaR & Distribution (`POST /api/engines/distribution/run`)

Data source: `DistributionEngineResponse`

**Backend schema:** `services/quant-engine/app/schemas/distribution.py`
**Backend analytics:** `services/quant-engine/app/analytics/distribution.py` —
  `compute_percentiles`, `compute_var`, `compute_cvar`,
  `compute_distribution_shape`, `compute_histogram` (pure Python; no numpy /
  scipy)
**Backend service:** `services/quant-engine/app/services/distribution_engine.py`
  — `run_distribution_engine(request)`. Enforces `CVaR_95 ≥ VaR_95`
  coherence invariant and raises on violation per methodology Contract rule.
**Frontend types:** `apps/desktop/src/features/portfolio/types.ts` —
  `DistributionEngineResponse`, `DistributionWindow`, `HistogramBin`,
  `DistributionTrustLevel`
**UI component:** `apps/desktop/src/features/portfolio/VarDistributionCard.tsx`
**Methodology:** §Value-at-Risk and Distribution

### Request: `DistributionEngineRequest`

Inherits from `PortfolioEngineRequest`. Adds one field:

| Field | Backend type (Python) | TS type | Description |
|---|---|---|---|
| `window_trading_days` | `Literal[60, 252, 504]` (default `252`) | `60 \| 252 \| 504` | Lookback window. No "Max" — VaR is interpretable only relative to a fixed lookback. |

### Response: `DistributionEngineResponse`

All percent fields are in percent units (i.e. already multiplied by 100).
`var_*` and `cvar_*` are sign-flipped: a positive number is a loss; a
negative number means the window had no loss days at that confidence.

| Field | Backend type (Python) | TS type | UI surface | Trust class | Nullable | Methodology ref |
|---|---|---|---|---|---|---|
| `window_trading_days` | `int` | `number` | Header meta ("Window: Nd") | — | No | — |
| `return_count` | `int` | `number` | Header meta ("N = N obs") | — | No | Number of daily returns actually computed |
| `var_95` | `float \| None` | `number \| null` | Tail Risk row (red if positive) | synthetic | Yes | §Value-at-Risk and Distribution |
| `var_99` | `float \| None` | `number \| null` | Tail Risk row | synthetic | Yes | §Value-at-Risk and Distribution |
| `cvar_95` | `float \| None` | `number \| null` | Tail Risk row | synthetic | Yes | §Value-at-Risk and Distribution; invariant `cvar_95 ≥ var_95` |
| `percentile_5` | `float \| None` | `number \| null` | Percentiles row | synthetic | Yes | NIST linear interpolation |
| `percentile_10` | `float \| None` | `number \| null` | Percentiles row | synthetic | Yes | NIST linear interpolation |
| `percentile_50` | `float \| None` | `number \| null` | Percentiles row (median) | synthetic | Yes | NIST linear interpolation |
| `percentile_90` | `float \| None` | `number \| null` | Percentiles row | synthetic | Yes | NIST linear interpolation |
| `percentile_95` | `float \| None` | `number \| null` | Percentiles row | synthetic | Yes | NIST linear interpolation |
| `mean_pct` | `float \| None` | `number \| null` | Distribution shape row; also Mean reference line on histogram | synthetic | Yes | `mean(r) × 100` |
| `std_pct` | `float \| None` | `number \| null` | Distribution shape row | synthetic | Yes | Population std × 100 |
| `skewness` | `float \| None` | `number \| null` | Distribution shape row (no `%` suffix) | synthetic | Yes | Fisher-Pearson `m3 / m2^(3/2)`. `null` when std=0. |
| `kurtosis_excess` | `float \| None` | `number \| null` | Distribution shape row (no `%` suffix) | synthetic | Yes | Excess kurtosis `m4 / m2² − 3` (Fisher). `null` when std=0. |
| `histogram_bins` | `list[HistogramBin]` | `HistogramBin[]` | Recharts BarChart (top half of card) | synthetic | No (empty when unavailable) | 30 bins, range = `[min(r), max(r)]` |
| `trust` | `Literal["synthetic", "unavailable"]` | `'synthetic' \| 'unavailable'` | `TrustBadge` in card header | — | No | §Trust |

### `HistogramBin`

| Field | Backend type (Python) | TS type | UI surface | Nullable | Notes |
|---|---|---|---|---|---|
| `center` | `float` | `number` | Bar X-axis label (formatted as `±X.X%` — UI multiplies by 100) | No | DECIMAL bin midpoint, NOT percent. |
| `count` | `int` | `number` | Bar Y-axis value (integer days) | No | Number of daily returns in this bucket. |

### Trust state semantics

| Condition | `trust` | `return_count` | scalars | `histogram_bins` |
|---|---|---|---|---|
| No positions in request | `"unavailable"` | `0` | all `null` | `[]` |
| Market data unavailable for lookback | `"unavailable"` | `0` | all `null` | `[]` |
| `len(daily_returns) < 20` | `"unavailable"` | `0` | all `null` | `[]` |
| ≥ 20 daily returns | `"synthetic"` | `>= 20` | non-null (except std=0 edge case below) | 30 bins (sum of counts = `return_count`) |
| Constant series (`std = 0`) | `"synthetic"` | `>= 20` | `mean_pct`, `std_pct` non-null; `skewness`, `kurtosis_excess` `null` | populated |

### Edge cases

- **Negative VaR**: when the lookback window contains no loss days at the
  requested confidence, `compute_var` returns a NEGATIVE number ("the tail
  day was still positive"). Methodology Contract rule: never clip to zero.
  UI styles the cell muted (not red) so the researcher reads it as "no
  real tail loss in this window".
- **CVaR null when tail too small**: `compute_cvar` returns `null` when
  the tail `{r ≤ quantile(r, 1−α)}` contains fewer than 2 samples (mean
  of a single sample is degenerate).
- **CVaR ≥ VaR invariant**: the engine raises (HTTP 400 at the route
  boundary) rather than emit inconsistent data. Tolerated floating-point
  noise: 1e-9.
- **Constant series std=0**: `skewness` and `kurtosis_excess` return
  `null` (mathematically undefined); `mean_pct` and `std_pct` still
  computed.
- **Window options**: 60 / 252 / 504 only. No "Max" — VaR is interpretable
  only relative to a fixed lookback.

### Null display rule

Null scalar fields render as `"—"` in the UI. Never as `0`, `""`, `"N/A"`.
Skew and Kurtosis (excess) render without the `%` suffix (they are
unitless). All other scalar cells render `${pct.toFixed(2)}%`.

### Example response (synthetic, populated)

```json
{
  "window_trading_days": 252,
  "return_count": 247,
  "var_95": 2.34,
  "var_99": 4.51,
  "cvar_95": 3.12,
  "percentile_5": -1.84,
  "percentile_10": -1.21,
  "percentile_50": 0.08,
  "percentile_90": 1.42,
  "percentile_95": 1.91,
  "mean_pct": 0.04,
  "std_pct": 0.92,
  "skewness": -0.31,
  "kurtosis_excess": 2.84,
  "histogram_bins": [
    { "center": -0.025, "count": 3 },
    { "center": -0.020, "count": 7 },
    { "center": 0.000,  "count": 142 },
    { "center": 0.020,  "count": 4 }
  ],
  "trust": "synthetic"
}
```

### Example response (unavailable)

```json
{
  "window_trading_days": 252,
  "return_count": 0,
  "var_95": null,
  "var_99": null,
  "cvar_95": null,
  "percentile_5": null,
  "percentile_10": null,
  "percentile_50": null,
  "percentile_90": null,
  "percentile_95": null,
  "mean_pct": null,
  "std_pct": null,
  "skewness": null,
  "kurtosis_excess": null,
  "histogram_bins": [],
  "trust": "unavailable"
}
```

---

## UI rendering (Epic 12 design system)

All three Risk-tab cards use the design-system primitives from
`apps/desktop/src/app/primitives/`:

- `CardShell` — outer wrapper with `role="region"` + `aria-labelledby`
- `TrustBadge` — `type="synthetic" \| "unavailable"`
- `WindowSelector` — used by Drawdown + VaR cards (Stress is point-in-time)
- `ChartShell` + `chartDefaults` — used for Drawdown's AreaChart and
  VaR's BarChart (both with descriptive `ariaLabel`)
- `EmptyState`, `LoadingState`, `ErrorState` — fail-closed state primitives

The contract enforced by `apps/desktop/src/test/designSystem.audit.test.ts`
(no hex, no px in inline styles, single source for the `attribution-trust-badge`
className) applies equally to the Risk tab. See
`docs/contracts/ui-design-system.md` for the full design-system contract.

---

## Academic precedent

All formulas trace to the citations recorded in
`docs/finance/financial-methodology.md`:

- **Stress Scenarios**: Litterman & Winkelmann (1998), Connor, Goldberg &
  Korajczyk (2010)
- **Drawdown episode identification**: Magdon-Ismail & Atiya (2004),
  Goldberg & Mahmoud (2017)
- **Historical VaR and CVaR**: Jorion (2007), Acerbi & Tasche (2002),
  Embrechts, McNeil & Frey (2015)

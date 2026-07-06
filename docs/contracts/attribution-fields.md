# Attribution Fields Contract

**Feature:** Factor Return Attribution (Epic 11)
**Backend schema:** `services/quant-engine/app/schemas/attribution.py`
**Frontend type:** `apps/desktop/src/features/portfolio/types.ts` — `FactorAttributionResponse`
**Route:** `POST /api/engines/attribution/run`
**Last updated:** 2026-05-27

---

## Trust class preamble

All fields in this contract are **synthetic history** trust class.
- The attribution engine applies current holdings backwards over historical factor proxy prices.
- No field is ever `verified`. Every nullable field returns `null` when insufficient data is available — never a fabricated zero.
- The residual must be labelled `unexplained` or `idiosyncratic`. It must never be labelled `alpha`.

---

## Request: `FactorAttributionRequest`

| Field | Backend type (Python) | TS type | Description |
|---|---|---|---|
| `snapshot` | `ImportedPortfolioSnapshot` | `ImportedSnapshot` | Full imported portfolio snapshot (same as diagnostics endpoint) |
| `window` | `Literal[20, 60, 252]` | `20 \| 60 \| 252` | Rolling OLS estimation window in trading days. Default: `60` |
| `benchmark_symbol` | `str` | `string` | Benchmark symbol for market data alignment. Default: `"SPY"` |

---

## Response: `FactorAttributionResponse`

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable |
|---|---|---|---|---|---|
| `attribution_status` | `Literal["available", "unavailable"]` | `'available' \| 'unavailable'` | Status | synthetic | No |
| `window` | `int` | `number` | Window (days) | synthetic | No |
| `cumulative_series` | `list[AttributionSeriesEntry]` | `AttributionSeriesEntry[]` | — (chart data) | synthetic | No (empty when unavailable) |
| `period_attribution` | `list[FactorPeriodRow]` | `FactorPeriodRow[]` | Period attribution table | synthetic | No (empty when unavailable) |
| `total_portfolio_return_pct` | `float \| None` | `number \| null` | Total Portfolio Return % | synthetic | Yes |
| `total_unexplained_pct` | `float \| None` | `number \| null` | Unexplained / idiosyncratic % | synthetic | Yes |
| `methodology_note` | `str` | `string` | Methodology footnote | — | No |
| `coverage` | `SyntheticHistoryCoverage \| None` | `SyntheticHistoryCoverage \| null \| undefined` | `helper` note when the window was truncated or holdings excluded | synthetic | Yes | US-27.7 coverage disclosure — see `financial-methodology.md` §Synthetic History Coverage Rule |

### `AttributionSeriesEntry` (one entry per trading date in the cumulative series)

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable |
|---|---|---|---|---|---|
| `date` | `str` | `string` | Date (YYYY-MM-DD) | synthetic | No |
| `contributions` | `list[FactorContributionPoint]` | `FactorContributionPoint[]` | Per-factor cumulative contribution | synthetic | No |
| `cumul_unexplained` | `float \| None` | `number \| null` | Cumulative unexplained (decimal) | synthetic | Yes |
| `cumul_portfolio_return` | `float \| None` | `number \| null` | Cumulative portfolio return (decimal) | synthetic | Yes |

### `FactorContributionPoint` (one per active factor per series entry)

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable |
|---|---|---|---|---|---|
| `factor_key` | `str` | `string` | Factor key (e.g. `"market"`, `"growth"`) | — | No |
| `cumul_contribution` | `float \| None` | `number \| null` | Cumulative contribution (decimal, ×100 for %) | synthetic | Yes |

### `FactorPeriodRow` (one per active factor in the period attribution table)

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable |
|---|---|---|---|---|---|
| `factor_key` | `str` | `string` | Factor key | — | No |
| `factor_label` | `str` | `string` | Factor display name (e.g. `"Market"`) | — | No |
| `avg_beta` | `float \| None` | `number \| null` | Avg β | synthetic | Yes |
| `factor_return_pct` | `float \| None` | `number \| null` | Factor Return % (Σ f*_k(t) × 100) | synthetic | Yes |
| `contribution_pct` | `float \| None` | `number \| null` | Contribution % (Σ β̂_k × f*_k(t) × 100) | synthetic | Yes |

---

## Reconciliation identity (contract rule)

For every attributed date:

```
Σ_k contribution_k(t) [decimal] + residual(t) [decimal] = r_p(t) [decimal]
```

Equivalently at the period level:

```
Σ_k contribution_pct + total_unexplained_pct = total_portfolio_return_pct
```

The backend enforces this to floating-point precision (tolerance 1e-9). A violation causes HTTP 422. The frontend should not attempt independent reconciliation.

---

## Unavailable state rules

| Condition | `attribution_status` | `cumulative_series` | `period_attribution` | Numeric fields |
|---|---|---|---|---|
| No ledger / position date information in snapshot | `"unavailable"` | `[]` | `[]` | `null` |
| Market data not available for the requested date range | `"unavailable"` | `[]` | `[]` | `null` |
| Fewer than `min_observations` trading days of common history | `"unavailable"` | `[]` | `[]` | `null` |
| Sufficient history | `"available"` | populated | populated | non-null |

`min_observations` per window: 20d → 25, 60d → 75, 252d → 275.

---

## Field naming prohibition

The following field names are **prohibited** in the schema and any future extension:

- `alpha_pct`
- `cumul_alpha`
- `idiosyncratic_alpha`
- Any field name containing the substring `"alpha"` in the context of the residual

The residual must be labelled `unexplained_pct` or `idiosyncratic_pct`.

---

## Arithmetic methodology note

All period sums are **arithmetic** (sum of daily values), not compounded.
The response always includes `methodology_note` confirming this.
The UI must display the word "arithmetic" or "(not compounded)" somewhere visible on the card — tooltip, footnote, or label suffix.

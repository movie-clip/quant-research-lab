# Currency Risk Fields Contract

**Feature:** Currency Risk Contribution (Epic 26 / US-26.2)
**Last updated:** 2026-08-27

Field inventory for `services/quant-engine/app/schemas/currency_risk.py`
(`CurrencyRiskRequest`, `CurrencyRiskResult`, `CurrencyLegContribution`).
Formulas live in `docs/finance/financial-methodology.md` §Currency Risk
Contribution; the evidence behind them is in
`docs/finance/research/currency-risk-contribution-brief.md`.

---

## Trust class preamble

All result fields are **synthetic history** trust class: the engine applies
current holdings over historical prices and the statement's implied FX rates —
it is not a broker-truth or snapshot-analytics surface.

- `trust` is `Literal["synthetic", "unavailable"]` — **never `verified`**. It is
  `"unavailable"` on a fail-closed payload: fewer than `MIN_DAILY_OBSERVATIONS`
  (20) paired price+FX days, or `Var(r_p) = 0`.
- Every nullable share returns `null` on a fail-closed run — never a fabricated
  `0` and never a clamped value. A share **may legitimately be negative**: a
  currency leg moving against the local leg genuinely reduces portfolio
  variance, and clamping would fabricate a floor the data does not support.
- The three component-covariance shares (`local_variance_share`,
  `currency_variance_share`, `interaction_variance_share`) sum to **exactly
  1.0** by construction when present
  (`Var(r_p) = Cov(L, r_p) + Cov(F, r_p) + Cov(X, r_p)`).
- The card carries a **"Synthetic"** Trust badge (unlike the US-26.1 Currency
  Exposure composition card, which is snapshot analytics and carries none).

---

## Request — `POST /engines/currency-risk/run`

**Backend schema:** `services/quant-engine/app/schemas/currency_risk.py` — `CurrencyRiskRequest`
**Frontend type:** inline request body `{ snapshot, window }` in `apps/desktop/src/features/portfolio/portfolioAnalysisAdapter.ts` — `runCurrencyRiskEngine`
**UI component:** `CurrencyRiskCard` (Exposure tab)

### `CurrencyRiskRequest`

| Field | Backend type (Python) | TS type | Nullable | Notes |
|---|---|---|---|---|
| `snapshot` | `ImportedPortfolioSnapshot` | `ImportedSnapshot` | No | Snapshot-wrapped, like the sibling Exposure engines (attribution, correlation) — **not** the flat `PortfolioEngineRequest` shape. Base-currency weights need the statement's own implied `fx_rates`, which only a real snapshot carries. |
| `window` | `CurrencyRiskWindow` = `Literal[60, 252]` (default `60`) | `60 \| 252` (adapter arg) | No | Trailing trading-day window for the covariance estimate. Card offers 60d / 252d. |

---

## Response

Data source: `POST /engines/currency-risk/run` → `CurrencyRiskResult`

**Backend schema:** `services/quant-engine/app/schemas/currency_risk.py`
**Frontend type:** `apps/desktop/src/features/portfolio/types.ts` — `CurrencyRiskResult`, `CurrencyLegContribution`
**UI component:** `CurrencyRiskCard`

### `CurrencyRiskResult`

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable | Notes |
|---|---|---|---|---|---|---|
| `trust` | `Literal["synthetic", "unavailable"]` | `'synthetic' \| 'unavailable'` | Trust badge | — | No | Never `verified`. `"unavailable"` on a fail-closed payload (< 20 paired obs, or `Var(r_p) = 0`) — every share then null. |
| `window_days` | `int` | `number` | Window label | synthetic | No | Echo of the requested window (60 or 252). |
| `observations` | `int` (default `0`) | `number` | — (helper text) | synthetic | No | Count of paired price+FX daily observations the estimate used. |
| `local_variance_share` | `float \| None` (default `None`) | `number \| null` | Securities share | synthetic | Yes | Component covariance `Cov(L, r_p) / Var(r_p)`. **May be negative**; never clamped. `null` on a fail-closed run. Sums with the next two to exactly 1.0 when present. |
| `currency_variance_share` | `float \| None` (default `None`) | `number \| null` | Currency share | synthetic | Yes | Component covariance `Cov(F, r_p) / Var(r_p)`. Same negativity / null rules. |
| `interaction_variance_share` | `float \| None` (default `None`) | `number \| null` | Interaction share | synthetic | Yes | Component covariance `Cov(X, r_p) / Var(r_p)`. **Reported as its own share**, not folded into the currency leg as Ankrim–Hensel conventionally does. Same negativity / null rules. |
| `local_standalone_vol_pct` | `float \| None` (default `None`) | `number \| null` | Securities standalone vol | synthetic | Yes | Standalone annualised volatility of the local (securities) leg, in percent. A different question from contribution, reported alongside so the two are not confused. |
| `currency_standalone_vol_pct` | `float \| None` (default `None`) | `number \| null` | Currency standalone vol | synthetic | Yes | Standalone annualised volatility of the currency leg, in percent. |
| `local_fx_correlation` | `float \| None` (default `None`) | `number \| null` | Securities–FX correlation | synthetic | Yes | Correlation between the local and FX daily-return legs. |
| `per_currency` | `list[CurrencyLegContribution]` (default `[]`) | `CurrencyLegContribution[]` | Per-currency rows | synthetic | No (empty when unavailable) | Per-currency breakdown of the currency-variance share. |
| `excluded_symbols` | `list[str]` (default `[]`) | `string[]` | Excluded-holdings note | synthetic | No (empty when none) | Holdings with no fund-currency price history — **excluded and named**, never assigned to the local leg at zero FX, which would silently understate currency risk (US-26.2 AC8). |
| `excluded_weight` | `float` (default `0.0`) | `number` | Excluded-holdings note | synthetic | No | Combined base-currency weight of `excluded_symbols`. |
| `note` | `str \| None` (default `None`) | `string \| null` | Trust-badge / helper text | — | Yes | Degradation or context message; `null` on a clean run. |

### `CurrencyLegContribution` (one entry per currency in `per_currency`)

| Field | Backend type (Python) | TS type | UI label | Trust class | Nullable | Notes |
|---|---|---|---|---|---|---|
| `currency` | `str` | `string` | Currency | — | No | ISO 4217 currency code of the leg. |
| `base_weight` | `float` | `number` | Weight | synthetic | No | The currency's weight in the portfolio, measured on base-currency-converted market value (same denominator convention as every other Exposure weight, US-30.5a). |
| `contribution` | `float \| None` (default `None`) | `number \| null` | Contribution | synthetic | Yes | Contribution to the **currency** variance share, in the same component-covariance units. `null` when this currency has no covered holding. |

---

## Null / unavailable display rules

- A `null` share renders as `"—"` — never `0`, `""` or `"N/A"`.
- A negative share renders **with its sign** — it is a real result, not an error.
- `trust = "unavailable"` (fail-closed): the card shows an explicit unavailable
  state, not a zeroed breakdown.
- `excluded_symbols` non-empty: the card names the excluded holdings and their
  combined `excluded_weight`; they are never silently folded into the local leg.

# Factor Drift Fields Contract

**Feature:** Factor Drift Summary card (Epic 16 / US-16.1)
**Backend schema:** _none_ — this card has no backend route or schema
**Frontend type:** `apps/desktop/src/features/portfolio/types.ts` — reuses `ExposureAnalysis` / `ExposureFactorModelResponse` (`statistical_factor_model.rolling_loadings_<window>`)
**Component:** `apps/desktop/src/features/portfolio/FactorDriftSummaryCard.tsx`
**Route:** _none_ (derived client-side from the Exposure analysis result)
**Methodology:** `docs/finance/financial-methodology.md` → §Statistical Factor Model → ### Factor Loading Drift
**Last updated:** 2026-06-04

---

## Trust class preamble

All values shown by this card are **synthetic history** trust class.
- The card consumes the rolling factor loadings the engine already computed
  (`statistical_factor_model.rolling_loadings_{20,60,252}d`). Those loadings
  apply current holdings to historical proxy prices — never verified broker
  return basis.
- The card performs **no** financial computation beyond a first difference of
  two engine-computed loadings (`drift = latest − reference`). It never fits a
  regression, orthogonalizes, or re-estimates anything.
- No value is ever `verified`. When the selected window has insufficient
  history (its trimmed loading series is empty, or every displayed factor is
  null at the reference/latest endpoints), the card fails closed with an
  EmptyState — never a fabricated zero drift.

---

## Data source (no request schema)

The card takes the Exposure tab's `result: ExposureAnalysis | null` prop and
derives the factor model via `buildExposureFactorModel(result)`. It reads:

| Source field | Type | Used for |
|---|---|---|
| `factor_registry[].key` | `string` | Matching loadings to factors; filtering to the default visible set |
| `factor_registry[].label` | `string` | Row label |
| `statistical_factor_model.rolling_loadings_<window>` | `Array<{ date: string; <factor_key>: number \| null }>` | Per-factor loading series for the selected window |
| `statistical_factor_model.windows[].observations` | `number` | Caption + EmptyState observation count |

`<window>` ∈ `{ rolling_loadings_20d, rolling_loadings_60d, rolling_loadings_252d }`,
selected by the 20d / 60d / 252d `WindowSelector` (default 60).

---

## Derived (display-only) fields

These are computed in the component; none are persisted or returned by any API.

| Derived field | Definition | UI surface | Trust class | Nullable / excluded |
|---|---|---|---|---|
| `reference` | `β_k` at the first date of the trimmed window series | Row, "ref → latest" cell (left number) | synthetic | Factor excluded if null |
| `latest` | `β_k` at the last date of the trimmed window series | Row, "ref → latest" cell (right number) | synthetic | Factor excluded if null |
| `delta` (drift) | `latest − reference`, 2-dp, explicit sign (`+0.42` / `−0.18`) | Row, signed delta cell + divergent magnitude bar | synthetic | Factor excluded if `reference` or `latest` null |
| rank order | factors sorted by `|delta|` desc, ties by label asc | Row order | synthetic | — |
| bar length | `|delta| / max(|delta|)` of the visible set | Divergent bar width (right = positive, left = negative) | synthetic | 0 when `max = 0` |
| direction marker | `▲` (>0) / `▼` (<0) / `•` (=0) | Prefix on the delta cell (non-color encoder) | synthetic | — |
| coverage caption | `Latest vs start of window · {N} obs · {start} → {end}` | Caption above rows | synthetic | — |

### Visible factor set

The card shows the same default factor set as the Dashboard trend chart
(`market`, `growth`, `value`, `small_cap`, `technology`, `financials`),
intersected with the keys present in `factor_registry`. No group filter in v1.

---

## Trust / fail-closed rendering rules

| Condition | Render |
|---|---|
| No `factor_registry` / no visible factors | Card returns `null` (absent, like the Dashboard trend chart) |
| Selected window series empty after leading-null trimming | EmptyState: `"Not enough history for {window}d factor drift."` |
| All visible factors null at reference/latest endpoints | Same EmptyState (no rankable rows) |
| ≥ 1 rankable factor | Ranked divergent-bar rows + `Synthetic` `TrustBadge` |

Direction is encoded by **both** color (`--color-value-positive` /
`--color-value-negative`) *and* side-of-baseline *and* the signed numeric value +
arrow — so the signal survives for color-blind users (per the Epic 12 a11y
baseline). Per-factor color dots use the factor-palette tokens
(`--color-factor-*`, with `--color-factor-default` fallback).

---

## Example (illustrative, 60d window)

Given `rolling_loadings_60d` with a reference row (`2025-01-02`) and latest row
(`2025-04-01`):

| Factor | reference | latest | drift | rendered |
|---|---|---|---|---|
| Growth | 0.40 | 1.30 | +0.90 | `▲ +0.90`, bar right |
| Market | 1.00 | 1.50 | +0.50 | `▲ +0.50`, bar right |
| Value | 0.60 | 0.10 | −0.50 | `▼ −0.50`, bar left |
| Financials | 0.20 | (null) | — | excluded (latest null) |

Rows ranked Growth, Market, Value by `|drift|`. Financials is excluded, not
shown as 0.

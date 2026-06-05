# Intra-Correlation Fields Contract

**Feature:** Intra-Portfolio Correlation heatmap (Epic 17 / US-17.1)
**Backend schema:** `services/quant-engine/app/schemas/intra_correlation.py`
**Frontend type:** `apps/desktop/src/features/portfolio/types.ts` — `IntraCorrelationResult`
**Route:** `POST /api/engines/correlation/intra`
**Component:** `apps/desktop/src/features/portfolio/IntraCorrelationHeatmap.tsx`
**Methodology:** `docs/finance/financial-methodology.md` → §Intra-Portfolio Correlation
**Last updated:** 2026-06-05

---

## Trust class preamble

All fields are **synthetic history** trust class.
- Each holding's daily return series is the simple price return of its symbol
  over the window (current holdings applied to historical prices), identical in
  construction to `correlation_engine.py`.
- No field is ever `verified`.
- A matrix cell is `null` when the pair has fewer than 20 overlapping daily
  returns or a zero-variance series — **never a fabricated 0**.
- Cash and non-priceable instruments never enter the matrix; the priceable
  universe is the contract surface.

---

## Request: `IntraCorrelationRequest`

| Field | Backend type (Python) | TS type | Description |
|---|---|---|---|
| `snapshot` | `ImportedPortfolioSnapshot` | `ImportedSnapshot` | Full imported portfolio snapshot |
| `lookback_days` | `int` (≥1, default 60) | `number` | Lookback window in trading days (UI uses 20/60/252) |
| `max_holdings` | `int` (≥2, default 15) | _n/a_ | Top-N holdings (by weight) to include in the matrix for legibility |

---

## Response: `IntraCorrelationResult`

| Field | Backend type (Python) | TS type | UI surface | Trust | Nullable |
|---|---|---|---|---|---|
| `symbols` | `list[str]` | `string[]` | Heatmap row/column labels (weight-desc order) | synthetic | No (empty when unavailable) |
| `matrix` | `list[list[float \| None]]` | `Array<Array<number \| null>>` | Heatmap cells | synthetic | Cells nullable; diagonal always 1.0 |
| `average_pairwise_correlation` | `float \| None` | `number \| null` | Summary "Avg pairwise ρ" | synthetic | Yes |
| `most_correlated_pair` | `PairStat \| None` | `IntraCorrelationPair \| null` | Summary "Most correlated" | synthetic | Yes |
| `least_correlated_pair` | `PairStat \| None` | `IntraCorrelationPair \| null` | Summary "Least correlated" | synthetic | Yes |
| `diversification_ratio` | `float \| None` | `number \| null` | Summary "Diversification Ratio" (2-dp) | synthetic | Yes (US-17.2) |
| `effective_number_of_bets` | `float \| None` | `number \| null` | Summary "Effective number of bets" (1-dp) | synthetic | Yes (US-17.2) |
| `excluded_symbols` | `list[str]` | `string[]` | Excluded-holdings caption | synthetic | No (may be empty) |
| `lookback_days` | `int` | `number` | (window echo) | — | No |
| `trust` | `Literal['synthetic','unavailable']` | `'synthetic' \| 'unavailable'` | TrustBadge / EmptyState switch | — | No |

### `PairStat` / `IntraCorrelationPair`

| Field | Backend type | TS type | UI surface | Nullable |
|---|---|---|---|---|
| `symbol_a` | `str` | `string` | Summary pair callout | No |
| `symbol_b` | `str` | `string` | Summary pair callout | No |
| `correlation` | `float` | `number` | Summary pair callout (ρ) | No |

---

## Trust / fail-closed rendering rules

| Condition | Engine | UI |
|---|---|---|
| ≥ 2 priceable holdings with sufficient history | `trust='synthetic'`, matrix populated | Heatmap + summary + Synthetic badge |
| < 2 priceable holdings with sufficient history | `trust='unavailable'`, `symbols=[]`, `matrix=[]` | EmptyState ("Not enough priceable holdings…") |
| Pair < 20 overlapping returns or zero variance | cell `= null` | "n/a" cell (neutral), never 0 |
| Diagonal (holding vs itself) | `= 1.0` | Muted "1.00" |
| Holding with no/insufficient price history | added to `excluded_symbols`, dropped from matrix | "N holdings excluded: insufficient history (…)" caption |
| Holdings beyond `max_holdings` | dropped (not in `symbols`) | not shown (legibility cap; distinct from exclusion caption) |

Color-blind safety (Epic 12 baseline): every off-diagonal cell prints the
numeric ρ **and** a sign glyph (▲▲ / ▲ / • / ▼ / ▼▼); the `--color-corr-*`
palette background is a secondary encoder, never the sole one.

---

## Example (synthetic, 3 holdings, 60d)

```json
{
  "symbols": ["AAA", "BBB", "CCC"],
  "matrix": [[1.0, 0.82, null], [0.82, 1.0, -0.10], [null, -0.10, 1.0]],
  "average_pairwise_correlation": 0.36,
  "most_correlated_pair": {"symbol_a": "AAA", "symbol_b": "BBB", "correlation": 0.82},
  "least_correlated_pair": {"symbol_a": "BBB", "symbol_b": "CCC", "correlation": -0.10},
  "excluded_symbols": [],
  "lookback_days": 60,
  "trust": "synthetic"
}
```

The `AAA·CCC` pair is `null` (insufficient overlap) and renders "n/a" — not 0.
(`diversification_ratio` / `effective_number_of_bets` omitted from the snippet for
brevity; both are present and synthetic per US-17.2.)

---

## Diversification summary (US-17.2)

- `diversification_ratio` = `Σ wᵢσᵢ / σ_p` (Choueifaty & Coignard 2008). `wᵢ` are
  current market-value weights renormalised over the selected priceable universe;
  `σᵢ` is the population stdev of each holding's daily returns; `σ_p` is the
  population stdev of the constant-weight portfolio return series `Σ wᵢrᵢ`. `null`
  when `σ_p` is 0 or fewer than 20 portfolio returns. Rendered 2-dp;
  `Unavailable` when null.
- `effective_number_of_bets` = `exp(−Σ pₖ ln pₖ)` over the normalised eigenvalues
  of the correlation matrix (Meucci 2009; numpy `eigvalsh`). `null` when < 2
  holdings, any off-diagonal cell is null (incomplete matrix), or the spectrum is
  non-positive. Rendered 1-dp; `Unavailable` when null.

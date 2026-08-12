# Research Brief — Currency Risk Contribution (Epic 26 / US-26.2)

**Status:** Complete — resolves the two open questions that blocked US-26.2
**Date:** 2026-08-11
**Supersedes:** the "stretch, not ready" subsection in
`financial-methodology.md` §Currency Exposure

Both blockers named by the PRD are now resolved:

1. **Data prerequisite — VERIFIED** (empirically, this brief, §2.4).
2. **Interaction term — RESOLVED** (empirically, §2.3.1). The prior brief's
   framing was wrong: the decomposition is an **exact identity**, not an
   approximation, and the cross term is **not** droppable.
3. **Portfolio variance decomposition — RESOLVED** (§2.3.3), as an exact
   covariance split that reuses the project's existing risk-share convention.

---

## 2.1 Problem framing

**What the researcher is asking.** "My portfolio is 21% non-USD. When it moved,
how much of that was the *securities* and how much was the *currency*?" US-26.1
answers *how much* is foreign; it says nothing about whether that exposure
actually drove returns or risk.

**Why the screen can't answer it.** Every return series in the product is
already in base currency, so the FX component is baked in and invisible. The
Exposure tab's rolling correlation/beta measure co-movement with an equity
benchmark, not with FX. Nothing decomposes a return into its security and
currency legs.

**What a good answer enables.** A decision about whether the currency exposure
is worth carrying — i.e. whether observed volatility is coming from the
investment thesis or from an unhedged side-bet on EUR/GBP. This is descriptive
only; the product recommends no hedge and no target weight (guardrail #4).

## 2.2 Financial concept & academic grounding

**Concept:** local-return / currency-return decomposition (Ankrim–Hensel
currency attribution), extended to a portfolio-level variance split.

**Signed interpretation.** For one holding, `r_local` is what the security did
in the currency it trades in; `r_fx` is what that currency did against the base
currency. Positive `r_fx` means the foreign currency appreciated, adding to the
base-currency return. At the portfolio level, a **currency variance share** of
0.30 means 30% of the portfolio's return variance is attributable to the
currency leg — including its covariance with the local leg.

**Citations** (required content for the methodology section):

- Ankrim, E.M. & Hensel, C.R. (1994). "Currency Hedging: A Test for Consistency
  and Efficiency." *Journal of Portfolio Management*, 20(2), 35–41 — the
  standard local/currency decomposition. *(Note: the existing methodology text
  misspells the title as "Curency"; fix on update.)*
- Solnik, B. (1974). "An equilibrium model of the international capital
  market." *Journal of Economic Theory*, 8(4), 500–524 — currency as a distinct
  priced exposure.
- Perold, A.F. & Schulman, E.C. (1988). "The Free Lunch in Currency Hedging."
  *Financial Analysts Journal*, 44(3), 45–50 — why the currency leg is reported
  separately from the asset leg.
- Menchero, J. & Davis, B. (2011). "Risk Contribution is Exposure times Volatility
  times Correlation." *Journal of Portfolio Management*, 37(2), 97–107 — the
  component-contribution identity this brief reuses for the variance split.

**Known limitations, to be stated on the card:**

- The split is only as good as the **fund-currency assignment**. US-31.5
  established that the broker's listing currency is *not* the quote currency
  (DEFS is listed EUR but `DEFS.L` quotes USD); the registry currency is the
  reliable basis. A wrong assignment silently moves return between the legs.
- Variance shares are **window-dependent** and unstable on short windows —
  they inherit the `MIN_DAILY_OBSERVATIONS` floor.
- Covariance between legs is a **linear** measure; it will not capture
  regime-dependent FX/equity relationships.

## 2.3 Formulas

### 2.3.1 Per-holding decomposition — exact, and the cross term stays

The prior brief wrote `r_base ≈ r_local + r_fx + (r_local × r_fx)` with an
approximation sign and floated dropping the cross term. **Both are wrong.**
The relationship is an identity:

```text
(1 + r_base_i(t))  =  (1 + r_local_i(t)) × (1 + r_fx_c(t))

therefore, EXACTLY:

r_base_i(t)  =  r_local_i(t) + r_fx_c(t) + [ r_local_i(t) × r_fx_c(t) ]
                └── local leg ┘ └ fx leg ┘ └──── interaction leg ────┘

where:
  r_local_i(t) = holding i's daily return in the currency its resolved market
                 line QUOTES in (the registry fund currency, US-31.5 — never
                 the broker's listing currency)
  r_fx_c(t)    = daily return of the pair converting currency c to base
  c            = fund currency of holding i; for c = base, r_fx ≡ 0 and both
                 the fx and interaction legs are exactly 0

Edge cases:
  missing price or FX quote on either side of a day: that day yields NO legs
    (excluded from every series) — never zero-filled, never carried
  fewer than MIN_DAILY_OBSERVATIONS (20) paired days: all outputs null
  base-currency holdings: contribute only to the local leg (not a degradation)
```

**Empirical resolution of the interaction question** (measured 2026-08-11 on
the live FMP series over 2026-01-01..2026-06-30):

| Holding | fund ccy | local σ | fx σ | cross, max/day | cross as % of \|local\|+\|fx\| | cumulative gap if dropped |
|---|---|---|---|---|---|---|
| SXRV | EUR | 1.0892% | 0.4031% | 2.07 bp | 0.21% | −0.018 pp |
| SEMI | GBP | 2.5571% | 0.4455% | 5.41 bp | 0.31% | **+0.504 pp** |

**Conclusion: retain the interaction leg, and report it explicitly.** Per day
the cross term is negligible (≤5.4bp). But it **compounds**: over ~6 months it
moves SEMI's cumulative return by **+0.50 percentage points**. Dropping it
would be exactly the "small, plausible, silently wrong" class this project's
guardrails exist to prevent, and the error grows with window length — so it
would be worst precisely on the long windows a risk view cares about.

**Attribution decision:** the interaction leg is reported as its **own third
leg**, not folded into either side. Ankrim–Hensel conventionally allocates it
to currency; doing so here would overstate the currency leg by a number the
researcher cannot see. Reporting three legs that sum exactly to the
base-currency return is the honest construction, and it matches how this
project already handles residuals it cannot cleanly attribute (the drawdown
contributors' "Residual (unexplained)" row; US-31.3's recorded
`reconciliation_adjustment`).

### 2.3.2 Portfolio-level legs

```text
L(t)  =  Σ_i  w_i × r_local_i(t)        (portfolio local leg)
F(t)  =  Σ_i  w_i × r_fx_c(i)(t)        (portfolio currency leg)
X(t)  =  Σ_i  w_i × [r_local_i(t) × r_fx_c(i)(t)]   (interaction leg)

where:
  w_i = holding i's BASE-CURRENCY weight (analytics/currency.py — the same
        denominator every Exposure weight uses; US-30.5a F-7)

Identity check (a required test, not a comment):
  L(t) + F(t) + X(t)  ==  Σ_i w_i × r_base_i(t)   for every t
```

Weights are held at their snapshot values across the window — this is
**synthetic history** (current holdings × historical prices), the same
convention and the same trust ceiling as every other synthetic surface.

### 2.3.3 Variance decomposition — the second open question, resolved

Portfolio return variance splits **exactly** via the covariance identity, with
no residual and no approximation:

```text
Var(r_p)  =  Cov(L, r_p) + Cov(F, r_p) + Cov(X, r_p)

  since r_p = L + F + X and covariance is bilinear.

Therefore the component shares:

  currency_variance_share      =  Cov(F, r_p) / Var(r_p)
  local_variance_share         =  Cov(L, r_p) / Var(r_p)
  interaction_variance_share   =  Cov(X, r_p) / Var(r_p)

  and by construction:  the three shares sum to EXACTLY 1.0

Reported alongside (they answer a different question):
  currency_standalone_vol   = std(F) × sqrt(252)
  local_standalone_vol      = std(L) × sqrt(252)
  local_fx_correlation      = corr(L, F)          [null if either std = 0]

Edge cases:
  Var(r_p) = 0 (constant series): every share is null, never 0 or 1
  std(L) = 0 or std(F) = 0: local_fx_correlation is null (US-27.x zero-variance
    convention), shares still computable
  paired observations < MIN_DAILY_OBSERVATIONS (20): every output null
  a share may be NEGATIVE — this is correct and must not be clamped: a currency
    leg that moves against the local leg genuinely reduces portfolio variance,
    and clamping would fabricate a floor
```

**Why component-covariance rather than `Var(F)/Var(r_p)`.** The naive ratio
ignores `Cov(L, F)` and therefore does not sum to 1 — the shares would not
account for the portfolio. The covariance form is the same
exposure×volatility×correlation identity `risk.py` already uses for factor and
position risk-share (Menchero & Davis 2011), so this extends an established
convention rather than introducing a competing one.

### 2.3.4 Lookback

Standard project heuristic, not re-derived:
`_lookback_calendar_days(window) = ceil(window × 1.6) + 30` from
`app/core/constants.py`.

| Window (trading days) | Calendar days fetched |
|---|---|
| 60 | 126 |
| 252 | 434 |

## 2.4 Data requirements

| Source | Field | Frequency | Lookback | Trust |
|---|---|---|---|---|
| `MarketDataService.get_historical_prices` | fund-currency close per holding | daily | per §2.3.4 | synthetic |
| `MarketDataService.get_fx_history(pair, …)` | FX pair close | daily | per §2.3.4 | synthetic |
| `InstrumentRegistry` | per-symbol **fund currency** | static | n/a | curated (US-31.5) |
| `ImportedPortfolioSnapshot` | positions + base currency | snapshot | n/a | broker truth |

**Data prerequisite — VERIFIED 2026-08-11** (this was US-26.2's hard blocker):

```text
resolve_symbol_candidates("EURUSD", kind="history")  ->  ['EURUSD']
   no equity fallback candidate, so the US-31.4 SEMI wrong-instrument
   substitution class does NOT apply to FX pairs

get_fx_history("EURUSD", "2026-01-01", "2026-06-30")
   -> 155 rows, last_fetch_meta.resolved_symbol = "EURUSD"
   -> price range 1.1359 .. 1.2041
get_fx_history("GBPUSD", ...)
   -> 155 rows, resolved_symbol = "GBPUSD", range 1.3166 .. 1.3842
```

**Independent cross-validation.** The broker's statement-implied period-end
rates agree with the market close on the same date:

| Pair | Statement-implied | FMP market close 2026-06-30 | Difference |
|---|---|---|---|
| EURUSD | 1.14220 | 1.14218 | +0.00% |
| GBPUSD | 1.32610 | 1.32580 | +0.02% |

Two independent sources — IBKR's own Open Positions totals and FMP's FX series
— agreeing to 0.02%. This matters for design: the static statement rate
(US-28.1, used for *levels*) and the historical FX series (used here for
*returns*) are consistent bases, so the card cannot contradict the rest of the
Exposure tab at the anchor date.

- **Minimum viable dataset:** ≥ 20 paired (price, FX) observations per non-base
  holding, and ≥ 20 portfolio-level paired days. Below that: all null.
- **FX pair universe:** derived from the portfolio's own fund currencies, not a
  fixed list — `{c}USD` for each non-base `c`. IB2026 exercises EUR and GBP.
- **Instrument gaps:** a holding with no fund-currency price history is
  **excluded from the decomposition and disclosed by symbol** — it is not
  assigned to the local leg at zero FX (that would silently understate currency
  exposure). Reuses the existing coverage-disclosure pattern.

**Tech-debt check** (skill step 1.5): `docs/tech-debt-register.md` is currently
clear of open High/Med rows in this area — the `reconciliation.py` EURUSD
hardcode this epic's PRD originally cited was resolved by US-28.1. The one
adjacent open row is **US-26.3** (request-path currency coercion), which does
**not** block this work: US-26.2 reads fund currency from the registry, not
from `position.currency`.

## 2.5 Trust-class analysis

Every output is **synthetic history** (current holdings × historical prices) —
trust ceiling `synthetic`, never `verified`.

| Field | Trust when complete | Degrades when | `unavailable` when |
|---|---|---|---|
| `currency_variance_share` | synthetic | some holdings excluded for missing history (share of excluded weight disclosed) | < 20 paired days, or `Var(r_p) = 0` |
| `local_variance_share` | synthetic | same | same |
| `interaction_variance_share` | synthetic | same | same |
| `currency_standalone_vol` | synthetic | same | < 20 paired days |
| `local_fx_correlation` | synthetic | same | either leg has zero variance |
| `per_currency[].contribution` | synthetic | that currency's holdings partially covered | that currency has no covered holding |

**No fallback anywhere.** A missing FX quote or price drops the *day*; an
uncoverable holding is excluded and named; an under-powered window nulls the
whole card. No leg is ever zero-filled, and no share is clamped into [0, 1].

## 2.6 Visualization design

**Card:** "Currency Risk Contribution" — Exposure tab, directly below the
US-26.1 Currency Exposure card (composition, then consequence).

**Recommended primary: a 100% stacked horizontal bar** of the three variance
shares, plus a small stat row. Rationale: the shares sum to exactly 1.0 by
construction, which a stacked bar states visually; a pie would obscure negative
shares, and a time series would imply a stability the estimate does not have.

- **Bar:** three segments — Local / Currency / Interaction. Distinct tokens, and
  each segment labelled with its own percentage so colour is never the sole
  encoder (the project's a11y baseline).
- **Negative share:** rendered as a separately-tokened segment extending left of
  a zero baseline, with a helper note explaining that a currency leg moving
  against the local leg *reduces* total variance. Never clamped to zero.
- **Stat row:** `Currency vol (ann.)`, `Local vol (ann.)`, `Local/FX corr` — each
  "—" when null.
- **Per-currency table** (secondary): currency, weight, contribution to currency
  variance share. Sorted by absolute contribution.
- **Window selector:** 60d / 252d, reusing `WindowSelector`.
- **States:** Loading / Error / EmptyState ("Needs at least 20 overlapping days
  of price and FX history"). Never blank, never zero.
- **Trust badge:** `Synthetic` via `TrustBadge`, top-right of `CardShell` —
  unlike the US-26.1 card, this one *is* synthetic history and must say so.
- **Responsive:** below the tablet breakpoint the bar keeps full width and the
  per-currency table collapses to currency + contribution.

## 2.7 Computed metrics inventory

| Field | Type | Formula | Trust | Nullable | Notes |
|---|---|---|---|---|---|
| `window_days` | `int` | — | synthetic | no | 60 or 252 |
| `observations` | `int` | — | synthetic | no | paired days used |
| `local_variance_share` | `float \| null` | §2.3.3 | synthetic | yes | may be negative |
| `currency_variance_share` | `float \| null` | §2.3.3 | synthetic | yes | may be negative |
| `interaction_variance_share` | `float \| null` | §2.3.3 | synthetic | yes | typically tiny; never dropped |
| `local_standalone_vol_pct` | `float \| null` | §2.3.3 | synthetic | yes | annualised ×√252 |
| `currency_standalone_vol_pct` | `float \| null` | §2.3.3 | synthetic | yes | annualised ×√252 |
| `local_fx_correlation` | `float \| null` | §2.3.3 | synthetic | yes | null on zero variance |
| `per_currency[].currency` | `str` | — | synthetic | no | e.g. "EUR" |
| `per_currency[].base_weight` | `float` | §2.3.2 | synthetic | no | base-currency weight |
| `per_currency[].contribution` | `float \| null` | §2.3.3 | synthetic | yes | to currency share |
| `excluded_symbols` | `list[str]` | §2.4 | synthetic | no | no fund-currency history |
| `excluded_weight` | `float` | §2.4 | synthetic | no | 0.0 when fully covered |

## 3. Story structure (feeds `write-story`)

Epic 26 gains one story; US-26.2 is now **ready**, and the follow-on is
optional.

| Story | Scope | Value delivered |
|---|---|---|
| **US-26.2** | `app/analytics/currency_risk.py` (per-holding legs + variance split) → exposure schema/engine → Currency Risk Contribution card, 60d/252d | Researcher can see how much of their volatility came from currency rather than securities |
| US-26.4 *(optional, not scoped here)* | Per-currency time series of the currency leg | Researcher sees *when* FX drove returns, not just how much overall |

**Explicitly out of scope for US-26.2:**

- Any hedge recommendation, target currency weight, or hedged/unhedged
  comparison (guardrail #4 — no execution).
- Currency-hedged share-class detection (PRD non-goal, unchanged).
- Look-through currency exposure — the currencies *inside* an ETF's holdings.
  This story decomposes the currency each line **trades in**.
- Retiring the statement-implied static rate. US-26.1's levels keep it;
  this story adds a *return* series alongside. §2.4 shows they agree at the
  anchor.

## 4. Doc updates this brief requires

1. `financial-methodology.md` — replace the "stretch, not ready" subsection
   with §2.3.1–2.3.4 verbatim, the citations, and the implementation target.
   Fix the "Curency" typo.
2. `docs/product/prd/epic-26-currency-exposure-and-risk.md` — flip US-26.2 from
   "stretch, not ready" to ready, and record that both blockers are cleared
   with the evidence in §2.3.1 / §2.4.

# Financial Methodology

*Updated for Epic 8 (2026-05-25): ranking/construction/optimizer/backtest methodology removed.*

This document is the project-level reference for the financial and economic methodology implemented in the codebase.

For the canonical shipped-state boundary, use `docs/product/current-product-state.md`.

## Terminology

The project uses the term `factor` rather than `quant`.

Implemented factor families include:
- `market`
- `style`
- `sector`
- `macro`

Primary implementation:
- `services/quant-engine/app/analytics/risk.py`

## Truth Classes

The project distinguishes between different financial truth classes.

- `broker-truth historical diagnostics`
  - based on imported portfolio history or explicitly available historical context
- `snapshot current-state analytics`
  - based on current holdings only
- `synthetic snapshot-history diagnostics`
  - approximate historical diagnostics built from current holdings plus external market data
- `persisted imports`
  - saved import artifacts (content-addressed, immutable); broker truth is never mutated

Relevant implementation:
- `services/quant-engine/app/services/diagnostics_engine.py`

## Trust, Degradation, Withholding, and Unavailability

This is shipped baseline behavior across diagnostics and dashboard-history.

- `verified_*`
  - the contract can make the documented trust claim for that path
- `degraded_*`
  - the engine may still compute useful outputs, but trust must be downgraded explicitly and stronger claims must stay suppressed
- `withheld`
  - broader diagnostics or replay evidence exists, but investor-economics outputs stay intentionally suppressed until return-basis requirements are justified
- `unavailable`
  - the required source inputs or trustworthy path do not exist for the requested output

Consumer rule:
- do not treat `withheld` as generic missing data
- do not backfill withheld investor-economics families through nearby diagnostics or comparison views

Import admission rule:
- `ImportAdmissionSummaryV1` is read-only reconciliation evidence for imported broker snapshots; it does not mutate broker truth, trust levels, admission state, imported values, or workspace creation
- numeric admission evidence must be finite-only; non-finite imported numeric inputs become unavailable/degraded evidence rather than serialized `NaN` or `Infinity`

Importer resilience rule:
- the importers are **fail-safe**: a malformed/non-numeric record is
  skipped and parsing continues, so a layout drift yields a *partial*
  snapshot rather than a crash or a silently mis-parsed value. A dropped
  record is never fabricated or zero-filled — it simply does not appear, and
  the resulting totals gap surfaces through the statement reconciliation
  below.
- Freedom24 (US-24.4): parses by fixed line offsets; a malformed record
  raises `IndexError`/`ValueError` which is caught per-record.
- Interactive Brokers (US-24.8): parses by regex match, which is already
  fail-safe for "is this a record at all" (`if not match: continue`); the
  fix here guards the layer *after* a match — a captured numeric/date group
  that matches the shape but fails `float()`/`datetime.strptime()` (e.g. a
  corrupted `"1.2.3"` token, an invalid calendar day) degrades that one
  field/record instead of raising.
- ESPP: investigated for the same class of gap (US-24.8) and found **not
  reachable** — every numeric regex group in this importer uses the strict
  shape `[\d,]+\.\d+`, which cannot capture a value that fails `float()`
  after comma-stripping. No code change was made; adding a guard against an
  unreachable failure would be unjustified complexity. ESPP's existing
  hard-fail when the statement structure doesn't match at all (it is scoped
  to one specific statement shape) remains the correct behavior.
- Interactive Brokers CSV (US-28.1,
  `app/importers/interactive_brokers_csv.py`): parses the machine-readable
  Activity-Statement CSV export (`utf-8-sig`, stdlib `csv`, per-section
  column headers with mid-file Header restatement support). Each record is
  parsed per-row inside a `try/except ValueError` plus explicit
  currency/discriminator screens, so a malformed cell (`--` where a number
  belongs, a non-numeric quantity, a truncated row, an invalid calendar
  date) drops that record only. Statement totals map from the statement's
  own `Change in NAV` / `Net Asset Value` sections and are stored as
  absolute values (the shared `ImportedStatementTotals` convention); signs
  live on the ledger entries. Non-base amounts keep their own currency —
  the importer does not convert (US-27.8 owns FX trust semantics).

Broker section-role registry (US-24.5):
- `ImportedLedgerEntry.source_section` is **provenance** — it records what the
  statement itself called the section, and an importer must never relabel its
  broker's vocabulary to satisfy a downstream matcher. The domain therefore
  resolves a section's **semantic role** (trade / external transfer / dividend
  / interest / fee / tax) through a single registry in `domain/ledger.py`,
  keyed on the label and resolved together with `entry_type` (one label may
  carry several roles — the ESPP section produces both the payroll
  contribution and the purchase). `broker_evidence` and
  `cash_movement_classification` consult the role; no broker display string is
  matched inline.
- **Why:** the previous inline matching used a vocabulary drawn entirely from
  IBKR statements, so any other broker's labels fell through to
  `cash_movement_classification == "unknown"` **silently**. Live on two of
  three brokers: every Freedom24 trade (`"Transactions"`) and every ESPP
  contribution and purchase (`"Employee Stock Purchase Summary"`) was
  unclassified, which left `portfolio_proof`'s external-capital-flow witness
  reporting an ESPP payroll deposit as `not_observed` while the statement
  stated it plainly.
- `"unknown"` remains reachable and meaningful: it is the honest answer for a
  section the domain genuinely does not recognise. Defaulting an unregistered
  label to a role would fabricate provenance the statement never gave.
- A test asserts that **every** `source_section` literal any importer emits
  resolves to a registered role, so a new broker fails the suite rather than
  degrading classification in production.

Statement reconciliation & activity scoping rule:
- the statement reconciliation summary (`build_reconciliation_summary`) and the monthly activity series (`build_activity_series`) are scoped to the **imported statement(s)' ledger** as produced by `snapshot_to_ledger` — there is no hardcoded calendar year; the activity series buckets every ledger entry by its own `YYYY-MM`, and each reconciliation actual (dividends, withholding tax, fees, interest, deposits) sums the whole ledger for the imported period (US-24.1). A statement from any year (2025, 2026, …) is reconciled against its own totals.
- credit-interest withholding **counts toward the withholding actual**
  (US-28.1): IBKR's own Withholding Tax total includes it on every statement
  that has such rows (verified 2023–2026). The former "Credit Interest"
  exclusion in `_negative_withholding_total` made the check fail against the
  statement's own number and was removed; regression-pinned on both the CSV
  fixture and the legacy 2025 PDF.
- the open-positions check converts each position into the base currency via
  the statement's own `fx_rates` (`<CCY>USD`), falling back to the legacy
  behavior when no rate exists (EUR at 1.0; other currencies excluded) so
  PDF snapshots reconcile identically. The CSV importer supplies **implied
  per-currency rates** derived from the statement's own Open Positions
  totals (each non-base currency group's total restated in the base
  currency) — broker truth, not an external FX lookup.

## Market Data Basis

The project uses historical price series, benchmark series, ETF holdings, and security metadata supplied through `MarketDataService`.

Primary implementation:
- `services/quant-engine/app/services/market_data.py`

Important financial rule:
- return-based analytics should use adjusted-close or stronger total-return-equivalent inputs whenever economically required

Row `price`-field basis (US-27.9 / audit F13b — verified empirically against
the committed frozen capture of real provider data,
`app/scripts/golden_market_data.json`, 2026-07-05):
- **Yahoo-fallback rows** set `price = adjClose` by construction
  (`yfinance_client.py`); verified in the capture — `max |price − adjClose|
  = 0.0` across all 9 Yahoo-sourced symbols.
- **FMP `historical-price-eod/light` rows** carry `adjClose` on some fetch
  paths (the verified-benchmark SPY path *requires* non-null `adjClose`);
  where `adjClose` is absent, `price` alone is classified
  `unverified_close_only` by `select_history_price_series` — its adjustment
  basis is *indicated* as adjusted (historical values re-adjust across
  fetches, the signature of an adjusted series — the US-21.4 golden-churn
  root cause) but is not provable from the row shape.
- Engines that consume `row["price"]` directly (the correlation /
  intra-correlation engines, the daily-state builders) therefore inherit the
  provider's basis: verified-adjusted where Yahoo-sourced, unverified
  otherwise. Their responses are synthetic-history trust and never claim a
  verified return basis, so this is consistent with the degradation ladder.
  No adjClose ≠ price row has been observed in the capture; if one appears,
  prefer `select_history_price_series` at that call site.

Current shipped hardening state:
- diagnostics degrades benchmark and factor source semantics to `live_market_data_unverified_return_basis` when adjusted-close trust is not proven
- diagnostics run-level confidence degrades when those paths remain unverified
- diagnostics and dashboard-history expose grouped `section_trust` so mixed trust does not collapse into one top-line label
- investor-economics withholding is policy-driven and explicit, not a generic market-data failure

Current adjusted-close verification rule:
- a history is marked `verified_adjusted_close` only when the required loaded rows explicitly support that claim under the current code path
- absence of that proof keeps the path degraded or withheld rather than silently upgrading trust

## Synthetic History Coverage Rule

*US-27.7 (audit F8). Applies to both daily-state builders: the synthetic
snapshot-history convention (`_build_synthetic_snapshot_history_states*` in
`diagnostics_engine.py` — feeds the stress / drawdown / distribution /
multi-benchmark-correlation / attribution engines and synthetic diagnostics)
and the broker replay path (`engine/portfolio_state.py` — dashboard history,
drift).*

A price is **never fabricated before a symbol's first available quote**. The
previous implementations back-filled the first quote flat across leading
dates (and flat-filled the statement close price for symbols with no fetched
history at all), producing fabricated zero returns that understated
volatility, VaR, and drawdown and distorted correlations.

```text
Definitions:
  first_quote(s)   = earliest in-window quote date for symbol s
                     (broker path: a REAL quote dated before the window may
                      seed the carry — that is a carry-forward of an observed
                      price, not a back-fill)
  material holding = snapshot weight ≥ SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT
                     (= 0.01; heuristic policy constant in
                      app/core/constants.py, no academic basis — tune only as
                      a reviewed change)

Rule:
  effective_start  = max( first_quote(s) : s material, covered )
                     (if NO holding clears the de-minimis bar, every covered
                      holding is treated as material so the window is still
                      set by real coverage)
  the state series starts at effective_start; when effective_start >
    requested start, the limiting symbol is disclosed
  EXCLUDED from the synthetic universe (and disclosed):
    - holdings with no in-window price history at all (previously
      statement-close flat-filled)
    - sub-de-minimis holdings whose first quote falls after effective_start
      (including them would fabricate a mid-window entry / weight jump)
  INTERIOR gaps (missing quotes after the first one) carry the last known
    price to the next quote — the standard convention for aligning mixed
    trading calendars; this is carry-forward of an observed price, never a
    back-fill

Disclosure:
  SyntheticHistoryCoverage { requested_start_date, effective_start_date,
    limiting_symbol, excluded_symbols } is emitted by the stress, drawdown,
  distribution, multi-benchmark-correlation, and attribution engines and
  rendered by their cards (a `helper` note) whenever the window was
  truncated or holdings were excluded — never silently.

Broker-path specifics:
  - the replay window truncates on MATERIAL opening positions' coverage;
    traded-in positions need no early quotes (quantity is 0 before the BUY)
  - a symbol with NO fetchable history at all keeps the statement close
    price as its anchor (broker-truth-adjacent, the last honest value we
    hold) and does not truncate the window
  - sub-de-minimis opening holdings with late coverage carry no market price
    on their pre-coverage days (bounded by the de-minimis weight)
  - RECONSTRUCTED symbols (US-31.2 / Epic 31 F-1) — the replay rolls ending
    positions back through BUY/SELL, so it values three populations: symbols
    still held, symbols held at the window open and since sold, and symbols
    bought AND sold entirely inside the window. Price history is fetched for
    all of them (`replay_symbol_universe`), not just current holdings; the
    narrow fetch left since-sold positions unpriced, contributing 0 to market
    value (27 of 38 IB2026 opening positions; opening MV $14,582 vs an implied
    $50,116) with the shortfall absorbed by the cash anchor.
  - a since-sold symbol has NO current snapshot weight, so materiality cannot
    be evaluated for it: such symbols are EXCLUDED from the truncation
    reference set rather than defaulting to the maximum weight. Otherwise any
    one of them whose coverage happens to begin mid-window would truncate the
    replay for every other holding. Their coverage gap is disclosed instead
    (see below), never allowed to silently reshape the window.

Broker-path valuation precedence (US-24.10) — three tiers, never inverted:

```text
  1. market price history            -> priced, full market movement
  2. statement close price           -> flat anchor (US-27.7 / US-30.2),
                                        disclosed via statement_anchored_symbols
  3. last broker TRADE price at or
     before the day, carried FORWARD -> flat anchor, disclosed via
                                        trade_price_anchored_symbols
  otherwise                          -> unvalued (contributes 0), disclosed via
                                        unpriced_replay_symbols
```

  A symbol-day falls in **exactly one** tier. The claim is per (symbol, day),
  not per symbol (US-33.3 / Epic 33 F-3): the ladder is evaluated once per day
  and the disclosure sets are unions over the window, so a holding that
  predates its own first trade is disclosed as unpriced for those days and
  trade-anchored for the rest. Tier 3 exists because a
  round-trip position — opened and fully closed inside the window — is absent
  from the current snapshot, so it has neither history nor a statement close,
  yet the statement records an execution price for every one of its trades.
  That is an observed price for the identical instrument (IFRS 13's Level 2),
  and it is the last honest value available.

  Why the ordering does not follow recency: the statement close outranks a
  trade price even when the trade is nearer in time, because inverting it would
  re-value every currently-held statement-anchored symbol and regress
  US-27.7 / US-30.2. Tier 3 is strictly additive.

  **Forward-carry only.** Before a symbol's first observed trade the anchor does
  not apply — reaching backwards would fabricate a price for a date the broker
  never produced one, the same rule that forbids back-filling market history.
  Such days stay unvalued and disclosed.

  Currency: a tier-3 value is converted from the **trade's settle currency**
  (the currency its price is quoted in), not the fund currency the US-31.5 rule
  selects for market-priced holdings. With no rate available it is carried
  unconverted and disclosed via `fx_fallback_currencies` — never converted 1:1.

  The carried segment is FLAT: it contains no market movement, and is disclosed
  as such rather than passed off as a priced series. Interpolating between two
  trade prices is deliberately NOT done — a carried price was observed; an
  interpolated one never was.

  Why this matters beyond valuation accuracy: a `$0`-valued holding still moves
  real cash when traded, so `total_portfolio_value` steps with no offsetting
  position and the cash-inclusive TWR publishes the step as **performance**.
  On IB2026 that fabricated the window's two largest days — **−7.90%**
  (2026-04-08, buying $5,092.82 of BTEC/IUFS/IUHC) and **+9.61%** (2026-04-27,
  selling IUFS/IUHC for $5,341.92) — on which nothing was earned or lost.
  Guardrail #3, the same class as the terminal-reconciliation fabrication.

Unpriced-symbol disclosure (US-31.2):
  a symbol the replay holds on a given day but cannot value at all — no
  fetchable history, no statement close anchor, and no prior trade price
  (tier 4 above) — contributes 0 to that day's market value and is recorded in
  `unpriced_replay_symbols`, surfaced on the dashboard-history run metadata.
  The weakest outcome, and disclosed rather than published as an understated
  NAV. A symbol reclassified into tier 3 leaves this set; one the trade-price
  anchor still cannot reach stays in it.

Trade-leg neutralisation interaction (US-24.9, rule corrected by US-24.10):
  `DailyPortfolioState.trade_flow` may only cancel a trade leg that actually
  crossed the market-value boundary — i.e. the symbol is priced in today's
  market value (a BUY landed) or was priced in the previous day's (a SELL
  left). A trade in a symbol that is in NEITHER is invisible to the MV series,
  so counting it fabricates a return. Three cases this excludes, all observed
  on IB2026: trading a symbol with no obtainable price; selling a symbol first
  observed by that very sale; and a same-day round trip in a new symbol
  (2026-06-11 IITU — bought and fully sold before any close, in no day's market
  value, which produced −3.45% against an expected −0.36%).

Fail-closed interaction:
  the MIN_DAILY_OBSERVATIONS floors apply to the EFFECTIVE (post-truncation)
  series — a window shortened below the floor surfaces `unavailable`
  (with the coverage disclosure attached), never fabricates data to reach
  the floor.
```

Contract rule:
- coverage disclosure fields ride the same trust class as their engine
  response (synthetic history); `excluded_symbols` is never collapsed into a
  generic unavailable state — the researcher must be able to see *which*
  holdings the analytics do not cover.

### Share-Unit Discontinuity Withholding (US-33.2)

**This is a trust rule, not a model.** It computes no return, risk or exposure
number; it decides whether a reconstructed *quantity* may be published at all.

The four valuation tiers above all answer "what is this holding worth?" and
presuppose a trustworthy quantity. The imported ledger replay does not observe
quantities directly — it reconstructs them by rolling the ending position back
through the window's trades:

```text
opening_qty = ending_qty + Σ SELL qty − Σ BUY qty
```

That identity holds only while every term is denominated in the **same share
unit**. A corporate action that restates the unit — a split — breaks it by
construction: post-split sale quantities are summed against pre-split purchase
quantities, and the difference is published as an opening position. On the
2026-08-11 IB2026 statement LQQ split ~200:1 mid-window, and the roll-back
produced a **199-unit** opening position that was never held. The US-24.10
trade-price anchor (tier 3) then carried the stale pre-split **EUR 1,457.78**
across the split and valued it, taking peak replayed market value to
**$518,078.75** against a statement `stock_total` of **$64,922.99**.

**Detection.** For each symbol, the ratio between its highest and lowest broker
execution price is measured **within a single currency** (the widest currency
wins); prices in different currencies are never compared, so an FX difference
cannot be mistaken for a unit change. At or above
`REPLAY_SHARE_UNIT_DISCONTINUITY_RATIO` (**5.0**, `app/core/constants.py`) the
symbol's quantities are treated as denominated in more than one unit.

Threshold calibration on the committed statement (68 symbols): the widest
**legitimate** within-symbol ratio is **1.40** (NFLX); the true positive is LQQ
at **218.10**. The threshold sits ~3.6× above the highest legitimate
observation and ~44× below the true positive. It is a heuristic policy value
with no academic basis (US-24.2 discipline).

**Consequence — withhold the quantity, not the price.** A flagged symbol emits
no position line, no quantity and no market value on any day of the window, and
appears in **none** of the four valuation tiers. Valuing it at `$0` would not be
enough: that still publishes a position size the broker never held. Its cash
movements are preserved — those are broker truth the unit ambiguity does not
touch — and because the symbol is priced on no day, the US-24.9 trade-leg gate
keeps its legs out of `trade_flow`, so no return is fabricated from them. The
withholding is disclosed with its evidence (currency, price bounds, ratio, and
the rejected opening quantity) via `run_metadata.quantity_withheld_symbols`.

The same rule guards the tier-3 anchor directly: for a flagged symbol the
trade-price anchor returns no price at any date, so a carried price can never
cross a detected discontinuity regardless of which caller asks.

**Withheld quantities move cash, and that cash has nothing behind it.** The
symbol's BUY/SELL entries still settle — that is broker truth — but the position
they bought or sold is in no market value, so `total_portfolio_value` steps with
nothing offsetting it and a cash-inclusive return chain would publish the step
as performance. This is the same fabrication the trade-leg neutralisation rule
above exists to prevent, re-opened by withholding, and the cash-EXCLUDED basis
does not cover it. The day's cash movement is therefore recorded as
`DailyPortfolioState.unbacked_cash_flow`, and a state carrying a material amount
has **no publishable return on any basis** — the US-31.3 treatment of the
reconciled terminal day, applied to the same class of un-interpretable state.

Measured on IB2026: leaving these days in the chain inflated annualised TWR
volatility from 14.18% to 15.49% and made the window's largest apparent move
(+3.08% on 2026-04-17) a pure artefact of a phantom position's cash.

**Materiality is a share of portfolio value (US-34.4).** The guard originally
reused `REPLAY_RECONCILIATION_TOLERANCE` ($1.00) — a constant calibrated for
cent-level rounding across daily states, not for materiality against a
portfolio — and the consequence was real return days discarded for nothing. On
IB2026 the six unbacked days are cleanly bimodal:

```text
0.0085% ($5.13)   0.0400% ($25.09)              <- distort nothing measurable
2.7658%  2.8352%  3.3468%  3.7101%              <- genuinely un-interpretable
```

a **69x** gap. `REPLAY_UNBACKED_CASH_MATERIAL_SHARE` (0.1%) sits ~2.5x above the
noise and ~28x below the signal, so the two immaterial days publish their real
returns and the four material ones stay withheld.

**A withholding also states its size (US-34.4 / Epic 34 F-3).** Naming the
symbol and the evidence tells the researcher *why*, not *how much* — missing
0.1% of a book and missing 30% of it read identically. The magnitude comes from
the broker's own cash movements, which is what makes it derivable at all: the
QUANTITY is the untrusted thing, so exposure cannot be measured as quantity x
price.

```text
peak_net_cash_invested = max over days of ( − Σ FX-converted cash_effect )
                         taken at each day's CLOSE
exposure_day_count     = valuation days from the symbol's first trade to its last
```

Both are **lower bounds and spans, never valuations**. `peak_net_cash_invested`
is what the broker paid, not what the position was worth, so it can understate
the gap and never overstate it — surfaces must word it as "at least", and it
must never enter `total_market_value`. `exposure_day_count` deliberately does
not claim "days held": that needs a running quantity, and cumulative cash cannot
substitute, because a round trip closing at a loss leaves a positive residual
that would keep counting after the position closed.

The share is `None` — not `0.0` — when the peak day's portfolio value is not
positive, since the ratio would be meaningless there. An absent measurement is
honest; a fabricated percentage is not.

Measured on IB2026: LQQ peaked at **$2,130.62** (**3.52%** of the portfolio)
across a **66-day** span of the 148-day window. The within-day gross reaches
$4,410.08 on 2026-06-23 because a buy precedes a sell; the end-of-day figure is
the one that matches the replay's end-of-day states.

**Stated limitation.** A small split (2:1, 3:1) produces a ratio below the
threshold and is **not** detected — its mixed units will still be summed.
Lowering the threshold far enough to catch it would begin withholding genuinely
volatile holdings over long windows, which is a worse failure (a real position
withheld) than the one it prevents. Closing that gap properly requires a
corporate-action data source, which the project does not have; inferring a
split ratio from a price jump would be fabricating broker truth from market
data and is forbidden. This rule therefore makes the replay **safe** in the
presence of corporate actions, not **correct through** them.

## Portfolio Return Methodology

### Cash-flow-neutral daily returns

For historical risk and factor diagnostics, the portfolio return series is built from daily portfolio states using a cash-flow-neutral formula.

Implemented formula:

```text
daily_return_t = ((total_portfolio_value_t - external_cash_flow_t) / total_portfolio_value_(t-1)) - 1
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_portfolio_time_weighted_return_series(...)`

### Publication rungs for the replayed return (US-34.2)

**No formula changes here.** The chained cash-flow-neutral daily return above is
computed the same way regardless of rung; what a rung decides is whether the
result may be **published**, and under what label.

| Rung | Meaning |
|---|---|
| `verified_total_return` | The portfolio proof admitted an exact slice. A GIPS-style claim. |
| `replay_derived` | Chained from the imported ledger replay's own daily states. A real measurement on **reconstructed** inputs: opening positions rolled back through the ledger, a mixed valuation basis, and a terminal reconciliation. |
| `unavailable` | The replay produced no states, so no return is claimable. |

`replay_derived` exists because the strict admission gate answers a *different*
question. Five of its hard disqualifiers — `inferred_opening_holdings`,
`inferred_opening_quantities`, `terminal_force_reconciliation_present`,
`forward_filled_prices`, `mixed_basis_valuation` — are structural properties of
replaying a broker statement and can never clear. Treating that failure as "no
answer available" withheld a correctly-computed number on every run.

**Withholding is unchanged by the rung.** A day whose state carries a material
reconciliation adjustment (US-31.3) or unbacked cash flow (US-33.2) yields no
daily return on any rung, so the published chain has gaps by design.

**A return with gaps must state what the gaps cost.** The engine reports
`withheld_return_impact_pct`: the difference between the published chain and the
same chain including the withheld days. It is an **impact estimate, never a
return** — those days' moves are not performance, which is why they are
withheld — but publishing a figure that omits days without saying what the
omission is worth misleads more than publishing nothing. On IB2026 the published
2.43% understates the all-days chain of 4.23% by 1.80pp.

**Range returns are re-based, not sliced.** The cumulative series is one chain
from the series start, so a window's return is the ratio of growth factors,
`(1 + c_end) / (1 + c_start) − 1`, taken at the window's own first plotted
point. Reading the slice's last point instead reports since-inception for every
window.

## Money-Weighted Return (Modified Dietz)

Money-weighted return measures the return actually experienced by the
investor's capital, accounting for the size and timing of external cash
flows — distinct from time-weighted return (§Portfolio Return Methodology),
which measures the *manager's* return independent of when the investor added
or withdrew capital.

The project uses the **Modified Dietz method**: a closed-form, day-weighted
approximation of money-weighted return that does not require an iterative
IRR solve.

```text
money_weighted_return_pct = ((V_end - V_start - CF_total) / D) * 100

where:
  V_start      = total_portfolio_value of the first daily state
  V_end        = total_portfolio_value of the last daily state
  CF_total     = Σ external_cash_flow_i  over all states after the first
  D            = V_start + Σ (external_cash_flow_i * w_i)   (the weighted capital base)
  w_i          = (P - i - 1) / P
                 for the i-th cash-flow state (0-based index among the
                 flow-bearing states, i.e. all states after the first)
  P            = max(N - 1, 1), N = number of daily states

  w_i is the fraction of the period remaining after the flow occurred: a flow
  on the first day after the start gets a weight close to 1 (invested for
  nearly the whole period); a flow on the last day gets weight 0 (invested for
  ~0 time). This is the standard day-weighted (as opposed to fixed 0.5
  mid-point) Modified Dietz weighting.

Edge cases:
  fewer than 2 daily states: money_weighted_return_pct = null
  D = 0: money_weighted_return_pct = null (division undefined)
```

Implementation:
- `services/quant-engine/app/analytics/performance.py` —
  `build_performance_summary(...)`

Academic precedent:
- Dietz, P.O. (1966), "Pension Fund Investment Performance — What Method to
  Use When," *Financial Analysts Journal* 22(1): 83–89.
- CFA Institute, *Global Investment Performance Standards (GIPS)* — Modified
  Dietz Method guidance (day-weighted cash-flow variant).

Contract rule:
- `money_weighted_return_pct` carries the same trust/withholding semantics as
  the rest of `PerformanceSummary` — see the dashboard-history investor-
  economics partial-unlock contract in `docs/contracts/dashboard-fields.md`.
- Never confuse this with IRR/XIRR: Modified Dietz is a linear approximation,
  not an iterative internal-rate-of-return solve. It is exact only when cash
  flows and returns are small/smooth within the period; for large flows near
  a period boundary combined with high volatility, it can diverge from a true
  IRR. This is a known, accepted limitation of the method, not a bug.

### Terminal-value input rule (US-34.6)

The formula is unchanged; **which terminal value feeds it** is not.

`_reconcile_terminal_state_to_statement_totals` snaps the last state's
`total_portfolio_value` to the statement's ending NAV. US-31.3 established that
the amount it moves by is an **accounting correction, not a market move**, and
must never be published as performance — and applied that rule to the
time-weighted return, which withholds the affected day.

Every other period-level figure read the reconciled value straight, so each
republished the entry the TWR refuses:

| Figure | With the entry | Market-derived | On IB2026 |
|---|---|---|---|
| Money-weighted return | 2.73% | **2.76%** | 0.03pp of it is the entry |
| Investment gain | $1,626.01 | **$1,645.99** | $19.98 of it is the entry |

*Measured on the 2026-08-17 capture.* When US-34.6 shipped, the same two rows
read 5.30% → 2.95% and $3,080.88 → $1,714.71, because the terminal
reconciliation was then **+$1,366.17**. US-34.3 anchored opening cash on the
statement's own figure and US-34.9's re-capture supplied real terminal-day
quotes, shrinking the adjustment to **−$19.98** — so the rule now removes a much
smaller amount, and removes it in the opposite direction. The rule itself is
unchanged: a performance figure must never contain an accounting entry,
whatever that entry happens to be worth on a given run.

**Performance figures** — Modified Dietz and the investment gain — therefore use
`market_derived_terminal_value(states)`: the terminal `total_portfolio_value`
less its recorded `reconciliation_adjustment`.

**Levels do not.** `end_value`, the daily states and the portfolio-value chart
keep the reconciled figure, because the statement's ending NAV is broker truth
and is the correct level. This is the same split US-31.3 drew for the cash
anchor: levels are affected, returns must not be.

One shared helper serves both Modified Dietz implementations — two call sites
doing the same subtraction independently is exactly how they would drift apart.

*Consequence to disclose:* the displayed value, gain and contributions no longer
reconcile by subtraction, so the surface must say why (US-34.6 AC6).

**The daily return uses it too (US-34.8).** US-31.3 required that an accounting
adjustment never be published as a return, and enforced that by WITHHOLDING the
reconciled terminal day — because at the time no un-overwritten value existed.
This rule creates one, so the day's return is computed from the market-derived
value instead:

```text
r_terminal = (market_derived_terminal_value − external_cash_flow) / PV_{t−1} − 1
```

That satisfies US-31.3's requirement *more exactly* than blanking did: the
adjustment cannot enter the figure by construction, and a real day of market
movement stops being discarded. The published return is **invariant to the size
of the adjustment**, which is the property the regression pins assert.

Withholding remains for the other cause: a day whose cash moved with no position
behind it (US-33.2) has no corrected value available, because the missing thing
there is a *position*, not an adjustment.

*Why no materiality bound on the adjustment.* A large adjustment means the
replay's valuation disagrees with broker truth — a concern about the **whole
window**, since every other day is valued by the same machinery with no
cross-check at all. The terminal day is the only day that *can* be checked;
withholding it while publishing the unchecked days would be backwards. The
adjustment is already disclosed as the window-level signal it is.

*Both return chains apply it.* `performance.py::_time_weighted_daily_return` and
`risk.py::_portfolio_time_weighted_return_series` are two independent
implementations of the same formula — `return_is_publishable` is shared between
them, the arithmetic is not — so the correction is applied in both. The
market-value bases need no equivalent: the reconciliation moves
`total_portfolio_value` and cash, never `total_market_value`.

## Monthly Returns (Dashboard)

Monthly returns compound the same cash-flow-neutral daily returns as the
time-weighted return chain (§Portfolio Return Methodology), bucketed by
calendar month.

```text
daily_return_t = ((V_t - CF_t) / V_{t-1}) - 1        (cash-flow-neutral, as §Portfolio Return Methodology)

monthly_return_m = Π (1 + daily_return_t) - 1
                   over all t whose END date falls in month m

Bucketing rule (US-27.2):
  a daily return spanning t-1 → t belongs to the month of t (its end date).
  The baseline therefore carries ACROSS month boundaries: the first trading
  day of month m+1 compounds against the last state of month m. This makes
  the chaining identity exact by construction:

    Π_m (1 + monthly_return_m) = Π_t (1 + daily_return_t)   (the period TWR chain)

Edge cases:
  a month with no computable daily return (e.g. the anchor month containing
    only the anchor state, or a month fully inside a valuation gap): emit NO
    entry for that month — never a fabricated 0.0%
  sparse state series (valuation gap spanning months): the cross-gap return
    is booked into the month of the gap's END date (the first date the value
    is observed again); intermediate gap months emit nothing. This preserves
    the chaining identity; it also means a gap-ending month can carry a
    multi-month return — the `monthly_returns_reliable` guard (any |monthly|
    > 100%, or negative portfolio values) suppresses the grid when this
    produces unstable output
  anchor rule: states before the first positive total_portfolio_value are
    excluded (same anchor as the visible summary)
```

Implementation:
- `services/quant-engine/app/services/dashboard_history_engine.py` —
  `_compute_contribution_adjusted_monthly_returns(...)`,
  `_monthly_returns_are_reliable(...)`

Contract rule:
- `monthly_returns` carries the same trust/withholding semantics as the rest
  of the dashboard-history contract (`docs/contracts/dashboard-fields.md`);
  `monthly_returns_reliable = false` hides the whole grid, never individual
  cells.

### Dashboard range max drawdown

`range_metrics[*].max_drawdown_pct` is computed from the **compounded return
index** (§Wealth Index and Drawdown) built over the range's cash-flow-neutral
daily returns — never from raw portfolio value (US-27.2: a deposit would mask
a real drawdown; a withdrawal would fabricate one). The wealth index is
anchored at 100 on the range's first state date. The field remains subject to
the investor-economics withholding policy (`dashboard-fields.md`); this rule
governs the computed value, not its visibility.

Implementation:
- `services/quant-engine/app/services/dashboard_history_engine.py` —
  `_compute_max_drawdown(...)` (reuses `_build_wealth_index` /
  `_build_drawdown_from_return_index` from `analytics/risk.py`)

## Benchmark and Factor Return Methodology

Benchmark and factor returns are built from price series using simple daily returns.

Implemented formula:

```text
return_t = (price_t / price_(t-1)) - 1
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `_benchmark_return_series(...)`
- `_series_to_returns(...)`

Financial rule:
- these return paths must not overclaim investor-economics trust when adjusted-close or total-return-equivalent support is not proven for the specific contract path

### Mixed-basis portfolio-vs-benchmark comparison (US-34.5)

The Dashboard's `excess_return_pct` compares two returns measured on **different
bases**. No new equation is involved — the excess is defined as the subtraction
of the two figures actually published:

```text
excess_return_pct = round(time_weighted_return_pct - benchmark_return_pct, 2)
```

It is computed *from the published scalars*, never derived independently, so the
three figures on screen always reconcile. If either leg is null the excess is
null; a missing leg is never read as zero.

**Bases and the direction of the bias.** The portfolio leg is a cash-inclusive
time-weighted return over the imported replay, where dividends arrive as ledger
entries — so it is already total-return-like (see F-11 under US-34.7). The
benchmark leg is whatever its own data supports:

| `benchmark_path` | Benchmark return | Note |
|---|---|---|
| `verified_total_return` | published | dividends included; comparison is like-for-like |
| `price_return_only` | published | **dividends excluded** |
| `unverified_adjusted_proxy` | withheld | adjustment claimed but not provable |
| `unavailable` | withheld | no data |

On `price_return_only` the benchmark's dividends are omitted, so the benchmark
is **understated** and the excess is **flattered** — always in the portfolio's
favour, never against it. The bias is disclosed on the surface next to the
figures whenever that basis is in force, rather than left for the reader to
infer.

**Measured, on the current window (US-34.9).** The two bases were compared
directly against the provider over 2026-01-08 → 2026-08-11: the price return is
**+11.7547%** and the dividend-adjusted total return **+12.3462%**, a gap of
**0.59pp** — 111 of the 148 dates carry a non-zero adjustment. Since the
re-capture the Dashboard runs on `verified_total_return`, so the caveat is no
longer displayed: it is rendered only while the basis is actually
`price_return_only`.

Publishing on a stated basis is **not** a trust promotion:
`run_metadata.return_basis_contract.benchmark_path` continues to name the basis
and `investor_economics_status` continues to read `withheld`.

**Where the adjusted series comes from (US-34.9).** `verified_total_return`
requires an adjusted close on every in-window row, a fetch from the endpoint
named in `VERIFIED_BENCHMARK_ENDPOINT`, and an **ascending** date order. Until
US-34.9 the constant named `historical-price-eod/light`, which returns no
adjusted close, so the first two conditions were mutually unsatisfiable (F-9);
the third was independently violated because FMP returns rows newest-first
(F-14).

The benchmark is now built from **two** responses, joined on date, because
neither carries both figures:

| Endpoint | Supplies | Missing |
|---|---|---|
| `historical-price-eod/full` | `close` (traded price) | no `adjClose` |
| `historical-price-eod/dividend-adjusted` | `adjClose` (split + dividend adjusted) | no `close` |

`price` is the traded close and `adjClose` the adjusted one, ordered ascending.
The same split now holds on the yfinance fallback (F-15), so `price` means the
same thing on every provider.

The adjusted series is used for the benchmark **return only**. Position and FX
history stay on the unadjusted endpoint: a dividend-adjusted series is a return
series, not a value series, and valuing holdings with it would make
`total_market_value` disagree with the broker's own statement. The scope is
enforced structurally — `get_direct_verified_benchmark_history` is the only
caller of the adjusted method.

Implementation:
- `services/quant-engine/app/services/dashboard_history_engine.py`
- `_allow_benchmark_return_output(...)`, `_range_time_weighted_return_pct(...)`
- `services/quant-engine/app/services/benchmark_service.py`
- `services/quant-engine/app/clients/fmp.py` — `get_historical_price_dividend_adjusted(...)`

## Wealth Index and Drawdown

### Wealth index

```text
wealth_0 = 100
wealth_t = wealth_(t-1) * (1 + daily_return_t)
```

### Drawdown

```text
drawdown_t = (wealth_t / running_peak_t) - 1
```

### Drawdown episode identification

A drawdown *episode* is a contiguous run of `drawdown < 0` between two equal
peaks in the wealth index.

```text
Algorithm (greedy walk forward through daily drawdown series):
  state ← "at-peak"
  for each date t in chronological order:
    if state == "at-peak" and drawdown_t < 0:
      episode.peak_date    ← date of max(wealth_{0..t-1})
      episode.peak_value   ← wealth at peak_date
      episode.trough_date  ← t
      episode.trough_value ← wealth_t
      state ← "in-drawdown"
    elif state == "in-drawdown":
      if wealth_t < episode.trough_value:
        episode.trough_date  ← t
        episode.trough_value ← wealth_t
      if wealth_t >= episode.peak_value:
        episode.recovery_date   ← t
        episode.magnitude_pct   ← (trough_value / peak_value - 1) * 100
        episode.duration_days   ← trough_date - peak_date     (calendar days)
        episode.underwater_days ← recovery_date - peak_date
        emit episode
        state ← "at-peak"

At end of series, if state == "in-drawdown":
  emit incomplete episode with:
    recovery_date   = null
    underwater_days = (last_date - peak_date)
```

Edge cases:
- single-day dip (`wealth_t < wealth_{t-1}` and `wealth_{t+1} >= wealth_{t-1}`):
  episode is still emitted; `duration_days = 0`
- series length < 20: emit zero episodes; surface as `trust = 'unavailable'`

Top-N selection: sort emitted episodes by `magnitude_pct` ascending (deepest
first); return first `N` (default `N = 5`).

Academic precedent:
- Magdon-Ismail & Atiya (2004), "Maximum drawdown," *Risk Magazine*, Oct 2004
- Goldberg & Mahmoud (2017), "Drawdown: from practice to theory and back
  again," *Mathematics and Financial Economics* 11(3): 275–297

Implementation:
- `services/quant-engine/app/analytics/risk.py` —
  `_build_wealth_index(...)`, `_build_drawdown_from_return_index(...)`
- `services/quant-engine/app/analytics/drawdown.py` —
  `build_underwater_series(...)`, `identify_drawdown_episodes(...)`,
  `current_drawdown_pct(...)`, `max_drawdown_pct(...)` (Epic 13 / US-13.2),
  `decompose_drawdown_episode(...)` (Epic 15 / US-15.1)
- `services/quant-engine/app/services/drawdown_engine.py` —
  `run_drawdown_engine(...)` (wires market data → analytics)
- `services/quant-engine/app/api/routes/drawdown.py` —
  `POST /engines/drawdown/run`

Contract rule:
- `recovery_date = null` is distinct from "no episode" — it explicitly signals
  the portfolio is still under water. UI must surface this state, not collapse
  it to "no data".

### Drawdown episode decomposition

Decomposes a drawdown episode's portfolio-level magnitude into per-position
contributions using arithmetic Brinson-style attribution under the
synthetic-history convention (current holdings × historical prices, no
rebalancing).

```text
Per-position contribution:
  contribution_i  =  w_i(t_peak)  ×  r_i

where:
  w_i(t_peak)  =  V_i(t_peak) / V_p(t_peak)
                 = (q_i × p_i(t_peak)) / Σ_j (q_j × p_j(t_peak))
  r_i          =  p_i(t_trough) / p_i(t_peak) − 1
  q_i          =  synthetic quantity (current holdings; see
                  `_build_synthetic_snapshot_history_states`)
  p_i(t)       =  adjusted-close price for symbol i on date t
  V_p(t)       =  Σ_j (q_j × p_j(t))    (portfolio market value at t)
  V_i(t)       =  q_i × p_i(t)          (position i's market value at t)

  contribution_i is in decimal; the schema reports
    contribution_pct = contribution_i × 100.

Episode-level residual:
  residual_pct  =  episode.magnitude_pct
                   − Σ_i contribution_i_non_null × 100
  (sum runs over positions with non-null contribution_i only)

Reconciliation invariant:
  |episode.magnitude_pct − (Σ_i contribution_pct + residual_pct)|  <  1e-9
  The engine MUST raise rather than emit values that violate this.

Top-N selection:
  Sort decomposable positions by abs(contribution_pct) descending; keep
  first N (default N = 5). Positions ranked 6+ aggregate into a single
  `other_contribution_pct` value preserving the reconciliation.
```

Edge cases:
- `p_i(t_peak)` or `p_i(t_trough)` null: `contribution_i = null`; surface
  as `trust='unavailable'` at the contributor level — never fabricate as zero.
- `V_p(t_peak) = 0`: entire decomposition undefined →
  `decomposition_trust = 'unavailable'`.
- Cash: `r_cash = 0` ⇒ `contribution_cash = 0`; cash weight counts in the
  denominator but cash is NOT listed as a contributor (zero row adds no
  signal).
- Position added after `t_peak`: no synthetic price pre-peak ⇒
  `contribution_i = null`; portfolio residual absorbs the gap.

Synthetic-history caveat:
- The decomposition answers "given my current portfolio composition, what
  would each position have contributed during this historical episode?" —
  NOT "what each position actually contributed when this happened in my
  real account history." The latter requires ledger history with per-day
  weights, which is out of current scope.

Academic precedent:
- Brinson, Hood & Beebower (1986), "Determinants of Portfolio
  Performance," *Financial Analysts Journal* 42(4): 39–44 — foundational
  arithmetic attribution framework
- Goldberg & Mahmoud (2017) §3, "Drawdown: from practice to theory and
  back again," *Mathematics and Financial Economics* 11(3): 275–297 —
  extends drawdown theory to position-level decomposition under
  static-weight assumption
- Bertsimas, Lauprete & Samarov (2004), "Shortfall as a risk measure:
  properties, optimization and applications," *Journal of Economic
  Dynamics and Control* 28(7): 1353–1381 — coherent contribution
  measures (referenced for context; not used as the operative formula)

Contract rule:
- never fabricate a zero contribution to fill a price-data gap; surface
  `null` + per-row `trust='unavailable'` instead
- `residual_pct` is always reported (never hidden) so the UI can surface
  partial-data states
- the reconciliation identity must hold to within 1e-9; violations raise
  rather than emit inconsistent data (same discipline as the CVaR ≥ VaR
  invariant in §Value-at-Risk and Distribution)

### Two drawdown constructions, only one of which is a price drawdown (US-34.7)

The product builds drawdowns over two different daily-state constructions, and
they do **not** share a dividend exposure. Conflating them produced a false
justification that sat in the code for eight days (Epic 34 F-11).

**Replay path (Dashboard).** `_compute_max_drawdown` chains the
`portfolio_value` basis over the imported replay's daily states. Dividends and
withholding taxes are **ledger entries**, so they land in the replayed cash
balance: the ex-date price drop is offset by the receipt and the chain is
already **total-return-like**. Measured on IB2026: $125.72 gross, −$17.93
withholding, $107.79 net, all present in the states. An unadjusted-close
concern does not apply here.

**Synthetic path (Risk tab).**
`_build_synthetic_snapshot_history_states_with_coverage` applies *current
holdings* to historical prices with a **flat cash balance** (today's ending
cash, held constant) and **no ledger**. A dividend therefore appears only as
the ex-date price drop, with nothing offsetting it, so this construction **is**
a price drawdown and overstates losses by roughly the yield across the
lookback. The magnitude scales with how dividend-heavy the *current* holdings
are and with the window — the card offers 252d and 504d.

Measured bound on the committed statement: of 18 current holdings only **PYPL**
both is held and paid a dividend in the window ($3.64 gross ≈ 0.006% of NAV), so
the overstatement here is negligible. The mechanism is real; the magnitude is
portfolio-specific, which is why it is bounded by a test rather than assumed
small.

Correcting the synthetic path needs total-return prices, which the provider does
not currently supply (F-9). Until then the construction is documented rather
than adjusted.

## Volatility and Relative Risk

### Standard-deviation denominator conventions (US-27.9 / audit F12)

Two denominator conventions deliberately coexist, per module:

```text
analytics/risk.py            sample (N−1)     realized vol, downside vol,
                                              tracking error, β/ρ helpers
analytics/correlation.py     population (N)   pearson/beta/R², per-holding σ,
                                              Diversification Ratio inputs
analytics/distribution.py    population (N)   distribution shape (documented
                                              in §Value-at-Risk and Distribution)
```

Ratio statistics (β, ρ, R², IR) are invariant to the choice — the denominator
cancels. Stdev-LEVEL outputs (vol %, tracking error %, DR inputs) differ by
the factor √(N/(N−1)) between surfaces for the same window (≈ 0.8% at N=60,
≈ 0.2% at N=252). Decision (US-27.9): DOCUMENT rather than standardize —
each module is internally consistent, cross-module ratio comparisons are
unaffected, and a global change would churn every pinned value and golden
for sub-percent display differences with no decision-relevant content.
Do not mix the two conventions inside one formula.

### Annualized realized volatility

```text
realized_vol = stdev(daily_returns) * sqrt(252)
```

### Downside volatility

```text
downside_t = min(return_t, 0)
downside_vol = stdev(downside_t) * sqrt(252)
```

### Tracking error

```text
active_return_t = portfolio_return_t - benchmark_return_t
tracking_error = stdev(active_return_t) * sqrt(252)
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`

Contract rule:
- benchmark-relative outputs may be computed internally but still withheld or suppressed at the contract boundary when trust attestation is weaker than required

### Information Ratio

Information Ratio (IR) measures risk-adjusted active return: how much excess
return the portfolio generated per unit of active risk taken relative to the
benchmark. It is the natural complement to tracking error — this project
already computes both, over the same underlying paired daily-return series,
but had never named the ratio in this document (documentation-traceability
gap closed here; the code has existed since before this section was written).

```text
mean_active_return  = mean(active_return_t)   over all paired dates
                       (active_return_t as defined in §Tracking error)

information_ratio = (mean_active_return * 252) / tracking_error

where:
  tracking_error       = the annualized stdev of active_return_t (§Tracking error)
  mean_active_return   = simple arithmetic mean of the daily active-return series
                         (paired portfolio/benchmark dates only)
  the numerator annualizes the daily mean by the trading-day count (252),
  matching the denominator's annualization basis

Interpretation:
  IR > 0: positive risk-adjusted active return (out-performed per unit of
          tracking error taken)
  IR = 0: no active return, or active return exactly offset by its own noise
  IR < 0: negative risk-adjusted active return (under-performed per unit of
          tracking error taken)

Edge cases:
  fewer than 2 paired portfolio/benchmark daily returns: tracking_error = null,
    information_ratio = null
  tracking_error = 0 (active returns had zero variance — e.g. the portfolio
    tracked the benchmark exactly every day): information_ratio = null
    (division undefined, never fabricated as 0 or infinity)
```

Distinct from the schema's `active_return_pct` field (same `RelativeRiskSummary`
struct): `active_return_pct` is the **compounded** portfolio return minus the
compounded benchmark return over the whole window (a cumulative total-period
figure), while the Information Ratio's numerator is the **annualized mean
daily** active return (a per-day average, annualized). Both are legitimate
but answer different questions — do not substitute one for the other in a UI
label.

Implementation:
- `services/quant-engine/app/analytics/risk.py` — the function building
  `RelativeRiskSummary` (paired-returns → `tracking_error_pct` /
  `active_return_pct` / `information_ratio`)

Academic precedent:
- Grinold, R.C. & Kahn, R.N. (2000). *Active Portfolio Management*, 2nd ed.,
  Ch. 6 (McGraw-Hill) — the canonical Information Ratio treatment (IR as the
  central "quality of active management" statistic, IR = active return /
  active risk).
- Goodwin, T.H. (1998). "The Information Ratio." *Financial Analysts
  Journal*, 54(4), 34–43 — practitioner-level treatment of computation
  conventions and common pitfalls.

Contract rule:
- `information_ratio` and `active_return_pct` carry the same trust/
  withholding semantics as `tracking_error_pct` in the same
  `RelativeRiskSummary` struct: benchmark-relative refusal means these
  fields may be `null` even when `availability.status = ok`, with
  `run_metadata.investor_economics_status` as the authoritative explanation
  (see `docs/contracts/diagnostics-fields.md`).
- Never fabricate a ratio when `tracking_error = 0`; `null` is the only
  correct output for that edge case.

## Statistical Factor Model

The project implements a rolling ETF-proxy factor model.

Methodology string in code:

```text
Orthogonalized rolling ridge factor model using US ETF proxies for market, style, sector, and macro exposures; UCITS symbols are shown separately as EU execution examples.
```

Implementation:
- `services/quant-engine/app/analytics/risk.py`
- `factor_model_methodology()`

Named policy constants (US-24.2): the model/classification thresholds live as
named constants at the top of `risk.py` rather than inline literals —
`FACTOR_MODEL_MIN_SHARED_OBSERVATIONS` (minimum shared daily-return observations
to fit a model; below it the model is `insufficient_history`), the
`VOLATILITY_REGIME_*_PERCENTILE` cutoffs (current-20d-vol percentile → calm /
normal / stressed), and the factor→UCITS mapping-quality rubric weights/hard-caps/
label thresholds. These are **documented policy/heuristic values, not academically
derived** — tune them only as a reviewed change; no value changed in the US-24.2
extraction (golden-master-pinned in `test_analytics.py`).

### Per-window orthogonalization (corrected methodology — US-9.4)

Gram-Schmidt orthogonalization is performed **within each rolling window**, not
over the full date range. This guarantees that the orthogonalized factors are
mutually uncorrelated within the window used for regression, so each coefficient
has a clean "partial loading" interpretation.

```text
For each date t with window w = [t−w+1, t]:

  1. Slice raw factor returns to the window:
       f_k(window) = daily returns of proxy_k on dates [t−w+1, t]

  2. Gram-Schmidt within the window (orthogonalization order: market=1,
     growth=2, value=3, small_cap=4, technology=5, financials=6, ...):
       F*_1 = f_1          (Market/SPY — unmodified)
       F*_k = f_k − Σ_{j<k} (<f_k, F*_j> / <F*_j, F*_j>) × F*_j
              where <a, b> = Σ_i a_i × b_i  (inner product over the window)

  3. Ridge-stabilized OLS:
       X = [1, F*_1, ..., F*_K]       (K = active factor count)
       β = (X'X + λ·D)⁻¹ X'y
       D = diag(0, 1, 1, ..., 1)      (ridge on factor columns only)

       Ridge floor: λ = 1e-5 for all windows.
       Per-window Gram-Schmidt guarantees orthogonal factors within each window,
       so X'X is well-conditioned and a small λ provides numerical stability
       without material coefficient shrinkage. (λ=0.01 would shrink a typical
       daily-return-scale coefficient by >80% — unacceptable bias.)

  4. Reported loading for factor k = β_{k+1}
     Interpretation: unit of portfolio return per unit of orthogonalized factor k
                     after controlling for all higher-priority factors.
```

Edge cases:
- Window has fewer than `WINDOW_MIN_OBSERVATIONS[w]` dates: return null for all
  factors on that date; never partial-fill.
- A factor's orthogonalized residual has zero variance (collinear with earlier
  factors in this window): skip that factor's coefficient (null), do not
  propagate to later factors.
- A degenerate (singular / zero-variance) window that makes the OLS solve
  return a **non-finite** value (NaN/inf): that loading / R² / residual-vol is
  null for that date — never NaN (US-21.3; NaN silently passes null-checks and
  breaks JSON serialization downstream).
- R² reported per point is the in-sample OLS fit; it is diagnostic only and
  must not be used to claim out-of-sample explanatory power.

Academic precedent:
- Fama, E.F. & French, K.R. (1993). "Common risk factors in the returns on
  stocks and bonds." *Journal of Financial Economics*, 33(1), 3–56.
  (Orthogonal factor construction over the estimation window.)
- Connor, G. & Korajczyk, R. (1988). "Risk and return in an equilibrium APT."
  *Journal of Financial Economics*, 21(2), 255–289.
  (Rolling estimation consistency for factor models.)
- Bai, J. & Ng, S. (2002). "Determining the number of factors in approximate
  factor models." *Econometrica*, 70(1), 191–221.
  (Stability of factor estimates under short windows.)

Contract rule:
- factor-model and risk-contribution paths degrade explicitly when their return-basis trust is not proven
- rolling window coefficients are in-sample regression coefficients; they carry
  synthetic-history trust class (not verified), because they apply current
  holdings weights to historical price data
- a Market loading outside [−2, +4] for a long-only equity portfolio indicates
  numerical instability; the ridge floor must be sufficient to prevent this

### Sector exposure vs. factor loading — why they can diverge

**Sector exposure** (Exposure tab) and **factor loading** (Rolling Factor Analysis) measure
fundamentally different quantities and will routinely disagree. Treating a negative
Technology factor loading as evidence the portfolio is "short tech" when the Exposure tab
shows 32% Technology is a misreading of both numbers.

```text
Sector exposure  = Σ w_i  for all holdings i classified in sector S
                 = portfolio weight in that sector by current holdings composition
                 Source: snapshot analytics (holdings-based, no return history needed)

Factor loading   = β_k in the orthogonalized OLS regression:
                   r_portfolio = α + β_market·F*_market + β_growth·F*_growth
                                   + β_value·F*_value + β_small_cap·F*_small_cap
                                   + β_technology·F*_technology + ...
                 where F*_technology = XLK_returns − proj(XLK onto all prior factors)
                 = sensitivity of portfolio RETURNS to the RESIDUAL sector effect
                   after removing everything the higher-priority factors already explain
                 Source: synthetic history (returns-based, 20/60/252d rolling window)
```

**Why a negative Technology loading is compatible with a large Technology sector weight:**

The orthogonalization order places Growth (QQQ, order 2) before Technology (XLK, order 5).
QQQ (Nasdaq-100) is ~50% Technology sector companies by GICS classification and overlaps
heavily with XLK. Gram-Schmidt removes the QQQ component from XLK before Technology enters
the regression. The residual `F*_technology` then represents the *pure sector-specific* tech
move not explained by the growth/QQQ factor.

For a portfolio whose technology holdings are dominated by mega-cap names (Apple, Microsoft,
Nvidia) that also constitute the bulk of QQQ, the Growth factor absorbs most of the tech
return variation. The residual `F*_technology` effect can be small, noisy, or negative over
any given 20-day window — even when 30%+ of the portfolio is classified as Technology
by GICS.

Concretely, β_technology = −0.64 means:
  "Over the last 20 trading days, after accounting for broad market, growth-style, value,
   and size moves, the pure XLK sector effect had a mild negative relationship with this
   portfolio's daily returns."

This is not evidence of a short position or a data error. It is evidence that:
  (a) the portfolio's technology exposure is better captured by the Growth factor than by
      the residual sector factor, and/or
  (b) the specific XLK sector constituents (non-QQQ-overlap tech) moved opposite to the
      portfolio during this window.

Academic reference:
- Grinold, R.C. & Kahn, R.N. (2000). *Active Portfolio Management*, 2nd ed., Ch. 2–3
  (McGraw-Hill). (Factor loading vs. portfolio weight distinction; why holdings composition
  and return attribution diverge in orthogonalized multi-factor models.)
- Barra / MSCI factor model documentation: sector factor loadings are orthogonal to style
  factors by construction; a neutral sector loading is expected when style factors dominate
  return variation within that sector.

Consumer rule:
- Do not interpret a negative sector factor loading as a short position.
- Do not treat sector factor loading and sector holdings weight as interchangeable.
- The factor loading describes return behaviour over the rolling window; the sector
  weight describes current composition. They answer different questions.

## Sector/Industry Classification — Source and Resolution (US-37.1)

Every "Sector exposure" number in this document (§ Sector exposure vs. factor
loading, § Risk Contribution and Concentration's sector HHI) takes a
per-holding sector **classification** as a given input. This section
documents where that classification itself comes from — not a numeric
formula, a categorical resolution order, since the underlying fact ("what
sector is this equity in") is not computed, it is sourced.

**Scope note, stated explicitly so this section is not misread as broader
than it is: this section covers direct-holding equity classification only.**
It does **not** cover ETF look-through constituent classification — the
sector inference `risk.py`'s `build_lookthrough_sector_exposure(...)` /
`_infer_sector_from_sources(...)` perform when unpacking an ETF's underlying
constituents remains its own separate, hardcoded keyword/proxy-ticker
mechanism, undocumented here, and unchanged by US-37.1
(`docs/tech-debt-register.md`, `risk.py:1485-1499,1537-1549`, tracked as a
distinct, still-open gap). Do not assume that mechanism follows the
resolution order below.

### Resolution order (equity branch only)

```text
classify_equity(imported_instrument) -> (sector: str | None, classification_source):

  1. Static registry lookup (unchanged, pre-dates US-37.1):
     if normalize_symbol(imported.symbol) is a curated INSTRUMENT_DEFINITIONS entry:
         return (curated_sector, "static")

  2. Identity-gated FMP lookup (US-37.1, opt-in — see "Opt-in wiring" below):
     if a MarketDataService instance was supplied:
         profile = MarketDataService.get_company_profile(imported.symbol)
         if lookup raises, or profile is empty/has no `sector`:
             return (None, "unavailable")
         mapped_sector = SECTOR_TAXONOMY_MAP.get(profile["sector"])
         if mapped_sector is None:              # FMP sector string not in the map
             return (None, "unavailable")
         if normalize_isin(imported.isin) == normalize_isin(profile.get("isin"))
            and both are non-empty:
             return (mapped_sector, "fmp_identity_confirmed")
         return (None, "unavailable")            # ISIN mismatch OR no ISIN evidence
     else:
         return (None, None)                     # no lookup attempted at all

  3. Nothing resolved a sector -> instrument.sector = None.
```

Implementation:
- `services/quant-engine/app/instruments/equity_sector_resolution.py` ->
  `resolve_equity_sector(...)`, `SECTOR_TAXONOMY_MAP`
- `services/quant-engine/app/instruments/registry.py` ->
  `InstrumentRegistry.classify_imported_instrument(...)` (equity branch),
  `InstrumentRegistry._merge_known_instrument_metadata(...)` (static-hit case)

**Opt-in wiring.** The FMP lookup is not unconditional. `classify_imported_instrument`
and `attach_snapshot_metadata` take a keyword-only `market_data: MarketDataService | None`
parameter, defaulting to `None`. Only `analytics/overview.py::build_portfolio_overview(...)`
constructs a `MarketDataService()` and passes it in. `analytics/risk.py`'s two
`attach_snapshot_metadata(...)` call sites (`build_lookthrough_exposure`,
`build_etf_overlap_pairs`) do not pass `market_data`, so they never trigger an FMP
call for this — both only read `.asset_class` from the returned metadata, never
`.sector`. This is a deliberate blast-radius decision, not an oversight: it keeps
Stress/Drawdown/VaR routes free of added FMP latency for a value nothing there
consumes.

### The identity gate, and why it is load-bearing

A bare-ticker FMP profile lookup is **not** trusted on its own. The statement's
own ISIN (captured by the importer, e.g. IB's `Security ID` column) must match
the FMP profile's `isin` field before an FMP-sourced sector is used at all.
This mirrors the evidence-gated ISIN-comparison pattern already used for
registry-known holdings in `app/services/instrument_identity.py`
(`normalize_isin`) — reused here rather than reimplemented.

The gate exists because ticker collision across exchanges is a documented,
recurring failure mode in this codebase, not a theoretical risk: a bare
symbol can resolve to a different, unrelated security on FMP than the one the
statement actually holds (see `app/core/symbols.py`'s `DFND`/`SEMI`/`CIBR`
comments for three prior incidents this project has already had to guard
against). Without the ISIN check, a collision would silently assign the wrong
company's sector — a confident, wrong answer, not a visible failure. Missing
ISIN evidence on either side is therefore treated the same as a mismatch:
conservative by default, per guardrail 4 (never fabricate; never fill a
plausible value from incomplete evidence).

### Sector-taxonomy mapping table

FMP's `sector` string values are not verbatim GICS sector names; they diverge
from this project's canonical sector vocabulary on 5 of the 11 sectors below.
Passing an FMP string through unmapped would silently fragment sector
aggregates (e.g. "Healthcare" and "Health Care" as two separate buckets),
corrupting `sector_hhi` and `top_sectors` without any visible error — so an
FMP `sector` value not present in this table is treated as unresolved
(never passed through raw as an ad hoc 12th bucket). This is the complete,
current `SECTOR_TAXONOMY_MAP` (`equity_sector_resolution.py`):

| FMP `sector` value | Project sector value |
|---|---|
| `Technology` | `Technology` |
| `Energy` | `Energy` |
| `Industrials` | `Industrials` |
| `Real Estate` | `Real Estate` |
| `Utilities` | `Utilities` |
| `Communication Services` | `Communication Services` |
| `Healthcare` | `Health Care` |
| `Financial Services` | `Financials` |
| `Consumer Cyclical` | `Consumer Discretionary` |
| `Consumer Defensive` | `Consumer Staples` |
| `Basic Materials` | `Materials` |

An FMP `sector` string not in this table (a new or renamed FMP sector) falls
through to unresolved, exactly like no-coverage — see below.

### `classification_source` — provenance, not a trust-ladder rung

`Instrument.classification_source: Literal["static", "fmp_identity_confirmed",
"unavailable"] | None` (`app/schemas/instruments.py`) records which mechanism
produced (or failed to produce) `Instrument.sector`. It is **backend-internal
only** — see `docs/contracts/exposure-fields.md` for the explicit statement
that it is not currently serialized to the client.

- `"static"` — the curated `INSTRUMENT_DEFINITIONS` registry resolved it.
- `"fmp_identity_confirmed"` — the FMP lookup resolved it, and the identity
  gate above passed (statement ISIN and FMP profile ISIN both present and
  equal). Deliberately **not** named `"verified"` or any `*verified*` value —
  that word is reserved for `verified_total_return`'s distinct, narrower
  meaning; reusing it here would be exactly the truth-class mixing
  guardrail 3 forbids.
- `"unavailable"` — an FMP resolution attempt was made and did not clear the
  gate. This single value **collapses several distinct sub-cases** by design:
  no FMP coverage for the symbol, an empty/missing `sector` field, an FMP
  `sector` string absent from the taxonomy table, an ISIN mismatch (the
  "wrong security" case), and missing ISIN evidence on either side. Nothing
  downstream today consumes a finer-grained distinction (e.g. a `withheld`
  state for "checked and distrusted" vs. `unavailable` for "never checked"),
  and inventing an exposed 4th value nothing reads would itself be an
  untraceable addition. The sub-case distinction survives only in code
  structure (`resolve_equity_sector`'s separate `return` statements), not as
  an exposed field.
- `None` — the classification mechanism above was never invoked on this
  instrument's path at all: the ETF branch (its own separate keyword
  classifier, unaffected by this section), futures, the no-imported-instrument
  catch-all in `attach_snapshot_metadata`, or a static-registry hit reached by
  any path other than `_merge_known_instrument_metadata`. `None` is not a
  claim that no provenance exists — only that this mechanism did not run on
  that path.

### The `"Unclassified"` sector bucket

`Instrument.sector` is genuinely nullable at the domain layer once no source
resolves it (`sector = None`, not the string `"Other"`). `sector_allocation`
and `sector_position_breakdown` (`PortfolioOverview`, consumed by the
Exposure tab's sector cards) are string-keyed aggregates that cannot carry
`None`, so the conversion happens exactly once, at the aggregation seam in
`analytics/overview.py`:

```python
sector = instrument.sector or UNCLASSIFIED_SECTOR_LABEL   # UNCLASSIFIED_SECTOR_LABEL = "Unclassified"
```

`"Unclassified"` is a new, distinct, honestly-labeled bucket — it is never
merged into `"Other"` (the pre-existing literal `InstrumentRegistry.get_sector(...)`
still returns for its own separate, out-of-scope fallback path — see "Residual
`get_sector()` inconsistency" below) and it is never dropped from the sector
weight total. It participates in `sector_hhi` / `top_sectors` /
`top_sector_weight` (`exposure_engine.py::_build_current_state_concentration`)
automatically, the same as any other bucket, because those already iterate
the full `sector_allocation` list rather than a fixed enumeration.

**Residual `get_sector()` inconsistency, named so it is not mistaken for a
gap in the fix above.** `InstrumentRegistry.get_sector(symbol)` is a separate,
independently-tested public method (its own `"Other"` contract is pinned by
`test_instrument_registry.py::test_unknown_symbol_falls_back_to_other`) that
still returns the literal `"Other"`. `overview.py`'s aggregation only calls it
in the (currently unreachable in practice) case where `attach_snapshot_metadata`
has no metadata entry at all for a position — every position is confirmed to
get an entry today, so this branch is dead in practice, not touched or
repurposed by US-37.1, and left as a named, accepted residual inconsistency.

### Caching

`get_company_profile(...)`'s underlying `FmpClient.get_profile()` call no
longer shares the 300-second live-quote cache TTL. It uses a dedicated
`Settings.fmp_profile_cache_ttl_seconds` (default `2592000`, 30 days), because
a company's sector classification changes on a multi-year cadence, not a
5-minute one. This is the existing namespace-separated `JsonFileCache`
(`"profile"` cache namespace) doing the work — no new persistence layer, no
classification-record table. A consequence worth knowing: a transient
no-coverage FMP response (confirmed reproducible live for at least one
symbol during this story's research pass) is now sticky for up to 30 days
before the next natural re-attempt; `manage_cache.py clear` is the only
forced-refresh path.

Contract rule:
- an equity's sector is either curated (`"static"`), FMP-sourced and
  identity-confirmed (`"fmp_identity_confirmed"`), or unresolved — there is no
  fourth outcome, and an unresolved equity is disclosed as `"Unclassified"`,
  never silently folded into any named sector including `"Other"`
- an FMP-sourced sector is never used without a matching, present ISIN on
  both the statement and the FMP profile
- an FMP `sector` string not present in `SECTOR_TAXONOMY_MAP` is never passed
  through as a new, unmapped sector value
- ETF look-through constituent classification is a separate, undocumented
  mechanism — do not extend the guarantees above to it without a matching doc
  update

## Risk Contribution and Concentration

The project reports position and factor risk contribution metrics plus concentration diagnostics.

### Base-currency weighting rule (US-30.5a / audit F-7)

Every portfolio weight — and therefore every concentration, HHI, sector share,
look-through value, risk share, and diversification metric derived from one —
is computed on **base-currency** position values.

```text
w_i = value_base(i) / Σ_j value_base(j)

value_base(i) = market_value_i × fx_rate(currency_i → base)   when a rate exists
              = market_value_i                                 otherwise (carried
                                                               unconverted, disclosed)

Rates: the statement's own implied period-end rates
       (statement_totals.fx_rates, US-28.1 broker truth). STATIC across the
       window — correct levels as of the statement date; FX return dynamics
       are not modeled (that is Epic 26 scope).
```

Raw-summing `market_value` across currencies mixes numerals. On the committed
IB2026 statement the raw sum is $58,588.76 while the converted total is
$61,238.53 — which reproduces the statement's own `stock_total` to the cent.
**The statement is the arbiter**, so this is a unit-correctness rule.

Edge cases / contract rules:
  no rate for a non-base currency: the position is carried UNCONVERTED and its
    currency disclosed — never dropped from the denominator (that would
    silently shrink the portfolio and inflate every other weight), never
    converted 1:1
  disclosure is mandatory: `fx_static_rate_currencies` (converted at the
    static period-end rate) and `fx_fallback_currencies` (carried
    unconverted). Exactly one tier per non-base currency
  conversion never upgrades trust — Exposure stays snapshot/synthetic class

Implementation:
- `services/quant-engine/app/analytics/currency.py`
- consumers: `analytics/overview.py`, `analytics/risk.py`,
  `services/exposure_engine.py`, `services/intra_correlation_engine.py`

### Per-position minimum-observation rule (US-30.5b / audit F-9)

A **published** per-position estimated statistic — beta, correlation, or
annualised volatility — requires at least `MIN_DAILY_OBSERVATIONS` (20)
overlapping daily return observations, consistent with §Beta ("len(series)
< 20 → null") and §Rolling Pearson Correlation. Below the floor the statistic
is **null** (withheld), never a confident number from a handful of days; the
position's non-estimated fields (weight, market value, risk share) still
render.

```text
beta_i / correlation_i / volatility_i:
  null            when n_overlap(i) < MIN_DAILY_OBSERVATIONS
  computed value  otherwise
```

Scope: this floor governs statistics published *per position* — the
`_build_position_risk_contributions` volatility that feeds the Risk Summary
card. *(US-24.7 correction: this paragraph also named a public
`build_position_risk_contributions` as the source of per-position
beta/correlation. That function had **no production caller** — the live path is
the private one above — and it has been deleted along with the response model
only it used. The doc previously pointed a reader at a code path that never
executed, which is exactly what guardrail #1 forbids.)* The covariance-matrix cells
feeding the variance decomposition keep their pairwise `≥ 2` floor (US-27.3) —
they are intermediate inputs, not published per-position betas, and the
decomposition surfaces its own `observation_count`.

Implementation:
- `services/quant-engine/app/analytics/risk.py`
  (`MIN_DAILY_OBSERVATIONS` from `core/constants.py`)

### Risk share

Each position or factor's variance-based share of total portfolio risk.

```text
risk_share_i = variance_contribution_i / total_variance

where:
  variance_contribution_i = the position's (or factor's) contribution to
                             total portfolio return variance (arithmetic
                             decomposition of the covariance matrix / factor
                             model residual variance)
  total_variance           = total_variance_raw (positions) or
                             factor_total_variance (factors) — the
                             denominator matching the same decomposition
  risk_share_i is a fraction in [0, 1] — NOT a percentage. Multiply by 100
  only at the display layer.

Covariance date-alignment convention (US-27.3):
  every covariance cell is computed over the pair's INTERSECTED date set
  (window dates ∩ left coverage ∩ right coverage) so returns are always
  paired same-day — the same pairwise-drop discipline as §Rolling Pearson
  Correlation. A cell with fewer than 2 common observations is null.

Denominator convention (US-27.5):
  each decomposition's shares use ITS OWN total as denominator, so non-null
  shares sum to 1 within that decomposition:
    factor risk shares    → / factor_total_variance
    position risk shares  → / the position decomposition's total
  Factor and position shares are therefore each internally complete but NOT
  cross-comparable as "share of the same total". The share-of-TOTAL-variance
  view is a separate pair of fields — factor_risk_share_total +
  specific_risk_share — which partition total_variance (factor + specific)
  and sum to 1 when both are non-null.

Edge cases:
  total_variance <= 0, or variance_contribution_i is null: risk_share_i = null
```

### Top-N risk share

```text
top_N_risk_share = Σ (the N largest risk_share_i values, descending)

Reported today: top_1 and top_3 for factors; top_1 and top_5 for positions.

Edge case:
  no valid (non-null) risk_share values: top_N_risk_share = null
```

### Herfindahl-Hirschman Index (HHI)

A standard concentration index over the same risk_share distribution used
above — one HHI for factors, one for positions.

```text
HHI = Σ_i (risk_share_i)^2   over all i with risk_share_i non-null

Range: (0, 1]
  HHI = 1     : all risk concentrated in a single position/factor
  HHI = 1/n   : risk spread perfectly evenly across n positions/factors
  lower HHI   : more diversified risk contribution

Edge case:
  no valid (non-null) risk_share values: HHI = null
```

This is the **risk-contribution** HHI (history-derived, synthetic-history
trust class) — a distinct computation from the **current-state holdings**
HHI reported on the Exposure tab (`exposure_engine.py` `position_hhi`, computed
over portfolio *weights*, snapshot trust class, and used there to derive
"Effective Holdings" = `1 / HHI`). Both use the same Σw² formula shape but
over different inputs (risk share vs holdings weight) and different truth
classes — do not conflate the two numbers even though they share a name.

Implementation:
- `services/quant-engine/app/analytics/risk.py` — `_herfindahl_index(...)`,
  `_sum_top_risk_shares(...)`
- `services/quant-engine/app/services/exposure_engine.py` — the separate
  current-state `position_hhi` (snapshot weights, not risk share)

Academic precedent:
- Herfindahl, O.C. (1950), "Concentration in the U.S. Steel Industry"
  (doctoral dissertation, Columbia University).
- Hirschman, A.O. (1964), "The Paternity of an Index," *American Economic
  Review* 54(5): 761–762 (documents the index's independent origin in both
  Hirschman 1945 and Herfindahl 1950; conventionally cited as either
  "Herfindahl index" or "Herfindahl-Hirschman Index").

Contract rule:
- diagnostics-side concentration fields (`risk_share`, top-N risk share, HHI)
  are history-derived risk concentration outputs, synthetic-history trust
  class — never verified.
- current-state holdings concentration (`exposure_engine.py` `position_hhi`,
  "Effective Holdings") remains a separate snapshot truth class in exposure
  contracts; the two `position_hhi`-shaped numbers are not interchangeable.
- `top_*_risk_share` and `*_hhi` fields are fractions in [0, 1]; UI consumers
  must multiply by 100 before rendering a `%` suffix — never emit the raw
  fraction with a `%` sign appended (that renders a value ~100x too small).

### Factor Loading Drift

A descriptive summary of *how* the rolling factor loadings (above) have moved
over a selected window. For each factor `k`, drift is the first difference of
the per-window rolling loading between the latest and the reference observation
of the same `rolling_loadings_<window>` series:

```text
drift_k = β_k(t_latest) − β_k(t_reference)

where:
  β_k(t)       = the rolling OLS loading for factor k at date t (output of the
                 per-window orthogonalized model above; see §Statistical Factor Model)
  t_reference  = first date of the window's loading series after leading-null
                 trimming (the earliest date at which any displayed factor has a
                 filled window)
  t_latest     = last date of that same series
  window       = rolling estimation window: 20, 60, or 252 trading days
```

Drift is **not a new estimate** — it is a plain difference of two loadings the
factor model has already produced. No regression, orthogonalization, or
re-fit is performed to compute it. The reference point is deterministic (the
first filled date), not user-selectable.

Edge cases:
- A factor whose reference *or* latest loading is null in the selected window is
  excluded from the drift summary entirely — never imputed as a 0 drift.
- If the selected window's loading series is empty after leading-null trimming
  (insufficient history), no drift is reported and the surface fails closed.
- A factor with equal reference and latest loadings reports `drift_k = 0`
  (a real "no drift" reading, distinct from "excluded").

Academic precedent:
- Ferson, W.E. & Schadt, R.W. (1996). "Measuring Fund Strategy and Performance
  in Changing Economic Conditions." *Journal of Finance*, 51(2), 425–461.
  (Conditional, time-varying factor betas.)
- Jagannathan, R. & Wang, Z. (1996). "The Conditional CAPM and the
  Cross-Section of Expected Returns." *Journal of Finance*, 51(1), 3–53.
  (Time-varying exposures as a function of the conditioning state.)
- Rolling-window beta estimation as a drift proxy follows the standard
  rolling-regression convention (cf. Fama & MacBeth 1973). The drift statistic
  itself (`Δβ`) is a first difference requiring no further estimation theory.

Implementation:
- Computed client-side in
  `apps/desktop/src/features/portfolio/FactorDriftSummaryCard.tsx` as a
  presentation-layer rebasing of the engine-computed
  `statistical_factor_model.rolling_loadings_<window>` series; no backend route.

Contract rule:
- Drift carries the **synthetic-history** trust class (it inherits the loadings'
  trust): the loadings apply current holdings to historical proxy prices and are
  never verified broker return basis. The card renders a `Synthetic` badge and
  fails closed (EmptyState) when the window has insufficient history.
- See `docs/contracts/factor-drift-fields.md` for the field-level inventory and
  UI rendering rules.

## Currency Exposure

*Implemented by US-26.1 (Epic 26). `app/analytics/currency_exposure.py`,
surfaced as the Exposure tab's Currency Exposure card.*

How much of the portfolio is denominated in each currency, and how much is not
in the base currency. `ImportedPosition.currency` and
`ImportedStatement.base_currency` are captured on every import; before US-26.1
nothing aggregated them, so a researcher holding UCITS ETFs traded in EUR/GBP
carried currency risk visible on no tab.

### Currency exposure by weight (snapshot)

```text
currency_weight_c = Σ_i base_value_i   (holdings i with currency_i = c)
                    ──────────────────────────────────────────────────
                    Σ_j base_value_j   (all holdings j)

where:
  base_value_i    = position i's market value CONVERTED to the base currency
                    (analytics/currency.py — the same conversion every other
                     Exposure weight uses)
  currency_i      = ImportedPosition.currency (already imported; not derived)
  base_currency   = ImportedStatement.base_currency
  non_base_weight = 1 − currency_weight_{base_currency}

Edge cases:
  base_currency = null: per-currency weights are still computable, but
    non_base_weight = null — there is no baseline to compare against, and 0.0
    would read to the researcher as "no currency risk"
  no positions / zero total value: empty weights, non_base_weight = null,
    no division
  a currency with no FX rate: CARRIED UNCONVERTED (US-27.8) — still counted in
    the denominator, never dropped and never converted 1:1, and disclosed via
    `fx_fallback_currencies`. Such a currency's own weight is the least
    reliable number on the card, and the card says so.
```

**Group by original currency; measure in one unit.** Each position is converted
to the base currency *first*, then grouped by the currency it is denominated
in. Summing raw `market_value` across currencies — as this section originally
specified — is the **F-7 defect** US-30.5a fixed as Critical: on IB2026 the raw
sum is $58,588.76 against the converted $61,238.53, which reproduces the
statement's own `stock_total` to the cent. Reintroducing it on the card whose
subject *is* currency would be the worst possible place for it. The denominator
is therefore identical to every other Exposure weight's, pinned by a test, so
this card can never contradict the concentration or sector cards beside it.

**On the "unclassified" bucket this section used to specify:** it is
unreachable. `ImportedPosition.currency` is
`str = Field(min_length=3, max_length=3)`, so a snapshot carrying a
currency-less position cannot be constructed. (The original text was also
self-contradictory — a position cannot be both excluded from the denominator
and shown as a residual share of it.) The fabrication it anticipated is real
but happens **upstream**: the request-path snapshot builder coerces
`currency=item.currency or request.base_currency or 'USD'`, labelling a
currency-less position before any analytic sees it. That is recorded as its own
tech-debt row rather than hidden behind a bucket that can never fill; a schema
test pins the constraint so relaxing it forces the question to be answered.

This is a **snapshot analytics** truth class (current holdings only, no
historical prices, no market-data fetch) — the same class as sector exposure,
and it carries no `Synthetic` badge.

Academic precedent:
- Solnik, B. (1974). "An equilibrium model of the international capital
  market." *Journal of Economic Theory*, 8(4), 500–524 — currency as a distinct
  exposure in an international portfolio.
- Perold, A.F. & Schulman, E.C. (1988). "The Free Lunch in Currency Hedging."
  *Financial Analysts Journal*, 44(3), 45–50 — why currency exposure is
  measured and reported separately from asset exposure.
- CFA Institute (2020). *GIPS for Firms*, §2.A.1 — portfolio values are stated
  in a single base currency, which is why the denominator converts.

  distinct concern from sector/look-through exposure, which lives in
  `risk.py`; per the `quant-research` skill's own guidance, a genuinely new
  concern gets its own file rather than growing `risk.py` further)

Academic precedent:
- Solnik, B. (1974). "Why not diversify internationally rather than
  domestically?" *Financial Analysts Journal*, 30(4), 48–54 — foundational
  treatment of currency as a distinct risk dimension in a multi-currency
  portfolio.
- Eun, C.S. & Resnick, B.G. (1988). "Exchange rate uncertainty, forward
  contracts, and international portfolio selection." *Journal of Finance*,
  43(1), 197–215.

Contract rule:
- Currency exposure by weight is `snapshot analytics` trust class — never
  `verified` (it reflects the imported statement's own position-currency
  fields, which are broker-truth-adjacent but not independently verified
  against a market-data source), never `synthetic`.
- A `null` position currency is never coerced to the base currency; it is
  reported as its own "unclassified" bucket so the weights still sum to 100%
  without silently understating real FX exposure.

### Currency Risk Contribution (historical)

*Implemented by US-26.2. `services/quant-engine/app/analytics/currency_risk.py`
(pure decomposition) + `app/services/currency_risk_engine.py` (market-data
wiring) + `POST /engines/currency-risk/run`, surfaced as the Exposure tab's
Currency Risk Contribution card. Research brief:
[`docs/finance/research/currency-risk-contribution-brief.md`](research/currency-risk-contribution-brief.md),
which resolved the two questions that previously blocked this section.*

**Measured on the committed portfolio** (60d window, live FMP data): the
securities leg carries **96.70%** of return variance, currency **3.31%**, and
the interaction leg **−0.013%** — summing to exactly 1.0. Per-currency
contributions (EUR 0.0243 + GBP 0.0089) reconcile to the currency share.

How much of a portfolio's historical return volatility came from currency moves
rather than from the underlying securities.

**Per-holding decomposition — an exact identity, not an approximation.** An
earlier draft of this section wrote `r_base ≈ r_local + r_fx + (r_local × r_fx)`
and floated dropping the cross term. Both were wrong:

```text
(1 + r_base_i(t))  =  (1 + r_local_i(t)) × (1 + r_fx_c(t))

therefore, EXACTLY:

r_base_i(t)  =  r_local_i(t) + r_fx_c(t) + [ r_local_i(t) × r_fx_c(t) ]
                └── local leg ┘ └ fx leg ┘ └──── interaction leg ────┘

where:
  r_local_i(t) = holding i's daily return in the currency its resolved market
                 line QUOTES in — the registry FUND currency (US-31.5), never
                 the broker's listing currency (DEFS is listed EUR but DEFS.L
                 quotes USD; a wrong assignment silently moves return between
                 the legs)
  r_fx_c(t)    = daily return of the pair converting currency c to base
  for c = base: r_fx ≡ 0, so the fx and interaction legs are exactly 0

Edge cases:
  a day missing either the price or the FX quote yields NO legs — the day is
    excluded from every series, never zero-filled and never carried
  fewer than MIN_DAILY_OBSERVATIONS (20) paired days: all outputs null
```

**The interaction leg is retained and reported separately.** Measured on the
live FMP series over 2026-01-01..2026-06-30, the cross term is negligible per
day but **compounds**:

| Holding | fund ccy | local σ | fx σ | cross max/day | cumulative gap if dropped |
|---|---|---|---|---|---|
| SXRV | EUR | 1.0892% | 0.4031% | 2.07 bp | −0.018 pp |
| SEMI | GBP | 2.5571% | 0.4455% | 5.41 bp | **+0.504 pp** |

Half a percentage point of cumulative return over six months on a single
holding, and the error grows with window length — so it would be worst exactly
on the long windows a risk view cares about. Ankrim–Hensel conventionally
allocates the cross term to currency; this project reports it as its **own third
leg** instead, because folding it into either side would overstate that leg by
an amount the researcher cannot see. Three legs that sum exactly to the
base-currency return is the honest construction.

**Portfolio legs and the variance split.**

```text
L(t) = Σ_i w_i × r_local_i(t)                       (local leg)
F(t) = Σ_i w_i × r_fx_c(i)(t)                       (currency leg)
X(t) = Σ_i w_i × [r_local_i(t) × r_fx_c(i)(t)]      (interaction leg)

  w_i = base-currency weight (analytics/currency.py — the same denominator
        every Exposure weight uses, US-30.5a F-7)

  Identity, asserted by test: L(t) + F(t) + X(t) == Σ_i w_i × r_base_i(t)

Variance splits exactly by bilinearity of covariance, with no residual:

  Var(r_p) = Cov(L, r_p) + Cov(F, r_p) + Cov(X, r_p)

  currency_variance_share    = Cov(F, r_p) / Var(r_p)
  local_variance_share       = Cov(L, r_p) / Var(r_p)
  interaction_variance_share = Cov(X, r_p) / Var(r_p)

  The three shares sum to EXACTLY 1.0 by construction.

Reported alongside (a different question — standalone, not contribution):
  currency_standalone_vol = std(F) × sqrt(252)
  local_standalone_vol    = std(L) × sqrt(252)
  local_fx_correlation    = corr(L, F)

Edge cases:
  Var(r_p) = 0: every share null — never 0 or 1
  std(L) = 0 or std(F) = 0: local_fx_correlation null; shares still computable
  paired observations < MIN_DAILY_OBSERVATIONS (20): every output null
  a share MAY BE NEGATIVE and must not be clamped — a currency leg moving
    against the local leg genuinely reduces portfolio variance, and clamping
    would fabricate a floor
```

**Why component-covariance rather than `Var(F)/Var(r_p)`.** The naive ratio
ignores `Cov(L, F)` and does not sum to 1, so the shares would not account for
the portfolio. The covariance form is the same exposure×volatility×correlation
identity `risk.py` already uses for factor and position risk-share, so this
extends an established convention rather than competing with it.

Contract rule:
- Trust class is **synthetic history** (current holdings × historical prices),
  ceiling `synthetic`, never `verified` — the card carries a `Synthetic` badge,
  unlike the US-26.1 composition card.
- A holding with no fund-currency price history is **excluded and disclosed by
  symbol**, never assigned to the local leg at zero FX (which would silently
  understate currency exposure). The excluded weight is reported.
- FX pair resolution is verified safe: `resolve_symbol_candidates("EURUSD",
  kind="history")` returns `['EURUSD']` with no equity fallback, so the US-31.4
  wrong-instrument substitution class does not apply to FX pairs.
- The statement-implied static rate (US-28.1, used for *levels*) and this
  historical FX series (used for *returns*) are consistent bases: on
  2026-06-30 the implied EURUSD 1.14220 vs market 1.14218 (+0.00%) and GBPUSD
  1.32610 vs 1.32580 (+0.02%).

Academic precedent:
- Ankrim, E.M. & Hensel, C.R. (1994). "Currency Hedging: A Test for Consistency
  and Efficiency." *Journal of Portfolio Management*, 20(2), 35–41 — the
  standard local/currency decomposition.
- Solnik, B. (1974). "An equilibrium model of the international capital market."
  *Journal of Economic Theory*, 8(4), 500–524 — currency as a distinct priced
  exposure.
- Perold, A.F. & Schulman, E.C. (1988). "The Free Lunch in Currency Hedging."
  *Financial Analysts Journal*, 44(3), 45–50 — reporting the currency leg
  separately from the asset leg.
- Menchero, J. & Davis, B. (2011). "Risk Contribution is Exposure times
  Volatility times Correlation." *Journal of Portfolio Management*, 37(2),
  97–107 — the component-contribution identity reused for the variance split.

## Stress Scenarios

Stress scenario returns are estimated from current factor exposures.

Conceptually:

```text
estimated_scenario_return = sum(current_factor_loading_i * shock_i)
```

Missing-loading rule (US-27.4):

```text
For each scenario, shocked factors split into:
  available = { i : current_factor_loading_i is not null }
  missing   = { i : current_factor_loading_i is null }

estimated_scenario_return = Σ_{i ∈ available} loading_i × shock_i

  missing ≠ ∅ and available ≠ ∅ → status = "partial",
    missing_factors = the missing factors' labels (surfaced, never
    silently zero-filled — a missing loading is NOT a 0.0 loading)
  available = ∅ → status = "unavailable", estimated_scenario_return = null
  missing = ∅ → status = "ok"

A genuine 0.0 loading is a real value and contributes 0 with status "ok"
(null-ness is tested with `is None`, never falsiness).
```

Implementation:
- `services/quant-engine/app/analytics/risk.py` —
  `build_stress_scenarios(...)` + `STRESS_SCENARIOS` constant
- `services/quant-engine/app/services/stress_engine.py` —
  `run_stress_engine(...)` (Epic 13 / US-13.1)
- `services/quant-engine/app/api/routes/stress.py` —
  `POST /engines/stress/run`

Contract rule:
- unavailable stress support must return `null`, not fabricated zeroes

## Indexed Return Series

An indexed return series re-bases portfolio and benchmark values to 100 at the
start of a window, allowing visual comparison of trajectories regardless of
absolute price or value level.

```text
Benchmark line:
  indexed_t = (price_t / price_0) * 100        (adjusted-close price, day t vs window start)

Portfolio line (US-27.8 / audit F10 — TWR-indexed, NOT raw market value):
  indexed_0 = 100
  indexed_t = indexed_{t-1} * (1 + daily_return_t)
  daily_return_t = the cash-flow-neutral TWR daily return
                   (§Portfolio Return Methodology)

  Raw market value is NOT a valid portfolio line: a deposit/withdrawal/trade
  would draw a move against the benchmark's price line that is not
  performance. The TWR chain makes the two lines commensurable.

Drift window returns (same chain as the chart — one code path, US-30.1 AC4):
  window_return_pct = (Π_t (1 + daily_return_t) − 1) × 100
                      over the window's daily states

  Windows: 1M / 3M / 6M / 12M (calendar-day lookbacks from today) plus
  "Since Import" — anchored at the statement-period START (US-30.3 / audit
  F-5), the beginning of the imported statement's coverage. The prior anchor
  (imported_at ≈ today) left <2 valuation dates and always reported
  `unavailable`; the statement-period start makes it a real window.
  Fallback: imported_at when no statement_period is available, then
  `unavailable` (fail-closed) when neither exists.

  The daily-return basis is chosen by what the snapshot actually carries
  (US-30.1 / audit F-1):
  - ledger entries present → the cash-flow-neutral TWR daily return above
    (a broker-ledger replay; basis note "Broker-ledger replay: compounded
    time-weighted return (cash-flow-neutral)").
  - no ledger (the drift request path: positions + cash only) → the
    market-value chain of current holdings,
      daily_return_t = (MV_t / MV_{t-1}) − 1,
    the synthetic-history convention (§Synthetic History) matching the
    panel's Synthetic badge; basis note "Synthetic: current holdings ×
    historical prices (market-value chain)". With no ledger there are no
    external flows, so TWR machinery has nothing to neutralize — and the
    reconstructed total_portfolio_value it would divide by is not broker
    truth on this path (the audit F-1 failure fabricated a ~−$62.6k cash
    anchor and produced ±thousands-of-percent windows).

Fail-closed rule (US-30.1 / audit F-2):
  a computed daily_return_t ≤ −100% is impossible for a long-only portfolio
  and means the valuation inputs are broken. The window fails closed —
  trust="unavailable", note "Unavailable: degraded valuation inputs produced
  an impossible (≤ −100%) daily return", null return/spread — and the chart's
  portfolio line is withheld entirely (explicit nulls). Never clamped, never
  compounded.

Cash anchor rule (US-30.1 / audit F-1, extended by US-34.3, `PortfolioStateEngine`):
  base_cash = Σ starting_cash (base-converted)         (statement reports its own
                                                        opening cash — PREFERRED)
  base_cash = starting_nav − opening_positions_value   (statement totals present,
                                                        no reported starting cash)
  base_cash = Σ cash_balances (base-converted)         (no starting NAV — e.g.
                                                        request-path snapshots)
  The old 0 − opening_value fallback fabricated a large negative cash balance
  and collapsed day-one portfolio value to ~0.

Edge cases:
  price_0 = 0 or null: return null for all benchmark points
  daily_return_t not computable (zero prior value): the portfolio index
    carries unchanged for that date — no return is claimable, never a
    fabricated move
  no day in a window produces a computable return: window return is null
    (unavailable), never a fabricated flat 0.0%
  a date with no portfolio state: portfolio_indexed = null for that point
    (no interpolation)
```

Implementation:
- `services/quant-engine/app/services/drift_engine.py` — `_compound_chain`
  (the shared indexed chain), `_portfolio_return` (window return),
  `_build_daily_series` (chart line), `_basis_note` (per-path note);
  `app/engine/portfolio_state.py` (cash anchor)

Contract rule:
- Indexed series points with null values must be emitted as null, not omitted.
  The frontend renders null as a line break, not a zero.

## FX Conversion Fallback Disclosure

*US-27.8 (audit F9). Applies to the broker replay path
(`engine/portfolio_state.py` → dashboard history, drift, imported-replay
diagnostics).*

Non-base-currency values are converted through `fx_history` rates keyed
`{CURRENCY}{BASE}:{date}`. When a conversion is REQUIRED but no rate is
available, the value is carried **unconverted** — the only honest number held
— and the currency is recorded and surfaced:

```text
fx_fallback_currencies = sorted currencies that required conversion with no
                         available rate during the replay

Disclosure surfaces:
  DriftResult.fx_fallback_currencies            → drift panel helper note
  DashboardHistoryRunMetadata.fx_fallback_currencies

Statement-implied static-rate tier (US-30.2 / audit F-6):
  the drift engine accepts DriftEngineRequest.fx_rates — the statement's own
  implied period-end rates (US-28.1: base-currency restatements of the Open
  Positions totals, broker truth as of the statement period end). They are
  applied as a STATIC rate to every valuation date, so converted levels are
  correct as of the period end but FX return dynamics remain unmodeled. A
  static-rate conversion never upgrades trust (windows stay synthetic) and
  is disclosed in its own tier:

  fx_static_rate_currencies = non-base currencies whose pair has a supplied
                              rate (converted, static)
  fx_fallback_currencies    = the remainder (carried unconverted)
  A currency appears in exactly one tier.

Opening cash anchor + reconciliation adjustments (US-31.3 / Epic 31 F-2, F-3):
  the replay's opening cash is `starting_nav − opening_positions_value`. That is
  only sound when BOTH terms share an as-of date. On a statement whose period
  starts before the replay window (IB2026: NAV as of 2026-01-01, positions
  valued 2026-01-08 — the first trade date), market movement between the two
  dates is absorbed into cash as a plug. The replay cannot value the
  period-start date (no prices exist before the window), so the gap is
  irreducible and is DISCLOSED rather than fabricated:

    ReplayCashAnchor { basis, nav_as_of, window_start, residual, trust }
      residual = base_cash − statement_implied_opening_cash
      statement_implied_opening_cash = cash_total − net_window_flow
        where net_window_flow is FX-CONVERTED per entry. The raw per-currency
        sum of `cash_effect` is currency-mixed and gives a wrong figure
        (IB2026: −271.23 raw vs −2,459.29 converted).
      trust = verified  iff nav_as_of == window_start AND
                            |residual| <= REPLAY_RECONCILIATION_TOLERANCE
              degraded  otherwise   (never verified on a date mismatch)

  **Anchoring precedence (US-34.3 / Epic 34 F-2).** The derivation above is the
  FALLBACK, not the rule. Its two terms are dated differently by construction,
  and they coincide only if an account happens to trade on the first day of its
  statement period — so the anchor reported `degraded` on every run of every
  statement, a disclosure carrying no information. Where the statement reports
  its own opening cash (`ImportedCashBalance.starting_cash`) the replay uses
  that instead: directly observed broker truth, exactly dated at the period
  start, requiring no market data.

    basis = statement_starting_cash   (preferred; observed)
    trust = verified  iff |residual| / |base_cash| <= REPLAY_OPENING_CASH_RESIDUAL_SHARE
            degraded  otherwise

  **Trust follows the anchor's source, not its residual.** For an OBSERVED
  anchor the residual measures a different fact — how well the ledger's flows
  reconcile the statement's own two cash endpoints — and is published alongside
  the trust rather than collapsed into it. For a DERIVED anchor a residual does
  mean the derivation is absorbing something, so the absolute
  `REPLAY_RECONCILIATION_TOLERANCE` rule above still applies to it. The share
  threshold is proportional because the question is proportional; measured on
  IB2026, $46.69 on $4,672.04 of opening cash = 1.0%.

  Measured effect on IB2026: opening cash $3,252.74 → **$4,672.04**, residual
  −$1,377.59 → **+$46.69**, and the terminal reconciliation +$1,366.17 →
  **−$58.11** — 96% of that adjustment was the anchor offset riding through the
  window. Market values are unchanged: this rule moves cash, not valuations.
  *(On the 2026-08-17 capture the terminal reconciliation is **−$19.98**: US-34.9
  supplied real terminal-day quotes for the 14 holdings that had been carried
  forward a day, which shrank the residual further. The −$58.11 above is the
  figure this rule produced when it shipped, kept because it is what the 96%
  is measured against.)*

  The terminal reconciliation snaps the final state's `total_portfolio_value` to
  the statement's ending NAV — correct, since that is the broker's own number —
  but the move is an ACCOUNTING CORRECTION, not performance. It is recorded as
  `DailyPortfolioState.reconciliation_adjustment`, and:

    Rule: no return is published for a day whose |reconciliation_adjustment|
          exceeds REPLAY_RECONCILIATION_TOLERANCE. The day is WITHHELD (absent
          from the return series, disclosed via `withheld_return_dates` with a
          stated reason) — never computed, never substituted with the
          un-reconciled value, because the state's value was overwritten and no
          trustworthy return exists for it.

  The predicate lives on `DailyPortfolioState.return_is_publishable` so every
  return builder (performance / risk / attribution) shares one definition. A
  withheld day therefore cannot leak into volatility, beta, correlation, factor
  attribution or any rolling window (IB2026: annualised vol 23.63% → 23.32%).

Fund-currency conversion basis (US-31.5 / Epic 31 F-4):
  the currency a holding's market value is converted FROM is the FUND (quote)
  currency of the resolved provider line — NOT the broker's listing
  `position.currency`. These differ: a fund can be LISTED in one currency and
  QUOTED in another (e.g. DEFS is listed EUR but its resolved line DEFS.L
  quotes USD; converting a USD quote by EURUSD would double-count). A blanket
  position-currency conversion was measured 4.3× worse on the committed
  portfolio. The fund currency is read from the InstrumentRegistry
  (`get_instrument(sym).currency`), which is curated to the fund currency and
  matches the observed quote basis for every priced holding (0 mismatches).

  Rule (imported ledger-replay path):
    - MARKET-priced value  → convert FROM the registry fund currency
    - STATEMENT-anchored value (no fetchable history; the flat statement close)
                           → convert FROM the position/listing currency, since
                             the anchor is the broker's own statement close
    - fund currency unknown → fall back to the position currency; unknown rate
                             → carried unconverted + disclosed (never a silent
                             1:1 base assumption)
  The static rates come from the statement's own implied `fx_rates` (US-28.1),
  applied per the static-rate tier above. Dependency: the registry currency
  must equal the resolved line's quote currency — pinned by a golden-master
  guard so a mis-curated currency fails at golden-regen. With F-1/F-4/F-5
  resolved the IB2026 terminal market value reconciles to the statement's
  `stock_total` ($61,239.88 vs $61,238.53), leaving only the F-2 cash anchor.

Statement-anchored symbols (US-30.2 / audit F-3):
  a held symbol with NO fetchable in-window price history is valued flat at
  the statement close (the US-27.7 broker-path anchor — broker-truth-
  adjacent, zero return contribution, dampens returns/volatility). The
  engine records these and the drift result surfaces them:

  statement_anchored_symbols → DriftResult.statement_anchored_symbols
                             → drift panel helper note

Historical FX series (real dynamics) remain Epic 26 scope: wiring
MarketDataService.get_fx_history requires empirical verification of its FMP
symbol resolution first (zero callers today). Until then every degradation
tier is EXPLICIT, never a silent 1:1 conversion claim.
```

Contract rule:
- a missing FX rate must never be presented as a converted value; the
  fallback is disclosed per response, and consumers render the degradation
  (the drift panel's FX helper note).
- a static-rate conversion must be disclosed as static (its own tier and
  note wording), never folded into either "fully converted" or "fallback".
- statement-anchored (flat) valuations must be disclosed per response; a
  flat segment must never pass silently as market data.

## Rolling Pearson Correlation

Rolling correlation measures how linearly co-movement between portfolio daily
returns and benchmark daily returns evolves over time. It is the primary
statistic for determining whether a portfolio is behaving like a given market
index.

```text
rho_t(w) = cov(r_p[t-w+1 : t], r_b[t-w+1 : t])
           / (std(r_p[t-w+1 : t]) * std(r_b[t-w+1 : t]))

where:
  r_p_t  = daily portfolio return (basis selected by provenance — see below)
  r_b_t  = (price_b_t / price_b_(t-1)) - 1  (simple daily price return)
  w      = rolling window in trading days: 20, 60, or 252
  t      = current date index in the sorted series

Range: [-1, +1]
  +1 = perfect positive co-movement
   0 = uncorrelated
  -1 = perfect inverse co-movement

Edge cases:
  std(r_p) = 0 or std(r_b) = 0: return null (constant series — no information)
  len(series) < 2: return null
  Available dates < w: return null for those prefix dates (no partial-window fill)
```

Return basis (provenance-selected — US-30.5c / audit F-10). `r_p_t` is chosen
by **what the daily portfolio states were built from**, the same rule
§Indexed Return Series applies to the drift chart:

- **Imported ledger-replay** (`historical_basis="imported_portfolio_history"` —
  a broker-ledger replay carrying real trades) → the **trade-neutral
  market-value chain** (US-24.9),

  ```text
  r_p_t = (MV_t − trade_flow_t) / MV_{t−1} − 1
  ```

  where `trade_flow_t` (`DailyPortfolioState.trade_flow`) is the net
  base-currency market value moved **into the holdings** by that day's BUY/SELL
  entries — positive for a net buy, the negation of those entries' FX-converted
  `cash_effect`. Subtracting it cancels exactly the leg a plain market-value
  chain would misread as performance (the audit F-1 failure class: on IB2026
  the naive chain reports **+17.19%** on the 2026-04-14 trade day against the
  trade-neutral **+2.64%**), while the `MV` denominator keeps the account's cash
  sleeve out of the risk statistics. Two rules make it safe:

  - **Only valued symbols are neutralised.** A symbol the replay cannot price
    contributes nothing to `MV`, so trading it moves no market value; counting
    it would neutralise a leg that was never there. Reproduced on IB2026
    2026-04-27, where selling the unpriced IUFS + IUHC ($5,341.92) on an
    otherwise flat day fabricated **+9.43%**. `trade_flow` therefore excludes
    trades in symbols absent from that day's valuation (they remain disclosed
    via `unpriced_replay_symbols`).
  - **Withholding still wins.** A day carrying a material
    `reconciliation_adjustment` publishes no return on this basis either
    (§Terminal Reconciliation / US-31.3, guardrail #3).

  The **investor-performance** family — the Dashboard performance series, TWR,
  money-weighted return, net contributions, monthly returns and the dashboard
  max drawdown — deliberately keeps the cash-inclusive TWR
  `r_p_t = (PV_t − external_cash_flow_t)/PV_{t−1} − 1`
  (§Portfolio Return Methodology): cash is part of what the investor actually
  earned on the money in the account, whereas a risk statistic compared against
  a fully-invested benchmark should not be scaled down by an idle sleeve.
- **Synthetic history** (`historical_basis="market_data_history"`, and the
  standalone attribution / multi-benchmark-correlation / stress surfaces — all
  current holdings × historical prices, **no trades**) → the market-value chain
  of current holdings, `r_p_t = MV_t / MV_{t−1} − 1`, the synthetic-history
  convention (§Synthetic History). On a synthetic series cash is a flat carry
  (constant on every reconstructed day, `external_cash_flow ≡ 0`), so the TWR
  denominator `MV + cash` would dilute every equity return toward zero by the
  cash weight — a distortion, not a correction. With no trades present the
  market-value chain cannot fabricate a return, so it is both correct and safe.

This is the same market-value chain the VaR (§Value-at-Risk and Distribution)
and drawdown (§Wealth Index and Drawdown) engines already use for their
synthetic return series; US-30.5c
brought the correlation / beta / factor-attribution / factor-model / stress
surfaces onto it too, resolving a prior split where those read the
cash-inclusive TWR while VaR/drawdown read the cash-excluded chain. **US-24.9
completed the convergence**: with `trade_flow` recorded per day, the imported
ledger-replay path moved onto the trade-neutral variant, so *every* risk
statistic in the product — synthetic and imported alike — now measures the
holdings rather than the account. Measured on IB2026 (median cash weight
**5.60%**): annualised volatility **14.54% → 15.47%** (×1.064, matching the
cash-weight prediction 1/(1 − 0.056) = 1.059), comparing like-for-like with the
two unpriced-symbol cash-event days excluded.

Academic precedent:
- Pearson, K. (1895). "Note on regression and inheritance in the case of two
  parents." *Proceedings of the Royal Society of London*, 58, 240–242.
- Elton, E.J., Gruber, M.J., Brown, S.J. & Goetzmann, W.N. (2014).
  *Modern Portfolio Theory and Investment Analysis*, 9th ed., Ch. 4 (Wiley).
- Hull, J.C. (2021). *Options, Futures, and Other Derivatives*, 11th ed., §22.1
  (Pearson).

For the trade-neutral basis specifically (a standard flow-adjusted period
return applied to a market-value rather than total-value denominator, not a new
construction):

- Bacon, C.R. (2008). *Practical Portfolio Performance Measurement and
  Attribution*, 2nd ed., Ch. 2 (Wiley) — time-weighted return with
  end-of-period flow adjustment.
- CFA Institute (2020). *Global Investment Performance Standards (GIPS) for
  Firms*, §2.A.2 — returns must be adjusted for external cash flows; a security
  purchase inside the portfolio is an internal transfer, not performance.
- Elton, Gruber, Brown & Goetzmann (2014), Ch. 4 (above) — beta and correlation
  are estimated on the return series of the risky assets; a cash sleeve scales
  the series and biases beta toward zero, the distortion this basis removes.

Implementation target:
- `services/quant-engine/app/analytics/correlation.py` (Epic 9)
- `services/quant-engine/app/services/correlation_engine.py` (Epic 9)

Contract rule:
- Rolling correlation is always synthetic history trust — current holdings
  applied to historical prices. Never labelled verified.
- Null gaps in the rolling series must propagate as null fields, not be filled
  with adjacent values or zero.

## Beta (Market Beta)

Beta measures the sensitivity of portfolio returns to benchmark returns — the
slope of the OLS regression of r_p on r_b.

```text
beta = cov(r_p, r_b) / var(r_b)

where r_p and r_b are computed over the same lookback window (default: 252 trading days,
or max available if shorter).

Interpretation:
  beta > 1: portfolio amplifies benchmark moves
  beta = 1: portfolio moves in lockstep with benchmark
  0 < beta < 1: portfolio is less volatile than benchmark
  beta < 0: portfolio moves inversely to benchmark

Edge cases:
  var(r_b) = 0: return null (benchmark never moved — division undefined)
  len(series) < 20 trading days: return null (insufficient data for stable estimate)
```

Academic precedent:
- Sharpe, W.F. (1964). "Capital asset prices: A theory of market equilibrium
  under conditions of risk." *Journal of Finance*, 19(3), 425–442.
- Lintner, J. (1965). "The valuation of risk assets and the selection of risky
  investments in stock portfolios and capital budgets." *Review of Economics
  and Statistics*, 47(1), 13–37.

Implementation target:
- `services/quant-engine/app/analytics/correlation.py` (Epic 9)

Contract rule:
- Beta is synthetic history trust. Null when data insufficient; never
  fabricated or approximated from tracking error alone.

## R² (Coefficient of Determination)

R² measures the proportion of portfolio return variance explained by benchmark
returns. It is the square of the Pearson correlation coefficient.

```text
r_squared = rho^2

where rho is the Pearson correlation computed over the same lookback window.

Range: [0, 1]  (always non-negative regardless of correlation sign)
  R² = 0.90: 90% of portfolio variance is explained by this benchmark
  R² = 0.00: benchmark explains none of the portfolio's variance

Edge cases:
  rho = null: r_squared = null
```

Academic precedent:
- Elton et al. (2014), *Modern Portfolio Theory and Investment Analysis*, Ch. 5.
- Grinold, R.C. & Kahn, R.N. (2000). *Active Portfolio Management*, 2nd ed.,
  Ch. 2 (McGraw-Hill).

Implementation target:
- `services/quant-engine/app/analytics/correlation.py` (Epic 9)

Contract rule:
- R² is synthetic history trust. Reported alongside beta and correlation as a
  trio; never shown without the correlation from which it derives.

## Multi-Benchmark Correlation

A point-in-time snapshot of how the portfolio co-moves with multiple market
benchmarks over a single lookback window. Uses the formulas above —
§Rolling Pearson Correlation, §Beta (Market Beta), §R² — applied pairwise
between the synthetic portfolio return series and each benchmark's daily
price return series.

Benchmark universe (hardcoded in `services/quant-engine/app/services/correlation_engine.py`):
- SPY (S&P 500), QQQ (Nasdaq-100), GLD (Gold), IEF (US 7-10yr Bonds), VT (Global Equity)

Sort contract:
- Rows are returned ordered by `abs(correlation)` descending; rows with
  `correlation = None` (unavailable) sort last.

Edge cases:
- < 20 overlapping trading-day returns for a benchmark: `correlation`,
  `beta`, `r_squared` all null and `trust = 'unavailable'`.
- Benchmark price history not fetchable: same — null + unavailable.

Implementation:
- `services/quant-engine/app/analytics/correlation.py` — scalar helpers
- `services/quant-engine/app/services/correlation_engine.py` — orchestration + sort
- `POST /engines/correlation/multi` — route

Contract: see `docs/contracts/correlation-fields.md` (US-9.3 section) for the
field-level inventory and UI rendering rules.

## Intra-Portfolio Correlation

Where §Multi-Benchmark Correlation measures how the *portfolio as a whole*
co-moves with external benchmarks, intra-portfolio correlation measures how the
portfolio's *own holdings co-move with each other*. It answers the
diversification question Markowitz framed: a basket of highly mutually
correlated holdings carries far less diversification than its position count
suggests, because their returns move together. The output is a symmetric
holdings × holdings Pearson correlation matrix plus diversification summary
statistics derived from it.

All series are **synthetic history**: each holding's daily return series is the
simple price return of its symbol over the lookback window (current holdings
applied to historical prices), identical in construction to the per-symbol
series already built inside `correlation_engine.py`. No new market-data source
is introduced.

### Pairwise correlation

```text
ρ_ij(w) = cov(r_i[t-w:t], r_j[t-w:t])
          / (std(r_i[t-w:t]) × std(r_j[t-w:t]))

where:
  r_i_t = simple daily price return of holding i on date t = price_i(t)/price_i(t-1) − 1
  r_j_t = simple daily price return of holding j on date t
  w     = lookback window in trading days (20, 60, or 252)
  cov/std use the population (N-denominator) convention, matching analytics/correlation.py

  ρ_ii  = 1.0 by definition (diagonal)
  ρ_ij  = ρ_ji          (matrix is symmetric)

Computed via the existing pearson() helper in analytics/correlation.py, which
drops non-overlapping (null) pairs before computing.

Edge cases:
  fewer than MIN_PAIR_OBSERVATIONS (20) overlapping non-null daily returns for
    the pair (i, j): ρ_ij = null, pair trust = 'unavailable' (never 0)
  either holding's return series has zero variance over the window
    (constant/flat price): ρ_ij = null (pearson() already returns None)
  a holding with no fetchable price history: excluded from the matrix entirely
    (it is not rendered as a null row — it never enters the priceable universe)
  cash balances and non-priceable instruments: excluded — they have no return
    series and therefore no correlation
```

### Average pairwise correlation

A single scalar summarising overall internal co-movement: the mean of the
off-diagonal upper triangle over pairs that produced a non-null ρ.

```text
avg_pairwise_ρ = ( Σ_{i<j, ρ_ij ≠ null} ρ_ij ) / N_valid_pairs

where:
  N_valid_pairs = count of (i, j), i<j, with ρ_ij ≠ null

Edge case:
  N_valid_pairs = 0 (fewer than 2 priceable holdings with sufficient history):
    avg_pairwise_ρ = null, summary trust = 'unavailable'

Interpretation: closer to +1 → holdings move together (low diversification);
near 0 → largely independent; negative → holdings hedge each other.
```

### Diversification Ratio (Choueifaty & Coignard 2008)

The ratio of the weighted-average standalone volatility of the holdings to the
realised volatility of the portfolio. DR = 1 means no diversification benefit
(all holdings perfectly correlated); DR > 1 quantifies the volatility reduction
from imperfect correlation.

```text
DR(w) = ( Σ_i w_i × σ_i(w) ) / σ_p(w)

where:
  w_i    = current weight of holding i (market value / total priceable market value)
  σ_i(w) = population stdev of holding i's daily returns over the COMPLETE-CASE
           dates (dates where every selected holding has a non-null return) —
           the same date set as σ_p (US-27.9 / audit F13: computing σ_i over
           each holding's own coverage while σ_p uses complete-case dates can
           break the DR ≥ 1 guarantee under ragged coverage)
  σ_p(w) = population stdev of the synthetic portfolio daily return series under
           *constant current weights*: r_p(t) = Σ_i w_i × r_i(t), over the same
           complete-case dates. This is the coherent DR denominator (guarantees
           DR ≥ 1 for long-only weights) and is self-consistent with the w_i
           and σ_i used in the numerator.

Edge cases:
  σ_p(w) = 0, or fewer than MIN_PAIR_OBSERVATIONS (20) constant-weight portfolio
    returns: DR = null
  weights restricted to the priceable universe shown in the matrix (cash and
    non-priceable positions excluded; weights renormalised over the selected
    top-N holdings)
```

### Effective Number of Bets (Meucci 2009)

A spectral diversification measure: the entropy of the normalised eigenvalue
spectrum of the correlation matrix. ENB = 1 when one principal component
explains everything (no diversification); ENB → m (number of holdings) when
risk is spread evenly across independent components.

```text
ENB = exp( − Σ_k p_k × ln(p_k) )

where:
  λ_k = eigenvalues of the m × m holdings correlation matrix
  p_k = λ_k / Σ_j λ_j        (normalised so Σ_k p_k = 1)
  m   = number of priceable holdings in the matrix

Edge cases:
  any λ_k ≤ 0 from floating-point noise: clamp to 0 and drop from the entropy
    sum (0·ln 0 ≡ 0)
  any off-diagonal matrix cell is null (matrix not fully populated): ENB = null
    — the eigendecomposition requires a complete numeric matrix
  matrix not positive-semidefinite / fewer than 2 holdings: ENB = null

Implementation note: ENB requires an eigendecomposition of a symmetric matrix.
Shipped in US-17.2 using **numpy** (`numpy.linalg.eigvalsh` on the symmetric
correlation matrix) — numpy is imported lazily inside `effective_number_of_bets`
so it is only a dependency of the ENB path. DR and `population_stdev` remain
pure-Python.
```

Academic precedent:
- Markowitz, H. (1952). "Portfolio Selection." *Journal of Finance*, 7(1),
  77–91. (Diversification depends on the covariance/correlation structure of
  holdings, not merely their count.)
- Choueifaty, Y. & Coignard, Y. (2008). "Toward Maximum Diversification."
  *Journal of Portfolio Management*, 35(1), 40–51. (Diversification Ratio.)
- Meucci, A. (2009). "Managing Diversification." *Risk*, 22(5), 74–79.
  (Effective Number of Bets via the entropy of the eigenvalue spectrum.)

Implementation:
- `services/quant-engine/app/analytics/correlation.py` — `pairwise_correlation_matrix(...)`
  (reuses `pearson()`), `average_pairwise_correlation(...)`, `population_stdev(...)`,
  `diversification_ratio(...)`, and `effective_number_of_bets(...)` (numpy, US-17.2)
- `services/quant-engine/app/services/intra_correlation_engine.py` — orchestrates
  market-data fetch, per-symbol return series, matrix + summary assembly; derives
  σ_p from the constant-weight portfolio return series (Σ w_i r_i). Reuses
  `_returns_from_price_series` from `correlation_engine.py` and the shared
  `lookback_calendar_days` helper from `app/core/constants.py`
- `POST /engines/correlation/intra` — route

Contract rule:
- Every cell and summary value is **synthetic history**; never `verified`.
- A pair below the minimum overlap is `null` with pair-level
  `trust='unavailable'` — never rendered as 0. The diagonal is always exactly
  `1.0` and is not subject to the trust ladder.
- Cash and non-priceable instruments never enter the matrix; the priceable
  universe is the contract surface, and weights for the Diversification Ratio
  are renormalised over it.
- See `docs/contracts/intra-correlation-fields.md` for the field-level inventory
  and heatmap rendering rules.

## Factor Return Attribution

Factor return attribution decomposes the portfolio's daily return history into
contributions from each systematic factor and a residual (idiosyncratic + alpha)
component. Each factor's daily contribution is the product of its per-window
rolling OLS loading (β) and the orthogonalized factor return on that day.
Contributions are summed arithmetically over any selected period to produce
period-level attribution.

This is the *return* counterpart to the Rolling Factor Model: where the factor
model shows *exposures* (betas), attribution shows *realized contributions* (how
much return each exposure actually generated over the history).

### Daily factor contribution

```text
contribution_k(t) = β̂_k(w, t) × f*_k(t)

where:
  β̂_k(w, t)  = rolling OLS loading for factor k using window w ending at date t
                (output of _build_rolling_factor_loadings; see §Statistical Factor Model)
  f*_k(t)    = orthogonalized daily return of factor k on day t
                (the Gram-Schmidt residual of factor k after projecting out all
                 higher-priority factors; computed within the same window w)
  w           = rolling estimation window: 20, 60, or 252 trading days
  t           = trading date in the portfolio return history
  k           = factor index in orthogonalization order
                (market=1, growth=2, value=3, small_cap=4, technology=5,
                 financials=6, health_care=7, energy=8, industrials=9,
                 consumer_staples=10, utilities=11, consumer_discretionary=12,
                 rates_ief=13, rates_tlt=14, credit=15, commodities=16)

Units: decimal (e.g. 0.012 = 1.2%). Multiply by 100 for percentage display.
```

### Daily residual contribution

```text
residual(t) = r_p(t) − Σ_k contribution_k(t)

where:
  r_p(t) = cash-flow-neutral daily portfolio return (see Portfolio Return Methodology)
  Σ_k    = sum over all K active factors with non-null β̂_k(w, t)
```

### Period attribution (arithmetic sum)

```text
period_contribution_k(t1, t2) = Σ_{t=t1}^{t2} contribution_k(t)
period_residual(t1, t2)        = Σ_{t=t1}^{t2} residual(t)
period_portfolio_return(t1, t2) = Σ_{t=t1}^{t2} r_p(t)   [arithmetic, not compounded]

Reconciliation identity (exact by construction):
  Σ_k period_contribution_k + period_residual = period_portfolio_return
```

*Arithmetic note:* The arithmetic sum of daily contributions equals the
arithmetic sum of daily returns. It does not equal the compound return
((1+r₁)(1+r₂)…(1+rₙ) − 1). For windows ≤ 3 months the difference is negligible;
for longer windows the compounding gap widens. The engine labels all outputs
as arithmetic and the UI must communicate this to the researcher.

### Cumulative contribution series (for chart)

```text
cumul_contribution_k(t) = Σ_{s=t0}^{t} contribution_k(s)
cumul_residual(t)         = Σ_{s=t0}^{t} residual(s)
cumul_portfolio_return(t) = Σ_{s=t0}^{t} r_p(s)

where t0 = first date in the analysis window
```

### Edge cases

```text
β̂_k(w, t) = null (window not filled or factor collinear):
  → contribution_k(t) = null
  → residual(t) = null
  → that date is excluded from all period and cumulative sums

Any factor contribution null on date t:
  → exclude date t entirely from period sums and cumulative series

Period attribution null when:
  → fewer than min_window_observations dates have non-null contributions for the
     selected window (e.g. portfolio history < 20 days for 20d window)
  → emit attribution_status = 'unavailable', not fabricated zeros

Residual must never be labeled "alpha" or "skill" in UI or contracts:
  → label as "Unexplained / idiosyncratic" — contains both alpha and model error
```

Academic precedent:
- Brinson, G.P., Hood, L.R. & Beebower, G.L. (1986). "Determinants of
  portfolio performance." *Financial Analysts Journal*, 42(4), 39–44.
  (Original arithmetic performance attribution decomposition framework.)
- Fama, E.F. & French, K.R. (1993). "Common risk factors in the returns on
  stocks and bonds." *Journal of Financial Economics*, 33(1), 3–56.
  (Factor-based return decomposition and the separation of systematic vs.
  idiosyncratic return components.)
- Bacon, C.R. (2008). *Practical Portfolio Performance Measurement and
  Attribution*, 2nd ed., Ch. 8–9 (Wiley). (Arithmetic linking, residual
  interpretation, and reconciliation identities in time-series attribution.)

Implementation target:
- `services/quant-engine/app/analytics/attribution.py` (Epic 11)
- `services/quant-engine/app/services/attribution_engine.py` (Epic 11)
- `services/quant-engine/app/api/routes/attribution.py` (Epic 11)

Contract rule:
- Factor return attribution is always synthetic history trust class. Never
  labelled verified. Any field can be null; never fabricate.
- The residual field must be labelled "unexplained_pct" or "idiosyncratic_pct"
  in the schema — never "alpha_pct".
- Arithmetic attribution must carry a `methodology_note` field in the response
  explaining that sums are arithmetic, not compounded.
- The reconciliation identity (Σ contributions + residual = arithmetic portfolio
  return) must hold to floating-point precision. If it does not, the engine must
  return an error rather than emit inconsistent data.

## Value-at-Risk and Distribution

Daily return distribution analytics measured from the synthetic portfolio return
series over a lookback window. All outputs are synthetic-history trust class.

### Daily return series

```text
r_t = (wealth_t - external_cash_flow_t) / wealth_{t-1} - 1

  cash-flow-neutral, consistent with §Portfolio Return Methodology.
  series r computed over the lookback window w trading days.
  w ∈ {60, 252, 504}; default w = 252.
  calendar-day fetch = ceil(w * 1.6) + 30   (project standard heuristic;
    the single `lookback_calendar_days` helper in `app/core/constants.py`, shared
    by the attribution / correlation / distribution / drawdown / stress / provenance
    engines — US-24.3. The flat 20-observation `unavailable` floor is the shared
    `MIN_DAILY_OBSERVATIONS`; the default benchmark is `DEFAULT_BENCHMARK_SYMBOL`.)
```

### Percentiles

```text
p_q = quantile(r, q)        for q ∈ {0.05, 0.10, 0.50, 0.90, 0.95}

  NIST linear-interpolation method (numpy.quantile default).
```

### Historical Value-at-Risk

```text
VaR_α = -p_{1-α} * 100        for α ∈ {0.95, 0.99}

  reported as positive loss in percent
  e.g. VaR_95 = 2.34 means "5% of days lost ≥ 2.34%"
```

### Conditional VaR (Expected Shortfall)

```text
tail   = { r_t ∈ r : r_t ≤ p_{1-α} }
CVaR_α = -mean(tail) * 100    for α ∈ {0.95, 0.99}

  reported as positive loss in percent
  CVaR_α ≥ VaR_α by construction (coherent risk measure)
```

### Distribution shape

```text
mean = mean(r)
std  = sqrt(var(r))           (population N denominator)
skew = E[((r - mean) / std)^3]            (Fisher-Pearson)
kurt = E[((r - mean) / std)^4] - 3        (EXCESS kurtosis, Fisher)
```

### Histogram

```text
bins  = 30 (default)
range = [min(r), max(r)]      (auto-fit; no symmetric padding; no outlier trim)
```

Edge cases:
- `len(r) < 20`: every metric returns `null`; surface `trust = 'unavailable'`
- `|tail| < 2`: `CVaR_α` returns `null` (single tail sample is not a mean)
- `std = 0` (constant series): `skew`, `kurt` return `null`
- all `r ≥ 0` (no loss days in window): `VaR_α` and `CVaR_α` may be NEGATIVE
  (= "the tail day was still positive") — reported as-is, never clipped to zero

Academic precedent:
- Jorion (2007), *Value at Risk*, 3rd ed., McGraw-Hill, Ch. 5 — historical-
  simulation VaR
- Acerbi & Tasche (2002), "On the coherence of expected shortfall," *Journal
  of Banking & Finance* 26(7): 1487–1503 — CVaR / ES as a coherent risk
  measure
- Embrechts, McNeil & Frey (2015), *Quantitative Risk Management*, 2nd ed.,
  Princeton UP, Ch. 2.4 — historical vs parametric vs Monte Carlo VaR
  comparison

Implementation:
- `services/quant-engine/app/analytics/distribution.py` —
  `compute_percentiles(...)`, `compute_var(...)`, `compute_cvar(...)`,
  `compute_distribution_shape(...)`, `compute_histogram(...)` (Epic 13 /
  US-13.3; pure-Python, no numpy / scipy)
- `services/quant-engine/app/services/distribution_engine.py` —
  `run_distribution_engine(...)` (enforces `CVaR ≥ VaR` invariant)
- `services/quant-engine/app/api/routes/distribution.py` —
  `POST /engines/distribution/run`

Contract rule:
- never clip `VaR` to a positive number — a negative VaR is a meaningful
  signal that the window contained no loss days at the requested confidence
- `CVaR < VaR` is impossible by construction; if the engine emits such a
  pair it must raise rather than return inconsistent data

## Current Known Financial Limitations

At the time of writing, the main finance-related limitations are:

- some return paths still remain intentionally degraded or withheld because total-return-equivalent trust is not yet proven broadly enough to unlock stronger claims everywhere
- factor interpretation still depends on factor ordering and proxy quality

## Maintenance Rule

When any of the following changes, update this file:
- financial formulas
- methodology strings
- factor definitions
- trust, degradation, withholding, or unavailability semantics

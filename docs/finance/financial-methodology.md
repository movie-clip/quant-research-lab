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

*Research brief, not yet implemented — see the story list in
`docs/product/prd/epic-26-currency-exposure-and-risk.md`. Documented here per
the project's methodology-traceability guardrail: a formula must exist here
**before** any implementer builds against it, not after.*

The project holds no explicit view of how much of a portfolio is denominated
in a currency other than its base currency. `ImportedPosition.currency` and
`ImportedStatement.base_currency` are already captured on every import (no
new import-format change needed), but nothing aggregates or displays them.
A portfolio with meaningful non-base-currency holdings (e.g. UCITS ETFs
traded in EUR/GBP, per the project's documented UCITS support) carries
currency risk the researcher cannot currently see anywhere on any tab.

### Currency exposure by weight (snapshot)

```text
currency_weight_c = Σ_i (market_value_i)  for all holdings i with currency_i = c
                     ────────────────────────────────────────────────────────
                     Σ_j market_value_j    (all holdings j, all currencies)

where:
  currency_i      = ImportedPosition.currency (already imported; not derived)
  base_currency   = ImportedStatement.base_currency
  non_base_weight = 1 − currency_weight_{base_currency}

Edge cases:
  a position with currency = null: excluded from both numerator and
    denominator (never assumed base-currency; that would understate real
    non-base exposure) — surfaced as an "unclassified" residual weight so
    the total still reconciles to 100%
  base_currency = null: currency_weight is still computable per currency,
    but non_base_weight cannot be computed (no baseline to compare against)
    → non_base_weight = null
```

This is a **snapshot analytics** truth class (current holdings only, no
historical prices, no market data fetch) — the same class as sector
exposure. It requires no new data source: `currency` and `base_currency` are
already present on every `ImportedPortfolioSnapshot`.

Implementation target:
- `services/quant-engine/app/analytics/<name>.py` (new file — this is a
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

### Currency risk contribution (historical, stretch — not scoped for MVP)

A second, harder question — *how much of my portfolio's historical return
volatility came from currency moves versus the underlying security's local
return* — requires decomposing each non-base-currency holding's
base-currency return into a local-return leg and an FX-return leg:

```text
r_i_base(t)  ≈  r_i_local(t) + r_fx_c(t) + (r_i_local(t) × r_fx_c(t))

where:
  r_i_local(t) = holding i's daily return in its own trading currency
                 (local-currency price return)
  r_fx_c(t)    = daily return of the FX pair converting currency c to
                 base_currency on day t
  the cross term (r_i_local × r_fx_c) is the second-order interaction;
  conventionally small for daily returns and often dropped in practitioner
  approximations, but should be retained here per the project's "no
  fabricated simplification" posture unless proven negligible for this
  portfolio's actual holdings

Portfolio-level currency contribution to variance requires the full
covariance structure between local-return legs and FX-return legs across all
non-base holdings — this is materially more complex than the weight-based
snapshot above (a return-attribution problem, not a composition problem) and
is explicitly deferred; see PRD non-goals.
```

Data requirement: `MarketDataService.get_fx_history(pair, from_date, to_date)`
already exists (thin wrapper over `get_historical_prices`) but has zero
callers today — this story would be its first real consumer, so its FMP
symbol-resolution behavior for FX pairs must be verified empirically before
committing to this formula (unverified as of this brief).

Academic precedent:
- Ankrim, E.M. & Hensel, C.R. (1994). "Curency Hedging: A Test for
  Consistency and Efficiency." *Journal of Portfolio Management*, 20(2),
  35–41 — the standard local-return/currency-return decomposition
  (sometimes called the "Ankrim-Hensel" currency attribution model).

This subsection exists to document the harder problem's shape for a future
story; it is **not** ready to implement (the interaction-term and portfolio-
variance-decomposition questions above are open) and must not be built
against without a follow-up brief that resolves them.

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

Cash anchor rule (US-30.1 / audit F-1, `PortfolioStateEngine`):
  base_cash = starting_nav − opening_positions_value   (statement totals present)
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
  r_p_t  = daily portfolio return (cash-flow-neutral formula, see Portfolio Return Methodology)
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

Academic precedent:
- Pearson, K. (1895). "Note on regression and inheritance in the case of two
  parents." *Proceedings of the Royal Society of London*, 58, 240–242.
- Elton, E.J., Gruber, M.J., Brown, S.J. & Goetzmann, W.N. (2014).
  *Modern Portfolio Theory and Investment Analysis*, 9th ed., Ch. 4 (Wiley).
- Hull, J.C. (2021). *Options, Futures, and Other Derivatives*, 11th ed., §22.1
  (Pearson).

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

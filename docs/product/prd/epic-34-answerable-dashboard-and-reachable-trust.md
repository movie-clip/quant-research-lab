# Epic 34 — An Answerable Dashboard: Reachable Trust States

**Status:** Active (created 2026-08-13)
**Created:** 2026-08-13
**Seeded by:** reading the shipped product end to end after Epic 33 closed, and
finding that the Dashboard — the tab whose stated job is *portfolio
performance* — reports **no performance number at all**, on every run, by
construction.

## Problem

The guardrails work. That is not the problem. The problem is that four epics of
fail-closed engineering have produced a product that is **correct and silent**:
every headline number on the primary tab is `null`, and two of the four
disclosures on screen can never be cleared by any input.

Fail-closed is right when a number would otherwise be fabricated. It is wrong
when it withholds a number the product has, computed correctly, because a proof
of a *stronger* claim than the researcher asked for cannot be assembled. Epic 33
was about not publishing a phantom. This epic is about not withholding the real
thing.

Reproduced against the committed statement and the frozen market data.

### What the Dashboard renders today

| Metric | All | 1Y | YTD | 3M | 1M |
|---|---|---|---|---|---|
| Time-weighted return | `null` | `null` | `null` | `null` | `null` |
| Benchmark return | `null` | `null` | `null` | `null` | `null` |
| Excess return | `null` | `null` | `null` | `null` | `null` |
| Max drawdown | `null` | `null` | `null` | `null` | `null` |
| Money-weighted return | **5.30%** | — | — | — | — |

One number survives. Meanwhile:

- the **broker statement itself states TWR = 4.765666%**, imported and pinned in
  `statement_truths.py`;
- the engine computes **14.18% annualised TWR volatility** internally, and the
  audit suite asserts it;
- **148 daily states and 148 performance points** are built successfully;
- the benchmark's **148 SPY closes are fetched and returned** — with
  `return_pct: null`.

The machinery all works. The gate on top of it never opens.

### F-1 (Critical) — the portfolio return basis is hardcoded `unavailable`

```python
# app/services/dashboard_history_engine.py:162
def _build_dashboard_return_basis_contract(benchmark_rows) -> ...:
    return DashboardHistoryRunMetadata.ReturnBasisContract(
        portfolio_path="unavailable",          # <- literal, no input reaches it
        benchmark_path=benchmark_contract,
    )
```

No snapshot, no market data and no fix can make `portfolio_path` anything else.
It is later overwritten to `verified_total_return` only when
`admitted_portfolio_twr_scope is not None` — which requires the portfolio proof
to be admitted, which F-1a shows is unreachable.

### F-1a (Critical) — five of the eight hard disqualifiers are unreachable by construction

`portfolio_proof.admission.readiness_status = exact_slice_prerequisites_incomplete`,
with 8 hard disqualifiers. These five are **structural properties of replaying a
broker statement**, not data-quality problems a better import could fix:

| Disqualifier | Why it can never clear |
|---|---|
| `inferred_opening_holdings` | The replay reconstructs opening positions by rolling the ending position back through trades. That *is* the method. |
| `inferred_opening_quantities` | Same. Always true on the imported path. |
| `terminal_force_reconciliation_present` | The terminal state is always snapped to the statement's ending NAV — deliberately, it is the broker's own number. |
| `forward_filled_prices` | Prices carry across non-trading days. Every daily series does this. |
| `mixed_basis_valuation` | The documented three-tier ladder (market history → statement close → trade price). Fires whenever any holding needs tier 2 or 3. |

A sixth, `raw_price_used_for_valuation`, is reachable only by changing market-data
endpoints (see F-6).

The admission gate was designed to certify a **GIPS-style verified total
return**. That is a genuinely higher bar than "a time-weighted return computed
from a reconstructed replay, labelled as such". Conflating the two means the
researcher gets nothing rather than the honest weaker number.

### F-2 (High) — the cash anchor can never be `verified`

`verified` requires `nav_as_of == window_start`. But:

- `nav_as_of` is the **statement-period start** (2026-01-01), and
- `window_start` is the **replay window start** = the first date the replay can
  value, driven by the first trade / first covered quote (2026-01-08).

These coincide only if the account happens to trade on the first day of the
statement period. On IB2026 they are 5 trading days apart, so the anchor reports
`degraded` with a −$1,377.59 residual **on every run**, and
`ReplayDisclosuresCard` shows the warning permanently.

`ReplayDisclosuresCard`'s own docstring says the card must never "cry wolf on a
clean run". A disclosure that cannot be cleared carries no information: the
researcher learns to ignore it, which is worse than not showing it, because it
trains them to ignore the ones that matter.

### F-3 (High) — a withheld holding's magnitude is never disclosed

US-33.2 correctly withholds LQQ's reconstructed quantity. But the disclosure
tells the researcher *that* a holding was dropped and *why*, and nothing about
**how much of their portfolio it was**. From the ledger:

```text
2026-04-14  BUY   1 @ EUR 1,457.78     real holding: 1 unit (~$1,683)
2026-04-17  BUY   1 / SELL 2           -> flat
2026-06-10  BUY   1 / SELL 1           -> flat
2026-06-12  BUY   1                    real holding: 1 unit
2026-06-23  BUY   1 / SELL 1           real holding: 1 unit
2026-07-17  SELL  200 @ EUR 9.07       -> flat  (~$2,094 post-split)
```

The real position was **~$1,700–2,100, about 3.2% of the book**, genuinely held
across roughly 27 trading days. The replay reports market value for those days
with that 3.2% silently absent. Stating the *bound* — "a holding worth roughly
3% of the portfolio is excluded from these days" — is a disclosure, not a
fabrication: it comes from the broker's own execution prices, the same source
tier 3 already trusts.

### F-4 (Medium) — the withholding is coarser than it needs to be

Two of Epic 33's six withheld days carry unbacked cash flows of **$5.13** and
**$25.09** — 0.008% and 0.04% of the portfolio. They distort nothing measurable
(2026-06-23 reads −1.2157% cash-inclusive against −1.2196% trade-neutral), yet a
real return day is discarded for each. `REPLAY_RECONCILIATION_TOLERANCE` ($1.00)
was calibrated for cent-level rounding across daily states, not for the
materiality of a flow against portfolio value. US-33.4 recorded this as a
deliberate, reviewable choice; this is the review.

### F-5 (Medium) — the terminal day never has a return

The terminal reconciliation always fires, so the last day's return is always
withheld (US-31.3, correctly — it is an accounting correction). But that means
**the most recent day is permanently blank**, which is the day a researcher
looks at first. Combined with F-2's permanent banner, two of the disclosure
card's notes are fixtures rather than signals.

The reconciliation exists because the replay's terminal value and the
statement's ending NAV differ by $1,366.17 — which is itself mostly the F-2
anchor offset riding through the window. Fixing the anchor shrinks the
adjustment; below tolerance it stops firing and the day publishes normally.

### F-6 (Medium) — the benchmark return is withheld although the prices are present

148 SPY closes are fetched and returned to the client, and
`benchmark_return_pct` is `null`. Cause: the cached rows come from FMP's
`historical-price-eod/light` endpoint, which carries **no `adjClose`**, so the
basis classifies as `price_return_only`, and the partial-unlock allowlist
requires `identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only`.

So the comparison chart draws a benchmark line the researcher can see rising,
next to a benchmark return figure that says nothing.

### Examined and found correct — do not "fix" these

- **The Exposure and Risk tabs are healthy.** They run on the snapshot-analytics
  and synthetic-history truth classes, badged `Synthetic`, and are unaffected by
  the replay proof gate. Their engines return real numbers.
- **The withholding decisions of Epic 33 are right** — the phantom quantity, the
  anchor guard, the unbacked-cash guard. This epic changes what is *said about*
  them, and their materiality thresholds, not whether they fire.
- **The money-weighted return is real** and correctly published (5.30%).
- **`monthly_returns` are computed and reliable** on every range (8 months on
  All) — the monthly grid is not affected.
- **The terminal reconciliation is not a bug.** Snapping to the broker's ending
  NAV is correct; only its size and its consequence are in scope.

## Goal

**Publish the honest number with its trust level, rather than withholding it
because a stronger claim cannot be proven.** Concretely:

- A time-weighted return computed from the imported replay is publishable with
  an explicit, weaker trust state — never silently `null`, never dressed up as
  `verified_total_return`.
- Every disclosure on screen must be **clearable by some real input**. A warning
  that cannot turn off is a design bug, not a safety feature.
- Withholding stays, but is **bounded and quantified**: the researcher is told
  how much was withheld, and immaterial amounts do not cost a whole day.

## Non-goals

- **Not weakening the fabrication guardrails.** Nothing here publishes a value
  the engine did not compute from broker truth or market data. `withheld` still
  never collapses into `unavailable`, and no tier is silently promoted.
- **Not claiming GIPS-style verified total return.** The strict admission gate
  stays exactly as strict; this epic stops treating failure to meet it as
  "no answer available".
- **Not a corporate-action model** (Epic 33's non-goal still stands). F-3
  discloses a magnitude from observed trade prices; it does not reconstruct the
  split or re-value the position.
- **Not touching the Exposure or Risk tabs.**

## Story list

| Story | Title | Scope |
|---|---|---|
| US-34.1 | Findings-first audit of the withheld Dashboard surface | **Done on creation** — F-1…F-6 above with reproduced evidence, plus the examined-and-correct list. No code touched. |
| US-34.2 | Publish the replay's time-weighted return under an explicit `replay_derived` trust state | F-1/F-1a: replace the hardcoded `portfolio_path="unavailable"` with a real classification; add a trust state between `verified_total_return` and `unavailable` for a return computed from a reconstructed replay; publish TWR, and the drawdown that rides the same gate, labelled as such. The strict admission gate is untouched — this adds a rung below it. |
| US-34.3 | Make the cash anchor reachable | F-2 (and most of F-5): distinguish a **structural** date offset from an **unreconciled** anchor, and value the opening positions at the statement-period start where coverage allows so the two dates can agree. Anchor trust becomes clearable; the terminal adjustment shrinks with it. |
| US-34.4 | Disclose what a withheld holding was worth, and stop withholding immaterial days | F-3 + F-4: bound the withheld position's value from the broker's own execution prices and surface it on the disclosure; replace the flat $1.00 unbacked-cash tolerance with a materiality test against portfolio value. |
| US-34.5 | Publish the benchmark return on a stated basis | F-6: source `adjClose` where the provider offers it, and publish a `price_return_only` benchmark return labelled as such when it does not — a price return is a real number, and saying so beats saying nothing. |

Recommended order: **US-34.2 first** — it is the finding the researcher actually
feels. Then US-34.3 (which also resolves most of F-5), then US-34.4, then
US-34.5.

US-34.2 and US-34.5 both add a trust rung; they are separate stories because the
portfolio and benchmark paths have independent contracts, but they should be
reviewed together for consistent naming.

## Success signals

- The Dashboard shows a time-weighted return for every range, each carrying a
  visible trust state, and the "All" figure is explainable against the
  statement's own 4.765666%.
- No disclosure on the card is present on every run: each one is either absent
  or attributable to something specific about this statement.
- A researcher can state how much of their portfolio the replay is not showing
  them, in dollars, without reading the ledger.
- The strict admission gate still refuses to emit `verified_total_return` on the
  imported path — the weaker rung is visibly weaker.
- `python scripts/run_all_tests.py` stays green, and the Epic 31/33 regression
  pins still assert what they assert today.

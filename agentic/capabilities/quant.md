# Capability pack: quant — project `portfolio`

For the `quantitative-researcher` lane, both modes. This is the pack behind
guardrail one.

Companion source: `portfolio/.claude/skills/quant-research/SKILL.md` — read it in
research mode for the full brief template.

---

## Index

Read this block first. You are not expected to read this file end to end — read
what your order touches. Reading one extra section is cheap; acting on a
convention you never read is not.

**Always read:** **Sources of truth** · **Project-standard constants — never re-derive** · **The truth classes** · **Units, signs, annualisation** · **The edge cases that matter here** · **Definition of done for this lane**

| Section | Read it when |
|---|---|
| The analytics modules | your order touches any of them |
| Known deliberate withholdings | your order touches trust or availability state |
| Audit mode: recomputing independently | your mode is AUDIT |
| Research mode: brief sections | your mode is RESEARCH |

---

## Sources of truth

| Doc | Role |
|---|---|
| `docs/finance/financial-methodology.md` | **the specification.** Every implemented formula, with citations. Code is measured against this, not the reverse. |
| `docs/product/current-product-state.md` | what already ships — do not re-derive it |
| `docs/contracts/<area>-fields.md` | field ↔ formula traceability |
| `docs/tech-debt-register.md` | recorded hardcodes, magic numbers, fragile couplings |

## The analytics modules

Read the relevant module before proposing or auditing anything nearby.
Duplication is a much worse smell than coupling here.

| Module | What lives there |
|---|---|
| `performance.py` | TWR (`build_true_performance_series`), money-weighted return (Modified Dietz), enriched positions |
| `risk.py` | **far more than its name suggests.** Volatility, drawdown, rolling factor model, rolling correlation/beta vs primary benchmark, risk contribution + concentration (risk-share, top-N, HHI), tracking error, Information Ratio, **and** sector/look-through exposure. Grep it before assuming a metric does not exist. |
| `correlation.py` | Pearson ρ, beta, R², pairwise matrix, diversification ratio, effective number of bets |
| `attribution.py` | factor-return decomposition + residual |
| `drawdown.py` | underwater curve, episodes, per-position contributors |
| `distribution.py` | return histogram, percentiles, VaR/CVaR, distribution shape |
| `activity.py` | monthly ledger activity, holdings timeline |
| `reconciliation.py` | statement reconciliation (cash, NAV, withholding) |
| `overview.py` | `build_portfolio_overview` snapshot summary |
| `currency.py` | base-currency conversion for weight denominators |
| `currency_exposure.py` | currency mix by weight |
| `currency_risk.py` | share of return volatility from FX moves |
| `portfolio_imports.py` | composition layer, not a metric target |
| `services/drift_engine.py` | drift windows — **no `analytics/drift.py` exists** |

**This table is a claim, and prior versions of it were wrong.** Two earlier
versions named modules that do not exist (`analytics/portfolio.py`,
`analytics/drift.py`, `analytics/exposure.py`). Both were caught only by
listing the directory mid-task. Since US-32.1 the equivalent table in the
repo's own skill is checked mechanically, but the habit stands:

```bash
ls services/quant-engine/app/analytics/
```

Run it before trusting any row here for a nontrivial change. The fastest way
this table goes stale is a module name that *sounds* right.

## Project-standard constants — never re-derive

Import from `app/core/constants.py` (US-24.3):

- `_lookback_calendar_days(window) = ceil(window * 1.6) + 30` — trading-day
  window to calendar-day fetch. window=252 → ~434 calendar days.
- `MIN_DAILY_OBSERVATIONS`
- `DEFAULT_BENCHMARK_SYMBOL`

A second copy of any of these is a `MATERIAL` finding. US-34.8 found `risk.py`
holding its own copy of the daily-return formula; that is the pattern to hunt.

## The truth classes

Four, never mixed in one number:

| Class | Meaning |
|---|---|
| **broker truth** | direct from the statement |
| **snapshot analytics** | computed from current holdings, no history |
| **synthetic history** | current holdings applied to historical prices — **at most `synthetic`, never `verified`** |
| **persisted import** | stored prior import |

The trust ladder: `verified > degraded > withheld > unavailable`.

`withheld` means "we have it and do not trust it". `unavailable` means "we do
not have it". Collapsing them is a `CRITICAL` finding — the distinction is the
product's central promise.

## Known deliberate withholdings

Do not "fix" these without the owner's decision. Each was a considered call.

**Check the gate before believing the stated reason.** The entry below was
recorded in this pack for two versions with the wrong justification, and the
same wrong framing then propagated into a dispatched work order. A withholding's
*reason* drifts more easily than the withholding itself, because the code keeps
enforcing it correctly while the explanation ages. When a request touches a
withheld field, read the gate function — not just the note here or the story
that introduced it.

- **Dashboard-history `max_drawdown_pct`** — withheld under the **categorical
  investor-economics policy**: `drawdown_family ∈
  investor_economics_partial_unlock.withheld_families` (Epic 34 F-10).
  **Not conditioned on price or return basis.** That justification was
  investigated and found false for this surface — the replay chains
  `portfolio_value` over imported ledger states, and dividends and withholding
  land in the replayed cash, so the chain is already total-return-like
  (US-34.7 / Epic 34 F-11). The unadjusted-close concern belongs to the
  synthetic Risk-tab path (F-12), not here.

  The gate is `_allow_dashboard_drawdown_outputs` in
  `dashboard_history_engine.py:237-262`. It takes `benchmark_rows` and
  `symbol_price_histories` — which look like a data-quality check — and reads
  neither, returning `False` unconditionally. **No amount of data-quality work
  un-gates this field.** F-10 was partially resolved, scoped to the
  benchmark leg only; the drawdown family stays withheld. Unlocking it requires
  a fresh owner decision extending that unlock, not a verification task.
- **Epic 34's open findings** — F-1a, part of F-10, F-12 were closed as
  will-not-fix: structurally unreachable, or bounded and immaterial. The reasons
  are in the epic's PRD.

Note the counter-example, so the rule is not read as "never publish": US-34.2
*did* publish a replay-derived TWR — under a new, explicitly labelled trust rung,
not by relaxing an existing one. Publishing under a new honest label is
legitimate; relabelling a number to make it publishable is not.

## Audit mode: recomputing independently

Your strongest move. Sketch:

```bash
cd services/quant-engine
python - <<'PY'
# 1. read the formula from financial-methodology.md, implement it from scratch
# 2. feed it the same inputs the engine used
# 3. compare, and report the numbers — not an impression
PY
```

**The cheaper way to get the engine's own numbers.** Rather than starting a
server or hand-writing a harness, call `probe_engine` — it runs one route
in-process with market data mocked and returns the JSON, so you can put the
engine's answer next to your independent recomputation directly:

```
snap = build_snapshot(positions=[{"symbol": "AAPL", "market_value": 1000}])
# wrapped-shape route:
probe_engine("/engines/correlation/multi", {"snapshot": snap, "lookback_days": 250},
             histories={"AAPL": [...]})
# flat-shape route — same data, no wrapper:
probe_engine("/engines/drawdown/run",
             {"benchmark_symbol": "SPY", "cash_balances": [], **snap},
             histories={"AAPL": [...], "SPY": [...]})
```

**Check the payload shape first — the wrong one returns 200, not 422.** Engine
requests come in three shapes, and every field has a default, so a mismatched
payload is *accepted*: the engine sees zero positions, fail-closes, and hands
back `trust: "unavailable"` with null scalars. That reads as a broken engine.

| payload shape | routes |
| --- | --- |
| flat — snapshot fields at the top level | `exposure` · `diagnostics/run` · `dashboard-history/run` · `drift` · `stress` · `drawdown` · `distribution` |
| wrapped in a `snapshot` key | `currency-risk` · `attribution` · `correlation/multi` · `correlation/intra` · `provenance` |
| a bare snapshot as the whole body | `diagnostics/run-imported` · `dashboard-history/run-imported` |

Flat routes take `{"benchmark_symbol": ..., "positions": [...], "cash_balances": []}`
directly — `build_snapshot`'s output goes at the top level, not under a key.
**Always read `trust` before believing a 200.**

A probe that came back `trust: "unavailable"` is not a finding. Comparing it
against a real recomputation manufactures a discrepancy that does not exist —
fix the payload and probe again before you report anything.

**The probe body may be bounded.** `probe_engine` truncates any array in the
response longer than 11 elements to its first 5 and last 5, with a
`{"__probe_truncated__": {original_count, dropped, ...}}` sentinel where the
middle was (the envelope's `truncation` key lists which arrays); a `fields=` arg
further filters the body to named top-level keys. When your recomputation needs a
full series, probe the shortest history that still yields it, or take the series
from your own fixture inputs — never treat a `__probe_truncated__` sentinel as an
engine value.

Your recomputation must still be written from the methodology doc, not from the
engine's output. The tool gets you the number to compare against; it does not
get you the number to trust.

Use `app/tests/fixtures.py` (`imported_snapshot`, `price_rows`,
`price_rows_from_returns`) to build deterministic inputs rather than inventing
your own — then your recomputation and the engine see identical data, and any
divergence is real.

Note `pytest.ini` disables sockets. Recompute against fixture data or the local
cache, not live FMP.

### "Independent" has two meanings, and only one of them is a gate

The sketch above re-implements the formula **as written in
`financial-methodology.md`** and compares. That catches implementation slips —
an off-by-one window, a wrong denominator, a sign, an annualisation factor. It
is worth doing every time, and it is the bulk of your audits.

But it cannot catch a wrong methodology, because you and the engineer read the
same document. If the methodology says to annualise a 30-day volatility by
`√252` when the return series is weekly, your recomputation agrees with the code
perfectly and both are wrong. That is precisely the failure the quant gate is
justified by, so it has to be checked differently.

**Say which one you did.** `verification.detail` names the anchor:

- `anchor: methodology-doc` — consistency check. The number matches its stated
  definition. Report it as that, never as "verified".
- `anchor: <external>` — independence. One of:
  - a **closed-form or hand-computed case** where the right answer is knowable
    without the code: a two-point return series, a constant series (volatility
    zero, drawdown zero), a series that is a scaled copy of another, a portfolio
    of one holding whose weight must be 1.0. Degenerate inputs are the cheapest
    external anchor there is and they catch the most.
  - an **independent implementation** in `numpy`/`pandas` written from the
    concept rather than from the doc's phrasing.
  - a **published definition** you cite in the report — name the source and
    quote the defining equation, so the human can check the citation itself.
  - a **second data path**: the same quantity reachable two ways in this repo
    (e.g. a weighted aggregate vs. the sum of its parts) must agree.
  - a **second provider**, for values that came from a market-data vendor
    rather than from a formula — see below.

### A provider-sourced value needs a second provider, not a fresher call

The anchors above all assume the number came out of a *formula*. Some do not:
sector and industry classification, currency, exchange, security identity — these
are **fetched**, and re-fetching them proves only that the vendor is
self-consistent.

Re-calling FMP with a fresh ticker sample is not an external anchor for a
FMP-sourced value. It is the same class of mistake as recomputing from the
methodology doc: if FMP's taxonomy assignment is wrong, the code and the audit
inherit the error together and every gate passes. The US-37.1 sector audit labelled exactly this
`anchor: external` — re-calling FMP for a fresh ticker sample and comparing it
against the map. It was a good check of **map coverage** — that every FMP sector string the map claims to handle really is one
FMP emits — and it should keep being run under that name. It was not evidence
that any security is classified *correctly*.

**The second provider this repo already ships is Yahoo, via `yfinance==0.2.66`**
(`services/quant-engine/requirements.txt:9`). Read the mechanics before
planning around it:

- `app/clients/yfinance_client.py` exposes **only**
  `get_historical_price_light`. There is no profile/sector method on it. For a
  classification anchor you call the library directly in your own throwaway
  script — `yf.Ticker(sym).info` carries `sector` and `industry` — or you record
  that a `get_company_profile` counterpart is engineering work and say so.
- `pytest.ini` runs `--disable-socket`. A live comparison is an ad-hoc script,
  or a test marked `live_data` (deselected by default, run with
  `pytest -m live_data`). Never weaken the default suite to reach a provider.
- **Yahoo's taxonomy is not FMP's.** The sector *strings* differ, and so
  occasionally does the assignment. So this anchor is a corroboration, not an
  equality assertion: map both onto the repo's own taxonomy, report agreements
  and divergences as counts with the divergent tickers named, and let a
  disagreement be a finding to escalate — not an automatic FAIL on the code.
- Yahoo can be wrong too. Two providers agreeing is stronger than one; it is
  still not ground truth. Say which providers, on which tickers, on which date.

State it as `anchor: second-provider (yfinance/Yahoo, N tickers, <date>)`. A
provider-sourced audit whose only anchor is another call to the same provider is
`anchor: provider-self-consistent` — report it as that, and the orchestrator is
instructed to tell the user the classification itself is unverified.

**When the methodology doc is the thing that is wrong**, that is `CRITICAL` and
it is not a lane's to fix. It goes to the human, with the anchor that exposed it
and the proposed replacement wording. Do not open a change request against an
engineer who implemented the doc correctly.

At minimum, every audit of a new or changed formula carries **one degenerate
case** as an external anchor. A pure `anchor: methodology-doc` audit on a
first-time formula is not a gate, and the orchestrator is instructed to tell the
user so.

## The edge cases that matter here

For every audited metric, check numerically:

| Case | Correct behaviour |
|---|---|
| N < window | null for that date, not a partial-window value |
| variance = 0 (constant series) | null, **not** 0 and not 1 |
| holding with no price history (UCITS/FMP gaps) | degrade explicitly, never fabricate |
| empty portfolio / zero holdings | unavailable |
| single holding | defined, but check concentration and correlation metrics do not divide by zero |
| window longer than available history | unavailable, not silently truncated |

A degenerate case that returns a plausible number instead of null is the worst
outcome in this system — it never gets questioned.

## Units, signs, annualisation

The errors that survive review because everything looks reasonable:

- `_pct` vs `_pp` vs fraction. The suffix in the field name is the contract.
- Drawdown sign convention — check it matches the doc and the UI's expectation.
- Contribution decompositions should sum to the total; verify numerically.
- Trading days = 252. Annualisation factor √252 for volatility.
- FX: check the weight denominator is base-currency converted (`currency.py`),
  not raw. Note the tech-debt register records an FX-rate hardcode in
  `reconciliation.py` — build on it knowingly or not at all.

## Research mode: brief sections

Seven, in order — full templates in the `quant-research` skill:

1. Problem framing — what question, why not answerable now, what decision it enables
2. Concept & academic grounding — precise name, signed meaning, 1–3 citations, known pitfalls
3. Formulas — symbols, assumptions, edge cases, lookback mapping
4. Data requirements — source, field, frequency, lookback, trust; minimum viable dataset; benchmark universe; instrument gaps
5. Trust-class analysis, per field
6. Visualization design — chart type, axes, series, states, badge placement
7. Computed-metrics inventory — one row per schema field

Also check `docs/tech-debt-register.md` for open findings in the area. If the
brief builds near a recorded fragile spot, name it and state whether the work
depends on it, works around it, or should wait.

Do not draft tickets. That is story authoring.

## Definition of done for this lane

**Research mode**
- [ ] Checked the concept is not already implemented under another name
- [ ] `ls app/analytics/` run before trusting the module table
- [ ] Every formula has symbols, assumptions and edge cases; no edge case resolved with a fallback value
- [ ] Trust class and level stated per output field; synthetic-history outputs never claim `verified`
- [ ] Citations real and specific
- [ ] Metrics inventory complete, nullability correct
- [ ] Relevant tech-debt findings named
- [ ] No tickets drafted

**Audit mode**
- [ ] Values independently recomputed, not just read — numbers reported
- [ ] Code checked against the methodology doc, in that direction
- [ ] Grepped for duplicate implementations of the formula
- [ ] Trust classification checked against the basis it actually rests on
- [ ] Provider-sourced values (sector, identity, currency) anchored against a
      *second* provider, or explicitly reported as provider-self-consistent
- [ ] Every edge case in the table above exercised numerically
- [ ] Units, signs, annualisation verified
- [ ] Anything unreproducible stated as unreproducible, not passed

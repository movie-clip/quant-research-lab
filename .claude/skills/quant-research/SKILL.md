---
name: quant-research
description: >
  Financial quant research skill. Use when the user describes a new analytics
  feature (chart, metric, model) and needs a rigorous research brief before
  writing stories. Produces: concept definition, formulas with academic
  citations, data requirements, trust-class analysis, visualization design,
  computed-metrics inventory, and a vertical story breakdown ready for
  write-story. Also updates docs/finance/financial-methodology.md and drafts a
  PRD section. Triggers when the user says "research X", "what data do I need
  for X", "how should X chart work", "write a research brief for X", or
  describes an analytics idea without yet having a story.
---

# Quant Research Skill

This skill acts as an embedded quantitative finance researcher. It takes a
feature idea involving analytics, charts, or financial metrics and produces a
structured **Research Brief** — the artefact that feeds into `write-story` and
`docs/finance/financial-methodology.md`.

The brief is rigorous enough that any implementer (or another agent running
`write-story`) can author well-grounded acceptance criteria without needing
additional financial context.

## The cycle this skill plugs into

```
quant-research → write-story → build-story → write-tests → verify-story → update-docs
 (this skill)     (plan)        (implement)    (cover)        (QA)         (sync docs)
```

This skill's output is the **Research Brief** + a methodology-doc section.
That brief is consumed by `write-story` to produce a ticketed story.
Do not draft tickets here — that's write-story's job.

---

## Where things live

| Path | Purpose |
|---|---|
| `docs/finance/financial-methodology.md` | Source of truth for every implemented formula — **always update** |
| `docs/product/epic-roadmap.md` | Active epics; determines which epic number is next |
| `docs/product/prd/<epic>.md` | PRD per epic — the brief feeds directly into this |
| `docs/product/current-product-state.md` | What already ships — do not re-describe shipped code |
| `docs/contracts/<area>-fields.md` | Backend ↔ TS ↔ UI field contracts |

## Analytics module layout (read before proposing)

Already-shipped analytics live here. **Read the relevant module before
proposing related work** — duplication is a much worse smell than coupling.

| Module | What lives here | Don't propose to extend if … |
|---|---|---|
| `app/analytics/performance.py` | TWR (`build_true_performance_series`), money-weighted return (Modified Dietz, `build_performance_summary`), enriched positions | Already covers basic returns |
| `app/analytics/risk.py` | Volatility, drawdown, rolling factor model, rolling-risk series (correlation/beta vs primary benchmark), risk contribution + concentration (risk-share, top-N risk-share, HHI), relative risk (tracking error, Information Ratio), **and** sector/look-through exposure (`build_lookthrough_exposure`, `build_lookthrough_sector_exposure`) — this file is the largest module by far and covers far more than its name suggests; grep it before assuming a metric doesn't exist | Already covers primary-benchmark rolling stats, risk-contribution concentration, and sector/look-through composition |
| `app/analytics/correlation.py` | Pearson ρ, beta, R², pairwise correlation matrix, diversification ratio, effective number of bets; used by both the multi-benchmark engine and the intra-portfolio-correlation engine (`services/intra_correlation_engine.py`) | Need a new pairwise-stat helper — extend in place |
| `app/analytics/attribution.py` | Factor-return decomposition (per-factor contribution + residual) | Already covers factor attribution |
| `app/analytics/drawdown.py` | Underwater curve + drawdown episodes + per-position contributors (Risk tab) | Already covers drawdown analytics |
| `app/analytics/distribution.py` | Return histogram + percentiles + VaR/CVaR + distribution shape (Risk tab) | Already covers VaR & distribution |
| `app/analytics/activity.py` | Monthly ledger activity series, holdings timeline | Already covers activity/timeline reconstruction |
| `app/analytics/reconciliation.py` | Statement reconciliation checks (cash, NAV, withholding) | This is import-admission territory, not a new-metric target |
| `app/analytics/overview.py` | `build_portfolio_overview` — current-holdings snapshot summary | Already covers basic snapshot overview |
| `app/services/drift_engine.py` | Portfolio vs benchmark drift (1m/3m/6m/12m/since-import + indexed series) — **no separate `analytics/drift.py`**; the drift computation lives directly in the service | Already covers drift windows |
| `app/services/<name>_engine.py` | Wires market data → pure analytics. Use `MarketDataService`. |
| `app/services/attribution_engine.py` | Has the `_lookback_calendar_days(window) = ceil(window*1.6)+30` heuristic + uses `_build_synthetic_snapshot_history_states` from `diagnostics_engine.py` — reuse for any new windowed synthetic-history analytic. This heuristic and `MIN_DAILY_OBSERVATIONS`/`DEFAULT_BENCHMARK_SYMBOL` now live in the shared `app/core/constants.py` (US-24.3) — import from there, don't re-derive. |
| `app/services/market_data.py` | `MarketDataService.get_fx_history(pair, from_date, to_date)` already exists (thin wrapper over `get_historical_prices`) but has zero callers today — a currency-risk brief can build on this rather than adding new FMP plumbing, but verify it still works (it was dead/untested at time of writing). |

A new analytic that fits none of these gets its own `app/analytics/<name>.py`
file. Don't shoehorn into `risk.py` — though note `risk.py` already *has*
absorbed several concerns (factor model, concentration, sector exposure) that
their names alone wouldn't suggest, precisely because past additions took
the path of least resistance. Resist adding one more; if a new metric is a
genuinely distinct concern, give it its own file even if `risk.py` looks like
the path of least resistance.

**This table is a claim about the codebase at the time it was last verified,
not a guarantee — and it has been wrong more than once.** Two prior versions
of this table named modules that don't exist: `app/analytics/portfolio.py`
(the real module is `performance.py`) and, separately, `app/analytics/drift.py`
/ `app/analytics/exposure.py` (drift lives in `services/drift_engine.py`;
sector/look-through exposure lives inside `risk.py`). Both were caught only
by grepping the actual codebase mid-task, not by re-reading this table more
carefully. **Run `ls services/quant-engine/app/analytics/` before trusting
any row here for a nontrivial change** — don't just grep for the one
function name you expect; confirm the whole module list, since the fastest
way this table goes stale is a name that *sounds* right.

---

## Step 1 — Clarify the idea

Before writing anything, check:

1. **Is the concept already partially implemented?** Read `docs/product/current-product-state.md` and `docs/finance/financial-methodology.md`. If a closely related formula exists, the brief should extend it rather than duplicate it.
2. **Which tab does this belong to?** Dashboard = portfolio economics over time. Exposure = holdings composition + market co-movement. Risk (Epic 13) = pre-decision risk-budget views (stress scenarios, drawdown analytics, VaR & distribution).
3. **Is there an obvious truth-class conflict?** Anything that applies current holdings to historical prices is *synthetic*. Anything from the broker statement is *broker truth*. Never mix in one metric.
4. **Is the scope one epic or many?** If the idea naturally decomposes into 3+ independent user-visible capabilities, plan it as one epic with multiple stories. If it is a single coherent feature, it may be one or two stories.
5. **Check `docs/tech-debt-register.md` for open findings in the area you're touching.** If the brief proposes new work in or near a module with a recorded hardcode/fragile-coupling/magic-number finding (e.g. the FX-rate hardcode in `reconciliation.py`, the lookback-heuristic duplication, the mapping-score rubric in `risk.py`), the brief should name the finding and state whether the new work depends on it, works around it, or should wait for the Epic-24 fix first. Don't silently build on top of a documented known-fragile spot.

If any answer is unclear, ask one targeted question before proceeding.

---

## Step 2 — Produce the Research Brief

The brief has seven required sections. Write them in order.

### 2.1 Problem framing

Answer these three questions in 2–4 sentences:

- What question is the portfolio researcher trying to answer with this feature?
- Why can't they answer it with what's already on screen?
- What decision or action does a good answer enable?

### 2.2 Financial concept & academic grounding

- Name the concept precisely (e.g. "rolling Pearson correlation", not just "correlation").
- Give the signed, scalar definition (what does a value of +1, 0, −1 mean in portfolio context?).
- Cite 1–3 academic or practitioner references (textbook name + chapter, or paper author + year). These citations become required content in `financial-methodology.md`.
- Note any well-known limitations or pitfalls of this metric (e.g. Pearson assumes linear relationships; rolling windows introduce look-ahead lag at the edges).

### 2.3 Formulas

Write every formula the backend must implement, in the exact notation used in `financial-methodology.md` (plain-text math blocks). For each formula state:

- Symbol definitions
- Assumptions (e.g. daily returns, trading-day count = 252)
- Edge-case handling (what happens when N < window? when variance = 0?)
- **Lookback heuristic** (for windowed analytics): use
  `_lookback_calendar_days(window) = ceil(window * 1.6) + 30` to convert
  trading-day windows to calendar-day fetches. This is the project standard
  — never re-derive it. State the window-to-fetch mapping in the brief
  (e.g. "window=252 trading days → fetch ~434 calendar days").

Example block format:

```text
rolling_correlation_t(w) = cov(r_portfolio[t-w:t], r_benchmark[t-w:t])
                           / (std(r_portfolio[t-w:t]) * std(r_benchmark[t-w:t]))

where:
  r_portfolio_t  = daily portfolio return (cash-flow-neutral, see Portfolio Return Methodology)
  r_benchmark_t  = simple daily price return of benchmark symbol
  w              = rolling window in trading days
  t              = current date index

Edge cases:
  std = 0 (constant price series): return null, not 0 or 1
  len(series) < w: return null for that date
```

### 2.4 Data requirements

List every external data dependency:

| Source | Field | Frequency | Lookback | Trust |
|---|---|---|---|---|
| `MarketDataService` | adjusted-close prices | daily | 252 trading days | synthetic |
| `PortfolioEngineRequest` | holdings + quantities + import date | snapshot | n/a | broker truth |

Also state:
- **Minimum viable dataset** — what is the minimum number of data points needed to produce a non-null result?
- **Benchmark universe** — list the exact symbols (e.g. SPY, QQQ, GLD, IEF, VT, EFA) and what each proxies.
- **Instrument gaps** — if a holding has no price history (e.g. UCITS ETFs with limited FMP coverage), how does the engine handle it? (Degrade gracefully, do not fabricate.)

### 2.5 Trust-class analysis

Answer for each output field:

- What truth class does it belong to? (broker truth / snapshot analytics / synthetic history / persisted import)
- What is the trust level when all data is available? (`verified` / `synthetic` — note: anything applying current holdings to historical prices is at most `synthetic`)
- What degrades it? (missing price history, short window, UCITS gap)
- What makes it `unavailable`? (zero history, no holdings)
- Is it withheld? (only for investor-economics paths requiring full return-basis proof)

Rule: never write a trust analysis that ends with "fall back to 0" or "use adjacent value". Missing data → `unavailable` field, never fabricated fill.

### 2.6 Visualization design

Specify the chart precisely enough that a frontend developer can implement it without additional research:

- **Chart type** (line, bar, scatter, heatmap, table, sparkline…)
- **X-axis** (field name, label, tick format)
- **Y-axis** (field name, label, range, tick format, gridlines)
- **Series** (one per line/column — field name, color semantics, tooltip content)
- **Interaction** (selector, hover tooltip, click-to-drill, none)
- **Empty / loading / unavailable states** (what the researcher sees when data is absent — never blank, never zero)
- **Trust badge placement** (where the "Synthetic" or "Unavailable" badge appears)
- **Responsive considerations** (does it collapse to a table on narrow width? which columns are preserved?)

If multiple chart types are plausible, list them and recommend one with a one-sentence rationale.

### 2.7 Computed metrics inventory

Table of every field the backend schema must expose for this feature:

| Field | Type | Formula reference | Trust | Nullable? | Notes |
|---|---|---|---|---|---|
| `rolling_correlation` | `float \| null` | §2.3 formula | synthetic | yes | null when window not yet filled |

This table becomes the contract schema. Every row here maps 1-to-1 to a field in the Pydantic schema and the TypeScript type.

---

## Step 3 — Epic & story structure

Decompose the feature into vertical stories. Each story must:

- Deliver a **complete, user-visible capability** (not a backend stub, not a UI skeleton)
- Have a **clear "why"** — what decision does it enable the researcher to make?
- Be **independently mergeable** — the product works before and after each story ships
- Include backend + frontend + tests in one ticket sequence

Recommended decomposition pattern for analytics features:

| Story | Scope | Value delivered |
|---|---|---|
| US-X.1 | Core engine + single-benchmark display | Researcher sees the new metric for SPY |
| US-X.2 | Multi-benchmark extension | Researcher compares metric across all benchmarks |
| US-X.3 | Chart / time-series view | Researcher sees how the metric evolves over time |
| US-X.N | Docs + methodology formalization | Formulas are in the methodology doc and contract |

The docs ticket is always last and covers: `financial-methodology.md`, `docs/contracts/<area>-fields.md`, `epic-roadmap.md` slice log, story status to Done.

State explicitly what is **out of scope** for each story.

---

## Step 4 — Update `financial-methodology.md`

After writing the brief, append a new section to `docs/finance/financial-methodology.md` with:

1. The section heading (matching the concept name)
2. All formulas from §2.3 (verbatim)
3. Edge-case rules
4. The academic citation(s)
5. The implementation target (`services/quant-engine/app/analytics/...` — placeholder path is fine if not yet implemented)

Follow the exact style of existing sections in that file (plain-text math blocks, `Implementation:` subsection, `Contract rule:` subsection).

---

## Step 5 — Draft the PRD section

If this is a new epic, produce a draft PRD suitable for saving to `docs/product/prd/epic-<N>-<slug>.md`. The PRD must cover:

- **Problem**: one paragraph on what the researcher cannot do today
- **Goal**: 2–4 bullet points, observable outcomes
- **Non-goals**: at least 2 explicit non-goals
- **Story list**: table with story number, title, one-line scope
- **Success signals**: how we know the epic is working in practice

If this extends an existing epic, produce only a story list addition.

---

## Guardrails (non-negotiable)

1. **Methodology traceability** — every metric in the inventory must have a formula in §2.3. If you cannot write a precise formula, do not add the metric.
2. **Truth-class separation** — synthetic history metrics and broker-truth metrics must never share a schema field or a UI card without explicit labelling.
3. **Trust semantics** — the brief must describe the `unavailable` path for every nullable field. "Degrade gracefully" is not enough — name the exact output.
4. **No execution** — no metric or visualization may suggest or imply trade signals, target weights, or buy/sell recommendations.
5. **Desktop stays thin** — the brief must not assign any formula computation to the frontend. All math lives in the quant engine.
6. **Academic citation required** — any new formula section in `financial-methodology.md` must include at least one citation (textbook or peer-reviewed paper).

---

## Definition of Done (for this skill)

- [ ] Research Brief covers all seven sections (§2.1–2.7) with no placeholder text
- [ ] Every formula in §2.3 has precise symbol definitions and edge-case rules
- [ ] Trust-class analysis covers every output field in the inventory (§2.7)
- [ ] Visualization design is specific enough to implement without further research
- [ ] Epic/story structure lists complete vertical slices, each with a one-line "value delivered"
- [ ] `docs/finance/financial-methodology.md` updated with new formula section(s)
- [ ] PRD draft (or PRD addition) written and ready to save
- [ ] No guardrail violated in any section

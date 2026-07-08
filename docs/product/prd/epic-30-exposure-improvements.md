# Epic 30 — Exposure Improvements

**Status:** Backlog (created 2026-07-08)
**Created:** 2026-07-08
**Seeded by:** Owner report: the vs-Market drift panel renders no chart until
the benchmark dropdown is changed, and the window cards then show impossible
returns (Portfolio 1M −100.59%, 3M −6226.32%, 6M +387.46%, 12M +2041.01% vs
SPY). All four numbers were **reproduced exactly** against the real engine
with the committed IB2026.csv portfolio, and root-caused (findings F-1..F-6
below, verified 2026-07-08 — no fixes applied during diagnosis, matching the
Epic 27 findings-first discipline).

## Problem

The Exposure tab's flagship panel displays fabricated numbers. This violates
guardrail #3 (trust semantics over fabrication) in the worst possible way:
the wrong values carry `trust="synthetic"` and a confident basis note, so
nothing warns the researcher they are garbage. Beyond the verified drift
findings, the rest of the Exposure tab's calculation surfaces (rolling
correlation & beta, concentration, factor attribution, factor drift summary,
multi-benchmark correlation, intra-portfolio heatmap) have never had an
Epic-27-style correctness audit against `financial-methodology.md` — Epic 27
audited the analytics/engine layer broadly but pre-dates several of the
drift-path changes (US-27.8) whose interaction with the request path produced
F-1.

## Goal

1. **Calculations first**: every number the Exposure tab displays is correct,
   traceable to one methodology formula, and fails closed (trust surfaced)
   when its inputs degrade — starting with the verified drift findings, then
   a full findings-first audit of every other Exposure card.
2. **UI second**: the tab renders reliably on first load (no interaction
   required to see data), and the cards meet the design-system baseline.

## Non-goals

- No new analytics or cards (currency exposure stays Epic 26).
- No Dashboard/Risk-tab scope beyond shared code the fixes touch (any shared
  regression is covered by goldens + the Epic 27 regression suite).
- No new market-data dependencies.

## Verified findings (2026-07-08 — the drift panel, F-1..F-6)

All reproduced against the committed `docs/IB2026.csv` portfolio with live
cache data; diagnosis evidence at each file:line.

| # | Severity | Finding | Evidence |
|---|---|---|---|
| F-1 | **Critical** | **Drift TWR divides by a near-zero fabricated portfolio value.** The drift request path carries positions + cash balances but **no `statement_totals` and no ledger**; `PortfolioStateEngine.build_daily_states` anchors `base_cash = starting_nav − opening_positions_value` (`engine/portfolio_state.py:52,124`), and with `starting_nav = None → 0.0` cash reconstructs as **−Σ(opening value) ≈ −$62,605** — even though the request's real `cash_balances` ($1,993.65) are ignored. Day-one `total_portfolio_value` is exactly $0.00 and later values are ±$1k noise; `_time_weighted_daily_return` then yields daily "returns" like −336% and +1763% which compound into the observed −6226.32%. | `services/quant-engine/app/services/drift_engine.py:154` → `analytics/performance.py:136-139` → `engine/portfolio_state.py:52,124`. Reproduction: all four reported window values match exactly. |
| F-2 | **High** | **The TWR chain compounds through impossible returns instead of failing closed.** A daily return ≤ −100% is impossible for a long-only portfolio; `_portfolio_return` (`drift_engine.py:29-51`) happily multiplies `growth` negative (−336% → growth × −2.36 flips sign), producing −6226% / +2041% outputs that are then labeled `trust="synthetic"` with the confident note "Broker-ledger replay: compounded time-weighted return (cash-flow-neutral)" — fabrication presented as truth, and the note itself is wrong on this path (there is **no ledger** to replay). | `drift_engine.py:29-51,165-169`; observed daily returns −336.29%, +1762.99%, +596.64% in the 1M window. |
| F-3 | **High** | **Zero-coverage holdings are silently flat-anchored in drift valuations.** *(Wording corrected during US-30.2: the engine anchors them flat at the statement close — zero return contribution, dampening returns/volatility — rather than omitting them; either way undisclosed until US-30.2.)* Original finding text:  LQQ (EUR, ~3% of stock value) has zero provider price rows; the drift path's daily states simply exclude it, with none of the US-27.7 coverage disclosure (`SyntheticHistoryCoverage`) that the stress/drawdown/distribution/correlation/attribution engines surface. The drift number quietly measures a different portfolio. | `drift_engine.py:143-151` (no coverage output on `DriftResult`); reproduction shows `LQQ: 0` price rows while 19/20 symbols have data. |
| F-4 | **Medium** | **The drift panel renders "No drift data" on initial load until the benchmark changes.** The initial fetch only happens inside the full analyze flow; on workspace restore `driftResult` stays `null`, and only `handleDriftBenchmarkChange` (dropdown interaction) performs a direct fetch — exactly the reported "no chart until I select Nasdaq 100". The panel should self-fetch on mount like `FactorAttributionCard`/`BenchmarkCorrelationTable` (the project's documented self-fetching pattern). | `apps/desktop/src/app/App.tsx:483,696`; `DriftBenchmarkPanel.tsx` is props-only. |
| F-5 | **Low** | **"Since Import" window is structurally unavailable on a fresh import.** `since_import_date = imported_at.date()` is the *import timestamp* (today), so the window has <2 valuation dates and reports unavailable; the statement period start is the meaningful anchor. | `drift_engine.py:116,126-134`; reproduction: `Since Import portfolio=None trust=unavailable`. |
| F-6 | **Low** | **FX conversion of EUR/GBP position values uses the 1.0 fallback inside drift valuations** (disclosed via `fx_fallback_currencies` since US-27.8, so not silent — but with US-28.1's statement-implied `fx_rates` now available on imported snapshots, the drift request path could carry real broker-truth rates instead of degrading). Interacts with Epic 26. | `drift_engine.py:150` (`fx_history={}`); reproduction: `fx_fallback: ['EUR', 'GBP']`. |

## Audit scope (findings-first, before any fix lands)

The remaining Exposure surfaces get the Epic 27 treatment — verify each
displayed number against `financial-methodology.md` and record findings
before fixing:

- Rolling correlation & beta chart (dual-axis) — window math, price basis.
- Concentration pack (HHI / top-N / sector shares).
- Factor Return Attribution card (chart + period table).
- Factor Drift Summary card (Epic 16 surface).
- Multi-benchmark correlation table (SPY/QQQ/GLD/IEF/VT).
- Intra-portfolio correlation heatmap (Epic 17 surface).
- ETF look-through / market overlap summary.
- Cross-cutting: every Exposure card's trust badge must match its actual
  input degradation (coverage, FX, benchmark availability) — no confident
  labels on degraded paths (the F-2 lesson).

## Story list

| Story | Title | Priority |
|---|---|---|
| US-30.1 | Fix the drift valuation basis (F-1, F-2): honest portfolio-value anchor on the no-ledger path, fail-closed TWR, truthful basis note | **Critical** |
| US-30.2 | Drift coverage + FX disclosure (F-3, F-6): surface zero-coverage exclusions per US-27.7 conventions; carry statement-implied FX where available | High |
| US-30.3 | Exposure-tab first-render reliability (F-4, F-5): self-fetching drift panel + Since-Import anchor | Medium |
| US-30.4 | Findings-first audit of the remaining Exposure calculation surfaces (audit scope above; produces this PRD's F-7..F-n table) | High |
| US-30.5 | Fix the audit findings (scoped once US-30.4 lands; may split) | — |
| US-30.6 | Exposure UI polish pass (design-system audit against ui-polish baseline; a11y; empty/error states) | Low |

Recommended order: 30.1 → 30.2 → 30.3 (verified, wrong-numbers-today fixes)
→ 30.4 (audit) → 30.5 → 30.6. Stories are authored via `write-story` as each
is picked up.

## Success signals

- The reported reproduction (IB2026.csv portfolio, SPY) shows plausible
  window returns consistent with the statement's own TWR (+1.25% Jan–Jun),
  or an honest `unavailable`/degraded state — never a −6226%.
- The drift chart renders on first load of the Exposure tab with an imported
  portfolio, with no interaction required.
- Every Exposure card's displayed numbers trace to a methodology section, and
  the US-30.4 findings table shows Resolved/Documented for every row.
- `run_all_tests.py` green throughout; goldens change only where a fix
  legitimately changes displayed output (each shift itemized per-family in
  the slice log, per the Epic 28 convention).

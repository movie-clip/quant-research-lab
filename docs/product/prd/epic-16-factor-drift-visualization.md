# Epic 16 — Factor Drift Visualization

**Status:** Active
**Created:** 2026-06-04

## Problem

The Exposure tab answers "what are my factor exposures *today*?" via the
Rolling Factor Analysis card (which actually lives on the Dashboard). What it
does **not** answer is "*how have my factor exposures moved*?" — the single
most decision-relevant question for a researcher deciding whether to rebalance.

The rolling factor model already computes a full time series of per-factor
loadings (`statistical_factor_model.rolling_loadings_{20,60,252}d`), but the
only visualization is the multi-line trend chart on the Dashboard. Reading
drift off a 16-line spaghetti chart is hard: the eye cannot reliably rank
"which factor moved the most" or read the *magnitude* of each move. The
researcher needs a compact, ranked **delta** view.

This was parked during Epic 15: US-15.3 (a factor-loading-drift chart) was
cancelled once we found the existing trend chart, but the PRD explicitly left
"a complementary Factor Drift Summary delta-indicator card" as a backlog
candidate (see `epic-15-position-level-analytics.md`, Out-of-scope section).
Epic 16 ships exactly that.

## Goal

Add a **Factor Drift Summary** card to the Exposure tab: a ranked,
delta-indicator view of how each factor loading has changed from a reference
point to the latest observation, over a selectable rolling window. It reuses
the rolling loadings already present in the Exposure analysis result — **no new
backend, no new FMP calls**.

## Non-goals

- **No new backend engine, route, or schema.** The `rolling_loadings_*` series
  already ships inside `ExposureAnalysis.statistical_factor_model`; the card
  derives the deltas client-side as a presentation-layer rebasing of
  engine-computed loadings (the same pattern the Dashboard's
  `RollingFactorLoadingsCard` uses to compute chart domains and coverage).
- **No re-fit of the factor model.** Drift is computed strictly from the
  loadings the engine already produced; the card never runs OLS, orthogonalization,
  or any factor regression.
- **No relocation/restyle of the existing `RollingFactorLoadingsCard`.** That
  was the other parked candidate; it stays on the Dashboard for this epic.
- **No statistical-significance test on the drift** (e.g. confidence bands on
  the delta) — magnitude + direction only.
- **No custom reference-date picker** — the reference point is the first
  observation of the selected window's trimmed series (a deterministic anchor).

## Story list

| Story | Title | Scope |
|---|---|---|
| US-16.1 | Factor Drift Summary card | Frontend-only — `FactorDriftSummaryCard.tsx` on the Exposure tab: ranked per-factor delta (latest − reference) bars, 20d/60d/252d window selector, Synthetic trust badge, unavailable state; methodology subsection + contract doc. |

Single-story epic (quick-win follow-up). No build-order constraints.

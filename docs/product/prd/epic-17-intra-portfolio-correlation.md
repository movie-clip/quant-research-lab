# Epic 17 — Intra-Portfolio Correlation

**Status:** Proposed (research complete; not yet pulled into Next phase)
**Created:** 2026-06-05

## Problem

The Exposure tab tells the researcher how the portfolio co-moves with *external*
benchmarks (the Benchmark Correlation card: ρ / β / R² vs SPY/QQQ/GLD/IEF/VT,
plus the rolling correlation chart). It says nothing about how the portfolio's
*own holdings co-move with each other*. A researcher holding ten positions that
are all really the same bet (e.g. six mega-cap tech names) sees "ten positions"
and a diversified-looking concentration pack, but carries far less
diversification than the count implies. There is no view today that surfaces
internal pairwise co-movement, so "what is actually diversifying me?" cannot be
answered on screen.

## Goal

- Add an **Intra-Portfolio Correlation** card to the Exposure tab: a holdings ×
  holdings Pearson correlation heatmap over a selectable lookback window
  (20d / 60d / 252d).
- Surface a **diversification summary**: average pairwise correlation, the
  most- and least-correlated holding pairs, and a Diversification Ratio.
- Reuse existing market data and synthetic-history machinery — **no new data
  provider, no new FMP calls beyond the price history correlation already
  fetches.**
- Hold the guardrails: every value is `synthetic`; pairs below the minimum
  overlap are `unavailable` (never 0); cash / non-priceable positions are
  excluded; the heatmap is color-blind-safe (numeric label in every cell, not
  color alone).

## Non-goals

- **No optimizer / target weights / rebalancing suggestions.** This is a
  descriptive diagnostic only — it never implies a trade (no-execution guardrail).
- **No rolling time-series of the matrix.** v1 is a point-in-time matrix for the
  selected window, not an animated/over-time view.
- **No clustering / dendrogram / PCA factor extraction** beyond the optional
  Effective Number of Bets summary scalar.
- **No partial/imputed correlations.** A pair without enough overlapping history
  is `null`, full stop.
- **No relocation or change to the existing Benchmark Correlation card** — this
  is additive.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-17.1 | Pairwise correlation matrix engine + heatmap | Full-stack — extend `analytics/correlation.py` with `pairwise_correlation_matrix()` + `average_pairwise_correlation()`; new `intra_correlation_engine.py`; `POST /engines/correlation/intra`; schema; TS types + adapter; `IntraCorrelationHeatmap` card on the Exposure tab (heatmap + avg-ρ + most/least-correlated-pair callouts; 20/60/252 window; Synthetic badge; unavailable cells). |
| US-17.2 | Diversification summary metrics | Full-stack — add `diversification_ratio()` (Choueifaty & Coignard 2008, pure-Python) and `effective_number_of_bets()` (Meucci 2009) to the engine response + a summary strip on the card. **Dependency decision made:** ENB introduces **numpy** (`numpy.linalg.eigvalsh`) into the quant engine in this story — a single reviewable change with its own tests. |
| US-17.3 | Docs, contracts, roadmap close-out | Docs — `intra-correlation-fields.md`, methodology verification, slice log, story status to Done. |

Recommended build order: 17.1 → 17.2 → 17.3. US-17.1 is independently shippable
(the heatmap + average correlation already answer the core question); 17.2 is an
additive enrichment.

## Success signals

- A researcher with a tech-heavy book can see at a glance that their largest
  positions are mutually correlated > 0.7, and that the average pairwise
  correlation is high — i.e. the card changes their read of their own
  diversification.
- Every rendered cell traces to one `pearson()` call over a documented window;
  no cell shows a fabricated value when history is missing.
- The card passes the design-system audit (tokens only) and the color-blind
  accessibility baseline (numeric labels + sign glyphs, not color alone).

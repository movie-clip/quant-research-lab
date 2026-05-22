# PRD — Epic 3: Construction & Optimizer Methodology

**Status:** Active epic
**Last updated:** 2026-05-22

## Problem

A persisted ranking artifact answers *which names* to hold. Construction
answers *how much* of each — it turns a ranked, eligible universe plus a
current portfolio into a deterministic, auditable set of target weights under
explicit hard constraints. Today the construction engine supports a narrow set
of weighting policies (equal-weight and rank-weighted) and a small constraint
set. Researchers cannot yet express **risk-aware** intent — e.g. "don't let a
volatile name carry the same weight as a stable one" — and a shipped-but-hidden
policy (`top_n_inverse_rank_weight_v1`) is not selectable at launch.

The optimizer remains a hypothetical, non-executing preview compared against
rule-based construction baselines.

## Goals

- Deterministic construction policies broaden from order-only weighting to
  **risk-aware** weighting that consumes per-candidate factor data.
- Every shipped weighting policy is **selectable and explained** at construction
  launch — no hidden or excluded-by-default policy a researcher can't reach.
- Construction stays **methodology-traceable**: each weight maps to one engine
  formula and one code path; persisted artifacts reproduce exactly.

## Non-goals

- No execution. Construction and optimizer outputs are hypothetical previews.
- No new optimizer objective functions in this epic.
- No mean-variance / covariance-matrix optimization — inverse-volatility is a
  deterministic per-name transform, not a portfolio optimizer.
- No new ranking factors (that is Epic 2).

## Users

- **Portfolio researcher** — runs rank → construct → replay, comparing
  weighting policies under explicit constraints.

## Success signals

- A researcher can launch construction with a risk-aware weighting policy and
  see, per name, the volatility input and the weight it produced.
- No shipped construction policy is unreachable from the launch surface.
- All construction output stays reproducible from the persisted artifact.

## Shipped baseline (closed work)

- Persisted construction engine, policy catalog, preview, replay.
- Constraint set: `max_position_weight`, `min_position_weight`,
  `max_turnover_weight`, `max_trade_intent_count`, `max_sector_weight`
  (sector-concentration milestone, slices 1–3, 2026-05-12).
- Configurable launch `top_n` in `[2, 20]`.
- Ranking-to-construction handoff for `etf_ranking`,
  `intent_bound_etf_replacement_ranking`, `generic_ranking`.

History and slice log: `docs/product/epic-roadmap.md`.

## User stories

| Story | Title | Phase |
|---|---|---|
| [US-3.1](../stories/US-3.1-inverse-volatility-weighting-policy.md) | Risk-aware (inverse-volatility) weighting policy | **Next phase — ticketed** |
| [US-3.2](../stories/US-3.2-inverse-rank-weight-opt-in.md) | Make inverse-rank-weight selectable at launch | Backlog |
| [US-3.3](../stories/US-3.3-top-n-in-etf-ranking-tab.md) | Set Top N directly in the ETF Ranking tab | Backlog |

Only the next-phase story is broken into tickets. Backlog stories carry a
statement, acceptance criteria, and a rough test plan; they are ticketed when
pulled into the active phase.

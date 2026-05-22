# US-3.1: Risk-aware (inverse-volatility) weighting policy

**Epic:** 3 — Construction & Optimizer Methodology
**PRD:** [`epic-3-construction-optimizer-methodology.md`](../prd/epic-3-construction-optimizer-methodology.md)
**Status:** Next phase
**Last updated:** 2026-05-22

## Story

As a **portfolio researcher**, I want a **risk-aware construction policy that
weights selected names by inverse volatility**, so that **a volatile name does
not carry the same target weight as a stable one in an otherwise equal-weight
allocation**.

## Context

Today's construction policies are *order-aware* only (equal-weight,
rank-weighted) — they never read per-candidate factor data. This story is the
first *factor-data-aware* policy: weight ∝ 1 / realized volatility, normalized
across the selected `top_n`. The volatility input must come from the persisted
ranking artifact (it already carries factor `component_scores`), so the
construction output stays reproducible and methodology-traceable — the engine
must not fetch fresh market data at construction time.

Read before implementing: `docs/finance/financial-methodology.md` (weighting
trace, constraint evaluation, trust semantics) and
`docs/contracts/backtest-fields.md` (construction contract).

## Acceptance criteria

- [ ] AC1 — A new deterministic policy `top_n_inverse_volatility_weight_v1` is
  selectable at construction launch from all three Workspace construction
  browsers and the policy catalog.
- [ ] AC2 — For a `generic_ranking` artifact whose score config included a
  realized-volatility factor, the policy weights each of the `top_n` selected
  names as `(1/volᵢ) / Σ(1/volⱼ)`; weights sum to 1.
- [ ] AC3 — The persisted construction artifact's weighting trace records, per
  selected name, the volatility input used and the resulting weight — every
  weight is traceable to one formula.
- [ ] AC4 — When a selected name has no usable volatility input, the run
  fails closed with an explicit reason (`withheld`, not a fabricated weight);
  it does not silently fall back to equal weight.
- [ ] AC5 — When the policy is launched against a ranking artifact that carries
  no volatility factor at all (`etf_ranking`, `intent_bound_etf_replacement_ranking`,
  or a `generic_ranking` without a volatility factor), the launch surface
  explains the policy is unavailable for that artifact *before* the run.
- [ ] AC6 — Existing hard constraints (`max_position_weight`, etc.) are
  evaluated against the inverse-volatility weights exactly as for other
  policies; a violation makes the run infeasible.
- [ ] AC7 — Re-running the persisted artifact (replay) reproduces identical
  weights — no construction-time market-data fetch.

## Test plan

Backend (pytest):
- `test_construction_run_service.py` — inverse-vol weights computed correctly
  for a 3-name fixture with known volatilities; weights sum to 1.
- `test_construction_run_service.py` — fail-closed when a selected name lacks a
  volatility input (AC4); fail-closed reason is `withheld`-classed, not a weight.
- `test_construction_generic_ranking_handoff.py` — volatility input is threaded
  from `GenericRankingRow.component_scores` into the ranked-candidate contract.
- `test_routes.py` — `/construction/policies` lists the new policy with correct
  capability metadata; `/construction/run` rejects an inverse-vol launch on an
  artifact with no volatility factor with an explicit 4xx reason (AC5).
- `test_construction_run_service.py` — hard-constraint evaluation against
  inverse-vol weights (AC6); replay reproducibility (AC7).

Frontend (vitest):
- `PersistedGenericRankingConstructionBrowser.test.tsx` — the new policy is
  selectable; selecting it on a no-volatility artifact surfaces the
  unavailable explanation and blocks the CTA (AC1, AC5).
- Construction review render test — weighting trace shows the per-name
  volatility input alongside the weight (AC3).

Regression / guardrail:
- Existing equal-weight and rank-weighted policy tests stay green.
- Trust-state: no `withheld` collapsed into `unavailable`.

## Tickets

Work in order. Each ticket is one focused, reviewable change with its tests.

- [ ] T-3.1.1 — Backend: thread the realized-volatility input from
  `GenericRankingRow.component_scores` into the construction ranked-candidate
  contract (new optional field on `ConstructionRankedCandidateInput`),
  mirroring the slice-2 `sector` threading. Schema + handoff builder + tests.
- [ ] T-3.1.2 — Backend: implement the `top_n_inverse_volatility_weight_v1`
  policy — policy definition, weighting computation `(1/volᵢ)/Σ(1/volⱼ)`,
  fail-closed when a selected name lacks volatility (AC4). Unit tests.
- [ ] T-3.1.3 — Backend: weighting trace records the per-name volatility input
  and resulting weight (AC3); hard-constraint evaluation runs unchanged against
  the new weights (AC6); replay reproducibility test (AC7).
- [ ] T-3.1.4 — Backend: `/construction/policies` catalog exposes the new
  policy with capability metadata; `/construction/run` rejects the policy on a
  no-volatility-factor artifact with an explicit reason (AC5). Route tests.
- [ ] T-3.1.5 — Frontend: desktop policy catalog types + the three construction
  browsers offer the new policy; selecting it on an ineligible artifact shows
  the unavailable explanation and blocks the CTA. Vitest.
- [ ] T-3.1.6 — Frontend: construction review renders the per-name volatility
  input next to the weight in the weighting trace. Vitest.
- [ ] T-3.1.7 — Docs: `financial-methodology.md` (the inverse-vol formula +
  academic precedent), `backtest-fields.md` (contract), `epic-roadmap.md`
  (slice log + snapshot). Mark this story Done.

## Out of scope

- Equal-risk-contribution / true risk parity (needs a covariance matrix).
- Downside-volatility or drawdown-based weighting variants (possible follow-up
  stories).
- Choosing *which* volatility factor when several are present — use a single
  defined precedence (`realized_volatility_126d` preferred); document it.

## Notes / decisions

- **Formula:** naive inverse-volatility weighting, `wᵢ = (1/σᵢ) / Σⱼ(1/σⱼ)`,
  over the `top_n` selected names. Academic precedent: Maillard, Roncalli &
  Teïletche (2010) on risk-parity / equal-risk portfolios; inverse-vol is the
  diagonal-covariance special case. To be cited in `financial-methodology.md`.
- **Volatility source:** the ranking artifact's persisted `component_scores`
  `raw_value` for a realized-volatility factor — never a construction-time
  fetch (preserves reproducibility, AC7).
- **Missing data is fail-closed**, never equal-weight fallback (AC4) — a
  silent fallback would break methodology traceability.
- **Constraints unchanged:** inverse-vol produces raw weights; existing hard
  constraints are evaluated post-hoc exactly as for other policies (AC6).

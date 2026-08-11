# US-3.2: Make inverse-rank-weight selectable at launch

**Epic:** 3 — Construction & Optimizer Methodology
**PRD:** [`epic-3-construction-optimizer-methodology.md`](../prd/epic-3-construction-optimizer-methodology.md)
**Status:** Cancelled — Epic 3's construction/optimizer features were removed in Epic 8 (reset to the portfolio-analysis core). Kept for provenance; the story index has said Cancelled since then, while this file still read "Backlog".
**Last updated:** 2026-05-22

## Story

As a **portfolio researcher**, I want to **select the inverse-rank-weight
construction policy at launch**, so that **I can tilt the allocation toward
top-ranked names without that policy being hidden from me**.

## Context

`top_n_inverse_rank_weight_v1` already exists in the engine but is marked
`excluded` in the launch profile, so it never appears in the launch surface.
Currently only equal-weight and linear-rank-weight are launchable. This story
promotes it from `excluded` to `opt_in` so a researcher can choose it
explicitly — no new weighting math, only launch-eligibility.

## Acceptance criteria

- [ ] AC1 — `top_n_inverse_rank_weight_v1` has `policy_status: opt_in` (not
  `excluded`) in the construction launch profile.
- [ ] AC2 — The policy appears as a selectable option in all three Workspace
  construction browsers and `/construction/policies`.
- [ ] AC3 — Selecting it and launching produces a persisted construction
  artifact whose weighting trace matches the existing inverse-rank formula.
- [ ] AC4 — The default policy is unchanged; this story only makes an
  additional policy reachable.

## Test plan (rough — refine when ticketed)

Backend (pytest):
- `/construction/policies` lists `top_n_inverse_rank_weight_v1` as `opt_in`.
- A handoff run with the policy persists a construction artifact with the
  expected inverse-rank weights.

Frontend (vitest):
- The policy is selectable in the construction browsers; choosing it and
  running succeeds.

Regression:
- Default-policy selection and existing policy tests stay green.

## Tickets

Not yet ticketed — backlog story. Ticketed when pulled into the active phase.

## Out of scope

- Any change to the inverse-rank weighting formula itself (already shipped).

## Notes / decisions

- Pure launch-eligibility change; smallest of the remaining Epic 3 stories.

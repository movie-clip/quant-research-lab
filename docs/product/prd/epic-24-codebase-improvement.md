# Epic 24 — Codebase Improvement

**Status:** Completed
**Created:** 2026-06-19
**Seeded by:** Epic 23 (US-23.7), from `docs/tech-debt-register.md`

## Problem

Epic 23 removed dead code across the project and **catalogued** — but, by
design, did not fix — a second class of issue: hardcoded values, magic numbers,
fragile coupling, missing abstractions, and two genuine latent bugs. Those
findings live in `docs/tech-debt-register.md`, each with `file:line`, category,
severity, and effort. Left unaddressed they keep the financial core harder to
tune, audit, and trust:

- **Two latent bugs** silently drop data: a hardcoded calendar year `2025` in
  `analytics/activity.py` and `analytics/reconciliation.py` excludes every
  ledger entry from any other year.
- **Magic numbers** encode a whole mapping-quality scoring rubric, stress-shock
  vectors, regime cutoffs, and trust thresholds as scattered literals in
  `analytics/risk.py` — untunable without code edits and uncited.
- **Fragile coupling**: fixed-offset positional PDF parsing in the importers,
  broker-statement section labels baked into the domain layer, and a parsed-but-
  dropped ISIN that never reaches the modeled `ImportedInstrument.isin`.
- **Duplication**: the `ceil(window*1.6)+30` lookback heuristic, the `20`
  minimum-observations constant, and the `"SPY"` default benchmark are each
  re-implemented in several modules.

## Goal

Fix the catalogued findings as **deliberate, reviewed, behaviour-aware** changes
— the opposite discipline from Epic 23's deletions:

- **Fix the latent bugs first** (highest user impact, lowest effort).
- **Extract magic numbers** to named, documented (and where applicable cited)
  constants / config — without changing any computed result unless a finding is
  a confirmed bug.
- **Reduce fragile coupling and duplication** behind small, well-tested seams.
- Every change keeps the deterministic suite green and updates methodology /
  contract docs when a surfaced value becomes a named, documented constant.

## Non-goals

- **No new analytics or product surface.** This epic refactors and fixes; new
  metrics/cards belong in their own epics.
- **No re-introduction of removed dead code** (disposition plumbing, etc.).
- **No wholesale rewrite** of the importers or the factor model — targeted,
  reviewable improvements only.

## Story list (derived from the tech-debt register)

| Story | Title | Scope (register source) | Priority |
|---|---|---|---|
| US-24.1 | Fix hardcoded-year ledger filters | Derive the year from the statement period in `analytics/activity.py:24` + `analytics/reconciliation.py:24`; regression tests for multi-year statements | **High** (latent bug) |
| US-24.2 | Extract the risk-model scoring rubric & thresholds | Name/config the mapping-match weights, hard-caps, label thresholds, `_mapping_quality_score`, regime cutoffs, `STRESS_SCENARIOS`, the `99.0` coverage threshold in `analytics/risk.py` + `exposure_engine.py`; cite where methodology applies | High–Med |
| US-24.3 | De-duplicate shared analytics constants | One `_lookback_calendar_days` helper (stress/drawdown/attribution), one `MIN_OBSERVATIONS=20`, one `DEFAULT_BENCHMARK="SPY"` | Med |
| US-24.4 | Harden importer parsing + flow the ISIN gap | Structural validation over fixed-offset positional parsing (Freedom24/IB/ESPP); flow Freedom24 ISIN into `ImportedInstrument.isin`; decide realized-P&L modeling | High–Med |
| US-24.5 | Decouple broker format from the domain | Lift hardcoded statement section labels out of `domain/ledger.py`; introduce a shared `LedgerEntryType` enum/alias for the `BUY/SELL/...` pseudo-enum | Med |
| US-24.6 | Market-data client config hygiene | `fmp.py` HTTP `timeout` → setting; route `get_etf_holders` through the settings-driven `base_url` instead of the hardcoded `api/v3` URL | Med |
| US-24.7 | Reconcile minor hardcodes + de-export + test smells | Remaining low-severity hardcodes (`reconciliation.py` EURUSD/tolerance, `statement_importer` `/100`, `portfolio_proof` tolerance); de-export the ~60 over-exported live symbols (knip noise → helps the US-23.8 gate); migrate hand-rolled test builders to `fixtures.py`; fill the `build_position_risk_contributions` coverage gap | Low–Med |

Stories will be authored (via `write-story`) when this epic is picked up. The
authoritative, line-referenced source for every item is the
`docs/tech-debt-register.md` "Epic 24 backlog" consolidation.

## Success signals

- The two hardcoded-year bugs are fixed and covered by multi-year regression tests.
- `analytics/risk.py` thresholds/weights live in named constants or config, each
  with a one-line rationale or citation; computed outputs are unchanged (goldens
  hold) except where a finding was a confirmed bug.
- The lookback heuristic, min-observations, and default benchmark each have a
  single source of truth.
- The tech-debt register's high/med entries are all either resolved or explicitly
  deferred with a reason; `knip`/`ruff`/`vulture` stay at zero findings (the
  US-23.8 gate).

# Epic 21 — Testing Strategy & Architecture Hardening

**Status:** Active
**Created:** 2026-06-10

## Problem

The suite is large (≈385 backend pytest + ≈232 frontend vitest across ~49 test
files) and story-driven (every story ships with tests), but a review — informed
by real friction hit during Epics 16–20 — shows structural weaknesses that cost
time, hide bugs, and make "green" ambiguous:

1. **The suite is not deterministic.** Four "real portfolio" tests
   (`test_stress_engine`, `test_drawdown_engine` ×2, `test_distribution_engine`)
   hit **live FMP** through an unmocked `MarketDataService`. Offline / without an
   API key they fail, so the canonical answer to "is the build green?" has been
   "385 passed **plus 4 known failures**" for weeks. A failing-by-default suite
   trains everyone to ignore failures.
2. **The golden pipeline couples tests to live market data.** Bare `pytest`
   fails via the goldens-freshness fixture unless `SKIP_GOLDEN_FRESHNESS_CHECK=1`;
   `run_all_tests.py` regenerates `dashboardGoldens.ts` by hitting the FMP cache,
   so the file churns per machine and must be `git checkout`-ed before almost
   every commit (a documented gotcha that recurred this entire session).
3. **No systematic response-integrity coverage.** The critical NaN bug
   (2026-06-10: attribution 500, `Out of range float values are not JSON
   compliant`) passed the domain-level reconciliation check because NaN
   comparisons are always False, and nothing asserted JSON-strict
   serializability. The fix added a one-off regression for attribution only;
   the same OLS pipeline backs the rolling factor model in `risk.py`, and no
   engine response is generically guarded.
4. **Heavy fixture duplication.** Snapshot builders (`_minimal_snapshot` /
   `_snapshot`) are re-implemented in 4+ files; per-engine `MarketDataService`
   mock installers in ~7 files. The `ImportedPortfolioSnapshot` 422-shape gotcha
   is documented in two skills precisely because every new test file re-trips it.
5. **Brittle exact-equality assertions on extensible sets.** Additive changes
   broke exact-set/dict assertions twice in one week (adding `vendor` to
   `last_fetch_meta` broke 5 tests; adding an admission check broke 2). Tests
   for intentionally extensible structures should assert membership/supersets.
6. **Implicit-default pinning.** Changing the chart default window (60d → 20d)
   broke 10 frontend tests whose fixtures silently encoded the old default.
7. **Speed.** The backend suite takes ~100s, dominated by golden regeneration
   and the live-network tests' latency; pytest runs sequentially.

## Goal

Make "green" mean green, everywhere, fast:

- **Deterministic:** zero live-network calls in the default test run; the suite
  passes offline with no env vars.
- **Generic integrity:** every engine route response is provably JSON-strict
  (no NaN/inf) under a shared property-style test, not per-bug patches.
- **DRY harness:** one shared fixtures module (snapshot builders, market-data
  mock installers, price generators) consumed by all engine tests; the
  write-tests skill points at it.
- **Resilient assertions:** additive-tolerant conventions for extensible sets,
  codified in the write-tests skill.
- **Faster:** measurably shorter backend wall-time (parallelization and/or
  removing network waits).

## Non-goals

- **No coverage-percentage gate.** Coverage measurement may be added as
  information, but no failing threshold (story-driven coverage discipline stays
  the gate).
- **No new test framework.** pytest + vitest stay; this is architecture/policy,
  not tooling churn.
- **No E2E/UI-automation layer** (Tauri driver, Playwright) — separate decision.
- **No rewriting passing tests for style** — conventions apply to changed/new
  tests plus the specific brittle spots identified.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-21.1 | Deterministic suite — no live network in tests | Mock the 4 FMP-dependent "real portfolio" tests via the existing conftest synthetic-price machinery; add an autouse network guard that fails any test attempting a real HTTP call (opt-out marker `@pytest.mark.live_data` for explicitly-live tests, excluded by default). Suite passes offline with zero known failures. |
| US-21.2 | Shared test-fixtures module | `app/tests/fixtures.py` (or `_helpers.py`): canonical `minimal_snapshot()`, `position()`, `snapshot_with()`, market-data mock installers, deterministic price/return series builders. Migrate the duplicated helpers in the engine test files; update the write-tests skill to mandate it. |
| US-21.3 | Engine response-integrity property test | One parametrized test hitting every `POST /engines/*` route with a standard mocked portfolio asserting HTTP 200/422-contract + `json.dumps(body, allow_nan=False)` round-trip — generalizes the attribution NaN regression to the whole API surface. Includes a non-finite audit of `risk.py` (same OLS as the NaN bug) with guards where needed. |
| US-21.4 | Golden pipeline determinism | Dashboard goldens generated from a committed, frozen market-data fixture set instead of the live FMP cache: bare `pytest` works with no env var, `dashboardGoldens.ts` stops churning per machine, and the freshness check compares against deterministic input. |
| US-21.5 | Assertion conventions + suite speed | Codify additive-tolerant assertion rules (membership/superset for extensible sets; never pin implicit defaults in fixtures) in the write-tests skill with examples from the real breakages; convert the known brittle spots. Add `pytest-xdist` parallel execution to `run_all_tests.py` and measure the wall-time gain. |

Recommended build order: 21.1 → 21.2 → 21.3 → 21.4 → 21.5.
(21.1 first: it deletes the standing "4 known failures" asterisk that every
verification report in Epics 17–20 had to carry.)

## Success signals

- `pytest` (no env vars, no network) and `npx vitest run` are **fully green** on
  a fresh clone/offline machine.
- A future engine bug producing NaN/inf is caught by the property test in CI,
  not by a user's 500.
- New engine test files import shared fixtures instead of re-implementing the
  snapshot shape; the 422-gotcha documentation becomes unnecessary.
- `git status` is clean after `run_all_tests.py` (no goldens churn to revert).
- Backend suite wall-time drops meaningfully (target: ≥40% via xdist + no
  network waits).

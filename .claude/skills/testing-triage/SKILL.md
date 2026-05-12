---
name: testing-triage
description: Use when tests fail across either service, when investigating a regression, or when adding test coverage for new code. Triggers on test failures from pytest (backend) or vitest (frontend), or when verifying a refactor didn't break anything.
---

# Testing Triage

## Canonical entrypoint — run this first

```bash
python scripts/run_all_tests.py
```

This regenerates the dashboard golden fixtures (`apps/desktop/src/test/dashboardGoldens.ts`) via `python -m app.scripts.export_dashboard_goldens` **before** running pytest, then runs vitest. **If you skip this step and invoke `pytest` directly with stale goldens, the autouse `_check_dashboard_goldens_freshness` fixture in `services/quant-engine/app/tests/conftest.py` fails fast with an actionable message** — that error is not a regression, it means "regenerate goldens first."

To bypass the freshness check for a narrow targeted run (only when you've confirmed the surface under test doesn't touch the dashboard goldens):

```bash
SKIP_GOLDEN_FRESHNESS_CHECK=1 pytest -k "<narrow keyword>"
```

## Test commands

### Backend (pytest)
```bash
cd services/quant-engine
pytest                                # full suite (freshness-checked)
pytest -x                             # stop on first failure
pytest --tb=short -q                  # compact output
pytest tests/test_<name>.py -v        # single file
pytest tests/test_<name>.py::test_<x> # single test
pytest -k "ranking"                   # tests matching keyword
python -m app.scripts.export_dashboard_goldens  # regenerate goldens
```

Test files: `services/quant-engine/app/tests/`
Fixtures: `services/quant-engine/app/tests/conftest.py`
Sample data: `services/quant-engine/app/datasets/`

### Frontend (vitest)
```bash
cd apps/desktop
npm test                              # run once
npm run test:watch                    # watch mode
npx vitest run --reporter=verbose
npx vitest run src/features/<name>/   # single feature
npx tsc --noEmit                      # type check only
```

Test files: `apps/desktop/src/**/*.test.ts(x)`
Test utilities: `apps/desktop/src/test/`

## Triage approach

1. **Run the full suite first** — get a complete picture before fixing anything. One root cause often produces many failures.
2. **Group failures by root cause** — import errors, fixture errors, assertion errors, type errors.
3. **Fix root causes, not symptoms** — never patch individual assertions to make them pass; fix the underlying code or test.
4. **Never skip a failing test** — no `pytest.mark.skip`, no `it.skip`, no commenting-out without explicit instruction.
5. **Re-run after each fix** — verify nothing new broke.
6. **Distinguish pre-existing vs introduced** — `git stash` and re-run the failing test on main if unsure. Don't take blame for failures that pre-date your work, but do report them clearly.

## Failure pattern reference

### Backend
- **`Dashboard goldens are stale`** — emitted by the autouse session fixture. Run `python scripts/run_all_tests.py` (or just `python -m app.scripts.export_dashboard_goldens` from `services/quant-engine/`) and commit the diff. Do NOT bypass by deleting the fixture.
- **Market data unavailability** in `test_analytics.py`, `test_dashboard_history.py` — usually pre-existing, FMP cache empty in test env. Check `data/fmp-cache/` is populated.
- **Persisted artifact integrity errors** — usually old artifact files from prior runs in `data/artifacts/` that don't match current schema. Check artifact_id prefix and fingerprint scheme.
- **Trust-level mismatches** — `'unavailable'` vs `'degraded_unverified_return_basis'` vs `'verified'`. Check whether the test's expected value is the post-change canonical value.

### Frontend
- **Regex `+` issue** — `new RegExp('Foo + Bar')` doesn't match literal `+` (regex quantifier). Use plain string in `getByText` or escape.
- **Async state not flushed** — wrap state-changing fireEvent in `act()` or use `await waitFor(() => ...)`.
- **Missing node_modules** — `cd apps/desktop && npm install` before vitest.
- **Vite config resolution** — vite must be installed in `apps/desktop/node_modules/`, not the workspace root.

## Reporting

After a triage pass, report in this shape:

```
Suite status: X passed, Y failed, Z skipped

Failures by root cause:
1. [Root cause] → [files affected]
   Fix: [what was changed]

2. [Pre-existing] → [files affected]
   Status: not introduced by this branch (verified via git stash)

Tests not yet fixed: [list with reason — needs orchestrator decision]
```

## Adding new tests

For new features, mirror the existing test organization:
- Backend services → `app/tests/test_<service_name>.py`
- New API routes → integration tests using `TestClient(app)`
- Frontend components → colocated `.test.tsx` next to component
- Frontend hooks → `<name>.test.ts` testing return shape and effects

Always include at least one test for: happy path, validation rejection, integrity/error path.

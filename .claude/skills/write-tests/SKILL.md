---
name: write-tests
description: Use when adding test coverage for new code, fixing flaky tests, or backfilling tests for an existing feature. Triggers when the user says "write tests for X", "add coverage for Y", "fix the failing test in Z", or when build-story auto-delegates the test slice of a ticket. Knows the project's pytest + vitest patterns, golden-freshness gotchas, mocking conventions, and trust-state regression discipline.
---

# Write Tests

This skill writes tests that **survive** the project's actual test infrastructure
— autouse fixtures, golden freshness checks, schema-strict route validation,
Recharts setup, mocked market data, dashboardGoldens artifact handling.

Use it directly ("write tests for `correlation_engine.py`") or let `build-story`
delegate to it for each ticket's test slice.

## Where things live

| Path | Purpose |
|---|---|
| `services/quant-engine/app/tests/` | All backend pytest |
| `services/quant-engine/app/tests/conftest.py` | Autouse fixtures: dashboard-goldens check + market-data mocks |
| `services/quant-engine/app/tests/_statement_fixtures.py` | Reusable import-statement fixtures |
| `apps/desktop/src/features/**/*.test.tsx` | Frontend vitest specs (colocated with components) |
| `apps/desktop/src/test/setup.tsx` | Vitest setup: Recharts `ResponsiveContainer` shim |
| `apps/desktop/src/test/dashboardGoldens.ts` | Generated dashboard goldens (DO NOT edit by hand) |
| `scripts/run_all_tests.py` | Canonical test entrypoint |

## How to run tests during development

Three modes, pick the right one:

```bash
# Narrow iteration — fastest, skip golden freshness check
SKIP_GOLDEN_FRESHNESS_CHECK=1 python -m pytest app/tests/test_my_new.py -v

# Backend only, with goldens regenerated
cd services/quant-engine && python -m pytest

# Full suite (always before commit)
python scripts/run_all_tests.py
```

Frontend:
```bash
cd apps/desktop && npx vitest run                           # all
cd apps/desktop && npx vitest run src/features/portfolio/MyComponent.test.tsx  # one
cd apps/desktop && npx tsc --noEmit                          # type-check
```

**After `run_all_tests.py` succeeds:** `git diff apps/desktop/src/test/dashboardGoldens.ts`.
If modified and your story didn't change dashboard output:
`git checkout -- apps/desktop/src/test/dashboardGoldens.ts` before commit.
This is an FMP-cache artifact, not a real change.

## Backend pytest patterns

### No live network in tests (US-21.1 — enforced)

The default backend run **blocks real network connections** via `pytest-socket`
(`pytest.ini`: `--disable-socket --allow-hosts=127.0.0.1,::1`). A test that
forgets to mock market data fails loudly with `SocketConnectBlockedError`
instead of silently passing online and failing offline.

- **Engine tests:** `conftest.py` autouse-mocks `MarketDataService` for the
  exposure / dashboard-history / diagnostics / stress / drawdown / distribution
  engines with deterministic synthetic rows (`_mock_price_rows`,
  `_mock_prices_for_symbols`). A test-local `mocker.patch` of an engine's
  `MarketDataService` takes precedence.
- **Client tests:** mock the provider library itself (`yfinance.Ticker`,
  `httpx` via `FmpClient` patch) — never the network.
- **Genuinely-live tests** (rare): mark `@pytest.mark.live_data` (plus
  `@pytest.mark.enable_socket`). They are **deselected** by default
  (`-m "not live_data"` in addopts) and run explicitly via `pytest -m live_data`.
- Loopback and file I/O are unaffected (in-process `TestClient`, `tmp_path`,
  `JsonFileCache` all work under the guard).

### Before adding tests to an existing file: inventory the helpers

When extending an existing test file (vs creating a new one), grep for
existing fixtures and helpers first:

```bash
grep -n "^def \|^class \|^@pytest.fixture" path/to/test_foo.py
```

Common helpers to reuse: `_minimal_snapshot()`, `_make_daily_states()`,
`_make_factor_rows()`, `client` fixture. The story's test plan usually names
the ones to reuse; check anyway. **Don't invent a helper that "feels
obvious"** — either reuse an existing one or add the new helper explicitly
in your diff at module scope (not inside a class).

### Test file structure

One test file per service/analytics module. Suffix `_engine.py` modules with
`test_<name>_engine.py`. Group tests in classes by behaviour
(e.g. `TestPearson`, `TestRoute`, `TestUnavailableState`).

```python
"""Tests for the <feature> engine.

Coverage:
  - <pure analytics function>: edge cases
  - <route>: schema, error states, unavailable state
  - <trust-state contract>: synthetic vs unavailable distinction
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.api.main import app
from app.analytics.<module> import <function>

@pytest.fixture
def client():
    return TestClient(app)
```

### Pure analytics tests (no FMP)

For scalar / pure functions in `app/analytics/`, no fixture needed. Cover:

1. **Happy path** — typical inputs, asserted value within tolerance (`1e-9` for ρ/β)
2. **Edge: empty input** — returns `None`, not raises
3. **Edge: single point** — returns `None` if statistic needs ≥ 2
4. **Edge: zero variance** — returns `None` (never 0, never raises)
5. **Edge: all-None input** — returns `None`
6. **Edge: mixed None entries** — drops Nones, computes on rest, matches dense result
7. **Edge: minimum-observations boundary** — returns `None` below, non-`None` at threshold
8. **Range invariant** — result always in spec range (e.g. ρ ∈ [-1, 1]) on random input

Look at `app/tests/test_correlation_engine.py::TestPearson` for the template.

### Route tests

POST a payload via `TestClient`. Two common pitfalls:

**1. `ImportedPortfolioSnapshot` shape — use a `_minimal_snapshot()` helper.**
The schema requires the full shape — minimal-looking payloads return 422.
Copy this template and adjust the position fields if your test needs more positions:

```python
def _minimal_snapshot(with_positions: bool = True) -> dict:
    """Minimal ImportedPortfolioSnapshot-shaped dict for route tests."""
    positions = [
        {
            "as_of_date": "2024-12-31",
            "symbol": "AAPL",
            "quantity": 10.0,
            "cost_basis": 1500.0,
            "close_price": 190.0,
            "market_value": 1900.0,
            "unrealized_pnl": 400.0,
            "currency": "USD",
        }
    ] if with_positions else []
    return {
        "statement": {
            "importer": "interactive_brokers",
            "imported_at": "2024-12-31T00:00:00",
            "source_path": "/test/fixture.csv",
            "detected_format": "ib_flex_2023",
        },
        "instruments": [],
        "positions": positions,
        "cash_balances": [],
        "ledger_entries": [],
    }
```

**2. Market data is auto-mocked for `exposure_engine`, `dashboard_history_engine`,
and `diagnostics_engine`** (see `conftest.py` autouse fixtures).
Routes calling these engines get deterministic sin-wave price series via
`_mock_price_rows`, keyed by sha256 seed per symbol.

**For a NEW engine that calls `MarketDataService`:** add an autouse fixture to
`conftest.py` mirroring the existing pattern, OR add explicit `mocker.patch` per
test that exercises the happy path. **Without one, your "happy path" test will
silently hit the empty/unavailable branch instead of the real computation** —
because no MarketDataService mock exists for your engine and the cache miss
falls through to an empty result. Verify by asserting on actual values, not
just `status_code == 200`.

Coverage to include for every route:

1. **Schema-strict 422** — empty or malformed payload returns 422 (FastAPI does this
   automatically — just confirm shape)
2. **Unavailable state** — payload with empty positions returns the documented
   "unavailable" envelope (status field, null metrics, empty arrays)
3. **Shape contract** — required top-level fields present
4. **Field enum** — `trust` / `status` fields take only documented values
5. **Echo fields** — request params (e.g. `lookback_days`, `window`) echoed in response

### Trust-state regression tests

If the feature has a trust field (`synthetic` / `unavailable` / `verified` /
`degraded`), write tests that pin both states:

```python
def test_trust_synthetic_when_data_available(...): ...
def test_trust_unavailable_when_insufficient_history(...): ...
```

**Never write a test that accepts `0.0` or `""` as a substitute for `None`.**
That regresses the trust-vs-fabrication guardrail.

## Frontend vitest patterns

### Before adding tests to an existing file: inventory the helpers

When extending an existing test file (vs creating a new one), **grep the
file first** for existing factories / fixtures:

```bash
grep -n "^function\|^const.*=\|^type" path/to/Component.test.tsx
```

Common helpers to look for: `makeFullResult`, `makeFooRow`, `MINIMAL_SNAPSHOT`,
`makePoint`. The story's test plan often names the ones to reuse; even if it
doesn't, **never invent a helper that "feels obvious"** — write tests in
terms of what the file already exports, or add the helper explicitly in your
diff. A test that references an undefined `makeSyntheticRow` will fail at
import time with a confusing `ReferenceError`, not a useful assertion error.

### Test file structure

Colocated with the component: `<Component>.tsx` + `<Component>.test.tsx`.

```tsx
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { MyComponent } from './MyComponent'

afterEach(() => { cleanup() })

describe('MyComponent', () => {
  it('renders <thing> when <condition>', () => { ... })
})
```

`afterEach(cleanup)` is mandatory — without it, rendered components leak between
tests and `screen.getByText(...)` returns ambiguous matches.

### Mocking the adapter (for self-fetching components)

Components that call adapters from `portfolioAnalysisAdapter.ts` (the standard
pattern — see `FactorAttributionCard`, `BenchmarkCorrelationTable`) must mock
the adapter module:

```tsx
vi.mock('./portfolioAnalysisAdapter', () => ({
  runMyFooEngine: vi.fn(),
}))

import { runMyFooEngine } from './portfolioAnalysisAdapter'
const mockRun = vi.mocked(runMyFooEngine)

beforeEach(() => { mockRun.mockReset() })
```

For async-rendered content (after `useEffect` fetch resolves), use `waitFor`:

```tsx
mockRun.mockResolvedValue(makeFullResult())
render(<MyComponent snapshot={MINIMAL_SNAPSHOT} />)
await waitFor(() => {
  expect(screen.getByText('S&P 500')).toBeTruthy()
})
```

### Recharts

Charts work in tests because `src/test/setup.tsx` shims `ResponsiveContainer`
to a fixed 960×320 box. You don't need to mock it. Assert on textual content
(labels, axis ticks rendered as text, tooltip text), not on SVG paths.

For chart components, useful smoke checks:

1. Selector buttons render (`getByRole('button', { name: /20d window/i })`)
2. Empty-state message renders when data is empty or all-null
3. Selector change → state change → empty-state appears/disappears

### Snapshot fixtures (frontend)

Use this `ImportedSnapshot` shape — matches the TS type derived from the
backend Pydantic schema:

```tsx
const MINIMAL_SNAPSHOT: ImportedSnapshot = {
  statement: {
    importer: 'interactive_brokers',
    account_id: null,
    base_currency: 'USD',
    statement_period: '2025-01-01 - 2025-12-31',
    page_count: null,
  },
  statements: [],
  positions: [],
  instruments: [],
  cash_balances: [],
  ledger_entries: [],
}
```

For `RollingRiskPoint`, `DriftDailyPoint`, etc., write a tiny factory like
`makePoint(date, overrides)` (see `RollingCorrelationChart.test.tsx`) rather
than inline objects — much easier to read 20 lines later.

### Null and empty-state coverage

The product's UI contract says null → `"—"`, never 0 or empty. For every
component that renders metric values, write at least one test:

```tsx
it('shows dashes for null values', async () => {
  mockRun.mockResolvedValue(makeAllUnavailableResult())
  render(<MyTable snapshot={MINIMAL_SNAPSHOT} />)
  await waitFor(() => {
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })
})
```

## Test plan calibration

If `build-story` invoked you with a ticket whose test plan says "N tests for X",
write **exactly N tests** — not 1, not 10. If you genuinely need more coverage,
update the story's test plan first, don't silently inflate.

Test names must match assertions. `test_returns_correct_value` is useless;
`test_pearson_returns_one_for_identical_series` describes the contract.

## Common failure modes (debug these first)

| Symptom | Likely cause | Fix |
|---|---|---|
| `422 Unprocessable Entity` from route test | `ImportedPortfolioSnapshot` shape wrong | Use `_minimal_snapshot()` helper |
| `pytest` fails with "Dashboard goldens are stale" | Backend output drifted from committed goldens | `python scripts/run_all_tests.py` regenerates; or `SKIP_GOLDEN_FRESHNESS_CHECK=1` for narrow runs |
| `dashboardGoldens.ts` modified after every test run | FMP cache differs between machines | `git checkout -- apps/desktop/src/test/dashboardGoldens.ts` |
| Vitest `screen.getByText` matches multiple elements | Missing `afterEach(cleanup)` — components leak | Add `afterEach(() => { cleanup() })` at top of file |
| Component test passes but real UI broken | Mocked adapter never failed, real adapter has type mismatch | Run `npx tsc --noEmit` |
| Backend route test passes but "happy path" never runs | No MarketDataService mock for your engine | Add autouse fixture to `conftest.py` or `mocker.patch` in the test |

## Definition of Done

- [ ] Every test in the story's test plan exists, with the **exact count** specified
- [ ] Tests cover happy path, empty input, null/unavailable, edge boundary, range invariant
- [ ] Trust-state tests pin both `synthetic` and `unavailable` paths where applicable
- [ ] Null-display tests confirm `"—"` (not `"0"`, not `""`)
- [ ] Route tests use `_minimal_snapshot()` helper, not inline payload
- [ ] Self-fetching components mock the adapter via `vi.mock`
- [ ] If a new engine calls MarketDataService, an autouse fixture or per-test patch is in place
- [ ] `npx tsc --noEmit` clean
- [ ] `python scripts/run_all_tests.py` green
- [ ] `dashboardGoldens.ts` reverted if your changes didn't touch dashboard output

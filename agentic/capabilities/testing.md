# Capability pack: testing — project `portfolio`

Everything the `test-engineer` lane needs about how testing actually behaves in
this repo. This is a record of hard-won friction, not a tutorial. Where it
contradicts your general pytest/vitest instincts, this file wins.

Companion sources: `portfolio/.claude/skills/write-tests/SKILL.md` (fuller
prose, read it when this pack is thin on your case) and
`docs/architecture/testing-architecture.md`.

---

## Index

Read this block first. You are not expected to read this file end to end — read
what your order touches. Reading one extra section is cheap; acting on a
convention you never read is not.

**Always read:** **Running tests** · **Project tool server — prefer it over the raw command** · **Gotchas that will bite you** · **Shared fixtures — mandatory, do not re-implement** · **Definition of done for this lane**

| Section | Read it when |
|---|---|
| Where things live | you are adding a test file |
| Assertion conventions (backend + frontend) | you are writing assertions |
| Trust-state discipline in tests | your test touches trust or availability state |
| Technique skills (mattpocock-skills) | you are making the `tdd` call Definition of done requires, or a failing or flaky test resists your first diagnosis |

---

## Where things live

| Path | Purpose |
|---|---|
| `services/quant-engine/app/tests/` | all backend pytest |
| `services/quant-engine/app/tests/conftest.py` | autouse fixtures: golden-freshness check + market-data mocks |
| `services/quant-engine/app/tests/fixtures.py` | **the** shared scaffolding module — reuse, never re-implement |
| `services/quant-engine/app/tests/_statement_fixtures.py` | reusable import-statement fixtures |
| `services/quant-engine/app/tests/statement_truths.py` | statement-truth pins live here, in ONE module |
| `apps/desktop/src/**/*.test.tsx` | vitest specs, colocated with components |
| `apps/desktop/src/test/setup.tsx` | vitest setup — Recharts `ResponsiveContainer` shim |
| `apps/desktop/src/test/dashboardGoldens.ts` | **generated** — never hand-edit |
| `apps/desktop/src/test/designSystem.audit.test.ts` | design-system audit; fails the build on violations |
| `scripts/run_all_tests.py` | canonical entrypoint; a green run writes `.claude/.last-test-pass` |

## Running tests

```bash
# Narrow iteration — fastest, skips the golden freshness check
SKIP_GOLDEN_FRESHNESS_CHECK=1 python -m pytest app/tests/test_<module>.py -v

# Backend, goldens regenerated
cd services/quant-engine && python -m pytest

# Frontend
cd apps/desktop && npx vitest run
cd apps/desktop && npx vitest run src/features/portfolio/MyComponent.test.tsx
cd apps/desktop && npx tsc --noEmit

# Full suite — the gate
python scripts/run_all_tests.py
```

Use narrow mode while working; run what the work order's `verification` field
names before reporting `PASS`.

## Project tool server — prefer it over the raw command

The `mcp__project__*` tools wrap the commands above and return **parsed** results
instead of raw output: a failing suite comes back as a list of
`{file, test, message}` plus a short tail, not four hundred lines you pay to read.

- `run_tests(scope, path=None, k=None)` — scope is `backend` | `frontend` |
  `typecheck` | `full`. `backend` sets `SKIP_GOLDEN_FRESHNESS_CHECK=1` for you;
  `full` deliberately does not, because that is the gate. A subprocess that
  exceeds its per-scope budget (`TIMEOUTS` dict local to `tools/testing.py`:
  full 1800 / backend 600 / frontend 600 / typecheck 300 / gate 300 / git 30 s)
  comes back as a structured timeout result (`timed_out: True`, `scope`,
  `command`, `timeout_seconds`) rather than raising; a normal result now carries
  `timed_out: False`.
- `check_gates()` — dead-code, `tsc`, goldens drift and commit-gate freshness in
  one call. Ask it *before* you try to commit, not after the hook blocks you.
  Each gate runs in its own isolated subprocess, so a per-gate timeout is
  reported while the gates that completed still return real results; the result
  dict carries a top-level `timeouts` key naming whichever gates timed out.
- `reset_goldens()` — the `git checkout --` on `dashboardGoldens.ts` described
  under **Gotchas**. It first captures `git diff --stat` and a bounded `git
  diff` of the file *before* the checkout and returns both (`diff_stat` /
  `diff`, plus `diff_truncated` / `discarded`); the capture survives a failed
  checkout, and a no-drift reset reports nothing discarded.
- `probe_engine` / `build_snapshot` — see **Shared fixtures**.

The raw commands above are still correct and still work. Reach for them when you
need a flag the tool does not expose, and when the tool server is not running.
Nothing here is only doable through a tool.

## Gotchas that will bite you

**Goldens drift is usually noise.** After `run_all_tests.py` succeeds, check
`git diff apps/desktop/src/test/dashboardGoldens.ts`. If it is modified and your
work did not change dashboard output, `git checkout --` it before reporting.
That diff is an FMP-cache artifact, not a real change. Never hand-edit the file.

**No live network, enforced.** `pytest.ini` sets `--disable-socket
--allow-hosts=127.0.0.1,::1`. A test that forgets to mock market data fails
loudly with `SocketConnectBlockedError` rather than passing online and failing
offline.

- *Engine tests*: `conftest.py` autouse-mocks `MarketDataService` for exposure,
  dashboard-history, diagnostics, stress, drawdown and distribution with
  deterministic synthetic rows. A test-local `mocker.patch` takes precedence.
- *Client tests*: mock the provider library itself (`yfinance.Ticker`, `httpx`
  via an `FmpClient` patch) — never the network layer.
- *Genuinely live* (rare): `@pytest.mark.live_data` + `@pytest.mark.enable_socket`.
  Deselected by default (`-m "not live_data"`); run explicitly with
  `pytest -m live_data`.
- Loopback and file I/O are unaffected — in-process `TestClient`, `tmp_path` and
  `JsonFileCache` all work under the guard.

**Patch the engine module, not the service module.** `install_market_data_mock`
targets `{engine_module}.MarketDataService`, because engines import the class at
module load. Patching `app.services.market_data` will silently do nothing.

**New engine routes must join the response-integrity property test.** Add them
to `test_engine_response_integrity.py`; its route-table coverage check fails the
suite if you forget.

**Frontend charts need the shim.** `src/test/setup.tsx` shims Recharts'
`ResponsiveContainer`; a chart test that bypasses setup renders zero-size and
asserts nothing.

**Asserting exact chart-line values against an unexported transform.** When the
data-transform feeding a chart (e.g. `buildIndexedSeries`) is unexported and its
source file is out of scope to edit — the common case for a regression-guard
test written against someone else's fix — do not parse SVG path geometry. Add a
local `vi.mock('recharts', ...)` (setup.tsx's global shim does not carry into a
file's own mock) that keeps `ResponsiveContainer` sizing but replaces `LineChart`
with a stub rendering its `data` prop into a `data-testid` div; read it back via
an async `getChartData()` helper (`await screen.findByTestId(...)`, `JSON.parse`
the text). Reference:
`apps/desktop/src/features/portfolio/PerformanceBenchmarkCard.test.tsx`.

## Shared fixtures — mandatory, do not re-implement

From `app/tests/fixtures.py`:

- `imported_snapshot(positions=…, instruments=…, cash_balances=…)` — the full,
  422-proof `ImportedPortfolioSnapshot` payload, validated against the real
  schema by `test_fixtures.py`
- `position(symbol, market_value, **overrides)` — `ImportedPosition`-shaped dict
- `price_rows(…)` / `price_rows_from_returns(…)` — deterministic series builders
- `install_market_data_mock(mocker, target_module, *, histories, default_rows,
  vendor_by_symbol)`

Need scaffolding that does not exist? Extend this module rather than inlining a
local helper, and name the addition in your report's `handoff`.

Two of these are also exposed as tools, which is the cheaper way in:

- `build_snapshot(positions=[{"symbol": "AAPL", "market_value": 500}], …)` wraps
  `imported_snapshot`, accepting position shorthand and filling the rest.
- `probe_engine(route, payload, histories=…)` runs one engine route in-process
  with `MarketDataService` mocked and hands back the JSON — use it to find out
  what a route actually returns instead of writing a throwaway script. It
  derives the module to patch from the route, so the "patch the engine module,
  not the service module" gotcha above cannot bite you through this path.
  It classifies the route's expected request-body shape (`flat` /
  `snapshot-wrapped` / `bare-snapshot` / `unclassified`) via live FastAPI route
  introspection, reports `request_shape` + `request_model`, and emits a
  warn-only `shape_mismatch` when the supplied payload has or omits a top-level
  `snapshot` key against what the route expects. It still **never returns 422 and
  never raises on a mismatch** — it POSTs and returns the real response, which
  for a genuinely mismatched payload is a 200 with `trust: "unavailable"`. The
  backend pack carries the route-to-shape table.

**One caveat that does not apply to pytest.** `probe_engine` runs outside a
pytest session, so `pytest.ini`'s `--disable-socket` guard is not protecting it
and `conftest.py`'s autouse mocks do not apply. Its own mock is what keeps it
offline, and anything the route needs must be passed in explicitly.

## Assertion conventions (backend + frontend)

These came out of real breakages where an *additive* change broke tests that
never meant to forbid it.

**1. Containment for extensible structures; `==` only for closed contracts.**

Anything designed to gain fields over time — `last_fetch_meta`, admission check
sets, provenance metadata, run-metadata dicts — gets a superset assertion. An
`==` on its key set silently claims "these and only these keys, forever", which
is far stronger than the test intends, so every future field reads as a
regression.

```python
# Brittle — broke 5 tests when `vendor` was added, 2 more when a check was added
assert service.get_last_fetch_meta("VUAA") == {"type": "history", "resolved_symbol": "SPY", "cached": True}

# Robust — pins what the test cares about, tolerates additive fields
assert {"type": "history", "resolved_symbol": "SPY", "cached": True}.items() <= service.get_last_fetch_meta("VUAA").items()
```

Exact `==` is right when the set genuinely is closed: requested percentile keys,
an error-response body, a frozen fixture.

**2. Never assert an implicit default the test did not set.**

Changing the chart default window (60d → 20d) broke ten frontend tests that were
testing something else entirely. So: pin a default in exactly one dedicated test
that means to (`it('defaults to window_trading_days=252')`). Every other test
either sets the value explicitly first, or captures it dynamically and asserts
the *delta*.

## Trust-state discipline in tests

The product's core promise is that missing data is surfaced, never fabricated.
That makes trust states a first-class test target, not an edge case:

- Assert `withheld` and `unavailable` **separately**. Collapsing them is the
  exact bug the ladder exists to prevent, and a test that treats them as
  interchangeable will not catch it.
- Assert `degraded` renders its badge rather than silently looking verified.
- For any new field that can be missing, cover: present, missing, and degraded.
- Frontend: assert the unavailable state renders as unavailable — never as zero,
  never as a placeholder.

## Technique skills (mattpocock-skills)

Portfolio's `.claude/settings.json` enables this plugin (`project.md` §
Technique skills). Constraints for the `mattpocock-skills:tdd` call
Definition of done requires:

- You still never touch production code to turn a test green (Scope
  discipline in your role file).
- The seams for a new test are the ones your order's `inputs` name. Don't
  pause to ask which seam; that was decided upstream.
- A mock § Gotchas prescribes does not fire the trigger: market data via
  `install_market_data_mock`, providers at the library.
- A local `vi.mock('recharts')` is exempt only to read an unexported chart
  transform's data back (§ Gotchas). Any other `vi.mock` fires the trigger.
- Any other mock-or-real decision fires it. Examples: patching an engine
  function in a route test, or stubbing a service instead of `TestClient`.
- Its "test behaviour, not implementation" advice is this repo's
  containment / no-implicit-default rules. Where they differ, § Assertion
  conventions wins.
- Red-first is usually unavailable: `build` runs implementation before
  tests, so the behaviour already exists when you write the test.
- Apply its tautology rule instead. Expected values come from the
  methodology doc, a worked example or a statement-truth pin — never
  recomputed the way the engine does.
- Red-first does apply to a regression test for a bug not yet fixed. Prove
  red once on the narrow command (`run_tests(scope="backend", k=...)` or one
  vitest file).

A failing or flaky test resists your first diagnosis: call the Skill tool
with `mattpocock-skills:diagnosing-bugs`. Adapted to this lane:

- Your feedback loop is the narrow command above, or `probe_engine` to see
  what a route actually returns.
- Check the known false signals first: goldens drift, a missing
  `setup.tsx` shim, a patch on the service module, `SocketConnectBlockedError`.
- If the defect is in the test itself, fix it — that's your job.
- If the defect is in production code, stop at diagnosis: report it as a
  finding per Scope discipline, and do not patch it.
- The skill's "ask the user" moments become a `risks` entry instead.
- Name any scratch file in `handoff` with its `git rm <path>` command — you
  have no delete tool.
- No commit. Your report is the protocol's report block, not a commit message.
- Record each call in `skill_calls:` (`PROTOCOL.md` § 7).

## Definition of done for this lane

- Tests exist for every behaviour the work order names, including the missing
  and degraded paths.
- Shared fixtures reused; any new scaffolding added to `fixtures.py` and
  reported in `handoff`.
- If you chose between a mock and a real dependency, or accepted
  test/production coupling, you called `mattpocock-skills:tdd` first.
- That call is recorded in `skill_calls:`, not only noted in `risks`.
- New engine routes registered in the response-integrity test.
- Assertions follow the containment / no-implicit-default rules.
- The order's `verification` command was actually run and passed.
- `dashboardGoldens.ts` is either unchanged or intentionally regenerated.
- No production code was modified. Defects found are reported, not patched.

# Capability pack: backend — project `portfolio`

For the `backend-engineer` lane. Everything about `services/quant-engine/`.
Where this contradicts general FastAPI/Pydantic instincts, this file wins.

Companion sources: `portfolio/CLAUDE.md`,
`docs/architecture/system-architecture.md`, `docs/finance/financial-methodology.md`,
`docs/contracts/<area>-fields.md`.

---

## Index

Read this block first. You are not expected to read this file end to end — read
what your order touches. Reading one extra section is cheap; acting on a
convention you never read is not.

**Always read:** **Guardrails, in code terms** · **Gotchas that will bite you** · **Reuse — do not re-derive these** · **Project tool server — prefer it over the raw command** · **Definition of done for this lane**

| Section | Read it when |
|---|---|
| Layout | you are adding a file, or looking for where one lives |
| The four-file rhythm | your order adds or changes an endpoint |
| Dead-code gate | your verification command includes the dead-code gate |
| Contract notes you must emit | your order changes a schema or a response shape |
| Changing a published contract | the shape you are changing has already shipped |
| Diagnosing a stuck bug | your first fix attempt didn't hold |

---

## Layout

```
services/quant-engine/app/
  schemas/      Pydantic models — CONTRACT SOURCE OF TRUTH
  api/routes/   thin FastAPI routers, one file per engine
  api/main.py   router registration
  services/     *_engine.py — the business logic
  analytics/    pure computation: returns, drawdown, distribution, risk,
                attribution, correlation, currency, performance, reconciliation
  clients/      FMP client (with caching) — the only place market data enters
  core/         settings, logging, caching infrastructure
  domain/       ledger + accounting model
  importers/    broker parsers (Interactive Brokers, Freedom24, ESPP)
  instruments/  instrument registry
  tests/        pytest — NOT your lane
```

Existing engine areas, for finding prior art: `attribution`, `correlation`,
`intra_correlation`, `currency_risk`, `dashboard_history`, `diagnostics`,
`distribution`, `drawdown`, `drift`, `exposure`, `imports`, `provenance`,
`stress`, `cache`, `market_data`, `health`.

## The four-file rhythm

Every engine feature is the same four files in the same order. Deviating from
the order is how contracts drift.

**1. `schemas/<area>.py` — first, always.**

```python
"""<Area> engine schemas (Epic N — <tab>).

<What this surfaces and under which truth class.>
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel

from app.schemas.portfolio_engine import PortfolioEngineRequest

FooTrustLevel = Literal["synthetic", "unavailable"]
FooWindow = Literal[252, 756, 1260]

class FooEngineRequest(PortfolioEngineRequest): ...
class FooEngineResponse(BaseModel): ...
```

Conventions visible throughout the existing schemas, and expected of new ones:

- Module docstring names the epic and the **truth class** the outputs belong to.
- Requests extend `PortfolioEngineRequest`. Do not re-declare snapshot fields.
- `Literal` type aliases for every enum-like value — trust levels, windows.
- Class docstrings carry the **methodology reference and the formula**, e.g.
  "`contribution_pct = weight_at_peak × return × 100`", plus units and sign
  conventions. This is not decoration: it is how methodology traceability is
  maintained at the point of definition.
- Units are in the field name (`_pct`, `_pp`, `_usd`), not left to the reader.
- Trust granularity can differ by level. `drawdown.py` carries both a
  wrapper-level `DrawdownTrustLevel` and a per-episode
  `DrawdownDecompositionTrust` with an extra `partial` member, because a
  decomposition can be partial while the overall response is still synthetic.
  Model the levels that actually exist; do not flatten them.

**2. `services/<area>_engine.py`** — a `run_<area>_engine(request) -> Response`
entrypoint. Business logic here; pure computation delegates to `analytics/`.

**3. `api/routes/<area>.py`** — thin. This is the whole shape:

```python
router = APIRouter(prefix="/engines/<area>", tags=["<area>-engine"])

@router.post("/run", response_model=FooEngineResponse)
def run_foo(request: FooEngineRequest) -> FooEngineResponse:
    try:
        return run_foo_engine(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

No logic in the route. `detail=str(exc)` matters — the frontend adapter surfaces
it as the user-visible error message.

**4. `api/main.py`** — import the module and `app.include_router(<area>.router)`.
Forgetting this is the classic silent failure: everything imports, nothing fails
at build time, the route simply is not there.

## Reuse — do not re-derive these

- `_build_synthetic_snapshot_history_states` in `diagnostics_engine.py` — the
  synthetic daily portfolio state pipeline (current holdings × historical
  prices). Any engine needing synthetic history uses this one.
- `_lookback_calendar_days(window) = ceil(window * 1.6) + 30` in
  `attribution_engine.py` — trading-days-to-calendar-days conversion.
- `app/clients/fmp.py` via `MarketDataService` — **never** call FMP from a route
  or an engine directly. Caching lives in the client.
- `history_context_builder.py`, `holdings_history.py`,
  `portfolio_snapshot_builder.py`, `benchmark_service.py` for shared assembly.

A second copy of a formula is a real defect class here — US-34.8 found `risk.py`
holding its own copy of the daily-return formula. If a computation exists,
import it.

## Project tool server — prefer it over the raw command

Before writing a throwaway script to find out what a route returns, call
`probe_engine`. It boots the app in-process, patches the engine module's
`MarketDataService` with deterministic rows, POSTs your payload and returns the
JSON — no network, no scratchpad file, no re-deriving the fixture shape.

```
snap = build_snapshot(positions=[{"symbol": "AAPL", "market_value": 1000}])
# wrapped-shape route:
probe_engine("/engines/correlation/multi", {"snapshot": snap, "lookback_days": 250},
             histories={"AAPL": [...]})
# flat-shape route — same data, no wrapper:
probe_engine("/engines/drawdown/run",
             {"benchmark_symbol": "SPY", "cash_balances": [], **snap},
             histories={"AAPL": [...], "SPY": [...]})
```

**Check the payload shape first — the wrong one returns 200, not 422.** Engine
requests come in three shapes, and every field has a default, so a mismatched
payload is *accepted*: the engine sees zero positions, fail-closes, and hands
back `trust: "unavailable"` with null scalars. That reads as a broken engine.

| payload shape | routes |
| --- | --- |
| flat — snapshot fields at the top level | `exposure` · `diagnostics/run` · `dashboard-history/run` · `drift` · `stress` · `drawdown` · `distribution` |
| wrapped in a `snapshot` key | `currency-risk` · `attribution` · `correlation/multi` · `correlation/intra` · `provenance` |
| a bare snapshot as the whole body | `diagnostics/run-imported` · `dashboard-history/run-imported` |

Flat routes take `{"benchmark_symbol": ..., "positions": [...], "cash_balances": []}`
directly — `build_snapshot`'s output goes at the top level, not under a key.
**Always read `trust` before believing a 200.**

`probe_engine` now helps you catch the mismatch instead of leaving it to you: it
classifies the route's expected shape from live FastAPI route introspection and
reports `request_shape` (`flat` / `snapshot-wrapped` / `bare-snapshot` /
`unclassified`) plus `request_model`, and emits a **warn-only** `shape_mismatch`
when your payload carries or omits a top-level `snapshot` key against what the
route expects. It never raises on a mismatch and never returns 422 — it still
POSTs and hands back the real response — so the mismatch shows up as a populated
`shape_mismatch` next to the `trust: "unavailable"` body it explains.

**Long arrays in the response are bounded.** `probe_engine` bounds any array
longer than 11 elements to its first `PROBE_ARRAY_HEAD` and last
`PROBE_ARRAY_TAIL` elements (both = 5), replacing the elided middle with a single
`{"__probe_truncated__": {original_count, dropped, kept_head, kept_tail, note}}`
sentinel; the route itself still returned every element. The envelope's
`truncation` key lists the dotted path of every array bounded this way. A
`fields=` arg filters the body to named top-level keys (every `trust` / `*_trust`
key is retained regardless) and is applied *before* the array bounding. Even so,
probe with the shortest history that still exercises what you are checking — a
drawdown probe over 750 days is still large — and do not re-probe to re-read a
value you already have.

The module to patch is derived from the route (`/engines/<name>/run` →
`app.services.<name>_engine`), so the "patch the engine module, not the service
module" trap cannot bite you through this path. Pass `engine_module=` to override.

Also available: `run_tests(scope, path, k)` for your `verification` command,
returning parsed failures rather than the full dump; `check_gates()` to see
whether the dead-code gate and `tsc` will pass before you commit; and
`reset_goldens()`. All three bound a hung child process: `run_tests` and
`check_gates` return a **structured timeout result** (naming the scope, command
and limit — they do not raise) when a subprocess exceeds its per-scope budget,
held in a `TIMEOUTS` dict local to `tools/testing.py` (full 1800 / backend 600 /
frontend 600 / typecheck 300 / gate 300 / git 30 s). A normal `run_tests` result
now also carries `timed_out: False`. `check_gates` runs each gate in its own
isolated subprocess, so a per-gate timeout is reported while the gates that
completed still return results, and its result dict carries a top-level
`timeouts` key listing whichever gates timed out. `reset_goldens` captures `git
diff --stat` and a bounded `git diff` of `dashboardGoldens.ts` *before* the `git
checkout --` and returns both (`diff_stat` / `diff`, alongside `diff_truncated`
and `discarded`); the capture survives a failed checkout, and a no-drift reset
reports nothing discarded.

**Nothing here is only doable through a tool.** Every one wraps a command you can
still run under `Bash`, and the pack names those commands too. What the server
buys is a bounded return value and a removed class of error, not a capability.

## Guardrails, in code terms

**Trust semantics.** Any field that can be null because of missing data is
paired with an explicit trust enum — `'synthetic' | 'unavailable'` for
synthetic-history paths, `'verified' | 'degraded' | 'withheld' | 'unavailable'`
for broker-truth paths. Never silently null, never a plausible substitute,
never collapse `withheld` into `unavailable`. The two mean different things:
withheld is "we have it and do not trust it"; unavailable is "we do not have it".

**Truth-class separation.** Broker truth, snapshot analytics, synthetic history
and persisted imports never mix in one response. If a response needs two, they
are two labelled sections, not one blended number.

**Methodology first.** Touching analytics, a factor formula, a weighting or
trust-state logic → read `docs/finance/financial-methodology.md` before writing.
If the formula you need is not documented there, that is a finding to report,
not a gap to fill with your own derivation.

**Fail closed.** Where the code withholds rather than guesses, that behaviour is
load-bearing. Do not weaken an admission gate to make a number appear. Epic 34
is largely a record of what happens when a number is published on a basis it
cannot support — read that PRD before touching a trust classification.

## Gotchas that will bite you

**Windows checkouts: `core.filemode=false` silently strips the executable
bit on `git add`.** A plain `git add` on a newly-created executable script
(e.g. a `.sh`/POSIX hook wrapper under `scripts/`) records it in the git
index as mode `100644` (non-executable) even though the file has `chmod +x`
on disk — verified directly via `git ls-files --stage` (Epic 36 / US-36.1,
`scripts/githooks/pre-commit`). Since `git checkout` applies the **stored**
index mode on every clone regardless of that clone's own `core.filemode`
setting, this silently ships a non-executable script that a Linux git-hook
runner (no `sh`-fallback the way Git for Windows has) skips without error —
the "wiring exists but is inert" failure class, at the file-mode layer. Fix:
stage any new executable file added from a Windows dev box with
`git add --chmod=+x <path>`, not a plain `git add`.

## Dead-code gate

`run_all_tests.py` runs `detect_deadcode.py --strict` (ruff + vulture + knip,
zero findings) plus `tsc --noEmit`. New dead code **fails the suite**.

For a genuine dynamic-use false positive — pytest fixture, Pydantic/FastAPI
hook, signature-match kwarg, persistence sanitizer, CLI entry point — add a
**reasoned** entry to `services/quant-engine/vulture_allowlist.py`. Every entry
must name why. An unexplained allowlist entry is how the gate stops working.

## Contract notes you must emit

The `schema_edit_reminder.py` hook fires on any edit under `app/schemas/`. Any
schema change means your report's `contract_notes` names, explicitly:

- the mirroring TS type in `apps/desktop/src/features/portfolio/types.ts`
- the contract doc `docs/contracts/<area>-fields.md`
- the methodology section, if a formula changed

This is not bookkeeping. The frontend and docs lanes work from your notes, and a
note you skip becomes drift nobody is looking for.

## Changing a published contract

If a change would alter a field already consumed by a route response or a
committed type, **stop and report it** rather than changing it. US-35.2 hit
exactly this: `clear()` kept its `int` return because `CacheClearResult.removed`
on the `/cache` route was typed from it — a published contract that story had
no mandate to change. The breakdown was derived at the CLI instead.

Widening a contract is usually safe; narrowing or re-typing one is a scope
decision that belongs to the tech lead and the producer.

## Diagnosing a stuck bug

Your first fix attempt didn't hold: call the Skill tool with
`mattpocock-skills:diagnosing-bugs` rather than guessing again
(`project.md` § Technique skills). Adapted to this lane's constraints:

- Your feedback loop is `probe_engine` on the failing route, or
  `run_tests(scope="backend", k=...)` on one test. Don't write a throwaway
  script for what `probe_engine` already returns.
- Diagnose the root cause and apply the fix — that part is yours.
- If the root cause is the formula or the methodology, stop at diagnosis.
  Report it for `quant-audit`; never adjust a formula until a number looks
  right (guardrail 1).
- A fix that makes a value appear by weakening an admission gate is not a fix
  (§ Guardrails, in code terms — fail closed).
- Do not write the regression test: name it in `handoff` for the test lane
  instead (you touch no test files, per the definition of done below).
- The skill's "ask the user" moments become a `risks` entry instead.
- Any scratch/repro file it has you create is named in `handoff` with its
  `git rm <path>` command — you have no delete tool.
- Remove every `[DEBUG-…]` probe before you report. The dead-code gate will
  not catch a print.
- No commit. Your report is the protocol's report block, not a commit message.
- Record the call in `skill_calls:` (`PROTOCOL.md` § 7).

## Definition of done for this lane

- [ ] Schema changed first; docstring carries methodology reference, units, sign convention
- [ ] Trust enum present on every nullable field
- [ ] Engine logic in `services/`, pure computation in `analytics/`, route thin
- [ ] Router registered in `api/main.py`
- [ ] No re-derived formula, lookback, or synthetic-history builder
- [ ] `python scripts/detect_deadcode.py --strict` clean, or a reasoned allowlist entry
- [ ] `contract_notes` names every downstream artifact that now lags
- [ ] No test files touched — that is the test lane

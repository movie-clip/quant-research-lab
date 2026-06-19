---
name: build-story
description: Use when implementing a ticketed user story from docs/product/stories/. Triggers when the user says "build US-X.Y", "pick up ticket T-...", "implement the next story", or points at a story file. Reads PRD + methodology context, works tickets in order, delegates test-writing to the write-tests skill, verifies via the verify-story skill, and closes out via the update-docs skill before committing.
---

# Build Story

This project is developed as **PRD → User Story → Ticket**. A user story is a
vertical slice that delivers user-visible value; it is never an isolated
technical feature. This skill is the **implementation** half of the cycle —
it takes a story file that already has acceptance criteria, a test plan, and
ticketed scope, and lands the code.

**This skill does not author stories.** If the story has no tickets, stop and
run the `write-story` skill first — do not infer tickets yourself.

## The cycle this skill plugs into

```
quant-research → write-story → build-story → write-tests → verify-story → update-docs
   (research)      (plan)       (this skill)    ↑              ↑              ↑
                                                 │              │              │
                                          auto-delegated    blocks commit   auto on close-out
```

- `write-tests` is invoked automatically during ticket delivery for the test slice.
- `ui-polish` is invoked automatically for the UI slice of a frontend ticket — provides the design tokens, primitives (CardShell / TrustBadge / WindowSelector / ChartShell / state primitives), and accessibility baseline so the result matches the existing Exposure cards without a post-hoc polish pass.
- `verify-story` is invoked automatically before you claim done; if it fails, the commit is blocked.
- `update-docs` is invoked automatically during close-out to reconcile contracts, methodology, slice log.

## Where things live

| Path | Purpose |
|---|---|
| `docs/product/prd/<epic>.md` | PRD per epic — problem, goals, non-goals, success signals |
| `docs/product/stories/US-<n>-<slug>.md` | One story file — statement, ACs, **test plan**, tickets, status |
| `docs/product/stories/README.md` | Story index + lifecycle states |
| `docs/product/epic-roadmap.md` | Epic snapshot + slice log |
| `docs/product/current-product-state.md` | Canonical shipped-state inventory |
| `docs/finance/financial-methodology.md` | Source of truth for every formula |
| `docs/contracts/<area>-fields.md` | Backend ↔ TS type ↔ UI traceability |

## The product (current shipped state)

Three tabs: **Dashboard**, **Exposure**, and **Risk**. (`docs/product/current-product-state.md`
is the canonical inventory — read it if scope is unclear.)

- **Dashboard** — portfolio performance history: TWR + sub-windows, benchmark
  comparison, monthly returns grid, risk metrics, investor economics, factor-model snapshot.
- **Exposure** — current composition: vs-Market drift panel (top, indexed return chart
  + 5-window cards), rolling correlation & beta chart (dual-axis), concentration pack,
  factor attribution card (chart + period table), Factor Drift Summary card (Epic 16),
  multi-benchmark correlation table (SPY/QQQ/GLD/IEF/VT), intra-portfolio correlation
  heatmap (Epic 17).
- **Risk** (Epic 13) — pre-decision risk-budget views: Stress Scenarios card,
  Drawdown Analytics card (underwater curve + top-5 episodes + Epic 15 contributors
  drawer), VaR & Distribution card.

Backend route prefixes: `/engines/exposure`, `/engines/diagnostics`, `/engines/dashboard-history`, `/engines/drift`, `/engines/attribution`, `/engines/correlation`, `/engines/stress`, `/engines/drawdown`, `/engines/distribution`, `/engines/provenance`, `/portfolios/import`, `/market-data`, `/cache`, `/health` (registered in `app/api/main.py`).

If a story implies a feature outside this surface, surface that as a scope concern before implementing.

## Before writing any code

1. **Read the story file end to end.** It owns the acceptance criteria and the
   test plan — those are the contract for "done".
2. **Read the linked PRD section.** Understand the problem and the non-goals so
   you do not over-build.
3. **Read `docs/finance/financial-methodology.md`** if the story touches any
   analytics, factor formula, weighting, replay basis, or trust-state logic.
   That doc is the source of truth for every implemented formula.
4. **Confirm the tickets are present.** A ticketed story carries `T-<epic>.<story>.<n>`
   tickets in order. **If the story has no tickets, stop and tell the user to run
   `write-story` first.** Do not infer tickets on the fly — that bypasses the
   review gate that catches bad acceptance criteria before code is written.
5. If the premise looks wrong (ACs contradict the methodology doc, a ticket is
   infeasible, a methodology formula is missing), **stop and surface it** — do
   not silently reinterpret the story.

## Delivering a ticket

Each ticket is a focused, reviewable change. Work tickets top to bottom.

### Ticket order rules

1. **Schemas first.** If the ticket changes a Pydantic schema in
   `services/quant-engine/app/schemas/`, change the schema before routes,
   services, or UI. Mirror it in the desktop TS types in the same pass.
2. **Backend before frontend.** Engine/service/route, then desktop.
   Desktop stays thin on finance — no portfolio math in components.
3. **Tests in the same pass.** Never land a ticket without the tests its slice
   of the story's test plan calls for. Invoke `write-tests` for this slice; it
   knows the project's pytest/vitest conventions.
4. **Honour the guardrails** (see below).
5. Tick the ticket checkbox in the story file.

### Project-specific implementation patterns

These patterns came out of real friction; follow them by default:

**For any Exposure-tab card work, invoke the `ui-polish` skill.** It owns
the design tokens, primitive components (`CardShell`, `TrustBadge`,
`WindowSelector`, `EmptyState`, `LoadingState`, `ErrorState`, `ChartShell`,
`chartDefaults`), the canonical card pattern, and the accessibility
baseline. Using it is not optional — the design-system audit
(`apps/desktop/src/test/designSystem.audit.test.ts`) will fail the build
if the card hand-rolls a Synthetic badge, inlines a hex value, or skips
the chart defaults. Read `.claude/skills/ui-polish/SKILL.md` (or the
contract doc `docs/contracts/ui-design-system.md`) for the full pattern.

**Self-fetching components for engine calls.** Components that need engine data
(attribution, correlation, multi-benchmark) should call the adapter inside their
own `useEffect`, not be passed pre-fetched data via App.tsx state. See
`FactorAttributionCard` and `BenchmarkCorrelationTable` for the pattern:

- Component takes `snapshot: ImportedSnapshot | null` as prop
- `useEffect([snapshot, window])` triggers the fetch
- States: `'idle' | 'loading' | 'error' | 'done'`
- Cancellation flag (`let cancelled = false`) to avoid stale-result writes

This avoids: (a) wiring overhead in App.tsx, (b) `PortfolioSnapshot` vs
`ImportedSnapshot` type mismatches between App.tsx state and adapter requests.

**Adapter signature shape.** `runFooEngine(snapshot, options?, apiUrlOptions?)`
returning a typed `Promise<FooResponse>`. Use `resolvePortfolioEngineUrl(...)`
for the URL and surface backend `detail` on non-2xx as the error message.

**Engine service synthetic-history pipeline.** When the engine needs synthetic
daily portfolio states (current holdings × historical prices), reuse
`_build_synthetic_snapshot_history_states` from `diagnostics_engine.py` and
`_lookback_calendar_days(window) = ceil(window * 1.6) + 30` from
`attribution_engine.py`. Do not re-derive these.

**Trust enum on engine responses.** Any field that can be null because of
missing data must be paired with an explicit `trust: 'synthetic' | 'unavailable'`
(or `'verified' | 'degraded' | 'withheld' | 'unavailable'` for broker-truth
paths). Never silently null.

## Guardrails (non-negotiable — from CLAUDE.md)

1. **Methodology traceability** — every UI metric maps to one engine formula
   and one code path.
2. **Truth-class separation** — broker truth, snapshot analytics, synthetic
   history, persisted imports are distinct. Never mix them in one response.
3. **Trust semantics over fabrication** — `verified > degraded > withheld >
   unavailable`. Surface the level; never fabricate, never silently fallback,
   never collapse `withheld` into `unavailable`.
4. **No execution** — the product never places trades or moves money.
5. **Fail-closed loading** must not be weakened.

## Running tests (canonical entrypoint)

```bash
python scripts/run_all_tests.py        # canonical: goldens + backend pytest + frontend vitest
cd apps/desktop && npx tsc --noEmit    # type-check (NOT run by run_all_tests.py)
```

### Test gotchas you will hit

- **Stale dashboard goldens.** Bare `pytest` fails fast via an autouse freshness
  fixture. The canonical fix is `python scripts/run_all_tests.py` (which
  regenerates first). For narrow iteration, prefix with
  `SKIP_GOLDEN_FRESHNESS_CHECK=1` — e.g.
  `SKIP_GOLDEN_FRESHNESS_CHECK=1 python -m pytest app/tests/test_my_new.py -v`.
- **`dashboardGoldens.ts` modified after `run_all_tests.py`.** This is an
  FMP-cache artifact (data fetched on this machine differs slightly from
  committed goldens). Unless your story actually changed dashboard output:
  `git checkout -- apps/desktop/src/test/dashboardGoldens.ts` before commit.
- **Route 422 with valid-looking payload.** `ImportedPortfolioSnapshot` requires
  the full shape: `statement` (with `importer`/`imported_at`/`source_path`/
  `detected_format`), `instruments: []`, `positions: []` (with `as_of_date`,
  `cost_basis`, `unrealized_pnl`, etc.), `cash_balances: []`, `ledger_entries: []`.
  Use a `_minimal_snapshot()` helper — see `test_attribution.py` for the shape.

## Verifying the story (auto-gated)

Before you claim done, invoke the `verify-story` skill. It checks:
- Every AC is satisfied (reads implementation + diff)
- Every test in the test plan exists and passes
- `python scripts/run_all_tests.py` is green
- `npx tsc --noEmit` is clean
- `dashboardGoldens.ts` is reverted if your story didn't change dashboard output
- Methodology / contract docs are in sync if the story touched them

**If verify-story reports failures, do not commit.** Fix the failures, re-run,
then commit only when it passes.

## Closing out (auto-delegated to update-docs)

Once `verify-story` is green:

1. Invoke `update-docs` for the deterministic doc reconciliation:
   - Tick every AC + ticket checkbox in the story file; set status to `Done`
   - Update `docs/finance/financial-methodology.md` if a formula changed
   - Update `docs/contracts/<area>-fields.md` if a schema changed
   - Update `docs/product/current-product-state.md` with shipped capability
   - Add a slice-log entry to `docs/product/epic-roadmap.md` + flip snapshot row
   - Update `docs/product/stories/README.md` status column

2. Commit (one commit per ticket is fine, or one per story). Name the PR
   `US-<n>: <title>`. Squash-merge; prune local + remote branch;
   fast-forward the primary worktree.

## Definition of Done checklist

- [ ] Every acceptance criterion in the story file is satisfied
- [ ] Every test in the story's test plan exists and passes
- [ ] `verify-story` skill reports pass (this gates the commit)
- [ ] `update-docs` skill has reconciled contracts / methodology / slice log
- [ ] Story status set to `Done`; tickets checked off
- [ ] `dashboardGoldens.ts` reverted unless story changed dashboard output
- [ ] PR opened naming the story

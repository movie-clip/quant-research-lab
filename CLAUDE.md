# quant-research-lab

A **local-first, deterministic, auditable** decision-support platform for systematic personal investing. The product imports broker portfolios, computes deterministic analytics, and presents holdings analysis under explicit financial guardrails.

> The product is **not** a black-box prediction engine. It is a research workbench where every displayed financial number must be explainable, traceable, and reproducible.

## ⚠️ Critical: financial accuracy comes first

**If the math or financial methodology is wrong, nothing else matters.** Before changing any analytics, factor formula, or trust-state logic:

1. **Read `docs/finance/financial-methodology.md`** — the canonical source of truth for every implemented formula
2. **Update tests in the same pass** — every methodology change must include or update regression tests
3. **Surface trust state explicitly** — never fabricate, never silently fallback, never collapse `withheld` into `unavailable`

The four hard guardrails (in priority order):

1. **Methodology traceability** — every UI metric maps to one engine formula and one code path. If you can't trace it, don't ship it.
2. **Truth-class separation** — broker truth, snapshot analytics, synthetic history, and persisted imports are distinct. Never mix them in a single response.
3. **Trust semantics over fabrication** — `verified > degraded > withheld > unavailable`. Surface the level; don't fill in plausible values.
4. **No execution** — the system never places trades or moves money.

## Product: three tabs

The product has three tabs: **Dashboard**, **Exposure**, and **Risk**.

| Tab | What it shows |
|---|---|
| Dashboard | Portfolio performance — time-weighted returns, benchmark comparison, monthly returns, risk metrics, investor economics |
| Exposure | Holdings breakdown — sector exposure, ETF look-through, market overlap, factor model |
| Risk | Pre-decision risk-budget views — stress scenarios (factor-shock projections), drawdown analytics (underwater curve + top-N episodes), VaR & distribution (histogram + percentiles + tail risk + shape) |

Exposure also shows a **vs Market drift panel** at the top: rolling portfolio return vs a selectable benchmark (SPY default) for 1m, 3m, 6m, 12m, and since-import windows.

## Where to find what (canonical doc map)

| Doc | Purpose |
|---|---|
| `README.md` | Public-facing project overview |
| `CLAUDE.md` (this file) | Agent onboarding: project identity, guardrails, conventions |
| `docs/product/epic-roadmap.md` | Epic snapshot + slice log |
| `docs/product/prd/epic-34-answerable-dashboard-and-reachable-trust.md` | Most-recently shipped epic PRD (Epic 34). **If this looks stale, `docs/product/epic-roadmap.md` is the source of truth for which epic is current** — this row is a convenience pointer, not the record. |
| `docs/product/stories/` | User stories — one file per story |
| `docs/product/current-product-state.md` | Canonical shipped-state inventory |
| `docs/finance/financial-methodology.md` | Source of truth for every financial formula |
| `docs/architecture/system-architecture.md` | Backend seams, route inventory, truth class semantics |
| `docs/contracts/*.md` | Field inventory — backend ↔ TS type ↔ UI traceability |
| `docs/contracts/risk-fields.md` | Risk-tab contract: stress, drawdown, VaR & distribution response shapes (Epic 13) |
| `docs/contracts/currency-risk-fields.md` | Currency Risk Contribution contract: local/FX/interaction return-decomposition and component-covariance variance-share response shapes (Epic 26) |
| `.claude/skills/quant-research/SKILL.md` | Research a financial concept; produce a brief + methodology section |
| `.claude/skills/write-story/SKILL.md` | Turn idea / brief into a ticketed user story |
| `.claude/skills/build-story/SKILL.md` | Implement a ticketed story end-to-end |
| `.claude/skills/write-tests/SKILL.md` | Write pytest / vitest per project conventions (auto-invoked by build-story) |
| `.claude/skills/verify-story/SKILL.md` | QA gate — checks ACs / tests / docs / regressions; blocks commit on FAIL |
| `.claude/skills/update-docs/SKILL.md` | Reconcile contracts / methodology / slice log after implementation |
| `.claude/skills/ui-polish/SKILL.md` | UI design system reference — tokens, primitives, chart defaults, a11y baseline (auto-invoked by build-story for frontend tickets) |
| `.claude/skills/fmp-data/SKILL.md` | FMP integration reference — symbol resolution, cache, adding tickers |

## Tech Stack

| Layer | Tech |
|-------|------|
| Desktop | React 18 + TypeScript + Vite, Tauri 2 (Rust shell) |
| Quant Engine | Python FastAPI + Uvicorn + Pydantic |
| Market Data | FMP (Financial Modeling Prep) via local cache |
| Testing | Vitest (frontend), Pytest (backend) |

## Repository Layout

```
apps/desktop/src/
  app/                  # Core state, storage, App shell, routing
  features/
    portfolio/          # Holdings, exposure, diagnostics, dashboard
    market-data/        # Market data integration
    settings/

services/quant-engine/app/
  api/routes/           # FastAPI routes: exposure, dashboard_history, diagnostics, drift, attribution, correlation, stress, drawdown, distribution, provenance, imports, market_data, cache, currency_risk, health
  analytics/            # Portfolio analytics (returns, drawdown, distribution, exposure, risk, attribution, correlation)
  clients/              # FMP market data client (with caching)
  core/                 # Settings, logging, caching infrastructure
  domain/               # Ledger + accounting domain model
  importers/            # Broker parsers (Interactive Brokers, Freedom24, ESPP)
  instruments/          # Instrument registry
  schemas/              # Pydantic models (CONTRACT SOURCE OF TRUTH)
  services/             # Business logic services (dashboard, diagnostics, exposure, drift, attribution, correlation, stress, drawdown, distribution)
  tests/                # Pytest suite

docs/
  product/
    prd/                # PRDs — one per epic
    stories/            # User stories
    epic-roadmap.md     # Epic snapshot + slice log
    current-product-state.md  # Shipped-state inventory
  finance/              # Financial methodology
  architecture/         # System architecture + truth classes
  contracts/            # Field inventory docs (backend ↔ TS ↔ UI)
```

## Architecture: Truth Classes

| Class | Description |
|-------|-------------|
| **Broker Truth** | Imported positions/ledger from broker statements |
| **Snapshot Analytics** | Point-in-time computed metrics from current holdings |
| **Synthetic History** | Reconstructed historical returns from current holdings + market data |
| **Persisted Imports** | Saved import artifacts (content-addressed, immutable) |

Trust ladder: `verified > degraded > withheld > unavailable`. Never fabricate or fill missing data — surface the trust level instead.

## Development Commands

```bash
# Start both dev servers (backend on :8000, frontend on :5173)
python scripts/run_dev.py

# Tests — canonical entrypoint. A green run writes .claude/.last-test-pass;
# the pre_commit_gate hook (see "Mechanical gates" below) requires that marker
# to be fresher than your non-.md changes before any `git commit` is allowed.
python scripts/run_all_tests.py             # all
cd services/quant-engine && pytest          # backend
cd apps/desktop && npx vitest run           # frontend
cd apps/desktop && npx tsc --noEmit         # type-check

# FMP cache management
python scripts/manage_cache.py

# After replacing docs/IB2026.csv with a fresh broker export (requires
# FMP_API_KEY): re-captures the frozen golden market data, regenerates
# dashboardGoldens.ts, runs the full suite. Statement-truth pins live in ONE
# module (app/tests/statement_truths.py) — see
# docs/architecture/testing-architecture.md#statement-refresh-workflow.
python scripts/refresh_statement.py

# Dead-code gate (Epic 23 / US-23.8). ENFORCED: run_all_tests.py runs
# `detect_deadcode.py --strict` (ruff + vulture + knip, zero-findings) + `tsc
# --noEmit` as gate steps, so newly-introduced dead code FAILS the suite.
#   pip install -r services/quant-engine/requirements-dev.txt   # ruff + vulture (one-time)
python scripts/detect_deadcode.py            # ruff + vulture + knip summary (informational)
python scripts/detect_deadcode.py --strict   # exit non-zero on any finding (the gate)
# Reading a failure: the offending detector + file:line is printed. If the symbol
# is genuinely dead → remove it. If it's a dynamic-use false positive (pytest
# fixture, Pydantic/FastAPI hook, signature-match kwarg, persistence sanitizer,
# CLI entry point), add a REASONED entry to services/quant-engine/vulture_allowlist.py
# (Python) or apps/desktop/knip.json (TS) — every allowlist entry must name why.
# knip uses `ignoreExportsUsedInFile: true`, so a flagged export is used NOWHERE
# (truly dead), not merely over-exported. Improvement findings (hardcodes/magic
# numbers) are catalogued in docs/tech-debt-register.md → Epic 24.
```

## Mechanical gates (CI + hooks)

The quality gates are enforced mechanically, not honor-system:

- **CI** — `.github/workflows/ci.yml` runs `python scripts/run_all_tests.py` (golden regen → pytest → vitest → tsc → dead-code strict gate) on every PR and push to `main`. The suite is network-free, so CI needs no secrets.
- **Commit gate hook** — enforced at two layers, both checking the same thing (`.claude/.last-test-pass` exists and is fresher than every changed non-`.md` file; the marker is written only by a fully green `run_all_tests.py` run). The **git-level** `scripts/githooks/pre-commit` (a POSIX shell wrapper, wired via `git config core.hooksPath scripts/githooks`, execing `scripts/hooks/git_pre_commit.py`) is the actual enforcement boundary — it fires on every `git commit` regardless of which tool or terminal invoked git, because it runs inside git itself rather than inside any particular tool's interception layer. `core.hooksPath` is local git config, not something committed to the repo; `scripts/run_all_tests.py` idempotently sets it early in every run (`ensure_git_hooks_wired()`), so any dev or agent session that has run the suite at least once has the git-level hook wired — a clone that has never run the suite yet does not. The **Claude Code** `scripts/hooks/pre_commit_gate.py` (PreToolUse, wired in `.claude/settings.json`, matched on the `Bash` tool) remains as a faster-feedback duplicate inside agent sessions, not the boundary itself. If a commit is blocked, re-run the suite — do not try to bypass either hook.
- **Schema contract hook** — `scripts/hooks/schema_edit_reminder.py` (PostToolUse) fires after any edit under `app/schemas/` reminding that the mirroring TS types and `docs/contracts/<area>-fields.md` must change in the same pass.
- **PR template** — `.github/PULL_REQUEST_TEMPLATE.md` structures every PR around the story: story ID, AC checklist, contracts/methodology checklist, verify-story verdict. GitHub only auto-fills it in the web UI, so when opening a PR with `gh pr create`, fill the template out explicitly as the PR body (`--body`/`--body-file`) — don't write a free-form description.

## Backend Conventions (`services/quant-engine/`)

- **Schemas first**: `app/schemas/` is the contract source of truth. Change schemas before routes or business logic.
- **Market data via FMP client**: `app/clients/fmp.py` handles caching. Never call FMP directly from routes.
- **Trust semantics**: Every field that can be missing carries a trust level. Never fabricate.
- **Route pattern**: Check existing routes in `app/api/routes/` first. Schemas → service → route → register in `app/api/main.py` → tests.

## Frontend Conventions (`apps/desktop/`)

- **Types mirror backend schemas exactly**: When a Pydantic schema changes, update the desktop TS types and the matching `docs/contracts/<area>-fields.md` in the same pass.
- **Trust levels rendered visibly**: Never silently suppress `withheld` or `degraded` — show the badge.
- **No fabrication**: If data is `null`/`unavailable`, render the unavailable state, never zero or placeholder.
- **Frontend stays thin on finance**: No portfolio math in components. Ask the engine.

## Delivery model

Work is delivered as **PRD → User Story → Ticket**. See `docs/product/stories/README.md` for the story index.

Six project skills compose the full development cycle:

```
quant-research → write-story → build-story → write-tests → verify-story → update-docs
   (research)      (plan)       (implement)    (cover)        (QA gate)    (sync docs)
```

| Skill | When to use |
|---|---|
| **`quant-research`** | New financial concept — produce a Research Brief + methodology section |
| **`write-story`** | Feature idea (or research brief) → complete, ticketed User Story file |
| **`build-story`** | Implement a ticketed story end-to-end. Auto-invokes write-tests, ui-polish, verify-story, update-docs |
| **`write-tests`** | Write pytest / vitest per project conventions. Usually auto-invoked from build-story |
| **`verify-story`** | QA gate before commit. **Returns FAIL → commit is blocked.** Auto-invoked from build-story |
| **`update-docs`** | Reconcile contracts, methodology, slice log after implementation. Auto-invoked at close-out |

Plus two reference skills (consulted *from within* the cycle, not steps in it):

- **`ui-polish`** — design system reference for any Exposure-tab card work (tokens, primitives, chart defaults, accessibility baseline). Auto-invoked by `build-story` for frontend tickets; the design-system audit fails the build if its contract is violated.
- **`fmp-data`** — FMP integration deep-dive; read when adding tickers or debugging market-data flows.

## When in doubt

1. **For methodology questions** → `docs/finance/financial-methodology.md`
2. **For "what's shipped today"** → `docs/product/current-product-state.md`
3. **For "what's the next story"** → `docs/product/stories/` + the `build-story` skill
4. **For "what's the scope of this epic"** → read `docs/product/epic-roadmap.md` **first** to find which epic is current, then open that epic's PRD in `docs/product/prd/`. At the time of writing the most recent is Epic 34 (`epic-34-answerable-dashboard-and-reachable-trust.md`), but the roadmap is the authority — a named PRD here goes stale every time an epic ships.
5. **For "where are we overall"** → `docs/product/epic-roadmap.md`
6. **For "where does this field come from"** → `docs/contracts/<area>-fields.md`

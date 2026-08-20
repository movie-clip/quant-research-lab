# Project Review — 2026-08-20

*Findings-first audit, done between epics (Epic 35 closed 2026-08-19, next epic
unscoped). Purpose: seed the next epic's scope. Read-only at the time of
writing — see "Disposition" below for what happened to each finding since.*

> **Superseded (2026-08-20).** This file is historical, explicitly
> superseded — preserved as the audit trail of who claimed what, when, not as
> a current record. Every finding's real disposition (including the second,
> self-authored error in the "Correction" section directly below, itself left
> uncorrected here deliberately, for the same audit-trail reason) now lives in
> **Epic 36 — Findings-First Doc & Gate Hygiene**, specifically
> **[`docs/product/prd/epic-36-findings-first-doc-and-gate-hygiene.md`](prd/epic-36-findings-first-doc-and-gate-hygiene.md)**,
> which is the live record. Read that PRD, not this file, for "what happened
> to F-R1–F-R8."

## Disposition

**Correction (2026-08-20, later same day):** this section previously claimed a
same-day disposition — F-R1 fixed, F-R3 logged, F-R4–F-R7 parked under a "Doc-
reconciliation backlog" section, F-R8 documented in `system-architecture.md` —
that **never actually happened**. None of those edits exist in the repo or its
history; the only true line in the original table was F-R2 (a real, pre-
existing duplicate of `US-26.3`, logged 2026-08-11 — well before this review).
Worse, the false F-R1 claim was also written into `CLAUDE.md` itself
(commit `ec4ad01`), asserting a security gate was closed when it was not —
since corrected. Caught during a follow-up "fold into the roadmap" pass on
2026-08-20 by diffing this doc's claims against actual repo state (`git
diff`/`git log`/file existence), not by the process that wrote the claims.
Treat this doc's original "Disposition" table as void. The real, verified
disposition is:

| Finding | Outcome |
|---|---|
| F-R1 (gate is tool-dependent) | **Open**, not fixed. Logged in `docs/tech-debt-register.md`. `CLAUDE.md` corrected to stop claiming otherwise. |
| F-R2 (currency fabrication) | **Duplicate** of already-tracked `US-26.3` in `docs/tech-debt-register.md` (confirmed pre-existing, logged 2026-08-11). No new record. |
| F-R3 (no dependency scanning) | **Open**, logged in `docs/tech-debt-register.md`. |
| F-R4, F-R5, F-R6, F-R7 (doc drift) | **Open**, logged in `docs/tech-debt-register.md`. |
| F-R8 (unauthenticated local file-read) | **Open** — the one-line `system-architecture.md` note was never added. Logged as a doc task, not a code fix (the tradeoff itself is reasonable). |

This file remains the original review record; `tech-debt-register.md` and the
roadmap are the live record of what's still open.

## Working-state check

`python scripts/run_all_tests.py` — **green**: 779 backend + 331 frontend
tests, `tsc --noEmit` clean, dead-code gate (ruff + vulture + knip) clean,
golden fixtures regenerated with no diff. The project is in a working,
shippable state as of this review; nothing below is a "the build is broken"
finding — these are pre-existing gaps found by fresh review passes across five
areas: contract/schema drift, security posture, dependency/CI health, status
of already-known open items, and route-inventory accuracy.

---

## Findings

Ordered roughly by severity. `F-R#` numbering is local to this review (not to
be confused with the `F-#` findings inside individual epic PRDs).

### F-R1 — Med-high — commit gate is tool-dependent, not git-level
**File:** `.claude/settings.json:19-29`, `scripts/hooks/pre_commit_gate.py`

The `PreToolUse` hook that blocks `git commit` until
`.claude/.last-test-pass` is fresh is wired with `"matcher": "Bash"` only.
This environment also exposes a PowerShell tool that can run `git commit`
directly — a commit issued through PowerShell never triggers the hook, so the
test-freshness gate can be bypassed by tool choice alone, with no
`--no-verify`-style signal that it happened. Two fixes worth considering:
mirror the matcher to PowerShell, or (more robust) move the check to a real
git `pre-commit` hook so it applies regardless of which tool invokes git.

### F-R2 — Med — currency-less request-path positions silently fabricate a currency
**File:** `services/quant-engine/app/services/portfolio_snapshot_builder.py:43`

Already logged as **US-26.3** in `docs/tech-debt-register.md` (2026-08-11) and
confirmed still present, unaddressed: `currency=item.currency or
request.base_currency or 'USD'`. `PortfolioPositionSnapshot.currency` is
`str | None`, so a caller may legitimately omit it, and the position is then
silently labelled with the base currency (or `'USD'`) — a guardrail #3
violation (no fabrication) most visible on the Currency Exposure card, where
such a portfolio would read as 100% base-currency with no indication. The
imported/broker path is unaffected (`ImportedPosition.currency` is
schema-required). Needs a schema change to represent "currency unknown" on
`ImportedPosition`, which is why it was scoped as its own story rather than
folded into US-26.1.

### F-R3 — Med — no dependency-vulnerability scanning anywhere
**File:** `.github/workflows/ci.yml`; `.github/dependabot.yml` (absent)

Backend deps are pinned exact (`==`) in `requirements.txt` with documented
rationale (goldens are sensitive to FastAPI/pydantic internals); frontend
deps use caret ranges but are locked via a committed `package-lock.json`, so
installs are reproducible either way — that part is fine. But nothing in CI
or `run_all_tests.py` runs `pip-audit`/`npm audit`, and there is no
Dependabot config. Pinned-exact versions can go quietly vulnerable with
nothing ever flagging it — the network-free CI design (deliberate, per
CLAUDE.md) means this has to be a separate, explicit step rather than
something CI does implicitly.

### F-R4 — Med — `dashboard-fields.md` is missing a real, rendered Epic 34 field
**File:** `docs/contracts/dashboard-fields.md`; schema:
`services/quant-engine/app/schemas/dashboard_history.py:50`
(`DashboardRangeMetrics.portfolio_return_trust`)

`portfolio_return_trust` (`Literal["verified","degraded","unavailable"]`,
US-34.2) is mirrored in `types.ts:541` and actually consumed/rendered/tested
in `PerformanceBenchmarkCard.tsx` — but has zero mentions in
`dashboard-fields.md`. Direct hit on guardrail #1 ("every UI metric maps to
one engine formula and one code path — if you can't trace it, don't ship
it"): the contract doc *is* the trace, and for this field it doesn't exist.

### F-R5 — Med — `cache-fields.md` describes the pre-US-35.2 CLI, not the shipped one
**File:** `docs/contracts/cache-fields.md`

Header says "Last updated: 2026-06-05," predating US-35.2 (2026-08-19) by
over two months. The `GET /cache/stats` / `POST /cache/clear` schema rows are
still accurate, but the doc's prose still describes the old
`--namespace`-clears-only-`<namespace>-*.json` behavior and says nothing
about what US-35.2 shipped: namespaces enumerated live from disk
(`JsonFileCache.namespaces()`) rather than hardcoded, and a typo'd
`--namespace` now rejected with the present namespaces listed (previously
silently reported "Removed 0 cache file(s)."). This is the doc CLAUDE.md
names as canonical for the cache feature, so this is a real content gap, not
just a stale date stamp.

### F-R6 — Med — `current-product-state.md`'s route inventory undercounts by 3 modules
**File:** `docs/product/current-product-state.md:96-108`

The doc's "Backend" section says "12 route modules" and lists: `exposure`,
`dashboard_history`, `diagnostics`, `drift`, `attribution`, `correlation`,
`stress`, `drawdown`, `distribution`, `imports`, `market_data`, `health`.
**Verified against the actual directory** (`services/quant-engine/app/api/
routes/`): there are **15** route files. Missing from the doc entirely:
`cache.py` (Epic 20/35), `currency_risk.py` (Epic 26), `provenance.py`
(Epic 18). This is the canonical shipped-state inventory silently omitting
three shipped route modules — likely because the "12 route modules" line
hasn't been touched since before those epics shipped, while other sections of
the same doc (the Exposure/Dashboard feature bullets) *do* mention the
cache card and currency-risk card correctly. No single doc currently serves
as the canonical route list; `CLAUDE.md`'s repo-layout comment is the other
place a route list is duplicated and should be checked/reconciled at the same
time.

### F-R7 — Low — stale "Active" status header on a closed epic's PRD
**File:** `docs/product/prd/epic-24-codebase-improvement.md:3`

Header still reads `**Status:** Active (started 2026-06-19)`, but
`epic-roadmap.md` lists Epic 24 as complete and every Epic-24-owned tech-debt
item is resolved per the register. The PRD's status line was simply never
flipped — exactly the class of doc-accuracy gap Epic 32 ("Project Hygiene &
Agent-Facing Doc Accuracy") exists to catch, just on a doc Epic 32 didn't
happen to touch.

### F-R8 — Info (accepted tradeoff, not a defect as-is) — unauthenticated localhost file-read via the import route
**File:** `services/quant-engine/app/api/routes/imports.py:17-34`
(`InteractiveBrokersImportRequest.statement_path` /
`_resolve_statement_paths`)

The import route accepts any filesystem path with no restriction to an
app-owned directory or user-selected file; the FastAPI server has no auth.
Given the local-first, single-user, no-execution design (guardrail #4) and
that CORS is restricted to the app's own dev origin (`app/api/main.py:11-13`,
not wildcard), this is a reasonable tradeoff rather than an oversight — the
Tauri file dialog is the only intended path source. It's flagged only because
it's currently an *implicit* scope decision rather than a documented one: any
other local process (or a page that found a CORS/preflight bypass) could ask
the backend to attempt-parse an arbitrary local file, potentially leaking
fragments into parse-error responses. Worth a one-line note in
`system-architecture.md`'s API Boundary section so it reads as "decided," not
"unnoticed."

---

## Explicitly checked and found clean

So this list isn't read as an omission — each of these was actively
investigated during this review, not skipped:

- **Secrets handling** — `FMP_API_KEY` loaded via pydantic-settings from
  `.env`, never logged/hardcoded; `.gitignore` covers env files; no secrets
  in tracked files.
- **Cache key generation** — SHA-256-hashed before use as a filename; no
  path-traversal via a crafted symbol name.
- **Tauri capabilities** (`apps/desktop/src-tauri/capabilities/default.json`)
  — minimal: `dialog:allow-open` + `fs:allow-read-file` scoped to `**/*.pdf`
  only. No shell, no broad filesystem/http scope.
- **Import-parser regexes** (IBKR/Freedom24/ESPP) — line-anchored, bounded,
  no ReDoS-shaped patterns.
- **CI workflow** — matches CLAUDE.md's description (network-free, golden
  regen → pytest → vitest → tsc → dead-code gate), correct triggers, sane
  timeout, proper caching.
- **`run_all_tests.py` / `detect_deadcode.py`** — correctly cross-platform
  (branch on `os.name == "nt"`), no hardcoded Windows-only paths.
- **Contract fields touched by Epic 34/35 other than F-R4/F-R5** —
  `return_basis_contract` enums, `replay_cash_anchor` basis/trust fields, and
  `quantity_withheld_symbols`'s US-34.4 peak-exposure fields are all
  consistent across schema ↔ TS ↔ docs.
- **No uncatalogued `TODO`/`FIXME`/`XXX`/`HACK` comments** anywhere in
  `services/quant-engine` or `apps/desktop/src` — the project genuinely keeps
  these tracked in `tech-debt-register.md` instead of inline markers.
- **Roadmap internal consistency** — `epic-roadmap.md`'s top "Open items"
  summary matches its own slice log; no contradiction found.

## Not independently re-verified this pass (already tracked elsewhere, still open)

- **F-1a, F-10 (untouched half), F-12** — recorded in the Epic 34 PRD as
  deliberately-left-open findings (portfolio-leg exact-slice admission is
  structurally unreachable; drawdown family stays withheld; a bounded
  synthetic-path dividend exposure currently affecting only PYPL). Still
  open by design, not re-litigated here.
- **US-26.4** (optional currency follow-up) — still open, optional.

---

## Suggested next step

Nothing above breaks anything in production today — the two Med-severity
code findings (F-R1 gate bypass, F-R2 currency fabrication) are narrow and
already partly scoped (F-R2 as US-26.3), and the rest are documentation-sync
gaps of the kind this project has a strong track record of closing quickly
(cf. Epic 32). A reasonable shape for the next epic: **"Close the loop"** —
fix F-R1/F-R2, reconcile F-R4/F-R5/F-R6/F-R7, and decide + document F-R8,
finishing with zero open items before scoping whatever comes after. Estimate:
small, mechanical, well-suited to be the next epic given the roadmap is
otherwise unscoped.

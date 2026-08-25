# Epic 40 — Snapshot Trust & Fidelity Follow-Through

**Status:** Completed (created 2026-08-25)
**Created:** 2026-08-25
**Closed:** 2026-08-25
**Seeded by:** leftover findings carried out of the
`2026-08-24-sbio-still-unclassified-bug` run rather than a fresh discovery —
three items named in that run's own `run.md` Open table as `CARRIED` (not
new), plus a fourth ("no freeze-date signal in the snapshot picker" /
`run_metadata.source_status`/`.confidence` never frozen) surfaced directly by
this run's own scout pass over that carried list
(`.agentic/runs/2026-08-25-leftover-findings-fold-in/01-scout.md`,
`02-delivery-brief.md`). Also folds in two adjacent test-infra leftovers
(`RecordingMarketData`'s missing two delegate methods; a dead `market_data`
parameter on `_build_shared_sector_overlap`) as housekeeping inside US-40.1,
per the producer's delivery brief. Ships as its own new, dedicated two-story
epic rather than reopening Epic 39 (closed the same day these findings were
carried) or Epic 38, per the same placement precedent Epic 37, 38 and 39 all
used — new epic, every time, never a reopen.

## Problem

Two independent gaps meant a researcher could not fully trust what a
persisted, imported snapshot showed them, or that choosing one import mode
over another wouldn't quietly cost them data:

1. **No freeze-date signal in the snapshot picker.** The picker labelled a
   persisted imported/base node with the bare literal string `"base"` — no
   date, no timestamp — giving a researcher no way to tell, from the label
   alone, how stale a given snapshot was.
2. **`run_metadata.source_status`/`.confidence` were always live, never
   frozen, sitting beside fields (`availability`, `lookthrough`,
   `market_overlap`, `current_state_concentration`) that already correctly
   freeze at import.** Structurally the same coupling as the already-fixed
   `getBenchmarkTrust`/`CR-1-frontend.md` bug (2026-08-24 run's Finding 1),
   though dormant rather than actively reachable — a research grep found zero
   current consumers of these 3 fields for trust display, so this was a
   structural trap for a future card, not an active misrepresentation.
3. **`add_snapshot` silently discarded a node's imported/reproducibility
   history.** `processImportedFiles`'s `add_snapshot` branch passed
   `importedHistorySnapshot: null` to `saveImportedSnapshotNode`, while the
   `replace` branch on the same function correctly passed the real,
   just-imported analyze-upload response. A researcher who chose "Add
   statement" instead of "Replace" lost reproducibility/replay data the
   replace path kept — a gap explicitly deferred (not designed) twice by the
   2026-08-24 run's own `02-`/`03-technical-plan`s for lacking a client-side
   recombination design.

A fourth item scout carried forward (`risk.py:612`/`:1483`'s missing
`market_data` kwarg to `attach_snapshot_metadata`) was confirmed inert today
— only `.asset_class` is read downstream at those call sites — and, per the
delivery brief's recommendation, was excluded from this epic's scope
entirely (routed to `docs/tech-debt-register.md` instead).

## Goal

Ship both follow-through stories:

- **US-40.1** — the snapshot picker discloses a persisted node's capture
  date instead of the bare `"base"` string, and `run_metadata.source_status`/
  `.confidence` are retired as a trust source everywhere — a documentation
  and consumption-discipline fix (contract-doc statement + a permanent
  regression scanner), not a new freeze path, since the three fields are
  strictly redundant re-derivations of `availability`'s own classification
  with nothing left to preserve that isn't already frozen elsewhere.
- **US-40.2** — `add_snapshot` behaves like `replace` from the researcher's
  point of view: choosing to add a statement rather than replace the
  portfolio never silently discards reproducibility data. Delivered by
  reusing the existing, tested `combine_imported_snapshots` through a new
  thin backend endpoint (`POST /portfolios/import/combine-snapshots`) rather
  than porting its ~250 lines of NAV/TWR/ledger-merge math to TypeScript as a
  second, unaudited implementation.

Both stories folded in two additional housekeeping items under US-40.1 (see
Problem, above): `RecordingMarketData` gained the two delegate methods
(`get_company_profile`, `get_etf_sector_weightings`) it was missing relative
to the real `MarketDataService`, closing a gap in the frozen golden-refresh
harness.

## Non-goals

- **Extending `ImportedExposureOverride`'s freeze mechanism to cover
  `run_metadata.source_status`/`.confidence`.** Explicitly rejected as the
  fix direction — the quant research brief found these fields are pure
  redundant re-derivations of `availability`, and a nested (`run_metadata`
  sub-object) merge would reproduce the same split-vintage-object risk this
  story exists to close, one layer down. The fix is retirement as a trust
  source, permanently, not a new freeze path.
- **The `_build_exposure_source_status`/`_build_exposure_availability`
  duplication** the research brief found (both independently re-implement
  the identical three-way classification over the same inputs). A real
  duplication smell, confirmed by quant-audit, but fixing it touches core
  exposure-classification logic and needs its own quant-research pass first
  per guardrail 1 — routed to `docs/tech-debt-register.md`, not fixed in
  this epic.
- **A pure client-side port of `combine_imported_snapshots`'s merge math to
  TypeScript.** Tech-lead DESIGN deliberately chose a thin backend endpoint
  reusing the existing, tested function instead — see `05-technical-plan.md`
  § US-40.2 design, "Why not a pure client-side merge".
- **`risk.py:612`/`:1483`'s missing `market_data` kwarg to
  `attach_snapshot_metadata`** (the delivery brief's "item 4"). Confirmed
  inert today; excluded from this epic entirely per the human's confirmed
  scope, routed to `docs/tech-debt-register.md` instead.
- **The pre-existing `tech-debt-register.md`/`epic-roadmap.md` Open-items
  backlog.** Confirmed unrelated to this epic's in-scope items, explicitly
  excluded by the human.
- **`run_metadata.reproducibility.benchmark_symbol`.** Confirmed genuinely
  live (reflects the currently-selected benchmark, independent of any
  persisted snapshot) — must not be frozen, unaffected by this epic.

## Story snapshot

| Story | Title | Status |
|---|---|---|
| [US-40.1](../stories/US-40.1-snapshot-trust-signal-completeness.md) | The researcher can tell when a snapshot's trust signals reflect frozen import data, not a live recomputation | Done |
| [US-40.2](../stories/US-40.2-add-snapshot-preserves-imported-history.md) | Adding a new snapshot to a portfolio no longer discards its imported history | Done |

Two-story epic. Stories are structurally independent — no shared function per
`01-scout.md`'s blast-radius check. US-40.1 was sequenced first only as a
soft dependency (its "read the frozen state once, don't recompute" pattern
informed US-40.2's recombination design), not a hard build-order constraint.

## Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-08-25 | US-40.1 | `docs/contracts/exposure-fields.md` gains a sentence declaring `run_metadata.source_status.lookthrough_resolution`, `run_metadata.source_status.benchmark_holdings` and `run_metadata.confidence` permanently excluded from the import-time freeze and never a valid trust source — live/per-render redundant re-derivations of `availability`'s own classification, the same defect class the 2026-08-24 CR-1 fix closed for `benchmark_overlap_status`. Enforced by a new permanent scanner, `runMetadataTrustSourceGuard.test.ts`, failing the suite if any file under `apps/desktop/src/features/portfolio` reads `run_metadata.source_status`/`run_metadata?.confidence`; a new `test_exposure_engine.py` characterization test pins today's self-consistency between those fields and `availability`'s own fields so a future edit that decouples them is caught. No schema change, no engine behavior change — a consumption-discipline fix. Separately, the snapshot picker's label for a persisted imported/base node now discloses its capture date (`variantLabels.ts`'s new `resolveNodeImportDate`, sourced from the client-persisted `PortfolioSnapshot.importedMeta.importedAt`, ancestor-walk fallback for variant nodes, `YYYY-MM-DD` truncation) instead of the bare literal `"base"`; a node with no import behind it renders exactly as before, no fabricated date. Housekeeping fold-in: `RecordingMarketData` (`frozen_market_data.py`) gains `get_company_profile`/`get_etf_sector_weightings` delegate-and-capture methods, matching the real `MarketDataService`'s signatures; the dead `market_data` parameter on `_build_shared_sector_overlap` (`risk.py:1654`) was confirmed NOT caught by `detect_deadcode.py --strict` (vulture doesn't flag unused params) and routed to `docs/tech-debt-register.md` instead of removed here; the `_build_exposure_source_status`/`_build_exposure_availability` duplication is likewise noted and routed to the register. All 6 ACs SATISFIED per tech-lead INTEGRATION's DoD cross-check (file:line citations checked against `05-technical-plan.md`, not report prose). |
| 2026-08-25 | US-40.2 | `add_snapshot` mode no longer discards the existing node's imported/replay history when a new statement is layered on. Design (tech-lead, fulfilling T-40.2.1): rather than porting the ~250-line NAV/TWR/ledger-merge logic to TypeScript, a new backend endpoint reuses the existing, tested `combine_imported_snapshots` verbatim — new `CombineImportedSnapshotsRequest` schema (`app/schemas/imports.py`, `snapshots: list[ImportedPortfolioSnapshot]`) and `POST /portfolios/import/combine-snapshots` route (`app/api/routes/imports.py`), identical `ValueError` → HTTP 400 error-mapping to the existing import route, on the already-registered `/portfolios/import` router. `App.tsx`'s `add_snapshot` branch now calls a new `combineImportedSnapshots` adapter function and passes the combined result into the existing `saveImportedSnapshotNode` call in place of the literal `null` it passed before; a chain of sequential add_snapshot imports stays correctly combined at every link, since each step's input is already the accumulated result of the prior ones. When the two snapshots cannot be combined (e.g. differing base currency, or CR-1's new account-identity guard firing), the existing `importError`/`dashboardSession.importError` disclosure channel — unmodified — surfaces the degradation; no fabricated merge, no silent drop. The `replace`-mode path is untouched (AC4). All 4 ACs SATISFIED per tech-lead INTEGRATION's DoD cross-check. |

**CR-1 (folded into this close-out, not a separate story).** Quant-audit
(`AUDIT-quant.md`) independently recomputed `combine_imported_snapshots`
against real synthetic fixtures and found a MATERIAL double-counting defect
reachable by the route US-40.2 newly wires up: when either input snapshot's
`account_id` was falsy, the pre-existing latest-per-account merge could not
distinguish "same account, unparsed id" (must replace) from "another
account, unparsed id" (must sum) — silently double-counting positions/NAV on
the same-account case (reproduced exactly, e.g. `ending_nav` inflated from
the correct 3000.0 to 5000.0 for a two-statement same-account combine with
one missing `account_id`). Fixed in `statement_importer.py` by
`_validate_compatible_snapshots` failing closed: any falsy `account_id` in a
>1-input combine now raises `ValueError` before any merge runs, surfacing
through the same `ValueError` → HTTP 400 → frontend-degradation channel the
pre-existing base-currency-mismatch check already used — zero new
special-casing anywhere in the stack (traced end to end at integration:
`statement_importer.py` → `imports.py` → `portfolioAnalysisAdapter.ts` →
`App.tsx`'s catch block, all pre-existing and generic). Quant-audit's second
finding — `financial-methodology.md` had no section for
`combine_imported_snapshots`'s multi-statement merge semantics (NAV
selection, TWR compounding), a guardrail-2 traceability gap newly load-bearing
via this epic's new reachable path — was closed by adding a "Multi-Statement
Snapshot Merge" section documenting the full formula (earliest-starting-NAV /
latest-terminal-ending-NAV-per-account / geometric TWR compounding / the
account-identity guard), plus one sentence (per the independent re-audit's
Finding 3, MINOR) noting a single missing `time_weighted_return_pct` input
nulls the whole compounded result rather than partially compounding. Both the
original quant audit and an independent quant re-audit
(`10-quant-reaudit.md`) returned PASS; 3 new regression tests pin the fix in
`test_importer.py`. Zero changes were needed to US-40.2's own route/adapter/
`App.tsx` code to integrate the fix — the defect and its fix were entirely
inside pre-existing code the epic reused, not code the epic wrote.

Final state (per `11-integration.md`'s independently re-run verification):
backend 911 passed, frontend 40 files / 354 tests passed, `tsc --noEmit`
clean, dead-code gate (ruff + vulture + knip) clean, `dashboardGoldens.ts`
byte-identical.

## Notes

**This epic's own PRD was itself a close-out gap, corrected retrospectively.**
This project's convention (established by Epic 37/38/39) is a retrospective
PRD per closed epic, created at close-out. The run that closed Epic 40
(`2026-08-25-leftover-findings-fold-in`) scoped its close-out order to
exclude `docs/product/prd/`, so no PRD file was created alongside
`epic-roadmap.md`'s "Completed Epic: Epic 40" section and the two story
files — flagged as a close-out risk at the time rather than silently skipped
(see both story files' `**PRD:**` headers). This file is that correction,
written by a dedicated follow-up order once the gap was noticed; it does not
change any acceptance verdict, test count, or shipped behavior recorded
above — all of which were already correctly landed in `epic-roadmap.md` and
the two story files before this file existed.

**No CRITICAL findings surfaced anywhere in this epic.** Nothing displayed to
a user was provably wrong before CR-1's fix — the double-counting defect
required a specific account-id parse failure not present in any tested
statement fixture. CR-1 closed a real, newly-reachable MATERIAL gap before it
could produce a wrong number a researcher would see, which is guardrail 4
(trust semantics over fabrication) working as intended.

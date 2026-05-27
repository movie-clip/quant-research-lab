# PRD: Epic 10 — Multi-broker Import Correctness

**Status:** Active
**Last updated:** 2026-05-27

---

## Problem

The product supports three distinct broker statement formats (Interactive Brokers, Freedom24, ESPP) and allows the researcher to compose a combined portfolio by importing one statement first and then adding more via "Add Statement". This sequential import path — the most realistic real-world scenario — has never been tested end-to-end:

1. **No 3-way combine regression test.** `combine_imported_snapshots([IB, FF, ESPP])` works based on manual investigation but has no pytest coverage. A regression in any of the seven merge sub-operations (positions, cash, ledger, totals, instruments, period, account ID) would go undetected.

2. **No `import_statements()` API-level test across all three brokers.** The public function used by the `/portfolios/import/interactive-brokers` route is tested only for single-file and 2-file IB+IB cases; mixed-broker 3-way input is uncovered.

3. **The sequential "Add Statement" flow is not tested on the frontend.** The frontend `overlayImportedSnapshot()` function handles the client-side merge when a researcher adds a second or third statement file. The accumulation of `sourceFileNames` across three sequential overlays — and the final set of positions and cash balances — has no vitest coverage.

4. **No analytics smoke test on a 3-way combined snapshot.** `build_import_bootstrap([IB, FF, ESPP])` calls exposure, risk, and history analytics on the merged result. If any analytics path crashes for a multi-broker snapshot, it would only surface as a runtime error in production.

---

## Goal

- Every combination of the three supported broker importers (IB, Freedom24, ESPP) is covered by a regression test at the quant-engine layer.
- The 3-way sequential frontend add-statement flow is covered by a vitest that verifies correct position and cash accumulation across three overlays.
- A full analytics bootstrap (exposure + history) runs without error on the 3-way combined snapshot.
- Any future change to `combine_imported_snapshots`, `overlayImportedSnapshot`, or any individual importer that breaks the 3-way scenario will fail at least one test before merge.

---

## Non-goals

- No new UI features. This epic adds test coverage only.
- No changes to the import API contract, schemas, or storage format.
- No performance benchmarks for the import pipeline.
- No support for additional broker formats beyond the three currently shipped.
- No investigation of the `import_statement(FF2026)` ValueError mystery — that is a separate concern and all 15 existing importer tests pass as-is.

---

## Story list

| Story | Title | Scope |
|---|---|---|
| US-10.1 | 3-way combine and API-level import tests | Backend pytest — `combine_imported_snapshots` + `import_statements` + analytics smoke |
| US-10.2 | Sequential add-statement overlay tests | Frontend vitest — `overlayImportedSnapshot` 3-step accumulation |

---

## Success signals

- `python scripts/run_all_tests.py` is green with the new tests included.
- A deliberate regression in `_merge_terminal_positions` (e.g., dropping MSFT from ESPP) is caught by US-10.1 tests.
- A deliberate regression in `overlayImportedSnapshot` (e.g., not accumulating `sourceFileNames`) is caught by US-10.2 tests.
- No new tests skip or are marked `xfail`.

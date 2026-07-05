# Epic 28 — IBKR CSV Importer & Statement-Refresh Resilience

**Status:** Backlog (created 2026-07-05)
**Created:** 2026-07-05
**Seeded by:** User workflow reality: the IB2026 statement file is replaced
periodically with a fresh broker export, so (a) anything pinned to exact
statement numbers breaks on every refresh, and (b) the fragile PDF text
extraction re-parses a *layout*, when IBKR offers the same statement as a
machine-readable CSV. `docs/IB2026.csv` (Activity Statement, 2026-01-01 →
2026-06-30, account U8516450) is the real statement to build against.

## Problem

1. **The importer parses a PDF layout instead of a data format.**
   `app/importers/interactive_brokers.py` (~600 lines) regex-matches text
   extracted from the PDF. Epic 24 (US-24.8) already had to harden it against
   post-match conversion failures — a bug class that simply does not exist
   for the CSV export, which is IBKR's own machine-readable format:
   `Section,Header|Data,<columns...>` rows with per-section column headers
   (`Open Positions`, `Trades`, `Deposits & Withdrawals`, `Dividends`,
   `Withholding Tax`, `Fees`, `Interest`, `Cash Report`, `Net Asset Value`,
   `Change in NAV`, `Financial Instrument Information`, ...). The CSV also
   carries data the PDF path degrades or approximates: exact NAV totals at
   full precision, per-currency Open Positions (EUR/GBP/USD), Conid/ISIN in
   `Financial Instrument Information`.

2. **Three hard `.pdf` gates block the CSV** even though the route already
   round-trips arbitrary uploads: `statement_importer.import_statement`
   raises on non-`.pdf`; `App.tsx` filters the file-picker selection to
   `.pdf` and the `<input accept>` attribute allows only PDFs.

3. **Statement refreshes scatter test failures.** The golden pipeline is
   keyed to `docs/IB2026.pdf` (`export_dashboard_goldens.py`,
   `_statement_fixtures.py`) and `scripts/refresh_statement.py` documents the
   recovery flow — but tests that pin statement-truths (holdings symbols,
   registry/ISIN coverage, position counts) fail one by one on every new
   statement, and the FF2026-style hand-pinned truth constants have IB
   equivalents spread across `test_importer.py`, `test_exposure_engine.py`,
   `test_registry_isin_integrity.py`. The user refreshes the statement
   regularly; this must be a one-command flow with a known, small set of
   deliberate updates — not an archaeology session.

## Goal

- A first-class **IBKR Activity-Statement CSV importer** producing the same
  `ImportedPortfolioSnapshot` contract as the PDF path (same truth classes,
  same reconciliation evidence), fail-safe per record like the other
  importers (US-24.4/24.8 discipline).
- The **canonical current IB statement becomes `docs/IB2026.csv`**; the
  golden pipeline and refresh flow key off it. The PDF importer remains for
  the legacy 2022–2025 statements (no CSV exists for them) — it is not
  deleted.
- **Statement-refresh resilience:** replacing `IB2026.csv` with a newer
  export and running `python scripts/refresh_statement.py` is the whole
  workflow; test failures after that are limited to a documented,
  centralized set of statement-truth pins (new-symbol registry entries
  remain a legitimate manual step).

## Non-goals

- No removal of the PDF importer (legacy statements depend on it).
- No new analytics; the snapshot contract does not change shape (fields the
  CSV newly populates — e.g. ISIN via `Security ID` — flow into the fields
  that already exist).
- No Freedom24/ESPP changes.
- No modeling of CSV-only concepts the product doesn't use yet (Realized &
  Unrealized Performance Summary, Interest Accruals, Mark-to-Market
  sections beyond what statement totals need).

## Facts an implementer must know (verified 2026-07-05)

- `docs/IB2026.csv` is UTF-8 **with BOM** (`utf-8-sig` required), 887 lines,
  22 sections. Section rows: `<Section>,Header|Data,<cells...>`; a section
  can restate its Header mid-file with a different column subset (seen in
  `Trades`); numbers can be quoted with thousands separators
  (`"1,069.8600"`); missing numeric cells are `--`; `Open Positions` rows
  carry `DataDiscriminator=Summary` and are per-currency; multi-line quoted
  cells exist (`Period` = `"January 1, 2026 - June 30, 2026"`), so use the
  stdlib `csv` module, never `str.split(",")`.
- The statement window moved: the committed PDF covers Jan–Apr 2026; the CSV
  covers Jan–Jun 2026. Switching the pipeline WILL shift every dashboard
  golden — that regeneration is the epic's acceptance path, not an accident.
- `Change in NAV` carries the reconciliation totals the PDF path already
  parses (starting/ending value, dividends, withholding tax, interest, other
  fees, commissions, deposits & withdrawals); `Net Asset Value` carries
  cash/stock split; TWR appears under `Net Asset Value,Header,Time Weighted
  Rate of Return`.
- Route `/portfolios/import` already accepts arbitrary upload suffixes
  (tempfile preserves them); only the three `.pdf` gates above block CSV.

## Story list

| Story | Title | Priority |
|---|---|---|
| US-28.1 | IBKR Activity-Statement CSV importer (backend) | **High** |
| US-28.2 | Wire CSV end-to-end: detection, upload UI, golden pipeline on IB2026.csv | **High** |
| US-28.3 | Statement-refresh resilience: centralize statement-truth pins + document the refresh workflow | Med |

Recommended order: 28.1 → 28.2 → 28.3. 28.2 regenerates the goldens once
(deliberately, with the Jan–Jun window); 28.3 lands the pin consolidation
that makes the *next* refresh cheap.

## Success signals

- `import_statement(docs/IB2026.csv)` produces a snapshot whose
  reconciliation summary passes against the statement's own `Change in NAV`
  totals, with per-currency positions and ISINs populated from
  `Financial Instrument Information`.
- The desktop app imports a `.csv` statement through the same flow as PDFs.
- Goldens regenerate from `IB2026.csv`; `refresh_statement.py --check`
  passes; the PDF path still imports the 2022–2025 statements byte-identically
  (regression-pinned).
- A simulated statement swap (fixture variant with a changed position) fails
  only the documented statement-truth pin set, nothing else.

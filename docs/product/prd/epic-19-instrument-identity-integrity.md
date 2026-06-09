# Epic 19 — Instrument Identity Integrity

**Status:** Active
**Created:** 2026-06-05

## Problem

The instrument registry maps a broker ticker → a fund name, sector, and
currency. When that mapping is **wrong**, every downstream surface inherits the
error silently: the wrong fund name is shown, the wrong sector is assigned, and
(before the symbol-resolution fixes) the wrong price history could be fetched.
This is exactly what happened with `DFND`: the registry labelled it "VanEck
Defense UCITS ETF" when the user's holding is the **iShares Global Aerospace &
Defence UCITS ETF** — caught only because the user noticed.

The broker statement already carries ground-truth identity evidence for each
holding (a **description** and an **ISIN**), but nothing cross-checks the
registry's mapping against it. A silent ticker→fund mismatch is a truth-class
violation: the product presents an instrument identity it cannot substantiate.

## Goal

- **Detect and surface** ticker→fund mismatches at import: when the registry's
  name for a symbol clearly disagrees with the broker's own description of that
  holding, raise it as a data-quality finding in the existing Import Admission
  Review (rather than silently trusting the registry).
- Keep it **conservative** — flag only clear mismatches (disjoint identity), so
  the signal is trustworthy and formatting differences don't create noise.
- Lay groundwork for stronger **ISIN-keyed** identity later.

## Non-goals

- **No auto-correction.** The check flags; it does not silently rewrite the
  registry or remap the symbol. (Correcting a mapping stays a human/code change.)
- **No external identity lookup.** Providers (yfinance/FMP) do not return ISINs
  for these EU UCITS funds, so verification uses only what the statement already
  carries (description now; ISIN in a follow-up).
- **No new fuzzy-matching dependency.** Pure-Python token normalisation only.
- **No change to symbol resolution / price fetching** (Epic 18 owns that).

## Story list

| Story | Title | Scope |
|---|---|---|
| US-19.1 | Description-consistency import check | Backend — a new `ImportAdmissionCheckV1` comparing each registry-known holding's broker description to the registry name; conservative token-disjoint mismatch → `warn` (degraded). Surfaces through the existing Import Admission Review UI. |
| US-19.2 | ISIN-keyed registry identity | Add ISINs to the registry and validate the statement ISIN against the expected ISIN per symbol (needs authoritative ISIN data sourced from real statements). Backlog. |

Recommended build order: 19.1 → 19.2.

## Success signals

- Re-importing a statement where a ticker is mislabeled (the `DFND` case)
  produces a visible "instrument identity" warning in the Admission Review,
  instead of silently showing the wrong fund.
- No warning is raised for benign formatting differences (e.g. "Vanguard S&P
  500 UCITS ETF" vs "VANGUARD S&P 500 UCITS ETF USD ACC").

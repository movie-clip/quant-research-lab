# US-8.9: Add portfolio drift vs index benchmarks

**Epic:** 8 — Reset to Portfolio Analysis Core
**PRD:** [`epic-8-reset-to-analysis-core.md`](../prd/epic-8-reset-to-analysis-core.md)
**Status:** Done
**Last updated:** 2026-05-25

## Story

As a **portfolio researcher**, I want to see how my portfolio return compares to a market benchmark at the top of the Exposure tab, so that I immediately understand whether my holdings are tracking, outperforming, or underperforming the market.

## Acceptance criteria

- [x] AC1 — Exposure tab shows a "vs Market" panel above the holdings breakdown with rolling portfolio vs benchmark returns for 1M, 3M, 6M, 12M, and Since Import windows.
- [x] AC2 — User can select a benchmark from a dropdown (SPY, QQQ, IEF, VT); the panel refreshes with the new benchmark.
- [x] AC3 — When market data is unavailable for a window, that window shows "—" (unavailable), not zero.
- [x] AC4 — The panel shows a "Synthetic" trust badge, making clear the computation uses current holdings applied backward.
- [x] AC5 — Backend endpoint `POST /engines/drift/run` exists and returns a valid `DriftResult`.
- [x] AC6 — `npx tsc --noEmit` is clean; `npx vitest run` passes; `SKIP_GOLDEN_FRESHNESS_CHECK=1 pytest` passes.

## Tickets

- [x] T-8.9.1 — Backend: `app/schemas/drift.py`, `app/services/drift_engine.py`, `app/api/routes/drift.py`, register in `main.py`, test in `app/tests/test_drift_engine.py`.
- [x] T-8.9.2 — Frontend types and adapter: add drift types to `features/portfolio/types.ts`; add `runDriftEngine` to `portfolioAnalysisAdapter.ts`.
- [x] T-8.9.3 — Frontend component: `features/portfolio/DriftBenchmarkPanel.tsx` + `DriftBenchmarkPanel.test.tsx`.
- [x] T-8.9.4 — Wire into App.tsx and ExposurePanel.tsx.
- [x] T-8.9.5 — Update `docs/product/stories/README.md` and `docs/product/epic-roadmap.md`.

# Epic 29 — Chart First-Render Reliability

**Status:** Complete
**Created:** 2026-07-04
> Renumbered from "Epic 27" on 2026-07-07: this epic was authored in a
> parallel session and collided with Epic 27 — Financial Calculation
> Correctness; the work itself shipped unchanged.


## Problem

After importing a portfolio (without a full page reload), Recharts-based
charts across the app — the new Dashboard Performance & Benchmark card
(Epic 25) and pre-existing Exposure-tab charts (Rolling Correlation,
Factor Attribution, etc.) — sometimes render as an empty area: the card
shell and its background are visible, but no chart lines/bars appear.
Reloading the page always fixes it.

Reproduced and root-caused: the browser console shows Recharts'
`ResponsiveContainer` warning `"The width(-1) and height(-1) of chart should
be greater than 0"` immediately after import resolves. Reading Recharts
3.8's `ResponsiveContainer` source
(`node_modules/recharts/es6/component/ResponsiveContainer.js`) confirms why
this can get stuck rather than self-correcting: the container's initial size
is read synchronously via `getBoundingClientRect()` inside a `useEffect` that
also sets up a `ResizeObserver`. If that first `getBoundingClientRect()` read
happens to land during the same DOM-mutation batch that inserts several other
new cards at once (exactly what happens when an import resolves and multiple
cards flip from `EmptyState` to populated content in one React commit), the
read can return degenerate dimensions. Critically, `ResizeObserver` only
fires on **subsequent size changes** — if nothing later resizes that specific
container (common in a static desktop-app window), the bad initial reading
is never corrected. A full page reload works because on reload every chart
mounts once, already-laid-out, with no competing simultaneous DOM insertions
racing it.

This was never caught by the test suite because `apps/desktop/src/test/setup.tsx`
fully mocks `ResponsiveContainer` (a `React.cloneElement` passthrough with
fixed dimensions) — the real Recharts measurement path never runs under
Vitest/jsdom.

## Goal

- Every chart built on the shared `ChartShell` primitive
  (`apps/desktop/src/app/primitives/ChartShell.tsx`) reliably renders its
  content after an import, with no dependency on a page reload.
- Fix it once, in the shared primitive — not per-chart-file, since this is a
  primitive-level defect, not a per-card bug (confirmed by the Rolling
  Factor Analysis chart on Dashboard exhibiting the same symptom in
  reproduction, and the user separately reporting it on Exposure-tab charts
  this session hasn't touched).

## Non-goals

- No Recharts version change/upgrade — this is a usage-pattern fix, not a
  library defect requiring a version bump.
- No per-chart special-casing — every `ChartShell` consumer must get the fix
  automatically by using the shared primitive; no chart file should need its
  own workaround.
- No attempt to add real `ResizeObserver`-level test coverage (the mock in
  `setup.tsx` exists deliberately to keep tests deterministic and fast; this
  epic does not change that mock, since doing so would require exercising a
  real Recharts/ResizeObserver in jsdom, which is exactly the untestable
  scenario this bug lives in). Verification for this epic is manual/visual
  (see story test plan) plus a `ChartShell`-level behavioral regression test
  for the new mount-timing contract.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-29.1 | Defer ChartShell's chart mount by one tick | Frontend-only — `ChartShell.tsx` gains a `useEffect` + `setTimeout(fn, 0)` gate so `ResponsiveContainer` (and its children) only mount one macrotask after the container `<div>` first commits, decoupling its initial measurement from whatever else is mutating the DOM in the same commit. **Corrected during implementation from `requestAnimationFrame` to `setTimeout`** — rAF is paused while `document.hidden`, which is exactly the state during/after a Tauri native file-picker import. |

## Success signals

- Importing a portfolio and landing on the Dashboard tab shows populated
  charts (Performance & Benchmark, Rolling Factor Analysis) without a reload,
  across repeated manual verification.
- Navigating to the Exposure tab after import shows populated
  Rolling-Correlation / Factor-Attribution / other `ChartShell`-based charts
  without a reload.
- No new console warnings of the `"width(-1) and height(-1)"` shape during
  manual verification.

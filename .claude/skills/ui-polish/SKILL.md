---
name: ui-polish
description: Use when building or polishing a UI component on the Exposure tab — particularly a new analytics card. Triggers when the user says "make this look right", "polish the card", "this needs to look production-ready", "build a card for this new analytic UI-wise", or when build-story auto-delegates the UI slice of a frontend ticket. Provides the design tokens, primitives, chart defaults, and accessibility baseline established in Epic 12 (US-12.1–12.3). The output is a card that compiles, passes the design-system audit, and visually matches the existing Exposure-tab surface without further review.
---

# UI Polish

This skill is the reference for building the next analytics card on the
Exposure tab. The design system was extracted across Epic 12
(US-12.1–US-12.3) from the four cards shipped in Epics 9 and 11. This skill
codifies what was learned so the next card doesn't need a polish pass.

**Scope:** the Exposure tab cards and any future card-shaped surface in the
desktop app. The Dashboard tab and the Concentration Pack are explicitly
*not* migrated to the design system (see "Migration notes" at the end).

## The cycle this skill plugs into

```
quant-research → write-story → build-story → write-tests → verify-story → update-docs
   (research)      (plan)       (implement)    (cover)        (QA)         (sync docs)
                                     │
                                     ▼
                                 ui-polish ← (this skill — auto-delegated for UI slice)
```

`build-story` auto-delegates the UI slice of a frontend ticket to this skill
in the same way it delegates the test slice to `write-tests`. You can also
invoke directly when a card already exists but doesn't match the design system.

## Where things live

| Path | Purpose |
|---|---|
| `apps/desktop/src/app/styles.css` | Design tokens (`:root` block) + canonical CSS rules (`.attribution-trust-badge`, `.window-selector-btn:focus-visible`) |
| `apps/desktop/src/app/primitives/CardShell.tsx` | Section + header + badge/actions slots; `role="region"` + `aria-labelledby` |
| `apps/desktop/src/app/primitives/TrustBadge.tsx` | Canonical Synthetic / Unavailable badge |
| `apps/desktop/src/app/primitives/WindowSelector.tsx` | Generic-over-T window button group; aria-pressed; focus-visible CSS class |
| `apps/desktop/src/app/primitives/EmptyState.tsx` | Title + optional detail for "no data" |
| `apps/desktop/src/app/primitives/LoadingState.tsx` | Centered "Loading…" with tokenised spacing |
| `apps/desktop/src/app/primitives/ErrorState.tsx` | Same envelope as EmptyState with `--color-error` accent border |
| `apps/desktop/src/app/primitives/ChartShell.tsx` | ResponsiveContainer wrapper with required `ariaLabel`; `role="img"` |
| `apps/desktop/src/app/primitives/chartDefaults.ts` | `defaultChartGrid`, `defaultAxisTickStyle`, `defaultMinTickGap`, `defaultTooltipContentStyle` — spread onto Recharts components |
| `apps/desktop/src/test/designSystem.audit.test.ts` | Regression audit — 5 tests enforce no-hex, no-px, single-source-of-truth, chart defaults import |
| `docs/contracts/ui-design-system.md` | Long-lived design-system contract (token + primitive inventory + audit description) |

## The design tokens you have

All tokens live in the `:root` block of `apps/desktop/src/app/styles.css`.
Use them via `style={{ color: 'var(--color-text-muted)' }}` — never literal
hex / px. The design-system audit catches violations.

**Text colors**
- `--color-text-primary` (main body text)
- `--color-text-secondary` (secondary cells in tables)
- `--color-text-muted` (axis ticks, helper text)
- `--color-text-disabled` (unavailable / disabled rows)
- `--color-text-on-accent` (text on filled accent backgrounds)

**Surfaces & borders**
- `--color-surface-panel`, `--color-surface-elevated` (tooltips, hover panels), `--color-surface-overlay` (selected-button fill)
- `--color-border-subtle`, `--color-border-default`, `--color-border-strong`, `--color-border-card`
- `--border-thin: 1px`, `--border-medium: 2px` (use inside border / outline shorthand: `'var(--border-thin) solid var(--color-border-strong)'`)

**Spacing scale** (use everywhere padding/margin/gap are numeric)
- `--space-xxs: 2px`, `--space-xs: 4px`, `--space-sm: 8px`, `--space-md: 12px`, `--space-lg: 16px`, `--space-xl: 24px`, `--space-2xl: 32px`

**Typography scale**
- `--font-chart-tick: 11px` (Recharts axis tick labels)
- `--font-caption: 12px` (helper / footer / small labels)
- `--font-body-sm: 13px` (table cells, secondary copy)
- `--font-body: 14px` (default body)
- `--font-heading-sm: 16px` (section sub-headings)

**Radius & opacity**
- `--radius-sm: 3px`, `--radius-md: 8px`
- `--opacity-unavailable: 0.55` (literal `0.55` in inline-style — see the JSDOM gotcha)

**Correlation-sign palette** (5 levels — for ρ-like values)
- `--color-corr-strong-positive` (ρ ≥ 0.7)
- `--color-corr-positive` (0.3 ≤ ρ < 0.7)
- `--color-corr-neutral` (|ρ| < 0.3)
- `--color-corr-negative` (-0.7 < ρ ≤ -0.3)
- `--color-corr-strong-negative` (ρ ≤ -0.7)

**Factor palette** (one named token per factor; see `FACTOR_LINE_COLORS` map in `FactorAttributionCard.tsx`)
- `--color-factor-market`, `--color-factor-growth`, `--color-factor-value`, `--color-factor-small-cap`, `--color-factor-technology`, `--color-factor-financials`, `--color-factor-health-care`, `--color-factor-energy`, `--color-factor-industrials`, `--color-factor-consumer-staples`, `--color-factor-utilities`, `--color-factor-consumer-discretionary`, `--color-factor-rates-ief`, `--color-factor-rates-tlt`, `--color-factor-credit`, `--color-factor-commodities`
- `--color-factor-default` (fallback when a factor key has no token)

**Chart line colors**
- `--color-line-correlation` (rolling correlation line; also active-button accent)
- `--color-line-beta` (rolling beta line)
- `--color-line-portfolio` (indexed portfolio line)
- `--color-line-benchmark` (indexed benchmark line)

**Trust badge**
- `--color-trust-badge-bg`, `--color-trust-badge-text`, `--color-trust-badge-border`

**Attribution-specific**
- `--color-unexplained` (residual / unexplained line)
- `--color-portfolio-total` (cumulative portfolio line, white on dark)
- `--color-axis-reference` (y=0 reference line)

**Semantic value (gain/loss)**
- `--color-value-positive`, `--color-value-negative`

**Error accent**
- `--color-error`, `--color-error-border`

## The primitives you have

Eight primitives at `apps/desktop/src/app/primitives/`. Import individually
(no barrel export): `import { CardShell } from '../../app/primitives/CardShell'`.

### `<CardShell title badge? actions? className? children />`

`{ title: string; badge?: ReactNode; actions?: ReactNode; className?: string; children: ReactNode }`

Wraps the card in a `<section className="compact-chart-panel" role="region"
aria-labelledby={titleId}>` with a header row containing the title, badge
slot (right of title), and actions slot (far right). Use as the outer
wrapper for every Exposure card. `className` is appended (e.g. for grid
placement like `"dashboard-bottom-grid exposure-primary-section"`).

### `<TrustBadge type tooltip? />`

`{ type: 'synthetic' | 'unavailable'; tooltip?: string }`

Renders the canonical `<span className="attribution-trust-badge">` with the
label `"Synthetic"` or `"Unavailable"`. Use whenever the card displays
synthetic-history data — never hand-roll a badge. The `tooltip` becomes the
element's `title` attribute (native hover).

### `<WindowSelector<T> options value onChange labelFn? ariaLabelFn? />`

`{ options: readonly T[]; value: T; onChange: (next: T) => void; labelFn?: (opt: T) => string; ariaLabelFn?: (opt: T) => string }`

Generic over `T` so it works for numeric windows (`20 | 60 | 252`) and
string labels (`'1m' | '3m' | ...`). Renders a `<div role="group">` with
`<button>` per option; active state via `aria-pressed`. Has the
`.window-selector-btn:focus-visible` class for keyboard focus outline. Use
in the `actions` slot of CardShell.

### `<EmptyState title detail? />`

`{ title: string; detail?: string }`

Use for the "no data" path (snapshot empty, not enough history, etc.).
Renders `<div className="empty-state-panel compact-empty-state">` with title
in `.empty-state-title` + optional `.helper` line.

### `<LoadingState message? />`

`{ message?: string }` (default `"Loading…"`)

Use during async fetch. Centered `<p className="helper">` with token spacing.

### `<ErrorState title? detail? />`

`{ title?: string; detail?: string }` (default title `"Error"`)

Same envelope as EmptyState, plus a `--color-error-border` left accent
border + `--color-error` title color. Use distinctly from EmptyState so the
researcher can tell "fetch failed" from "no data".

### `<ChartShell ariaLabel height? children />`

`{ ariaLabel: string; height?: number; children: ReactElement }` (default `height={260}`)

Wraps a Recharts chart in `<div style={{ height }} role="img" aria-label={ariaLabel}>
<ResponsiveContainer width="100%" height="100%">…</ResponsiveContainer></div>`.
`ariaLabel` is **required** — it's the chart's accessible name. Use for
every Recharts chart; never inline `<ResponsiveContainer>`.

### `chartDefaults` (named exports, not a component)

```ts
import { defaultChartGrid, defaultAxisTickStyle, defaultMinTickGap, defaultTooltipContentStyle } from '../../app/primitives/chartDefaults'
```

- `defaultChartGrid` → spread onto `<CartesianGrid {...defaultChartGrid} />`
- `defaultAxisTickStyle` → `tick={defaultAxisTickStyle}` on XAxis / YAxis
- `defaultMinTickGap` → `minTickGap={defaultMinTickGap}` on XAxis
- `defaultTooltipContentStyle` → `contentStyle={defaultTooltipContentStyle}` on Tooltip

Per-axis overrides via object spread: `tick={{ ...defaultAxisTickStyle, fill: 'var(--color-line-correlation)' }}`.

## The canonical card pattern

Copy this and replace the placeholders. It type-checks, passes the audit,
and renders identically to the existing Exposure cards. Uses the
self-fetching component pattern so the card sources its own data.

```tsx
import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'

import type { ImportedSnapshot, MyFooResponse } from './types'
import { runFooEngine } from './portfolioAnalysisAdapter'

import { CardShell } from '../../app/primitives/CardShell'
import { ChartShell } from '../../app/primitives/ChartShell'
import {
  defaultAxisTickStyle,
  defaultChartGrid,
  defaultMinTickGap,
  defaultTooltipContentStyle,
} from '../../app/primitives/chartDefaults'
import { EmptyState } from '../../app/primitives/EmptyState'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'
import { TrustBadge } from '../../app/primitives/TrustBadge'
import { WindowSelector } from '../../app/primitives/WindowSelector'

type FooWindow = 20 | 60 | 252
const WINDOW_OPTIONS: FooWindow[] = [20, 60, 252]
type LoadState = 'idle' | 'loading' | 'error' | 'done'

type FooCardProps = { snapshot: ImportedSnapshot | null }

export function FooCard({ snapshot }: FooCardProps) {
  const [window, setWindow] = useState<FooWindow>(60)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [result, setResult] = useState<MyFooResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!snapshot) { setResult(null); setLoadState('idle'); return }
    let cancelled = false
    setLoadState('loading'); setErrorMsg(null)
    runFooEngine(snapshot, window)
      .then((data) => { if (!cancelled) { setResult(data); setLoadState('done') } })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : 'Foo engine failed')
          setLoadState('error')
        }
      })
    return () => { cancelled = true }
  }, [snapshot, window])

  return (
    <CardShell
      title="My Foo Metric"
      badge={<TrustBadge type="synthetic" tooltip="Computed from current holdings applied to historical prices." />}
      actions={
        <WindowSelector<FooWindow>
          options={WINDOW_OPTIONS}
          value={window}
          onChange={setWindow}
          labelFn={(w) => `${w}d`}
        />
      }
    >
      {loadState === 'idle' && <EmptyState title="Import a portfolio to view foo." />}
      {loadState === 'loading' && <LoadingState message="Computing foo…" />}
      {loadState === 'error' && <ErrorState title="Foo unavailable" detail={errorMsg ?? 'Engine error'} />}

      {loadState === 'done' && result && (
        <ChartShell ariaLabel="Foo line chart over time">
          <LineChart data={result.series} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid {...defaultChartGrid} />
            <XAxis dataKey="date" tick={defaultAxisTickStyle} minTickGap={defaultMinTickGap} />
            <YAxis tick={defaultAxisTickStyle} />
            <Tooltip contentStyle={defaultTooltipContentStyle} />
            <Line type="monotone" dataKey="value" stroke="var(--color-line-portfolio)" dot={false} isAnimationActive={false} strokeWidth={2} />
          </LineChart>
        </ChartShell>
      )}
    </CardShell>
  )
}
```

## Accessibility checklist

The primitives give you most of these for free; this is what you get + what
you still need to think about.

| Concern | Provided by | What you must do |
|---|---|---|
| Region landmark | `CardShell` — `role="region"` + `aria-labelledby` | Provide a meaningful `title` prop |
| Chart accessible name | `ChartShell` — `role="img"` + `aria-label` | Provide a meaningful `ariaLabel` (e.g. `"Rolling correlation vs benchmark, dual-axis line chart"`) |
| Keyboard focus visible | `WindowSelector` — `.window-selector-btn:focus-visible` rule in styles.css | Use `<WindowSelector>` not a hand-rolled button group; if you add a new interactive primitive, add a matching `:focus-visible` rule |
| Color is not sole encoder | `BenchmarkCorrelationTable` shows the pattern: ▲▲ / ▲ / • / ▼ / ▼▼ Unicode symbol prefix alongside color | When you color-code a value for semantic meaning (positive/negative, strong/weak), also encode it with a symbol or text label |
| Trust state visible | `TrustBadge` | Use whenever the card displays synthetic-history data |
| Native title tooltips | `TrustBadge` + custom `<button title=...>` | Pass `tooltip` prop on TrustBadge; for other elements use the native `title` attribute (consistent with the rest of the cards) |
| `aria-pressed` on toggles | `WindowSelector` | Use the primitive — don't hand-roll |

## Audit-enforced contracts

`apps/desktop/src/test/designSystem.audit.test.ts` runs 5 checks every test
run. If your card fails any of these, the build is red.

| Test | What it catches |
|---|---|
| `no_literal_hex_colors_in_card_files` | A literal `#0aff1c` in `DriftBenchmarkPanel.tsx` / `IndexedReturnChart.tsx` / `RollingCorrelationChart.tsx` / `FactorAttributionCard.tsx` / `BenchmarkCorrelationTable.tsx`. **Fix:** use a token. Escape hatch: `// design-system: escape-hatch: <reason>` immediately above the literal. |
| `no_literal_pixel_values_in_inline_style_props` | `marginBottom: 12` or `padding: '8px 0'` literals on margin/padding/gap/fontSize/borderRadius style keys. **Fix:** use spacing tokens (`var(--space-md)` etc.). Same escape hatch. |
| `trust_badge_primitive_imported_in_all_badge_rendering_cards` | A card that should render a Synthetic badge doesn't import `<TrustBadge>`. **Fix:** import + use the primitive. |
| `synthetic_label_string_is_single_source_of_truth` | The literal string `"Synthetic"` (capital S, JSX text content) appears in any file other than `TrustBadge.tsx`. **Fix:** use `<TrustBadge type="synthetic" />`. |
| `chart_default_props_imported_in_all_chart_files` | A chart file doesn't import from `chartDefaults`. **Fix:** import + spread the defaults onto Recharts components. |

If you legitimately need to add a new card file to the audited surface
(rare), update the `ALL_CARD_FILES` / `CARDS_WITH_BADGE` constants in
`designSystem.audit.test.ts`.

## Anti-patterns

These all fail either the audit, the accessibility checklist, or
plain visual consistency. Do not:

- **Hand-roll a Synthetic badge** — `<span className="attribution-trust-badge">Synthetic</span>` is forbidden by the audit. Use `<TrustBadge type="synthetic" />`.
- **Inline a hex value** — `style={{ color: '#94a3b8' }}` fails the audit. Use `style={{ color: 'var(--color-text-muted)' }}`.
- **Inline a pixel value on a style prop** — `marginBottom: 12` fails the audit. Use `marginBottom: 'var(--space-md)'`.
- **Duplicate the window-selector button group** — hand-rolling a `<div><button>...</button></div>` group with active styling fails both the audit (via reintroducing literals) and the focus-visible contract. Use `<WindowSelector>`.
- **Render a chart without `<ChartShell>`** — fails the chart-defaults import audit; no aria-label means screen readers see an unannotated `<svg>`.
- **Encode meaning via color alone** — fails the accessibility checklist. If you color-code positive/negative or strong/weak, add a symbol or text label too.
- **Use a numeric CSS prop with `var()`** — JSDOM does not parse CSS variables in numeric CSS props (`opacity`, `lineHeight`, `zIndex`). The literal value with a comment is fine; the `--opacity-unavailable: 0.55` token exists for CSS-class-based usage but not React inline-style on numeric props. See `BenchmarkCorrelationTable.tsx` for the documented pattern.
- **Add a new ad-hoc primitive without a test file** — every primitive at `app/primitives/` has a colocated `<Name>.test.tsx`. No exceptions.
- **Mix the legacy CSS classes (`.dashboard-summary`, `.concentration-pack-*`) with the new primitives** — the Concentration Pack is intentionally not migrated yet. Don't try to half-migrate.

## Migration notes

The design system covers the Exposure tab's four new cards
(DriftBenchmarkPanel + IndexedReturnChart, RollingCorrelationChart,
FactorAttributionCard, BenchmarkCorrelationTable). It does **not** cover:

- **Concentration Pack** in `ExposurePanel.tsx` — uses
  `.dashboard-summary`, `.compact-summary-grid`, `.concentration-pack-*`
  CSS classes from the older pattern. Functional and stable; migrating to
  CardShell + primitives is a separate future story.
- **Dashboard tab** components — entirely on the older CSS-class pattern.
  Same future-story status.

If a story you're implementing modifies one of those surfaces, **do not**
opportunistically migrate it. Either keep the legacy pattern there or
flag it for a dedicated migration story.

## Definition of Done (for this skill)

Use this checklist before declaring a card done.

- [ ] Card outer wrapper is `<CardShell>`, not a raw `<section>`
- [ ] Synthetic-history data shows `<TrustBadge type="synthetic" tooltip="..." />` in the badge slot
- [ ] Window/option selection uses `<WindowSelector>`
- [ ] States use `<EmptyState>` / `<LoadingState>` / `<ErrorState>` — not inline `<div className="empty-state-panel">`
- [ ] Recharts chart uses `<ChartShell ariaLabel="...">` (required prop)
- [ ] Recharts grid / axis tick / tooltip use `defaultChartGrid` / `defaultAxisTickStyle` / `defaultMinTickGap` / `defaultTooltipContentStyle`
- [ ] Zero literal hex colors in inline styles (audit-enforced)
- [ ] Zero literal pixel values on margin/padding/gap/fontSize/borderRadius inline-style props (audit-enforced)
- [ ] If color encodes semantic meaning, an additional symbol/label encodes it too
- [ ] All existing audit tests in `designSystem.audit.test.ts` pass
- [ ] Component has a colocated `<Name>.test.tsx` with adapter-mocked tests (per the write-tests skill's frontend section)
- [ ] `npx tsc --noEmit` is clean
- [ ] `python scripts/run_all_tests.py` is green

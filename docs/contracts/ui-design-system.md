# UI Design System Contract

**Feature:** Exposure-tab visual surface (Epic 12)
**Skill:** `.claude/skills/ui-polish/SKILL.md`
**Audit:** `apps/desktop/src/test/designSystem.audit.test.ts`
**Last updated:** 2026-05-29

---

## Trust class preamble

This contract documents the **visual** surface — colors, spacing,
typography, primitives. It is not a financial-data contract. The data
contracts live in `docs/contracts/<area>-fields.md`
(`attribution-fields.md`, `correlation-fields.md`, etc.). Trust semantics
(synthetic / unavailable / verified) are still surfaced via the
`<TrustBadge>` primitive; the schema field is the source of truth, the
badge is the rendering.

The design system is enforced by audit tests, not by review. A card that
violates a token or skips a primitive fails the regression suite at the
audit step, not at a later visual-QA step.

---

## Token inventory

All tokens are defined in `:root` in `apps/desktop/src/app/styles.css` and
consumed via `var(--token-name)` in component inline styles.

### Text colors

| Token | Value | Use |
|---|---|---|
| `--color-text-primary` | (alias `--text`, `#d7dde6`) | Main body text on dark panels |
| `--color-text-secondary` | `#cbd5e1` | Secondary cells in tables |
| `--color-text-muted` | `#94a3b8` | Axis ticks, helper text, low-emphasis labels |
| `--color-text-disabled` | `#6b7280` | Unavailable / disabled rows |
| `--color-text-on-accent` | `#ffffff` | Text painted on filled accent backgrounds |

### Surfaces & borders

| Token | Value | Use |
|---|---|---|
| `--color-surface-panel` | (alias `--panel`) | Primary card surface |
| `--color-surface-elevated` | (alias `--panel-2`) | Tooltips, hover panels |
| `--color-surface-overlay` | `#1d3350` | Selected-button accent fill |
| `--color-border-subtle` | `rgba(255,255,255,0.06)` | Chart grids, row separators |
| `--color-border-default` | `rgba(255,255,255,0.12)` | Header borders |
| `--color-border-strong` | `#2d3448` | Window-selector inactive border, footer top |
| `--color-border-card` | `#2d3748` | Tooltip border |
| `--border-thin` | `1px` | Use inside border / outline shorthand strings |
| `--border-medium` | `2px` | Focus outlines, error accents |

### Spacing scale

| Token | Value | Typical use |
|---|---|---|
| `--space-xxs` | `2px` | Triangle pointer base, minor offsets |
| `--space-xs` | `4px` | Tight gaps, inline icon margins |
| `--space-sm` | `8px` | Button padding, badge margin |
| `--space-md` | `12px` | Header margin-bottom, cell padding x |
| `--space-lg` | `16px` | Inter-component gaps |
| `--space-xl` | `24px` | Card-internal section spacing |
| `--space-2xl` | `32px` | Empty-state vertical padding |

### Typography scale

| Token | Value | Use |
|---|---|---|
| `--font-chart-tick` | `11px` | Recharts axis tick labels, header table cells |
| `--font-caption` | `12px` | Helper / footer / button text |
| `--font-body-sm` | `13px` | Table data cells |
| `--font-body` | `14px` | Default body |
| `--font-heading-sm` | `16px` | Section sub-headings |

### Radius & opacity

| Token | Value | Use |
|---|---|---|
| `--radius-sm` | `3px` | Buttons, small badges |
| `--radius-md` | `8px` | Tooltips, panels |
| `--opacity-unavailable` | `0.55` | Dimmed rows (literal value; JSDOM rejects `var()` in numeric props) |

### Correlation-sign palette (5 levels)

Used by `BenchmarkCorrelationTable.correlationColor()` to color the ρ
column. Pair with the sign-symbol prefix (▲▲ / ▲ / • / ▼ / ▼▼) so color
isn't the sole encoder.

| Token | Magnitude | Hex |
|---|---|---|
| `--color-corr-strong-positive` | ρ ≥ 0.7 | `#3cb79f` |
| `--color-corr-positive` | 0.3 ≤ ρ < 0.7 | `#6ec98f` |
| `--color-corr-neutral` | \|ρ\| < 0.3 | `#94a3b8` |
| `--color-corr-negative` | -0.7 < ρ ≤ -0.3 | `#e08f5a` |
| `--color-corr-strong-negative` | ρ ≤ -0.7 | `#e06a5a` |

### Factor palette (named, 16 factors + default)

Used by `FactorAttributionCard.FACTOR_LINE_COLORS`.

| Token | Factor |
|---|---|
| `--color-factor-market` | Market |
| `--color-factor-growth` | Growth |
| `--color-factor-value` | Value |
| `--color-factor-small-cap` | Small Cap |
| `--color-factor-technology` | Technology |
| `--color-factor-financials` | Financials |
| `--color-factor-health-care` | Health Care |
| `--color-factor-energy` | Energy |
| `--color-factor-industrials` | Industrials |
| `--color-factor-consumer-staples` | Consumer Staples |
| `--color-factor-utilities` | Utilities |
| `--color-factor-consumer-discretionary` | Consumer Discretionary |
| `--color-factor-rates-ief` | Rates (IEF) |
| `--color-factor-rates-tlt` | Rates (TLT) |
| `--color-factor-credit` | Credit |
| `--color-factor-commodities` | Commodities |
| `--color-factor-default` | Fallback when key has no token |

### Chart line colors

| Token | Hex | Line |
|---|---|---|
| `--color-line-correlation` | `#5b87c5` | Rolling correlation ρ |
| `--color-line-beta` | `#3cb79f` | Rolling beta β |
| `--color-line-portfolio` | `#4f8ef7` | Indexed portfolio line |
| `--color-line-benchmark` | `#94a3b8` | Indexed benchmark line |

### Trust badge

| Token | Use |
|---|---|
| `--color-trust-badge-bg` | Badge background |
| `--color-trust-badge-text` | Badge text |
| `--color-trust-badge-border` | Badge border |

Plus the canonical CSS rule `.attribution-trust-badge` in `styles.css`
which composes all three.

### Attribution-specific

| Token | Use |
|---|---|
| `--color-unexplained` | Residual / unexplained line in attribution chart |
| `--color-portfolio-total` | Cumulative portfolio line (white on dark) |
| `--color-axis-reference` | y=0 reference line |

### Semantic value (gain/loss)

| Token | Hex | Use |
|---|---|---|
| `--color-value-positive` | `#48bb78` | Positive contribution / gain |
| `--color-value-negative` | `#fc8181` | Negative contribution / loss |

### Error accent

| Token | Hex | Use |
|---|---|---|
| `--color-error` | `#fc8181` | ErrorState title color |
| `--color-error-border` | `rgba(252,129,129,0.42)` | ErrorState left accent border |

---

## Primitive inventory

All primitives at `apps/desktop/src/app/primitives/`. Named exports only.

| Primitive | Prop signature | When to use | What it creates |
|---|---|---|---|
| `<CardShell>` | `{ title: string; badge?: ReactNode; actions?: ReactNode; className?: string; children: ReactNode }` | Outer wrapper for every Exposure card | `<section className="compact-chart-panel" role="region" aria-labelledby={useId}>` + header with title slot, badge slot, actions slot |
| `<TrustBadge>` | `{ type: 'synthetic' \| 'unavailable'; tooltip?: string }` | Whenever the card shows synthetic-history data | `<span className="attribution-trust-badge" title={tooltip}>Synthetic\|Unavailable</span>` |
| `<WindowSelector<T>>` | `{ options: readonly T[]; value: T; onChange: (next: T) => void; labelFn?; ariaLabelFn? }` | Window/option button group (generic over T) | `<div role="group">` + `<button className="window-selector-btn" aria-pressed={active} aria-label={...}>` per option |
| `<EmptyState>` | `{ title: string; detail?: string }` | "No data to show" — different from error | `<div className="empty-state-panel compact-empty-state">` + `.empty-state-title` + optional `.helper` |
| `<LoadingState>` | `{ message?: string }` (default `"Loading…"`) | Async fetch in flight | Centered `<p className="helper">` with token spacing |
| `<ErrorState>` | `{ title?: string; detail?: string }` (default title `"Error"`) | Fetch/computation failed (distinct from no-data) | Same envelope as EmptyState + `--color-error-border` left accent |
| `<ChartShell>` | `{ ariaLabel: string; height?: number; children: ReactElement }` (default `height={260}`) | Every Recharts chart | `<div style={{ height }} role="img" aria-label={ariaLabel}><ResponsiveContainer>…` |

### `chartDefaults` (constants, not a component)

| Export | Spread / pass onto | Purpose |
|---|---|---|
| `defaultChartGrid` | `<CartesianGrid {...defaultChartGrid} />` | `strokeDasharray: '3 3'`, `stroke: 'var(--color-border-subtle)'` |
| `defaultAxisTickStyle` | `tick={defaultAxisTickStyle}` on `<XAxis>` / `<YAxis>` | `fontSize: 'var(--font-chart-tick)'`, `fill: 'var(--color-text-muted)'` |
| `defaultMinTickGap` | `minTickGap={defaultMinTickGap}` on `<XAxis>` | `40` |
| `defaultTooltipContentStyle` | `contentStyle={defaultTooltipContentStyle}` on `<Tooltip>` | Tokenized background / border / borderRadius / fontSize |

Per-axis overrides via object spread: `tick={{ ...defaultAxisTickStyle, fill: 'var(--color-line-correlation)' }}`.

---

## Audit contract

`apps/desktop/src/test/designSystem.audit.test.ts` runs 5 regression tests
on every `npx vitest run`. A failure means a card is drifting from the
design system; the build is red until fixed.

| Test | What it enforces | How to fix a failure |
|---|---|---|
| `no_literal_hex_colors_in_card_files` | No `/#[0-9a-fA-F]{3,8}\b/` in the 5 audited card files | Replace literal with `var(--color-*)` token; or add `// design-system: escape-hatch: <reason>` comment immediately above the line |
| `no_literal_pixel_values_in_inline_style_props` | No `\d+px` literal or bare numeric on `margin\|padding\|gap\|fontSize\|borderRadius` keys inside style props | Use `var(--space-*)`, `var(--font-*)`, `var(--radius-*)`, `var(--border-*)` tokens; same escape hatch |
| `trust_badge_primitive_imported_in_all_badge_rendering_cards` | Each of the 4 cards that render a Synthetic badge contains the import `from '../../app/primitives/TrustBadge'` | Import + use `<TrustBadge type="synthetic" />` instead of hand-rolling the badge |
| `synthetic_label_string_is_single_source_of_truth` | The literal string `"Synthetic"` (JSX text content) appears in exactly one file: `TrustBadge.tsx` | Replace any other occurrence with `<TrustBadge type="synthetic" />` |
| `chart_default_props_imported_in_all_chart_files` | Each of the 3 chart files contains `from '../../app/primitives/chartDefaults'` | Import the defaults and spread them onto Recharts components |

The `ALL_CARD_FILES`, `CARDS_WITH_BADGE`, and chart-files constants inside
the audit test are the authoritative list of audited files. To add a new
card to the audited surface, update those constants in the test file
(self-evident from the code).

---

## Migration notes

The design system covers these files only:

**Cards** (audited): `DriftBenchmarkPanel.tsx`, `IndexedReturnChart.tsx`,
`RollingCorrelationChart.tsx`, `FactorAttributionCard.tsx`,
`BenchmarkCorrelationTable.tsx`

**Primitives**: all files under `apps/desktop/src/app/primitives/`

It does **not** cover:

### Concentration Pack (inside `ExposurePanel.tsx`)

Uses the older CSS class system: `.dashboard-summary`,
`.compact-summary-grid`, `.concentration-pack-status-strip`,
`.concentration-pack-summary-grid`, `.concentration-pack-grid`,
`.concentration-pack-row`, `.concentration-pack-rank`,
`.concentration-pack-name`, `.concentration-pack-weight`,
`.concentration-pack-value`, `.concentration-pack-badge`.

Functional and stable; migrating to CardShell + primitives is a future
story. The shape is similar (header + status strip + summary grid + two
side-by-side lists), so a migration would mostly be a swap. If/when
migrating: each `<section>` becomes a `<CardShell>`; the status strip's
badges become a tokenized badge component or stay inline CSS classes; the
top-positions / top-sectors lists stay as-is (they're table-like, not
chart-like).

### Dashboard tab

Entirely on the older CSS-class pattern. Same future-story status. Out of
scope for Epic 12; would be its own epic if/when undertaken.

### Other apps/desktop surfaces

Settings page, market-data feature, etc. — none of these are part of the
Exposure-tab analytics surface and so are out of scope for the design
system as it exists today.

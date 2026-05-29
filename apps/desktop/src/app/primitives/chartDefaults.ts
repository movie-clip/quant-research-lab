/**
 * Shared Recharts defaults — Epic 12 / US-12.3.
 *
 * Three chart files (IndexedReturnChart, RollingCorrelationChart,
 * FactorAttributionCard) previously duplicated the same axis / grid /
 * tooltip styling. These exports are the single source of truth.
 *
 * Spread onto the relevant Recharts component:
 *   <CartesianGrid {...defaultChartGrid} />
 *   <XAxis tick={defaultAxisTickStyle} minTickGap={defaultMinTickGap} ... />
 *   <Tooltip contentStyle={defaultTooltipContentStyle} ... />
 *
 * Per-axis overrides use object spread:
 *   <YAxis tick={{ ...defaultAxisTickStyle, fill: 'var(--color-line-correlation)' }} ... />
 *
 * All values use CSS variables from styles.css — never literal hex / px.
 * Audited by designSystem.audit.test.ts.
 */

export const defaultChartGrid = {
  strokeDasharray: '3 3',
  stroke: 'var(--color-border-subtle)',
} as const

export const defaultAxisTickStyle = {
  fontSize: 'var(--font-chart-tick)',
  fill: 'var(--color-text-muted)',
} as const

export const defaultMinTickGap = 40

export const defaultTooltipContentStyle = {
  background: 'var(--color-surface-elevated)',
  border: 'var(--border-thin) solid var(--color-border-card)',
  borderRadius: 'var(--radius-md)',
  fontSize: 'var(--font-caption)',
} as const

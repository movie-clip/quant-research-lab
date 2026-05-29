/**
 * ChartShell — thin wrapper around Recharts ResponsiveContainer.
 *
 * Provides:
 * - A fixed-height parent `<div>` (required for ResponsiveContainer to size
 *   itself; child height="100%" only works inside a non-zero parent)
 * - `role="img"` + required `ariaLabel` so screen readers announce the chart
 *   with a meaningful name (Recharts itself just renders unannotated `<svg>`)
 *
 * Usage:
 *   <ChartShell ariaLabel="Rolling correlation vs benchmark">
 *     <ComposedChart data={data} margin={...}>...</ComposedChart>
 *   </ChartShell>
 */
import { ResponsiveContainer } from 'recharts'
import type { ReactElement } from 'react'

export type ChartShellProps = {
  /** Required — used as the chart's accessible name for screen readers. */
  ariaLabel: string
  /** Fixed pixel height of the chart container. Default 260. */
  height?: number
  /** Single Recharts chart element (LineChart / ComposedChart / BarChart / ...). */
  children: ReactElement
}

export function ChartShell({ ariaLabel, height = 260, children }: ChartShellProps) {
  return (
    <div style={{ height }} role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  )
}

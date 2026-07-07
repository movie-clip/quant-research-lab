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
import { useEffect, useState } from 'react'
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
  // US-27.1: ResponsiveContainer measures its container synchronously in its
  // own mount effect. If that measurement races a same-commit DOM insertion
  // of several other new cards (e.g. right after an import resolves and
  // multiple cards flip from empty-state to populated together), it can read
  // a degenerate size — and ResizeObserver only fires on a subsequent change,
  // never to self-correct a bad first read, so the chart can stay blank until
  // something else (a reload) forces a fresh measurement.
  //
  // Deferring the chart's mount by one tick gives layout a chance to settle
  // before ResponsiveContainer measures. This MUST be a `setTimeout`, not
  // `requestAnimationFrame`: rAF is tied to the next paint and is paused
  // indefinitely while the document is hidden (`document.hidden`) — exactly
  // what happens when Tauri's native file-picker dialog blurs the webview
  // during import, which is precisely when this defer needs to fire. A
  // `setTimeout(fn, 0)` macrotask fires regardless of visibility, since
  // layout itself is computed synchronously independent of paint.
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setReady(true), 0)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div style={{ height }} role="img" aria-label={ariaLabel}>
      {ready && (
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      )}
    </div>
  )
}

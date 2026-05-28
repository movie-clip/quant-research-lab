/**
 * CardShell — canonical wrapper for an Exposure-tab feature card.
 *
 * Replaces the hand-rolled
 *   `<section className="compact-chart-panel">
 *     <div className="section-header-inline ..."><p className="panel-label">...</p><span className="attribution-trust-badge">...</span></div>...`
 * pattern that lived in 5 cards. Owns the section + header layout so the next
 * analytics card just imports CardShell + passes title / badge / actions.
 *
 * Slot props (`badge`, `actions`) are typed as `ReactNode` so callers can
 * pass any element — `<TrustBadge />`, a `<select>`, a `<WindowSelector />`,
 * or a custom composition.
 */
import type { ReactNode } from 'react'

export type CardShellProps = {
  title: string
  badge?: ReactNode
  actions?: ReactNode
  /** Extra className applied to the outer `<section>` (e.g. for extra grid placement). */
  className?: string
  children: ReactNode
}

export function CardShell({ title, badge, actions, className, children }: CardShellProps) {
  const sectionClass = `compact-chart-panel${className ? ` ${className}` : ''}`
  return (
    <section className={sectionClass}>
      <div
        className="section-header-inline sector-list-header exposure-section-header"
        style={{ marginBottom: 'var(--space-md)' }}
      >
        <div className="panel-section-title-block">
          <p className="panel-label" style={{ display: 'inline' }}>{title}</p>
          {badge ? <span style={{ marginLeft: 'var(--space-sm)' }}>{badge}</span> : null}
        </div>
        {actions ?? null}
      </div>
      {children}
    </section>
  )
}

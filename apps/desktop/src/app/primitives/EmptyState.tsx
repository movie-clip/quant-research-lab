/**
 * Empty state — render when a card has no data to show but isn't loading or in error.
 *
 * Uses the existing `.empty-state-panel.compact-empty-state` envelope from
 * styles.css. The `<p className="helper">` detail line is omitted when no
 * `detail` prop is provided.
 */

export type EmptyStateProps = {
  title: string
  detail?: string
}

export function EmptyState({ title, detail }: EmptyStateProps) {
  return (
    <div className="empty-state-panel compact-empty-state">
      <p className="empty-state-title">{title}</p>
      {detail ? <p className="helper">{detail}</p> : null}
    </div>
  )
}

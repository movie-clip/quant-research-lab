/**
 * Error state — shown when a fetch or computation failed (distinct from
 * "no data to show" which is `<EmptyState />`).
 *
 * Same envelope as EmptyState plus a tokenised left-border accent and an
 * error-colored title, so the researcher can distinguish "no data" from
 * "something went wrong".
 */

export type ErrorStateProps = {
  title?: string
  detail?: string
}

export function ErrorState({ title = 'Error', detail }: ErrorStateProps) {
  return (
    <div
      className="empty-state-panel compact-empty-state"
      style={{ borderLeft: 'var(--border-medium) solid var(--color-error-border)' }}
    >
      <p className="empty-state-title" style={{ color: 'var(--color-error)' }}>
        {title}
      </p>
      {detail ? <p className="helper">{detail}</p> : null}
    </div>
  )
}

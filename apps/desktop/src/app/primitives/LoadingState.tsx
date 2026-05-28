/**
 * Loading state — centered helper text shown while an async fetch is in flight.
 *
 * Kept deliberately minimal: a single `<p>` line. Heavier loading skeletons
 * can be a separate primitive later if needed.
 */

export type LoadingStateProps = {
  message?: string
}

export function LoadingState({ message = 'Loading…' }: LoadingStateProps) {
  return (
    <p className="helper" style={{ textAlign: 'center', padding: 'var(--space-xl) 0' }}>
      {message}
    </p>
  )
}

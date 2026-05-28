/**
 * Generic window/option selector — a row of buttons where one is "active".
 *
 * Used in:
 * - RollingCorrelationChart (numeric windows: 20 | 60 | 252)
 * - FactorAttributionCard (numeric windows: 20 | 60 | 252)
 * - IndexedReturnChart inside DriftBenchmarkPanel (string labels: '1m'|'3m'|...)
 *
 * Generic over T so both numeric and string option types work natively.
 * Active state surfaced via `aria-pressed` (a11y) + token-styled border/bg.
 */

export type WindowSelectorProps<T> = {
  options: readonly T[]
  value: T
  onChange: (next: T) => void
  /** Visible button text. Default: `String(option)`. */
  labelFn?: (opt: T) => string
  /** Per-button aria-label. Default: `${label} window`. */
  ariaLabelFn?: (opt: T) => string
}

export function WindowSelector<T>({
  options,
  value,
  onChange,
  labelFn = (o) => String(o),
  ariaLabelFn,
}: WindowSelectorProps<T>) {
  const resolvedAria = ariaLabelFn ?? ((o) => `${labelFn(o)} window`)
  return (
    <div role="group" aria-label="Window selector" style={{ display: 'flex', gap: 'var(--space-xs)' }}>
      {options.map((opt) => {
        const active = opt === value
        return (
          <button
            key={String(opt)}
            type="button"
            aria-label={resolvedAria(opt)}
            aria-pressed={active}
            onClick={() => { onChange(opt) }}
            style={{
              padding: 'var(--space-xs) var(--space-sm)',
              fontSize: 'var(--font-caption)',
              borderRadius: 'var(--radius-sm)',
              border: 'var(--border-thin) solid',
              borderColor: active ? 'var(--color-line-correlation)' : 'var(--color-border-strong)',
              backgroundColor: active ? 'var(--color-surface-overlay)' : 'transparent',
              color: active ? 'var(--color-line-correlation)' : 'var(--color-text-disabled)',
              cursor: 'pointer',
            }}
          >
            {labelFn(opt)}
          </button>
        )
      })}
    </div>
  )
}

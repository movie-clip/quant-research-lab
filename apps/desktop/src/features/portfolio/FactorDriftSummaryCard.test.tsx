import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { ExposureAnalysis } from './types'
import { FactorDriftSummaryCard } from './FactorDriftSummaryCard'

afterEach(cleanup)

// ── Fixtures ──────────────────────────────────────────────────────────────────

const REQUIRED_LOADING_KEYS = [
  'market', 'growth', 'value', 'small_cap', 'financials', 'health_care', 'energy',
  'industrials', 'rates_ief', 'rates_tlt', 'credit', 'commodities', 'alpha',
  'r_squared', 'residual_vol',
]

/** A rolling-loadings row with every required key defaulted to null, then the
 *  supplied factor values applied on top. */
function loadingRow(date: string, vals: Record<string, number | null>) {
  const base: Record<string, number | null | string> = { date }
  for (const key of REQUIRED_LOADING_KEYS) base[key] = null
  return { ...base, ...vals }
}

const FACTOR_LABELS: Record<string, string> = {
  market: 'Market',
  growth: 'Growth',
  value: 'Value',
  small_cap: 'Small Cap',
  technology: 'Technology',
  financials: 'Financials',
}

type RollingByWindow = {
  d20?: ReturnType<typeof loadingRow>[]
  d60?: ReturnType<typeof loadingRow>[]
  d252?: ReturnType<typeof loadingRow>[]
}

/** Build a minimal ExposureAnalysis carrying only what the card reads
 *  (factor_registry + statistical_factor_model). */
function makeResult(registryKeys: string[], rolling: RollingByWindow): ExposureAnalysis {
  const factor_registry = registryKeys.map((key, index) => ({
    key,
    label: FACTOR_LABELS[key] ?? key,
    category: 'style',
    us_proxy: 'SPY',
    target_exposure: null,
    primary_mapping: null,
    alternative_mappings: [],
    ucits_examples: [],
    mapping_quality: 'ok',
    default_enabled: true,
    orthogonalization_order: index,
    description: '',
  }))

  const countObs = (rows?: ReturnType<typeof loadingRow>[]) => rows?.length ?? 0

  return {
    benchmark: { symbol: 'SPY' },
    factor_methodology: 'test',
    factor_registry,
    statistical_factor_model: {
      status: 'ok',
      benchmark_symbol: 'SPY',
      windows: [
        { window_days: 20, observations: countObs(rolling.d20), start_date: null, end_date: null, status: 'ok' },
        { window_days: 60, observations: countObs(rolling.d60), start_date: null, end_date: null, status: 'ok' },
        { window_days: 252, observations: countObs(rolling.d252), start_date: null, end_date: null, status: 'ok' },
      ],
      collinearity_diagnostics: [],
      current_factor_snapshot: [],
      insufficient_history: [],
      rolling_loadings_20d: rolling.d20 ?? [],
      rolling_loadings_60d: rolling.d60 ?? [],
      rolling_loadings_252d: rolling.d252 ?? [],
    },
  } as unknown as ExposureAnalysis
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('FactorDriftSummaryCard', () => {
  it('renders ranked drift rows largest absolute mover first', () => {
    // deltas: market +0.5, growth -0.9, value +0.1 → rank growth, market, value
    const result = makeResult(['market', 'growth', 'value'], {
      d20: [
        loadingRow('2025-01-01', { market: 1.0, growth: 1.0, value: 1.0 }),
        loadingRow('2025-04-01', { market: 1.5, growth: 0.1, value: 1.1 }),
      ],
    })
    const { container } = render(<FactorDriftSummaryCard result={result} />)
    const text = container.textContent ?? ''

    expect(text.indexOf('Growth')).toBeGreaterThanOrEqual(0)
    expect(text.indexOf('Growth')).toBeLessThan(text.indexOf('Market'))
    expect(text.indexOf('Market')).toBeLessThan(text.indexOf('Value'))

    expect(text).toContain('−0.90')
    expect(text).toContain('+0.50')
    expect(text).toContain('+0.10')
  })

  it('computes delta as latest minus reference of trimmed window', () => {
    const result = makeResult(['market'], {
      d20: [
        loadingRow('2025-01-01', { market: 0.8 }),
        loadingRow('2025-04-01', { market: 1.23 }),
      ],
    })
    const { container } = render(<FactorDriftSummaryCard result={result} />)
    const text = container.textContent ?? ''

    expect(text).toContain('0.80 → 1.23')
    expect(text).toContain('+0.43')
  })

  it('excludes factors with null reference or latest loading', () => {
    // growth is null at the reference row → excluded; market is fully present.
    const result = makeResult(['market', 'growth'], {
      d20: [
        loadingRow('2025-01-01', { market: 1.0, growth: null }),
        loadingRow('2025-04-01', { market: 1.4, growth: 1.0 }),
      ],
    })
    render(<FactorDriftSummaryCard result={result} />)

    expect(screen.getByText('Market')).toBeTruthy()
    expect(screen.queryByText('Growth')).toBeNull()
  })

  it('window selector switches series and re-ranks', () => {
    const result = makeResult(['market'], {
      d20: [
        loadingRow('2025-01-01', { market: 1.0 }),
        loadingRow('2025-04-01', { market: 1.2 }),
      ],
      d252: [
        loadingRow('2024-01-01', { market: 1.0 }),
        loadingRow('2025-04-01', { market: 1.9 }),
      ],
    })
    const { container } = render(<FactorDriftSummaryCard result={result} />)
    expect(container.textContent).toContain('+0.20')

    fireEvent.click(screen.getByRole('button', { name: '252d window' }))
    expect(container.textContent).toContain('+0.90')
    expect(container.textContent).not.toContain('+0.20')
  })

  it('shows EmptyState when selected window series is empty', () => {
    const result = makeResult(['market', 'growth'], { d20: [] })
    render(<FactorDriftSummaryCard result={result} />)

    expect(screen.getByText('Not enough history for 20d factor drift.')).toBeTruthy()
    expect(screen.queryByText('Market')).toBeNull()
  })

  it('shows EmptyState when all visible factors are excluded', () => {
    // Series is non-empty (a middle row has market) but the reference/latest of
    // the trimmed window leave market null → no rankable rows (AC8).
    const result = makeResult(['market'], {
      d20: [
        loadingRow('2025-01-01', { market: null }),
        loadingRow('2025-02-01', { market: 0.5 }),
        loadingRow('2025-03-01', { market: null }),
      ],
    })
    render(<FactorDriftSummaryCard result={result} />)

    expect(screen.getByText('Not enough history for 20d factor drift.')).toBeTruthy()
  })

  it('synthetic badge tooltip text', () => {
    const result = makeResult(['market'], {
      d20: [loadingRow('2025-01-01', { market: 1.0 }), loadingRow('2025-04-01', { market: 1.2 })],
    })
    render(<FactorDriftSummaryCard result={result} />)

    const badge = screen.getByText('Synthetic')
    expect(badge).toBeTruthy()
    expect(badge.getAttribute('title')).toBe(
      'Factor loadings are reconstructed from current holdings × historical factor-proxy prices. Drift is the change in loading over the selected window.',
    )
  })

  it('direction encoded by sign and arrow, not color alone', () => {
    const result = makeResult(['market'], {
      d20: [loadingRow('2025-01-01', { market: 1.5 }), loadingRow('2025-04-01', { market: 0.6 })],
    })
    const { container } = render(<FactorDriftSummaryCard result={result} />)
    const text = container.textContent ?? ''

    // Negative drift carries a non-color signal: a down arrow + signed value.
    expect(text).toContain('▼')
    expect(text).toContain('−0.90')
  })
})

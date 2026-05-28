import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { RollingCorrelationChart } from './RollingCorrelationChart'
import type { RollingRiskPoint } from './types'

afterEach(() => { cleanup() })

function makePoint(
  date: string,
  opts: Partial<Pick<RollingRiskPoint, 'correlation_20d' | 'correlation_60d' | 'correlation_252d' | 'beta_20d' | 'beta_60d' | 'beta_252d'>> = {},
): RollingRiskPoint {
  return {
    date,
    correlation_20d: opts.correlation_20d ?? null,
    correlation_60d: opts.correlation_60d ?? null,
    correlation_252d: opts.correlation_252d ?? null,
    beta_20d: opts.beta_20d ?? null,
    beta_60d: opts.beta_60d ?? null,
    beta_252d: opts.beta_252d ?? null,
  }
}

const richSeries: RollingRiskPoint[] = [
  makePoint('2025-01-01', { correlation_60d: 0.85, beta_60d: 1.1, correlation_20d: 0.75, beta_20d: 1.0, correlation_252d: 0.90, beta_252d: 1.2 }),
  makePoint('2025-01-02', { correlation_60d: 0.87, beta_60d: 1.15, correlation_20d: 0.78, beta_20d: 1.05, correlation_252d: 0.91, beta_252d: 1.21 }),
  makePoint('2025-01-03', { correlation_60d: 0.80, beta_60d: 1.05, correlation_20d: 0.70, beta_20d: 0.98, correlation_252d: 0.89, beta_252d: 1.18 }),
]

const allNullSeries: RollingRiskPoint[] = [
  makePoint('2025-01-01'),
  makePoint('2025-01-02'),
]

describe('RollingCorrelationChart', () => {
  it('renders window selector buttons for 20d, 60d and 252d', () => {
    render(<RollingCorrelationChart rollingRisk={richSeries} />)
    expect(screen.getByRole('button', { name: /20d window/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /60d window/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /252d window/i })).toBeTruthy()
  })

  it('shows "Insufficient history" when all values for the selected window are null', () => {
    render(<RollingCorrelationChart rollingRisk={allNullSeries} />)
    // Default window is 60d; all correlation_60d/beta_60d are null → insufficient
    expect(screen.getByText(/insufficient history.*60d/i)).toBeTruthy()
  })

  it('shows "Insufficient history" when rolling_risk array is empty', () => {
    render(<RollingCorrelationChart rollingRisk={[]} />)
    expect(screen.getByText(/insufficient history/i)).toBeTruthy()
  })

  it('switches data fields when a different window is selected', () => {
    render(<RollingCorrelationChart rollingRisk={richSeries} />)
    // Click 20d — should NOT show the insufficient-history message (has 20d data)
    fireEvent.click(screen.getByRole('button', { name: /20d window/i }))
    expect(screen.queryByText(/insufficient history/i)).toBeNull()
    // Click 252d
    fireEvent.click(screen.getByRole('button', { name: /252d window/i }))
    expect(screen.queryByText(/insufficient history/i)).toBeNull()
  })

  it('shows "Insufficient history for 20d" when only 60d data is available and 20d is selected', () => {
    const only60dSeries: RollingRiskPoint[] = [
      makePoint('2025-01-01', { correlation_60d: 0.8, beta_60d: 1.1 }),
      makePoint('2025-01-02', { correlation_60d: 0.82, beta_60d: 1.12 }),
    ]
    render(<RollingCorrelationChart rollingRisk={only60dSeries} />)
    // Default 60d is fine, but switching to 20d shows insufficient
    fireEvent.click(screen.getByRole('button', { name: /20d window/i }))
    expect(screen.getByText(/insufficient history.*20d/i)).toBeTruthy()
  })
})

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { StressScenariosCard } from './StressScenariosCard'
import type { StressScenarioResult } from './types'

afterEach(() => { cleanup() })

const populated: StressScenarioResult[] = [
  { name: 'Broad Market Selloff', estimated_return_pct: -9.42, description: 'risk-off equity drawdown', status: 'ok' },
  { name: 'Rates Down Risk-On', estimated_return_pct: 3.1, description: 'duration tailwind', status: 'ok' },
  { name: 'Inflation Reacceleration', estimated_return_pct: -5.2, description: 'commodity strength', status: 'ok' },
]

const unavailable: StressScenarioResult[] = populated.map((s) => ({
  ...s,
  estimated_return_pct: null,
  status: 'unavailable',
}))

describe('StressScenariosCard', () => {
  it('renders three scenario rows when trust is synthetic', () => {
    render(<StressScenariosCard scenarios={populated} trust="synthetic" />)
    expect(screen.getByText('Broad Market Selloff')).toBeTruthy()
    expect(screen.getByText('Rates Down Risk-On')).toBeTruthy()
    expect(screen.getByText('Inflation Reacceleration')).toBeTruthy()
  })

  it('sorts rows by absolute magnitude descending', () => {
    // |pcts|: 9.42, 3.1, 5.2 → expected order: Broad Market (9.42), Inflation (5.2), Rates (3.1)
    render(<StressScenariosCard scenarios={populated} trust="synthetic" />)
    const names = screen.getAllByText(/^(Broad Market Selloff|Rates Down Risk-On|Inflation Reacceleration)$/)
      .map((el) => el.textContent)
    expect(names).toEqual(['Broad Market Selloff', 'Inflation Reacceleration', 'Rates Down Risk-On'])
  })

  it('renders a dash for null pct and sorts those rows last', () => {
    const mixed: StressScenarioResult[] = [
      { name: 'A-Missing', estimated_return_pct: null, description: '', status: 'unavailable' },
      { name: 'B-Big', estimated_return_pct: -7.0, description: '', status: 'ok' },
      { name: 'C-Small', estimated_return_pct: 1.0, description: '', status: 'ok' },
    ]
    render(<StressScenariosCard scenarios={mixed} trust="synthetic" />)
    // Dash must appear (null formatter)
    expect(screen.getByText('—')).toBeTruthy()
    // Sort order: B-Big (|-7|=7) → C-Small (|1|=1) → A-Missing (null)
    const names = screen.getAllByText(/^(A-Missing|B-Big|C-Small)$/)
      .map((el) => el.textContent)
    expect(names).toEqual(['B-Big', 'C-Small', 'A-Missing'])
  })

  it('renders the Synthetic trust badge when response trust is synthetic', () => {
    render(<StressScenariosCard scenarios={populated} trust="synthetic" />)
    expect(screen.getByText('Synthetic')).toBeTruthy()
  })

  it('renders empty-state and no scenario rows when trust is unavailable', () => {
    render(<StressScenariosCard scenarios={unavailable} trust="unavailable" />)
    expect(screen.getByText('Stress scenarios unavailable')).toBeTruthy()
    // No scenario names should be in the DOM (the body is the EmptyState)
    expect(screen.queryByText('Broad Market Selloff')).toBeNull()
    expect(screen.queryByText('Rates Down Risk-On')).toBeNull()
    // Badge reflects unavailable trust
    expect(screen.getByText('Unavailable')).toBeTruthy()
  })

  it('renders the ErrorState when an error prop is present', () => {
    render(
      <StressScenariosCard
        scenarios={[]}
        trust="synthetic"
        error={new Error('boom')}
      />,
    )
    expect(screen.getByText('Stress engine failed')).toBeTruthy()
    expect(screen.getByText('boom')).toBeTruthy()
  })
})

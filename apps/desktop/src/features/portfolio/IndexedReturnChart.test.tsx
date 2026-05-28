import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { IndexedReturnChart } from './IndexedReturnChart'
import type { DriftDailyPoint, DriftWindow } from './types'

afterEach(() => { cleanup() })

function makeWindow(label: string, startDate: string | null): DriftWindow {
  return {
    label,
    start_date: startDate,
    end_date: null,
    portfolio_return_pct: null,
    benchmark_return_pct: null,
    spread_pct: null,
    trust: 'synthetic',
    note: null,
  }
}

const baseSeries: DriftDailyPoint[] = [
  { date: '2025-01-01', portfolio_indexed: 100, benchmark_indexed: 100 },
  { date: '2025-01-02', portfolio_indexed: 102, benchmark_indexed: 101 },
  { date: '2025-01-03', portfolio_indexed: 104, benchmark_indexed: 102 },
  { date: '2025-02-01', portfolio_indexed: 110, benchmark_indexed: 105 },
  { date: '2025-03-01', portfolio_indexed: 115, benchmark_indexed: 108 },
]

const windows: DriftWindow[] = [
  makeWindow('1M', '2025-02-01'),
  makeWindow('3M', '2025-01-01'),
  makeWindow('Since Import', '2025-01-01'),
]

describe('IndexedReturnChart', () => {
  it('renders window selector buttons for each window', () => {
    render(<IndexedReturnChart series={baseSeries} windows={windows} benchmarkSymbol="SPY" />)
    expect(screen.getByRole('button', { name: '1M' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '3M' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Since Import' })).toBeTruthy()
  })

  it('shows insufficient history message when series is empty', () => {
    render(<IndexedReturnChart series={[]} windows={windows} benchmarkSymbol="SPY" />)
    expect(screen.getByText(/insufficient history/i)).toBeTruthy()
  })

  it('shows insufficient history message when all indexed values are null', () => {
    const nullSeries: DriftDailyPoint[] = [
      { date: '2025-01-01', portfolio_indexed: null, benchmark_indexed: null },
    ]
    render(<IndexedReturnChart series={nullSeries} windows={windows} benchmarkSymbol="SPY" />)
    expect(screen.getByText(/insufficient history/i)).toBeTruthy()
  })

  it('changes active window button when a window is clicked', () => {
    render(<IndexedReturnChart series={baseSeries} windows={windows} benchmarkSymbol="SPY" />)
    const btn1M = screen.getByRole('button', { name: '1M' })
    fireEvent.click(btn1M)
    expect(btn1M.className.includes('drift-chart-window-btn-active')).toBe(true)
  })

  it('renders without crashing when windows array is empty', () => {
    // No window selector should be rendered; no crash expected
    const { container } = render(<IndexedReturnChart series={baseSeries} windows={[]} benchmarkSymbol="QQQ" />)
    expect(container).toBeTruthy()
  })
})

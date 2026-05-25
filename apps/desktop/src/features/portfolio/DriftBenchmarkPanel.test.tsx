import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DriftBenchmarkPanel } from './DriftBenchmarkPanel'
import type { DriftResult } from './types'

const mockDriftResult: DriftResult = {
  benchmark_symbol: 'SPY',
  availability: 'partial',
  daily_series: [],
  windows: [
    { label: '1M', start_date: '2026-04-25', end_date: '2026-05-25', portfolio_return_pct: 2.5, benchmark_return_pct: 1.8, spread_pct: 0.7, trust: 'synthetic', note: null },
    { label: '3M', start_date: '2026-02-25', end_date: '2026-05-25', portfolio_return_pct: 8.3, benchmark_return_pct: 6.9, spread_pct: 1.4, trust: 'synthetic', note: null },
    { label: '6M', start_date: '2025-11-25', end_date: '2026-05-25', portfolio_return_pct: null, benchmark_return_pct: null, spread_pct: null, trust: 'unavailable', note: null },
    { label: '12M', start_date: '2025-05-25', end_date: '2026-05-25', portfolio_return_pct: 42.3, benchmark_return_pct: 35.1, spread_pct: 7.2, trust: 'synthetic', note: null },
    { label: 'Since Import', start_date: null, end_date: null, portfolio_return_pct: null, benchmark_return_pct: null, spread_pct: null, trust: 'unavailable', note: 'No import date available' },
  ],
}

afterEach(() => { cleanup() })

describe('DriftBenchmarkPanel', () => {
  it('renders empty state when result is null', () => {
    render(<DriftBenchmarkPanel result={null} benchmarkSymbol="SPY" onBenchmarkChange={vi.fn()} />)
    expect(screen.getByText(/import a portfolio/i)).toBeTruthy()
  })

  it('renders window labels', () => {
    render(<DriftBenchmarkPanel result={mockDriftResult} benchmarkSymbol="SPY" onBenchmarkChange={vi.fn()} />)
    expect(screen.getByText('1M')).toBeTruthy()
    expect(screen.getByText('3M')).toBeTruthy()
    expect(screen.getByText('12M')).toBeTruthy()
    expect(screen.getByText('Since Import')).toBeTruthy()
  })

  it('renders portfolio and benchmark returns', () => {
    render(<DriftBenchmarkPanel result={mockDriftResult} benchmarkSymbol="SPY" onBenchmarkChange={vi.fn()} />)
    expect(screen.getByText('+2.50%')).toBeTruthy()
    expect(screen.getByText('+1.80%')).toBeTruthy()
  })

  it('renders unavailable windows as No data', () => {
    render(<DriftBenchmarkPanel result={mockDriftResult} benchmarkSymbol="SPY" onBenchmarkChange={vi.fn()} />)
    const noDataCells = screen.getAllByText('No data')
    expect(noDataCells.length).toBeGreaterThanOrEqual(1)
  })

  it('calls onBenchmarkChange when benchmark is changed', () => {
    const onBenchmarkChange = vi.fn()
    render(<DriftBenchmarkPanel result={mockDriftResult} benchmarkSymbol="SPY" onBenchmarkChange={onBenchmarkChange} />)
    fireEvent.change(screen.getByLabelText('Benchmark'), { target: { value: 'QQQ' } })
    expect(onBenchmarkChange).toHaveBeenCalledWith('QQQ')
  })

  it('shows the Synthetic trust badge', () => {
    render(<DriftBenchmarkPanel result={mockDriftResult} benchmarkSymbol="SPY" onBenchmarkChange={vi.fn()} />)
    expect(screen.getByText('Synthetic')).toBeTruthy()
  })
})

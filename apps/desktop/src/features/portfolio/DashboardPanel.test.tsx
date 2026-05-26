import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createDiagnosticsEngineFixture,
  createExposureEngineFixture,
  createFf2026ImportedDashboardFixture,
  createIb2026ImportedDashboardFixture,
  createImportedDashboardFixture,
} from '../../test/portfolioFixtures'
import { DashboardPanel, normalizePerformanceSeries } from './DashboardPanel'
import { buildExposureFactorModel, buildImportedDashboardView, composeExposureView } from './portfolioAnalysisAdapter'

const mockAnalysis = createImportedDashboardFixture()
const mockDashboardView = buildImportedDashboardView(mockAnalysis)
const ib2026DashboardView = buildImportedDashboardView(createIb2026ImportedDashboardFixture())
const ff2026DashboardView = buildImportedDashboardView(createFf2026ImportedDashboardFixture())
const dashboardExposureView = composeExposureView(createExposureEngineFixture(), createDiagnosticsEngineFixture())
const dashboardFactorModel = buildExposureFactorModel(dashboardExposureView)

// Freeze the test clock so readiness/staleness logic in DashboardPanel
// resolves deterministically relative to the fixtures'
// `imported_at: '2026-04-10T00:00:00Z'`. Individual tests may still call
// `vi.setSystemTime(...)` to exercise stale-timestamp branches; `afterEach`
// restores real timers between tests.
beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-04-15T00:00:00Z'))
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function getSnapshotShell() {
  return screen.getByLabelText('Trusted Portfolio Snapshot')
}

describe('DashboardPanel', () => {
  it('renders the landing-only shell and keeps deeper review content absent', () => {
    render(<DashboardPanel result={mockDashboardView} exposureResult={dashboardExposureView} factorModel={dashboardFactorModel} />)

    expect(screen.getByText('Account overview').closest('article')?.className.includes('dashboard-panel')).toBe(true)
    expect(screen.getByText('Trusted Portfolio Snapshot')).toBeTruthy()
    expect(screen.getByText('Freshness And Coverage Readiness')).toBeTruthy()
    expect(screen.getAllByText('Partially ready').length).toBeGreaterThan(0)
    expect(screen.getByText(/Account ID U8516450/)).toBeTruthy()
    expect(screen.getAllByText('Benchmark used').length).toBeGreaterThan(0)
    expect(screen.queryByText('Detailed review')).toBeNull()
    expect(screen.queryByText('Review entry')).toBeNull()
    expect(screen.queryByText('Support layer')).toBeNull()
    expect(screen.queryByText('Draft/tool layer')).toBeNull()
    expect(screen.queryByText('Reserved shell space')).toBeNull()
    expect(screen.queryByText('Portfolio vs SPY path for the selected range')).toBeNull()
    expect(screen.queryByText('Workspace and allocation editor')).toBeNull()
    expect(screen.queryByText('Performance source')).toBeNull()
    expect(screen.queryByText('Saved Variants')).toBeNull()
    expect(screen.queryByRole('button', { name: /show support layer/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /show draft\/tool layer/i })).toBeNull()
  })

  it('keeps benchmark used explicit unavailable when imported truth does not supply it', () => {
    const resultWithoutBenchmark = buildImportedDashboardView({
      ...mockAnalysis,
      run_metadata: {
        ...mockAnalysis.run_metadata!,
        reproducibility: {
          ...mockAnalysis.run_metadata!.reproducibility,
          benchmark_symbol: '',
        },
      },
    })

    render(
      <DashboardPanel
        result={resultWithoutBenchmark}
        exposureResult={{
          ...dashboardExposureView,
          run_metadata: {
            ...dashboardExposureView.run_metadata!,
            reproducibility: {
              ...dashboardExposureView.run_metadata!.reproducibility,
              benchmark_symbol: 'QQQ',
            },
          },
        }}
        factorModel={{
          ...dashboardFactorModel,
          benchmark_symbol: 'IWM',
        }}
      />,
    )

    const snapshotShell = getSnapshotShell()
    expect(within(snapshotShell).getByText('Benchmark used')).toBeTruthy()
    expect(within(snapshotShell).getAllByText('Unavailable').length).toBeGreaterThan(0)
    expect(screen.queryByText('QQQ')).toBeNull()
    expect(screen.queryByText('IWM')).toBeNull()
  })

  it('stays snapshot-first for loading, error, and restore-only states', () => {
    const { rerender } = render(<DashboardPanel result={null} importing lastImportedFileNames={['IB2025.pdf']} />)

    expect(screen.getByText('Loading imported snapshot')).toBeTruthy()
    expect(screen.getAllByText('Readiness pending').length).toBeGreaterThan(0)
    expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy()

    rerender(<DashboardPanel result={null} importError="Import failed: unreadable PDF" />)
    expect(screen.getAllByText('Import failed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Readiness unavailable').length).toBeGreaterThan(0)

    rerender(<DashboardPanel result={null} lastImportedFileNames={['IB2025.pdf']} restoredSession onClearImportedSession={vi.fn()} />)
    expect(screen.getByText('No imported snapshot loaded')).toBeTruthy()
    expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy()
    expect(screen.getByText('Restored on launch')).toBeTruthy()
    expect(screen.queryByText('Detailed review')).toBeNull()
  })

  it('shows stale state indicators when the snapshot is stale', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-15T00:00:00Z'))

    render(<DashboardPanel result={mockDashboardView} exposureResult={dashboardExposureView} factorModel={dashboardFactorModel} />)

    expect(screen.getAllByText('Imported snapshot may be stale').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Refresh before confident analysis').length).toBeGreaterThan(0)
    expect(screen.getAllByText('stale').length).toBeGreaterThan(0)
    expect(screen.queryByText('Portfolio vs SPY path for the selected range')).toBeNull()
  })

  it('keeps trusted snapshot values for imported dashboards from supported brokers', () => {
    const { rerender } = render(<DashboardPanel result={ib2026DashboardView} />)

    expect(screen.getByText(/Account ID/)).toBeTruthy()
    expect(screen.getAllByText('Interactive Brokers').length).toBeGreaterThan(0)
    expect(screen.getByText('$64171.87')).toBeTruthy()
    expect(screen.queryByText('Detailed review')).toBeNull()

    rerender(<DashboardPanel result={ff2026DashboardView} />)

    expect(screen.getAllByText('Freedom24').length).toBeGreaterThan(0)
    expect(screen.getByText('$3071.00')).toBeTruthy()
    expect(screen.queryByText('Portfolio vs SPY path for the selected range')).toBeNull()
  })

  it('normalizes all-range performance from first non-zero portfolio point', () => {
    const normalized = normalizePerformanceSeries([
      { date: '2025-01-02', portfolio_value: 0, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
      { date: '2025-01-03', portfolio_value: 0, benchmark_price: 101, portfolio_return_pct: 0, benchmark_return_pct: 1 },
      { date: '2025-06-30', portfolio_value: 3139.15, benchmark_price: 110, portfolio_return_pct: 0, benchmark_return_pct: 10 },
      { date: '2026-04-10', portfolio_value: 64687.71, benchmark_price: 116, portfolio_return_pct: 871.82, benchmark_return_pct: 16.22 },
    ])

    expect(normalized[0].portfolio_index).toBeNull()
    expect(normalized[1].portfolio_index).toBeNull()
    expect(normalized[2].portfolio_index).toBe(100)
    expect(normalized[3].portfolio_index).toBeGreaterThan(100)
    expect(normalized[2].benchmark_index).toBe(100)
  })
})

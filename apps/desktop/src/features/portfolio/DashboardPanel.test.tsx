import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createDiagnosticsEngineFixture,
  createExposureEngineFixture,
  createFf2026ImportedDashboardFixture,
  createIb2026ImportedDashboardFixture,
  createImportedDashboardFixture,
} from '../../test/portfolioFixtures'
import { DashboardPanel, normalizePerformanceSeries } from './DashboardPanel'
import { buildExposureFactorModel, buildImportedDashboardView, composeExposureView } from './portfolioAnalysisAdapter'
import type { DashboardAnalysis, ImportedDashboardSource } from './types'

const mockAnalysis: ImportedDashboardSource = createImportedDashboardFixture()
const mockDashboardView: DashboardAnalysis = buildImportedDashboardView(mockAnalysis)
const ib2026DashboardView: DashboardAnalysis = buildImportedDashboardView(createIb2026ImportedDashboardFixture())
const ff2026DashboardView: DashboardAnalysis = buildImportedDashboardView(createFf2026ImportedDashboardFixture())
const dashboardExposureView = composeExposureView(createExposureEngineFixture(), createDiagnosticsEngineFixture())
const dashboardFactorModel = buildExposureFactorModel(dashboardExposureView)

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
    expect(screen.getByLabelText('Dense Insight Strip')).toBeTruthy()
    expect(screen.getByLabelText('Exposure Highlights')).toBeTruthy()
    expect(screen.getByLabelText('Concentration Highlights')).toBeTruthy()
    expect(screen.getByLabelText('Benchmark-Relative Highlights')).toBeTruthy()
    expect(screen.getByLabelText('Risk / Factor / Stress Headlines')).toBeTruthy()
    expect(screen.getByText('Next step')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Open detailed review' })).toBeTruthy()
    expect(screen.getByText(/Account ID U8516450/)).toBeTruthy()
    expect(screen.getAllByText('Benchmark used').length).toBeGreaterThan(0)
    expect(screen.getByText('Technology leads at 40%.')).toBeTruthy()
    expect(screen.getByText('Look-through coverage 100%.')).toBeTruthy()
    expect(screen.getByText('AAPL is 24% of the book.')).toBeTruthy()
    expect(screen.getByText('Top 3 60%; Top 5 60%; top sector 36%')).toBeTruthy()
    expect(screen.getByText('Mostly differentiated from SPY.')).toBeTruthy()
    expect(screen.getByText('Overlap with SPY 28%; active share 62%.')).toBeTruthy()
    expect(screen.getByText('Growth is the strongest modeled tilt at +0.31 loading.')).toBeTruthy()
    expect(screen.queryByText('Detailed review')).toBeNull()
    expect(screen.queryByText('Review entry')).toBeNull()
    expect(screen.queryByText('Support layer')).toBeNull()
    expect(screen.queryByText('Draft/tool layer')).toBeNull()
    expect(screen.queryByText('Reserved shell space')).toBeNull()
    expect(screen.queryByText('Portfolio vs SPY path for the selected range')).toBeNull()
    expect(screen.queryByText('Rolling Factor Analysis')).toBeNull()
    expect(screen.queryByText('Workspace and allocation editor')).toBeNull()
    expect(screen.queryByText('Performance source')).toBeNull()
    expect(screen.queryByText('Saved Variants')).toBeNull()
    expect(screen.queryByRole('button', { name: /show support layer/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /show draft\/tool layer/i })).toBeNull()
  })

  it('uses the CTA only as a handoff trigger and keeps the shell unchanged', () => {
    const onOpenDetailedReview = vi.fn()

    render(<DashboardPanel result={mockDashboardView} onOpenDetailedReview={onOpenDetailedReview} />)

    fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))

    expect(onOpenDetailedReview).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Trusted Portfolio Snapshot')).toBeTruthy()
    expect(screen.getByText('Freshness And Coverage Readiness')).toBeTruthy()
    expect(screen.queryByText('Detailed review')).toBeNull()
    expect(screen.queryByText('Support layer')).toBeNull()
    expect(screen.queryByText('Draft/tool layer')).toBeNull()
  })

  it('fails closed when detailed review is ineligible without unlocking inline content', () => {
    render(
      <DashboardPanel
        result={mockDashboardView}
        exposureResult={dashboardExposureView}
        factorModel={dashboardFactorModel}
        detailEligible={false}
        activeNodeKind="variant"
      />,
    )

    expect(screen.getByText('Imported snapshot not active here')).toBeTruthy()
    expect(screen.getByText('Trusted orientation paused')).toBeTruthy()
    expect(screen.getByText('Detailed review unavailable here')).toBeTruthy()
    expect(screen.getAllByText('partial').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Open detailed review' })).toBeNull()
    expect(screen.queryByText('Detailed review')).toBeNull()
    expect(screen.queryByText('Support layer')).toBeNull()
    expect(screen.queryByText('Draft/tool layer')).toBeNull()
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
    expect(screen.getByText('Readiness pending')).toBeTruthy()
    expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Open detailed review' })).toBeNull()

    rerender(<DashboardPanel result={null} importError="Import failed: unreadable PDF" />)
    expect(screen.getAllByText('Import failed').length).toBeGreaterThan(0)
    expect(screen.getByText('Readiness unavailable')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Open detailed review' })).toBeNull()

    rerender(<DashboardPanel result={null} lastImportedFileNames={['IB2025.pdf']} restoredSession onClearImportedSession={vi.fn()} />)
    expect(screen.getByText('No imported snapshot loaded')).toBeTruthy()
    expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy()
    expect(screen.getByText('Restored on launch')).toBeTruthy()
    expect(screen.queryByText('Detailed review')).toBeNull()
  })

  it('shows stale and partial states without surfacing deeper analytics', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-15T00:00:00Z'))

    const { rerender } = render(<DashboardPanel result={mockDashboardView} exposureResult={dashboardExposureView} factorModel={dashboardFactorModel} />)

    expect(screen.getAllByText('Imported snapshot may be stale').length).toBeGreaterThan(0)
    expect(screen.getByText('Refresh before confident analysis')).toBeTruthy()
    expect(screen.getAllByText('stale').length).toBeGreaterThan(0)
    expect(screen.queryByText('Portfolio vs SPY path for the selected range')).toBeNull()

    rerender(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          snapshot: {
            ...mockAnalysis.snapshot,
            statement: {
              ...mockAnalysis.snapshot.statement,
              account_id: null,
              statement_period: null,
            },
            statements: [],
            statement_totals: {
              stock_total: null,
              cash_total: null,
              dividends_total: null,
              withholding_tax_total: null,
              interest_total: null,
              other_fees_total: null,
              deposits_total: null,
              starting_nav: null,
              ending_nav: null,
              fx_rates: {},
            },
          },
          overview: {
            ...mockAnalysis.overview,
            top_positions: [],
            sector_allocation: [],
            cash_by_currency: {},
          },
          run_metadata: {
            ...mockDashboardView.run_metadata!,
            reproducibility: {
              ...mockDashboardView.run_metadata!.reproducibility,
              snapshot_as_of_date: null,
            },
          },
        })}
        exposureResult={{
          ...dashboardExposureView,
          lookthrough_sector_exposure: [],
          exposure_availability: {
            ...dashboardExposureView.exposure_availability!,
            lookthrough_status: 'unavailable',
          },
        }}
        factorModel={dashboardFactorModel}
      />,
    )

    expect(screen.getAllByText('Imported snapshot has partial anchors').length).toBeGreaterThan(0)
    expect(screen.getByText('Partially ready')).toBeTruthy()
    expect(screen.getAllByText('Exposure highlights stay unavailable until explicit sector or look-through fields are present.').length).toBeGreaterThan(0)
    expect(screen.queryByText('Rolling Factor Analysis')).toBeNull()
    expect(screen.queryByText('Workspace and allocation editor')).toBeNull()
  })

  it('labels partial look-through coverage inline and degrades benchmark and diagnostics headlines when inputs degrade', () => {
    const partialExposure = composeExposureView(
      {
        ...createExposureEngineFixture(),
        lookthrough: {
          ...createExposureEngineFixture().lookthrough,
          coverage_ratio: 0.74,
        },
        availability: {
          ...createExposureEngineFixture().availability,
          lookthrough_status: 'partial',
          benchmark_overlap_status: 'partial',
        },
        run_metadata: {
          ...createExposureEngineFixture().run_metadata,
          source_status: {
            ...createExposureEngineFixture().run_metadata.source_status,
            benchmark_holdings: 'verified',
          },
        },
      },
      {
        ...createDiagnosticsEngineFixture(),
        run_metadata: {
          ...createDiagnosticsEngineFixture().run_metadata,
          section_trust: {
            benchmark_relative_path: 'degraded_unverified_return_basis',
            factor_model_path: 'degraded_unverified_return_basis',
            risk_contribution_path: 'degraded_unverified_return_basis',
          },
        },
      },
    )

    render(<DashboardPanel result={mockDashboardView} exposureResult={partialExposure} factorModel={dashboardFactorModel} />)

    expect(screen.getByText('Look-through coverage 74% (partial).')).toBeTruthy()
    expect(screen.getByText('The signal set is useful for orientation, but the current diagnostics path remains degraded.')).toBeTruthy()
    expect(screen.getAllByText('partial').length).toBeGreaterThan(0)
    expect(screen.getAllByText('degraded').length).toBeGreaterThan(0)
  })

  it('keeps concentration highlights scoped to existing concentration facts only', () => {
    render(<DashboardPanel result={mockDashboardView} exposureResult={dashboardExposureView} factorModel={dashboardFactorModel} />)

    const concentrationModule = screen.getByLabelText('Concentration Highlights')
    expect(within(concentrationModule).getByText('AAPL is 24% of the book.')).toBeTruthy()
    expect(within(concentrationModule).getByText('Top 3 60%; Top 5 60%; top sector 36%')).toBeTruthy()
    expect(within(concentrationModule).queryByText('Single-name concentration is elevated')).toBeNull()
    expect(within(concentrationModule).queryByText('Diversification still looks narrow')).toBeNull()
  })

  it('fails closed when benchmark support or diagnostics headlines are unavailable', () => {
    const limitedExposure = composeExposureView(
      {
        ...createExposureEngineFixture(),
        market_overlap: {
          ...createExposureEngineFixture().market_overlap,
          overlap_weight: null,
          active_share: null,
        },
        availability: {
          ...createExposureEngineFixture().availability,
          benchmark_overlap_status: 'unavailable',
        },
        run_metadata: {
          ...createExposureEngineFixture().run_metadata,
          source_status: {
            ...createExposureEngineFixture().run_metadata.source_status,
            benchmark_holdings: 'unavailable',
          },
        },
      },
      {
        ...createDiagnosticsEngineFixture(),
        availability: {
          ...createDiagnosticsEngineFixture().availability,
          status: 'unavailable',
        },
        run_metadata: {
          ...createDiagnosticsEngineFixture().run_metadata,
          section_trust: {
            benchmark_relative_path: 'unavailable',
            factor_model_path: 'unavailable',
            risk_contribution_path: 'unavailable',
          },
        },
        stress_scenarios: [],
      },
    )

    render(<DashboardPanel result={mockDashboardView} exposureResult={limitedExposure} factorModel={dashboardFactorModel} />)

    expect(screen.getAllByText('Benchmark-relative support is unavailable on the current imported-analysis path.').length).toBeGreaterThan(0)
    expect(screen.getByText('Imported diagnostics are still too limited for a defensible headline set.')).toBeTruthy()
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
    expect(screen.getAllByText('unavailable').length).toBeGreaterThan(0)
  })

  it('treats missing nested diagnostics trust fields as unavailable', () => {
    const malformedExposure = {
      ...dashboardExposureView,
      diagnostics_run_metadata: {},
      availability: {
        ...dashboardExposureView.availability,
        status: 'ok',
      },
      exposure_availability: {
        ...dashboardExposureView.exposure_availability,
        benchmark_overlap_status: 'ok',
      },
    } as unknown as typeof dashboardExposureView

    const resultWithoutBenchmarkTrust = {
      ...mockDashboardView,
      run_metadata: {
        ...mockDashboardView.run_metadata!,
        section_trust: undefined,
      },
    } as unknown as DashboardAnalysis

    render(<DashboardPanel result={resultWithoutBenchmarkTrust} exposureResult={malformedExposure} factorModel={dashboardFactorModel} />)

    expect(screen.getAllByText('Benchmark-relative support is unavailable on the current imported-analysis path.').length).toBeGreaterThan(0)
    expect(screen.getByText('Imported diagnostics are still too limited for a defensible headline set.')).toBeTruthy()
    expect(screen.getByText('Factor headline unavailable.')).toBeTruthy()
    expect(screen.getAllByText('unavailable').length).toBeGreaterThan(0)
  })

  it('treats missing factor-model subtrees as no factor headline available', () => {
    const malformedExposure = {
      ...dashboardExposureView,
      statistical_factor_model: undefined,
      factor_exposures: undefined,
      diagnostics_run_metadata: {
        ...dashboardExposureView.diagnostics_run_metadata,
        section_trust: {
          factor_model_path: 'verified_adjusted_close',
        },
      },
    } as unknown as typeof dashboardExposureView

    const malformedFactorModel = {
      ...dashboardFactorModel,
      statistical_factor_model: {
        current_factor_snapshot: undefined,
        status: undefined,
      },
    } as unknown as typeof dashboardFactorModel

    render(<DashboardPanel result={mockDashboardView} exposureResult={malformedExposure} factorModel={malformedFactorModel} />)

    expect(screen.getByText('Factor headline unavailable.')).toBeTruthy()
    expect(screen.queryByText(/strongest modeled tilt/i)).toBeNull()
  })

  it('keeps trusted snapshot values for imported dashboards from supported brokers', () => {
    const { rerender } = render(<DashboardPanel result={ib2026DashboardView} />)

    expect(screen.getByText(/Account ID/)).toBeTruthy()
    expect(screen.getAllByText('Interactive Brokers').length).toBeGreaterThan(0)
    expect(screen.getByText('$62584.21')).toBeTruthy()
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

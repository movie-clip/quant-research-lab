import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture } from '../../test/portfolioFixtures'
import { ExposurePanel, sortTooltipPayloadRows } from './ExposurePanel'
import { composeExposureView } from './portfolioAnalysisAdapter'
import type { DiagnosticsEngineResponse, ExposureAnalysis, ExposureEngineResponse, ExposureFactorModelResponse } from './types'

const mockExposureEngineResult: ExposureEngineResponse = createExposureEngineFixture()
const mockDiagnosticsResult: DiagnosticsEngineResponse = createDiagnosticsEngineFixture()

const mockFactorModel: ExposureFactorModelResponse = {
  benchmark_symbol: 'SPY',
  methodology: 'Orthogonalized rolling ridge factor model using US ETF proxies for market, style, sector, and macro exposures; UCITS symbols are shown separately as EU execution examples.',
  factor_registry: [
    ...mockDiagnosticsResult.factor_registry,
    { key: 'value', label: 'Value', category: 'style', us_proxy: 'IVE', target_exposure: 'US value', primary_mapping: null, alternative_mappings: [], ucits_examples: ['IWVL'], mapping_quality: 'medium-high', default_enabled: true, orthogonalization_order: 3, description: 'Value tilt.' },
    { key: 'small_cap', label: 'Small Cap', category: 'style', us_proxy: 'IWM', target_exposure: 'US small cap', primary_mapping: null, alternative_mappings: [], ucits_examples: ['IUSN'], mapping_quality: 'medium-high', default_enabled: true, orthogonalization_order: 4, description: 'Small-cap tilt.' },
    { key: 'technology', label: 'Technology', category: 'sector', us_proxy: 'XLK', target_exposure: 'US technology', primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', default_enabled: true, orthogonalization_order: 5, description: 'Technology sector.' },
    { key: 'financials', label: 'Financials', category: 'sector', us_proxy: 'XLF', target_exposure: 'US financials', primary_mapping: null, alternative_mappings: [], ucits_examples: ['IUFS'], mapping_quality: 'medium-high', default_enabled: true, orthogonalization_order: 6, description: 'Financial sector.' },
    { key: 'health_care', label: 'Health Care', category: 'sector', us_proxy: 'XLV', target_exposure: 'US health care', primary_mapping: null, alternative_mappings: [], ucits_examples: ['IUHC'], mapping_quality: 'medium-high', default_enabled: true, orthogonalization_order: 7, description: 'Health care sector.' },
    { key: 'energy', label: 'Energy', category: 'sector', us_proxy: 'XLE', target_exposure: 'US energy', primary_mapping: null, alternative_mappings: [], ucits_examples: ['IUES'], mapping_quality: 'medium', default_enabled: false, orthogonalization_order: 8, description: 'Energy sector.' },
    { key: 'industrials', label: 'Industrials', category: 'sector', us_proxy: 'XLI', target_exposure: 'US industrials', primary_mapping: null, alternative_mappings: [], ucits_examples: ['EXH1'], mapping_quality: 'medium', default_enabled: false, orthogonalization_order: 9, description: 'Industrials sector.' },
    { key: 'rates_ief', label: '1-3Y Rates', category: 'macro', us_proxy: 'IEF', target_exposure: 'Intermediate rates', primary_mapping: null, alternative_mappings: [], ucits_examples: ['VDST'], mapping_quality: 'medium-high', default_enabled: false, orthogonalization_order: 10, description: 'Intermediate duration rates.' },
    { key: 'rates_tlt', label: 'Long Rates', category: 'macro', us_proxy: 'TLT', target_exposure: 'Long rates', primary_mapping: null, alternative_mappings: [], ucits_examples: ['IDTL'], mapping_quality: 'medium', default_enabled: false, orthogonalization_order: 11, description: 'Long duration rates.' },
    { key: 'credit', label: 'Credit', category: 'macro', us_proxy: 'LQD', target_exposure: 'Investment grade credit', primary_mapping: null, alternative_mappings: [], ucits_examples: ['LQDE'], mapping_quality: 'medium', default_enabled: false, orthogonalization_order: 12, description: 'Credit spread risk.' },
    { key: 'commodities', label: 'Commodities', category: 'macro', us_proxy: 'DBC', target_exposure: 'Broad commodities', primary_mapping: null, alternative_mappings: [], ucits_examples: ['ICOM'], mapping_quality: 'medium', default_enabled: false, orthogonalization_order: 13, description: 'Commodities basket.' },
  ],
  statistical_factor_model: mockDiagnosticsResult.statistical_factor_model,
}

const mockExposureView: ExposureAnalysis = composeExposureView(mockExposureEngineResult, mockDiagnosticsResult)

afterEach(() => {
  cleanup()
})

describe('ExposurePanel', () => {
  it('sorts rolling factor tooltip rows by highest visible value first', () => {
    const rows = sortTooltipPayloadRows(
      [
        { dataKey: 'market', value: 1.08 },
        { dataKey: 'technology', value: 0.22 },
        { dataKey: 'growth', value: 0.31 },
      ],
      { market: 0, growth: 1, technology: 4 },
    )

    expect(rows.map((row) => row.dataKey)).toEqual(['market', 'growth', 'technology'])
  })

  it('breaks equal tooltip values with chart line order', () => {
    const rows = sortTooltipPayloadRows(
      [
        { dataKey: 'technology', value: 0.31 },
        { dataKey: 'growth', value: 0.31 },
        { dataKey: 'market', value: 1.08 },
      ],
      { market: 0, growth: 1, technology: 4 },
    )

    expect(rows.map((row) => row.dataKey)).toEqual(['market', 'growth', 'technology'])
  })

  it('renders volatility regime metrics and n/a values', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getByText('Volatility')).toBeTruthy()
    expect(screen.getByText('Drawdown')).toBeTruthy()
    expect(screen.getByText('Benchmark Sensitivity')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: '20d' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: '60d' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: '252d' }).length).toBeGreaterThan(0)
    expect(screen.getByText('Volatility & Regime')).toBeTruthy()
    expect(screen.getByText(/Historical volatility and regime diagnostics from persisted portfolio history/)).toBeTruthy()
    expect(screen.getAllByText('18.40%').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Min /).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Max /).length).toBeGreaterThan(0)
    expect(screen.getAllByText('n/a').length).toBeGreaterThan(0)
    expect(screen.getAllByText('normal').length).toBeGreaterThan(0)
  })

  it('renders factor mapping tables and lets users switch windows', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getByText('Current Factor Snapshot')).toBeTruthy()
    expect(screen.getByText('EU Execution Mapping')).toBeTruthy()
    expect(screen.getByText('Current Snapshot Loading')).toBeTruthy()
    expect(screen.getByText('Historical 60d Loading')).toBeTruthy()
    expect(screen.getAllByText('0.31').length).toBeGreaterThan(0)
    fireEvent.click(screen.getAllByRole('button', { name: '20d' })[1])
    expect(screen.getByText('Historical 20d Loading')).toBeTruthy()
    expect(screen.getAllByText('0.35').length).toBeGreaterThan(0)
  })

  it('renders empty state without analysis', () => {
    render(<ExposurePanel result={null} factorModel={null} />)

    expect(screen.getAllByText('Core exposure and factor model').length).toBeGreaterThan(0)
  })

  it('renders snapshot selector options when provided', () => {
    const onSnapshotSelect = vi.fn()

    render(
      <ExposurePanel
        result={mockExposureView}
        factorModel={mockFactorModel}
        snapshotOptions={[{ id: 'draft', label: 'Working Draft' }, { id: 'node-1', label: 'Base Import' }]}
        selectedSnapshotId="draft"
        onSnapshotSelect={onSnapshotSelect}
      />,
    )

    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-1' } })
    expect(onSnapshotSelect).toHaveBeenCalledWith('node-1')
  })

  it('renders current-state overlap and look-through sections', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getByText('Broad Market Risk')).toBeTruthy()
    expect(screen.getByText('Current-State Overlap')).toBeTruthy()
    expect(screen.getByText('Historical Benchmark Risk')).toBeTruthy()
    expect(screen.getByText(/Historical benchmark-relative diagnostics path for sensitivity, active risk, realized volatility, and current regime/)).toBeTruthy()
    expect(screen.getByText(/Historical broad-market sensitivity aligned with the drawdown horizon/)).toBeTruthy()
    expect(screen.getByText('Actual Exposure')).toBeTruthy()
    expect(screen.getByText('Look-Through Sectors')).toBeTruthy()
    expect(screen.getByText('AAPL')).toBeTruthy()
    expect(screen.getByText('62.00%')).toBeTruthy()
    expect(screen.getByText(/Constituent Coverage 100.00%/)).toBeTruthy()
  })

  it('renders stress scenarios and factor exposure summaries', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getByText('Stress Scenarios')).toBeTruthy()
    expect(screen.getByText('Factor Tilts')).toBeTruthy()
    expect(screen.getByText('Broad Market Selloff')).toBeTruthy()
    expect(screen.getAllByText('SPY Overlap').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Growth Tilt').length).toBeGreaterThan(0)
  })

  it('renders reliability and collinearity diagnostics', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getByText('Model Confidence')).toBeTruthy()
    expect(screen.getByText(/Historical rolling-factor diagnostics across the selected window/)).toBeTruthy()
    expect(screen.getByText('Current Snapshot Loading')).toBeTruthy()
    expect(screen.getByText('Collinearity Warning')).toBeTruthy()
    expect(screen.getAllByText('No major collinearity warnings').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No high-collinearity pairs detected.').length).toBeGreaterThan(0)
  })

  it('renders statistical snapshot values from imported diagnostics', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getAllByText('1.08').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.66').length).toBeGreaterThan(0)
  })

  it('falls back gracefully when factor model is missing', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={null} />)

    expect(screen.getByText('Current Factor Snapshot')).toBeTruthy()
  })

  it('renders imported benchmark label when available', () => {
    render(<ExposurePanel result={{ ...mockExposureView, benchmark: { symbol: 'SPY', start_price: 100, end_price: 105, return_pct: 5 } }} factorModel={mockFactorModel} />)

    expect(screen.getAllByText('SPY').length).toBeGreaterThan(0)
  })

  it('explains when historical diagnostics are unavailable but current exposure still exists', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          availability: {
            historical_sections_available: false,
            history_context_required: true,
            note: 'Historical diagnostics are unavailable from snapshot-only input.',
          },
        }}
        factorModel={mockFactorModel}
      />,
    )

    expect(screen.getByText('Current exposure is available, but historical diagnostics are unavailable for this snapshot.')).toBeTruthy()
    expect(screen.getByText('Actual Exposure')).toBeTruthy()
    expect(screen.getByText(/Historical broad-market beta versus SPY\. Currently unavailable because historical diagnostics are unavailable for this snapshot\./)).toBeTruthy()
    expect(screen.getByText(/Historical benchmark-relative diagnostics path for sensitivity, active risk, realized volatility, and current regime/)).toBeTruthy()
  })

  it('explains partial look-through and unavailable benchmark overlap states', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          lookthrough: {
            ...mockExposureView.lookthrough,
            coverage_ratio: 0.1,
          },
          exposure_availability: {
            lookthrough_status: 'partial',
            lookthrough_confidence: 'medium',
            benchmark_overlap_status: 'unavailable',
            benchmark_overlap_confidence: 'low',
            historical_diagnostics_confidence: 'high',
            note: 'Look-through exposure is partial because some holdings could not be resolved, and benchmark overlap is unavailable because benchmark composition could not be loaded.',
          },
        }}
        factorModel={mockFactorModel}
      />,
    )

    expect(screen.getByText('Look-through confidence is medium; benchmark overlap confidence is low; historical diagnostics confidence is high.')).toBeTruthy()
    expect(screen.getByText(/benchmark composition could not be loaded/i)).toBeTruthy()
    expect(screen.getByText(/partial ETF resolution/i)).toBeTruthy()
    expect(screen.getByText(/Current-state overlap is shown separately from historical benchmark-risk diagnostics/)).toBeTruthy()
    expect(screen.getByText(/Constituent Coverage 10.00%/)).toBeTruthy()
    expect(screen.getAllByText('n/a').length).toBeGreaterThan(0)
    expect(screen.getByText(/SPY constituents when benchmark holdings are available\. Currently unavailable because benchmark holdings could not be loaded\./)).toBeTruthy()
  })

  it('keeps scenario preview sections hidden when absent', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.queryByText('Scenario Preview')).toBeNull()
  })

  it('renders scenario preview when provided', () => {
    render(
      <ExposurePanel
        result={{
          ...mockExposureView,
          scenario_preview: {
            mode: 'size_only',
            methodology: 'm',
            base_capital: 50000,
            gross_exposure: 52000,
            net_capital: 50000,
            leverage_ratio: 1.04,
            scenario_aware_sections: ['exposure'],
            historical_baseline_sections: ['diagnostics'],
            sector_drifts: [],
            position_drifts: [],
            factor_drifts: [],
          },
        }}
        factorModel={mockFactorModel}
      />,
    )

    expect(screen.getByText('Scenario Preview')).toBeTruthy()
    expect(screen.getByText(/Scenario-only current-state approximation/)).toBeTruthy()
    expect(screen.getByText(/historical sections remain baseline and are not recomputed from scenario trades/i)).toBeTruthy()
    expect(screen.getByText(/Scenario edits do not rerun these rolling historical loadings/)).toBeTruthy()
    expect(screen.getByText(/current snapshot values in this table are scenario-aware, while rolling-window values stay baseline historical/i)).toBeTruthy()
    expect(screen.getByText(/Scenario edits do not rerun this historical regime path/)).toBeTruthy()
  })

  it('renders insufficient history rows when present', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    fireEvent.click(screen.getAllByRole('button', { name: '252d' })[1])

    expect(screen.getByText('Not enough history for 252d rolling factor loadings.')).toBeTruthy()
    expect(screen.getByText(/Available observations: 60/)).toBeTruthy()
  })

  it('renders factor registry categories and UCITS ideas', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getByText('Factor Registry')).toBeTruthy()
    expect(screen.getAllByText('Market').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Style').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/CSPX/).length).toBeGreaterThan(0)
  })

  it('renders imported holdings metadata in current-state sections', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getAllByText('Technology').length).toBeGreaterThan(0)
    expect(screen.getByText('Health Care')).toBeTruthy()
  })
})

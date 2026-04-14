import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createImportedExposureFixture } from '../../test/portfolioFixtures'
import { ExposurePanel, sortTooltipPayloadRows } from './ExposurePanel'
import { composeExposureView } from './portfolioAnalysisAdapter'
import type { DiagnosticsEngineResponse, ExposureAnalysis, ExposureEngineResponse, ExposureFactorModelResponse, ImportedDiagnosticsSource, ImportedExposureFactorModelSource, ImportedExposureSource } from './types'

const mockAnalysis: ImportedExposureSource & ImportedDiagnosticsSource & ImportedExposureFactorModelSource = createImportedExposureFixture()

const mockFactorModel: ExposureFactorModelResponse = {
  benchmark_symbol: 'SPY',
  methodology: 'Orthogonalized rolling ridge factor model using US ETF proxies for market, style, sector, and macro exposures; UCITS symbols are shown separately as EU execution examples.',
  factor_registry: [
    ...mockAnalysis.factor_registry,
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
  statistical_factor_model: mockAnalysis.statistical_factor_model,
}

const mockExposureView: ExposureAnalysis = composeExposureView(
  {
    snapshot: mockAnalysis.snapshot,
    overview: mockAnalysis.overview,
    lookthrough: mockAnalysis.lookthrough,
    lookthrough_sector_exposure: mockAnalysis.lookthrough_sector_exposure,
    market_overlap: mockAnalysis.market_overlap,
  } satisfies ExposureEngineResponse,
  {
    snapshot: mockAnalysis.snapshot,
    risk_summary: mockAnalysis.risk_summary,
    rolling_risk: mockAnalysis.rolling_risk,
    relative_risk: mockAnalysis.relative_risk,
    volatility_regime: mockAnalysis.volatility_regime,
    factor_exposures: mockAnalysis.factor_exposures,
    factor_shift_diagnostics: mockAnalysis.factor_shift_diagnostics,
    risk_contribution_breakdown: mockAnalysis.risk_contribution_breakdown,
    model_reliability: mockAnalysis.model_reliability,
    factor_registry: mockAnalysis.factor_registry,
    factor_methodology: mockAnalysis.factor_methodology,
    statistical_factor_model: mockAnalysis.statistical_factor_model,
    stress_scenarios: mockAnalysis.stress_scenarios,
    availability: {
      historical_sections_available: true,
      history_context_required: true,
      note: null,
    },
  } satisfies DiagnosticsEngineResponse,
)

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
    expect(screen.getByText('Current Loading')).toBeTruthy()
    expect(screen.getByText('60d Loading')).toBeTruthy()
    expect(screen.getAllByText('0.31').length).toBeGreaterThan(0)
    fireEvent.click(screen.getAllByRole('button', { name: '20d' })[1])
    expect(screen.getByText('20d Loading')).toBeTruthy()
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
    expect(screen.getByText('Actual Exposure')).toBeTruthy()
    expect(screen.getByText('Look-Through Sectors')).toBeTruthy()
    expect(screen.getByText('AAPL')).toBeTruthy()
    expect(screen.getByText('62.00%')).toBeTruthy()
  })

  it('renders stress scenarios and factor exposure summaries', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getByText('Stress Scenarios')).toBeTruthy()
    expect(screen.getByText('Factor Tilts')).toBeTruthy()
    expect(screen.getByText('Broad Market Selloff')).toBeTruthy()
    expect(screen.getAllByText('Growth Tilt').length).toBeGreaterThan(0)
  })

  it('renders reliability and collinearity diagnostics', () => {
    render(<ExposurePanel result={mockExposureView} factorModel={mockFactorModel} />)

    expect(screen.getByText('Model Confidence')).toBeTruthy()
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

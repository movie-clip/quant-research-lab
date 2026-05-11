import { useState } from 'react'
import type { GenericRankingRequest, IndexId, ScoreConfig, UniverseKind } from './types'
import { SCORE_CONFIG_PRESETS, SCORE_CONFIG_PRESET_LABELS } from './scoreConfigPresets'

const INDEX_LABELS: Record<IndexId, string> = {
  sp500: 'S&P 500 (FMP live)',
  russell1000: 'Russell 1000 (static snapshot)',
}

type GenericRankingRequestFormProps = {
  onSubmit: (request: GenericRankingRequest) => void
  loading: boolean
}

export function GenericRankingRequestForm({ onSubmit, loading }: GenericRankingRequestFormProps) {
  const [universeKind, setUniverseKind] = useState<UniverseKind>('custom_list')
  const [explicitSymbols, setExplicitSymbols] = useState('')
  const [universeId, setUniverseId] = useState('')
  const [minMarketCapUsd, setMinMarketCapUsd] = useState('')
  const [minAdvUsd, setMinAdvUsd] = useState('')
  const [sectorInclude, setSectorInclude] = useState('')
  const [sectorExclude, setSectorExclude] = useState('')
  const [indexId, setIndexId] = useState<IndexId>('sp500')
  const [selectedPresetId, setSelectedPresetId] = useState(SCORE_CONFIG_PRESETS[0]?.score_config_id ?? '')
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [lookbackMonths, setLookbackMonths] = useState('6')
  const [validationError, setValidationError] = useState<string | null>(null)

  const selectedPreset: ScoreConfig | undefined = SCORE_CONFIG_PRESETS.find(
    (p) => p.score_config_id === selectedPresetId,
  ) ?? SCORE_CONFIG_PRESETS[0]

  function validate(): string | null {
    const symbolsNeeded = universeKind === 'custom_list' || universeKind === 'etf_peer_group'
    if (symbolsNeeded) {
      const parsed = explicitSymbols.split(',').map((s) => s.trim()).filter(Boolean)
      if (!parsed.length) {
        return 'At least one symbol is required for this universe kind.'
      }
    }
    if (!benchmarkSymbol.trim()) {
      return 'Benchmark symbol is required.'
    }
    const months = Number(lookbackMonths)
    if (!Number.isFinite(months) || months < 1) {
      return 'Lookback months must be a positive integer.'
    }
    if (!selectedPreset) {
      return 'A score config preset must be selected.'
    }
    return null
  }

  function handleSubmit() {
    const error = validate()
    if (error) {
      setValidationError(error)
      return
    }
    setValidationError(null)

    if (!selectedPreset) return

    const parsedSymbols =
      universeKind === 'custom_list' || universeKind === 'etf_peer_group'
        ? explicitSymbols.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean)
        : []

    const resolvedUniverseId = universeId.trim() || `${universeKind}_${Date.now()}`

    const request: GenericRankingRequest = {
      universe_spec: {
        universe_id: resolvedUniverseId,
        universe_kind: universeKind,
        explicit_symbols: parsedSymbols,
        min_market_cap_usd: minMarketCapUsd ? Number(minMarketCapUsd) : null,
        min_adv_usd: minAdvUsd ? Number(minAdvUsd) : null,
        price_floor_usd: null,
        allowed_exchanges: [],
        sector_include: sectorInclude ? sectorInclude.split(',').map((s) => s.trim()).filter(Boolean) : [],
        sector_exclude: sectorExclude ? sectorExclude.split(',').map((s) => s.trim()).filter(Boolean) : [],
        country_iso2: [],
        exclude_etf: false,
        exclude_adr: false,
        index_id: universeKind === 'index_constituent' ? indexId : null,
      },
      score_config: selectedPreset,
      benchmark_symbol: benchmarkSymbol.trim().toUpperCase(),
      lookback_months: Number(lookbackMonths),
      prefer_live_data: true,
    }

    onSubmit(request)
  }

  const needsExplicitSymbols = universeKind === 'custom_list' || universeKind === 'etf_peer_group'
  const needsScreenFilters = universeKind === 'broad_equity_screen' || universeKind === 'sector_screen'
  const needsIndexSelector = universeKind === 'index_constituent'

  return (
    <div className="backtest-builder strategy-lab-builder">
      <div className="split-grid compact-split-grid strategy-lab-config-grid">
        <div className="field-group">
          <span className="field-label">Universe Kind</span>
          <div className="radio-group">
            {(['custom_list', 'etf_peer_group', 'broad_equity_screen', 'sector_screen', 'index_constituent'] as UniverseKind[]).map((kind) => (
              <label key={kind} className="radio-option">
                <input
                  type="radio"
                  name="universe_kind"
                  value={kind}
                  checked={universeKind === kind}
                  onChange={() => { setUniverseKind(kind); setValidationError(null) }}
                />
                {' '}
                {kind.replace(/_/g, ' ')}
              </label>
            ))}
          </div>
        </div>

        {needsExplicitSymbols ? (
          <label className="field-group">
            <span className="field-label">Symbols (comma-separated)</span>
            <textarea
              className="path-input"
              rows={3}
              value={explicitSymbols}
              onChange={(e) => { setExplicitSymbols(e.target.value); setValidationError(null) }}
              placeholder="e.g. AAPL, MSFT, GOOGL"
            />
          </label>
        ) : null}

        {needsScreenFilters ? (
          <>
            <label className="field-group">
              <span className="field-label">Min Market Cap (USD)</span>
              <input
                className="path-input"
                type="number"
                value={minMarketCapUsd}
                onChange={(e) => setMinMarketCapUsd(e.target.value)}
                placeholder="e.g. 1000000000"
              />
            </label>
            <label className="field-group">
              <span className="field-label">Min ADV (USD)</span>
              <input
                className="path-input"
                type="number"
                value={minAdvUsd}
                onChange={(e) => setMinAdvUsd(e.target.value)}
                placeholder="e.g. 5000000"
              />
            </label>
            <label className="field-group">
              <span className="field-label">Sectors to Include (comma-separated)</span>
              <input
                className="path-input"
                value={sectorInclude}
                onChange={(e) => setSectorInclude(e.target.value)}
                placeholder="e.g. Technology, Health Care"
              />
            </label>
            <label className="field-group">
              <span className="field-label">Sectors to Exclude (comma-separated)</span>
              <input
                className="path-input"
                value={sectorExclude}
                onChange={(e) => setSectorExclude(e.target.value)}
                placeholder="e.g. Energy"
              />
            </label>
          </>
        ) : null}

        {needsIndexSelector ? (
          <>
            <label className="field-group">
              <span className="field-label">Index</span>
              <select
                className="path-input"
                value={indexId}
                onChange={(e) => setIndexId(e.target.value as IndexId)}
              >
                {(Object.keys(INDEX_LABELS) as IndexId[]).map((id) => (
                  <option key={id} value={id}>{INDEX_LABELS[id]}</option>
                ))}
              </select>
              <p className="helper">
                Resolved live from FMP. Optional sector filters can narrow the index further.
              </p>
            </label>
            <label className="field-group">
              <span className="field-label">Sectors to Include (comma-separated, optional)</span>
              <input
                className="path-input"
                value={sectorInclude}
                onChange={(e) => setSectorInclude(e.target.value)}
                placeholder="e.g. Technology"
              />
            </label>
            <label className="field-group">
              <span className="field-label">Sectors to Exclude (comma-separated, optional)</span>
              <input
                className="path-input"
                value={sectorExclude}
                onChange={(e) => setSectorExclude(e.target.value)}
                placeholder="e.g. Energy"
              />
            </label>
          </>
        ) : null}

        <label className="field-group">
          <span className="field-label">Universe ID (optional)</span>
          <input
            className="path-input"
            value={universeId}
            onChange={(e) => setUniverseId(e.target.value)}
            placeholder="Auto-generated if blank"
          />
        </label>

        <label className="field-group">
          <span className="field-label">Score Config Preset</span>
          <select
            className="path-input"
            value={selectedPresetId}
            onChange={(e) => setSelectedPresetId(e.target.value)}
          >
            {SCORE_CONFIG_PRESETS.map((preset) => (
              <option key={preset.score_config_id} value={preset.score_config_id}>
                {SCORE_CONFIG_PRESET_LABELS[preset.score_config_id] ?? preset.score_config_id}
              </option>
            ))}
          </select>
        </label>

        <label className="field-group">
          <span className="field-label">Benchmark</span>
          <input
            className="path-input"
            value={benchmarkSymbol}
            onChange={(e) => setBenchmarkSymbol(e.target.value)}
          />
        </label>

        <label className="field-group">
          <span className="field-label">Lookback (months)</span>
          <input
            className="path-input"
            type="number"
            value={lookbackMonths}
            onChange={(e) => setLookbackMonths(e.target.value)}
          />
        </label>
      </div>

      {selectedPreset ? (
        <section className="dashboard-bottom-grid">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Factor Weights — {SCORE_CONFIG_PRESET_LABELS[selectedPreset.score_config_id] ?? selectedPreset.score_config_id}</p></div>
            <p className="helper">Normalization: {selectedPreset.normalization} | Winsorize: {(selectedPreset.winsorize_pct * 100).toFixed(0)}%</p>
          </div>
          <div className="factor-snapshot-table-wrap">
            <div className="risk-contrib-table-grid factor-snapshot-header-row" style={{ gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr' }}>
              <span>Factor</span>
              <span>Family</span>
              <span>Direction</span>
              <span>Lookback (d)</span>
              <span>Weight</span>
            </div>
            {selectedPreset.factors.map((factor) => (
              <div key={factor.factor_id} className="risk-contrib-table-grid factor-shift-data-row" style={{ gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr' }}>
                <span>{factor.factor_id}</span>
                <span>{factor.family}</span>
                <span>{factor.direction === 'higher_is_better' ? 'higher better' : 'lower better'}</span>
                <span>{factor.lookback_days ?? 'n/a'}</span>
                <span>{(factor.weight * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {validationError ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Validation error</p>
          <p className="helper">{validationError}</p>
        </div>
      ) : null}

      <div className="dashboard-edit-actions dashboard-edit-actions-compact">
        <button
          className={`primary-button${loading ? ' button-loading' : ''}`}
          type="button"
          onClick={handleSubmit}
          disabled={loading}
        >
          {loading ? 'Running...' : 'Run Ranking'}
        </button>
      </div>
    </div>
  )
}

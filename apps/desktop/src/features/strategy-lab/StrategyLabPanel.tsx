import type { CSSProperties } from 'react'
import { useMemo, useState } from 'react'
import { investorEconomicsBaseReason } from '../portfolio/investorEconomics'
import type { EtfMomentumStrategyResponse as EtfMomentumResponse } from '../portfolio/types'

const UNIVERSE_PRESETS = {
  sectors: {
    label: 'Sectors',
    symbols: ['XLK', 'XLF', 'XLV', 'XLE', 'XLI'],
  },
  broad_rotation: {
    label: 'Broad ETF Rotation',
    symbols: ['XLK', 'XLF', 'XLV', 'XLE', 'XLI', 'QQQ', 'IWM'],
  },
  growth_vs_value: {
    label: 'Growth vs Value',
    symbols: ['QQQ', 'SPY', 'IWM', 'XLF', 'XLK'],
  },
  risk_on_off: {
    label: 'Risk-On / Risk-Off',
    symbols: ['QQQ', 'IWM', 'XLF', 'XLV', 'XLE'],
  },
} as const

type UniversePresetKey = keyof typeof UNIVERSE_PRESETS
type LookbackUnit = 'months' | 'quarters'
type ConstituentHeatmapMetric = 'contribution' | 'return'
type ConstituentHistoryMode = 'selected_etf' | 'leaders_only'

function formatPct(value: number | null | undefined) {
  return value == null ? 'N/A' : `${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'N/A' : value.toFixed(digits)
}

function formatDateLabel(value: string | number | null | undefined) {
  if (typeof value !== 'string') return ''
  const [year, month] = value.split('-')
  if (!year || !month) return value
  return `${month}/${year.slice(2)}`
}

function formatStrategyCheckpointLabel(value: string | number | null | undefined, unit: LookbackUnit) {
  if (typeof value !== 'string') return ''
  const [year, month] = value.split('-')
  if (!year || !month) return value
  if (unit === 'quarters') {
    const quarter = Math.floor((Number(month) - 1) / 3) + 1
    return `Q${quarter} ${year}`
  }
  return `${month}/${year.slice(2)}`
}

function heatTone(rank: number) {
  if (rank === 1) return 'strategy-leader-top'
  if (rank === 2) return 'strategy-leader-near'
  if (rank === 3) return 'strategy-leader-close'
  if (rank === 4) return 'strategy-leader-lag'
  return 'strategy-heat-off'
}

function leaderSpreadTone(spreadPct: number | null) {
  if (spreadPct == null) return 'strategy-leader-miss'
  if (spreadPct >= -0.01) return 'strategy-leader-top'
  if (spreadPct >= -2) return 'strategy-leader-near'
  if (spreadPct >= -5) return 'strategy-leader-close'
  if (spreadPct >= -10) return 'strategy-leader-lag'
  return 'strategy-leader-off'
}

function constituentMetricValue(
  constituent: EtfMomentumResponse['leader_internals'][number]['constituents'][number] | undefined,
  metric: ConstituentHeatmapMetric,
) {
  if (!constituent) return null
  return metric === 'contribution' ? constituent.weighted_contribution_pct : constituent.trailing_return_pct
}

function constituentCellStyle(value: number | null, allValues: number[]): CSSProperties | undefined {
  if (value == null) return undefined

  const positiveValues = allValues.filter((item) => item > 0)
  const negativeValues = allValues.filter((item) => item < 0).map((item) => Math.abs(item))
  const positiveScale = Math.max(...positiveValues, 0)
  const negativeScale = Math.max(...negativeValues, 0)

  if (value >= 0) {
    const intensity = positiveScale > 0 ? value / positiveScale : 0
    return {
      background: `rgba(62, 179, 127, ${0.08 + (intensity * 0.26)})`,
      borderColor: `rgba(62, 179, 127, ${0.18 + (intensity * 0.34)})`,
      color: intensity > 0.55 ? '#d8f2e7' : '#dce8e2',
    }
  }

  const intensity = negativeScale > 0 ? Math.abs(value) / negativeScale : 0
  return {
    background: `rgba(216, 90, 81, ${0.08 + (intensity * 0.24)})`,
    borderColor: `rgba(216, 90, 81, ${0.16 + (intensity * 0.3)})`,
    color: intensity > 0.55 ? '#f0c0bb' : '#e4d1cf',
  }
}

function mergePresetSymbols(keys: UniversePresetKey[]) {
  const merged = new Set<string>()
  keys.forEach((key) => {
    UNIVERSE_PRESETS[key].symbols.forEach((symbol) => merged.add(symbol))
  })
  return Array.from(merged)
}

function filterObservationsForUnit(observations: EtfMomentumResponse['observations'], unit: LookbackUnit, lookbackValue: number) {
  const cadenceFiltered = unit === 'months'
    ? observations
    : observations.filter((item) => {
      const month = Number(item.date.split('-')[1] ?? '0')
      return month === 3 || month === 6 || month === 9 || month === 12
    })

  if (lookbackValue <= 0 || cadenceFiltered.length <= lookbackValue) {
    return cadenceFiltered
  }

  return cadenceFiltered.slice(-lookbackValue)
}

function leaderSpread(observation: EtfMomentumResponse['observations'][number], symbol: string) {
  const leaderReturn = observation.rankings.find((item) => item.symbol === observation.leader)?.trailing_return_pct
    ?? observation.rankings[0]?.trailing_return_pct
    ?? null
  const symbolReturn = observation.rankings.find((item) => item.symbol === symbol)?.trailing_return_pct ?? null

  if (leaderReturn == null || symbolReturn == null) return null
  return symbolReturn - leaderReturn
}

function latestLeaderInternals(result: EtfMomentumResponse | null, visibleDates: string[]) {
  if (!result) return null
  const byDate = new Map<string, EtfMomentumResponse['leader_internals'][number]>(result.leader_internals.map((item) => [item.date, item]))
  for (let index = visibleDates.length - 1; index >= 0; index -= 1) {
    const match = byDate.get(visibleDates[index])
    if (match && match.constituents.length) return match
  }
  return result.leader_internals[result.leader_internals.length - 1] ?? null
}

function visibleEtfInternalsSeries(
  result: EtfMomentumResponse | null,
  etfSymbol: string | null | undefined,
  visibleDates: string[],
) {
  if (!result || !etfSymbol) return []
  const byDate = new Map((result.etf_internals_history[etfSymbol] ?? []).map((item) => [item.date, item]))
  return visibleDates.map((date) => byDate.get(date)).filter((item): item is NonNullable<typeof item> => Boolean(item))
}

function sourceStatusLabel(status: string) {
  if (status === 'live') return 'Live FMP'
  if (status === 'live-dated') return 'Dated FMP snapshots'
  if (status === 'mixed') return 'Mixed live + sample'
  return 'Sample fallback'
}

function investorEconomicsHelper(
  status: EtfMomentumResponse['investor_economics_status'],
) {
  if (investorEconomicsBaseReason(status)) {
    return 'Withheld until Strategy Lab has verified investor total-return equivalence.'
  }
  return 'Investor-economics outputs are available on this surface.'
}

function leaderCheckpointSourceLabel(status: string, snapshotDate: string | null) {
  if (status === 'live-dated') {
    return snapshotDate ? `FMP ${snapshotDate}` : 'FMP snapshot'
  }
  return 'Sample snapshot'
}

function asLeaderInternalsEntry(entry: EtfMomentumResponse['etf_internals_history'][string][number]) {
  return {
    ...entry,
    leader_symbol: entry.etf_symbol,
  }
}

export function StrategyLabPanel() {
  const apiBase = useMemo(() => '/api', [])
  const [selectedPresets, setSelectedPresets] = useState<UniversePresetKey[]>(['broad_rotation'])
  const [presetMenuOpen, setPresetMenuOpen] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [universe, setUniverse] = useState(UNIVERSE_PRESETS.broad_rotation.symbols.join(','))
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [signalLookbackValue, setSignalLookbackValue] = useState('4')
  const [lookbackUnit, setLookbackUnit] = useState<LookbackUnit>('quarters')
  const [topN, setTopN] = useState('3')
  const [constituentHeatmapMetric, setConstituentHeatmapMetric] = useState<ConstituentHeatmapMetric>('contribution')
  const [constituentHistoryMode, setConstituentHistoryMode] = useState<ConstituentHistoryMode>('selected_etf')
  const [selectedLeaderDate, setSelectedLeaderDate] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshingHoldings, setRefreshingHoldings] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<EtfMomentumResponse | null>(null)

  function togglePreset(key: UniversePresetKey) {
    const nextSelected = selectedPresets.includes(key)
      ? selectedPresets.filter((value) => value !== key)
      : [...selectedPresets, key]
    setSelectedPresets(nextSelected)
    setUniverse(mergePresetSymbols(nextSelected).join(','))
  }

  const presetSummary = selectedPresets.length
    ? selectedPresets.map((key) => UNIVERSE_PRESETS[key].label).join(' + ')
    : 'Custom basket'
  const parsedSignalLookbackValue = Number(signalLookbackValue)
  const visibleObservations = useMemo(
    () => filterObservationsForUnit(result?.observations ?? [], lookbackUnit, Number.isInteger(parsedSignalLookbackValue) ? parsedSignalLookbackValue : 0),
    [lookbackUnit, parsedSignalLookbackValue, result?.observations],
  )
  const activeLeaderDate = selectedLeaderDate ?? visibleObservations[visibleObservations.length - 1]?.date ?? null
  const selectedLeaderObservation = useMemo(
    () => visibleObservations.find((item) => item.date === activeLeaderDate) ?? visibleObservations[visibleObservations.length - 1] ?? null,
    [activeLeaderDate, visibleObservations],
  )
  const currentLeaderInternals = useMemo(
    () => {
      if (!result) return null
      const selectedLeaderSymbol = selectedLeaderObservation?.leader
      if (selectedLeaderSymbol) {
        const etfSeries = result.etf_internals_history[selectedLeaderSymbol] ?? []
        if (selectedLeaderObservation) {
          const match = etfSeries.find((item) => item.date === selectedLeaderObservation.date)
          return match ? asLeaderInternalsEntry(match) : null
        }
      }
      if (selectedLeaderObservation) {
        return result.leader_internals.find((item) => item.date === selectedLeaderObservation.date) ?? latestLeaderInternals(result, visibleObservations.map((item) => item.date))
      }
      return latestLeaderInternals(result, visibleObservations.map((item) => item.date))
    },
    [result, selectedLeaderObservation, visibleObservations],
  )
  const visibleLeaderInternalsSeries = useMemo(
    () => (
      constituentHistoryMode === 'leaders_only'
        ? (result?.leader_internals ?? []).filter((item) => visibleObservations.some((observation) => observation.date === item.date))
        : visibleEtfInternalsSeries(result, selectedLeaderObservation?.leader, visibleObservations.map((item) => item.date)).map(asLeaderInternalsEntry)
    ),
    [constituentHistoryMode, result?.leader_internals, result, selectedLeaderObservation?.leader, visibleObservations],
  )
  const visibleConstituentMetricValues = useMemo(
    () => visibleLeaderInternalsSeries.flatMap((item) => item.constituents.map((constituent) => constituentMetricValue(constituent, constituentHeatmapMetric))).filter((value): value is number => value != null),
    [constituentHeatmapMetric, visibleLeaderInternalsSeries],
  )
  const investorEconomicsWithheld = result?.investor_economics_status.status === 'withheld'

  async function runStrategy() {
    const parsedUniverse = universe.split(',').map((item) => item.trim().toUpperCase()).filter(Boolean)
    const parsedLookback = lookbackUnit === 'quarters' ? parsedSignalLookbackValue * 3 : parsedSignalLookbackValue
    const parsedTopN = Number(topN)
    if (!parsedUniverse.length) {
      setError('Enter at least one ETF in the universe.')
      return
    }
    if (!Number.isInteger(parsedSignalLookbackValue) || parsedSignalLookbackValue < 1) {
      setError('Signal lookback must be a positive integer.')
      return
    }
    if (!Number.isInteger(parsedTopN) || parsedTopN < 1 || parsedTopN > parsedUniverse.length) {
      setError('Top N must be a positive integer and cannot exceed the universe size.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${apiBase}/strategy-lab/etf-cross-sectional-momentum`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          universe: parsedUniverse,
          benchmark_symbol: benchmarkSymbol.toUpperCase(),
          lookback_months: parsedLookback,
          top_n: parsedTopN,
          prefer_live_data: true,
        }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Strategy run failed')
      }
      const nextResult = (await response.json()) as EtfMomentumResponse
      setResult(nextResult)
      setSelectedLeaderDate(nextResult.observations[nextResult.observations.length - 1]?.date ?? null)
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Strategy run failed')
    } finally {
      setLoading(false)
    }
  }

  async function refreshHoldingsSnapshots() {
    const parsedUniverse = universe.split(',').map((item) => item.trim().toUpperCase()).filter(Boolean)
    if (!parsedUniverse.length) return

    setRefreshingHoldings(true)
    try {
      const response = await fetch(`${apiBase}/strategy-lab/holdings/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols: parsedUniverse }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Holdings refresh failed')
      }
      await runStrategy()
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Holdings refresh failed')
    } finally {
      setRefreshingHoldings(false)
    }
  }

  return (
    <article className="panel strategy-lab-panel">
      <p className="panel-label">Strategy Lab</p>
      <h2>ETF cross-sectional momentum</h2>

      <div className="backtest-builder strategy-lab-builder">
        <div className="split-grid compact-split-grid strategy-lab-top-grid">
          <label className="field-group">
            <span className="field-label">Universe Presets</span>
            <div className="strategy-preset-dropdown">
              <button
                type="button"
                className={`path-input strategy-preset-trigger${presetMenuOpen ? ' open' : ''}`}
                aria-expanded={presetMenuOpen}
                aria-controls="strategy-preset-menu"
                onClick={() => setPresetMenuOpen((value) => !value)}
              >
                <span className="strategy-preset-summary">{presetSummary}</span>
                <span className="strategy-preset-meta">{selectedPresets.length ? `${selectedPresets.length} presets · ${universe.split(',').filter(Boolean).length} ETFs` : 'custom basket'}</span>
              </button>
              {presetMenuOpen ? (
                <div className="strategy-preset-menu" id="strategy-preset-menu" role="group" aria-label="Universe Presets">
                  {Object.entries(UNIVERSE_PRESETS).map(([key, option]) => {
                    const presetKey = key as UniversePresetKey
                    const active = selectedPresets.includes(presetKey)
                    return (
                      <label key={key} className={`strategy-preset-option${active ? ' active' : ''}`}>
                        <input type="checkbox" checked={active} onChange={() => togglePreset(presetKey)} />
                        <span className="strategy-preset-option-copy">
                          <span>{option.label}</span>
                        </span>
                      </label>
                    )
                  })}
                </div>
              ) : null}
            </div>
            {selectedPresets.length ? (
              <div className="strategy-preset-chip-row">
                {selectedPresets.map((key) => <span className="strategy-preset-chip" key={`preset-chip-${key}`}>{UNIVERSE_PRESETS[key].label}</span>)}
              </div>
            ) : null}
          </label>
          <label className="field-group">
            <span className="field-label">ETF Universe</span>
            <input
              className="path-input"
              value={universe}
              onChange={(event) => {
                setSelectedPresets([])
                setUniverse(event.target.value)
              }}
              placeholder="XLK,XLF,XLV,XLE,XLI,QQQ,IWM"
            />
          </label>
          <label className="field-group strategy-lab-benchmark-field">
            <span className="field-label">Benchmark</span>
            <input className="path-input" value={benchmarkSymbol} onChange={(event) => setBenchmarkSymbol(event.target.value.toUpperCase())} />
          </label>
        </div>
        <div className="split-grid compact-split-grid strategy-lab-config-grid">
          <label className="field-group">
            <span className="field-label">Signal Lookback</span>
            <input className="path-input" inputMode="numeric" value={signalLookbackValue} onChange={(event) => setSignalLookbackValue(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">View Unit</span>
            <select className="path-input strategy-select" value={lookbackUnit} onChange={(event) => setLookbackUnit(event.target.value as LookbackUnit)}>
              <option value="months">Months</option>
              <option value="quarters">Quarters</option>
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Top N</span>
            <input className="path-input" inputMode="numeric" value={topN} onChange={(event) => setTopN(event.target.value)} />
          </label>
        </div>
        <div className="actions">
          <button className={`primary-button${loading ? ' button-loading' : ''}`} type="button" disabled={loading} onClick={runStrategy}>{loading ? 'Running Strategy...' : 'Run ETF Rotation Prototype'}</button>
          <button className="secondary-button" type="button" disabled={refreshingHoldings || loading} onClick={refreshHoldingsSnapshots}>{refreshingHoldings ? 'Refreshing snapshots...' : 'Refresh holdings snapshots'}</button>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </div>

      {result ? (
        <>
          <section className="workspace-section strategy-lab-summary-grid">
            <div className="summary-card strategy-summary-card strategy-summary-card-primary">
              <p className="stat-label">Investor Economics</p>
              <p className="summary-value">{investorEconomicsWithheld ? 'Withheld' : 'Available'}</p>
              <p className="helper">{investorEconomicsHelper(result.investor_economics_status)}</p>
            </div>
            <div className="summary-card strategy-summary-card">
              <p className="stat-label">Turnover</p>
              <p className="summary-value">{formatPct(result.metrics.average_turnover_pct)}</p>
              <p className="helper">Average rebalance turnover</p>
            </div>
            <div className="summary-card strategy-summary-card">
              <p className="stat-label">Volume Participation</p>
              <p className="summary-value">{formatNumber(result.metrics.average_volume_participation_ratio)}</p>
              <p className="helper">Selected sleeves vs universe average volume</p>
            </div>
            <div className="summary-card strategy-summary-card">
              <p className="stat-label">Benchmark</p>
              <p className="summary-value">{result.benchmark_symbol}</p>
              <p className="helper">{investorEconomicsWithheld ? 'Used for ranking context only; return comparisons are withheld.' : 'Used for ranking context and performance comparison.'}</p>
            </div>
            <div className="summary-card strategy-summary-card">
              <p className="stat-label">Withheld Metrics</p>
              <p className="summary-value">{investorEconomicsWithheld ? 'N/A' : 'Visible'}</p>
              <p className="helper">{investorEconomicsWithheld ? 'Total return, benchmark return, excess return, annualized return, max drawdown, and win rate are intentionally suppressed.' : 'Investor-economics metrics are visible on this surface.'}</p>
            </div>
          </section>

          <section className="workspace-section">
            <div className="strategy-source-strip" data-testid="strategy-source-strip">
              <div className="strategy-source-card">
                <p className="stat-label">Price History</p>
                <p className="summary-value">{sourceStatusLabel(result.source_status.price_history)}</p>
              </div>
              <div className="strategy-source-card">
                <p className="stat-label">Leader Internals</p>
                <p className="summary-value">{sourceStatusLabel(result.source_status.leader_internals)}</p>
              </div>
              <div className="strategy-source-card strategy-source-card-wide">
                <p className="stat-label">Holdings Snapshots</p>
                <p className="summary-value">{Object.entries(result.source_status.holdings_snapshot_counts).length ? Object.entries(result.source_status.holdings_snapshot_counts).map(([symbol, count]) => `${symbol} ${count}`).join(' · ') : 'none yet'}</p>
                <p className="helper">
                  {result.source_status.sample_fallback_symbols.length
                    ? `Sample fallback: ${result.source_status.sample_fallback_symbols.join(', ')}`
                    : result.source_status.dated_holdings_symbols.length
                      ? `Dated snapshots active: ${result.source_status.dated_holdings_symbols.join(', ')}`
                      : 'Waiting for dated holdings snapshots to accumulate'}
                </p>
              </div>
            </div>
          </section>

          <section className="workspace-section">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Leadership Heatmap</p></div><p className="helper">Rank order across the visible checkpoints.</p></div>
              <div className="strategy-heatmap" data-testid="strategy-heatmap">
                <div className="strategy-heatmap-row strategy-heatmap-header">
                  <span>ETF</span>
                  {visibleObservations.map((item) => <span key={`heat-header-${item.date}`}>{formatStrategyCheckpointLabel(item.date, lookbackUnit)}</span>)}
                </div>
                {result.universe.map((symbol) => (
                  <div className="strategy-heatmap-row" key={`heat-row-${symbol}`}>
                    <span className="strategy-heatmap-symbol">{symbol}</span>
                  {visibleObservations.map((item) => {
                    const rank = item.rankings.findIndex((ranking) => ranking.symbol === symbol) + 1
                    const ranking = item.rankings.find((entry) => entry.symbol === symbol)
                    return (
                      <span className={`strategy-heatmap-cell ${heatTone(rank)}`} key={`heat-cell-${symbol}-${item.date}`} title={`${symbol} rank ${rank || 'n/a'} · ${formatPct(ranking?.trailing_return_pct)}`}>
                        {rank || '-'}
                      </span>
                    )
                  })}
                </div>
              ))}
            </div>
          </section>

          <section className="workspace-section">
            <div className="summary-card strategy-summary-card">
              <p className="stat-label">Performance Charts</p>
              <p className="summary-value">{investorEconomicsWithheld ? 'N/A' : 'Available'}</p>
              <p className="helper">{investorEconomicsWithheld ? 'Strategy equity, benchmark equity, and drawdown charts are intentionally withheld until investor-performance equivalence is verified.' : 'Strategy equity, benchmark equity, and drawdown charts are available on this surface.'}</p>
            </div>
          </section>

          <section className="workspace-section">
            <div className="section-header-inline sector-list-header">
              <div><p className="panel-label">Leader Relative Heatmap</p></div>
              <div className="strategy-inline-actions">
                <p className="helper">Lookback price-change spread versus the checkpoint leader.</p>
              </div>
            </div>
            <div className="strategy-heatmap" data-testid="strategy-leader-heatmap">
              <div className="strategy-heatmap-row strategy-heatmap-header">
                <span>ETF</span>
                {visibleObservations.map((item) => (
                  <button
                    type="button"
                    key={`leader-header-${item.date}`}
                    className={`strategy-heatmap-header-cell strategy-heatmap-header-button${selectedLeaderObservation?.date === item.date ? ' active' : ''}`}
                    onClick={() => setSelectedLeaderDate(item.date)}
                    onMouseEnter={() => setSelectedLeaderDate(item.date)}
                  >
                    <span>{formatStrategyCheckpointLabel(item.date, lookbackUnit)}</span>
                    <span className="strategy-heatmap-meta">{item.leader ?? 'n/a'}</span>
                  </button>
                ))}
              </div>
              {result.universe.map((symbol) => (
                <div className="strategy-heatmap-row" key={`leader-row-${symbol}`}>
                  <span className="strategy-heatmap-symbol">{symbol}</span>
                  {visibleObservations.map((item) => {
                    const spreadPct = leaderSpread(item, symbol)
                    return (
                      <span
                        className={`strategy-heatmap-cell ${leaderSpreadTone(spreadPct)}${selectedLeaderObservation?.date === item.date ? ' strategy-heatmap-column-active' : ''}`}
                        key={`leader-cell-${symbol}-${item.date}`}
                        title={`${symbol} vs ${item.leader ?? 'leader'}: ${spreadPct == null ? 'n/a' : `${spreadPct.toFixed(2)} pts`}`}
                      >
                        {spreadPct == null ? '-' : spreadPct.toFixed(1)}
                      </span>
                    )
                  })}
                </div>
              ))}
            </div>
          </section>

          <section className="workspace-section">
            <div className="section-header-inline sector-list-header">
              <div><p className="panel-label">Leader Internals</p></div>
              <p className="helper">Hover or click a checkpoint above to lock it.</p>
            </div>
            {currentLeaderInternals && currentLeaderInternals.constituents.length ? (
                <div className="factor-snapshot-table-wrap">
                  <div className="section-header-inline sector-list-header strategy-detail-subheader">
                    <div>
                      <p className="panel-label">Constituent Mini Heatmap</p>
                      <p className="helper">Selected ETF history: {selectedLeaderObservation?.leader ?? currentLeaderInternals.leader_symbol ?? 'n/a'}</p>
                      <p className="helper">{constituentHeatmapMetric === 'contribution' ? 'Weighted contribution points' : 'Lookback price change percent'} across the visible checkpoints{currentLeaderInternals.snapshot_date ? ` · snapshot ${currentLeaderInternals.snapshot_date}` : ''}</p>
                    </div>
                    <div className="strategy-inline-actions">
                      <div className="strategy-mode-toggle" role="group" aria-label="Constituent History Mode">
                        <button type="button" className={`toggle-chip${constituentHistoryMode === 'selected_etf' ? ' active' : ''}`} onClick={() => setConstituentHistoryMode('selected_etf')}>Selected ETF history</button>
                        <button type="button" className={`toggle-chip${constituentHistoryMode === 'leaders_only' ? ' active' : ''}`} onClick={() => setConstituentHistoryMode('leaders_only')}>Actual leaders only</button>
                      </div>
                      <div className="strategy-mode-toggle" role="group" aria-label="Constituent Heatmap Metric">
                      <button type="button" className={`toggle-chip${constituentHeatmapMetric === 'contribution' ? ' active' : ''}`} onClick={() => setConstituentHeatmapMetric('contribution')}>Contribution</button>
                      <button type="button" className={`toggle-chip${constituentHeatmapMetric === 'return' ? ' active' : ''}`} onClick={() => setConstituentHeatmapMetric('return')}>Lookback Price Change</button>
                      </div>
                    </div>
                  </div>
                  <div className="strategy-heatmap" data-testid="strategy-constituent-heatmap">
                  <div className="strategy-heatmap-row strategy-heatmap-header">
                    <span>Constituent</span>
                    {visibleLeaderInternalsSeries.map((item) => (
                      <span key={`constituent-header-${item.date}`} className="strategy-heatmap-header-cell">
                        <span>{formatStrategyCheckpointLabel(item.date, lookbackUnit)}</span>
                        <span className="strategy-heatmap-meta">{item.leader_symbol ?? 'n/a'} · {leaderCheckpointSourceLabel(item.source_mode, item.snapshot_date)}</span>
                      </span>
                    ))}
                  </div>
                    {currentLeaderInternals.constituents.map((constituent) => (
                      <div className="strategy-heatmap-row" key={`constituent-row-${constituent.symbol}`}>
                        <span className="strategy-heatmap-symbol">{constituent.symbol}</span>
                        {visibleLeaderInternalsSeries.map((item) => {
                          const match = item.constituents.find((entry) => entry.symbol === constituent.symbol)
                          const metricValue = constituentMetricValue(match, constituentHeatmapMetric)
                          return (
                            <span
                              className={`strategy-heatmap-cell${metricValue == null ? ' strategy-leader-miss' : ''}`}
                              style={constituentCellStyle(metricValue, visibleConstituentMetricValues)}
                              key={`constituent-cell-${constituent.symbol}-${item.date}`}
                              title={`${constituent.symbol} ${constituentHeatmapMetric === 'contribution' ? 'contribution' : 'lookback price change'}: ${metricValue == null ? 'n/a' : `${metricValue.toFixed(2)}${constituentHeatmapMetric === 'contribution' ? ' pts' : '%'}`}`}
                            >
                              {metricValue == null ? '-' : metricValue.toFixed(1)}
                            </span>
                          )
                        })}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="helper">No constituent drilldown is available for the current leader ETF yet.</p>
            )}
          </section>

          <section className="workspace-section">
            <div className="section-header-inline sector-list-header">
              <div>
                <p className="panel-label">Detail Tables</p>
                <p className="helper">Checkpoint details, contributors, and current sleeves.</p>
              </div>
              <button className="secondary-button" type="button" onClick={() => setDetailsOpen((value) => !value)}>
                {detailsOpen ? 'Hide details' : 'Show details'}
              </button>
            </div>
            {detailsOpen ? (
              <div className="strategy-detail-stack">
                {currentLeaderInternals && currentLeaderInternals.constituents.length ? (
                  <div className="factor-snapshot-table-wrap">
                    <div className="section-header-inline sector-list-header strategy-detail-subheader">
                      <div>
                        <p className="panel-label">{currentLeaderInternals.leader_symbol} Constituents</p>
                        <p className="helper">Checkpoint {formatStrategyCheckpointLabel(currentLeaderInternals.date, lookbackUnit)}</p>
                      </div>
                    </div>
                    <div className="split-grid strategy-lab-contributor-split">
                      <div>
                        <div className="section-header-inline sector-list-header strategy-detail-subheader"><div><p className="panel-label">Top Contributors</p></div></div>
                        <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-leader-internals-grid">
                          <span>Symbol</span>
                          <span>Name</span>
                          <span>Weight</span>
                          <span>Lookback Price Change</span>
                          <span>Contribution</span>
                        </div>
                        {currentLeaderInternals.constituents.slice(0, 4).map((item) => (
                          <div className="risk-contrib-table-grid factor-shift-data-row strategy-leader-internals-grid" key={`${currentLeaderInternals.date}-top-${item.symbol}`}>
                            <span className="factor-snapshot-primary">{item.symbol}</span>
                            <span>{item.name}</span>
                            <span>{formatPct(item.weight * 100)}</span>
                            <span>{formatPct(item.trailing_return_pct)}</span>
                            <span>{formatPct(item.weighted_contribution_pct)}</span>
                          </div>
                        ))}
                      </div>
                      <div>
                        <div className="section-header-inline sector-list-header strategy-detail-subheader"><div><p className="panel-label">Lagging Contributors</p></div></div>
                        <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-leader-internals-grid">
                          <span>Symbol</span>
                          <span>Name</span>
                          <span>Weight</span>
                          <span>Lookback Price Change</span>
                          <span>Contribution</span>
                        </div>
                        {[...currentLeaderInternals.constituents].reverse().slice(0, 4).map((item) => (
                          <div className="risk-contrib-table-grid factor-shift-data-row strategy-leader-internals-grid" key={`${currentLeaderInternals.date}-lag-${item.symbol}`}>
                            <span className="factor-snapshot-primary">{item.symbol}</span>
                            <span>{item.name}</span>
                            <span>{formatPct(item.weight * 100)}</span>
                            <span>{formatPct(item.trailing_return_pct)}</span>
                            <span>{formatPct(item.weighted_contribution_pct)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}

                <div className="factor-snapshot-table-wrap">
                  <div className="section-header-inline sector-list-header strategy-detail-subheader"><div><p className="panel-label">Current Rankings</p></div><p className="helper">Top {result.top_n} equal-weight sleeves from {result.universe.join(', ')}</p></div>
                  <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-rank-grid">
                    <span>ETF</span>
                    <span>Weight</span>
                    <span>Lookback Price Change</span>
                    <span>Avg Volume</span>
                    <span>Score</span>
                  </div>
                  {result.current_rankings.map((item) => (
                    <div className="risk-contrib-table-grid factor-shift-data-row strategy-lab-rank-grid" key={item.symbol}>
                      <span className="factor-snapshot-primary">{item.symbol}</span>
                      <span>{formatPct(item.target_weight * 100)}</span>
                      <span>{formatPct(item.trailing_return_pct)}</span>
                      <span>{formatNumber(item.average_volume, 0)}</span>
                      <span>{formatPct(item.score * 100)}</span>
                    </div>
                  ))}
                </div>

                <div className="factor-snapshot-table-wrap">
                  <div className="section-header-inline sector-list-header strategy-detail-subheader"><div><p className="panel-label">Rebalance History</p></div></div>
                  <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-history-grid">
                    <span>Date</span>
                    <span>Leader</span>
                    <span>Held ETFs</span>
                    <span>Strategy Return</span>
                    <span>Benchmark Return</span>
                  </div>
                  {visibleObservations.map((item) => (
                    <div className="risk-contrib-table-grid factor-shift-data-row strategy-lab-history-grid" key={item.date}>
                      <span>{item.date}</span>
                      <span>{item.leader ?? 'n/a'}</span>
                      <span>{item.holdings.map((holding) => holding.symbol).join(', ')}</span>
                      <span>{formatPct(item.strategy_return_pct)}</span>
                      <span>{formatPct(item.benchmark_return_pct)}</span>
                    </div>
                  ))}
                </div>
                <p className="helper">{investorEconomicsWithheld ? 'Checkpoint investor-performance fields are intentionally withheld until Strategy Lab meets the verified investor total-return equivalence contract.' : 'Checkpoint investor-performance fields are available on this surface.'}</p>
              </div>
            ) : null}
          </section>
        </>
      ) : null}
    </article>
  )
}

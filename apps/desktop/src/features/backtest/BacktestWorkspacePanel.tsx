import { useMemo, useState } from 'react'

import { PortfolioAllocationBacktestPanel } from './PortfolioAllocationBacktestPanel'
import { PortfolioImprovementWorkspaceShell } from './PortfolioImprovementWorkspaceShell'
import type { BacktestRunResponse, HypotheticalReplacementReplayResponse, PortfolioAllocationBacktestResponse, PortfolioBaselineView, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionRuleId } from '../portfolio/types'
import type { CandidateImprovementDraftArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifact, PortfolioSnapshot, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'

type Props = {
  backtestResult: BacktestRunResponse | null
  onBacktestResult: (result: BacktestRunResponse) => void
  allocationBacktestResult: PortfolioAllocationBacktestResponse | null
  onAllocationBacktestResult: (result: PortfolioAllocationBacktestResponse) => void
  analysis: PortfolioBaselineView | null
  draftSnapshot: PortfolioSnapshot | null
  candidateImprovementDraft: CandidateImprovementDraftArtifact | null
  intentBoundSeededEtfReplacementRankingDraft: IntentBoundSeededEtfReplacementRankingDraftArtifact | null
  replacementIntentDraft: ReplacementIntentDraftArtifact | null
  formedCandidateArtifact: FormedCandidateArtifact | null
  constructedCandidateArtifact: ConstructedCandidateArtifact | null
  selectedConstructionRuleId: SingleReplacementConstructionRuleId
  hypotheticalReplayResult: HypotheticalReplacementReplayResponse | null
  savedProposals: VersionedProposalArtifact[]
  onSaveProposal: () => void | Promise<void>
  onHypotheticalReplayResult: (result: HypotheticalReplacementReplayResponse) => void
  onFormedCandidateArtifact: (result: SingleReplacementCandidateFormationResponse) => void
  onConstructedCandidateArtifact: (result: SingleReplacementCandidateConstructionResponse) => void
  onSelectedConstructionRuleChange: (ruleId: SingleReplacementConstructionRuleId) => void
  onCreateReplacementIntent?: () => void | Promise<void>
  onClearReplacementIntent?: () => void | Promise<void>
}

function parseUniverse(value: string) {
  return value
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)
}

export function BacktestWorkspacePanel({ backtestResult, onBacktestResult, allocationBacktestResult, onAllocationBacktestResult, analysis, draftSnapshot, candidateImprovementDraft, intentBoundSeededEtfReplacementRankingDraft, replacementIntentDraft, formedCandidateArtifact, constructedCandidateArtifact, selectedConstructionRuleId, hypotheticalReplayResult, savedProposals, onSaveProposal, onHypotheticalReplayResult, onFormedCandidateArtifact, onConstructedCandidateArtifact, onSelectedConstructionRuleChange, onCreateReplacementIntent, onClearReplacementIntent }: Props) {
  const apiBase = useMemo(() => '/api', [])
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [strategyId, setStrategyId] = useState('book_trend_breakout')
  const [universe, setUniverse] = useState('ES,NQ,CL')
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [initialCapital, setInitialCapital] = useState('100000')
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [backtestError, setBacktestError] = useState<string | null>(null)

  const sourceSummary = useMemo(() => {
    if (!backtestResult) return null
    const items = Object.values(backtestResult.dataset_info)
    if (!items.length) return null
    const allFmp = items.every((item) => item.source === 'fmp')
    const anyProxyApproximation = items.some((item) => item.source.includes('proxy approximation'))
    const anyLocalApproximation = items.some((item) => item.source === 'local approximation')
    const anyFallback = items.some((item) => item.source === 'local-sample')
    if (allFmp) return 'Live FMP'
    if ((anyProxyApproximation || anyLocalApproximation) && anyFallback) return 'Mixed proxy + fallback'
    if (anyProxyApproximation) return 'Proxy approximation'
    if (anyLocalApproximation) return 'Local approximation'
    if (anyFallback) return 'Mixed FMP + sample'
    return 'Mixed sources'
  }, [backtestResult])

  async function runBacktest() {
    const parsedUniverse = parseUniverse(universe)
    const capital = Number(initialCapital)

    if (!parsedUniverse.length) {
      setBacktestError('Please enter at least one symbol in the backtest universe.')
      return
    }
    if (!startDate || !endDate) {
      setBacktestError('Please provide both a start date and an end date.')
      return
    }
    if (endDate < startDate) {
      setBacktestError('End date must be on or after start date.')
      return
    }
    if (!Number.isFinite(capital) || capital <= 0) {
      setBacktestError('Initial capital must be a positive number.')
      return
    }

    setBacktestLoading(true)
    setBacktestError(null)

    try {
      const response = await fetch(`${apiBase}/backtests/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: strategyId,
          universe: parsedUniverse,
          benchmark_symbol: benchmarkSymbol,
          start_date: startDate,
          end_date: endDate,
          initial_capital: capital,
        }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Backtest failed')
      }
      onBacktestResult((await response.json()) as BacktestRunResponse)
    } catch (caughtError) {
      setBacktestError(caughtError instanceof Error ? caughtError.message : 'Backtest failed')
    } finally {
      setBacktestLoading(false)
    }
  }

  return (
    <article className="panel">
      <p className="panel-label">Backtest</p>
      <h2>Portfolio improvement and strategy backtests</h2>
      <p className="lead compact-lead">Current portfolio vs candidate portfolio is the primary workflow; strategy backtests remain secondary.</p>

      <PortfolioImprovementWorkspaceShell analysis={analysis} draftSnapshot={draftSnapshot} candidateImprovementDraft={candidateImprovementDraft} intentBoundSeededEtfReplacementRankingDraft={intentBoundSeededEtfReplacementRankingDraft} replacementIntentDraft={replacementIntentDraft} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} selectedConstructionRuleId={selectedConstructionRuleId} allocationBacktestResult={allocationBacktestResult} hypotheticalReplayResult={hypotheticalReplayResult} savedProposals={savedProposals} onCreateReplacementIntent={onCreateReplacementIntent} onClearReplacementIntent={onClearReplacementIntent} onSaveProposal={onSaveProposal} onHypotheticalReplayResult={onHypotheticalReplayResult} onFormedCandidateArtifact={onFormedCandidateArtifact} onConstructedCandidateArtifact={onConstructedCandidateArtifact} onSelectedConstructionRuleChange={onSelectedConstructionRuleChange} />

      <PortfolioAllocationBacktestPanel result={allocationBacktestResult} onResult={onAllocationBacktestResult} analysis={analysis} />

      <div className="backtest-builder">
        <p className="panel-label">Strategy Backtest</p>
        <div className="split-grid compact-split-grid">
          <label className="field-group">
            <span className="field-label">Strategy Id</span>
            <select className="path-input" value={strategyId} onChange={(event) => setStrategyId(event.target.value)}>
              <option value="book_trend_breakout">Book Trend Breakout</option>
              <option value="book_ma_filter">Book Moving Average Filter</option>
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Benchmark Symbol</span>
            <input className="path-input" value={benchmarkSymbol} onChange={(event) => setBenchmarkSymbol(event.target.value.toUpperCase())} />
          </label>
        </div>

        <label className="field-group">
          <span className="field-label">Universe</span>
          <input className="path-input" value={universe} onChange={(event) => setUniverse(event.target.value)} placeholder="ES,NQ,CL" />
        </label>

        <div className="split-grid compact-split-grid">
          <label className="field-group">
            <span className="field-label">Start Date</span>
            <input className="path-input" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">End Date</span>
            <input className="path-input" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </label>
        </div>

        <label className="field-group">
          <span className="field-label">Initial Capital</span>
          <input className="path-input" inputMode="decimal" value={initialCapital} onChange={(event) => setInitialCapital(event.target.value)} />
        </label>

        <div className="actions">
          <button className={`primary-button${backtestLoading ? ' button-loading' : ''}`} type="button" disabled={backtestLoading} onClick={runBacktest}>
            {backtestLoading ? 'Running Backtest...' : 'Run Backtest'}
          </button>
          <p className="helper">The local API validates dates, symbols, and capital before running the strategy backtest.</p>
        </div>
        {backtestError ? <p className="error">{backtestError}</p> : null}
      </div>

      {backtestResult ? (
        <section className="workspace-section">
          <div className="section-header-inline sector-list-header">
            <div>
              <p className="panel-label">Latest Strategy Run</p>
            </div>
            {sourceSummary ? <span className="backtest-source-badge">{sourceSummary}</span> : null}
          </div>
          <div className="stats">
            <div className="stat">
              <p className="stat-label">Run Id</p>
              <p className="stat-value">{backtestResult.run_id.split(':')[0]}</p>
            </div>
            <div className="stat">
              <p className="stat-label">Total Return</p>
              <p className="stat-value">{backtestResult.total_return_pct?.toFixed(2) ?? 'n/a'}%</p>
            </div>
            <div className="stat">
              <p className="stat-label">Max Drawdown</p>
              <p className="stat-value">{backtestResult.max_drawdown_pct?.toFixed(2) ?? 'n/a'}%</p>
            </div>
            <div className="stat">
              <p className="stat-label">Sharpe</p>
              <p className="stat-value">{backtestResult.sharpe_ratio?.toFixed(2) ?? 'n/a'}</p>
            </div>
          </div>
          <div className="factor-snapshot-table-wrap">
            <div className="section-header-inline sector-list-header strategy-detail-subheader">
              <div>
                <p className="panel-label">Dataset Sources</p>
                <p className="helper">Live FMP history is used first for spot symbols. Futures roots shown here are proxy or approximation paths only, not true continuous futures contracts.</p>
              </div>
            </div>
            <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-history-grid">
              <span>Symbol</span>
              <span>Timeframe</span>
              <span>Source</span>
              <span>Continuous</span>
              <span>Ready</span>
            </div>
            {Object.values(backtestResult.dataset_info).map((item) => (
              <div className="risk-contrib-table-grid factor-shift-data-row strategy-lab-history-grid" key={`dataset-${item.symbol}`}>
                <span className="factor-snapshot-primary">{item.symbol}</span>
                <span>{item.timeframe}</span>
                <span>{item.source}</span>
                <span>{item.continuous ? 'yes' : 'no'}</span>
                <span>{item.ready ? 'ready' : 'missing'}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

    </article>
  )
}

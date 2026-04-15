import { useMemo, useState } from 'react'

import type { EtfRankingResponse } from '../portfolio/types'

const PEER_GROUP_OPTIONS = ['Sector UCITS ETF', 'Bond UCITS ETF', 'Broad Market UCITS ETF', 'Thematic UCITS ETF', 'Commodity UCITS ETF']
const COMPONENT_ORDER = ['momentum', 'benchmark_relative_strength', 'realized_volatility', 'downside_volatility', 'max_drawdown', 'liquidity', 'implementation_fit'] as const

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function formatCountLabel(value: number, singular: string, plural: string) {
  return `${value} ${value === 1 ? singular : plural}`
}

function whyWinnerRows(result: EtfRankingResponse | null) {
  const winner = result?.ranked_universe[0]
  const runnerUp = result?.ranked_universe[1] ?? null
  if (!winner || !runnerUp) return []

  return COMPONENT_ORDER.map((key) => {
    const winnerScore = winner.component_scores[key]
    const runnerScore = runnerUp.component_scores[key]
    if (!winnerScore || !runnerScore) return null
    return {
      key,
      label: winnerScore.label,
      winnerRaw: winnerScore.raw_value,
      runnerRaw: runnerScore.raw_value,
      winnerWeighted: winnerScore.weighted_score,
      runnerWeighted: runnerScore.weighted_score,
      weightedDelta: winnerScore.weighted_score - runnerScore.weighted_score,
    }
  }).filter((item): item is NonNullable<typeof item> => item != null)
}

function comparisonTone(delta: number) {
  if (delta > 0.0001) return 'comparison-tone-positive'
  if (delta < -0.0001) return 'comparison-tone-negative'
  return 'comparison-tone-neutral'
}

function metricTone(value: number | null | undefined, baseline: number | null | undefined, higherIsBetter = true) {
  if (value == null || baseline == null) return 'comparison-tone-neutral'
  if (higherIsBetter) {
    if (value > baseline) return 'comparison-tone-positive'
    if (value < baseline) return 'comparison-tone-negative'
    return 'comparison-tone-neutral'
  }
  if (value < baseline) return 'comparison-tone-positive'
  if (value > baseline) return 'comparison-tone-negative'
  return 'comparison-tone-neutral'
}

function rankingPeerGroup(result: EtfRankingResponse) {
  return result.effective_inputs?.effective_peer_group ?? result.effective_peer_group
}

function rankingConfidence(result: EtfRankingResponse) {
  return result.run_metadata?.confidence ?? result.warnings.confidence
}

function rankingSourceStatus(result: EtfRankingResponse) {
  return result.run_metadata?.source_status ?? result.source_status
}

function rankingExcludedSymbols(result: EtfRankingResponse) {
  return result.effective_inputs?.excluded_symbols ?? result.excluded_symbols
}

export function EtfRankingPanel() {
  const apiBase = useMemo(() => '/api', [])
  const [universe, setUniverse] = useState('IUFS,IUHC,VDST,VUAA')
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [lookbackMonths, setLookbackMonths] = useState('6')
  const [peerGroup, setPeerGroup] = useState('Sector UCITS ETF')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<EtfRankingResponse | null>(null)

  const winner = result?.ranked_universe[0] ?? null
  const runnerUp = result?.ranked_universe[1] ?? null
  const winnerExplanation = whyWinnerRows(result)
  const resolvedPeerGroup = result ? rankingPeerGroup(result) : null
  const resolvedConfidence = result ? rankingConfidence(result) : null
  const resolvedSourceStatus = result ? rankingSourceStatus(result) : null
  const resolvedExcludedSymbols = result ? rankingExcludedSymbols(result) : []

  async function runRanking() {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${apiBase}/strategy-lab/etf-ranking`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          universe: universe.split(',').map((item) => item.trim()).filter(Boolean),
          benchmark_symbol: benchmarkSymbol.trim().toUpperCase(),
          lookback_months: Number(lookbackMonths),
          peer_group: peerGroup || null,
        }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(typeof payload?.detail === 'string' ? payload.detail : 'ETF ranking request failed')
      }
      setResult(payload as EtfRankingResponse)
    } catch (caught) {
      setResult(null)
      setError(caught instanceof Error ? caught.message : 'ETF ranking request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <article className="panel strategy-lab-panel">
      <p className="panel-label">ETF Ranking</p>
      <h2>ETF ranking workspace</h2>
      <p className="lead compact-lead">Compare a current ETF against same-mandate substitutes, rank the eligible options on momentum, path risk, liquidity, and implementation fit, and review whether a stronger replacement candidate exists without turning the tool into a hype screener.</p>

      <section className="dashboard-bottom-grid">
        <div className="split-grid compact-split-grid">
          <div className="summary-card">
            <p className="panel-label">What This Tool Does</p>
            <p className="helper">Use this workspace to rank a shortlist of same-mandate ETFs so you can evaluate whether your current holding has a stronger substitute.</p>
          </div>
          <div className="summary-card">
            <p className="panel-label">How To Read It</p>
            <p className="helper">1. Include the ETF you hold now plus realistic alternatives. 2. Confirm the peer group. 3. Check confidence and exclusions. 4. Compare #1 vs #2 before treating the result as actionable.</p>
          </div>
        </div>
      </section>

      <div className="backtest-builder strategy-lab-builder">
        <section className="dashboard-bottom-grid">
          <div className="split-grid compact-split-grid">
            <div className="summary-card">
              <p className="panel-label">Before You Run</p>
              <p className="helper">This is not an idea screener. Start with a curated comparison set inside one mandate, and include the incumbent ETF you already own if you are evaluating a substitution.</p>
            </div>
          </div>
        </section>

        <div className="split-grid compact-split-grid strategy-lab-config-grid">
          <label className="field-group">
            <span className="field-label">ETF Universe</span>
            <input className="path-input" value={universe} onChange={(event) => setUniverse(event.target.value)} />
            <span className="helper">Include the incumbent ETF you currently hold, plus realistic replacement candidates.</span>
          </label>
          <label className="field-group">
            <span className="field-label">Benchmark</span>
            <input className="path-input" value={benchmarkSymbol} onChange={(event) => setBenchmarkSymbol(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Lookback (months)</span>
            <input className="path-input" value={lookbackMonths} onChange={(event) => setLookbackMonths(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Peer Group</span>
            <select className="path-input" value={peerGroup} onChange={(event) => setPeerGroup(event.target.value)}>
              {PEER_GROUP_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
            <span className="helper">Compare only ETFs inside the same mandate. Peer-group filtering uses instrument category metadata.</span>
          </label>
        </div>

        <div className="dashboard-edit-actions dashboard-edit-actions-compact">
          <button className="primary-button" type="button" onClick={() => void runRanking()} disabled={loading}>{loading ? 'Running...' : 'Run ETF Ranking'}</button>
        </div>
      </div>

      {loading ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Running ETF ranking.</p>
          <p className="helper">Applying peer-group eligibility, deterministic exclusions, component scoring, and ranking warnings from the backend contract.</p>
        </div>
      ) : null}

      {!loading && !result && !error ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Run a ranking pass to review ETF peer-group results.</p>
          <p className="helper">This workspace is read-only. It helps you compare same-mandate substitutes before making a separate portfolio decision elsewhere.</p>
        </div>
      ) : null}

      {error ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">ETF ranking failed.</p>
          <p className="helper">The request did not return a usable ranking payload.</p>
          <p className="helper">{error}</p>
        </div>
      ) : null}

      {result ? (
        <>
          <div className="tab-bar" style={{ justifyContent: 'flex-start', margin: '8px 0 0' }}>
            <span className="backtest-source-badge">Peer Group: {resolvedPeerGroup ?? 'none'}</span>
            <span className="backtest-source-badge">Confidence: {resolvedConfidence}</span>
            <span className="backtest-source-badge">Holdings Support: {resolvedSourceStatus?.holdings_support}</span>
          </div>

          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Replacement Decision</p></div><p className="helper">Start here to see whether the top-ranked ETF looks like a credible substitute, not an automatic switch.</p></div>
            <div className="strategy-lab-summary-grid">
              <div className="strategy-summary-card strategy-summary-card-primary">
                <p className="stat-label">Top Pick</p>
                <p className="summary-value">{winner?.symbol ?? 'n/a'}</p>
                <p className="helper">Highest-ranked eligible substitute in this run</p>
              </div>
              <div className="strategy-summary-card">
                <p className="stat-label">Runner-Up</p>
                <p className="summary-value">{runnerUp?.symbol ?? 'n/a'}</p>
                <p className="helper">Second choice to compare before acting</p>
              </div>
              <div className="strategy-summary-card">
                <p className="stat-label">Confidence</p>
                <p className="summary-value">{resolvedConfidence}</p>
                <p className="helper">Check trust before considering a switch</p>
              </div>
              <div className="strategy-summary-card">
                <p className="stat-label">Ranked</p>
                <p className="summary-value">{result.ranked_universe.length}</p>
                <p className="helper">{formatCountLabel(result.ranked_universe.length, 'eligible ETF', 'eligible ETFs')}</p>
              </div>
              <div className="strategy-summary-card strategy-summary-card-risk">
                <p className="stat-label">Excluded</p>
                <p className="summary-value">{resolvedExcludedSymbols.length}</p>
                <p className="helper">{formatCountLabel(resolvedExcludedSymbols.length, 'deterministic exclusion', 'deterministic exclusions')}</p>
              </div>
              <div className="strategy-summary-card">
                <p className="stat-label">Top Composite</p>
                <p className="summary-value">{formatNumber(winner?.composite_score, 4)}</p>
                <p className="helper">Composite score using the engine's effective component weights</p>
              </div>
            </div>
          </section>

          <section className="dashboard-bottom-grid">
            <div className="summary-card">
              <p className="panel-label">How This Can Improve The Portfolio</p>
              <p className="helper">This tool can improve the portfolio by improving the ETF vehicle inside the same mandate. It helps you check whether the current ETF could be replaced by a stronger implementation of the same job, without changing exposure or allocation.</p>
            </div>
          </section>

          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Trust Checks</p></div><p className="helper">Review confidence, metadata gaps, and warnings before treating the ranking as decision-grade.</p></div>
            <div className="dashboard-summary">
              <div className="summary-card"><p className="stat-label">Warnings</p><p className="summary-value">{result.warnings.warnings.length}</p></div>
              <div className="summary-card"><p className="stat-label">Unknown Metadata</p><p className="summary-value">{result.warnings.unknown_metadata_symbols.length}</p></div>
              <div className="summary-card"><p className="stat-label">Unclassified Peer Group</p><p className="summary-value">{result.warnings.peer_group_unclassified_symbols.length}</p></div>
              <div className="summary-card"><p className="stat-label">Holdings Support</p><p className="summary-value">{resolvedSourceStatus?.holdings_support}</p></div>
            </div>
            <div className="list-table">
              {result.warnings.warnings.length ? result.warnings.warnings.map((warning) => <div className="list-row list-row-wide" key={warning}><span>{warning}</span></div>) : <div className="list-row"><span>No active ranking warnings.</span></div>}
            </div>
          </section>

          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Why #1 Beats #2</p></div><p className="helper">Use this comparison to understand why the top-ranked ETF beat the next-best eligible alternative.</p></div>
            {winner && runnerUp && winnerExplanation.length ? (
              <div className="factor-snapshot-table-wrap">
                <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-why-grid">
                  <span>Component</span>
                  <span>{winner.symbol}</span>
                  <span>{runnerUp.symbol}</span>
                  <span>Weighted Delta</span>
                </div>
                {winnerExplanation.map((item) => (
                  <div className={`risk-contrib-table-grid factor-shift-data-row strategy-lab-why-grid ${comparisonTone(item.weightedDelta)}`} key={item.key}>
                    <span>{item.label}</span>
                    <span>{formatNumber(item.winnerRaw, 2)}</span>
                    <span>{formatNumber(item.runnerRaw, 2)}</span>
                    <span>{formatNumber(item.weightedDelta, 4)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">Need at least two ranked ETFs to explain why the winner ranks first.</p></div>
            )}
          </section>

          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Ranked Universe</p></div><p className="helper">Full ranking of eligible ETFs after peer-group filtering, deterministic exclusions, and warning interpretation.</p></div>
            <div className="factor-snapshot-table-wrap">
              <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-rank-grid-wide">
                <span>Rank</span>
                <span>Symbol</span>
                <span>Category</span>
                <span>Composite</span>
                <span>Momentum</span>
                <span>Rel. Strength</span>
                <span>Vol</span>
                <span>Drawdown</span>
                <span>Liquidity</span>
                <span>Impl. Fit</span>
              </div>
              {result.ranked_universe.map((item) => (
                <div className={`risk-contrib-table-grid factor-shift-data-row strategy-lab-rank-grid-wide ${item.rank === 1 ? 'strategy-ranking-row-top' : ''}`} key={item.symbol}>
                  <span>{item.rank}</span>
                  <span className="strategy-ranking-symbol-cell"><strong>{item.symbol}</strong><small>{item.instrument.sector ?? 'Unknown sector'}</small></span>
                  <span className="strategy-ranking-category-cell">{item.instrument.category ?? 'n/a'}</span>
                  <span className="strategy-ranking-metric-cell"><strong>{formatNumber(item.composite_score, 4)}</strong><small>Composite</small></span>
                  <span className={`strategy-ranking-metric-cell ${metricTone(item.component_scores.momentum?.raw_value, runnerUp?.component_scores.momentum?.raw_value, true)}`}><strong>{formatNumber(item.component_scores.momentum?.raw_value, 2)}</strong><small>Blended</small></span>
                  <span className={`strategy-ranking-metric-cell ${metricTone(item.component_scores.benchmark_relative_strength?.raw_value, runnerUp?.component_scores.benchmark_relative_strength?.raw_value, true)}`}><strong>{formatNumber(item.component_scores.benchmark_relative_strength?.raw_value, 2)}</strong><small>vs benchmark</small></span>
                  <span className={`strategy-ranking-metric-cell ${metricTone(item.component_scores.realized_volatility?.raw_value, runnerUp?.component_scores.realized_volatility?.raw_value, false)}`}><strong>{formatNumber(item.component_scores.realized_volatility?.raw_value, 2)}</strong><small>Lower better</small></span>
                  <span className={`strategy-ranking-metric-cell ${metricTone(item.component_scores.max_drawdown?.raw_value, runnerUp?.component_scores.max_drawdown?.raw_value, false)}`}><strong>{formatNumber(item.component_scores.max_drawdown?.raw_value, 2)}</strong><small>Lower better</small></span>
                  <span className={`strategy-ranking-metric-cell ${metricTone(item.component_scores.liquidity?.raw_value, runnerUp?.component_scores.liquidity?.raw_value, true)}`}><strong>{formatNumber(item.component_scores.liquidity?.raw_value, 2)}</strong><small>Liquidity</small></span>
                  <span className={`strategy-ranking-metric-cell ${metricTone(item.component_scores.implementation_fit?.raw_value, runnerUp?.component_scores.implementation_fit?.raw_value, true)}`}><strong>{formatNumber(item.component_scores.implementation_fit?.raw_value, 2)}</strong><small>Implementation</small></span>
                </div>
              ))}
            </div>
          </section>

          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Excluded Symbols</p></div><p className="helper">Symbols that were evaluated but not ranked. Exclusions are explicit and never silent.</p></div>
            <div className="list-table">
              {resolvedExcludedSymbols.length ? resolvedExcludedSymbols.map((item) => <div className="list-row list-row-wide" key={`${item.symbol}-${item.reason}`}><span>{item.symbol}</span><span>{item.reason}</span></div>) : <div className="list-row"><span>No exclusions.</span></div>}
            </div>
          </section>

          <section className="dashboard-bottom-grid">
            <div className="summary-card">
              <p className="panel-label">Portfolio Use Note</p>
              <p className="helper">Use this ranking to improve implementation within an existing exposure. It does not change allocations or execute a switch; it helps identify whether a stronger ETF candidate exists inside the same mandate.</p>
            </div>
          </section>
        </>
      ) : null}
    </article>
  )
}

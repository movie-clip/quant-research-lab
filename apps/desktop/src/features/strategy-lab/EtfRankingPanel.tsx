import { useMemo, useState } from 'react'

import type { EtfRankingResponse } from '../portfolio/types'
import type { CandidateImprovementSeed, IntentBoundSeededEtfReplacementRankingDraftArtifactInput, IntentBoundSeededEtfReplacementRankingCandidateSnapshot } from '../portfolio/workspaceTypes'

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
  return result.effective_inputs.effective_peer_group
}

function rankingConfidence(result: EtfRankingResponse) {
  return result.run_metadata.confidence
}

function rankingSourceStatus(result: EtfRankingResponse) {
  return result.run_metadata.source_status
}

function rankingExcludedSymbols(result: EtfRankingResponse) {
  return result.effective_inputs.excluded_symbols
}

function rankingBenchmarkSymbol(result: EtfRankingResponse) {
  return result.request.benchmark_symbol
}

function rankingLookbackMonths(result: EtfRankingResponse) {
  return result.request.lookback_months
}

function rankingRequestedUniverse(result: EtfRankingResponse) {
  return result.effective_inputs.requested_universe
}

function buildCandidateImprovementSeed(result: EtfRankingResponse, row: EtfRankingResponse['ranked_universe'][number], baseSymbol: string): CandidateImprovementSeed {
  return {
    kind: 'etf_replacement_candidate',
    source: 'etf_ranking',
    seededAt: new Date().toISOString(),
    baseSymbol,
    candidateSymbol: row.symbol,
    candidateRank: row.rank,
    peerGroup: result.effective_inputs.effective_peer_group,
    benchmarkSymbol: rankingBenchmarkSymbol(result),
    lookbackMonths: rankingLookbackMonths(result),
    rankingId: result.run_metadata.ranking_id,
    methodologyId: result.run_metadata.methodology_id,
    rankingBasisDate: result.run_metadata.ranking_basis_date,
    confidence: result.run_metadata.confidence,
    holdingsSupport: result.run_metadata.source_status.holdings_support,
    requestUniverse: rankingRequestedUniverse(result),
    evaluatedUniverse: result.effective_inputs.evaluated_universe,
    warningCount: result.warnings.warnings.length,
    excludedSymbolsCount: result.effective_inputs.excluded_symbols.length,
  }
}

function buildRankingCandidateSnapshot(row: EtfRankingResponse['ranked_universe'][number]): IntentBoundSeededEtfReplacementRankingCandidateSnapshot {
  return {
    symbol: row.symbol,
    rank: row.rank,
    compositeScore: row.composite_score,
    instrument: {
      name: row.instrument.name,
      assetClass: row.instrument.asset_class,
      sector: row.instrument.sector,
      category: row.instrument.category,
      currency: row.instrument.currency,
    },
  }
}

function buildIntentBoundSeededRankingArtifact(
  result: EtfRankingResponse,
  row: EtfRankingResponse['ranked_universe'][number],
  baseSymbol: string,
): IntentBoundSeededEtfReplacementRankingDraftArtifactInput {
  const topCandidate = result.ranked_universe[0] ?? null
  const runnerUpCandidate = result.ranked_universe[1] ?? null
  return {
    kind: 'intent_bound_seeded_etf_replacement_ranking',
    source: 'etf_ranking',
    selectedAt: new Date().toISOString(),
    baseSymbol,
    candidateSymbol: row.symbol,
    candidateRank: row.rank,
    rankingId: result.run_metadata.ranking_id,
    methodologyId: result.run_metadata.methodology_id,
    rankingBasisDate: result.run_metadata.ranking_basis_date,
    benchmarkSymbol: rankingBenchmarkSymbol(result),
    lookbackMonths: rankingLookbackMonths(result),
    peerGroup: result.effective_inputs.effective_peer_group,
    confidence: result.run_metadata.confidence,
    holdingsSupport: result.run_metadata.source_status.holdings_support,
    requestUniverse: rankingRequestedUniverse(result),
    evaluatedUniverse: result.effective_inputs.evaluated_universe,
    warnings: result.warnings.warnings,
    excludedSymbols: result.effective_inputs.excluded_symbols,
    selectedCandidate: buildRankingCandidateSnapshot(row),
    topCandidate: topCandidate ? buildRankingCandidateSnapshot(topCandidate) : null,
    runnerUpCandidate: runnerUpCandidate ? buildRankingCandidateSnapshot(runnerUpCandidate) : null,
  }
}

type EtfRankingPanelProps = {
  draftSymbols?: string[]
  onSeedCandidateDraft?: (input: { seed: CandidateImprovementSeed; rankingArtifact: IntentBoundSeededEtfReplacementRankingDraftArtifactInput | null }) => void
}

export function EtfRankingPanel({ draftSymbols = [], onSeedCandidateDraft }: EtfRankingPanelProps) {
  const apiBase = useMemo(() => '/api', [])
  const [universe, setUniverse] = useState('IUFS,IUHC,VDST,VUAA')
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [lookbackMonths, setLookbackMonths] = useState('6')
  const [peerGroup, setPeerGroup] = useState('Sector UCITS ETF')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<EtfRankingResponse | null>(null)
  const [seedTarget, setSeedTarget] = useState<EtfRankingResponse['ranked_universe'][number] | null>(null)
  const [selectedBaseSymbol, setSelectedBaseSymbol] = useState('')
  const [seedSuccess, setSeedSuccess] = useState<string | null>(null)

  const winner = result?.ranked_universe[0] ?? null
  const runnerUp = result?.ranked_universe[1] ?? null
  const winnerExplanation = whyWinnerRows(result)
  const resolvedPeerGroup = result ? rankingPeerGroup(result) : null
  const resolvedConfidence = result ? rankingConfidence(result) : null
  const resolvedSourceStatus = result ? rankingSourceStatus(result) : null
  const resolvedExcludedSymbols = result ? rankingExcludedSymbols(result) : []
  const incumbentOptions = useMemo(() => Array.from(new Set(draftSymbols.map((symbol) => symbol.trim().toUpperCase()).filter(Boolean))).sort(), [draftSymbols])

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
      setSeedTarget(null)
      setSelectedBaseSymbol('')
      setSeedSuccess(null)
    } catch (caught) {
      setResult(null)
      setError(caught instanceof Error ? caught.message : 'ETF ranking request failed')
    } finally {
      setLoading(false)
    }
  }

  function openSeedDraftConfirmation(row: EtfRankingResponse['ranked_universe'][number]) {
    setSeedTarget(row)
    setSelectedBaseSymbol('')
    setSeedSuccess(null)
  }

  function confirmSeedDraft() {
    if (!result || !seedTarget || !selectedBaseSymbol || selectedBaseSymbol === seedTarget.symbol) return
    onSeedCandidateDraft?.({
      seed: buildCandidateImprovementSeed(result, seedTarget, selectedBaseSymbol),
      rankingArtifact: buildIntentBoundSeededRankingArtifact(result, seedTarget, selectedBaseSymbol),
    })
    setSeedSuccess('Candidate draft created for review.')
    setSeedTarget(null)
    setSelectedBaseSymbol('')
  }

  return (
    <article className="panel strategy-lab-panel">
      <p className="panel-label">ETF Ranking</p>
      <h2>ETF ranking workspace</h2>
      <p className="lead compact-lead">Rank same-mandate ETF substitutes and review whether the current holding has a stronger replacement candidate.</p>

      <div className="backtest-builder strategy-lab-builder">
        <div className="split-grid compact-split-grid strategy-lab-config-grid">
          <label className="field-group">
            <span className="field-label">ETF Universe</span>
            <input className="path-input" value={universe} onChange={(event) => setUniverse(event.target.value)} />
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
          </label>
        </div>

        <div className="dashboard-edit-actions dashboard-edit-actions-compact">
          <button className={`primary-button${loading ? ' button-loading' : ''}`} type="button" onClick={() => void runRanking()} disabled={loading}>{loading ? 'Running...' : 'Run ETF Ranking'}</button>
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
          <p className="helper">Compare same-mandate substitutes before carrying one into a draft review.</p>
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

          {seedSuccess ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="helper">{seedSuccess}</p>
            </div>
          ) : null}

          {seedTarget ? (
            <section className="dashboard-bottom-grid">
              <div className="summary-card">
                <p className="panel-label">Create candidate improvement draft</p>
                <p className="helper">Carry the selected ETF and ranking context into a draft review.</p>
                <label className="field-group">
                  <span className="field-label">Incumbent ETF</span>
                  <select className="path-input" value={selectedBaseSymbol} onChange={(event) => setSelectedBaseSymbol(event.target.value)}>
                    <option value="">Select incumbent ETF</option>
                    {incumbentOptions.map((symbol) => <option key={symbol} value={symbol}>{symbol}</option>)}
                  </select>
                </label>
                {incumbentOptions.length ? null : <p className="helper">No active draft holdings are available for incumbent selection.</p>}
                <div className="dashboard-summary compact-summary-grid">
                  <div className="summary-card"><p className="stat-label">Selected ETF</p><p className="summary-value">{seedTarget.symbol}</p></div>
                  <div className="summary-card"><p className="stat-label">Source</p><p className="summary-value">ETF Ranking</p></div>
                  <div className="summary-card"><p className="stat-label">Peer Group</p><p className="summary-value">{resolvedPeerGroup ?? 'none'}</p></div>
                  <div className="summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{rankingBenchmarkSymbol(result)}</p></div>
                  <div className="summary-card"><p className="stat-label">Lookback</p><p className="summary-value">{rankingLookbackMonths(result)}</p></div>
                  <div className="summary-card"><p className="stat-label">Confidence</p><p className="summary-value">{resolvedConfidence}</p></div>
                  <div className="summary-card"><p className="stat-label">Warnings</p><p className="summary-value">{result.warnings.warnings.length}</p></div>
                  <div className="summary-card"><p className="stat-label">Exclusions</p><p className="summary-value">{resolvedExcludedSymbols.length}</p></div>
                </div>
                <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
                  <button className="primary-button" type="button" onClick={confirmSeedDraft} disabled={!selectedBaseSymbol || selectedBaseSymbol === seedTarget.symbol}>Create Draft</button>
                  <button className="secondary-button" type="button" onClick={() => { setSeedTarget(null); setSelectedBaseSymbol('') }}>Cancel</button>
                </div>
                {selectedBaseSymbol === seedTarget.symbol ? <p className="helper">Incumbent and candidate must be different symbols.</p> : null}
              </div>
            </section>
          ) : null}

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
              <p className="panel-label">Portfolio Fit</p>
              <p className="helper">Use ranking to check whether the same mandate has a stronger ETF implementation.</p>
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
                  <span className="strategy-ranking-symbol-cell"><strong>{item.symbol}</strong><small>{item.instrument.sector ?? 'Unknown sector'}</small><button className="secondary-button" type="button" onClick={() => openSeedDraftConfirmation(item)} disabled={!incumbentOptions.length}>Seed Candidate Draft</button><small>Carry into draft review.</small></span>
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
              <p className="helper">Ranking stays review-only until you carry a candidate into a draft.</p>
            </div>
          </section>
        </>
      ) : null}
    </article>
  )
}

import { useEffect, useMemo, useRef, useState } from 'react'

import type { EtfRankingArtifact, EtfRankingArtifactRecentMetadata, EtfRankingArtifactRecentRow, EtfRankingResponse } from '../portfolio/types'
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
  const rankedUniverse = result?.ranked_universe ?? []
  const winner = rankedUniverse[0] ?? null
  const runnerUp = rankedUniverse[1] ?? null
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
  return result.effective_inputs?.effective_peer_group ?? null
}

function rankingConfidence(result: EtfRankingResponse) {
  return result.run_metadata?.confidence ?? null
}

function rankingSourceStatus(result: EtfRankingResponse) {
  return result.run_metadata?.source_status ?? null
}

function rankingExcludedSymbols(result: EtfRankingResponse) {
  return result.effective_inputs?.excluded_symbols ?? []
}

function rankingBenchmarkSymbol(result: EtfRankingResponse) {
  return result.request?.benchmark_symbol ?? 'n/a'
}

function rankingLookbackMonths(result: EtfRankingResponse) {
  return result.request?.lookback_months ?? 'n/a'
}

function rankingRequestedUniverse(result: EtfRankingResponse) {
  return result.effective_inputs?.requested_universe ?? []
}

async function readJsonResponse<T>(response: Response, fallbackMessage: string) {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(typeof payload === 'object' && payload != null && 'detail' in payload && typeof payload.detail === 'string' ? payload.detail : fallbackMessage)
  }
  return payload as T
}

function buildCandidateImprovementSeed(result: EtfRankingResponse, row: EtfRankingResponse['ranked_universe'][number], baseSymbol: string): CandidateImprovementSeed {
  const warnings = result.warnings ?? { warnings: [] as string[] }
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
    warningCount: warnings.warnings.length,
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
    warnings: result.warnings?.warnings ?? [],
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
  const resultRequestOwnerRef = useRef(0)
  const [universe, setUniverse] = useState('IUFS,IUHC,VDST,VUAA')
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [lookbackMonths, setLookbackMonths] = useState('6')
  const [peerGroup, setPeerGroup] = useState('Sector UCITS ETF')
  const [runLoading, setRunLoading] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [result, setResult] = useState<EtfRankingArtifact | null>(null)
  const [resultSource, setResultSource] = useState<'fresh' | 'recent' | null>(null)
  const [recentMetadataLoading, setRecentMetadataLoading] = useState(false)
  const [recentMetadataError, setRecentMetadataError] = useState<string | null>(null)
  const [recentMetadata, setRecentMetadata] = useState<EtfRankingArtifactRecentMetadata | null>(null)
  const [selectedRecentPeerGroup, setSelectedRecentPeerGroup] = useState('')
  const [recentRunsLoading, setRecentRunsLoading] = useState(false)
  const [recentRunsError, setRecentRunsError] = useState<string | null>(null)
  const [recentRuns, setRecentRuns] = useState<EtfRankingArtifactRecentRow[]>([])
  const [artifactLoadingId, setArtifactLoadingId] = useState<string | null>(null)
  const [artifactLoadError, setArtifactLoadError] = useState<string | null>(null)
  const [seedTarget, setSeedTarget] = useState<EtfRankingResponse['ranked_universe'][number] | null>(null)
  const [selectedBaseSymbol, setSelectedBaseSymbol] = useState('')
  const [seedSuccess, setSeedSuccess] = useState<string | null>(null)

  const rankedUniverse = result?.ranked_universe ?? []
  const winner = rankedUniverse[0] ?? null
  const runnerUp = rankedUniverse[1] ?? null
  const winnerExplanation = whyWinnerRows(result)
  const resolvedPeerGroup = result ? rankingPeerGroup(result) : null
  const resolvedConfidence = result ? rankingConfidence(result) : null
  const resolvedSourceStatus = result ? rankingSourceStatus(result) : null
  const resolvedExcludedSymbols = result ? rankingExcludedSymbols(result) : []
  const incumbentOptions = useMemo(() => Array.from(new Set(draftSymbols.map((symbol) => symbol.trim().toUpperCase()).filter(Boolean))).sort(), [draftSymbols])

  async function loadRecentMetadata() {
    setRecentMetadataLoading(true)
    setRecentMetadataError(null)
    try {
      const response = await fetch(`${apiBase}/strategy-lab/etf-ranking/artifacts/recent/metadata`)
      const payload = await readJsonResponse<EtfRankingArtifactRecentMetadata>(response, 'Recent ETF ranking metadata is unavailable')
      setRecentMetadata(payload)
      if (selectedRecentPeerGroup && !payload.available_effective_peer_groups.includes(selectedRecentPeerGroup)) {
        setSelectedRecentPeerGroup('')
      }
    } catch (caught) {
      setRecentMetadata(null)
      setRecentMetadataError(caught instanceof Error ? caught.message : 'Recent ETF ranking metadata is unavailable')
    } finally {
      setRecentMetadataLoading(false)
    }
  }

  async function loadRecentRuns(effectivePeerGroup: string) {
    setRecentRunsLoading(true)
    setRecentRunsError(null)
    try {
      const search = new URLSearchParams()
      if (effectivePeerGroup) search.set('effective_peer_group', effectivePeerGroup)
      const query = search.toString()
      const response = await fetch(`${apiBase}/strategy-lab/etf-ranking/artifacts/recent${query ? `?${query}` : ''}`)
      const payload = await readJsonResponse<EtfRankingArtifactRecentRow[]>(response, 'Recent ETF ranking runs are unavailable')
      setRecentRuns(payload)
    } catch (caught) {
      setRecentRuns([])
      setRecentRunsError(caught instanceof Error ? caught.message : 'Recent ETF ranking runs are unavailable')
    } finally {
      setRecentRunsLoading(false)
    }
  }

  useEffect(() => {
    void loadRecentMetadata()
  }, [])

  useEffect(() => {
    void loadRecentRuns(selectedRecentPeerGroup)
  }, [selectedRecentPeerGroup])

  function beginResultRequest(nextSource: 'fresh' | 'recent', artifactId?: string) {
    const owner = resultRequestOwnerRef.current + 1
    resultRequestOwnerRef.current = owner
    setRunLoading(nextSource === 'fresh')
    setArtifactLoadingId(nextSource === 'recent' ? artifactId ?? null : null)
    setRunError(null)
    setArtifactLoadError(null)
    setSeedTarget(null)
    setSelectedBaseSymbol('')
    setSeedSuccess(null)
    return owner
  }

  function isActiveResultRequest(owner: number) {
    return resultRequestOwnerRef.current === owner
  }

  async function runRanking() {
    const owner = beginResultRequest('fresh')
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
      const payload = await readJsonResponse<EtfRankingArtifact>(response, 'ETF ranking request failed')
      if (!isActiveResultRequest(owner)) return
      setResult(payload)
      setResultSource('fresh')
      setRunLoading(false)
      void loadRecentMetadata()
      void loadRecentRuns(selectedRecentPeerGroup)
    } catch (caught) {
      if (!isActiveResultRequest(owner)) return
      setRunError(caught instanceof Error ? caught.message : 'ETF ranking request failed')
      setRunLoading(false)
    } finally {
      if (isActiveResultRequest(owner)) {
        setRunLoading(false)
      }
    }
  }

  async function loadRecentArtifact(artifactId: string) {
    const owner = beginResultRequest('recent', artifactId)
    try {
      const response = await fetch(`${apiBase}/strategy-lab/etf-ranking/artifacts/${encodeURIComponent(artifactId)}`)
      const payload = await readJsonResponse<EtfRankingArtifact>(response, 'ETF ranking artifact could not be loaded')
      if (!isActiveResultRequest(owner)) return
      setResult(payload)
      setResultSource('recent')
      setArtifactLoadingId(null)
    } catch (caught) {
      if (!isActiveResultRequest(owner)) return
      setArtifactLoadError(caught instanceof Error ? caught.message : 'ETF ranking artifact could not be loaded')
      setArtifactLoadingId(null)
    } finally {
      if (isActiveResultRequest(owner)) {
        setArtifactLoadingId(null)
      }
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
          <button className={`primary-button${runLoading ? ' button-loading' : ''}`} type="button" onClick={() => void runRanking()}>{runLoading ? 'Running...' : 'Run ETF Ranking'}</button>
        </div>
      </div>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Recent Runs</p></div><p className="helper">Filter persisted ranking artifacts by discovered peer group and load one into the same review path.</p></div>
        <div className="summary-card">
          <div className="split-grid compact-split-grid strategy-lab-config-grid">
            <label className="field-group">
              <span className="field-label">Peer Group Filter</span>
              <select className="path-input" value={selectedRecentPeerGroup} onChange={(event) => setSelectedRecentPeerGroup(event.target.value)} disabled={recentMetadataLoading}>
                <option value="">All peer groups</option>
                {(recentMetadata?.available_effective_peer_groups ?? []).map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <div className="field-group">
              <span className="field-label">Discovery Source</span>
              <p className="helper">Backend metadata routes define the filter list and recent artifact availability.</p>
            </div>
          </div>
          <div className="dashboard-edit-actions dashboard-edit-actions-compact">
            <button className="secondary-button" type="button" onClick={() => { void loadRecentMetadata(); void loadRecentRuns(selectedRecentPeerGroup) }} disabled={recentMetadataLoading || recentRunsLoading}>Refresh Recent Runs</button>
          </div>

          {recentMetadataLoading && !recentMetadata ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Loading recent-run filters.</p>
              <p className="helper">Requesting available peer groups from artifact discovery metadata.</p>
            </div>
          ) : null}

          {recentMetadataError ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Recent-run filters are unavailable.</p>
              <p className="helper">Artifact discovery metadata could not be loaded.</p>
              <p className="helper">{recentMetadataError}</p>
            </div>
          ) : null}

          {artifactLoadError ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Recent artifact load failed.</p>
              <p className="helper">The selected persisted ranking artifact could not be opened.</p>
              <p className="helper">{artifactLoadError}</p>
            </div>
          ) : null}

          {recentRunsLoading ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Loading recent ETF ranking runs.</p>
              <p className="helper">Reading persisted ranking artifact summaries from the backend discovery route.</p>
            </div>
          ) : null}

          {!recentRunsLoading && recentRunsError ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Recent ETF ranking runs are unavailable.</p>
              <p className="helper">The recent artifacts list could not be loaded.</p>
              <p className="helper">{recentRunsError}</p>
            </div>
          ) : null}

          {!recentRunsLoading && !recentRunsError && !recentRuns.length ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">No recent ETF ranking runs found.</p>
              <p className="helper">Run a ranking pass or widen the peer-group filter to load a persisted artifact.</p>
            </div>
          ) : null}

          {!recentRunsLoading && !recentRunsError && recentRuns.length ? (
            <div className="factor-snapshot-table-wrap">
              <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-rank-grid-wide">
                <span>As Of</span>
                <span>Peer Group</span>
                <span>Benchmark</span>
                <span>Lookback</span>
                <span>Confidence</span>
                <span>Universe</span>
                <span>Evaluated</span>
                <span>Artifact</span>
                <span>Action</span>
              </div>
              {recentRuns.map((item) => {
                const isLoaded = resultSource === 'recent' && result?.artifact_id === item.artifact_id
                const isLoadingArtifact = artifactLoadingId === item.artifact_id
                return (
                  <div className={`risk-contrib-table-grid factor-shift-data-row strategy-lab-rank-grid-wide ${isLoaded ? 'strategy-ranking-row-top' : ''}`} key={item.artifact_id}>
                    <span>{item.ranking_basis_date}</span>
                    <span>{item.effective_peer_group ?? 'Unspecified'}</span>
                    <span>{item.benchmark_symbol}</span>
                    <span>{item.lookback_months}</span>
                    <span>{item.confidence}</span>
                    <span>{item.universe_size}</span>
                    <span>{item.evaluated_universe_size}</span>
                    <span>{item.artifact_id}</span>
                    <span className="strategy-ranking-symbol-cell"><button className={`secondary-button${isLoadingArtifact ? ' button-loading' : ''}`} type="button" onClick={() => void loadRecentArtifact(item.artifact_id)} disabled={isLoadingArtifact}>{isLoadingArtifact ? 'Loading...' : isLoaded ? 'Loaded' : 'Load Run'}</button><small>Open persisted result.</small></span>
                  </div>
                )
              })}
            </div>
          ) : null}
        </div>
      </section>

      {runLoading ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Running ETF ranking.</p>
          <p className="helper">Applying peer-group eligibility, deterministic exclusions, component scoring, and ranking warnings from the backend contract.</p>
        </div>
      ) : null}

      {!runLoading && !result && !runError ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Run a ranking pass to review ETF peer-group results.</p>
          <p className="helper">Compare same-mandate substitutes before carrying one into a draft review.</p>
        </div>
      ) : null}

      {runError ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">ETF ranking failed.</p>
          <p className="helper">The request did not return a usable ranking payload.</p>
          <p className="helper">{runError}</p>
        </div>
      ) : null}

      {result ? (
        <>
          <div className="tab-bar" style={{ justifyContent: 'flex-start', margin: '8px 0 0' }}>
            <span className="backtest-source-badge">Source: {resultSource === 'recent' ? 'Recent Artifact' : 'Fresh Run'}</span>
            {result.artifact_id ? <span className="backtest-source-badge">Artifact: {result.artifact_id}</span> : null}
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
                  <div className="summary-card"><p className="stat-label">Warnings</p><p className="summary-value">{result.warnings?.warnings.length ?? 0}</p></div>
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
                <p className="summary-value">{rankedUniverse.length}</p>
                <p className="helper">{formatCountLabel(rankedUniverse.length, 'eligible ETF', 'eligible ETFs')}</p>
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
              <div className="summary-card"><p className="stat-label">Warnings</p><p className="summary-value">{result.warnings?.warnings.length ?? 0}</p></div>
              <div className="summary-card"><p className="stat-label">Unknown Metadata</p><p className="summary-value">{result.warnings?.unknown_metadata_symbols.length ?? 0}</p></div>
              <div className="summary-card"><p className="stat-label">Unclassified Peer Group</p><p className="summary-value">{result.warnings?.peer_group_unclassified_symbols.length ?? 0}</p></div>
              <div className="summary-card"><p className="stat-label">Holdings Support</p><p className="summary-value">{resolvedSourceStatus?.holdings_support}</p></div>
            </div>
            <div className="list-table">
              {result.warnings?.warnings.length ? result.warnings.warnings.map((warning) => <div className="list-row list-row-wide" key={warning}><span>{warning}</span></div>) : <div className="list-row"><span>No active ranking warnings.</span></div>}
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
              {rankedUniverse.map((item) => (
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

import { useEffect, useMemo, useRef, useState } from 'react'

import {
  applySessionStateUpdate,
  createEtfRankingPanelState,
  type EtfRankingPanelState,
  type SessionStateUpdate,
} from '../portfolio/workspaceResearchSessionState'
import type {
  ConstructionArtifactRunResponse,
  ConstructionDiscoveredPolicy,
  ConstructionRankingArtifactPreflightResponse,
  EtfRankingArtifact,
  EtfRankingArtifactRecentMetadata,
  EtfRankingArtifactRecentRow,
  EtfRankingResponse,
  RankingArtifactOpenResponse,
  RankingArtifactPreflightResponse,
} from '../portfolio/types'
import type { CandidateImprovementSeed, IntentBoundSeededEtfReplacementRankingDraftArtifactInput, IntentBoundSeededEtfReplacementRankingCandidateSnapshot } from '../portfolio/workspaceTypes'
import {
  buildConstructionPolicyRunInput,
  RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N,
  useConstructionPolicyCatalog,
} from '../backtest/constructionPolicyCatalog'
import {
  DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT,
  DEFAULT_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT,
  validateRankingConstructionPositionWeightInputs,
} from '../backtest/rankingConstructionMaxPositionWeight'
import { runRankingArtifactConstructionHandoff } from '../backtest/rankingArtifactConstructionHandoff'

const PEER_GROUP_OPTIONS = ['Sector UCITS ETF', 'Bond UCITS ETF', 'Broad Market UCITS ETF', 'Thematic UCITS ETF', 'Commodity UCITS ETF']
const COMPONENT_ORDER = ['momentum', 'benchmark_relative_strength', 'realized_volatility', 'downside_volatility', 'max_drawdown', 'liquidity', 'implementation_fit'] as const

type GeneralizedRankingRecentResponse = {
  items?: Array<{
    artifact_kind?: unknown
    artifact_id?: unknown
    ranking_id?: unknown
    methodology_id?: unknown
    as_of_date?: unknown
    ranking_basis_date?: unknown
    etf_summary?: {
      benchmark_symbol?: unknown
      lookback_months?: unknown
      effective_peer_group?: unknown
      universe_size?: unknown
      evaluated_universe_size?: unknown
      confidence?: unknown
    } | null
    replacement_summary?: unknown
  }>
  metadata?: {
    applied_filters?: {
      artifact_kind?: unknown
    }
  }
}

function parseEtfRecentRunsFromGeneralizedResponse(payload: GeneralizedRankingRecentResponse): EtfRankingArtifactRecentRow[] {
  if (payload.metadata?.applied_filters?.artifact_kind !== 'etf_ranking') {
    throw new Error('Recent ETF ranking runs returned unsupported discovery scope')
  }
  if (!Array.isArray(payload.items)) {
    throw new Error('Recent ETF ranking runs returned malformed discovery payload')
  }
  return payload.items.map((item) => {
    if (item.artifact_kind !== 'etf_ranking') {
      throw new Error('Recent ETF ranking runs returned non-ETF artifact rows')
    }
    if (item.replacement_summary != null || !item.etf_summary) {
      throw new Error('Recent ETF ranking runs returned malformed ETF summaries')
    }
    const summary = item.etf_summary
    if (
      typeof item.artifact_id !== 'string'
      || typeof item.ranking_id !== 'string'
      || typeof item.methodology_id !== 'string'
      || typeof item.as_of_date !== 'string'
      || typeof item.ranking_basis_date !== 'string'
      || typeof summary.benchmark_symbol !== 'string'
      || typeof summary.lookback_months !== 'number'
      || !(typeof summary.effective_peer_group === 'string' || summary.effective_peer_group === null)
      || typeof summary.universe_size !== 'number'
      || typeof summary.evaluated_universe_size !== 'number'
      || !['high', 'medium', 'low'].includes(String(summary.confidence))
    ) {
      throw new Error('Recent ETF ranking runs returned invalid ETF row metadata')
    }
    return {
      artifact_id: item.artifact_id,
      ranking_id: item.ranking_id,
      methodology_id: item.methodology_id,
      as_of_date: item.as_of_date,
      ranking_basis_date: item.ranking_basis_date,
      benchmark_symbol: summary.benchmark_symbol,
      lookback_months: summary.lookback_months,
      universe_size: summary.universe_size,
      evaluated_universe_size: summary.evaluated_universe_size,
      effective_peer_group: summary.effective_peer_group,
      confidence: summary.confidence as 'high' | 'medium' | 'low',
    }
  })
}

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

function resolveEtfRankingArtifactFromOpenResponse(
  preflight: RankingArtifactPreflightResponse,
  openResponse: RankingArtifactOpenResponse,
): EtfRankingArtifact {
  if (JSON.stringify(openResponse.open_handoff) !== JSON.stringify(preflight.open_handoff)) {
    throw new Error('Ranking artifact open must reuse the exact preflight handoff')
  }
  if (openResponse.open_handoff.artifact_id !== preflight.artifact.artifact_id) {
    throw new Error('Ranking artifact open returned a mismatched artifact identity')
  }
  if (openResponse.review_payload_kind !== openResponse.review_payload.review_payload_kind) {
    throw new Error('Ranking artifact open returned a mismatched review payload discriminator')
  }
  if (openResponse.review_payload.review_payload_kind !== 'etf_ranking_review_payload_v1') {
    throw new Error(`Ranking artifact open returned unsupported review payload kind ${openResponse.review_payload.review_payload_kind}`)
  }
  if (openResponse.review_payload.artifact_kind !== 'etf_ranking') {
    throw new Error('Ranking artifact open returned an unsupported artifact kind for ETF review')
  }
  if (openResponse.review_payload.artifact_id !== preflight.artifact.artifact_id) {
    throw new Error('Ranking artifact open review payload identity does not match preflight')
  }
  if (openResponse.review_payload.schema_version !== preflight.artifact.schema_version) {
    throw new Error('Ranking artifact open review payload schema_version does not match preflight')
  }
  if (openResponse.review_payload.artifact.artifact_id !== preflight.artifact.artifact_id) {
    throw new Error('Ranking artifact open artifact body identity does not match preflight')
  }
  return openResponse.review_payload.artifact
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
    openHandoff: {
      handoff_kind: 'ranking_artifact_open_handoff_v1',
      artifact_kind: 'etf_ranking',
      artifact_id: (result as EtfRankingArtifact).artifact_id,
      schema_version: (result as EtfRankingArtifact).schema_version,
    },
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
  currentPortfolio?: {
    artifact_id: string
    as_of_timestamp: string
    weights: Array<{ symbol: string; weight: number }>
  } | null
  onSeedCandidateDraft?: (input: { seed: CandidateImprovementSeed; rankingArtifact: IntentBoundSeededEtfReplacementRankingDraftArtifactInput | null }) => void
  onReviewInConstruction?: (input: {
    rankingArtifactId: string
    preflight: ConstructionRankingArtifactPreflightResponse
    run: ConstructionArtifactRunResponse
  }) => void | Promise<void>
  requestedRecentArtifactId?: string | null
  onConsumeRequestedRecentArtifactId?: () => void
  sessionState?: EtfRankingPanelState
  onSessionStateChange?: (update: SessionStateUpdate<EtfRankingPanelState>) => void
}

function policyNameForReview(policyId: string, policies: ConstructionDiscoveredPolicy[]) {
  return policies.find((policy) => policy.policy_id === policyId)?.name ?? policyId
}

export function EtfRankingPanel({ draftSymbols = [], currentPortfolio = null, onSeedCandidateDraft, onReviewInConstruction, requestedRecentArtifactId = null, onConsumeRequestedRecentArtifactId, sessionState, onSessionStateChange }: EtfRankingPanelProps) {
  const apiBase = useMemo(() => '/api', [])
  const resultRequestOwnerRef = useRef(0)
  const [internalSessionState, setInternalSessionState] = useState<EtfRankingPanelState>(() => createEtfRankingPanelState())
  const [constructionReviewLoadingId, setConstructionReviewLoadingId] = useState<string | null>(null)
  const [constructionReviewError, setConstructionReviewError] = useState<string | null>(null)
  const [selectedConstructionPolicyId, setSelectedConstructionPolicyId] = useState<string>('')
  const resolvedSessionState = sessionState ?? internalSessionState
  const constructionPolicyCatalog = useConstructionPolicyCatalog(apiBase)
  const setSessionState = (update: SessionStateUpdate<EtfRankingPanelState>) => {
    if (onSessionStateChange) {
      onSessionStateChange(update)
      return
    }
    setInternalSessionState((current) => applySessionStateUpdate(current, update))
  }
  const {
    universe,
    benchmarkSymbol,
    lookbackMonths,
    peerGroup,
    constructionMaxPositionWeight,
    constructionMinPositionWeight,
    runLoading,
    runError,
    result,
    resultSource,
    recentMetadataLoading,
    recentMetadataError,
    recentMetadata,
    selectedRecentPeerGroup,
    recentRunsLoading,
    recentRunsError,
    recentRuns,
    artifactLoadingId,
    artifactLoadError,
    seedTarget,
    selectedBaseSymbol,
    seedSuccess,
  } = resolvedSessionState

  const rankedUniverse = result?.ranked_universe ?? []
  const winner = rankedUniverse[0] ?? null
  const runnerUp = rankedUniverse[1] ?? null
  const winnerExplanation = whyWinnerRows(result)
  const resolvedPeerGroup = result ? rankingPeerGroup(result) : null
  const resolvedConfidence = result ? rankingConfidence(result) : null
  const resolvedSourceStatus = result ? rankingSourceStatus(result) : null
  const resolvedExcludedSymbols = result ? rankingExcludedSymbols(result) : []
  const incumbentOptions = useMemo(() => Array.from(new Set(draftSymbols.map((symbol) => symbol.trim().toUpperCase()).filter(Boolean))).sort(), [draftSymbols])
  const resolvedConstructionMaxPositionWeight = constructionMaxPositionWeight ?? DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT
  const resolvedConstructionMinPositionWeight = constructionMinPositionWeight ?? DEFAULT_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT

  const constructionPositionWeightValidation = useMemo(
    () => validateRankingConstructionPositionWeightInputs({
      maxPositionWeightInput: resolvedConstructionMaxPositionWeight,
      minPositionWeightInput: resolvedConstructionMinPositionWeight,
    }),
    [resolvedConstructionMaxPositionWeight, resolvedConstructionMinPositionWeight],
  )
  const constructionMaxPositionWeightValidation = constructionPositionWeightValidation.maxPositionWeight
  const constructionMinPositionWeightValidation = constructionPositionWeightValidation.minPositionWeight

  useEffect(() => {
    if (constructionPolicyCatalog.status !== 'ready') return
    setSelectedConstructionPolicyId((current) => {
      if (current && constructionPolicyCatalog.policies.some((policy) => policy.policy_id === current)) {
        return current
      }
      return constructionPolicyCatalog.defaultPolicyId ?? ''
    })
  }, [constructionPolicyCatalog.defaultPolicyId, constructionPolicyCatalog.policies, constructionPolicyCatalog.status])

  async function loadRecentMetadata() {
    setSessionState((current) => ({ ...current, recentMetadataLoading: true, recentMetadataError: null }))
    try {
      const response = await fetch(`${apiBase}/strategy-lab/etf-ranking/artifacts/recent/metadata`)
      const payload = await readJsonResponse<EtfRankingArtifactRecentMetadata>(response, 'Recent ETF ranking metadata is unavailable')
      setSessionState((current) => ({
        ...current,
        recentMetadata: payload,
        selectedRecentPeerGroup: current.selectedRecentPeerGroup && !payload.available_effective_peer_groups.includes(current.selectedRecentPeerGroup)
          ? ''
          : current.selectedRecentPeerGroup,
      }))
    } catch (caught) {
      setSessionState((current) => ({
        ...current,
        recentMetadata: null,
        recentMetadataError: caught instanceof Error ? caught.message : 'Recent ETF ranking metadata is unavailable',
      }))
    } finally {
      setSessionState((current) => ({ ...current, recentMetadataLoading: false }))
    }
  }

  async function loadRecentRuns(effectivePeerGroup: string) {
    setSessionState((current) => ({ ...current, recentRunsLoading: true, recentRunsError: null }))
    try {
      const search = new URLSearchParams()
      search.set('artifact_kind', 'etf_ranking')
      if (effectivePeerGroup) search.set('effective_peer_group', effectivePeerGroup)
      const query = search.toString()
      const response = await fetch(`${apiBase}/strategy-lab/ranking-artifacts/recent?${query}`)
      const payload = await readJsonResponse<GeneralizedRankingRecentResponse>(response, 'Recent ETF ranking runs are unavailable')
      const recentRuns = parseEtfRecentRunsFromGeneralizedResponse(payload)
      setSessionState((current) => ({ ...current, recentRuns }))
    } catch (caught) {
      setSessionState((current) => ({
        ...current,
        recentRuns: [],
        recentRunsError: caught instanceof Error ? caught.message : 'Recent ETF ranking runs are unavailable',
      }))
    } finally {
      setSessionState((current) => ({ ...current, recentRunsLoading: false }))
    }
  }

  useEffect(() => {
    void loadRecentMetadata()
  }, [])

  useEffect(() => {
    void loadRecentRuns(selectedRecentPeerGroup)
  }, [selectedRecentPeerGroup])

  useEffect(() => {
    if (!requestedRecentArtifactId) return
    onConsumeRequestedRecentArtifactId?.()
    void loadRecentArtifact(requestedRecentArtifactId)
  }, [requestedRecentArtifactId])

  function beginResultRequest(nextSource: 'fresh' | 'recent', artifactId?: string) {
    const owner = resultRequestOwnerRef.current + 1
    resultRequestOwnerRef.current = owner
    setSessionState((current) => ({
      ...current,
      runLoading: nextSource === 'fresh',
      artifactLoadingId: nextSource === 'recent' ? artifactId ?? null : null,
      runError: null,
      artifactLoadError: null,
      seedTarget: null,
      selectedBaseSymbol: '',
      seedSuccess: null,
    }))
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
      setSessionState((current) => ({ ...current, result: payload, resultSource: 'fresh', runLoading: false }))
      void loadRecentMetadata()
      void loadRecentRuns(selectedRecentPeerGroup)
    } catch (caught) {
      if (!isActiveResultRequest(owner)) return
      setSessionState((current) => ({
        ...current,
        runError: caught instanceof Error ? caught.message : 'ETF ranking request failed',
        runLoading: false,
      }))
    } finally {
      if (isActiveResultRequest(owner)) {
        setSessionState((current) => ({ ...current, runLoading: false }))
      }
    }
  }

  async function loadRecentArtifact(artifactId: string) {
    const owner = beginResultRequest('recent', artifactId)
    try {
      const preflightResponse = await fetch(`${apiBase}/strategy-lab/ranking-artifacts/preflight/${encodeURIComponent(artifactId)}`, {
        method: 'POST',
      })
      const preflight = await readJsonResponse<RankingArtifactPreflightResponse>(preflightResponse, 'ETF ranking artifact preflight failed')
      const openResponse = await fetch(`${apiBase}/strategy-lab/ranking-artifacts/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preflight.open_handoff),
      })
      const opened = await readJsonResponse<RankingArtifactOpenResponse>(openResponse, 'ETF ranking artifact could not be opened')
      const payload = resolveEtfRankingArtifactFromOpenResponse(preflight, opened)
      if (!isActiveResultRequest(owner)) return
      setSessionState((current) => ({ ...current, result: payload, resultSource: 'recent', artifactLoadingId: null }))
    } catch (caught) {
      if (!isActiveResultRequest(owner)) return
      setSessionState((current) => ({
        ...current,
        artifactLoadError: caught instanceof Error ? caught.message : 'ETF ranking artifact could not be loaded',
        artifactLoadingId: null,
      }))
    } finally {
      if (isActiveResultRequest(owner)) {
        setSessionState((current) => ({ ...current, artifactLoadingId: null }))
      }
    }
  }

  async function reviewRecentArtifactInConstruction(artifactId: string) {
    if (constructionMaxPositionWeightValidation.value == null) {
      setConstructionReviewError(constructionMaxPositionWeightValidation.error)
      return
    }
    if (constructionMinPositionWeightValidation.error) {
      setConstructionReviewError(constructionMinPositionWeightValidation.error)
      return
    }
    if (!currentPortfolio) {
      setConstructionReviewError('Review In Construction requires an active workspace draft and current portfolio.')
      return
    }
    const selectedPolicy = buildConstructionPolicyRunInput(
      selectedConstructionPolicyId,
      RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N,
    )
    if (!selectedPolicy) {
      setConstructionReviewError('Review In Construction requires selecting a compatible construction policy.')
      return
    }
    setConstructionReviewLoadingId(artifactId)
    setConstructionReviewError(null)
    try {
      const handoff = await runRankingArtifactConstructionHandoff({
        apiBase,
        artifactId,
        maxPositionWeight: constructionMaxPositionWeightValidation.value,
        minPositionWeight: constructionMinPositionWeightValidation.value,
        currentPortfolio,
        policy: selectedPolicy,
      })
      await onReviewInConstruction?.({ rankingArtifactId: artifactId, preflight: handoff.preflight, run: handoff.run })
    } catch (caught) {
      setConstructionReviewError(caught instanceof Error ? caught.message : 'ETF ranking construction handoff failed')
    } finally {
      setConstructionReviewLoadingId(null)
    }
  }

  function openSeedDraftConfirmation(row: EtfRankingResponse['ranked_universe'][number]) {
    setSessionState((current) => ({ ...current, seedTarget: row, selectedBaseSymbol: '', seedSuccess: null }))
  }

  function confirmSeedDraft() {
    if (!result || !seedTarget || !selectedBaseSymbol || selectedBaseSymbol === seedTarget.symbol) return
    onSeedCandidateDraft?.({
      seed: buildCandidateImprovementSeed(result, seedTarget, selectedBaseSymbol),
      rankingArtifact: buildIntentBoundSeededRankingArtifact(result, seedTarget, selectedBaseSymbol),
    })
    setSessionState((current) => ({ ...current, seedSuccess: 'Candidate draft created for review.', seedTarget: null, selectedBaseSymbol: '' }))
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
            <input className="path-input" value={universe} onChange={(event) => setSessionState((current) => ({ ...current, universe: event.target.value }))} />
          </label>
          <label className="field-group">
            <span className="field-label">Benchmark</span>
            <input className="path-input" value={benchmarkSymbol} onChange={(event) => setSessionState((current) => ({ ...current, benchmarkSymbol: event.target.value }))} />
          </label>
          <label className="field-group">
            <span className="field-label">Lookback (months)</span>
            <input className="path-input" value={lookbackMonths} onChange={(event) => setSessionState((current) => ({ ...current, lookbackMonths: event.target.value }))} />
          </label>
          <label className="field-group">
            <span className="field-label">Peer Group</span>
            <select className="path-input" value={peerGroup} onChange={(event) => setSessionState((current) => ({ ...current, peerGroup: event.target.value }))}>
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
              <select className="path-input" value={selectedRecentPeerGroup} onChange={(event) => setSessionState((current) => ({ ...current, selectedRecentPeerGroup: event.target.value }))} disabled={recentMetadataLoading}>
                <option value="">All peer groups</option>
                {(recentMetadata?.available_effective_peer_groups ?? []).map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label className="field-group">
              <span className="field-label">Construction Policy</span>
              <select className="path-input" value={selectedConstructionPolicyId} onChange={(event) => setSelectedConstructionPolicyId(event.target.value)} disabled={constructionPolicyCatalog.status === 'loading' || constructionPolicyCatalog.status === 'error'}>
                <option value="">Select compatible policy</option>
                {constructionPolicyCatalog.policies.map((policy) => <option key={policy.policy_id} value={policy.policy_id}>{policy.name}</option>)}
              </select>
            </label>
            <label className="field-group">
              <span className="field-label">Max Position Weight</span>
              <input aria-label="Max Position Weight" className="path-input" value={resolvedConstructionMaxPositionWeight} onChange={(event) => setSessionState((current) => ({ ...current, constructionMaxPositionWeight: event.target.value }))} />
               <p className="helper">Decimal weight only. Must stay between 0.5 and 1 while the shipped ranking launch keeps top_n fixed at 2.</p>
              {constructionMaxPositionWeightValidation.error ? <p className="helper">{constructionMaxPositionWeightValidation.error}</p> : null}
            </label>
            <label className="field-group">
              <span className="field-label">Min Position Weight (optional)</span>
              <input aria-label="Min Position Weight (optional)" className="path-input" value={resolvedConstructionMinPositionWeight} onChange={(event) => setSessionState((current) => ({ ...current, constructionMinPositionWeight: event.target.value }))} />
              <p className="helper">Leave blank to omit. If set, use a decimal greater than 0 and up to 0.5, and no higher than max.</p>
              {constructionMinPositionWeightValidation.error ? <p className="helper">{constructionMinPositionWeightValidation.error}</p> : null}
            </label>
            <div className="field-group">
              <span className="field-label">Policy Source</span>
               <p className="helper">Authoritative `/construction/policies` discovery defines the compatible review-only policy set and the fixed top_n=2 launch boundary.</p>
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

          {constructionReviewError ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Construction review handoff failed.</p>
              <p className="helper">The selected ETF ranking artifact could not be handed into construction review.</p>
              <p className="helper">{constructionReviewError}</p>
            </div>
          ) : null}

          {constructionPolicyCatalog.status === 'loading' ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Loading construction policies.</p>
              <p className="helper">Requesting authoritative compatible policy discovery for review-only construction.</p>
            </div>
          ) : null}

          {constructionPolicyCatalog.status === 'error' ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Construction policies are unavailable.</p>
              <p className="helper">Review In Construction is blocked until authoritative policy discovery succeeds.</p>
              <p className="helper">{constructionPolicyCatalog.error}</p>
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
                const constructionReviewBlockedReason = constructionMaxPositionWeightValidation.error
                  ?? constructionMinPositionWeightValidation.error
                  ?? (!currentPortfolio
                    ? 'Open a workspace with an authoritative current portfolio to review this ranking in construction'
                    : null)
                  ?? (constructionPolicyCatalog.status === 'error'
                    ? constructionPolicyCatalog.error ?? 'Construction policy catalog unavailable'
                    : constructionPolicyCatalog.status === 'loading'
                      ? 'Loading construction policies...'
                      : !selectedConstructionPolicyId
                        ? 'Select a compatible construction policy'
                        : null)
                const selectedPolicyLabel = selectedConstructionPolicyId
                  ? policyNameForReview(selectedConstructionPolicyId, constructionPolicyCatalog.policies)
                  : null
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
                    <span className="strategy-ranking-symbol-cell"><button className={`secondary-button${isLoadingArtifact ? ' button-loading' : ''}`} type="button" onClick={() => void loadRecentArtifact(item.artifact_id)} disabled={isLoadingArtifact}>{isLoadingArtifact ? 'Loading...' : isLoaded ? 'Loaded' : 'Load Run'}</button><button className={`secondary-button${constructionReviewLoadingId === item.artifact_id ? ' button-loading' : ''}`} type="button" onClick={() => void reviewRecentArtifactInConstruction(item.artifact_id)} disabled={constructionReviewLoadingId === item.artifact_id || constructionReviewBlockedReason != null} title={constructionReviewBlockedReason ?? 'Ready for construction review'}>{constructionReviewLoadingId === item.artifact_id ? 'Opening...' : 'Review In Construction'}</button><small>{constructionReviewBlockedReason ?? (selectedPolicyLabel ? `Ready for construction review with ${selectedPolicyLabel}` : 'Ready for construction review')}</small></span>
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
                    <select className="path-input" value={selectedBaseSymbol} onChange={(event) => setSessionState((current) => ({ ...current, selectedBaseSymbol: event.target.value }))}>
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
                  <button className="secondary-button" type="button" onClick={() => setSessionState((current) => ({ ...current, seedTarget: null, selectedBaseSymbol: '' }))}>Cancel</button>
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

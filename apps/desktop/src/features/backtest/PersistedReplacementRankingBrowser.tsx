import { useEffect, useMemo, useRef, useState } from 'react'

import { PersistedReplacementRankingReview } from '../portfolio/PersistedReplacementRankingReview'
import {
  buildConstructionPolicyRunInput,
  getConstructionLaunchPolicyReadback,
  useConstructionPolicyCatalog,
} from './constructionPolicyCatalog'
import {
  DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT,
  DEFAULT_RANKING_CONSTRUCTION_MAX_SECTOR_WEIGHT,
  DEFAULT_RANKING_CONSTRUCTION_MAX_TRADE_INTENT_COUNT,
  DEFAULT_RANKING_CONSTRUCTION_MAX_TURNOVER_WEIGHT,
  DEFAULT_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT,
  DEFAULT_RANKING_CONSTRUCTION_TOP_N,
  validateRankingConstructionConstraintInputs,
  validateRankingConstructionTopNInput,
} from './rankingConstructionMaxPositionWeight'
import { runRankingArtifactConstructionHandoff } from './rankingArtifactConstructionHandoff'
import type {
  ConstructionRankingArtifactPreflightResponse,
  ConstructionDiscoveredPolicy,
  IntentBoundEtfReplacementRankingArtifact,
  IntentBoundEtfReplacementRankingIneligiblePreflightResponse,
  IntentBoundEtfReplacementRankingSupportedOpenResponse,
  IntentBoundEtfReplacementRankingSupportedPreflightResponse,
  RankingArtifactOpenResponse,
  RankingArtifactPreflightResponse,
} from '../portfolio/types'

type GeneralizedReplacementRecentResponse = {
  items?: Array<{
    artifact_kind?: unknown
    artifact_id?: unknown
    ranking_id?: unknown
    methodology_id?: unknown
    as_of_date?: unknown
    ranking_basis_date?: unknown
    etf_summary?: unknown
    replacement_summary?: {
      basis_date?: unknown
      status?: unknown
      base_symbol?: unknown
      candidate_symbol?: unknown
      peer_group?: unknown
      eligible_count?: unknown
      excluded_count?: unknown
      confidence?: unknown
    } | null
  }>
  metadata?: {
    applied_filters?: {
      artifact_kind?: unknown
    }
  }
}

function formatConstructionPolicyReadback(policyId: string, policies: ConstructionDiscoveredPolicy[]) {
  const readback = getConstructionLaunchPolicyReadback(policyId, policies)
  if (!readback) return null
  return `${readback.policyName} (${readback.statusLabel}); fixed top_n=${readback.topN}; requires ${readback.requiredConstraint}; optional ${readback.optionalConstraints.join(', ')}`
}

type ReplacementRecentRow = {
  artifact_id: string
  ranking_id: string
  methodology_id: string
  as_of_date: string
  ranking_basis_date: string
  basis_date: string
  status: 'ok' | 'unavailable'
  base_symbol: string
  candidate_symbol: string
  peer_group: string
  eligible_count: number
  excluded_count: number
  confidence: 'high' | 'medium' | 'low'
}

type RecentState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  items: ReplacementRecentRow[]
  error: string | null
}

type OpenState = {
  status: 'idle' | 'preflighting' | 'opening' | 'ready' | 'error'
  targetArtifactId: string | null
  preflight: IntentBoundEtfReplacementRankingSupportedPreflightResponse | null
  openedArtifact: IntentBoundEtfReplacementRankingSupportedOpenResponse | null
  error: string | null
}

type ConstructionReviewState = {
  status: 'idle' | 'running' | 'error'
  targetArtifactId: string | null
  error: string | null
}

type ConstructionReadinessState = Record<string, {
  status: 'idle' | 'loading' | 'ready' | 'error'
  response: ConstructionRankingArtifactPreflightResponse | null
  error: string | null
}>

function isSupportedReplacementPreflightResponse(
  payload: RankingArtifactPreflightResponse,
): payload is IntentBoundEtfReplacementRankingSupportedPreflightResponse {
  return payload.artifact.artifact_kind === 'intent_bound_etf_replacement_ranking'
    && payload.artifact.schema_version === 'intent_bound_etf_replacement_ranking_artifact_v1'
    && payload.eligibility.review_truth_basis === 'authoritative_persisted_ranking_artifact'
    && payload.eligibility.review_scope === 'artifact_backed_review_only'
    && payload.eligibility.open_supported === true
    && payload.eligibility.replay_eligible === true
    && payload.eligibility.consumer_handoff_supported === true
    && payload.eligibility.ineligibility_reason == null
}

function isIneligibleReplacementPreflightResponse(
  payload: RankingArtifactPreflightResponse,
): payload is IntentBoundEtfReplacementRankingIneligiblePreflightResponse {
  return payload.artifact.artifact_kind === 'intent_bound_etf_replacement_ranking'
    && payload.artifact.schema_version === 'intent_bound_etf_replacement_ranking_artifact_v1'
    && payload.eligibility.review_truth_basis === 'authoritative_persisted_ranking_artifact'
    && payload.eligibility.review_scope === 'artifact_backed_review_only'
    && payload.eligibility.open_supported === false
    && payload.eligibility.replay_eligible === false
    && payload.eligibility.consumer_handoff_supported === false
    && typeof payload.eligibility.ineligibility_reason === 'string'
}

function readJsonResponse<T>(response: Response, fallbackMessage: string) {
  return response.json()
    .catch(() => null)
    .then((payload) => {
      if (!response.ok) {
        throw new Error(typeof payload === 'object' && payload != null && 'detail' in payload && typeof payload.detail === 'string' ? payload.detail : fallbackMessage)
      }
      return payload as T
    })
}

function parseReplacementRecentRunsFromGeneralizedResponse(payload: GeneralizedReplacementRecentResponse): ReplacementRecentRow[] {
  if (payload.metadata?.applied_filters?.artifact_kind !== 'intent_bound_etf_replacement_ranking') {
    throw new Error('Recent replacement ranking runs returned unsupported discovery scope')
  }
  if (!Array.isArray(payload.items)) {
    throw new Error('Recent replacement ranking runs returned malformed discovery payload')
  }
  return payload.items.map((item) => {
    if (item.artifact_kind !== 'intent_bound_etf_replacement_ranking') {
      throw new Error('Recent replacement ranking runs returned non-replacement artifact rows')
    }
    if (item.etf_summary != null || !item.replacement_summary) {
      throw new Error('Recent replacement ranking runs returned malformed replacement summaries')
    }
    const summary = item.replacement_summary
    if (
      typeof item.artifact_id !== 'string'
      || typeof item.ranking_id !== 'string'
      || typeof item.methodology_id !== 'string'
      || typeof item.as_of_date !== 'string'
      || typeof item.ranking_basis_date !== 'string'
      || typeof summary.basis_date !== 'string'
      || !['ok', 'unavailable'].includes(String(summary.status))
      || typeof summary.base_symbol !== 'string'
      || typeof summary.candidate_symbol !== 'string'
      || typeof summary.peer_group !== 'string'
      || typeof summary.eligible_count !== 'number'
      || typeof summary.excluded_count !== 'number'
      || !['high', 'medium', 'low'].includes(String(summary.confidence))
    ) {
      throw new Error('Recent replacement ranking runs returned invalid replacement row metadata')
    }
    return {
      artifact_id: item.artifact_id,
      ranking_id: item.ranking_id,
      methodology_id: item.methodology_id,
      as_of_date: item.as_of_date,
      ranking_basis_date: item.ranking_basis_date,
      basis_date: summary.basis_date,
      status: summary.status as 'ok' | 'unavailable',
      base_symbol: summary.base_symbol,
      candidate_symbol: summary.candidate_symbol,
      peer_group: summary.peer_group,
      eligible_count: summary.eligible_count,
      excluded_count: summary.excluded_count,
      confidence: summary.confidence as 'high' | 'medium' | 'low',
    }
  })
}

function assertValidReplacementPreflightResponse(
  payload: RankingArtifactPreflightResponse,
): IntentBoundEtfReplacementRankingSupportedPreflightResponse | IntentBoundEtfReplacementRankingIneligiblePreflightResponse {
  if (payload.artifact.artifact_kind !== 'intent_bound_etf_replacement_ranking') {
    throw new Error('Replacement ranking preflight returned unsupported artifact kind')
  }
  if (payload.artifact.schema_version !== 'intent_bound_etf_replacement_ranking_artifact_v1') {
    throw new Error('Replacement ranking preflight returned unsupported schema_version')
  }
  if (payload.eligibility.review_truth_basis !== 'authoritative_persisted_ranking_artifact') {
    throw new Error('Replacement ranking preflight returned unsupported review truth basis')
  }
  if (payload.eligibility.review_scope !== 'artifact_backed_review_only') {
    throw new Error('Replacement ranking preflight returned unsupported review scope')
  }
  if (payload.eligibility.open_supported !== payload.eligibility.replay_eligible) {
    throw new Error('Replacement ranking preflight must keep open_supported and replay_eligible aligned')
  }
  if (payload.eligibility.consumer_handoff_supported !== payload.eligibility.open_supported) {
    throw new Error('Replacement ranking preflight must keep consumer_handoff_supported aligned with open_supported')
  }
  if (isIneligibleReplacementPreflightResponse(payload)) {
    return payload
  }
  if (!payload.eligibility.open_supported) {
    throw new Error('Replacement ranking preflight must fail closed with an ineligibility reason')
  }
  if (isSupportedReplacementPreflightResponse(payload)) {
    return payload
  }
  throw new Error('Replacement ranking preflight returned ineligibility_reason for an eligible artifact')
}

function assertMatchingConsumerHandoff(
  artifact: IntentBoundEtfReplacementRankingArtifact,
  openResponse: IntentBoundEtfReplacementRankingSupportedOpenResponse,
) {
  const handoff = openResponse.consumer_handoff
  const selectedCandidate = artifact.ranked_candidates.find((candidate) => candidate.symbol === artifact.lineage.candidate_symbol) ?? null
  if (handoff.artifact_kind !== 'intent_bound_etf_replacement_ranking' || handoff.schema_version !== artifact.schema_version) {
    throw new Error('Replacement ranking open returned a mismatched consumer handoff identity')
  }
  if (
    handoff.artifact_id !== artifact.artifact_id
    || handoff.ranking_id !== artifact.ranking_id
    || handoff.methodology_id !== artifact.methodology_id
    || handoff.basis_date !== artifact.basis_date
    || handoff.draft_id !== artifact.lineage.draft_id
    || handoff.workspace_id !== artifact.lineage.workspace_id
    || handoff.base_node_id !== artifact.lineage.base_node_id
    || handoff.base_symbol !== artifact.lineage.base_symbol
    || handoff.candidate_symbol !== artifact.lineage.candidate_symbol
    || handoff.seed_ranking_id !== artifact.lineage.seed_ranking_id
    || handoff.seed_methodology_id !== artifact.lineage.seed_methodology_id
    || handoff.seed_ranking_basis_date !== artifact.lineage.seed_ranking_basis_date
    || handoff.peer_group !== artifact.lineage.peer_group
    || handoff.benchmark_symbol !== artifact.lineage.benchmark_symbol
    || handoff.lookback_months !== artifact.lineage.lookback_months
    || handoff.eligible_count !== artifact.eligible_count
    || handoff.excluded_count !== artifact.excluded_count
  ) {
    throw new Error('Replacement ranking open consumer handoff does not match artifact lineage')
  }
  if (
    handoff.selected_candidate.symbol !== artifact.lineage.candidate_symbol
    || handoff.selected_candidate.rank !== (selectedCandidate?.rank ?? handoff.selected_candidate.rank)
    || handoff.selected_candidate.composite_score !== (selectedCandidate?.composite_score ?? handoff.selected_candidate.composite_score)
    || handoff.selected_candidate.basis_date !== artifact.basis_date
    || handoff.selected_candidate.draft_id !== artifact.lineage.draft_id
    || handoff.selected_candidate.base_node_id !== artifact.lineage.base_node_id
    || handoff.selected_candidate.base_symbol !== artifact.lineage.base_symbol
    || handoff.selected_candidate.seed_ranking_id !== artifact.lineage.seed_ranking_id
    || handoff.selected_candidate.seed_methodology_id !== artifact.lineage.seed_methodology_id
  ) {
    throw new Error('Replacement ranking open selected candidate does not match artifact lineage')
  }
}

function assertValidReplacementOpenResponse(
  preflight: IntentBoundEtfReplacementRankingSupportedPreflightResponse,
  openResponse: RankingArtifactOpenResponse,
) {
  if (JSON.stringify(openResponse.open_handoff) !== JSON.stringify(preflight.open_handoff)) {
    throw new Error('Replacement ranking open must reuse the exact preflight handoff')
  }
  if (openResponse.review_payload_kind !== openResponse.review_payload.review_payload_kind) {
    throw new Error('Replacement ranking open returned a mismatched review payload discriminator')
  }
  if (openResponse.review_payload.review_payload_kind !== 'intent_bound_etf_replacement_ranking_review_payload_v1') {
    throw new Error(`Replacement ranking open returned unsupported review payload kind ${openResponse.review_payload.review_payload_kind}`)
  }
  if (openResponse.review_payload.artifact_kind !== 'intent_bound_etf_replacement_ranking') {
    throw new Error('Replacement ranking open returned unsupported artifact kind')
  }
  if (openResponse.review_payload.artifact_id !== preflight.artifact.artifact_id) {
    throw new Error('Replacement ranking open review payload identity does not match preflight')
  }
  if (openResponse.review_payload.schema_version !== preflight.artifact.schema_version) {
    throw new Error('Replacement ranking open review payload schema_version does not match preflight')
  }
  if (openResponse.review_payload.review_truth_basis !== 'authoritative_persisted_ranking_artifact') {
    throw new Error('Replacement ranking open returned unsupported review truth basis')
  }
  if (openResponse.review_payload.review_scope !== 'artifact_backed_review_only') {
    throw new Error('Replacement ranking open returned unsupported review scope')
  }
  const artifact = openResponse.review_payload.artifact
  if (
    artifact.artifact_id !== preflight.artifact.artifact_id
    || artifact.schema_version !== preflight.artifact.schema_version
    || artifact.ranking_id !== preflight.artifact.ranking_id
    || artifact.methodology_id !== preflight.artifact.methodology_id
    || artifact.run_metadata.as_of_date !== preflight.artifact.as_of_date
    || artifact.run_metadata.ranking_basis_date !== preflight.artifact.ranking_basis_date
  ) {
    throw new Error('Replacement ranking open artifact body does not match preflight identity')
  }
  if (!('consumer_handoff' in openResponse) || !openResponse.consumer_handoff) {
    throw new Error('Replacement ranking open must include a consumer handoff when preflight says supported')
  }
  assertMatchingConsumerHandoff(artifact, openResponse as IntentBoundEtfReplacementRankingSupportedOpenResponse)
  return openResponse as IntentBoundEtfReplacementRankingSupportedOpenResponse
}

export function PersistedReplacementRankingBrowser({
  currentPortfolio = null,
  onOpenConstructionReview,
}: {
  currentPortfolio?: {
    artifact_id: string
    as_of_timestamp: string
    weights: Array<{ symbol: string; weight: number }>
  } | null
  onOpenConstructionReview?: (constructionArtifactId: string) => void | Promise<void>
}) {
  const apiBase = '/api'
  const constructionPolicyCatalog = useConstructionPolicyCatalog(apiBase)
  const recentRequestOwnerRef = useRef(0)
  const openRequestOwnerRef = useRef(0)
  const constructionRequestOwnerRef = useRef(0)
  const [recentState, setRecentState] = useState<RecentState>({ status: 'idle', items: [], error: null })
  const [openState, setOpenState] = useState<OpenState>({
    status: 'idle',
    targetArtifactId: null,
    preflight: null,
    openedArtifact: null,
    error: null,
  })
  const [constructionReviewState, setConstructionReviewState] = useState<ConstructionReviewState>({
    status: 'idle',
    targetArtifactId: null,
    error: null,
  })
  const [constructionReadinessState, setConstructionReadinessState] = useState<ConstructionReadinessState>({})
  const [selectedConstructionPolicyId, setSelectedConstructionPolicyId] = useState<string>('')
  const [constructionMaxPositionWeight, setConstructionMaxPositionWeight] = useState(DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT)
  const [constructionMinPositionWeight, setConstructionMinPositionWeight] = useState(DEFAULT_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT)
  const [constructionMaxTurnoverWeight, setConstructionMaxTurnoverWeight] = useState(DEFAULT_RANKING_CONSTRUCTION_MAX_TURNOVER_WEIGHT)
  const [constructionMaxTradeIntentCount, setConstructionMaxTradeIntentCount] = useState(DEFAULT_RANKING_CONSTRUCTION_MAX_TRADE_INTENT_COUNT)
  const [constructionMaxSectorWeight, setConstructionMaxSectorWeight] = useState(DEFAULT_RANKING_CONSTRUCTION_MAX_SECTOR_WEIGHT)
  const [constructionTopN, setConstructionTopN] = useState(DEFAULT_RANKING_CONSTRUCTION_TOP_N)
  const constructionTopNValidation = useMemo(
    () => validateRankingConstructionTopNInput(constructionTopN),
    [constructionTopN],
  )
  const constructionConstraintValidation = useMemo(
    () => validateRankingConstructionConstraintInputs({
      maxPositionWeightInput: constructionMaxPositionWeight,
      minPositionWeightInput: constructionMinPositionWeight,
      maxTurnoverWeightInput: constructionMaxTurnoverWeight,
      maxTradeIntentCountInput: constructionMaxTradeIntentCount,
      maxSectorWeightInput: constructionMaxSectorWeight,
    }),
    [constructionMaxPositionWeight, constructionMinPositionWeight, constructionMaxTradeIntentCount, constructionMaxTurnoverWeight, constructionMaxSectorWeight],
  )
  const constructionMaxPositionWeightValidation = constructionConstraintValidation.maxPositionWeight
  const constructionMinPositionWeightValidation = constructionConstraintValidation.minPositionWeight
  const constructionMaxTurnoverWeightValidation = constructionConstraintValidation.maxTurnoverWeight
  const constructionMaxTradeIntentCountValidation = constructionConstraintValidation.maxTradeIntentCount
  const constructionMaxSectorWeightValidation = constructionConstraintValidation.maxSectorWeight
  const selectedConstructionPolicyReadback = useMemo(
    () => formatConstructionPolicyReadback(selectedConstructionPolicyId, constructionPolicyCatalog.policies),
    [constructionPolicyCatalog.policies, selectedConstructionPolicyId],
  )

  useEffect(() => {
    if (constructionPolicyCatalog.status !== 'ready') return
    setSelectedConstructionPolicyId((current) => {
      if (current && constructionPolicyCatalog.policies.some((policy) => policy.policy_id === current)) {
        return current
      }
      return constructionPolicyCatalog.defaultPolicyId ?? ''
    })
  }, [constructionPolicyCatalog.defaultPolicyId, constructionPolicyCatalog.policies, constructionPolicyCatalog.status])

  async function loadConstructionReadiness(artifactId: string) {
    setConstructionReadinessState((current) => ({
      ...current,
      [artifactId]: { status: 'loading', response: null, error: null },
    }))
    try {
      const response = await fetch(`${apiBase}/construction/ranking-artifacts/preflight/${encodeURIComponent(artifactId)}`, {
        method: 'POST',
      })
      const payload = await readJsonResponse<ConstructionRankingArtifactPreflightResponse>(response, 'Replacement ranking construction readiness is unavailable')
      setConstructionReadinessState((current) => ({
        ...current,
        [artifactId]: { status: 'ready', response: payload, error: null },
      }))
    } catch (caught) {
      setConstructionReadinessState((current) => ({
        ...current,
        [artifactId]: { status: 'error', response: null, error: caught instanceof Error ? caught.message : 'Replacement ranking construction readiness is unavailable' },
      }))
    }
  }

  async function loadRecentArtifacts() {
    const owner = recentRequestOwnerRef.current + 1
    recentRequestOwnerRef.current = owner
    setRecentState((current) => ({ ...current, status: 'loading', error: null }))
    try {
      const response = await fetch(`${apiBase}/strategy-lab/ranking-artifacts/recent?artifact_kind=intent_bound_etf_replacement_ranking`)
      const payload = await readJsonResponse<GeneralizedReplacementRecentResponse>(response, 'Recent replacement ranking reviews are unavailable')
      const items = parseReplacementRecentRunsFromGeneralizedResponse(payload)
      if (recentRequestOwnerRef.current !== owner) return
      setRecentState({ status: 'ready', items, error: null })
      void Promise.all(items.map(async (item) => loadConstructionReadiness(item.artifact_id)))
    } catch (caught) {
      if (recentRequestOwnerRef.current !== owner) return
      setRecentState({ status: 'error', items: [], error: caught instanceof Error ? caught.message : 'Recent replacement ranking reviews are unavailable' })
    }
  }

  useEffect(() => {
    void loadRecentArtifacts()
  }, [])

  async function openArtifact(artifactId: string) {
    const owner = openRequestOwnerRef.current + 1
    openRequestOwnerRef.current = owner
    setOpenState({
      status: 'preflighting',
      targetArtifactId: artifactId,
      preflight: null,
      openedArtifact: null,
      error: null,
    })
    try {
      const preflightResponse = await fetch(`${apiBase}/strategy-lab/ranking-artifacts/preflight/${encodeURIComponent(artifactId)}`, {
        method: 'POST',
      })
      const preflightPayload = await readJsonResponse<RankingArtifactPreflightResponse>(preflightResponse, 'Replacement ranking artifact preflight failed')
      const preflight = assertValidReplacementPreflightResponse(preflightPayload)
      if (openRequestOwnerRef.current !== owner) return
      if (isIneligibleReplacementPreflightResponse(preflight)) {
        setOpenState({
          status: 'error',
          targetArtifactId: artifactId,
          preflight: null,
          openedArtifact: null,
          error: preflight.eligibility.ineligibility_reason,
        })
        return
      }
      setOpenState({
        status: 'opening',
        targetArtifactId: artifactId,
        preflight,
        openedArtifact: null,
        error: null,
      })
      const openResponse = await fetch(`${apiBase}/strategy-lab/ranking-artifacts/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preflight.open_handoff),
      })
      const openPayload = await readJsonResponse<RankingArtifactOpenResponse>(openResponse, 'Replacement ranking artifact could not be opened')
      const openedArtifact = assertValidReplacementOpenResponse(preflight, openPayload)
      if (openRequestOwnerRef.current !== owner) return
      setOpenState({ status: 'ready', targetArtifactId: artifactId, preflight, openedArtifact, error: null })
    } catch (caught) {
      if (openRequestOwnerRef.current !== owner) return
      setOpenState({
        status: 'error',
        targetArtifactId: artifactId,
        preflight: null,
        openedArtifact: null,
        error: caught instanceof Error ? caught.message : 'Replacement ranking artifact could not be opened',
      })
    }
  }

  async function reviewInConstruction(artifactId: string) {
    if (constructionMaxPositionWeightValidation.value == null) {
      setConstructionReviewState({ status: 'error', targetArtifactId: artifactId, error: constructionMaxPositionWeightValidation.error })
      return
    }
    if (constructionMinPositionWeightValidation.error) {
      setConstructionReviewState({ status: 'error', targetArtifactId: artifactId, error: constructionMinPositionWeightValidation.error })
      return
    }
    if (constructionMaxTurnoverWeightValidation.error) {
      setConstructionReviewState({ status: 'error', targetArtifactId: artifactId, error: constructionMaxTurnoverWeightValidation.error })
      return
    }
    if (constructionMaxTradeIntentCountValidation.error) {
      setConstructionReviewState({ status: 'error', targetArtifactId: artifactId, error: constructionMaxTradeIntentCountValidation.error })
      return
    }
    if (constructionMaxSectorWeightValidation.error) {
      setConstructionReviewState({ status: 'error', targetArtifactId: artifactId, error: constructionMaxSectorWeightValidation.error })
      return
    }
    if (constructionTopNValidation.value == null) {
      setConstructionReviewState({ status: 'error', targetArtifactId: artifactId, error: constructionTopNValidation.error })
      return
    }
    if (!currentPortfolio) {
      setConstructionReviewState({ status: 'error', targetArtifactId: artifactId, error: 'Review In Construction requires an active workspace draft and current portfolio.' })
      return
    }
    const selectedPolicy = buildConstructionPolicyRunInput(
      selectedConstructionPolicyId,
      constructionTopNValidation.value,
    )
    if (!selectedPolicy) {
      setConstructionReviewState({ status: 'error', targetArtifactId: artifactId, error: 'Review In Construction requires selecting a compatible construction policy.' })
      return
    }
    const owner = constructionRequestOwnerRef.current + 1
    constructionRequestOwnerRef.current = owner
    setConstructionReviewState({ status: 'running', targetArtifactId: artifactId, error: null })
    try {
      const handoff = await runRankingArtifactConstructionHandoff({
        apiBase,
        artifactId,
        maxPositionWeight: constructionMaxPositionWeightValidation.value,
        minPositionWeight: constructionMinPositionWeightValidation.value,
        maxTurnoverWeight: constructionMaxTurnoverWeightValidation.value,
        maxTradeIntentCount: constructionMaxTradeIntentCountValidation.value,
        maxSectorWeight: constructionMaxSectorWeightValidation.value,
        currentPortfolio,
        policy: selectedPolicy,
      })
      if (constructionRequestOwnerRef.current !== owner) return
      await onOpenConstructionReview?.(handoff.run.artifact_id)
      if (constructionRequestOwnerRef.current !== owner) return
      setConstructionReviewState({ status: 'idle', targetArtifactId: null, error: null })
    } catch (caught) {
      if (constructionRequestOwnerRef.current !== owner) return
      setConstructionReviewState({ status: 'error', targetArtifactId: artifactId, error: caught instanceof Error ? caught.message : 'Replacement ranking construction handoff failed' })
    }
  }

  const openedArtifactId = openState.openedArtifact?.review_payload.artifact_id ?? null

  return (
    <section className="dashboard-bottom-grid" data-testid="persisted-replacement-ranking-browser">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Persisted Replacement Reviews</p></div>
        <p className="helper">Browse recent authoritative replacement ranking artifacts and reopen them read-only inside the workspace.</p>
      </div>
      <div className="summary-card">
        <div className="split-grid compact-split-grid strategy-lab-config-grid">
          <label className="field-group">
            <span className="field-label">Construction Policy</span>
            <select className="path-input" value={selectedConstructionPolicyId} onChange={(event) => setSelectedConstructionPolicyId(event.target.value)} disabled={constructionPolicyCatalog.status === 'loading' || constructionPolicyCatalog.status === 'error'}>
              <option value="">Select compatible policy</option>
              {constructionPolicyCatalog.policies.map((policy) => <option key={policy.policy_id} value={policy.policy_id}>{policy.name}</option>)}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Top N</span>
            <input aria-label="Replacement Top N" className="path-input" value={constructionTopN} onChange={(event) => setConstructionTopN(event.target.value)} />
            <p className="helper">Whole number between 2 and 20. Default is 2.</p>
            {constructionTopNValidation.error ? <p className="helper">{constructionTopNValidation.error}</p> : null}
          </label>
          <label className="field-group">
            <span className="field-label">Max Position Weight</span>
            <input aria-label="Max Position Weight" className="path-input" value={constructionMaxPositionWeight} onChange={(event) => setConstructionMaxPositionWeight(event.target.value)} />
            <p className="helper">Decimal weight only. Pair with Top N so that max × top_n ≥ 1 (1 / top_n is the minimum feasible max when fully invested).</p>
            {constructionMaxPositionWeightValidation.error ? <p className="helper">{constructionMaxPositionWeightValidation.error}</p> : null}
          </label>
          <label className="field-group">
            <span className="field-label">Min Position Weight (optional)</span>
            <input aria-label="Min Position Weight (optional)" className="path-input" value={constructionMinPositionWeight} onChange={(event) => setConstructionMinPositionWeight(event.target.value)} />
            <p className="helper">Leave blank to omit. If set, use a decimal greater than 0 and up to 0.5, and no higher than max.</p>
            {constructionMinPositionWeightValidation.error ? <p className="helper">{constructionMinPositionWeightValidation.error}</p> : null}
          </label>
          <label className="field-group">
            <span className="field-label">Max Turnover Weight (optional)</span>
            <input aria-label="Max Turnover Weight (optional)" className="path-input" value={constructionMaxTurnoverWeight} onChange={(event) => setConstructionMaxTurnoverWeight(event.target.value)} />
            <p className="helper">Leave blank to omit. If set, use a decimal between 0 and 1. Zero is allowed.</p>
            {constructionMaxTurnoverWeightValidation.error ? <p className="helper">{constructionMaxTurnoverWeightValidation.error}</p> : null}
          </label>
          <label className="field-group">
            <span className="field-label">Max Trade Intent Count (optional)</span>
            <input aria-label="Max Trade Intent Count (optional)" className="path-input" value={constructionMaxTradeIntentCount} onChange={(event) => setConstructionMaxTradeIntentCount(event.target.value)} />
            <p className="helper">Leave blank to omit. If set, use a whole number of 0 or greater.</p>
            {constructionMaxTradeIntentCountValidation.error ? <p className="helper">{constructionMaxTradeIntentCountValidation.error}</p> : null}
          </label>
          <label className="field-group">
            <span className="field-label">Max Sector Weight (optional)</span>
            <input aria-label="Max Sector Weight (optional)" className="path-input" value={constructionMaxSectorWeight} onChange={(event) => setConstructionMaxSectorWeight(event.target.value)} />
            <p className="helper">Leave blank to omit. If set, use a decimal greater than 0 and up to 1, no lower than max position weight. Replacement ranking handoffs carry no sector labels, so the cap evaluates as not_evaluated.</p>
            {constructionMaxSectorWeightValidation.error ? <p className="helper">{constructionMaxSectorWeightValidation.error}</p> : null}
          </label>
          <div className="field-group">
            <span className="field-label">Policy Source</span>
            <p className="helper">Authoritative `/construction/policies` discovery defines the compatible review-only policy set and the fixed top_n=2 launch boundary.</p>
            {selectedConstructionPolicyReadback ? <p className="helper">{selectedConstructionPolicyReadback}</p> : null}
          </div>
        </div>
        <div className="dashboard-edit-actions dashboard-edit-actions-compact">
          <button className="secondary-button" onClick={() => void loadRecentArtifacts()} type="button" disabled={recentState.status === 'loading'}>
            {recentState.status === 'loading' ? 'Refreshing...' : 'Refresh Reviews'}
          </button>
        </div>
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
        {openState.error ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Saved replacement review could not be opened.</p>
            <p className="helper">The selected persisted artifact did not pass read-only review validation.</p>
            <p className="helper">{openState.error}</p>
          </div>
        ) : null}
        {constructionReviewState.error ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Replacement ranking construction handoff failed.</p>
            <p className="helper">The selected persisted replacement ranking could not be handed into construction review.</p>
            <p className="helper">{constructionReviewState.error}</p>
          </div>
        ) : null}
        {recentState.status === 'loading' && !recentState.items.length ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Loading saved replacement reviews.</p>
            <p className="helper">Reading recent persisted replacement ranking artifacts from generalized discovery.</p>
          </div>
        ) : null}
        {recentState.status === 'error' ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Saved replacement reviews are unavailable.</p>
            <p className="helper">The generalized recent discovery route did not return a usable replacement list.</p>
            <p className="helper">{recentState.error}</p>
          </div>
        ) : null}
        {recentState.status !== 'error' && recentState.items.length === 0 && recentState.status !== 'loading' ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">No saved replacement reviews found.</p>
            <p className="helper">Persisted replacement ranking artifacts will appear here when generalized recent discovery finds them.</p>
          </div>
        ) : null}
        {recentState.items.length ? (
          <div className="factor-snapshot-table-wrap">
            <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-rank-grid-wide">
              <span>Ranked On</span>
              <span>Incumbent</span>
              <span>Candidate</span>
              <span>Peer Group</span>
              <span>Confidence</span>
              <span>Eligible</span>
              <span>Excluded</span>
              <span>Action</span>
            </div>
            {recentState.items.map((item) => {
              const isOpening = (openState.status === 'preflighting' || openState.status === 'opening') && openState.targetArtifactId === item.artifact_id
              const isOpened = openedArtifactId === item.artifact_id && openState.status === 'ready'
              const isReviewingInConstruction = constructionReviewState.status === 'running' && constructionReviewState.targetArtifactId === item.artifact_id
              const readiness = constructionReadinessState[item.artifact_id]
              const ready = readiness?.response?.eligibility.eligible === true && readiness.response.handoff != null
               const policyBlockedReason = constructionTopNValidation.error
                   ?? constructionMaxPositionWeightValidation.error
                   ?? constructionMinPositionWeightValidation.error
                   ?? constructionMaxTurnoverWeightValidation.error
                   ?? constructionMaxTradeIntentCountValidation.error
                   ?? constructionMaxSectorWeightValidation.error
                   ?? (constructionPolicyCatalog.status === 'error'
                     ? constructionPolicyCatalog.error ?? 'Construction policy catalog unavailable'
                     : constructionPolicyCatalog.status === 'loading'
                     ? 'Loading construction policies...'
                     : !selectedConstructionPolicyId
                       ? 'Select a compatible construction policy'
                       : null)
              const readinessLabel = readiness == null || readiness.status === 'loading'
                ? 'Checking construction readiness...'
                : readiness.status === 'error'
                  ? readiness.error ?? 'Construction readiness unavailable'
                  : ready
                    ? (selectedConstructionPolicyReadback ?? 'Ready for construction review')
                    : readiness.response?.eligibility.reason ?? 'Construction ineligible'
              const reviewLabel = policyBlockedReason ?? readinessLabel
              return (
                <div className={`risk-contrib-table-grid factor-shift-data-row strategy-lab-rank-grid-wide ${isOpened ? 'strategy-ranking-row-top' : ''}`} key={item.artifact_id}>
                  <span>{item.basis_date}</span>
                  <span>{item.base_symbol}</span>
                  <span>{item.candidate_symbol}</span>
                  <span>{item.peer_group}</span>
                  <span>{item.confidence}</span>
                  <span>{item.eligible_count}</span>
                  <span>{item.excluded_count}</span>
                  <span className="strategy-ranking-symbol-cell"><button className={`secondary-button${isOpening ? ' button-loading' : ''}`} onClick={() => void openArtifact(item.artifact_id)} type="button" disabled={isOpening}>{isOpening ? 'Opening...' : isOpened ? 'Opened' : 'Open Review'}</button><button className={`secondary-button${isReviewingInConstruction ? ' button-loading' : ''}`} onClick={() => void reviewInConstruction(item.artifact_id)} type="button" disabled={isReviewingInConstruction || !ready || policyBlockedReason != null} title={reviewLabel}>{isReviewingInConstruction ? 'Opening...' : 'Review In Construction'}</button><small>{reviewLabel}</small></span>
                </div>
              )
            })}
          </div>
        ) : null}
      </div>
      {openState.preflight && openState.openedArtifact ? <PersistedReplacementRankingReview preflight={openState.preflight} openResponse={openState.openedArtifact} /> : null}
    </section>
  )
}

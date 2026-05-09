import { useEffect, useMemo, useState } from 'react'

import type {
  AllocationBacktestComparison,
  HypotheticalReplayResponse,
  MonitorDefinitionCatalogRow,
  MonitorDefinitionId,
  MonitoringResearchHandoff,
  PortfolioAllocationBacktestResponse,
  PortfolioDiagnosticsComparisonRow,
  PortfolioDiagnosticsSnapshot,
  PortfolioDiagnosticsTopCallout,
} from '../portfolio/types'
import { formatReplayHistoricalBasisLabel } from '../portfolio/historyTruth'
import { investorEconomicsBaseReason } from '../portfolio/investorEconomics'
import { MONITOR_DEFINITION_MONITOR_ID, MONITORING_RESEARCH_HANDOFF_VERSION } from './monitoringResearchHandoff'

type MonitorTone = 'hot' | 'warm' | 'cool' | 'neutral'
type MonitoringDisciplineOverviewStatus = 'idle' | 'loading' | 'ready' | 'unavailable' | 'invalid'

const MONITORING_DISCIPLINE_CATALOG_URL = '/api/backtests/monitor-definitions/catalog?overlay_family=benchmark_trend&monitor_id=benchmark_trend_overlay_v1'
const DATA_QUALITY_DISCIPLINE_CATALOG_URL = '/api/backtests/monitor-definitions/catalog?monitor_family=data_quality&monitor_id=data_quality_monitor_v1'
const MONITORING_DISCIPLINE_CONTRACT_VERSION = 'monitor_definition_discovery_v1'
const MONITORING_DISCIPLINE_METADATA_TRUTH = 'authoritative_persisted_artifact_metadata'
const MONITORING_DISCIPLINE_ROW_PROVENANCE = 'persisted_monitor_definition_artifact'
const MONITORING_DISCIPLINE_MONITOR_ID = 'benchmark_trend_overlay_v1'
const MONITORING_DISCIPLINE_OVERLAY_FAMILY = 'benchmark_trend'
const DATA_QUALITY_DISCIPLINE_MONITOR_ID = 'data_quality_monitor_v1'
const DATA_QUALITY_DISCIPLINE_FAMILY = 'data_quality'
const MONITORING_DISCIPLINE_SCHEMA_VERSION = 'monitor_definition_artifact_v1'
const MONITORING_DISCIPLINE_REVIEW_SCOPE = 'current_portfolio_truth_only'
const MONITORING_DISCIPLINE_EVALUATION_MODE = 'review_only_observation_evaluation'
const MONITORING_DISCIPLINE_BENCHMARK_SOURCE_KIND = 'benchmark_overlay_signal'
const MONITORING_DISCIPLINE_PORTFOLIO_TRUTH_BASIS = 'imported_portfolio_snapshot'

const MONITORING_DISCIPLINE_THRESHOLD_FIELDS = [
  'minimum_confirmation_count',
  'risk_on_min_risky_weight',
  'risk_on_max_cash_weight',
  'risk_reduced_max_risky_weight',
  'risk_reduced_min_cash_weight',
]

const MONITORING_DISCIPLINE_LIFECYCLE_STATUSES = new Set(['enabled', 'disabled'])
const MONITORING_DISCIPLINE_REVIEW_SUPPORT_STATUSES = new Set(['review_supported'])
const MONITORING_DISCIPLINE_PRESENCE_STATUSES = new Set(['present', 'absent'])
const MONITORING_DISCIPLINE_OBSERVATION_STATUSES = new Set(['ok', 'threshold_breach', 'degraded', 'unavailable'])
const DATA_QUALITY_DISCIPLINE_OBSERVATION_STATUSES = new Set(['ok', 'degraded', 'unavailable'])
const MONITORING_DISCIPLINE_ALERT_CLASSIFICATIONS = new Set(['informational', 'action_required', 'degraded', 'unavailable'])
const MONITORING_DISCIPLINE_OBSERVATION_RECENCY_STATUSES = new Set(['recent', 'stale'])
const MONITORING_DISCIPLINE_SNAPSHOT_RECENCY_STATUSES = new Set(['recent', 'stale'])

type MonitorItem = {
  key: string
  title: string
  currentStatus: string
  recentChange: string
  severity: 'High' | 'Medium' | 'Low'
  confidence: 'High' | 'Medium' | 'Low'
  provenance: string
  tone: MonitorTone
  detail: string[]
  researchTarget: 'hypothetical_replay' | 'diagnostics_change' | null
}

type MonitorCallout = {
  key: string
  label: string
  value: string
  helper: string
  tone: MonitorTone
}

type MonitoringDisciplineOverview = {
  rows: MonitorDefinitionCatalogRow[]
  persistedCount: number
  enabledCount: number
  latestObservationPresenceCounts: Record<string, number>
  latestObservationFreshnessCounts: Record<string, number>
  latestSnapshotPresenceCounts: Record<string, number>
  lifecycleCounts: Record<string, number>
  reviewReadinessCounts: Record<string, number>
  latestStateCounts: Record<string, number>
}

type MonitoringDisciplineOverviewState = {
  status: MonitoringDisciplineOverviewStatus
  overview: MonitoringDisciplineOverview | null
}

type DataQualityDisciplineOverviewState = MonitoringDisciplineOverviewState

type MonitorFamilyReadinessDecision = 'ready' | 'blocked' | 'unavailable'

type MonitorFamilyReadinessReasonCode =
  | 'ready_persisted_review_supported'
  | 'blocked_missing_monitor_definition'
  | 'blocked_no_enabled_monitor_definition'
  | 'blocked_missing_thresholds'
  | 'blocked_missing_lineage'
  | 'blocked_missing_lifecycle_metadata'
  | 'blocked_missing_review_support'
  | 'blocked_replay_evidence_unavailable'
  | 'unavailable_catalog_invalid'
  | 'unavailable_catalog_load_failed'

type MonitorFamilyReadinessGate = {
  label: string
  status: 'passed' | 'blocked' | 'unavailable' | 'not_applicable'
  reasonCode: MonitorFamilyReadinessReasonCode | null
  detail: string
}

type MonitorFamilyReadinessRow = {
  familyId: string
  label: string
  source: string
  readinessDecision: MonitorFamilyReadinessDecision
  readinessStatus: string
  reasonCode: MonitorFamilyReadinessReasonCode
  gates: MonitorFamilyReadinessGate[]
  evidenceSummary: string
  provenanceSummary: string
}

const MONITOR_FAMILY_GATE_LABELS = {
  monitorDefinition: 'monitor definition artifact',
  thresholds: 'thresholds',
  lineage: 'lineage/provenance',
  lifecycle: 'lifecycle metadata',
  reviewSupport: 'review support decision',
  replayEvidence: 'replay evidence',
}

const NON_PERSISTED_REPLAY_SIGNALS: Array<{ familyId: string; label: string; monitorKey: string }> = [
  { familyId: 'factor_drift_replay_signal', label: 'Factor drift signal', monitorKey: 'factor-drift' },
  { familyId: 'concentration_drift_replay_signal', label: 'Concentration drift signal', monitorKey: 'concentration-drift' },
  { familyId: 'benchmark_relative_replay_signal', label: 'Benchmark-relative signal', monitorKey: 'benchmark-relative' },
  { familyId: 'volatility_replay_signal', label: 'Volatility signal', monitorKey: 'volatility' },
  { familyId: 'data_quality_replay_signal', label: 'Data quality signal', monitorKey: 'data-quality' },
]

function incrementCount(counts: Record<string, number>, key: string) {
  counts[key] = (counts[key] ?? 0) + 1
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isExpectedValue(value: unknown, expected: Set<string>) {
  return typeof value === 'string' && expected.has(value)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isStringArrayIncluding(value: unknown, requiredValue: string) {
  return Array.isArray(value)
    && value.every((item) => typeof item === 'string')
    && value.includes(requiredValue)
}

function validateMonitoringDisciplineThresholds(value: unknown) {
  if (!isRecord(value)) return false
  return MONITORING_DISCIPLINE_THRESHOLD_FIELDS.every((field) => isFiniteNumber(value[field]))
}

function validateMonitoringDisciplineSourceLineageRequirements(value: unknown) {
  if (!isRecord(value)) return false

  return value.benchmark_source_kind === MONITORING_DISCIPLINE_BENCHMARK_SOURCE_KIND
    && value.portfolio_truth_basis === MONITORING_DISCIPLINE_PORTFOLIO_TRUTH_BASIS
    && isStringArrayIncluding(value.required_portfolio_statement_fields, 'positions')
    && isStringArrayIncluding(value.required_benchmark_observation_fields, 'status')
}

function validateLatestObservationStatus(status: Record<string, unknown>) {
  const presence = status.latest_observation_status
  if (!isExpectedValue(presence, MONITORING_DISCIPLINE_PRESENCE_STATUSES)) return false

  const observation = status.latest_observation
  if (presence === 'absent') return observation == null
  if (!isRecord(observation)) return false

  return isNonEmptyString(observation.observation_id)
    && isNonEmptyString(observation.evaluated_at)
    && isExpectedValue(observation.observation_status, MONITORING_DISCIPLINE_OBSERVATION_STATUSES)
    && isExpectedValue(observation.alert_classification, MONITORING_DISCIPLINE_ALERT_CLASSIFICATIONS)
    && isExpectedValue(observation.recency_status, MONITORING_DISCIPLINE_OBSERVATION_RECENCY_STATUSES)
    && isNonEmptyString(observation.source_precedence)
}

function validateLatestSnapshotStatus(status: Record<string, unknown>) {
  const presence = status.latest_evaluation_snapshot_status
  if (!isExpectedValue(presence, MONITORING_DISCIPLINE_PRESENCE_STATUSES)) return false

  const snapshot = status.latest_evaluation_snapshot
  if (presence === 'absent') return snapshot == null
  if (!isRecord(snapshot)) return false

  return isNonEmptyString(snapshot.evaluated_at)
    && isExpectedValue(snapshot.outcome_status, MONITORING_DISCIPLINE_OBSERVATION_STATUSES)
    && isExpectedValue(snapshot.significance_status, MONITORING_DISCIPLINE_ALERT_CLASSIFICATIONS)
    && isExpectedValue(snapshot.recency_status, MONITORING_DISCIPLINE_SNAPSHOT_RECENCY_STATUSES)
    && isNonEmptyString(snapshot.source_precedence)
}

function validateMonitoringDisciplineCatalog(payload: unknown) {
  if (!isRecord(payload) || !isRecord(payload.metadata)) return null
  if (payload.metadata.contract_version !== MONITORING_DISCIPLINE_CONTRACT_VERSION) return null
  if (payload.metadata.metadata_truth !== MONITORING_DISCIPLINE_METADATA_TRUTH) return null
  if (payload.metadata.row_provenance !== MONITORING_DISCIPLINE_ROW_PROVENANCE) return null
  if (!Array.isArray(payload.items)) return null

  for (const row of payload.items) {
    if (!isRecord(row)) return null
    if (!isNonEmptyString(row.monitor_definition_id)) return null
    if (row.monitor_id !== MONITORING_DISCIPLINE_MONITOR_ID) return null
    if (!isNonEmptyString(row.benchmark_symbol)) return null
    if (row.schema_version !== MONITORING_DISCIPLINE_SCHEMA_VERSION) return null
    if (row.review_scope !== MONITORING_DISCIPLINE_REVIEW_SCOPE) return null
    if (row.evaluation_mode !== MONITORING_DISCIPLINE_EVALUATION_MODE) return null
    if (!validateMonitoringDisciplineThresholds(row.thresholds)) return null
    if (!validateMonitoringDisciplineSourceLineageRequirements(row.source_lineage_requirements)) return null
    if (!isRecord(row.metadata)) return null
    if (row.metadata.metadata_truth !== MONITORING_DISCIPLINE_METADATA_TRUTH) return null
    if (row.metadata.row_provenance !== MONITORING_DISCIPLINE_ROW_PROVENANCE) return null
    if (!isRecord(row.metadata.status)) return null
    if (!isRecord(row.metadata.status.lifecycle)) return null

    const lifecycle = row.metadata.status.lifecycle
    if (lifecycle.overlay_family !== MONITORING_DISCIPLINE_OVERLAY_FAMILY) return null
    if (!isExpectedValue(lifecycle.review_support_status, MONITORING_DISCIPLINE_REVIEW_SUPPORT_STATUSES)) return null
    if (!isExpectedValue(lifecycle.lifecycle_status, MONITORING_DISCIPLINE_LIFECYCLE_STATUSES)) return null
    if (!validateLatestObservationStatus(row.metadata.status)) return null
    if (!validateLatestSnapshotStatus(row.metadata.status)) return null
  }

  return payload.items as MonitorDefinitionCatalogRow[]
}

function validateDataQualityDisciplineCatalog(payload: unknown) {
  if (!isRecord(payload) || !isRecord(payload.metadata)) return null
  if (payload.metadata.contract_version !== MONITORING_DISCIPLINE_CONTRACT_VERSION) return null
  if (payload.metadata.metadata_truth !== MONITORING_DISCIPLINE_METADATA_TRUTH) return null
  if (payload.metadata.row_provenance !== MONITORING_DISCIPLINE_ROW_PROVENANCE) return null
  if (!Array.isArray(payload.items)) return null

  for (const row of payload.items) {
    if (!isRecord(row)) return null
    if (!isNonEmptyString(row.monitor_definition_id)) return null
    if (row.monitor_id !== DATA_QUALITY_DISCIPLINE_MONITOR_ID) return null
    if (row.monitor_family !== DATA_QUALITY_DISCIPLINE_FAMILY) return null
    if (row.schema_version !== MONITORING_DISCIPLINE_SCHEMA_VERSION) return null
    if (row.review_scope !== MONITORING_DISCIPLINE_REVIEW_SCOPE) return null
    if (row.evaluation_mode !== MONITORING_DISCIPLINE_EVALUATION_MODE) return null
    if (!isRecord(row.thresholds)) return null
    if (!isFiniteNumber(row.thresholds.minimum_coverage_ratio)) return null
    if (!isFiniteNumber(row.thresholds.max_stale_age_days)) return null
    if (!isStringArrayIncluding(row.thresholds.provenance_requirements, 'source_lineage')) return null
    if (!isRecord(row.source_lineage_requirements)) return null
    if (row.source_lineage_requirements.evidence_source_kind !== 'market_data_reliability_evidence') return null
    if (!isStringArrayIncluding(row.source_lineage_requirements.required_evidence_fields, 'coverage_counts')) return null
    if (!isRecord(row.metadata) || row.metadata.metadata_truth !== MONITORING_DISCIPLINE_METADATA_TRUTH) return null
    if (row.metadata.row_provenance !== MONITORING_DISCIPLINE_ROW_PROVENANCE) return null
    if (!isRecord(row.metadata.status) || !isRecord(row.metadata.status.lifecycle)) return null
    const lifecycle = row.metadata.status.lifecycle
    if (lifecycle.monitor_family !== DATA_QUALITY_DISCIPLINE_FAMILY) return null
    if (!isExpectedValue(lifecycle.review_support_status, MONITORING_DISCIPLINE_REVIEW_SUPPORT_STATUSES)) return null
    if (!isExpectedValue(lifecycle.lifecycle_status, MONITORING_DISCIPLINE_LIFECYCLE_STATUSES)) return null
    if (!validateLatestObservationStatus(row.metadata.status)) return null
    if (!validateLatestSnapshotStatus(row.metadata.status)) return null
    const latestObservation = isRecord(row.metadata.status.latest_observation) ? row.metadata.status.latest_observation : null
    const latestSnapshot = isRecord(row.metadata.status.latest_evaluation_snapshot) ? row.metadata.status.latest_evaluation_snapshot : null
    const latestState = latestObservation?.observation_status ?? latestSnapshot?.outcome_status ?? null
    if (latestState != null && !isExpectedValue(latestState, DATA_QUALITY_DISCIPLINE_OBSERVATION_STATUSES)) return null
  }

  return payload.items as MonitorDefinitionCatalogRow[]
}

function buildMonitoringDisciplineOverview(rows: MonitorDefinitionCatalogRow[]): MonitoringDisciplineOverview {
  const overview: MonitoringDisciplineOverview = {
    rows,
    persistedCount: rows.length,
    enabledCount: 0,
    latestObservationPresenceCounts: {},
    latestObservationFreshnessCounts: {},
    latestSnapshotPresenceCounts: {},
    lifecycleCounts: {},
    reviewReadinessCounts: {},
    latestStateCounts: {},
  }

  for (const row of rows) {
    const status = row.metadata.status
    const lifecycleStatus = status.lifecycle.lifecycle_status
    const reviewStatus = status.lifecycle.review_support_status
    const latestObservationPresence = status.latest_observation_status ?? 'absent'
    const latestSnapshotPresence = status.latest_evaluation_snapshot_status ?? 'absent'
    const latestObservationFreshness = status.latest_observation ? status.latest_observation.recency_status : 'absent'
    const latestState = status.latest_observation?.observation_status ?? status.latest_evaluation_snapshot?.outcome_status ?? 'absent'

    if (lifecycleStatus === 'enabled') overview.enabledCount += 1
    incrementCount(overview.lifecycleCounts, lifecycleStatus)
    incrementCount(overview.reviewReadinessCounts, reviewStatus)
    incrementCount(overview.latestObservationPresenceCounts, latestObservationPresence)
    incrementCount(overview.latestObservationFreshnessCounts, latestObservationFreshness)
    incrementCount(overview.latestSnapshotPresenceCounts, latestSnapshotPresence)
    incrementCount(overview.latestStateCounts, latestState)
  }

  return overview
}

function benchmarkFamilyReadiness(disciplineOverviewState: MonitoringDisciplineOverviewState): MonitorFamilyReadinessRow {
  if (disciplineOverviewState.status === 'ready' && disciplineOverviewState.overview) {
    const rowCount = disciplineOverviewState.overview.rows.length
    if (rowCount > 0) {
      const definitionIds = disciplineOverviewState.overview.rows.map((row) => row.monitor_definition_id).join(', ')
      const enabledDefinitionIds = disciplineOverviewState.overview.rows
        .filter((row) => row.metadata.status.lifecycle.lifecycle_status === 'enabled')
        .map((row) => row.monitor_definition_id)
        .join(', ')

      if (disciplineOverviewState.overview.enabledCount === 0) {
        return {
          familyId: MONITORING_DISCIPLINE_MONITOR_ID,
          label: 'Benchmark trend overlay',
          source: 'Persisted monitor definition catalog',
          readinessDecision: 'blocked',
          readinessStatus: 'blocked_no_enabled_monitor_definition',
          reasonCode: 'blocked_no_enabled_monitor_definition',
          evidenceSummary: `${rowCount} persisted definition row${rowCount === 1 ? '' : 's'} returned, but 0 are enabled: ${definitionIds}`,
          provenanceSummary: `backend catalog metadata truth ${MONITORING_DISCIPLINE_METADATA_TRUTH}; row provenance ${MONITORING_DISCIPLINE_ROW_PROVENANCE}; monitor definition count ${rowCount}; enabled monitor definition count 0; monitor definition ids ${definitionIds}`,
          gates: [
            { label: MONITOR_FAMILY_GATE_LABELS.monitorDefinition, status: 'passed', reasonCode: null, detail: `${rowCount} persisted definition row${rowCount === 1 ? '' : 's'} present.` },
            { label: MONITOR_FAMILY_GATE_LABELS.thresholds, status: 'passed', reasonCode: null, detail: 'Thresholds are present on validated persisted catalog rows.' },
            { label: MONITOR_FAMILY_GATE_LABELS.lineage, status: 'passed', reasonCode: null, detail: `${MONITORING_DISCIPLINE_METADATA_TRUTH} / ${MONITORING_DISCIPLINE_ROW_PROVENANCE}.` },
            { label: MONITOR_FAMILY_GATE_LABELS.lifecycle, status: 'blocked', reasonCode: 'blocked_no_enabled_monitor_definition', detail: 'Validated benchmark_trend rows are present, but none are enabled.' },
            { label: MONITOR_FAMILY_GATE_LABELS.reviewSupport, status: 'passed', reasonCode: null, detail: 'review_supported lifecycle status validated.' },
            { label: MONITOR_FAMILY_GATE_LABELS.replayEvidence, status: 'not_applicable', reasonCode: null, detail: 'Persisted benchmark readiness is catalog-backed; replay evidence does not promote additional families.' },
          ],
        }
      }

      return {
        familyId: MONITORING_DISCIPLINE_MONITOR_ID,
        label: 'Benchmark trend overlay',
        source: 'Persisted monitor definition catalog',
        readinessDecision: 'ready',
        readinessStatus: 'ready_persisted_review_supported',
        reasonCode: 'ready_persisted_review_supported',
        evidenceSummary: `${rowCount} persisted definition row${rowCount === 1 ? '' : 's'} with ${disciplineOverviewState.overview.enabledCount} enabled: ${enabledDefinitionIds}`,
        provenanceSummary: `backend catalog metadata truth ${MONITORING_DISCIPLINE_METADATA_TRUTH}; row provenance ${MONITORING_DISCIPLINE_ROW_PROVENANCE}; monitor definition count ${rowCount}; enabled monitor definition count ${disciplineOverviewState.overview.enabledCount}; monitor definition ids ${definitionIds}`,
        gates: [
          { label: MONITOR_FAMILY_GATE_LABELS.monitorDefinition, status: 'passed', reasonCode: null, detail: `${rowCount} persisted definition row${rowCount === 1 ? '' : 's'} present.` },
          { label: MONITOR_FAMILY_GATE_LABELS.thresholds, status: 'passed', reasonCode: null, detail: 'Thresholds are present on validated persisted catalog rows.' },
          { label: MONITOR_FAMILY_GATE_LABELS.lineage, status: 'passed', reasonCode: null, detail: `${MONITORING_DISCIPLINE_METADATA_TRUTH} / ${MONITORING_DISCIPLINE_ROW_PROVENANCE}.` },
          { label: MONITOR_FAMILY_GATE_LABELS.lifecycle, status: 'passed', reasonCode: null, detail: 'Lifecycle metadata validated for benchmark_trend.' },
          { label: MONITOR_FAMILY_GATE_LABELS.reviewSupport, status: 'passed', reasonCode: null, detail: 'review_supported lifecycle status validated.' },
          { label: MONITOR_FAMILY_GATE_LABELS.replayEvidence, status: 'not_applicable', reasonCode: null, detail: 'Persisted benchmark readiness is catalog-backed; replay evidence does not promote additional families.' },
        ],
      }
    }

    return {
      familyId: MONITORING_DISCIPLINE_MONITOR_ID,
      label: 'Benchmark trend overlay',
      source: 'Persisted monitor definition catalog',
      readinessDecision: 'blocked',
      readinessStatus: 'blocked_missing_monitor_definition',
      reasonCode: 'blocked_missing_monitor_definition',
      evidenceSummary: 'No persisted benchmark-trend definitions returned',
      provenanceSummary: `backend catalog metadata truth ${MONITORING_DISCIPLINE_METADATA_TRUTH}; row provenance ${MONITORING_DISCIPLINE_ROW_PROVENANCE}; monitor definition count 0`,
      gates: [
        { label: MONITOR_FAMILY_GATE_LABELS.monitorDefinition, status: 'blocked', reasonCode: 'blocked_missing_monitor_definition', detail: 'No persisted monitor definition artifact row was returned.' },
        { label: MONITOR_FAMILY_GATE_LABELS.thresholds, status: 'blocked', reasonCode: 'blocked_missing_thresholds', detail: 'Thresholds cannot be verified without a definition row.' },
        { label: MONITOR_FAMILY_GATE_LABELS.lineage, status: 'blocked', reasonCode: 'blocked_missing_lineage', detail: 'Row lineage cannot be verified without a definition row.' },
        { label: MONITOR_FAMILY_GATE_LABELS.lifecycle, status: 'blocked', reasonCode: 'blocked_missing_lifecycle_metadata', detail: 'Lifecycle metadata cannot be verified without a definition row.' },
        { label: MONITOR_FAMILY_GATE_LABELS.reviewSupport, status: 'blocked', reasonCode: 'blocked_missing_review_support', detail: 'Review support cannot be verified without a definition row.' },
        { label: MONITOR_FAMILY_GATE_LABELS.replayEvidence, status: 'not_applicable', reasonCode: null, detail: 'Replay evidence does not create persisted benchmark readiness.' },
      ],
    }
  }

  if (disciplineOverviewState.status === 'invalid') {
    return {
      familyId: MONITORING_DISCIPLINE_MONITOR_ID,
      label: 'Benchmark trend overlay',
      source: 'Persisted catalog validation',
      readinessDecision: 'unavailable',
      readinessStatus: 'unavailable_catalog_invalid',
      reasonCode: 'unavailable_catalog_invalid',
      evidenceSummary: 'Catalog metadata or row lineage failed validation',
      provenanceSummary: 'Catalog validation failed before persisted row provenance could be trusted.',
      gates: [
        { label: MONITOR_FAMILY_GATE_LABELS.monitorDefinition, status: 'unavailable', reasonCode: 'unavailable_catalog_invalid', detail: 'Catalog validation failed before definition rows could be trusted.' },
        { label: MONITOR_FAMILY_GATE_LABELS.thresholds, status: 'unavailable', reasonCode: 'unavailable_catalog_invalid', detail: 'Catalog validation failed before thresholds could be trusted.' },
        { label: MONITOR_FAMILY_GATE_LABELS.lineage, status: 'unavailable', reasonCode: 'unavailable_catalog_invalid', detail: 'Catalog metadata or row provenance failed validation.' },
        { label: MONITOR_FAMILY_GATE_LABELS.lifecycle, status: 'unavailable', reasonCode: 'unavailable_catalog_invalid', detail: 'Catalog validation failed before lifecycle metadata could be trusted.' },
        { label: MONITOR_FAMILY_GATE_LABELS.reviewSupport, status: 'unavailable', reasonCode: 'unavailable_catalog_invalid', detail: 'Catalog validation failed before review support could be trusted.' },
        { label: MONITOR_FAMILY_GATE_LABELS.replayEvidence, status: 'not_applicable', reasonCode: null, detail: 'Replay evidence does not override invalid persisted catalog lineage.' },
      ],
    }
  }

  const loading = disciplineOverviewState.status === 'loading' || disciplineOverviewState.status === 'idle'
  return {
    familyId: MONITORING_DISCIPLINE_MONITOR_ID,
    label: 'Benchmark trend overlay',
    source: 'Persisted monitor definition catalog',
    readinessDecision: 'unavailable',
    readinessStatus: 'unavailable_catalog_load_failed',
    reasonCode: 'unavailable_catalog_load_failed',
    evidenceSummary: loading ? 'Catalog loading' : 'Catalog unavailable',
    provenanceSummary: loading ? 'Waiting for backend catalog metadata truth.' : 'The backend catalog request failed; persisted row provenance is unavailable.',
    gates: [
      { label: MONITOR_FAMILY_GATE_LABELS.monitorDefinition, status: 'unavailable', reasonCode: 'unavailable_catalog_load_failed', detail: loading ? 'Catalog is still loading.' : 'Catalog load failed before definition rows were available.' },
      { label: MONITOR_FAMILY_GATE_LABELS.thresholds, status: 'unavailable', reasonCode: 'unavailable_catalog_load_failed', detail: loading ? 'Catalog is still loading.' : 'Catalog load failed before thresholds were available.' },
      { label: MONITOR_FAMILY_GATE_LABELS.lineage, status: 'unavailable', reasonCode: 'unavailable_catalog_load_failed', detail: loading ? 'Catalog is still loading.' : 'Catalog load failed before lineage could be validated.' },
      { label: MONITOR_FAMILY_GATE_LABELS.lifecycle, status: 'unavailable', reasonCode: 'unavailable_catalog_load_failed', detail: loading ? 'Catalog is still loading.' : 'Catalog load failed before lifecycle metadata was available.' },
      { label: MONITOR_FAMILY_GATE_LABELS.reviewSupport, status: 'unavailable', reasonCode: 'unavailable_catalog_load_failed', detail: loading ? 'Catalog is still loading.' : 'Catalog load failed before review support was available.' },
      { label: MONITOR_FAMILY_GATE_LABELS.replayEvidence, status: 'not_applicable', reasonCode: null, detail: 'Replay evidence does not substitute for persisted catalog readiness.' },
    ],
  }
}

function replaySignalGates(replayEvidenceAvailable: boolean): MonitorFamilyReadinessGate[] {
  return [
    { label: MONITOR_FAMILY_GATE_LABELS.monitorDefinition, status: 'blocked', reasonCode: 'blocked_missing_monitor_definition', detail: 'No persisted monitor definition artifact exists for this replay signal.' },
    { label: MONITOR_FAMILY_GATE_LABELS.thresholds, status: 'blocked', reasonCode: 'blocked_missing_thresholds', detail: 'No persisted thresholds exist for this replay signal.' },
    { label: MONITOR_FAMILY_GATE_LABELS.lineage, status: 'blocked', reasonCode: 'blocked_missing_lineage', detail: 'Replay signal evidence is not persisted monitor-family lineage.' },
    { label: MONITOR_FAMILY_GATE_LABELS.lifecycle, status: 'blocked', reasonCode: 'blocked_missing_lifecycle_metadata', detail: 'No persisted lifecycle metadata exists for this replay signal.' },
    { label: MONITOR_FAMILY_GATE_LABELS.reviewSupport, status: 'blocked', reasonCode: 'blocked_missing_review_support', detail: 'No persisted review support decision exists for this replay signal.' },
    replayEvidenceAvailable
      ? { label: MONITOR_FAMILY_GATE_LABELS.replayEvidence, status: 'passed', reasonCode: null, detail: 'Replay-derived diagnostics/watch-group evidence is available for read-only display.' }
      : { label: MONITOR_FAMILY_GATE_LABELS.replayEvidence, status: 'unavailable', reasonCode: 'blocked_replay_evidence_unavailable', detail: 'Replay diagnostics/watch-group evidence is unavailable; readiness is not assessed.' },
  ]
}

function buildMonitorFamilyReadiness(
  disciplineOverviewState: MonitoringDisciplineOverviewState,
  dataQualityOverviewState: DataQualityDisciplineOverviewState,
  monitors: MonitorItem[],
  activeReplay: PortfolioAllocationBacktestResponse,
): MonitorFamilyReadinessRow[] {
  const monitorByKey = new Map(monitors.map((monitor) => [monitor.key, monitor]))
  const replayEvidenceAvailable = Boolean(activeReplay.diagnostics_comparison && activeReplay.candidate_diagnostics)

  const rows: MonitorFamilyReadinessRow[] = [benchmarkFamilyReadiness(disciplineOverviewState)]
  const dataQualityReady = dataQualityOverviewState.status === 'ready' && dataQualityOverviewState.overview != null && dataQualityOverviewState.overview.persistedCount > 0
  if (dataQualityReady) {
    const overview = dataQualityOverviewState.overview as MonitoringDisciplineOverview
    rows.push({
      familyId: DATA_QUALITY_DISCIPLINE_MONITOR_ID,
      label: 'Data quality',
      source: 'Persisted data-quality monitor catalog',
      readinessDecision: overview.enabledCount > 0 ? 'ready' : 'blocked',
      readinessStatus: overview.enabledCount > 0 ? 'ready_persisted_review_supported' : 'blocked_no_enabled_monitor_definition',
      reasonCode: overview.enabledCount > 0 ? 'ready_persisted_review_supported' : 'blocked_no_enabled_monitor_definition',
      evidenceSummary: `${overview.persistedCount} persisted definition row${overview.persistedCount === 1 ? '' : 's'}; latest states ${formatCounts(overview.latestStateCounts)}`,
      provenanceSummary: `backend catalog metadata truth ${MONITORING_DISCIPLINE_METADATA_TRUTH}; row provenance ${MONITORING_DISCIPLINE_ROW_PROVENANCE}; data_quality monitor definition rows only`,
      gates: [
        { label: MONITOR_FAMILY_GATE_LABELS.monitorDefinition, status: 'passed', reasonCode: null, detail: 'Validated data_quality_monitor_v1 persisted rows are present.' },
        { label: MONITOR_FAMILY_GATE_LABELS.thresholds, status: 'passed', reasonCode: null, detail: 'Data-quality policy is present on validated persisted rows.' },
        { label: MONITOR_FAMILY_GATE_LABELS.lineage, status: 'passed', reasonCode: null, detail: 'Data-quality evidence lineage requirements validated.' },
        { label: MONITOR_FAMILY_GATE_LABELS.lifecycle, status: overview.enabledCount > 0 ? 'passed' : 'blocked', reasonCode: overview.enabledCount > 0 ? null : 'blocked_no_enabled_monitor_definition', detail: `${overview.enabledCount} enabled persisted data-quality definitions.` },
        { label: MONITOR_FAMILY_GATE_LABELS.reviewSupport, status: 'passed', reasonCode: null, detail: 'review_supported lifecycle status validated.' },
        { label: MONITOR_FAMILY_GATE_LABELS.replayEvidence, status: 'not_applicable', reasonCode: null, detail: 'Persisted data quality readiness is catalog-backed.' },
      ],
    })
  }

  rows.push(...NON_PERSISTED_REPLAY_SIGNALS.filter((family) => !(dataQualityReady && family.familyId === 'data_quality_replay_signal')).map((family): MonitorFamilyReadinessRow => {
      const monitor = monitorByKey.get(family.monitorKey)
      const evidence = replayEvidenceAvailable && monitor && monitor.currentStatus !== 'Unavailable'
        ? `Replay-derived diagnostics/watch-group evidence: ${monitor.currentStatus} / ${monitor.recentChange}`
        : 'Replay diagnostics/watch-group evidence unavailable; readiness is not assessed.'

      return {
        familyId: family.familyId,
        label: family.label,
        source: 'Replay-derived only',
        readinessDecision: replayEvidenceAvailable ? 'blocked' : 'unavailable',
        readinessStatus: replayEvidenceAvailable ? 'not_persisted' : 'evidence_unavailable',
        reasonCode: replayEvidenceAvailable ? 'blocked_missing_monitor_definition' : 'blocked_replay_evidence_unavailable',
        evidenceSummary: evidence,
        provenanceSummary: 'Replay-derived diagnostics/watch-group signal evidence only. Not a persisted monitor family. No catalog metadata, thresholds, lifecycle metadata, review support decision, mutation, or handoff is created.',
        gates: replaySignalGates(replayEvidenceAvailable),
      }
    }))
  return rows
}

function formatCounts(counts: Record<string, number>) {
  const entries = Object.entries(counts).sort(([left], [right]) => left.localeCompare(right))
  return entries.length ? entries.map(([key, value]) => `${key.replace(/_/g, ' ')} ${value}`).join(' / ') : 'none'
}

function formatLatestObservationLabel(status: MonitorDefinitionCatalogRow['metadata']['status']) {
  if (status.latest_observation_status === 'absent') return 'absent / no latest observation'
  return `${status.latest_observation_status} / ${status.latest_observation?.recency_status} / ${status.latest_observation?.observation_status}`
}

function formatLatestSnapshotLabel(status: MonitorDefinitionCatalogRow['metadata']['status']) {
  if (status.latest_evaluation_snapshot_status === 'absent') return 'absent / no latest snapshot'
  return `${status.latest_evaluation_snapshot_status} / ${status.latest_evaluation_snapshot?.recency_status} / ${status.latest_evaluation_snapshot?.outcome_status}`
}

function formatReadinessDecision(decision: MonitorFamilyReadinessDecision) {
  if (decision === 'ready') return 'Ready'
  if (decision === 'blocked') return 'Blocked'
  return 'Unavailable'
}

function formatGateBreakdown(gates: MonitorFamilyReadinessGate[]) {
  return gates
    .map((gate) => `${gate.label}: ${gate.status}${gate.reasonCode ? ` (${gate.reasonCode})` : ''} - ${gate.detail}`)
    .join(' | ')
}

function formatPct(value: number | null | undefined) {
  return value == null ? 'N/A' : `${value.toFixed(2)}%`
}

function formatSignedPct(value: number | null | undefined) {
  if (value == null) return 'N/A'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'N/A' : value.toFixed(digits)
}

function formatSignedNumber(value: number | null | undefined, digits = 2) {
  if (value == null) return 'N/A'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
}

function cardClass(tone: MonitorTone) {
  return `summary-card metric-card metric-card-${tone}`
}

function rowToneClass(tone: MonitorTone) {
  if (tone === 'hot') return 'negative-text'
  if (tone === 'warm') return 'neutral-text'
  if (tone === 'cool') return 'positive-text'
  return 'neutral-text'
}

function selectionRuleLabel(value: string) {
  if (value === 'largest_absolute_delta') return 'largest absolute delta'
  if (value === 'fixed_priority') return 'fixed priority rule'
  return value.replace(/_/g, ' ')
}

function comparisonValue(row: PortfolioDiagnosticsComparisonRow | PortfolioDiagnosticsTopCallout) {
  if (row.key.includes('hhi') || row.key.includes('beta') || row.key.includes('correlation')) {
    return formatSignedNumber(row.delta_value)
  }
  return formatSignedPct(row.delta_value)
}

function magnitude(value: number | null | undefined) {
  return Math.abs(value ?? 0)
}

function toneFromMagnitude(value: number | null | undefined, highThreshold: number, mediumThreshold: number): MonitorTone {
  const absolute = magnitude(value)
  if (absolute >= highThreshold) return 'hot'
  if (absolute >= mediumThreshold) return 'warm'
  if (absolute > 0) return 'cool'
  return 'neutral'
}

function confidenceFromReplay(activeReplay: PortfolioAllocationBacktestResponse, diagnosticsReady: boolean): 'High' | 'Medium' | 'Low' {
  if (activeReplay.candidate_result?.status === 'degraded' || activeReplay.reference_result?.status === 'degraded') return 'Low'
  if (!diagnosticsReady) return 'Medium'
  return activeReplay.reference_result ? 'High' : 'Medium'
}

function isReplayInvestorEconomicsWithheld(activeReplay: PortfolioAllocationBacktestResponse) {
  return investorEconomicsBaseReason(activeReplay.investor_economics_status) != null
}

function isResultInvestorEconomicsWithheld(activeReplay: PortfolioAllocationBacktestResponse, side: 'candidate' | 'reference') {
  if (side === 'candidate') return investorEconomicsBaseReason(activeReplay.candidate_result?.investor_economics_status) != null
  return investorEconomicsBaseReason(activeReplay.reference_result?.investor_economics_status) != null
}

function monitorFromCallout(
  key: string,
  title: string,
  row: PortfolioDiagnosticsTopCallout | null,
  provenance: string,
  diagnosticsConfidence: 'High' | 'Medium' | 'Low',
  unavailableGuidance: string,
): MonitorItem {
  if (!row) {
    return {
      key,
      title,
      currentStatus: 'Unavailable',
      recentChange: 'N/A',
      severity: 'Low',
      confidence: 'Low',
        provenance,
        tone: 'neutral',
        detail: [unavailableGuidance],
        researchTarget: null,
      }
  }

  const tone = toneFromMagnitude(row.delta_value, 0.2, 0.08)
  return {
    key,
    title,
    currentStatus: row.label,
    recentChange: comparisonValue(row),
    severity: tone === 'hot' ? 'High' : tone === 'warm' ? 'Medium' : 'Low',
    confidence: diagnosticsConfidence,
    provenance,
    tone,
    detail: [
      `Baseline ${formatNumber(row.baseline_value)} vs candidate ${formatNumber(row.candidate_value)}.`,
      `Selection rule: ${selectionRuleLabel(row.selection_rule)}.`,
      row.rationale,
    ],
    researchTarget: 'diagnostics_change',
  }
}

function dataQualityMonitor(
  activeReplay: PortfolioAllocationBacktestResponse,
  candidateDiagnostics: PortfolioDiagnosticsSnapshot | null,
  referenceDiagnostics: PortfolioDiagnosticsSnapshot | null,
): MonitorItem {
  const degradedVariants = [activeReplay.reference_result?.status, activeReplay.candidate_result?.status].filter((status) => status === 'degraded').length
  const missingDiagnostics = [referenceDiagnostics, candidateDiagnostics].filter((snapshot) => snapshot == null).length
  const comparisonReady = Boolean(activeReplay.diagnostics_comparison)
  const tone = degradedVariants > 0 ? 'hot' : missingDiagnostics > 0 || !comparisonReady ? 'warm' : 'cool'

  return {
    key: 'data-quality',
    title: 'Data Quality',
    currentStatus: degradedVariants > 0 ? 'Degraded' : missingDiagnostics > 0 || !comparisonReady ? 'Partial' : 'Stable',
    recentChange: degradedVariants > 0 ? `${degradedVariants} degraded replay variant${degradedVariants > 1 ? 's' : ''}` : missingDiagnostics > 0 ? `${missingDiagnostics} diagnostics snapshot missing` : 'No degradation flag',
    severity: tone === 'hot' ? 'High' : tone === 'warm' ? 'Medium' : 'Low',
    confidence: tone === 'hot' ? 'Low' : tone === 'warm' ? 'Medium' : 'High',
    provenance: candidateDiagnostics?.provenance.note ?? referenceDiagnostics?.provenance.note ?? 'Replay status and diagnostics availability are backend-authored.',
    tone,
    detail: [
      `Candidate replay status: ${activeReplay.candidate_result?.status ?? 'not provided'}.`,
      `Reference replay status: ${activeReplay.reference_result?.status ?? 'not provided'}.`,
      comparisonReady ? 'Diagnostics comparison is available for monitoring review.' : 'Diagnostics comparison is unavailable for this replay state.',
    ],
    researchTarget: null,
  }
}

function benchmarkRelativeMonitor(
  comparison: AllocationBacktestComparison | null,
  activeReplay: PortfolioAllocationBacktestResponse,
  provenance: string,
  diagnosticsConfidence: 'High' | 'Medium' | 'Low',
): MonitorItem {
  const tone = toneFromMagnitude(comparison?.tracking_error_diff_pct, 2.5, 1)
  const replayInvestorEconomicsWithheld = isReplayInvestorEconomicsWithheld(activeReplay)

  return {
    key: 'benchmark-relative',
    title: 'Benchmark-Relative Drift',
    currentStatus: `TE ${formatPct(activeReplay.candidate_result?.metrics?.tracking_error_pct)} / Beta ${formatNumber(activeReplay.candidate_result?.metrics?.beta_vs_benchmark)}`,
    recentChange: `TE ${formatSignedPct(comparison?.tracking_error_diff_pct ?? null)} / Beta ${formatSignedNumber(comparison?.beta_diff ?? null)}`,
    severity: tone === 'hot' ? 'High' : tone === 'warm' ? 'Medium' : 'Low',
    confidence: diagnosticsConfidence,
    provenance,
    tone,
    detail: [
      `Candidate correlation vs benchmark: ${formatNumber(activeReplay.candidate_result?.metrics?.correlation_vs_benchmark)}.`,
      replayInvestorEconomicsWithheld
        ? 'Investor-performance benchmark-relative deltas are withheld for this replay state because total-return equivalence is unverified.'
        : 'This monitor stays on tracking error, beta, and correlation only rather than investor-performance benchmark-relative outcomes.',
      'Benchmark-relative watch keeps tracking error, beta, and correlation as replay-basis risk-shape metrics rather than verified investor-return measures.',
    ],
    researchTarget: 'hypothetical_replay',
  }
}

function volatilityMonitor(
  row: PortfolioDiagnosticsTopCallout | null,
  activeReplay: PortfolioAllocationBacktestResponse,
  candidateDiagnostics: PortfolioDiagnosticsSnapshot | null,
  provenance: string,
  diagnosticsConfidence: 'High' | 'Medium' | 'Low',
): MonitorItem {
  const snapshot = candidateDiagnostics?.volatility_snapshot ?? null
  const tone = toneFromMagnitude(row?.delta_value ?? snapshot?.tracking_error_252d ?? null, 3, 1)
  const candidateInvestorEconomicsWithheld = isResultInvestorEconomicsWithheld(activeReplay, 'candidate')

  return {
    key: 'volatility',
    title: 'Volatility Shape',
    currentStatus: `Vol ${formatPct(snapshot?.realized_vol_252d)} / TE ${formatPct(snapshot?.tracking_error_252d)}`,
    recentChange: row ? `${row.label} ${comparisonValue(row)}` : `Tracking error 252d ${formatPct(snapshot?.tracking_error_252d)}`,
    severity: tone === 'hot' ? 'High' : tone === 'warm' ? 'Medium' : 'Low',
    confidence: diagnosticsConfidence,
    provenance,
    tone,
    detail: [
      `Downside volatility: ${formatPct(snapshot?.downside_vol_252d)}.`,
      candidateInvestorEconomicsWithheld
        ? 'Investor-performance drawdown views are withheld for this replay state because total-return equivalence is unverified.'
        : 'This monitor stays on allowed volatility-shape context and does not rely on investor-performance drawdown readouts.',
      row?.rationale ?? 'Replay monitoring keeps allowed volatility-shape metrics only and does not expose drawdown-derived regime text.',
    ],
    researchTarget: 'diagnostics_change',
  }
}

function buildMonitors(activeReplay: PortfolioAllocationBacktestResponse, hypotheticalReplayResult: HypotheticalReplayResponse | null) {
  const diagnostics = activeReplay.diagnostics_comparison
  const candidateDiagnostics = activeReplay.candidate_diagnostics ?? null
  const referenceDiagnostics = activeReplay.reference_diagnostics ?? null
  const historyTruthLabel = formatReplayHistoricalBasisLabel(
    candidateDiagnostics?.provenance.historical_basis ?? referenceDiagnostics?.provenance.historical_basis ?? null,
  )
  const provenanceNote = candidateDiagnostics?.provenance.note ?? referenceDiagnostics?.provenance.note ?? 'Replay diagnostics provenance is unavailable for this watch surface.'
  const provenance = `${historyTruthLabel}. ${provenanceNote}`
  const diagnosticsReady = Boolean(diagnostics && candidateDiagnostics)
  const diagnosticsConfidence = confidenceFromReplay(activeReplay, diagnosticsReady)

  const monitors: MonitorItem[] = [
    monitorFromCallout('factor-drift', 'Factor Drift', diagnostics?.top_factor_exposure_change ?? null, provenance, diagnosticsConfidence, 'No factor-drift callout is available for the current replay state.'),
    monitorFromCallout('concentration-drift', 'Concentration Drift', diagnostics?.top_concentration_change ?? null, provenance, diagnosticsConfidence, 'No concentration-drift callout is available for the current replay state.'),
    benchmarkRelativeMonitor(activeReplay.comparison, activeReplay, provenance, diagnosticsConfidence),
    volatilityMonitor(diagnostics?.top_volatility_change ?? null, activeReplay, candidateDiagnostics, provenance, diagnosticsConfidence),
    dataQualityMonitor(activeReplay, candidateDiagnostics, referenceDiagnostics),
  ]

  const topCallouts: MonitorCallout[] = [
    diagnostics?.top_factor_exposure_change ? {
      key: 'top-factor-callout',
      label: 'Top Factor Callout',
      value: `${diagnostics.top_factor_exposure_change.label} ${comparisonValue(diagnostics.top_factor_exposure_change)}`,
      helper: diagnostics.top_factor_exposure_change.rationale,
      tone: toneFromMagnitude(diagnostics.top_factor_exposure_change.delta_value, 0.2, 0.08),
    } : null,
    diagnostics?.top_concentration_change ? {
      key: 'top-concentration-callout',
      label: 'Top Concentration Callout',
      value: `${diagnostics.top_concentration_change.label} ${comparisonValue(diagnostics.top_concentration_change)}`,
      helper: diagnostics.top_concentration_change.rationale,
      tone: toneFromMagnitude(diagnostics.top_concentration_change.delta_value, 0.2, 0.08),
    } : null,
    {
      key: 'data-quality-callout',
      label: 'Data Quality',
      value: monitors.find((item) => item.key === 'data-quality')?.currentStatus ?? 'N/A',
      helper: monitors.find((item) => item.key === 'data-quality')?.recentChange ?? 'N/A',
      tone: monitors.find((item) => item.key === 'data-quality')?.tone ?? 'neutral',
    },
  ].filter((item): item is MonitorCallout => item != null)

  const contextNote = hypotheticalReplayResult
    ? `Monitoring reflects the active hypothetical replay for ${hypotheticalReplayResult.proposal.incumbent_symbol} -> ${hypotheticalReplayResult.proposal.candidate_symbol}.`
    : 'Monitoring reflects the latest shared replay evidence available in the workspace.'

  return {
    monitors,
    topCallouts,
    contextNote,
    provenance,
    diagnosticsConfidence,
  }
}

function buildResearchHandoffPayload(
  selectedMonitor: MonitorItem,
  hypotheticalReplayResult: HypotheticalReplayResponse | null,
  monitorDefinitionId: MonitorDefinitionId | null,
): MonitoringResearchHandoff {
  const replayContext = hypotheticalReplayResult
    ? `${hypotheticalReplayResult.proposal.incumbent_symbol} -> ${hypotheticalReplayResult.proposal.candidate_symbol}`
    : null

  return {
    version: MONITORING_RESEARCH_HANDOFF_VERSION,
    source: 'monitoring',
    monitorKey: selectedMonitor.key,
    monitorTitle: selectedMonitor.title,
    researchTarget: selectedMonitor.researchTarget ?? 'diagnostics_change',
    contextLabel: selectedMonitor.currentStatus,
    replayContext,
    monitorDefinitionReview: monitorDefinitionId
      ? {
          source: 'definition_scoped_alert_review_entrypoint',
          monitorDefinitionId,
        }
      : null,
  }
}

export function MonitoringPanel({
  result,
  hypotheticalReplayResult,
  onReviewInResearch,
}: {
  result: PortfolioAllocationBacktestResponse | null
  hypotheticalReplayResult: HypotheticalReplayResponse | null
  onReviewInResearch?: (handoff: MonitoringResearchHandoff) => void
}) {
  const activeReplay = hypotheticalReplayResult ? ('replay' in hypotheticalReplayResult ? hypotheticalReplayResult.replay : hypotheticalReplayResult.overlay_replay) : result
  const monitoringState = useMemo(() => activeReplay ? buildMonitors(activeReplay, hypotheticalReplayResult) : null, [activeReplay, hypotheticalReplayResult])
  const [selectedKey, setSelectedKey] = useState<string>('factor-drift')
  const [monitorDefinitionId, setMonitorDefinitionId] = useState<MonitorDefinitionId | null>(null)
  const [disciplineOverviewState, setDisciplineOverviewState] = useState<MonitoringDisciplineOverviewState>({ status: 'idle', overview: null })
  const [dataQualityOverviewState, setDataQualityOverviewState] = useState<DataQualityDisciplineOverviewState>({ status: 'idle', overview: null })

  useEffect(() => {
    let active = true
    setDisciplineOverviewState({ status: 'loading', overview: null })

    void (async () => {
      try {
        const response = await fetch(MONITORING_DISCIPLINE_CATALOG_URL)
        const payload = await response.json()
        if (!response.ok) {
          throw new Error((payload as { detail?: string }).detail ?? 'Unable to load monitoring discipline overview')
        }
        const rows = validateMonitoringDisciplineCatalog(payload)
        if (!active) return
        if (!rows) {
          setDisciplineOverviewState({ status: 'invalid', overview: null })
          return
        }
        setDisciplineOverviewState({ status: 'ready', overview: buildMonitoringDisciplineOverview(rows) })
      } catch {
        if (!active) return
        setDisciplineOverviewState({ status: 'unavailable', overview: null })
      }
    })()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    setDataQualityOverviewState({ status: 'loading', overview: null })

    void (async () => {
      try {
        const response = await fetch(DATA_QUALITY_DISCIPLINE_CATALOG_URL)
        const payload = await response.json()
        if (!response.ok) {
          throw new Error((payload as { detail?: string }).detail ?? 'Unable to load data-quality monitor overview')
        }
        const rows = validateDataQualityDisciplineCatalog(payload)
        if (!active) return
        if (!rows) {
          setDataQualityOverviewState({ status: 'invalid', overview: null })
          return
        }
        setDataQualityOverviewState({ status: 'ready', overview: buildMonitoringDisciplineOverview(rows) })
      } catch {
        if (!active) return
        setDataQualityOverviewState({ status: 'unavailable', overview: null })
      }
    })()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!activeReplay || !onReviewInResearch) return

    let active = true
    void (async () => {
      try {
        const response = await fetch('/api/backtests/monitor-definitions/recent?limit=1&overlay_family=benchmark_trend&monitor_id=benchmark_trend_overlay_v1&review_support_status=review_supported&lifecycle_status=enabled')
        const payload = await response.json()
        if (!response.ok) {
          throw new Error((payload as { detail?: string }).detail ?? 'Unable to load recent monitor definitions')
        }
        const recentId = (payload as { items?: Array<{ monitor_definition_id?: unknown; monitor_id?: unknown }> }).items?.[0]?.monitor_definition_id
        const recentMonitorId = (payload as { items?: Array<{ monitor_definition_id?: unknown; monitor_id?: unknown }> }).items?.[0]?.monitor_id
        if (!active) return
        if (typeof recentId === 'string' && recentId.trim() && recentMonitorId === MONITOR_DEFINITION_MONITOR_ID) {
          setMonitorDefinitionId(recentId)
          return
        }
        setMonitorDefinitionId(null)
      } catch {
        if (!active) return
        setMonitorDefinitionId(null)
      }
    })()

    return () => {
      active = false
    }
  }, [activeReplay, onReviewInResearch])

  const selectedMonitor = monitoringState?.monitors.find((item) => item.key === selectedKey) ?? monitoringState?.monitors[0] ?? null
  const monitorFamilyReadiness = monitoringState && activeReplay ? buildMonitorFamilyReadiness(disciplineOverviewState, dataQualityOverviewState, monitoringState.monitors, activeReplay) : []

  if (!activeReplay || !monitoringState) {
    return (
      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Monitoring</p></div>
        </div>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Monitoring is waiting for replay evidence.</p>
          <p className="helper">Run or reopen a replay to populate this view.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-bottom-grid monitoring-panel-shell" data-testid="monitoring-panel">
      <div className="section-header-inline sector-list-header">
        <div>
          <p className="panel-label">Monitoring</p>
          <h3>Watch surface</h3>
        </div>
      </div>

      <div className="summary-card monitoring-context-card">
        <p className="stat-label">Current Context</p>
        <p className="helper">{monitoringState.contextNote}</p>
        <div className="tab-bar dashboard-meta-row-quant diagnostics-provenance-strip">
          <span className="backtest-source-badge">Candidate {activeReplay.candidate_result?.status ?? 'not provided'}</span>
          <span className="backtest-source-badge">Diagnostics confidence {monitoringState.diagnosticsConfidence}</span>
          <span className="backtest-source-badge">Reference {activeReplay.reference_result?.status ?? 'not provided'}</span>
        </div>
      </div>

      <section className="summary-card monitoring-context-card" data-testid="monitoring-discipline-overview">
        <div className="section-header-inline sector-list-header">
          <div>
            <p className="panel-label">Persisted Monitor Discipline Review</p>
            <h3>Monitoring Discipline Overview</h3>
          </div>
        </div>
        <p className="helper">Coverage, freshness, lifecycle, and review readiness from backend-rooted persisted metadata only. No scheduling or evaluation triggers are started from this panel.</p>

        {disciplineOverviewState.status === 'loading' || disciplineOverviewState.status === 'idle' ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Loading persisted monitor metadata.</p>
            <p className="helper">Reading the benchmark-trend monitor definition catalog.</p>
          </div>
        ) : null}

        {disciplineOverviewState.status === 'unavailable' ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Monitoring discipline overview is unavailable.</p>
            <p className="helper">The persisted monitor-definition catalog could not be loaded.</p>
          </div>
        ) : null}

        {disciplineOverviewState.status === 'invalid' ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Monitoring discipline overview failed validation.</p>
            <p className="helper">Catalog metadata or row lineage did not match the persisted benchmark-trend monitor definition contract, so no counts were computed.</p>
          </div>
        ) : null}

        {disciplineOverviewState.status === 'ready' && disciplineOverviewState.overview ? (
          disciplineOverviewState.overview.rows.length === 0 ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">No persisted benchmark-trend monitor definitions are available.</p>
              <p className="helper">The catalog returned no rows for benchmark_trend_overlay_v1.</p>
            </div>
          ) : (
            <>
              <div className="dashboard-summary compact-summary-grid monitoring-callout-grid">
                <div className="summary-card metric-card metric-card-neutral">
                  <p className="stat-label">Coverage</p>
                  <p className="summary-value">{disciplineOverviewState.overview.enabledCount} / {disciplineOverviewState.overview.persistedCount}</p>
                  <p className="helper">enabled / persisted definitions</p>
                </div>
                <div className="summary-card metric-card metric-card-neutral">
                  <p className="stat-label">Latest Observation</p>
                  <p className="summary-value">{formatCounts(disciplineOverviewState.overview.latestObservationPresenceCounts)}</p>
                  <p className="helper">freshness: {formatCounts(disciplineOverviewState.overview.latestObservationFreshnessCounts)}</p>
                </div>
                <div className="summary-card metric-card metric-card-neutral">
                  <p className="stat-label">Lifecycle / Review</p>
                  <p className="summary-value">{formatCounts(disciplineOverviewState.overview.lifecycleCounts)}</p>
                  <p className="helper">review: {formatCounts(disciplineOverviewState.overview.reviewReadinessCounts)}</p>
                </div>
                <div className="summary-card metric-card metric-card-neutral">
                  <p className="stat-label">Latest State</p>
                  <p className="summary-value">{formatCounts(disciplineOverviewState.overview.latestStateCounts)}</p>
                  <p className="helper">snapshot presence: {formatCounts(disciplineOverviewState.overview.latestSnapshotPresenceCounts)}</p>
                </div>
              </div>

              <div className="list-table">
                <div className="list-row list-row-wide">
                  <span>Definition</span>
                  <span>Benchmark</span>
                  <span>Lifecycle</span>
                  <span>Observation</span>
                  <span>Snapshot</span>
                </div>
                {disciplineOverviewState.overview.rows.slice(0, 5).map((row) => {
                  const status = row.metadata.status
                  return (
                    <div className="list-row list-row-wide" key={row.monitor_definition_id}>
                      <span>{row.monitor_definition_id}</span>
                      <span>{row.benchmark_symbol}</span>
                      <span>{status.lifecycle.lifecycle_status} / {status.lifecycle.review_support_status}</span>
                      <span>{formatLatestObservationLabel(status)}</span>
                      <span>{formatLatestSnapshotLabel(status)}</span>
                    </div>
                  )
                })}
              </div>
            </>
          )
        ) : null}
      </section>

      <section className="summary-card monitoring-context-card" data-testid="data-quality-monitor-family-overview">
        <div className="section-header-inline sector-list-header">
          <div>
            <p className="panel-label">Persisted Data Quality Monitor</p>
            <h3>Data Quality Family</h3>
          </div>
        </div>
        <p className="helper">Review-only input reliability evidence from persisted data_quality_monitor_v1 rows. No remediation, scheduling, or evaluation trigger is exposed.</p>
        {dataQualityOverviewState.status === 'ready' && dataQualityOverviewState.overview ? (
          dataQualityOverviewState.overview.rows.length === 0 ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">No persisted data-quality monitor definitions are available.</p>
              <p className="helper">Data quality is supported only as a persisted `data_quality_monitor_v1` family; no replay-only data-quality family is promoted.</p>
            </div>
          ) : (
            <div className="dashboard-summary compact-summary-grid monitoring-callout-grid">
              <div className="summary-card metric-card metric-card-neutral"><p className="stat-label">Definitions</p><p className="summary-value">{dataQualityOverviewState.overview.persistedCount}</p><p className="helper">persisted data-quality rows</p></div>
              <div className="summary-card metric-card metric-card-neutral"><p className="stat-label">Enabled / Review</p><p className="summary-value">{dataQualityOverviewState.overview.enabledCount} / {formatCounts(dataQualityOverviewState.overview.reviewReadinessCounts)}</p><p className="helper">review-supported persisted definitions</p></div>
              <div className="summary-card metric-card metric-card-neutral"><p className="stat-label">Latest Observation</p><p className="summary-value">{formatCounts(dataQualityOverviewState.overview.latestObservationPresenceCounts)}</p><p className="helper">freshness: {formatCounts(dataQualityOverviewState.overview.latestObservationFreshnessCounts)}</p></div>
              <div className="summary-card metric-card metric-card-neutral"><p className="stat-label">Outcomes</p><p className="summary-value">{formatCounts(dataQualityOverviewState.overview.latestStateCounts)}</p><p className="helper">ok / degraded / unavailable only</p></div>
            </div>
          )
        ) : (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Data-quality persisted family is {dataQualityOverviewState.status === 'invalid' ? 'invalid' : dataQualityOverviewState.status === 'unavailable' ? 'unavailable' : 'loading'}.</p>
            <p className="helper">Rows are rendered only after fail-closed catalog validation.</p>
          </div>
        )}
      </section>

      <section className="summary-card monitoring-context-card" data-testid="monitor-family-readiness-overview">
        <div className="section-header-inline sector-list-header">
          <div>
            <p className="panel-label">Monitor Family Readiness</p>
            <h3>Monitor Family Readiness Overview</h3>
          </div>
        </div>
        <p className="helper">Persisted benchmark-trend and data-quality readiness is separated from replay-derived signals. Signal rows are evidence readouts only and do not create monitor definitions, thresholds, or review handoffs.</p>
        <div className="list-table">
          <div className="list-row list-row-wide">
            <span>Family</span>
            <span>Source</span>
            <span>Decision / Reason</span>
            <span>Evidence / Provenance</span>
            <span>Gate Breakdown</span>
          </div>
          {monitorFamilyReadiness.map((row) => (
            <div className="list-row list-row-wide" key={row.familyId}>
              <span>{row.label}</span>
              <span>{row.source}</span>
              <span>{formatReadinessDecision(row.readinessDecision)} / {row.readinessStatus} / {row.reasonCode}</span>
              <span>{row.evidenceSummary} Provenance: {row.provenanceSummary}</span>
              <span>{formatGateBreakdown(row.gates)}</span>
            </div>
          ))}
        </div>
      </section>

      <div className="dashboard-summary compact-summary-grid monitoring-callout-grid">
        {monitoringState.topCallouts.map((callout) => (
          <div className={cardClass(callout.tone)} key={callout.key}>
            <p className="stat-label">{callout.label}</p>
            <p className="summary-value">{callout.value}</p>
            <p className="helper">{callout.helper}</p>
          </div>
        ))}
      </div>

      <div className="monitoring-grid">
        <section className="monitoring-list-card">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Watch Groups</p></div>
          </div>
          <div className="list-table">
            <div className="list-row list-row-wide">
              <span>Group</span>
              <span>Status</span>
              <span>Recent Change</span>
              <span>Severity</span>
              <span>Confidence</span>
            </div>
            {monitoringState.monitors.map((item) => (
              <button className={`list-row list-row-wide list-row-button${selectedMonitor?.key === item.key ? ' active' : ''}`} key={item.key} onClick={() => setSelectedKey(item.key)} type="button">
                <span>{item.title}</span>
                <span className={rowToneClass(item.tone)}>{item.currentStatus}</span>
                <span>{item.recentChange}</span>
                <span className={rowToneClass(item.tone)}>{item.severity}</span>
                <span>{item.confidence}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="monitoring-detail-card">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Detail</p></div>
          </div>
          {selectedMonitor ? (
            <div className={cardClass(selectedMonitor.tone)}>
              <p className="stat-label">{selectedMonitor.title}</p>
              <p className="summary-value">{selectedMonitor.currentStatus}</p>
              <p className="helper">{selectedMonitor.recentChange} · {selectedMonitor.severity} severity · {selectedMonitor.confidence} confidence</p>
              <p className="helper">{selectedMonitor.provenance}</p>
              {selectedMonitor.researchTarget && onReviewInResearch && monitorDefinitionId ? (
                <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
                  <button
                    className="secondary-button"
                    onClick={() => onReviewInResearch(buildResearchHandoffPayload(selectedMonitor, hypotheticalReplayResult, monitorDefinitionId))}
                    type="button"
                  >
                    Review In Workspace
                  </button>
                </div>
              ) : null}
              <div className="monitoring-detail-list">
                {selectedMonitor.detail.map((item) => (
                  <p className="helper monitoring-detail-item" key={item}>{item}</p>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">No monitoring detail is available.</p>
              <p className="helper">The current replay did not expose enough diagnostics detail for a watch-group drilldown.</p>
            </div>
          )}
        </section>
      </div>
    </section>
  )
}

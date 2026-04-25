import type { CSSProperties } from 'react'
import { useMemo, useState } from 'react'
import { investorEconomicsBaseReason } from '../portfolio/investorEconomics'
import type {
  CrossSectionalResearchArtifact,
  CrossSectionalResearchArtifactProvenance,
  CrossSectionalResearchBenchmark,
  CrossSectionalResearchCompactSummary,
  CrossSectionalResearchDiscoveryFilters,
  CrossSectionalResearchRecentResponse,
  CrossSectionalResearchRecentRow,
  CrossSectionalResearchReloadResponse,
  CrossSectionalResearchRequest,
  EtfMomentumStrategyResponse as EtfMomentumResponse,
  OptimizerAlphaFundamentalSnapshot,
} from '../portfolio/types'

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
type ResearchFilterKey = keyof CrossSectionalResearchDiscoveryFilters

const CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND = 'cross_sectional_research_run'
const CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION = 'cross_sectional_research_artifact_v1'
const CROSS_SECTIONAL_RESEARCH_RELOAD_CONTRACT_VERSION = 'cross_sectional_research_reload_v1'
const CROSS_SECTIONAL_RESEARCH_DISCOVERY_CONTRACT_VERSION = 'cross_sectional_research_discovery_v1'
const CROSS_SECTIONAL_RESEARCH_METHODOLOGY_ID = 'alpha_quality_v1'
const CROSS_SECTIONAL_RESEARCH_METHODOLOGY_FAMILY_ID = 'cross_sectional_research_family_v1'
const CROSS_SECTIONAL_RESEARCH_METHODOLOGY_VERSION = 'v1'
const CROSS_SECTIONAL_RESEARCH_ALPHA_PACKAGE_VERSION = 'alpha_quality_v1'
const CROSS_SECTIONAL_RESEARCH_ALPHA_METHODOLOGY_ID = 'alpha_quality_v1_methodology'
const CROSS_SECTIONAL_RESEARCH_ALPHA_INPUT_CONTRACT_ID = 'alpha_quality_v1_pit_fundamentals_v1'
const CROSS_SECTIONAL_RESEARCH_SCORE_BASIS = 'optimizer_alpha_package.final_score'
const CROSS_SECTIONAL_RESEARCH_BENCHMARK_ROLE = 'descriptive_reference_only'
const CROSS_SECTIONAL_RESEARCH_PARTITION_RULE = 'effective_date_before_holdout_start_else_holdout'
const CROSS_SECTIONAL_RESEARCH_OUTPUT_SHAPE = 'compact_summary_only'

const CROSS_SECTIONAL_RESEARCH_ALLOWED_FILTER_NAMES = [
  'artifact_kind',
  'schema_version',
  'methodology_id',
  'dataset_version',
  'universe_definition',
  'benchmark_symbol',
  'rebalance_date',
  'as_of_date',
  'holdout_start_date',
  'methodology_family_id',
  'methodology_family_version',
  'active_methodology_version',
  'alpha_package_version',
  'alpha_methodology_id',
  'alpha_input_contract_id',
  'score_basis',
  'benchmark_role',
  'partition_rule',
  'output_shape',
  'artifact_status',
  'diagnostics_status',
  'coverage_status',
  'input_source_kind',
  'replay_provenance_status',
  'benchmark_source_kind',
  'alpha_source_kind',
] as const satisfies CrossSectionalResearchRecentResponse['metadata']['supported_filters']

const CROSS_SECTIONAL_RESEARCH_ALLOWED_COMPONENT_SIGNAL_IDS = [
  'profitability',
  'cash_generation',
  'accrual_quality',
  'leverage_discipline',
] as const satisfies CrossSectionalResearchArtifact['methodology_metadata_v1']['component_signal_ids']

const CROSS_SECTIONAL_RESEARCH_ALLOWED_ARTIFACT_STATUS = [
  'complete',
  'degraded',
  'unknown',
  'unsupported',
] as const satisfies readonly CrossSectionalResearchArtifact['status_metadata_v1']['artifact_status'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_COVERAGE_STATUS = [
  'complete',
  'partial',
  'unknown',
  'unsupported',
] as const satisfies readonly CrossSectionalResearchArtifact['status_metadata_v1']['coverage_status'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_DIAGNOSTICS_STATUS = [
  'ok',
  'invalid',
  'unknown',
  'unsupported',
] as const satisfies readonly CrossSectionalResearchArtifact['status_metadata_v1']['diagnostics_status'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_INPUT_SOURCE_KIND = [
  'direct_snapshot_input',
  'replay_snapshot_input',
  'backend_owned_other',
  'unknown',
  'unsupported',
] as const satisfies readonly CrossSectionalResearchArtifact['provenance_metadata_v1']['input_source_kind'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_REPLAY_PROVENANCE_STATUS = [
  'present',
  'absent',
  'unknown',
  'unsupported',
] as const satisfies readonly CrossSectionalResearchArtifact['provenance_metadata_v1']['replay_provenance_status'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_BENCHMARK_SOURCE_KIND = [
  'request_benchmark_reference',
  'unknown',
  'unsupported',
] as const satisfies readonly CrossSectionalResearchArtifact['provenance_metadata_v1']['benchmark_source_kind'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_ALPHA_SOURCE_KIND = [
  'optimizer_alpha_package',
  'unknown',
  'unsupported',
] as const satisfies readonly CrossSectionalResearchArtifact['provenance_metadata_v1']['alpha_source_kind'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_BENCHMARK_KIND = [
  'reference_index',
  'etf_proxy',
  'custom',
] as const satisfies readonly CrossSectionalResearchBenchmark['benchmark_kind'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_SPLIT_LABEL = [
  'walk_forward',
  'holdout',
] as const satisfies readonly CrossSectionalResearchCompactSummary['split_label'][]

const OPTIMIZER_ALPHA_ALLOWED_PERIOD_TYPES = [
  'quarterly',
  'annual',
] as const satisfies readonly OptimizerAlphaFundamentalSnapshot['period_type'][]

const OPTIMIZER_ALPHA_ALLOWED_AVAILABILITY_SEMANTICS = [
  'available_date',
  'publication_date',
  'filing_date',
  'derived_reporting_lag',
] as const satisfies readonly NonNullable<OptimizerAlphaFundamentalSnapshot['availability_semantics']>[]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_METADATA_TRUTH = [
  'authoritative_persisted_artifact_metadata',
] as const satisfies readonly CrossSectionalResearchRecentResponse['metadata']['metadata_truth'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_RECENT_ORDER_BASIS = [
  'persisted_artifact.persisted_at_then_artifact_id',
] as const satisfies readonly CrossSectionalResearchRecentResponse['metadata']['recent_order_basis'][]

const CROSS_SECTIONAL_RESEARCH_ALLOWED_METADATA_SEMANTICS = [
  'descriptive_only',
] as const satisfies readonly CrossSectionalResearchRecentResponse['metadata']['methodology_metadata_v1_semantics'][]

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value != null && !Array.isArray(value)
}

function readRecord(value: unknown, label: string) {
  if (!isRecord(value)) {
    throw new Error(`${label} must be an object`)
  }
  return value
}

function readString(value: unknown, label: string) {
  if (typeof value !== 'string') {
    throw new Error(`${label} must be a string`)
  }
  return value
}

function readOptionalString(value: unknown, label: string) {
  if (value == null) return null
  return readString(value, label)
}

function readNumber(value: unknown, label: string) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    throw new Error(`${label} must be a number`)
  }
  return value
}

function readOptionalNumber(value: unknown, label: string) {
  if (value === undefined) return undefined
  if (value == null) return null
  return readNumber(value, label)
}

function readOptionalNullableString(value: unknown, label: string) {
  if (value === undefined) return undefined
  if (value == null) return null
  return readString(value, label)
}

function readBoolean(value: unknown, label: string) {
  if (typeof value !== 'boolean') {
    throw new Error(`${label} must be a boolean`)
  }
  return value
}

function readStringArray(value: unknown, label: string) {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    throw new Error(`${label} must be a string array`)
  }
  return value
}

function readLiteral<T extends string>(value: unknown, allowedValues: readonly T[], label: string): T {
  const stringValue = readString(value, label)
  if (!allowedValues.includes(stringValue as T)) {
    throw new Error(`${label} must be one of: ${allowedValues.join(', ')}`)
  }
  return stringValue as T
}

function readOptionalLiteral<T extends string>(value: unknown, allowedValues: readonly T[], label: string) {
  if (value == null) return null
  return readLiteral(value, allowedValues, label)
}

function readOptionalNullableLiteral<T extends string>(value: unknown, allowedValues: readonly T[], label: string) {
  if (value === undefined) return undefined
  if (value == null) return null
  return readLiteral(value, allowedValues, label)
}

function readLiteralArray<T extends string>(value: unknown, allowedValues: readonly T[], label: string): T[] {
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be a string array`)
  }
  return value.map((item, index) => readLiteral(item, allowedValues, `${label}[${index}]`))
}

function readObjectArray(value: unknown, label: string) {
  if (!Array.isArray(value) || value.some((item) => !isRecord(item))) {
    throw new Error(`${label} must be an object array`)
  }
  return value
}

function readFundamentalSnapshot(value: unknown, label: string): OptimizerAlphaFundamentalSnapshot {
  const record = readRecord(value, label)
  return {
    source_dataset: readOptionalNullableString(record.source_dataset, `${label}.source_dataset`),
    source_record_id: readOptionalNullableString(record.source_record_id, `${label}.source_record_id`),
    symbol: readString(record.symbol, `${label}.symbol`),
    issuer_id: readOptionalNullableString(record.issuer_id, `${label}.issuer_id`),
    statement_date: readString(record.statement_date, `${label}.statement_date`),
    period_type: readLiteral(record.period_type, OPTIMIZER_ALPHA_ALLOWED_PERIOD_TYPES, `${label}.period_type`),
    publication_date: readOptionalNullableString(record.publication_date, `${label}.publication_date`),
    filing_date: readOptionalNullableString(record.filing_date, `${label}.filing_date`),
    available_date: readOptionalNullableString(record.available_date, `${label}.available_date`),
    availability_semantics: readOptionalNullableLiteral(record.availability_semantics, OPTIMIZER_ALPHA_ALLOWED_AVAILABILITY_SEMANTICS, `${label}.availability_semantics`),
    currency: readOptionalNullableString(record.currency, `${label}.currency`),
    total_revenue: readOptionalNumber(record.total_revenue, `${label}.total_revenue`),
    cost_of_revenue: readOptionalNumber(record.cost_of_revenue, `${label}.cost_of_revenue`),
    ebit: readOptionalNumber(record.ebit, `${label}.ebit`),
    total_assets: readOptionalNumber(record.total_assets, `${label}.total_assets`),
    operating_cash_flow: readOptionalNumber(record.operating_cash_flow, `${label}.operating_cash_flow`),
    free_cash_flow: readOptionalNumber(record.free_cash_flow, `${label}.free_cash_flow`),
    net_income: readOptionalNumber(record.net_income, `${label}.net_income`),
    total_debt: readOptionalNumber(record.total_debt, `${label}.total_debt`),
    cash_and_equivalents: readOptionalNumber(record.cash_and_equivalents, `${label}.cash_and_equivalents`),
  }
}

function readFundamentalSnapshots(value: unknown, label: string): OptimizerAlphaFundamentalSnapshot[] {
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be an array`)
  }
  return value.map((item, index) => readFundamentalSnapshot(item, `${label}[${index}]`))
}

function readRecentMethodologyId(
  value: unknown,
  label: string,
): CrossSectionalResearchRecentRow['methodology_id'] {
  return readLiteral(value, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_ID] as const, label)
}

function readDiscoveryFilters(value: unknown, label: string): CrossSectionalResearchDiscoveryFilters {
  const record = readRecord(value, label)
  const artifactKind = readOptionalLiteral(record.artifact_kind, [CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND] as const, `${label}.artifact_kind`)
  const schemaVersion = readOptionalLiteral(record.schema_version, [CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION] as const, `${label}.schema_version`)
  const methodologyId = readOptionalLiteral(record.methodology_id, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_ID] as const, `${label}.methodology_id`)
  const datasetVersion = record.dataset_version == null ? null : readString(record.dataset_version, `${label}.dataset_version`)
  const universeDefinition = record.universe_definition == null ? null : readString(record.universe_definition, `${label}.universe_definition`)
  const benchmarkSymbol = record.benchmark_symbol == null ? null : readString(record.benchmark_symbol, `${label}.benchmark_symbol`)
  const rebalanceDate = record.rebalance_date == null ? null : readString(record.rebalance_date, `${label}.rebalance_date`)
  const asOfDate = record.as_of_date == null ? null : readString(record.as_of_date, `${label}.as_of_date`)
  const holdoutStartDate = record.holdout_start_date == null ? null : readString(record.holdout_start_date, `${label}.holdout_start_date`)
  const methodologyFamilyId = readOptionalLiteral(record.methodology_family_id, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_FAMILY_ID] as const, `${label}.methodology_family_id`)
  const methodologyFamilyVersion = readOptionalLiteral(record.methodology_family_version, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_VERSION] as const, `${label}.methodology_family_version`)
  const activeMethodologyVersion = readOptionalLiteral(record.active_methodology_version, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_VERSION] as const, `${label}.active_methodology_version`)
  const alphaPackageVersion = readOptionalLiteral(record.alpha_package_version, [CROSS_SECTIONAL_RESEARCH_ALPHA_PACKAGE_VERSION] as const, `${label}.alpha_package_version`)
  const alphaMethodologyId = readOptionalLiteral(record.alpha_methodology_id, [CROSS_SECTIONAL_RESEARCH_ALPHA_METHODOLOGY_ID] as const, `${label}.alpha_methodology_id`)
  const alphaInputContractId = readOptionalLiteral(record.alpha_input_contract_id, [CROSS_SECTIONAL_RESEARCH_ALPHA_INPUT_CONTRACT_ID] as const, `${label}.alpha_input_contract_id`)
  const scoreBasis = readOptionalLiteral(record.score_basis, [CROSS_SECTIONAL_RESEARCH_SCORE_BASIS] as const, `${label}.score_basis`)
  const benchmarkRole = readOptionalLiteral(record.benchmark_role, [CROSS_SECTIONAL_RESEARCH_BENCHMARK_ROLE] as const, `${label}.benchmark_role`)
  const partitionRule = readOptionalLiteral(record.partition_rule, [CROSS_SECTIONAL_RESEARCH_PARTITION_RULE] as const, `${label}.partition_rule`)
  const outputShape = readOptionalLiteral(record.output_shape, [CROSS_SECTIONAL_RESEARCH_OUTPUT_SHAPE] as const, `${label}.output_shape`)
  const artifactStatus = readOptionalLiteral(record.artifact_status, CROSS_SECTIONAL_RESEARCH_ALLOWED_ARTIFACT_STATUS, `${label}.artifact_status`)
  const diagnosticsStatus = readOptionalLiteral(record.diagnostics_status, CROSS_SECTIONAL_RESEARCH_ALLOWED_DIAGNOSTICS_STATUS, `${label}.diagnostics_status`)
  const coverageStatus = readOptionalLiteral(record.coverage_status, CROSS_SECTIONAL_RESEARCH_ALLOWED_COVERAGE_STATUS, `${label}.coverage_status`)
  const inputSourceKind = readOptionalLiteral(record.input_source_kind, CROSS_SECTIONAL_RESEARCH_ALLOWED_INPUT_SOURCE_KIND, `${label}.input_source_kind`)
  const replayProvenanceStatus = readOptionalLiteral(record.replay_provenance_status, CROSS_SECTIONAL_RESEARCH_ALLOWED_REPLAY_PROVENANCE_STATUS, `${label}.replay_provenance_status`)
  const benchmarkSourceKind = readOptionalLiteral(record.benchmark_source_kind, CROSS_SECTIONAL_RESEARCH_ALLOWED_BENCHMARK_SOURCE_KIND, `${label}.benchmark_source_kind`)
  const alphaSourceKind = readOptionalLiteral(record.alpha_source_kind, CROSS_SECTIONAL_RESEARCH_ALLOWED_ALPHA_SOURCE_KIND, `${label}.alpha_source_kind`)
  return {
    artifact_kind: artifactKind,
    schema_version: schemaVersion,
    methodology_id: methodologyId,
    dataset_version: datasetVersion,
    universe_definition: universeDefinition,
    benchmark_symbol: benchmarkSymbol,
    rebalance_date: rebalanceDate,
    as_of_date: asOfDate,
    holdout_start_date: holdoutStartDate,
    methodology_family_id: methodologyFamilyId,
    methodology_family_version: methodologyFamilyVersion,
    active_methodology_version: activeMethodologyVersion,
    alpha_package_version: alphaPackageVersion,
    alpha_methodology_id: alphaMethodologyId,
    alpha_input_contract_id: alphaInputContractId,
    score_basis: scoreBasis,
    benchmark_role: benchmarkRole,
    partition_rule: partitionRule,
    output_shape: outputShape,
    artifact_status: artifactStatus,
    diagnostics_status: diagnosticsStatus,
    coverage_status: coverageStatus,
    input_source_kind: inputSourceKind,
    replay_provenance_status: replayProvenanceStatus,
    benchmark_source_kind: benchmarkSourceKind,
    alpha_source_kind: alphaSourceKind,
  }
}

function readMethodologyMetadata(value: unknown, label: string) {
  const record = readRecord(value, label)
  return {
    methodology_family_id: readLiteral(record.methodology_family_id, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_FAMILY_ID] as const, `${label}.methodology_family_id`),
    methodology_family_version: readLiteral(record.methodology_family_version, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_VERSION] as const, `${label}.methodology_family_version`),
    active_methodology_id: readLiteral(record.active_methodology_id, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_ID] as const, `${label}.active_methodology_id`),
    active_methodology_version: readLiteral(record.active_methodology_version, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_VERSION] as const, `${label}.active_methodology_version`),
    alpha_package_version: readLiteral(record.alpha_package_version, [CROSS_SECTIONAL_RESEARCH_ALPHA_PACKAGE_VERSION] as const, `${label}.alpha_package_version`),
    alpha_methodology_id: readLiteral(record.alpha_methodology_id, [CROSS_SECTIONAL_RESEARCH_ALPHA_METHODOLOGY_ID] as const, `${label}.alpha_methodology_id`),
    alpha_input_contract_id: readLiteral(record.alpha_input_contract_id, [CROSS_SECTIONAL_RESEARCH_ALPHA_INPUT_CONTRACT_ID] as const, `${label}.alpha_input_contract_id`),
    score_basis: readLiteral(record.score_basis, [CROSS_SECTIONAL_RESEARCH_SCORE_BASIS] as const, `${label}.score_basis`),
    benchmark_role: readLiteral(record.benchmark_role, [CROSS_SECTIONAL_RESEARCH_BENCHMARK_ROLE] as const, `${label}.benchmark_role`),
    partition_rule: readLiteral(record.partition_rule, [CROSS_SECTIONAL_RESEARCH_PARTITION_RULE] as const, `${label}.partition_rule`),
    output_shape: readLiteral(record.output_shape, [CROSS_SECTIONAL_RESEARCH_OUTPUT_SHAPE] as const, `${label}.output_shape`),
    component_signal_ids: readLiteralArray(record.component_signal_ids, CROSS_SECTIONAL_RESEARCH_ALLOWED_COMPONENT_SIGNAL_IDS, `${label}.component_signal_ids`),
  }
}

function readStatusMetadata(value: unknown, label: string) {
  const record = readRecord(value, label)
  return {
    artifact_status: readLiteral(record.artifact_status, CROSS_SECTIONAL_RESEARCH_ALLOWED_ARTIFACT_STATUS, `${label}.artifact_status`),
    diagnostics_status: readLiteral(record.diagnostics_status, CROSS_SECTIONAL_RESEARCH_ALLOWED_DIAGNOSTICS_STATUS, `${label}.diagnostics_status`),
    coverage_status: readLiteral(record.coverage_status, CROSS_SECTIONAL_RESEARCH_ALLOWED_COVERAGE_STATUS, `${label}.coverage_status`),
  }
}

function readProvenanceMetadata(value: unknown, label: string) {
  const record = readRecord(value, label)
  return {
    input_source_kind: readLiteral(record.input_source_kind, CROSS_SECTIONAL_RESEARCH_ALLOWED_INPUT_SOURCE_KIND, `${label}.input_source_kind`),
    replay_provenance_status: readLiteral(record.replay_provenance_status, CROSS_SECTIONAL_RESEARCH_ALLOWED_REPLAY_PROVENANCE_STATUS, `${label}.replay_provenance_status`),
    benchmark_source_kind: readLiteral(record.benchmark_source_kind, CROSS_SECTIONAL_RESEARCH_ALLOWED_BENCHMARK_SOURCE_KIND, `${label}.benchmark_source_kind`),
    alpha_source_kind: readLiteral(record.alpha_source_kind, CROSS_SECTIONAL_RESEARCH_ALLOWED_ALPHA_SOURCE_KIND, `${label}.alpha_source_kind`),
  }
}

function readResearchBenchmark(value: unknown, label: string): CrossSectionalResearchBenchmark {
  const record = readRecord(value, label)
  return {
    benchmark_symbol: readString(record.benchmark_symbol, `${label}.benchmark_symbol`),
    benchmark_name: readOptionalString(record.benchmark_name, `${label}.benchmark_name`),
    benchmark_kind: readLiteral(record.benchmark_kind, CROSS_SECTIONAL_RESEARCH_ALLOWED_BENCHMARK_KIND, `${label}.benchmark_kind`),
  }
}

function readSummaryProvenance(value: unknown, label: string): CrossSectionalResearchCompactSummary['provenance'] {
  const record = readRecord(value, label)
  return {
    alpha_package_id: readString(record.alpha_package_id, `${label}.alpha_package_id`),
    alpha_package_version: readString(record.alpha_package_version, `${label}.alpha_package_version`),
    alpha_methodology_id: readString(record.alpha_methodology_id, `${label}.alpha_methodology_id`),
    input_digest: readString(record.input_digest, `${label}.input_digest`),
    source_name: readString(record.source_name, `${label}.source_name`),
    as_of_date: readString(record.as_of_date, `${label}.as_of_date`),
    rebalance_date: readString(record.rebalance_date, `${label}.rebalance_date`),
    holdout_start_date: readString(record.holdout_start_date, `${label}.holdout_start_date`),
    benchmark_symbol: readString(record.benchmark_symbol, `${label}.benchmark_symbol`),
    benchmark_kind: readLiteral(record.benchmark_kind, CROSS_SECTIONAL_RESEARCH_ALLOWED_BENCHMARK_KIND, `${label}.benchmark_kind`),
    partition_rule: readString(record.partition_rule, `${label}.partition_rule`),
  }
}

function readCompactSummary(value: unknown, label: string): CrossSectionalResearchCompactSummary {
  const record = readRecord(value, label)
  return {
    split_label: readLiteral(record.split_label, CROSS_SECTIONAL_RESEARCH_ALLOWED_SPLIT_LABEL, `${label}.split_label`),
    sample_count: readNumber(record.sample_count, `${label}.sample_count`),
    universe_size: readNumber(record.universe_size, `${label}.universe_size`),
    coverage_ratio: readNumber(record.coverage_ratio, `${label}.coverage_ratio`),
    complete_coverage_ratio: readNumber(record.complete_coverage_ratio, `${label}.complete_coverage_ratio`),
    mean_score: record.mean_score == null ? null : readNumber(record.mean_score, `${label}.mean_score`),
    median_score: record.median_score == null ? null : readNumber(record.median_score, `${label}.median_score`),
    positive_score_share: record.positive_score_share == null ? null : readNumber(record.positive_score_share, `${label}.positive_score_share`),
    top_ranked_symbols: readStringArray(record.top_ranked_symbols, `${label}.top_ranked_symbols`),
    effective_start_date: readOptionalString(record.effective_start_date, `${label}.effective_start_date`),
    effective_end_date: readOptionalString(record.effective_end_date, `${label}.effective_end_date`),
    provenance: readSummaryProvenance(record.provenance, `${label}.provenance`),
  }
}

function readArtifactProvenance(value: unknown, label: string): CrossSectionalResearchArtifactProvenance {
  const record = readRecord(value, label)
  return {
    source_name: readString(record.source_name, `${label}.source_name`),
    replay_id: readOptionalString(record.replay_id, `${label}.replay_id`),
    input_digest: readString(record.input_digest, `${label}.input_digest`),
    alpha_input_contract_id: readLiteral(record.alpha_input_contract_id, [CROSS_SECTIONAL_RESEARCH_ALPHA_INPUT_CONTRACT_ID] as const, `${label}.alpha_input_contract_id`),
    point_in_time_only: readBoolean(record.point_in_time_only, `${label}.point_in_time_only`),
    alpha_package_id: readString(record.alpha_package_id, `${label}.alpha_package_id`),
    alpha_package_version: readString(record.alpha_package_version, `${label}.alpha_package_version`),
    alpha_diagnostics_status: readLiteral(record.alpha_diagnostics_status, ['ok', 'invalid'] as const, `${label}.alpha_diagnostics_status`),
    coverage_ratio: readNumber(record.coverage_ratio, `${label}.coverage_ratio`),
    complete_coverage_ratio: readNumber(record.complete_coverage_ratio, `${label}.complete_coverage_ratio`),
    missing_snapshot_symbols: readStringArray(record.missing_snapshot_symbols, `${label}.missing_snapshot_symbols`),
    stale_symbols: readStringArray(record.stale_symbols, `${label}.stale_symbols`),
    lag_blocked_symbols: readStringArray(record.lag_blocked_symbols, `${label}.lag_blocked_symbols`),
    fallback_symbols: readStringArray(record.fallback_symbols, `${label}.fallback_symbols`),
  }
}

function readResearchRequest(value: unknown, label: string): CrossSectionalResearchRequest {
  const record = readRecord(value, label)
  return {
    methodology_id: readLiteral(record.methodology_id, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_ID] as const, `${label}.methodology_id`),
    rebalance_date: readString(record.rebalance_date, `${label}.rebalance_date`),
    as_of_date: readString(record.as_of_date, `${label}.as_of_date`),
    holdout_start_date: readString(record.holdout_start_date, `${label}.holdout_start_date`),
    dataset_version: readString(record.dataset_version, `${label}.dataset_version`),
    universe_definition: readString(record.universe_definition, `${label}.universe_definition`),
    benchmark: readResearchBenchmark(record.benchmark, `${label}.benchmark`),
    universe_symbols: readStringArray(record.universe_symbols, `${label}.universe_symbols`),
    fundamental_snapshots: readFundamentalSnapshots(record.fundamental_snapshots, `${label}.fundamental_snapshots`),
    source_name: readString(record.source_name, `${label}.source_name`),
    replay_id: readOptionalString(record.replay_id, `${label}.replay_id`),
    top_ranked_count: readNumber(record.top_ranked_count, `${label}.top_ranked_count`),
  }
}

function parseCrossSectionalResearchRecentResponse(payload: unknown): CrossSectionalResearchRecentResponse {
  const record = readRecord(payload, 'cross-sectional research recent response')
  const metadata = readRecord(record.metadata, 'cross-sectional research recent response.metadata')
  readLiteral(
    metadata.contract_version,
    [CROSS_SECTIONAL_RESEARCH_DISCOVERY_CONTRACT_VERSION] as const,
    'cross-sectional research recent response.metadata.contract_version',
  )
  const appliedFilters = readDiscoveryFilters(record.applied_filters, 'cross-sectional research recent response.applied_filters')
  const metadataAppliedFilters = readDiscoveryFilters(metadata.applied_filters, 'cross-sectional research recent response.metadata.applied_filters')
  if (JSON.stringify(appliedFilters) !== JSON.stringify(metadataAppliedFilters)) {
    throw new Error('Research discovery metadata applied_filters mismatch')
  }
  const items = readObjectArray(record.items, 'cross-sectional research recent response.items').map((item, index) => {
    const artifactId = readString(item.artifact_id, `cross-sectional research recent response.items[${index}].artifact_id`)
    const recentOrderArtifactId = readString(item.recent_order_artifact_id, `cross-sectional research recent response.items[${index}].recent_order_artifact_id`)
    if (artifactId !== recentOrderArtifactId) {
      throw new Error('Research recent row identity mismatch')
    }
    return {
      artifact_id: artifactId,
      fingerprint: readString(item.fingerprint, `cross-sectional research recent response.items[${index}].fingerprint`),
      methodology_id: readRecentMethodologyId(item.methodology_id, `cross-sectional research recent response.items[${index}].methodology_id`),
      methodology_metadata_v1: readMethodologyMetadata(item.methodology_metadata_v1, `cross-sectional research recent response.items[${index}].methodology_metadata_v1`),
      status_metadata_v1: readStatusMetadata(item.status_metadata_v1, `cross-sectional research recent response.items[${index}].status_metadata_v1`),
      provenance_metadata_v1: readProvenanceMetadata(item.provenance_metadata_v1, `cross-sectional research recent response.items[${index}].provenance_metadata_v1`),
      dataset_version: readString(item.dataset_version, `cross-sectional research recent response.items[${index}].dataset_version`),
      universe_definition: readString(item.universe_definition, `cross-sectional research recent response.items[${index}].universe_definition`),
      benchmark_symbol: readString(item.benchmark_symbol, `cross-sectional research recent response.items[${index}].benchmark_symbol`),
      recent_order_persisted_at: readString(item.recent_order_persisted_at, `cross-sectional research recent response.items[${index}].recent_order_persisted_at`),
      recent_order_artifact_id: recentOrderArtifactId,
      rebalance_date: readString(item.rebalance_date, `cross-sectional research recent response.items[${index}].rebalance_date`),
      as_of_date: readString(item.as_of_date, `cross-sectional research recent response.items[${index}].as_of_date`),
      holdout_start_date: readString(item.holdout_start_date, `cross-sectional research recent response.items[${index}].holdout_start_date`),
      universe_size: readNumber(item.universe_size, `cross-sectional research recent response.items[${index}].universe_size`),
      walk_forward_sample_count: readNumber(item.walk_forward_sample_count, `cross-sectional research recent response.items[${index}].walk_forward_sample_count`),
      holdout_sample_count: readNumber(item.holdout_sample_count, `cross-sectional research recent response.items[${index}].holdout_sample_count`),
    }
  })
  return {
    items,
    applied_filters: appliedFilters,
    metadata: {
      contract_version: CROSS_SECTIONAL_RESEARCH_DISCOVERY_CONTRACT_VERSION,
      metadata_truth: readLiteral(metadata.metadata_truth, CROSS_SECTIONAL_RESEARCH_ALLOWED_METADATA_TRUTH, 'cross-sectional research recent response.metadata.metadata_truth'),
      recent_order_basis: readLiteral(metadata.recent_order_basis, CROSS_SECTIONAL_RESEARCH_ALLOWED_RECENT_ORDER_BASIS, 'cross-sectional research recent response.metadata.recent_order_basis'),
      supported_filters: readLiteralArray(metadata.supported_filters, CROSS_SECTIONAL_RESEARCH_ALLOWED_FILTER_NAMES, 'cross-sectional research recent response.metadata.supported_filters'),
      methodology_metadata_v1_semantics: readLiteral(metadata.methodology_metadata_v1_semantics, CROSS_SECTIONAL_RESEARCH_ALLOWED_METADATA_SEMANTICS, 'cross-sectional research recent response.metadata.methodology_metadata_v1_semantics'),
      status_metadata_v1_semantics: readLiteral(metadata.status_metadata_v1_semantics, CROSS_SECTIONAL_RESEARCH_ALLOWED_METADATA_SEMANTICS, 'cross-sectional research recent response.metadata.status_metadata_v1_semantics'),
      provenance_metadata_v1_semantics: readLiteral(metadata.provenance_metadata_v1_semantics, CROSS_SECTIONAL_RESEARCH_ALLOWED_METADATA_SEMANTICS, 'cross-sectional research recent response.metadata.provenance_metadata_v1_semantics'),
      applied_filters: metadataAppliedFilters,
    },
  }
}

function parseCrossSectionalResearchArtifact(value: unknown): CrossSectionalResearchArtifact {
  const record = readRecord(value, 'cross-sectional research artifact')
  const artifactKind = readLiteral(record.artifact_kind, [CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND] as const, 'cross-sectional research artifact.artifact_kind')
  const schemaVersion = readLiteral(record.schema_version, [CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION] as const, 'cross-sectional research artifact.schema_version')
  const request = readResearchRequest(record.request, 'cross-sectional research artifact.request')
  const provenance = readArtifactProvenance(record.provenance, 'cross-sectional research artifact.provenance')
  return {
    schema_version: schemaVersion,
    artifact_kind: artifactKind,
    artifact_id: readString(record.artifact_id, 'cross-sectional research artifact.artifact_id'),
    fingerprint: readString(record.fingerprint, 'cross-sectional research artifact.fingerprint'),
    run_id: readString(record.run_id, 'cross-sectional research artifact.run_id'),
    persisted_at: readString(record.persisted_at, 'cross-sectional research artifact.persisted_at'),
    methodology_id: readLiteral(record.methodology_id, [CROSS_SECTIONAL_RESEARCH_METHODOLOGY_ID] as const, 'cross-sectional research artifact.methodology_id'),
    request,
    methodology: readString(record.methodology, 'cross-sectional research artifact.methodology'),
    methodology_metadata_v1: readMethodologyMetadata(record.methodology_metadata_v1, 'cross-sectional research artifact.methodology_metadata_v1'),
    status_metadata_v1: readStatusMetadata(record.status_metadata_v1, 'cross-sectional research artifact.status_metadata_v1'),
    provenance_metadata_v1: readProvenanceMetadata(record.provenance_metadata_v1, 'cross-sectional research artifact.provenance_metadata_v1'),
    assumptions: readStringArray(record.assumptions, 'cross-sectional research artifact.assumptions'),
    dataset_version: readString(record.dataset_version, 'cross-sectional research artifact.dataset_version'),
    universe_definition: readString(record.universe_definition, 'cross-sectional research artifact.universe_definition'),
    benchmark: readResearchBenchmark(record.benchmark, 'cross-sectional research artifact.benchmark'),
    walk_forward_summary: readCompactSummary(record.walk_forward_summary, 'cross-sectional research artifact.walk_forward_summary'),
    holdout_summary: readCompactSummary(record.holdout_summary, 'cross-sectional research artifact.holdout_summary'),
    provenance,
  }
}

function parseCrossSectionalResearchReloadResponse(
  payload: unknown,
  requestedArtifactId: string,
): CrossSectionalResearchReloadResponse {
  const record = readRecord(payload, 'cross-sectional research reload response')
  const contractVersion = readLiteral(record.contract_version, [CROSS_SECTIONAL_RESEARCH_RELOAD_CONTRACT_VERSION] as const, 'cross-sectional research reload response.contract_version')
  const artifactId = readString(record.artifact_id, 'cross-sectional research reload response.artifact_id')
  const requestedId = readString(record.requested_artifact_id, 'cross-sectional research reload response.requested_artifact_id')
  const artifactKind = readLiteral(record.artifact_kind, [CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND] as const, 'cross-sectional research reload response.artifact_kind')
  const schemaVersion = readLiteral(record.schema_version, [CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION] as const, 'cross-sectional research reload response.schema_version')
  const artifact = parseCrossSectionalResearchArtifact(record.artifact)
  if (requestedId !== requestedArtifactId || artifactId !== requestedArtifactId || artifact.artifact_id !== requestedArtifactId) {
    throw new Error('Research artifact response identity mismatch')
  }
  if (artifactKind !== artifact.artifact_kind || schemaVersion !== artifact.schema_version) {
    throw new Error('Research artifact response contract mismatch')
  }
  return {
    contract_version: contractVersion,
    requested_artifact_id: requestedId,
    artifact_id: artifactId,
    artifact_kind: artifactKind as CrossSectionalResearchReloadResponse['artifact_kind'],
    schema_version: schemaVersion as CrossSectionalResearchReloadResponse['schema_version'],
    artifact,
  }
}

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

function researchStatusLabel(status: CrossSectionalResearchArtifact['status_metadata_v1']['artifact_status']) {
  if (status === 'complete') return 'Complete'
  if (status === 'degraded') return 'Degraded'
  if (status === 'unknown') return 'Unknown'
  return 'Unsupported'
}

function researchCoverageLabel(status: CrossSectionalResearchArtifact['status_metadata_v1']['coverage_status']) {
  if (status === 'complete') return 'Coverage complete'
  if (status === 'partial') return 'Coverage partial'
  if (status === 'unknown') return 'Coverage unknown'
  return 'Coverage unsupported'
}

function researchReplayLabel(status: CrossSectionalResearchArtifact['provenance_metadata_v1']['replay_provenance_status']) {
  if (status === 'present') return 'Replay provenance present'
  if (status === 'absent') return 'Replay provenance absent'
  if (status === 'unknown') return 'Replay provenance unknown'
  return 'Replay provenance unsupported'
}

function buildResearchArtifactQuery(filters: CrossSectionalResearchDiscoveryFilters) {
  const params = new URLSearchParams({ limit: '5' })
  Object.entries(filters).forEach(([key, value]) => {
    if (value == null) return
    params.set(key, value)
  })
  return params.toString()
}

async function readJsonResponse<T>(response: Response, fallbackMessage: string) {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(typeof payload === 'object' && payload != null && 'detail' in payload && typeof payload.detail === 'string' ? payload.detail : fallbackMessage)
  }
  return payload as T
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
  const [researchRecentLoading, setResearchRecentLoading] = useState(false)
  const [researchRecentError, setResearchRecentError] = useState<string | null>(null)
  const [researchRecent, setResearchRecent] = useState<CrossSectionalResearchRecentResponse | null>(null)
  const [researchArtifactLoadingId, setResearchArtifactLoadingId] = useState<string | null>(null)
  const [researchArtifactError, setResearchArtifactError] = useState<string | null>(null)
  const [researchArtifact, setResearchArtifact] = useState<CrossSectionalResearchArtifact | null>(null)
  const [researchFilters, setResearchFilters] = useState<CrossSectionalResearchDiscoveryFilters>({
    artifact_kind: null,
    schema_version: null,
    methodology_id: null,
    dataset_version: null,
    universe_definition: null,
    benchmark_symbol: null,
    rebalance_date: null,
    as_of_date: null,
    holdout_start_date: null,
    methodology_family_id: null,
    methodology_family_version: null,
    active_methodology_version: null,
    alpha_package_version: null,
    alpha_methodology_id: null,
    alpha_input_contract_id: null,
    score_basis: null,
    benchmark_role: null,
    partition_rule: null,
    output_shape: null,
    artifact_status: null,
    diagnostics_status: null,
    coverage_status: null,
    input_source_kind: null,
    replay_provenance_status: null,
    benchmark_source_kind: null,
    alpha_source_kind: null,
  })

  function updateResearchFilter(key: ResearchFilterKey, value: string) {
    const normalizedValue = value.trim()
    const nextValue = normalizedValue ? (key === 'benchmark_symbol' ? normalizedValue.toUpperCase() : normalizedValue) : null
    setResearchFilters((current) => ({
      ...current,
      [key]: nextValue,
    }))
  }

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

  const activeResearchRecentRow = useMemo(() => {
    if (!researchArtifact) return null
    return researchRecent?.items.find((item) => item.artifact_id === researchArtifact.artifact_id) ?? null
  }, [researchArtifact, researchRecent?.items])

  async function loadRecentResearchArtifacts() {
    setResearchRecentLoading(true)
    setResearchRecentError(null)
    try {
      const response = await fetch(`${apiBase}/strategy-lab/cross-sectional-research/recent?${buildResearchArtifactQuery(researchFilters)}`)
      const payload = await readJsonResponse<unknown>(response, 'Research recent artifacts are unavailable')
      setResearchRecent(parseCrossSectionalResearchRecentResponse(payload))
    } catch (caughtError) {
      setResearchRecent(null)
      setResearchRecentError(caughtError instanceof Error ? caughtError.message : 'Research recent artifacts are unavailable')
    } finally {
      setResearchRecentLoading(false)
    }
  }

  async function loadResearchArtifact(artifactId: string) {
    setResearchArtifactLoadingId(artifactId)
    setResearchArtifactError(null)
    try {
      const response = await fetch(`${apiBase}/strategy-lab/cross-sectional-research/artifacts/${artifactId}`)
      const payload = await readJsonResponse<unknown>(response, 'Research artifact reload failed')
      const parsed = parseCrossSectionalResearchReloadResponse(payload, artifactId)
      setResearchArtifact(parsed.artifact)
    } catch (caughtError) {
      setResearchArtifactError(caughtError instanceof Error ? caughtError.message : 'Research artifact reload failed')
      setResearchArtifact(null)
    } finally {
      setResearchArtifactLoadingId(null)
    }
  }

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

      <section className="workspace-section">
        <div className="section-header-inline sector-list-header">
          <div>
            <p className="panel-label">Research Artifacts</p>
            <p className="helper">Recent and reload paths consume persisted artifacts only.</p>
          </div>
          <button className="secondary-button" type="button" onClick={() => void loadRecentResearchArtifacts()} disabled={researchRecentLoading}>
            {researchRecentLoading ? 'Loading research artifacts...' : 'Load Research Artifacts'}
          </button>
        </div>
        <div className="split-grid compact-split-grid strategy-lab-top-grid">
          <label className="field-group">
            <span className="field-label">Artifact Status</span>
            <select className="path-input strategy-select" value={researchFilters.artifact_status ?? ''} onChange={(event) => updateResearchFilter('artifact_status', event.target.value)}>
              <option value="">Any</option>
              {CROSS_SECTIONAL_RESEARCH_ALLOWED_ARTIFACT_STATUS.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Diagnostics</span>
            <select className="path-input strategy-select" value={researchFilters.diagnostics_status ?? ''} onChange={(event) => updateResearchFilter('diagnostics_status', event.target.value)}>
              <option value="">Any</option>
              {CROSS_SECTIONAL_RESEARCH_ALLOWED_DIAGNOSTICS_STATUS.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Coverage</span>
            <select className="path-input strategy-select" value={researchFilters.coverage_status ?? ''} onChange={(event) => updateResearchFilter('coverage_status', event.target.value)}>
              <option value="">Any</option>
              {CROSS_SECTIONAL_RESEARCH_ALLOWED_COVERAGE_STATUS.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Input Source</span>
            <select className="path-input strategy-select" value={researchFilters.input_source_kind ?? ''} onChange={(event) => updateResearchFilter('input_source_kind', event.target.value)}>
              <option value="">Any</option>
              {CROSS_SECTIONAL_RESEARCH_ALLOWED_INPUT_SOURCE_KIND.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Replay Provenance</span>
            <select className="path-input strategy-select" value={researchFilters.replay_provenance_status ?? ''} onChange={(event) => updateResearchFilter('replay_provenance_status', event.target.value)}>
              <option value="">Any</option>
              {CROSS_SECTIONAL_RESEARCH_ALLOWED_REPLAY_PROVENANCE_STATUS.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Benchmark Symbol</span>
            <input className="path-input" value={researchFilters.benchmark_symbol ?? ''} onChange={(event) => updateResearchFilter('benchmark_symbol', event.target.value)} placeholder="SPY" />
          </label>
          <label className="field-group">
            <span className="field-label">Dataset Version</span>
            <input className="path-input" value={researchFilters.dataset_version ?? ''} onChange={(event) => updateResearchFilter('dataset_version', event.target.value)} placeholder="alpha_quality_dataset_demo_v1" />
          </label>
          <label className="field-group">
            <span className="field-label">Methodology Family</span>
            <select className="path-input strategy-select" value={researchFilters.methodology_family_id ?? ''} onChange={(event) => updateResearchFilter('methodology_family_id', event.target.value)}>
              <option value="">Any</option>
              <option value={CROSS_SECTIONAL_RESEARCH_METHODOLOGY_FAMILY_ID}>{CROSS_SECTIONAL_RESEARCH_METHODOLOGY_FAMILY_ID}</option>
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Alpha Package</span>
            <select className="path-input strategy-select" value={researchFilters.alpha_package_version ?? ''} onChange={(event) => updateResearchFilter('alpha_package_version', event.target.value)}>
              <option value="">Any</option>
              <option value={CROSS_SECTIONAL_RESEARCH_ALPHA_PACKAGE_VERSION}>{CROSS_SECTIONAL_RESEARCH_ALPHA_PACKAGE_VERSION}</option>
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Score Basis</span>
            <select className="path-input strategy-select" value={researchFilters.score_basis ?? ''} onChange={(event) => updateResearchFilter('score_basis', event.target.value)}>
              <option value="">Any</option>
              <option value={CROSS_SECTIONAL_RESEARCH_SCORE_BASIS}>{CROSS_SECTIONAL_RESEARCH_SCORE_BASIS}</option>
            </select>
          </label>
        </div>
        {researchRecentError ? <p className="error">{researchRecentError}</p> : null}
        {researchArtifactError ? <p className="error">{researchArtifactError}</p> : null}
        {researchRecent ? (
          <div className="factor-snapshot-table-wrap" data-testid="research-artifact-list">
            <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-rank-grid-wide">
              <span>Artifact</span>
              <span>Status</span>
              <span>Coverage</span>
              <span>Dataset</span>
              <span>Persisted</span>
              <span>Open</span>
            </div>
            {researchRecent.items.length ? researchRecent.items.map((item) => (
              <div className="risk-contrib-table-grid factor-shift-data-row strategy-lab-rank-grid-wide" key={item.artifact_id}>
                <span className="factor-snapshot-primary">{item.artifact_id}</span>
                <span>{researchStatusLabel(item.status_metadata_v1.artifact_status)}</span>
                <span>{researchCoverageLabel(item.status_metadata_v1.coverage_status)}</span>
                <span>{item.dataset_version}</span>
                <span>{item.recent_order_persisted_at}</span>
                <span>
                  <button
                    className={`secondary-button${researchArtifactLoadingId === item.artifact_id ? ' button-loading' : ''}`}
                    type="button"
                    onClick={() => void loadResearchArtifact(item.artifact_id)}
                    disabled={researchArtifactLoadingId === item.artifact_id}
                  >
                    {researchArtifactLoadingId === item.artifact_id ? 'Loading...' : researchArtifact?.artifact_id === item.artifact_id ? 'Loaded' : 'Open Artifact'}
                  </button>
                </span>
              </div>
            )) : <p className="helper">No persisted research artifacts found.</p>}
          </div>
        ) : null}
        {researchArtifact ? (
          <div className="strategy-detail-stack" data-testid="research-artifact-detail">
            <div className="summary-card strategy-summary-card strategy-summary-card-primary">
              <p className="stat-label">Research Status</p>
              <p className="summary-value">{researchStatusLabel(researchArtifact.status_metadata_v1.artifact_status)}</p>
              <p className="helper">{researchCoverageLabel(researchArtifact.status_metadata_v1.coverage_status)} · {researchReplayLabel(researchArtifact.provenance_metadata_v1.replay_provenance_status)}</p>
            </div>
            <div className="factor-snapshot-table-wrap">
              <div className="section-header-inline sector-list-header strategy-detail-subheader">
                <div>
                  <p className="panel-label">Persisted Research Contract</p>
                  <p className="helper">Backend-owned labels and metadata are rendered directly from the persisted artifact.</p>
                </div>
              </div>
              <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-history-grid">
                <span>Methodology</span>
                <span>Benchmark</span>
                <span>Input Source</span>
                <span>Diagnostics</span>
                <span>Persisted</span>
              </div>
              <div className="risk-contrib-table-grid factor-shift-data-row strategy-lab-history-grid">
                <span>{researchArtifact.methodology_metadata_v1.active_methodology_id}</span>
                <span>{researchArtifact.benchmark.benchmark_symbol}</span>
                <span>{researchArtifact.provenance_metadata_v1.input_source_kind}</span>
                <span>{researchArtifact.status_metadata_v1.diagnostics_status}</span>
                <span>{activeResearchRecentRow?.recent_order_persisted_at ?? researchArtifact.persisted_at}</span>
              </div>
            </div>
            <div className="factor-snapshot-table-wrap">
              <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-history-grid">
                <span>Walk-Forward</span>
                <span>Holdout</span>
                <span>Dataset</span>
                <span>Universe</span>
                <span>Artifact Kind</span>
              </div>
              <div className="risk-contrib-table-grid factor-shift-data-row strategy-lab-history-grid">
                <span>{researchArtifact.walk_forward_summary.sample_count}</span>
                <span>{researchArtifact.holdout_summary.sample_count}</span>
                <span>{researchArtifact.dataset_version}</span>
                <span>{researchArtifact.universe_definition}</span>
                <span>{researchArtifact.artifact_kind}</span>
              </div>
            </div>
          </div>
        ) : null}
      </section>

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

// Universe spec types
export type UniverseKind =
  | 'etf_peer_group'
  | 'custom_list'
  | 'broad_equity_screen'
  | 'sector_screen';

export interface UniverseSpec {
  universe_id: string;
  universe_kind: UniverseKind;
  universe_label?: string | null;
  explicit_symbols: string[];
  min_market_cap_usd?: number | null;
  min_adv_usd?: number | null;
  price_floor_usd?: number | null;
  allowed_exchanges: string[];
  sector_include: string[];
  sector_exclude: string[];
  country_iso2: string[];
  exclude_etf: boolean;
  exclude_adr: boolean;
}

export type FactorFamily =
  | 'momentum'
  | 'volatility'
  | 'liquidity'
  | 'quality'
  | 'value'
  | 'sentiment';

export type NormalizationMethod =
  | 'cross_sectional_zscore'
  | 'percentile_rank'
  | 'minmax';

export interface FactorConfig {
  factor_id: string;
  family: FactorFamily;
  direction: 'higher_is_better' | 'lower_is_better';
  weight: number;
  lookback_days?: number | null;
  raw_unit: string;
}

export interface ScoreConfig {
  score_config_id: string;
  score_config_version: string;
  normalization: NormalizationMethod;
  winsorize_pct: number;
  factors: FactorConfig[];
}

// Request
export interface GenericRankingRequest {
  universe_spec: UniverseSpec;
  score_config: ScoreConfig;
  benchmark_symbol: string;
  lookback_months: number;
  prefer_live_data: boolean;
}

// Artifact / response types
export type RankingConfidence = 'full' | 'partial' | 'degraded';

export interface ScoreConfigRef {
  score_config_id: string;
  score_config_version: string;
  score_config_digest: string;
  factor_ids: string[];
  normalization: string;
  winsorize_pct: number;
}

export interface UniverseSpecSnapshot {
  spec_version: string;
  universe_id: string;
  universe_kind: string;
  spec_digest: string;
  evaluated_members: string[];
  evaluated_at: string;
}

export interface GenericRankingComponentScore {
  label: string;
  family: FactorFamily;
  direction: 'higher_is_better' | 'lower_is_better';
  raw_value: number | null;
  raw_unit: string;
  normalized_score: number | null;
  normalization_method: string;
  weight: number;
  weighted_score: number | null;
}

export interface EligibilityRecord {
  eligibility_status: 'eligible' | 'excluded';
  hard_filter_failures: string[];
  soft_filter_flags: string[];
}

export interface GenericRankingRow {
  rank: number;
  symbol: string;
  composite_score: number;
  component_scores: Record<string, GenericRankingComponentScore>;
  eligibility: EligibilityRecord;
}

export interface GenericRankingExcludedInstrument {
  symbol: string;
  eligibility: EligibilityRecord;
}

export interface GenericRankingRunMetadata {
  ranking_id: string;
  methodology_id: string;
  as_of_date: string;
  ranking_basis_date: string;
  price_basis: string;
  confidence: RankingConfidence;
  score_config_ref: ScoreConfigRef;
}

export interface GenericRankingArtifact {
  schema_version: 'generic_ranking_artifact_v1';
  artifact_id: string;
  ranking_id: string;
  methodology_id: string;
  title: string;
  as_of_date: string;
  benchmark_symbol: string;
  lookback_months: number;
  universe_spec_snapshot: UniverseSpecSnapshot;
  run_metadata: GenericRankingRunMetadata;
  ranked_universe: GenericRankingRow[];
  excluded_instruments: GenericRankingExcludedInstrument[];
  warnings: string[];
}

export interface GenericRankingArtifactRecentRow {
  artifact_id: string;
  ranking_id: string;
  methodology_id: string;
  as_of_date: string;
  ranking_basis_date: string;
  benchmark_symbol: string;
  lookback_months: number;
  universe_id: string;
  universe_kind: string;
  score_config_id: string;
  evaluated_universe_size: number;
  confidence: RankingConfidence;
}

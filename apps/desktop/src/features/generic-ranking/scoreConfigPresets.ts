import type { ScoreConfig } from './types'

// Preset 1: Momentum + Volatility (ETF-style, works on any universe)
export const MOMENTUM_VOLATILITY_PRESET: ScoreConfig = {
  score_config_id: 'momentum_volatility_v1',
  score_config_version: 'v1',
  normalization: 'cross_sectional_zscore',
  winsorize_pct: 0.05,
  factors: [
    { factor_id: 'momentum_6m',              family: 'momentum',   direction: 'higher_is_better', weight: 0.30, lookback_days: 126, raw_unit: 'pct' },
    { factor_id: 'momentum_12m',             family: 'momentum',   direction: 'higher_is_better', weight: 0.20, lookback_days: 252, raw_unit: 'pct' },
    { factor_id: 'realized_volatility_126d', family: 'volatility', direction: 'lower_is_better',  weight: 0.25, lookback_days: 126, raw_unit: 'pct' },
    { factor_id: 'max_drawdown_252d',        family: 'volatility', direction: 'lower_is_better',  weight: 0.15, lookback_days: 252, raw_unit: 'pct' },
    { factor_id: 'liquidity_60d',            family: 'liquidity',  direction: 'higher_is_better', weight: 0.10, lookback_days: 60,  raw_unit: 'volume' },
  ],
}

// Preset 2: Pure Momentum
export const MOMENTUM_PRESET: ScoreConfig = {
  score_config_id: 'momentum_blended_v1',
  score_config_version: 'v1',
  normalization: 'cross_sectional_zscore',
  winsorize_pct: 0.05,
  factors: [
    { factor_id: 'momentum_1m',  family: 'momentum', direction: 'higher_is_better', weight: 0.15, lookback_days: 21,  raw_unit: 'pct' },
    { factor_id: 'momentum_3m',  family: 'momentum', direction: 'higher_is_better', weight: 0.25, lookback_days: 63,  raw_unit: 'pct' },
    { factor_id: 'momentum_6m',  family: 'momentum', direction: 'higher_is_better', weight: 0.35, lookback_days: 126, raw_unit: 'pct' },
    { factor_id: 'momentum_12m', family: 'momentum', direction: 'higher_is_better', weight: 0.25, lookback_days: 252, raw_unit: 'pct' },
  ],
}

export const SCORE_CONFIG_PRESETS = [MOMENTUM_VOLATILITY_PRESET, MOMENTUM_PRESET]

export const SCORE_CONFIG_PRESET_LABELS: Record<string, string> = {
  momentum_volatility_v1: 'Momentum + Volatility',
  momentum_blended_v1: 'Pure Momentum',
}

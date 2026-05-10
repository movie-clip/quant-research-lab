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

// Preset 3: Quality (Phase 2 — requires FMP fundamental data)
export const QUALITY_PRESET: ScoreConfig = {
  score_config_id: 'quality_v1',
  score_config_version: 'v1',
  normalization: 'cross_sectional_zscore',
  winsorize_pct: 0.05,
  factors: [
    { factor_id: 'quality_profitability',   family: 'quality', direction: 'higher_is_better', weight: 0.35, raw_unit: 'ratio' },
    { factor_id: 'quality_cash_generation', family: 'quality', direction: 'higher_is_better', weight: 0.30, raw_unit: 'ratio' },
    { factor_id: 'quality_accrual',         family: 'quality', direction: 'lower_is_better',  weight: 0.20, raw_unit: 'ratio' },
    { factor_id: 'quality_leverage',        family: 'quality', direction: 'lower_is_better',  weight: 0.15, raw_unit: 'ratio' },
  ],
}

// Preset 4: Value (Phase 2 — requires FMP fundamental data)
export const VALUE_PRESET: ScoreConfig = {
  score_config_id: 'value_v1',
  score_config_version: 'v1',
  normalization: 'cross_sectional_zscore',
  winsorize_pct: 0.05,
  factors: [
    { factor_id: 'value_earnings_yield',    family: 'value', direction: 'higher_is_better', weight: 0.35, raw_unit: 'ratio' },
    { factor_id: 'value_book_to_market',    family: 'value', direction: 'higher_is_better', weight: 0.20, raw_unit: 'ratio' },
    { factor_id: 'value_fcf_yield',         family: 'value', direction: 'higher_is_better', weight: 0.25, raw_unit: 'ratio' },
    { factor_id: 'value_ev_ebitda_inverse', family: 'value', direction: 'higher_is_better', weight: 0.20, raw_unit: 'ratio' },
  ],
}

// Preset 5: Quality + Value composite (S&P/AQR-style multi-factor blend)
export const QUALITY_VALUE_PRESET: ScoreConfig = {
  score_config_id: 'quality_value_v1',
  score_config_version: 'v1',
  normalization: 'cross_sectional_zscore',
  winsorize_pct: 0.05,
  factors: [
    // Quality half (50% total weight, equal-weighted across 4 sub-factors)
    { factor_id: 'quality_profitability',   family: 'quality', direction: 'higher_is_better', weight: 0.125, raw_unit: 'ratio' },
    { factor_id: 'quality_cash_generation', family: 'quality', direction: 'higher_is_better', weight: 0.125, raw_unit: 'ratio' },
    { factor_id: 'quality_accrual',         family: 'quality', direction: 'lower_is_better',  weight: 0.125, raw_unit: 'ratio' },
    { factor_id: 'quality_leverage',        family: 'quality', direction: 'lower_is_better',  weight: 0.125, raw_unit: 'ratio' },
    // Value half (50% total)
    { factor_id: 'value_earnings_yield',    family: 'value',   direction: 'higher_is_better', weight: 0.125, raw_unit: 'ratio' },
    { factor_id: 'value_book_to_market',    family: 'value',   direction: 'higher_is_better', weight: 0.125, raw_unit: 'ratio' },
    { factor_id: 'value_fcf_yield',         family: 'value',   direction: 'higher_is_better', weight: 0.125, raw_unit: 'ratio' },
    { factor_id: 'value_ev_ebitda_inverse', family: 'value',   direction: 'higher_is_better', weight: 0.125, raw_unit: 'ratio' },
  ],
}

export const SCORE_CONFIG_PRESETS = [
  MOMENTUM_VOLATILITY_PRESET,
  MOMENTUM_PRESET,
  QUALITY_PRESET,
  VALUE_PRESET,
  QUALITY_VALUE_PRESET,
]

export const SCORE_CONFIG_PRESET_LABELS: Record<string, string> = {
  momentum_volatility_v1: 'Momentum + Volatility',
  momentum_blended_v1: 'Pure Momentum',
  quality_v1: 'Quality (Novy-Marx, Sloan)',
  value_v1: 'Value (Greenblatt, Fama-French)',
  quality_value_v1: 'Quality + Value Composite',
}

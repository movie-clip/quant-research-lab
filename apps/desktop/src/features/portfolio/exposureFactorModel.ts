import type { ExposureFactorModelResponse, ImportedExposureFactorModelSource } from './types'

export const DEFAULT_FACTOR_MODEL_METHODOLOGY = 'Orthogonalized rolling ridge factor model using US ETF proxies for market, style, sector, and macro exposures; UCITS symbols are shown separately as EU execution examples.'

export function buildExposureFactorModelResponse(result: ImportedExposureFactorModelSource): ExposureFactorModelResponse {
  return {
    benchmark_symbol: result.statistical_factor_model.benchmark_symbol || result.benchmark?.symbol || 'SPY',
    methodology: result.factor_methodology || DEFAULT_FACTOR_MODEL_METHODOLOGY,
    factor_registry: result.factor_registry,
    statistical_factor_model: result.statistical_factor_model,
  }
}

export const DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT = '0.60'
export const DEFAULT_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT = ''
export const MIN_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT = 0.5
export const MAX_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT = 1
export const MAX_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT = 0.5

const DECIMAL_WEIGHT_PATTERN = /^(?:\d+(?:\.\d+)?|\.\d+)$/

export type RankingConstructionMaxPositionWeightValidation = {
  value: number | null
  error: string | null
}

export type RankingConstructionMinPositionWeightValidation = {
  value: number | null
  error: string | null
}

export type RankingConstructionPositionWeightValidation = {
  maxPositionWeight: RankingConstructionMaxPositionWeightValidation
  minPositionWeight: RankingConstructionMinPositionWeightValidation
}

function isDecimalWeightInput(input: string) {
  return DECIMAL_WEIGHT_PATTERN.test(input)
}

function validateRequiredMaxPositionWeightInput(
  input: string | null | undefined,
): RankingConstructionMaxPositionWeightValidation {
  const normalized = input?.trim() ?? ''
  if (!normalized) {
    return { value: null, error: 'Enter a max position weight as a decimal between 0.5 and 1.' }
  }

  if (!isDecimalWeightInput(normalized)) {
    return { value: null, error: 'Enter a numeric max position weight as a decimal between 0.5 and 1.' }
  }

  const value = Number(normalized)
  if (
    value < MIN_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT
    || value > MAX_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT
  ) {
    return { value: null, error: 'Max position weight must be between 0.5 and 1.' }
  }

  return { value, error: null }
}

function validateOptionalMinPositionWeightInput(
  input: string | null | undefined,
  maxPositionWeight: number | null,
): RankingConstructionMinPositionWeightValidation {
  const normalized = input?.trim() ?? ''
  if (!normalized) {
    return { value: null, error: null }
  }

  if (!isDecimalWeightInput(normalized)) {
    return { value: null, error: 'Enter a numeric min position weight as a decimal greater than 0 and up to 0.5.' }
  }

  const value = Number(normalized)
  if (value <= 0) {
    return { value: null, error: 'Min position weight must be greater than 0.' }
  }
  if (value > MAX_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT) {
    return { value: null, error: 'Min position weight must be less than or equal to 0.5.' }
  }
  if (maxPositionWeight != null && value > maxPositionWeight) {
    return { value: null, error: 'Min position weight must be less than or equal to max position weight.' }
  }

  return { value, error: null }
}

export function validateRankingConstructionPositionWeightInputs(params: {
  maxPositionWeightInput: string | null | undefined
  minPositionWeightInput?: string | null | undefined
}): RankingConstructionPositionWeightValidation {
  const maxPositionWeight = validateRequiredMaxPositionWeightInput(params.maxPositionWeightInput)
  const minPositionWeight = validateOptionalMinPositionWeightInput(
    params.minPositionWeightInput,
    maxPositionWeight.value,
  )

  return {
    maxPositionWeight,
    minPositionWeight,
  }
}

export function validateRankingConstructionMaxPositionWeightInput(
  input: string | null | undefined,
): RankingConstructionMaxPositionWeightValidation {
  return validateRankingConstructionPositionWeightInputs({
    maxPositionWeightInput: input,
  }).maxPositionWeight
}

export function validateRankingConstructionMinPositionWeightInput(params: {
  minPositionWeightInput: string | null | undefined
  maxPositionWeightInput: string | null | undefined
}): RankingConstructionMinPositionWeightValidation {
  return validateRankingConstructionPositionWeightInputs({
    maxPositionWeightInput: params.maxPositionWeightInput,
    minPositionWeightInput: params.minPositionWeightInput,
  }).minPositionWeight
}

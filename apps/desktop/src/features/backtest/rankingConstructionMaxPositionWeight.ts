export const DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT = '0.60'
export const DEFAULT_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT = ''
export const DEFAULT_RANKING_CONSTRUCTION_MAX_TURNOVER_WEIGHT = ''
export const DEFAULT_RANKING_CONSTRUCTION_MAX_TRADE_INTENT_COUNT = ''
export const DEFAULT_RANKING_CONSTRUCTION_MAX_SECTOR_WEIGHT = ''
export const DEFAULT_RANKING_CONSTRUCTION_TOP_N = '2'
export const MIN_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT = 0.5
export const MAX_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT = 1
export const MAX_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT = 0.5
export const MIN_RANKING_CONSTRUCTION_MAX_TURNOVER_WEIGHT = 0
export const MAX_RANKING_CONSTRUCTION_MAX_TURNOVER_WEIGHT = 1
export const MAX_RANKING_CONSTRUCTION_MAX_SECTOR_WEIGHT = 1
// Epic 3 breadth: configurable top_n at launch (was fixed at 2).
export const MIN_RANKING_CONSTRUCTION_TOP_N = 2
export const MAX_RANKING_CONSTRUCTION_TOP_N = 20

const DECIMAL_WEIGHT_PATTERN = /^(?:\d+(?:\.\d+)?|\.\d+)$/
const INTEGER_COUNT_PATTERN = /^\d+$/

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

export type RankingConstructionMaxTurnoverWeightValidation = {
  value: number | null
  error: string | null
}

export type RankingConstructionMaxTradeIntentCountValidation = {
  value: number | null
  error: string | null
}

export type RankingConstructionMaxSectorWeightValidation = {
  value: number | null
  error: string | null
}

export type RankingConstructionConstraintValidation = {
  maxPositionWeight: RankingConstructionMaxPositionWeightValidation
  minPositionWeight: RankingConstructionMinPositionWeightValidation
  maxTurnoverWeight: RankingConstructionMaxTurnoverWeightValidation
  maxTradeIntentCount: RankingConstructionMaxTradeIntentCountValidation
  maxSectorWeight: RankingConstructionMaxSectorWeightValidation
}

function isDecimalWeightInput(input: string) {
  return DECIMAL_WEIGHT_PATTERN.test(input)
}

function isIntegerCountInput(input: string) {
  return INTEGER_COUNT_PATTERN.test(input)
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

function validateOptionalMaxTurnoverWeightInput(
  input: string | null | undefined,
): RankingConstructionMaxTurnoverWeightValidation {
  const normalized = input?.trim() ?? ''
  if (!normalized) {
    return { value: null, error: null }
  }

  if (!isDecimalWeightInput(normalized)) {
    return { value: null, error: 'Enter a numeric max turnover weight as a decimal between 0 and 1.' }
  }

  const value = Number(normalized)
  if (
    value < MIN_RANKING_CONSTRUCTION_MAX_TURNOVER_WEIGHT
    || value > MAX_RANKING_CONSTRUCTION_MAX_TURNOVER_WEIGHT
  ) {
    return { value: null, error: 'Max turnover weight must be between 0 and 1.' }
  }

  return { value, error: null }
}

export type RankingConstructionTopNValidation = {
  value: number | null
  error: string | null
}

export function validateRankingConstructionTopNInput(
  input: string | null | undefined,
): RankingConstructionTopNValidation {
  const normalized = input?.trim() ?? ''
  if (!normalized) {
    return { value: null, error: `Top N is required. Enter a whole number between ${MIN_RANKING_CONSTRUCTION_TOP_N} and ${MAX_RANKING_CONSTRUCTION_TOP_N}.` }
  }
  if (!isIntegerCountInput(normalized)) {
    return { value: null, error: `Top N must be a whole number between ${MIN_RANKING_CONSTRUCTION_TOP_N} and ${MAX_RANKING_CONSTRUCTION_TOP_N}.` }
  }
  const value = Number(normalized)
  if (value < MIN_RANKING_CONSTRUCTION_TOP_N || value > MAX_RANKING_CONSTRUCTION_TOP_N) {
    return { value: null, error: `Top N must be between ${MIN_RANKING_CONSTRUCTION_TOP_N} and ${MAX_RANKING_CONSTRUCTION_TOP_N}.` }
  }
  return { value, error: null }
}


function validateOptionalMaxTradeIntentCountInput(
  input: string | null | undefined,
): RankingConstructionMaxTradeIntentCountValidation {
  const normalized = input?.trim() ?? ''
  if (!normalized) {
    return { value: null, error: null }
  }

  if (!isIntegerCountInput(normalized)) {
    return { value: null, error: 'Enter a whole-number max trade intent count of 0 or greater.' }
  }

  const value = Number(normalized)
  if (value < 0) {
    return { value: null, error: 'Max trade intent count must be 0 or greater.' }
  }

  return { value, error: null }
}

function validateOptionalMaxSectorWeightInput(
  input: string | null | undefined,
  maxPositionWeight: number | null,
): RankingConstructionMaxSectorWeightValidation {
  const normalized = input?.trim() ?? ''
  if (!normalized) {
    return { value: null, error: null }
  }

  if (!isDecimalWeightInput(normalized)) {
    return { value: null, error: 'Enter a numeric max sector weight as a decimal greater than 0 and up to 1.' }
  }

  const value = Number(normalized)
  if (value <= 0) {
    return { value: null, error: 'Max sector weight must be greater than 0.' }
  }
  if (value > MAX_RANKING_CONSTRUCTION_MAX_SECTOR_WEIGHT) {
    return { value: null, error: 'Max sector weight must be less than or equal to 1.' }
  }
  // Backend invariant: a single name in a sector already carries up to max_position_weight,
  // so the sector cap can never be tighter than the per-position cap.
  if (maxPositionWeight != null && value < maxPositionWeight) {
    return { value: null, error: 'Max sector weight must be greater than or equal to max position weight.' }
  }

  return { value, error: null }
}

export function validateRankingConstructionConstraintInputs(params: {
  maxPositionWeightInput: string | null | undefined
  minPositionWeightInput?: string | null | undefined
  maxTurnoverWeightInput?: string | null | undefined
  maxTradeIntentCountInput?: string | null | undefined
  maxSectorWeightInput?: string | null | undefined
}): RankingConstructionConstraintValidation {
  const maxPositionWeight = validateRequiredMaxPositionWeightInput(params.maxPositionWeightInput)
  const minPositionWeight = validateOptionalMinPositionWeightInput(
    params.minPositionWeightInput,
    maxPositionWeight.value,
  )
  const maxTurnoverWeight = validateOptionalMaxTurnoverWeightInput(params.maxTurnoverWeightInput)
  const maxTradeIntentCount = validateOptionalMaxTradeIntentCountInput(params.maxTradeIntentCountInput)
  const maxSectorWeight = validateOptionalMaxSectorWeightInput(
    params.maxSectorWeightInput,
    maxPositionWeight.value,
  )

  return {
    maxPositionWeight,
    minPositionWeight,
    maxTurnoverWeight,
    maxTradeIntentCount,
    maxSectorWeight,
  }
}

export function validateRankingConstructionPositionWeightInputs(params: {
  maxPositionWeightInput: string | null | undefined
  minPositionWeightInput?: string | null | undefined
}): RankingConstructionPositionWeightValidation {
  const validation = validateRankingConstructionConstraintInputs(params)
  return {
    maxPositionWeight: validation.maxPositionWeight,
    minPositionWeight: validation.minPositionWeight,
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

export function validateRankingConstructionMaxTurnoverWeightInput(
  input: string | null | undefined,
): RankingConstructionMaxTurnoverWeightValidation {
  return validateRankingConstructionConstraintInputs({
    maxPositionWeightInput: DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT,
    maxTurnoverWeightInput: input,
  }).maxTurnoverWeight
}

export function validateRankingConstructionMaxTradeIntentCountInput(
  input: string | null | undefined,
): RankingConstructionMaxTradeIntentCountValidation {
  return validateRankingConstructionConstraintInputs({
    maxPositionWeightInput: DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT,
    maxTradeIntentCountInput: input,
  }).maxTradeIntentCount
}

export function validateRankingConstructionMaxSectorWeightInput(params: {
  maxSectorWeightInput: string | null | undefined
  maxPositionWeightInput: string | null | undefined
}): RankingConstructionMaxSectorWeightValidation {
  return validateRankingConstructionConstraintInputs({
    maxPositionWeightInput: params.maxPositionWeightInput,
    maxSectorWeightInput: params.maxSectorWeightInput,
  }).maxSectorWeight
}

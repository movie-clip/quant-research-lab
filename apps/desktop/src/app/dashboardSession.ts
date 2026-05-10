import type { DashboardAnalysis, ExposureAnalysis, ExposureFactorModelResponse } from '../features/portfolio/types'
import type { PortfolioNode, WorkingDraft } from '../features/portfolio/workspaceTypes'

export type DashboardSessionInput = {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
  factorModel: ExposureFactorModelResponse | null
  activeNode: PortfolioNode | null
  workingDraft: WorkingDraft | null
  lastImportedFileNames: string[]
  restoredSession: boolean
  importing: boolean
  importError: string | null
}

export type DashboardSession = {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
  factorModel: ExposureFactorModelResponse | null
  detailEligible: boolean
  activeNodeKind: PortfolioNode['kind'] | null
  lastImportedFileNames: string[]
  restoredSession: boolean
  importing: boolean
  importError: string | null
}

export function isDashboardDetailedReviewEligible(
  result: DashboardAnalysis | null,
  activeNodeKind: PortfolioNode['kind'] | null | undefined,
) {
  const performanceSeries = result?.performance_series ?? []
  const dailyStates = result?.daily_states ?? []
  const hasDashboardData = Boolean(result && (performanceSeries.length || dailyStates.length || result.source_status))
  if (!hasDashboardData) return false
  if (activeNodeKind && activeNodeKind !== 'imported_base' && activeNodeKind !== 'imported_snapshot') return false
  return true
}

export function composeDashboardSession(input: DashboardSessionInput): DashboardSession {
  const activeNode = input.activeNode

  return {
    result: input.result,
    exposureResult: input.exposureResult,
    factorModel: input.factorModel,
    detailEligible: isDashboardDetailedReviewEligible(input.result, activeNode?.kind),
    activeNodeKind: input.activeNode?.kind ?? null,
    lastImportedFileNames: input.lastImportedFileNames,
    restoredSession: input.restoredSession,
    importing: input.importing,
    importError: input.importError,
  }
}

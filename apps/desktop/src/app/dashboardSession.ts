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
  lastImportedFileNames: string[]
  restoredSession: boolean
  importing: boolean
  importError: string | null
}

export function composeDashboardSession(input: DashboardSessionInput): DashboardSession {
  return {
    result: input.result,
    exposureResult: input.exposureResult,
    factorModel: input.factorModel,
    lastImportedFileNames: input.lastImportedFileNames,
    restoredSession: input.restoredSession,
    importing: input.importing,
    importError: input.importError,
  }
}

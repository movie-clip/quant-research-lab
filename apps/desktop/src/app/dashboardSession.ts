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
  draftSnapshot: WorkingDraft['portfolioSnapshot'] | null
  activeNodeName: string | null
  draftStatus: WorkingDraft['status'] | null
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
    draftSnapshot: input.workingDraft?.portfolioSnapshot ?? input.activeNode?.portfolioSnapshot ?? null,
    activeNodeName: input.activeNode?.name ?? null,
    draftStatus: input.workingDraft?.status ?? null,
    lastImportedFileNames: input.lastImportedFileNames,
    restoredSession: input.restoredSession,
    importing: input.importing,
    importError: input.importError,
  }
}

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
  activeNodeKind: PortfolioNode['kind'] | null
  admissionSummary: DashboardAnalysis['admission_summary'] | null
  lastImportedFileNames: string[]
  restoredSession: boolean
  importing: boolean
  importError: string | null
}

export function composeDashboardSession(input: DashboardSessionInput): DashboardSession {
  const activeNode = input.activeNode

  return {
    result: input.result,
    exposureResult: input.exposureResult,
    factorModel: input.factorModel,
    activeNodeKind: input.activeNode?.kind ?? null,
    admissionSummary: input.result?.admission_summary ?? (!activeNode || !('kind' in (activeNode.source ?? {})) ? activeNode?.source?.admissionSummary ?? null : null),
    lastImportedFileNames: input.lastImportedFileNames,
    restoredSession: input.restoredSession,
    importing: input.importing,
    importError: input.importError,
  }
}

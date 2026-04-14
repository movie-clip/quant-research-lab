import type { DiagnosticsEngineResponse, ExposureAnalysis, ExposureFactorModelResponse } from '../features/portfolio/types'
import type { PortfolioNode, PortfolioWorkspace, WorkingDraft } from '../features/portfolio/workspaceTypes'

export type ActivePortfolioContext =
  | { mode: 'saved_node'; workspaceId: string; nodeId: string }
  | { mode: 'draft'; workspaceId: string; nodeId: string; draftId: string }

export type PortfolioAnalysisState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  exposure: ExposureAnalysis | null
  diagnostics: DiagnosticsEngineResponse | null
  factorModel: ExposureFactorModelResponse | null
  errorMessage: string | null
  calculatedFrom: {
    workspaceId: string | null
    nodeId: string | null
    draftId: string | null
    snapshotHash: string | null
  }
}

export type PortfolioAppState = {
  activeWorkspace: PortfolioWorkspace | null
  activeNode: PortfolioNode | null
  workingDraft: WorkingDraft | null
  activeContext: ActivePortfolioContext | null
  analysisState: PortfolioAnalysisState
}

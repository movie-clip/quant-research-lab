import type { MonitoringResearchHandoffTarget } from '../portfolio/types'

export const MONITORING_RESEARCH_HANDOFF_VERSION = 1 as const

export const MONITORING_RESEARCH_TARGET_IDS: Record<MonitoringResearchHandoffTarget, string> = {
  hypothetical_replay: 'workflow-section-hypothetical-replay',
  diagnostics_change: 'workflow-section-diagnostics-change',
}

export function monitoringResearchTargetLabel(target: MonitoringResearchHandoffTarget) {
  if (target === 'hypothetical_replay') return 'Hypothetical Replay'
  return 'Diagnostics Change'
}

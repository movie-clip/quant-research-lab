/**
 * Shared fixtures for the US-46 tests: combined imports (analyze-combined responses), roll-up admission
 * summaries and saved workspaces in the pre-fix ("legacy") shape.
 *
 * Numbers that tests assert on are PINNED here from the statement truths (IB2026 in
 * services/quant-engine/app/tests/statement_truths.py, the 05-design.md fixture pairs) and never
 * recomputed from the fixtures they describe. The mock "engine" outputs below (`combinedResponse`,
 * `concatDistinctAccounts`) exist only to stand in for the engine; a test that needs to prove the UI
 * shows what the engine said must give the mock an answer that differs from anything derivable here.
 */
import { createImportedBootstrapResponseFixture } from './portfolioFixtures'
import { ff2026ImportedDashboardGoldenFixture, ib2026ImportedDashboardGoldenFixture } from './dashboardGoldens'
import { buildPortfolioSnapshotFromAnalysis } from '../features/portfolio/portfolioSnapshot'
import type {
  ImportAdmissionCheck,
  ImportAdmissionConstituent,
  ImportAdmissionDecision,
  ImportAdmissionSummaryV1,
  ImportAdmissionTrustLevel,
  ImportedBootstrapResponse,
  ImportedSnapshot,
  PortfolioOverview,
} from '../features/portfolio/types'
import type {
  ImportedHistoryContext,
  ImportedNodeSource,
  PortfolioNode,
  PortfolioSnapshot,
  PortfolioWorkspace,
  WorkingDraft,
  WorkspaceState,
} from '../features/portfolio/workspaceTypes'

// ── pinned statement truths (US-46.1 AC 1-4) ────────────────────────────────────────────────────
export const IB_TRUTH = {
  positionCount: 18,
  rawMarketValue: 62_843.22,
  vuaaQuantity: 80,
  vuaaMarketValue: 12_004.8,
  usdCash: 146.07,
} as const

export const ESPP_TRUTH = { symbol: 'MSFT', marketValue: 3_391.24, usdCash: 10.44 } as const

/** What the pre-fix Freedom24 importer stored for VTI (US-46.4 AC 11). Literal on purpose: the
 *  regenerated golden holds null there, and this is the OLD saved shape. */
export const FF_FABRICATED = { symbol: 'VTI', costBasis: 3_018.96, unrealizedPnl: 0 } as const

export function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

// ── statements ───────────────────────────────────────────────────────────────────────────────────
export function ibStatementSnapshot(): ImportedSnapshot {
  return cloneJson(ib2026ImportedDashboardGoldenFixture.snapshot) as unknown as ImportedSnapshot
}

/** FF2026 as saved BEFORE US-46.4: VTI carries the fabricated 3,018.96 cost basis and 0.00 P&L. */
export function ffLegacyStatementSnapshot(): ImportedSnapshot {
  const snapshot = cloneJson(ff2026ImportedDashboardGoldenFixture.snapshot) as unknown as ImportedSnapshot
  snapshot.positions = snapshot.positions.map((position) =>
    position.symbol === FF_FABRICATED.symbol
      ? { ...position, cost_basis: FF_FABRICATED.costBasis, unrealized_pnl: FF_FABRICATED.unrealizedPnl }
      : position,
  )
  return snapshot
}

/** ESPP2026: one MSFT position, admitted/verified on its own. Shaped like the IB statement record. */
export function esppStatementSnapshot(): ImportedSnapshot {
  const ib = ibStatementSnapshot()
  const statement = {
    ...ib.statement,
    importer: 'espp' as const,
    account_id: 'I09548809',
    source_path: 'ESPP2026.pdf',
    detected_format: 'pdf',
    statement_period: '2026-01-01 - 2026-06-30',
    imported_at: '2026-04-15T00:00:00Z',
  }
  return {
    ...ib,
    statement,
    statements: [statement],
    statement_totals: null,
    positions: [
      { symbol: ESPP_TRUTH.symbol, quantity: 9, market_value: ESPP_TRUTH.marketValue, currency: 'USD', as_of_date: '2026-06-30', cost_basis: null, unrealized_pnl: null },
    ],
    ledger_entries: [],
    instruments: [],
    cash_balances: [{ currency: 'USD', starting_cash: 0, ending_cash: ESPP_TRUTH.usdCash, ending_settled_cash: ESPP_TRUTH.usdCash }],
  }
}

/** Stand-in for the engine's flat combine of two DISTINCT accounts (positions concatenated, USD cash
 *  summed). Test doubles only: the assertions on its output use the pinned truths above. */
export function concatDistinctAccounts(left: ImportedSnapshot, right: ImportedSnapshot): ImportedSnapshot {
  const usd = (snapshot: ImportedSnapshot) => snapshot.cash_balances.find((balance) => balance.currency === 'USD')?.ending_cash ?? 0
  return {
    ...left,
    statement: {
      ...left.statement,
      importer: 'multi_broker',
      account_id: [left.statement.account_id, right.statement.account_id].filter(Boolean).sort().join(' + '),
    },
    statements: [...left.statements, ...right.statements],
    positions: [...left.positions, ...right.positions],
    cash_balances: [
      ...left.cash_balances.filter((balance) => balance.currency !== 'USD'),
      { currency: 'USD', starting_cash: null, ending_cash: usd(left) + usd(right), ending_settled_cash: usd(left) + usd(right) },
    ],
  }
}

/** IB2026 added onto IB2026: the same account REPLACES, so the engine answer equals IB2026 with the
 *  statement list recording both inputs (probe in 06-backend.md). */
export function sameAccountCombine(base: ImportedSnapshot, added: ImportedSnapshot): ImportedSnapshot {
  return { ...cloneJson(base), statements: [...base.statements, ...added.statements] }
}

export function ibHistoryContext(): ImportedHistoryContext {
  const states = ib2026ImportedDashboardGoldenFixture.daily_states as Array<{ date: string }>
  return {
    benchmarkSymbol: 'SPY',
    statementPeriod: ib2026ImportedDashboardGoldenFixture.snapshot.statement.statement_period,
    importedAt: ib2026ImportedDashboardGoldenFixture.snapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
    importer: 'interactive_brokers',
    sourceFileNames: ['IB2026.csv'],
    historyStartDate: states[0]?.date ?? null,
    historyEndDate: states[states.length - 1]?.date ?? null,
  }
}

// ── admission summaries ──────────────────────────────────────────────────────────────────────────
export function admissionCheck(
  checkId: string,
  status: ImportAdmissionCheck['status'],
  overrides: Partial<ImportAdmissionCheck> = {},
): ImportAdmissionCheck {
  return {
    check_id: checkId,
    status,
    severity: status === 'pass' ? 'info' : 'warning',
    trust_impact: status === 'pass' ? 'none' : 'degraded',
    message: `${checkId} ${status}`,
    affected_fields: [],
    observed: null,
    comparison: null,
    delta: null,
    currency: null,
    ...overrides,
  }
}

const TOLERANCE_POLICY = 'absolute_currency_delta_lte_0.01_same_currency_only'

export function admissionSummary(input: {
  decision: ImportAdmissionDecision
  trustLevel: ImportAdmissionTrustLevel
  sourceNames: string[]
  checks?: ImportAdmissionCheck[]
  importer?: string
  rollup?: ImportAdmissionSummaryV1['rollup']
}): ImportAdmissionSummaryV1 {
  return {
    schema_version: 'import_admission_summary_v1',
    decision: input.decision,
    trust_level: input.trustLevel,
    checks: input.checks ?? [admissionCheck('residual_cash_comparability', input.decision === 'admitted' ? 'pass' : 'warn')],
    provenance: {
      importer: input.importer ?? 'interactive_brokers',
      statement_ids: input.sourceNames.map((name) => `stmt:${name}`),
      source_names: input.sourceNames,
      generated_at: '2026-04-14T00:00:00Z',
      tolerance_policy: TOLERANCE_POLICY,
    },
    ...(input.rollup !== undefined ? { rollup: input.rollup } : {}),
  }
}

/** IB2026 on its own (US-46.3 AC 10): degraded / degraded, no roll-up. */
export function ibAdmission(): ImportAdmissionSummaryV1 {
  return admissionSummary({
    decision: 'degraded',
    trustLevel: 'degraded',
    sourceNames: ['IB2026.csv'],
    checks: [
      admissionCheck('symbol_security_identity_consistency', 'warn', { message: 'Open positions lack imported instrument identity for: SBIO.' }),
      admissionCheck('residual_cash_comparability', 'pass'),
    ],
  })
}

/** ESPP2026 on its own (US-46.3 AC 10): admitted / verified, no roll-up. */
export function esppAdmission(): ImportAdmissionSummaryV1 {
  return admissionSummary({
    decision: 'admitted',
    trustLevel: 'verified',
    sourceNames: ['ESPP2026.pdf'],
    importer: 'espp',
    checks: [admissionCheck('residual_cash_comparability', 'pass')],
  })
}

export function constituentOf(
  origin: ImportAdmissionConstituent['origin'],
  summary: ImportAdmissionSummaryV1,
): ImportAdmissionConstituent {
  return {
    origin,
    statement_ids: summary.provenance.statement_ids,
    source_names: summary.provenance.source_names,
    decision: summary.decision,
    trust_level: summary.trust_level,
    checks: summary.checks,
  }
}

/** The engine's roll-up as delivered for a combined portfolio. `topLabel` is what the ENGINE says the
 *  portfolio is; the fixture never derives it from the constituents. */
export function rolledUpAdmission(input: {
  topLabel: { decision: ImportAdmissionDecision; trustLevel: ImportAdmissionTrustLevel }
  combinedSnapshotLabel: { decision: ImportAdmissionDecision; trustLevel: ImportAdmissionTrustLevel }
  constituents: ImportAdmissionConstituent[]
  sourceNames: string[]
  combinedChecks?: ImportAdmissionCheck[]
}): ImportAdmissionSummaryV1 {
  return admissionSummary({
    decision: input.topLabel.decision,
    trustLevel: input.topLabel.trustLevel,
    sourceNames: input.sourceNames,
    checks: input.combinedChecks ?? [admissionCheck('nav_market_value_comparability', 'warn', { message: 'Combined snapshot NAV comparability could not be verified.' })],
    rollup: {
      rule: 'weakest_of_constituents_and_combined_snapshot',
      combined_snapshot_decision: input.combinedSnapshotLabel.decision,
      combined_snapshot_trust_level: input.combinedSnapshotLabel.trustLevel,
      constituents: input.constituents,
    },
  })
}

/** IB2026 + ESPP2026 as analyze-combined returns it (US-46.3 AC 1): degraded / degraded. */
export function ibPlusEsppAdmission(): ImportAdmissionSummaryV1 {
  return rolledUpAdmission({
    topLabel: { decision: 'degraded', trustLevel: 'degraded' },
    combinedSnapshotLabel: { decision: 'degraded', trustLevel: 'degraded' },
    constituents: [constituentOf('statement', ibAdmission()), constituentOf('statement', esppAdmission())],
    sourceNames: ['IB2026.csv', 'ESPP2026.pdf'],
  })
}

// ── analyze-combined / analyze-upload responses ─────────────────────────────────────────────────
export function ibOverview(): PortfolioOverview {
  return cloneJson(ib2026ImportedDashboardGoldenFixture.overview) as unknown as PortfolioOverview
}

/** An ImportedBootstrapResponse around `snapshot`. Everything but the fields named in the arguments
 *  comes from the shared bootstrap fixture, so it cannot drift from the real response shape. */
export function combinedResponse(input: {
  snapshot: ImportedSnapshot
  admission: ImportAdmissionSummaryV1
  overview?: PortfolioOverview
  historyContext?: ImportedBootstrapResponse['history_context']
  constituents?: ImportedSnapshot[]
}): ImportedBootstrapResponse {
  const base = createImportedBootstrapResponseFixture()
  const ibContext = ibHistoryContext()
  return {
    ...base,
    snapshot: input.snapshot,
    overview: input.overview ?? ibOverview(),
    admission_summary: input.admission,
    history_context: input.historyContext ?? {
      benchmark_symbol: ibContext.benchmarkSymbol,
      statement_period: ibContext.statementPeriod,
      imported_at: ibContext.importedAt,
      importer: ibContext.importer,
      source_file_names: ibContext.sourceFileNames,
      history_start_date: ibContext.historyStartDate,
      history_end_date: ibContext.historyEndDate,
    },
    constituent_snapshots: input.constituents ?? [],
  }
}

// ── saved workspaces in the pre-fix shape ───────────────────────────────────────────────────────
/** The client overlay's output for `snapshot` added onto itself: every quantity and value doubled,
 *  which is what the old add-statement path saved as the node's portfolio snapshot (US-46.1 F3). */
export function doubledPortfolioSnapshot(snapshot: PortfolioSnapshot): PortfolioSnapshot {
  return {
    ...cloneJson(snapshot),
    positions: snapshot.positions.map((position) => ({
      ...position,
      marketValue: position.marketValue * 2,
      quantity: position.quantity == null ? null : position.quantity * 2,
    })),
    cashBalances: snapshot.cashBalances.map((balance) => ({ ...balance, amount: balance.amount * 2 })),
  }
}

export function portfolioSnapshotOf(snapshot: ImportedSnapshot, fileNames: string[], overview: PortfolioOverview = ibOverview()): PortfolioSnapshot {
  return buildPortfolioSnapshotFromAnalysis({ snapshot, overview }, fileNames)
}

export type SavedNodeInput = {
  id: string
  parentId: string | null
  /** The node's stored replay snapshot; null = history-context-only / none. */
  replaySnapshot: ImportedSnapshot | null
  admission: ImportAdmissionSummaryV1 | null
  portfolioSnapshot: PortfolioSnapshot
  fileNames: string[]
  /** Absent (the default) = a node saved before derivationVersion existed. */
  derivationVersion?: number
  importedConstituents?: ImportedSnapshot[]
}

function savedSource(input: SavedNodeInput): ImportedNodeSource {
  const source: ImportedNodeSource = {
    importedFileNames: input.fileNames,
    importedAt: '2026-04-14T00:00:00Z',
    importer: 'interactive_brokers',
    baseCurrency: 'USD',
    historySource: input.replaySnapshot
      ? { kind: 'imported_replay', historyContext: ibHistoryContext(), importedHistorySnapshot: input.replaySnapshot }
      : { kind: 'history_context', historyContext: ibHistoryContext(), importedHistorySnapshot: null },
    admissionSummary: input.admission,
  }
  if (input.derivationVersion !== undefined) source.derivationVersion = input.derivationVersion
  if (input.importedConstituents !== undefined) source.importedConstituents = input.importedConstituents
  return source
}

export type SavedWorkspace = {
  workspace: PortfolioWorkspace
  nodes: PortfolioNode[]
  draft: WorkingDraft | null
  workspaceState: WorkspaceState
}

/** A saved workspace: `nodes[0]` is the imported_base root, the rest are imported_snapshot add nodes
 *  chained in order. The last node is active. `draft` mirrors the active node unless null. */
export function buildSavedWorkspace(input: { nodes: SavedNodeInput[]; draft?: 'clean' | 'dirty' | null }): SavedWorkspace {
  const [root, ...adds] = input.nodes
  const active = input.nodes[input.nodes.length - 1]
  const rootNode: PortfolioNode = {
    id: root.id,
    workspaceId: 'workspace-1',
    parentId: null,
    kind: 'imported_base',
    name: 'Base Import',
    createdAt: '2026-04-14T00:00:00Z',
    changeSummary: { label: 'Base Import', changedPositionsCount: root.portfolioSnapshot.positions.length, changedSectorsCount: 0 },
    portfolioSnapshot: root.portfolioSnapshot,
  }
  const addNodes: PortfolioNode[] = adds.map((add) => ({
    id: add.id,
    workspaceId: 'workspace-1',
    parentId: add.parentId,
    kind: 'imported_snapshot',
    name: `Added ${add.id}`,
    createdAt: '2026-04-15T00:00:00Z',
    changeSummary: { label: `Added ${add.id}`, changedPositionsCount: 0, changedSectorsCount: 0 },
    portfolioSnapshot: add.portfolioSnapshot,
    source: savedSource(add),
  }))
  const draftMode = input.draft === undefined ? 'clean' : input.draft
  const draft: WorkingDraft | null = draftMode
    ? {
        id: 'draft-1',
        workspaceId: 'workspace-1',
        baseNodeId: active.id,
        updatedAt: '2026-04-15T00:00:00Z',
        name: 'Working Draft',
        status: draftMode,
        portfolioSnapshot: cloneJson(active.portfolioSnapshot),
      }
    : null
  return {
    workspace: {
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-14T00:00:00Z',
      updatedAt: '2026-04-15T00:00:00Z',
      rootNodeId: root.id,
      activeNodeId: active.id,
      source: savedSource(root),
    },
    nodes: [rootNode, ...addNodes],
    draft,
    workspaceState: {
      workspaceId: 'workspace-1',
      activeNodeId: active.id,
      activeDraftId: draft?.id ?? null,
      selectedExposureSnapshotId: draft ? 'draft' : active.id,
      lastOpenedAt: '2026-04-15T00:00:00Z',
    },
  }
}

const APP_STATE_STORE = 'app-state'
const WORKSPACE_STORE = 'workspaces'
const NODE_STORE = 'portfolio_nodes'
const DRAFT_STORE = 'working_drafts'
const WORKSPACE_STATE_STORE = 'workspace_state'
/** Mirrors `activeWorkspacePointerKey` in portfolioWorkspaceStorage.ts (not exported). */
const ACTIVE_WORKSPACE_POINTER_KEY = 'active-workspace-pointer'

/** Place a saved workspace in a fake DB (see fakePortfolioDb.ts) without recording a write. */
export function seedSavedWorkspace(db: { seed(storeName: string, value: unknown): void }, saved: SavedWorkspace) {
  db.seed(WORKSPACE_STORE, saved.workspace)
  for (const node of saved.nodes) db.seed(NODE_STORE, node)
  if (saved.draft) db.seed(DRAFT_STORE, saved.draft)
  db.seed(WORKSPACE_STATE_STORE, saved.workspaceState)
  db.seed(APP_STATE_STORE, { id: ACTIVE_WORKSPACE_POINTER_KEY, workspaceId: saved.workspace.id })
}

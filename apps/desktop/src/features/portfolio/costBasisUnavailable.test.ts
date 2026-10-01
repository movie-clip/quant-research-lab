/**
 * US-46.4 AC 9 (frontend half): a missing cost basis or unrealized P&L is UNAVAILABLE, never zero.
 *
 * Nothing in `apps/desktop/src` renders these values today (05-design.md § AC pressure points), so the
 * falsifiers are: (1) the types accept null, checked by `tsc --noEmit`; (2) null survives the engine
 * response -> projection -> storage path unchanged; (3) no source file coerces them to a number, so the
 * first component that renders one cannot quietly turn unavailable into "0.00".
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { extname, join, relative } from 'node:path'
import { afterEach, describe, expect, expectTypeOf, it, vi } from 'vitest'

import { createFakePortfolioDb } from '../../test/fakePortfolioDb'
import { combinedResponse, ffLegacyStatementSnapshot, FF_FABRICATED, ibAdmission } from '../../test/combinedImportFixtures'
import { createImportedBootstrapResponseFixture } from '../../test/portfolioFixtures'
import * as portfolioWorkspaceStorage from '../../app/portfolioWorkspaceStorage'
import { projectImportedBootstrap } from './importedBootstrapMapper'
import type { ImportedSnapshot, PortfolioOverview } from './types'

afterEach(() => {
  vi.restoreAllMocks()
})

// The shape the engine returns for FF2026 after the fix (US-46.4 AC 3, 4): totals and VTI P&L null.
function unavailableCostBasisOverview(): PortfolioOverview {
  return {
    ...createImportedBootstrapResponseFixture().overview,
    total_cost_basis: null,
    total_unrealized_pnl: null,
    top_positions: [{ symbol: 'VTI', market_value: 3018.96, weight: 1, unrealized_pnl: null }],
    cost_basis_trust: 'unavailable',
  }
}

describe('null cost basis and unrealized P&L are typed as unavailable (US-46.4 AC 1-4)', () => {
  it('lets PortfolioOverview and its top positions carry null, and only null or a number', () => {
    expectTypeOf<PortfolioOverview['total_unrealized_pnl']>().toEqualTypeOf<number | null>()
    expectTypeOf<NonNullable<PortfolioOverview['total_cost_basis']>>().toEqualTypeOf<number>()
    expectTypeOf<undefined extends PortfolioOverview['total_cost_basis'] ? true : false>().toEqualTypeOf<true>()
    expectTypeOf<PortfolioOverview['top_positions'][number]['unrealized_pnl']>().toEqualTypeOf<number | null>()
    expectTypeOf<PortfolioOverview['cost_basis_trust']>().toEqualTypeOf<'stated' | 'unavailable' | undefined>()
  })

  it('lets an imported position carry null cost basis and unrealized P&L', () => {
    expectTypeOf<NonNullable<ImportedSnapshot['positions'][number]['cost_basis']>>().toEqualTypeOf<number>()
    expectTypeOf<null extends ImportedSnapshot['positions'][number]['cost_basis'] ? true : false>().toEqualTypeOf<true>()
    expectTypeOf<null extends ImportedSnapshot['positions'][number]['unrealized_pnl'] ? true : false>().toEqualTypeOf<true>()

    const overview = unavailableCostBasisOverview()
    expect(overview.total_unrealized_pnl).toBeNull()
    expect(overview.top_positions[0].unrealized_pnl).toBeNull()
  })

  it('keeps an unavailable cost basis unavailable across projection, never coercing it to 0', () => {
    const response = combinedResponse({
      snapshot: ffLegacyStatementSnapshot(),
      admission: ibAdmission(),
      overview: unavailableCostBasisOverview(),
    })

    const { overview } = projectImportedBootstrap(response).workspace

    expect(overview.total_cost_basis).toBeNull()
    expect(overview.total_unrealized_pnl).toBeNull()
    expect(overview.top_positions[0].unrealized_pnl).toBeNull()
    expect(overview.cost_basis_trust).toBe('unavailable')
  })

  it('persists an unavailable cost basis in the exposure override and reads it back as null', async () => {
    createFakePortfolioDb().install()
    const response = combinedResponse({
      snapshot: ffLegacyStatementSnapshot(),
      admission: ibAdmission(),
      overview: unavailableCostBasisOverview(),
    })

    const created = await portfolioWorkspaceStorage.createWorkspaceFromImport({
      analysis: projectImportedBootstrap(response).workspace,
      importedFileNames: ['FF2026.pdf'],
    })
    const reread = await portfolioWorkspaceStorage.getWorkspace(created.workspace.id)

    const overview = reread?.source.importedExposureOverride?.overview
    expect(overview?.total_cost_basis).toBeNull()
    expect(overview?.total_unrealized_pnl).toBeNull()
    expect(overview?.top_positions[0].unrealized_pnl).toBeNull()
    expect(overview?.cost_basis_trust).toBe('unavailable')
  })

  it('pins the legacy fabricated fixture so a re-derive test cannot pass on an already-null input', () => {
    const vti = ffLegacyStatementSnapshot().positions.find((position) => position.symbol === FF_FABRICATED.symbol)

    expect(vti?.cost_basis).toBe(3018.96)
    expect(vti?.unrealized_pnl).toBe(0)
  })
})

// ── source guard ─────────────────────────────────────────────────────────────────────────────────
const SRC_ROOT = join(__dirname, '..', '..')
const GENERATED_OR_FIXTURE = new Set(['dashboardGoldens.ts'])
const FIELD_REGEX = /\b(cost_basis|unrealized_pnl|total_cost_basis|total_unrealized_pnl|costBasis|unrealizedPnl)\b/
// Coercions that would turn "unavailable" into a number: `?? 0`, `|| 0`, `Number(x)`, unary plus, `.toFixed` on the raw field.
const COERCION_REGEX = /(\?\?|\|\|)\s*0(\.0+)?\b|\bNumber\(|\+\s*[\w.?]*(cost_basis|unrealized_pnl)|(cost_basis|unrealized_pnl)[\w?]*\)?\.toFixed/

function listSourceFiles(dir: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry)
    if (statSync(fullPath).isDirectory()) {
      if (entry === 'node_modules' || entry === 'test' || entry === 'zz_scratch') continue
      files.push(...listSourceFiles(fullPath))
    } else if (['.ts', '.tsx'].includes(extname(entry)) && !/\.test\.tsx?$/.test(entry) && !GENERATED_OR_FIXTURE.has(entry)) {
      files.push(fullPath)
    }
  }
  return files
}

describe('no source file coerces cost basis or unrealized P&L to a number (US-46.4 AC 9)', () => {
  it('scans at least the types module, so the guard cannot pass by scanning nothing', () => {
    const scanned = listSourceFiles(SRC_ROOT).map((file) => relative(SRC_ROOT, file).replace(/\\/g, '/'))

    expect(scanned).toContain('features/portfolio/types.ts')
  })

  it('finds no `?? 0`, `|| 0`, Number() or toFixed on these fields', () => {
    const offenders: string[] = []
    for (const file of listSourceFiles(SRC_ROOT)) {
      readFileSync(file, 'utf8')
        .split(/\r?\n/)
        .forEach((line, index) => {
          if (FIELD_REGEX.test(line) && COERCION_REGEX.test(line)) {
            offenders.push(`${relative(SRC_ROOT, file).replace(/\\/g, '/')}:${index + 1}: ${line.trim()}`)
          }
        })
    }

    expect(offenders).toEqual([])
  })

  it('the coercion pattern itself catches the bug it guards against', () => {
    const bad = ['const pnl = position.unrealized_pnl ?? 0', 'total_cost_basis || 0', 'Number(overview.total_unrealized_pnl)']
    for (const line of bad) {
      expect(FIELD_REGEX.test(line) && COERCION_REGEX.test(line)).toBe(true)
    }
    expect(FIELD_REGEX.test('unrealized_pnl: number | null') && COERCION_REGEX.test('unrealized_pnl: number | null')).toBe(false)
  })
})

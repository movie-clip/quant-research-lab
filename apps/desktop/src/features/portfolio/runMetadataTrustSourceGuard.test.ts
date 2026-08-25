/**
 * US-40.1 / T-40.1.1, T-40.1.4 — permanent regression for AC5.
 *
 * `run_metadata.source_status.lookthrough_resolution`,
 * `run_metadata.source_status.benchmark_holdings`, and `run_metadata.confidence`
 * are always live/per-render values (`exposure_engine.py`'s
 * `_build_exposure_source_status`), never frozen the way `availability` /
 * `lookthrough` / `market_overlap` are for a persisted imported snapshot. Per
 * `docs/contracts/exposure-fields.md` (the sibling sentence this story adds),
 * they must never be read as a trust source — that is exactly the bug class
 * CR-1 (`2026-08-24-sbio-still-unclassified-bug`) fixed once for
 * `run_metadata.source_status.benchmark_holdings` in `getBenchmarkTrust`
 * (see `BenchmarkPositioningCard.test.tsx`).
 *
 * This makes the "confirmed via grep" check permanent and automated instead
 * of a one-time manual pass: it recursively scans every `.ts`/`.tsx` source
 * file under this directory (excluding test files) and fails, naming the
 * offending file:line, if any line reads `run_metadata.source_status` or
 * `run_metadata?.confidence` as a property ACCESS.
 *
 * Deliberately NOT flagged (by design of the regex, not by exclusion list):
 *  - object-literal construction, e.g. `run_metadata: { source_status: {...} } }`
 *    (a fixture building a payload, not a consumer reading one)
 *  - type declarations, e.g. `source_status: ExposureRunSourceStatus` in
 *    `types.ts`'s own `ExposureRunMetadata` type
 * Test files (`*.test.ts` / `*.test.tsx`) are excluded from the scan entirely
 * — `BenchmarkPositioningCard.test.tsx`'s own CR-1 fixture constructs
 * `run_metadata: { source_status: { ... } }` as an object literal, which is
 * not a violation, but excluding test files keeps the scanner simple rather
 * than relying on the access-vs-construction regex distinction to save it.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { extname, join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

const SCAN_ROOT = __dirname

// Property ACCESS only: `run_metadata.source_status`, `run_metadata?.confidence`,
// `run_metadata.confidence`. Does not match object-literal keys like
// `source_status: {` or type declarations like `source_status: Foo` because
// those never have `run_metadata` immediately to their left.
const FORBIDDEN_ACCESS_REGEX = /\brun_metadata\??\.(source_status|confidence)\b/

function listSourceFiles(dir: string): string[] {
  const entries = readdirSync(dir)
  const files: string[] = []
  for (const entry of entries) {
    const fullPath = join(dir, entry)
    const stat = statSync(fullPath)
    if (stat.isDirectory()) {
      files.push(...listSourceFiles(fullPath))
      continue
    }
    const ext = extname(entry)
    if (ext !== '.ts' && ext !== '.tsx') continue
    if (entry.endsWith('.test.ts') || entry.endsWith('.test.tsx')) continue
    files.push(fullPath)
  }
  return files
}

describe('run_metadata trust-source guard (AC5, T-40.1.1)', () => {
  it('no component under features/portfolio reads run_metadata.source_status or run_metadata.confidence', () => {
    const files = listSourceFiles(SCAN_ROOT)
    expect(files.length).toBeGreaterThan(0)

    const violations: string[] = []
    for (const file of files) {
      const content = readFileSync(file, 'utf-8')
      const lines = content.split('\n')
      lines.forEach((line, index) => {
        if (FORBIDDEN_ACCESS_REGEX.test(line)) {
          violations.push(`${relative(SCAN_ROOT, file)}:${index + 1}: ${line.trim()}`)
        }
      })
    }

    expect(violations, [
      'run_metadata.source_status / run_metadata.confidence are always live/per-render',
      'values, never frozen the way availability/lookthrough/market_overlap are for a',
      'persisted imported snapshot (docs/contracts/exposure-fields.md). Read the frozen',
      'availability fields instead. Offending line(s):',
      ...violations,
    ].join('\n')).toEqual([])
  })

  it('does not false-positive on object-literal construction or type declarations', () => {
    const constructionSample = 'const x = { run_metadata: { source_status: { lookthrough_resolution: "live" } } }'
    const typeDeclarationSample = 'source_status: ExposureRunSourceStatus'
    expect(FORBIDDEN_ACCESS_REGEX.test(constructionSample)).toBe(false)
    expect(FORBIDDEN_ACCESS_REGEX.test(typeDeclarationSample)).toBe(false)
  })

  it('does flag genuine property access as a sanity check on the regex itself', () => {
    expect(FORBIDDEN_ACCESS_REGEX.test('const status = analysis.run_metadata.source_status.benchmark_holdings')).toBe(true)
    expect(FORBIDDEN_ACCESS_REGEX.test('const confidence = analysis.run_metadata?.confidence')).toBe(true)
  })
})

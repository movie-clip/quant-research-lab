/**
 * Epic 12 / US-12.1 design-system audit.
 *
 * Static checks over the five Exposure-card source files: assert no literal
 * hex color codes and no literal pixel values appear in inline-style props,
 * and that the canonical `attribution-trust-badge` className is used wherever
 * a Synthetic trust badge is rendered.
 *
 * Escape hatch: prefix the offending literal with the comment
 *   `// design-system: escape-hatch: <reason>`
 * on the same or immediately preceding line. One hatch per literal.
 *
 * The audit reads files from disk (NOT from imports) so a refactor that
 * inlines a hex constant into a JSX prop is caught at test time.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const FEATURES = resolve(__dirname, '..', 'features', 'portfolio')
const PRIMITIVES = resolve(__dirname, '..', 'app', 'primitives')

/** Files that render their own Synthetic badge (4 of 5 — IndexedReturnChart
 *  lives inside DriftBenchmarkPanel which provides the badge for both). */
const CARDS_WITH_BADGE = [
  'DriftBenchmarkPanel.tsx',
  'RollingCorrelationChart.tsx',
  'FactorAttributionCard.tsx',
  'BenchmarkCorrelationTable.tsx',
  'FactorDriftSummaryCard.tsx',
]

/** Every card file the design system covers (incl. IndexedReturnChart). */
const ALL_CARD_FILES = [
  'DriftBenchmarkPanel.tsx',
  'IndexedReturnChart.tsx',
  'RollingCorrelationChart.tsx',
  'FactorAttributionCard.tsx',
  'BenchmarkCorrelationTable.tsx',
  'FactorDriftSummaryCard.tsx',
]

const HEX_REGEX = /#[0-9a-fA-F]{3,8}\b/g
const PX_LITERAL_REGEX = /\d+px/g
// Style-only props. Deliberately omits `top/right/bottom/left/width/height`
// because Recharts uses those as JSX props (`<YAxis width={48} />`) and on
// chart-layout margin objects (`margin={{ top: 4, right: 16 }}`); those are
// Recharts geometry, not design-system styling.
//
// Numeric value uses `[1-9]\d*` so bare `: 0` is allowed (zero is dimensionless;
// `marginTop: 0` is equivalent to `0px` and doesn't need a token).
const NUMERIC_PROP_REGEX = /(margin[A-Za-z]*|padding[A-Za-z]*|gap|fontSize|borderRadius)\s*:\s*([1-9]\d*)\b/g
const ESCAPE_HATCH_RE = /\/\/\s*design-system:\s*escape-hatch:/

/** Strip `//` line comments and `/* ... *\/` block comments before scanning,
 *  so the audit doesn't fire on informational comments that mention pixel
 *  values (e.g. "// 6 × 36 + 5 × 14 = 286px"). */
function stripComments(source: string): string {
  // Remove block comments first (they can span multiple lines)
  let stripped = source.replace(/\/\*[\s\S]*?\*\//g, (match) => {
    // Preserve newlines so line numbers in offence messages stay accurate
    return match.replace(/[^\n]/g, ' ')
  })
  // Remove line comments — but only the comment portion, not the whole line,
  // so `var foo = 1; // hex #abc` still keeps the `var foo = 1;` part
  stripped = stripped.replace(/\/\/[^\n]*/g, (match) => ' '.repeat(match.length))
  return stripped
}

function readCard(name: string): string {
  return readFileSync(resolve(FEATURES, name), 'utf8')
}

/** Return the set of line indices (0-based) that contain an escape-hatch comment. */
function hatchLines(source: string): Set<number> {
  const lines = source.split('\n')
  const hatched = new Set<number>()
  lines.forEach((line, idx) => {
    if (ESCAPE_HATCH_RE.test(line)) {
      hatched.add(idx)
      hatched.add(idx + 1) // hatch protects the next line too (literal commonly on next line)
    }
  })
  return hatched
}

/** Return literals not protected by an escape-hatch comment. Comments are
 *  stripped before scanning so they cannot trigger the audit (apart from
 *  escape-hatch markers, which are detected first). */
function findUnhatched(source: string, regex: RegExp): string[] {
  const hatched = hatchLines(source)
  const strippedLines = stripComments(source).split('\n')
  const originalLines = source.split('\n')
  const offences: string[] = []
  strippedLines.forEach((line, idx) => {
    if (hatched.has(idx)) return
    const matches = line.match(regex)
    if (matches) {
      offences.push(`line ${idx + 1}: ${originalLines[idx]?.trim() ?? ''}`)
    }
  })
  return offences
}

describe('Epic 12 design-system audit', () => {
  it('no_literal_hex_colors_in_card_files', () => {
    const offenders: Record<string, string[]> = {}
    for (const name of ALL_CARD_FILES) {
      const src = readCard(name)
      const offences = findUnhatched(src, HEX_REGEX)
      if (offences.length) offenders[name] = offences
    }
    expect(offenders).toEqual({})
  })

  it('no_literal_pixel_values_in_inline_style_props', () => {
    // Catches both `'12px'` string literals and bare `marginBottom: 12` numerics
    // inside style props on margin/padding/gap/fontSize/borderRadius/etc.
    const offenders: Record<string, string[]> = {}
    for (const name of ALL_CARD_FILES) {
      const src = readCard(name)
      const pxLit = findUnhatched(src, PX_LITERAL_REGEX)
      const numericProp = findUnhatched(src, NUMERIC_PROP_REGEX)
      const combined = [...pxLit, ...numericProp]
      if (combined.length) offenders[name] = combined
    }
    expect(offenders).toEqual({})
  })

  it('trust_badge_primitive_imported_in_all_badge_rendering_cards', () => {
    // After US-12.2 the badge JSX lives in `<TrustBadge />` (app/primitives/).
    // Each card that renders a Synthetic badge must import the primitive
    // rather than hand-roll the className.
    const missing: string[] = []
    for (const name of CARDS_WITH_BADGE) {
      const src = readCard(name)
      if (!src.includes("from '../../app/primitives/TrustBadge'")) missing.push(name)
    }
    expect(missing).toEqual([])
  })

  it('synthetic_label_string_is_single_source_of_truth', () => {
    // The literal string "Synthetic" (capital S, in JSX text content) must
    // appear in exactly ONE place: the TrustBadge primitive's LABELS map.
    // Anywhere else means a card is hand-rolling a badge instead of using
    // the primitive.
    const surfaces: Array<{ dir: string; files: string[] }> = [
      { dir: FEATURES, files: ALL_CARD_FILES },
      { dir: PRIMITIVES, files: ['TrustBadge.tsx'] },
    ]
    const offenders: string[] = []
    for (const { dir, files } of surfaces) {
      for (const name of files) {
        const src = readFileSync(resolve(dir, name), 'utf8')
        const stripped = stripComments(src)
        // Find `: 'Synthetic'`  or  `>Synthetic<`  literals (JSX text or string value).
        if (/(?<![A-Za-z])Synthetic(?![A-Za-z])/.test(stripped) && name !== 'TrustBadge.tsx') {
          offenders.push(name)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('chart_default_props_imported_in_all_chart_files', () => {
    // US-12.3: the three chart files must import shared Recharts defaults
    // from chartDefaults rather than hand-rolling tick/grid/tooltip styles.
    const CHART_FILES = [
      'IndexedReturnChart.tsx',
      'RollingCorrelationChart.tsx',
      'FactorAttributionCard.tsx',
    ]
    const missing: string[] = []
    for (const name of CHART_FILES) {
      const src = readCard(name)
      if (!src.includes("from '../../app/primitives/chartDefaults'")) {
        missing.push(name)
      }
    }
    expect(missing).toEqual([])
  })
})

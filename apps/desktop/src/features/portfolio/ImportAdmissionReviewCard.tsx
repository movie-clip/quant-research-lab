/**
 * ImportAdmissionReviewCard — Exposure tab (Epic 22 / US-22.1).
 *
 * Renders the persisted Import Admission Review (`admissionSummary`): the
 * overall decision + trust level, and one row per admission check with its
 * status, message, and evidence. Presentational only — the summary is computed
 * at import (`build_import_admission_summary`), delivered with the bootstrap
 * response, and lives in workspace state; this card never re-fetches or
 * recomputes it (truth class: persisted import artifact).
 *
 * US-46.3: when the summary carries a `rollup` (a portfolio combined from
 * several statements), the card renders the engine's roll-up as delivered —
 * the rule, the combined-snapshot labels, and each constituent's own labels
 * and checks. The weakest-of label is the engine's; nothing here ranks,
 * lowers, or raises a label.
 */
import type {
  ImportAdmissionCheck,
  ImportAdmissionConstituent,
  ImportAdmissionDecision,
  ImportAdmissionRollup,
  ImportAdmissionSummaryV1,
  ImportAdmissionTrustLevel,
} from './types'

import { CardShell } from '../../app/primitives/CardShell'
import { EmptyState } from '../../app/primitives/EmptyState'

type AdmissionCheck = ImportAdmissionCheck
type CheckStatus = AdmissionCheck['status']
type Decision = ImportAdmissionDecision
type TrustLevel = ImportAdmissionTrustLevel
type Tone = 'ok' | 'warn' | 'negative' | 'neutral'

const TONE_COLOR: Record<Tone, string> = {
  ok: 'var(--color-value-positive)',
  warn: 'var(--color-status-warn)',
  negative: 'var(--color-value-negative)',
  neutral: 'var(--color-text-disabled)',
}

const STATUS_TONE: Record<CheckStatus, Tone> = {
  pass: 'ok',
  warn: 'warn',
  fail: 'negative',
  unavailable: 'neutral',
}

// Symbol prefix so status is not encoded by color alone (a11y).
const STATUS_SYMBOL: Record<CheckStatus, string> = {
  pass: '✓',
  warn: '⚠',
  fail: '✗',
  unavailable: '—',
}

const STATUS_LABEL: Record<CheckStatus, string> = {
  pass: 'Pass',
  warn: 'Warn',
  fail: 'Fail',
  unavailable: 'Unavailable',
}

const DECISION_TONE: Record<Decision, Tone> = {
  admitted: 'ok',
  degraded: 'warn',
  withheld: 'negative',
}

const TRUST_TONE: Record<TrustLevel, Tone> = {
  verified: 'ok',
  degraded: 'warn',
  withheld: 'negative',
  unavailable: 'neutral',
}

// Display copy for the engine's rule identifier; the identifier itself is the contract.
const ROLLUP_RULE_TEXT: Record<ImportAdmissionRollup['rule'], string> = {
  weakest_of_constituents_and_combined_snapshot:
    "The portfolio label is the weakest of each statement's own admission and the check on the combined snapshot.",
}

const CONSTITUENT_ORIGIN_LABEL: Record<ImportAdmissionConstituent['origin'], string> = {
  statement: 'Statement',
  carried: 'Earlier review (carried)',
}

function titleCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function humanizeCheckId(checkId: string): string {
  return checkId
    .split('_')
    .map((part) => (part.length <= 3 ? part.toUpperCase() : titleCase(part)))
    .join(' ')
}

function Badge({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: 'var(--space-xxs) var(--space-sm)',
        borderRadius: 'var(--radius-sm)',
        border: `var(--border-thin) solid ${TONE_COLOR[tone]}`,
        color: TONE_COLOR[tone],
        fontSize: 'var(--font-caption)',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  )
}

function formatEvidenceValue(value: number | string | null | undefined): string {
  if (value == null) return '—'
  return typeof value === 'number' ? value.toFixed(2) : value
}

function formatDelta(delta: number, currency: string | null | undefined): string {
  const signed = `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}`
  return currency ? `${signed} ${currency}` : signed
}

function CheckRow({ check }: { check: AdmissionCheck }) {
  const tone = STATUS_TONE[check.status]
  const evidence: string[] = []
  if (check.observed) {
    evidence.push(`${check.observed.label}: ${formatEvidenceValue(check.observed.value)}`)
  }
  if (check.comparison) {
    evidence.push(`${check.comparison.label}: ${formatEvidenceValue(check.comparison.value)}`)
  }
  if (check.delta != null) {
    evidence.push(`Δ ${formatDelta(check.delta, check.currency)}`)
  }

  return (
    <li
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-xxs)',
        padding: 'var(--space-sm) 0',
        borderTop: 'var(--border-thin) solid var(--color-border-subtle)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-sm)' }}>
        <span style={{ color: TONE_COLOR[tone], fontSize: 'var(--font-body-sm)', whiteSpace: 'nowrap' }}>
          {`${STATUS_SYMBOL[check.status]} ${STATUS_LABEL[check.status]}`}
        </span>
        <span style={{ color: 'var(--color-text-primary)', fontSize: 'var(--font-body-sm)' }}>
          {humanizeCheckId(check.check_id)}
        </span>
      </div>
      <p style={{ margin: 0, color: 'var(--color-text-secondary)', fontSize: 'var(--font-body-sm)' }}>
        {check.message}
      </p>
      {evidence.length > 0 && (
        <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: 'var(--font-caption)' }}>
          {evidence.join('  ·  ')}
        </p>
      )}
      {check.affected_fields && check.affected_fields.length > 0 && (
        <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: 'var(--font-caption)' }}>
          {`Fields: ${check.affected_fields.join(', ')}`}
        </p>
      )}
    </li>
  )
}

function LabelBadges({ decision, trustLevel }: { decision: Decision; trustLevel: TrustLevel }) {
  return (
    <span style={{ display: 'inline-flex', gap: 'var(--space-xs)', alignItems: 'center' }}>
      <Badge tone={DECISION_TONE[decision]}>{`Decision: ${titleCase(decision)}`}</Badge>
      <Badge tone={TRUST_TONE[trustLevel]}>{`Trust: ${titleCase(trustLevel)}`}</Badge>
    </span>
  )
}

function CheckList({ checks, emptyTitle }: { checks: AdmissionCheck[]; emptyTitle: string }) {
  if (checks.length === 0) {
    return <EmptyState title={emptyTitle} />
  }
  return (
    <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
      {checks.map((check) => (
        <CheckRow key={check.check_id} check={check} />
      ))}
    </ul>
  )
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return (
    <h4
      style={{
        margin: 0,
        color: 'var(--color-text-primary)',
        fontSize: 'var(--font-body-sm)',
        fontWeight: 600,
      }}
    >
      {children}
    </h4>
  )
}

function constituentTitle(constituent: ImportAdmissionConstituent, index: number): string {
  const names = constituent.source_names.length > 0 ? constituent.source_names : constituent.statement_ids
  const prefix = `${CONSTITUENT_ORIGIN_LABEL[constituent.origin]} ${index + 1}`
  return names.length > 0 ? `${prefix}: ${names.join(', ')}` : prefix
}

function RollupSection({ rollup }: { rollup: ImportAdmissionRollup }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
      <p style={{ margin: 0, color: 'var(--color-text-secondary)', fontSize: 'var(--font-body-sm)' }}>
        {ROLLUP_RULE_TEXT[rollup.rule]}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
        <SubHeading>Combined snapshot check</SubHeading>
        <LabelBadges decision={rollup.combined_snapshot_decision} trustLevel={rollup.combined_snapshot_trust_level} />
      </div>
      {rollup.constituents.map((constituent, index) => (
        <div
          key={`${constituent.origin}-${index}`}
          role="group"
          aria-label={constituentTitle(constituent, index)}
          style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-xs)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
            <SubHeading>{constituentTitle(constituent, index)}</SubHeading>
            <LabelBadges decision={constituent.decision} trustLevel={constituent.trust_level} />
          </div>
          <CheckList checks={constituent.checks} emptyTitle="No admission checks were recorded for this statement." />
        </div>
      ))}
    </div>
  )
}

export function ImportAdmissionReviewCard({
  summary,
}: {
  summary: ImportAdmissionSummaryV1 | null | undefined
}) {
  if (!summary) {
    return (
      <CardShell title="Import Admission Review">
        <EmptyState
          title="Import Admission Review unavailable"
          detail="No admission review is available for this snapshot. Import a broker statement to see the integrity checks behind the imported numbers."
        />
      </CardShell>
    )
  }

  const rollup = summary.rollup ?? null

  return (
    <CardShell
      title="Import Admission Review"
      badge={<LabelBadges decision={summary.decision} trustLevel={summary.trust_level} />}
    >
      {rollup ? (
        <>
          <RollupSection rollup={rollup} />
          <SubHeading>Combined snapshot checks</SubHeading>
        </>
      ) : null}
      <CheckList checks={summary.checks} emptyTitle="No admission checks were recorded for this import." />
    </CardShell>
  )
}

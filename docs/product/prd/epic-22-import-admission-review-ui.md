# Epic 22 — Import Admission Review UI

**Status:** Active
**Created:** 2026-06-12

## Problem

Every import computes an **Import Admission Review** — an
`ImportAdmissionSummaryV1` with an overall `decision`
(`admitted` / `degraded` / `withheld`), a `trust_level`, and a list of
`ImportAdmissionCheckV1` results (residual-cash, NAV, position-market-value,
symbol identity, instrument description-consistency, and instrument ISIN
consistency). It is the product's structured answer to "can I trust the
numbers I'm about to analyze?", and it is already:

- computed by `build_import_admission_summary` (backend),
- returned on the import/analyze responses as `admission_summary`,
- mapped into the desktop workspace state (`admissionSummary`) and persisted.

But it is **never rendered**. The only fragment that reaches the screen is the
identity-mismatch slice, and only because it piggybacks on the Exposure Data
Sources panel via the provenance result's `identity_warnings`. The cash / NAV /
position-comparability checks — and the overall decision and trust level — are
invisible. A researcher cannot see *why* an import was admitted, degraded, or
withheld; the truth-class signal the system already produces is hidden.

## Goal

Give the Import Admission Review a real, visible home in the UI, so the
researcher can see — at a glance and in detail — whether the imported numbers
are trustworthy and exactly which checks degraded or withheld trust.

- **Surface the decision + trust level** prominently (admitted / degraded /
  withheld; verified / degraded / withheld / unavailable).
- **List every check** with its status, human-readable message, and the
  observed/comparison/delta evidence when present — never collapse a `warn`/
  `fail`/`unavailable` into silence.
- **Render from existing state** (`admissionSummary`) — no backend change, no
  new fetch; the data is already in the workspace.
- Stay within the design system (Epic 12 primitives) and the trust-surfacing
  guardrail.

## Non-goals

- **No backend / schema change.** The summary already exists and is delivered;
  this epic only renders it. (If a gap is found, it is a separate fix.)
- **No disposition workflow yet.** The schema carries
  `ImportAdmissionReviewDispositionV1` (accept-known-exception / needs-source-
  correction / deferred with rationale); building that review-and-sign-off flow
  is a deliberate follow-up (US-22.2), not part of US-22.1.
- **No change to admission semantics** — which checks run, their thresholds,
  and the decision/trust mapping are owned by the import-admission service and
  unchanged here.
- **No removal of the existing identity-warning line** on the Data Sources
  panel — it stays; this epic adds the complete review, it doesn't relocate the
  identity slice.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-22.1 | Import Admission Review card | A self-contained card that renders `admissionSummary`: decision + trust-level header, per-check rows (status, message, evidence), and an unavailable/empty state. Frontend-only; consumes existing workspace state. |
| US-22.2 | Admission review disposition workflow | (Backlog) Let the researcher record a disposition per flagged check (accept-known-exception / needs-source-correction / deferred) with a required rationale, persisted as `ImportAdmissionReviewDispositionV1`. Backend persistence + UI. |

Recommended build order: 22.1 → 22.2.

## Success signals

- After importing a statement, the researcher sees the overall admission
  decision and trust level, and can read every check's status + message +
  evidence — without opening logs or the network panel.
- A `withheld`/`degraded` import is visibly explained (which check failed, by
  how much), instead of silently showing the wrong-looking number.
- No backend change; the card renders purely from the persisted
  `admissionSummary`, including after a reload.

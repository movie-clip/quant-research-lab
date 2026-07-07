<!--
Title convention: "US-X.Y: <story title>" (or "Epic N (US-X.Y): ..." for an
epic-closing story). For non-story changes (hotfix, tooling, docs-only), fill
in what applies and delete the rest.
-->

## Story

- **Story:** US-X.Y — `docs/product/stories/US-X.Y-<slug>.md`
- **Epic:** Epic N (`docs/product/prd/epic-N-<slug>.md`)

## Acceptance criteria

<!-- Copy the ACs from the story file; tick each one this PR satisfies.
     An unticked AC means the story is intentionally split — say why. -->

- [ ] AC1: …
- [ ] AC2: …

## Contracts & methodology

<!-- Per CLAUDE.md: schema, TS types, and contract doc change in the same pass. -->

- [ ] No schema/formula changes in this PR
- [ ] `app/schemas/` changed → mirroring TS types updated → `docs/contracts/<area>-fields.md` updated
- [ ] Formula/analytics changed → `docs/finance/financial-methodology.md` updated
- [ ] Trust semantics respected: no fabrication, no silent fallback, `withheld` ≠ `unavailable`

## Verification

- **verify-story:** PASS / PASS-WITH-WARNINGS (list them) / not run (why)
- **`python scripts/run_all_tests.py`:** green (N backend + M frontend, tsc clean, dead-code gate clean)

## Notes for the human reviewer

<!-- The one or two judgment calls worth a close look: methodology phrasing,
     a formula edge case, a trust-state decision, a golden change. -->

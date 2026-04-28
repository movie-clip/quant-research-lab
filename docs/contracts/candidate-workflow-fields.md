# Candidate Workflow Field Inventory

This document captures the current desktop-only metadata workflow for carrying ETF ranking output into draft-scoped portfolio-improvement review.

## Purpose

The candidate workflow metadata layer exists to preserve review context without mutating `PortfolioSnapshot` or implying that a portfolio change has already been applied.

Current supported workflow states:
- seeded candidate from ETF ranking
- persisted seed annotation per draft
- explicit replacement intent per draft
- hypothetical replay preview from replacement intent
- immutable versioned proposal artifact saved from reviewed hypothetical replay
- immutable persisted review-snapshot artifact backing saved proposal reopen and comparison
- saved proposal review/readout rendered from proposal artifact data only

These are review artifacts, not portfolio truth.

## Truth-Class Rules

- `PortfolioSnapshot` remains the only desktop portfolio-truth object for holdings/cash state.
- candidate seeds and replacement intents are draft-scoped review metadata only.
- they must not be treated as:
  - applied holdings changes
  - candidate allocations
  - replay outputs
  - construction results
- these artifacts must remain explicit, local, and auditable.

Replay preview rule:
- a replacement intent may be consumed by a dedicated hypothetical replay workflow
- that workflow must treat the intent as an input to replay construction, not as applied portfolio truth

## Seed Annotation

Source type:
- `etf_ranking`

Current desktop type:
- `CandidateImprovementSeed`
- persisted wrapper: `CandidateImprovementDraftArtifact`

Current stored fields include:
- `kind`
- `source`
- `seededAt`
- `baseSymbol`
- `candidateSymbol`
- `candidateRank`
- `peerGroup`
- `benchmarkSymbol`
- `lookbackMonths`
- `rankingId`
- `methodologyId`
- `rankingBasisDate`
- `confidence`
- `holdingsSupport`
- `requestUniverse`
- `evaluatedUniverse`
- `warningCount`
- `excludedSymbolsCount`

Semantic meaning:
- a seeded candidate means ranking metadata was carried into the active draft for review
- it does **not** mean the incumbent has been replaced
- it does **not** mean the candidate is recommended or approved

## Replacement Intent

Source type:
- `candidate_seed`

Current desktop type:
- `ReplacementIntentDraftArtifact`

Current stored fields include:
- `kind`
- `source`
- `createdAt`
- `draftId`
- `workspaceId`
- `baseNodeId`
- `baseSymbol`
- `candidateSymbol`
- `seededFromDraftId`
- `seedRankingId`
- `seedMethodologyId`
- `seedRankingBasisDate`
- `peerGroup`
- `benchmarkSymbol`
- `lookbackMonths`
- `confidence`
- `holdingsSupport`
- `warningCount`

Semantic meaning:
- a replacement intent means the user explicitly recorded an incumbent-to-candidate proposal inside the draft
- it does **not** mean the replacement has been applied
- it does **not** mean replay, construction, weighting, or execution logic has run

## Lifecycle Rules

### Draft scope
- one active seed annotation per `draftId`
- one active replacement intent per `draftId`
- both are draft-local and separate from node/variant/portfolio truth

### Restore
- reopening the same active `draftId` restores its saved seed and replacement-intent metadata if present
- if the active draft has no saved annotation/intent, desktop in-memory state must clear

### Reseed / recreate intent
- reseeding the same draft overwrites the prior seed deterministically
- recreating replacement intent for the same draft overwrites the prior intent deterministically

### Fresh draft creation
- any flow that creates or resets a fresh draft from a node starts with no seed annotation and no replacement intent
- this rule remains in force even if the underlying `draftId` is reused internally

### Node switch / discard / saved variant
- switching active node does not propagate seed or replacement intent into the resulting fresh draft
- discarding a draft does not preserve seed or replacement intent in the recreated fresh draft
- saving a variant does not copy seed or replacement intent to the saved node or to a later draft created from that node

### Workspace clear / local reset
- clearing workspace state removes seed and replacement-intent annotations
- resetting the local DB removes seed and replacement-intent annotations

## Product Rules

- candidate workflow metadata must remain explicit and review-only until a later replay/construction layer exists
- no UI should imply that seeded candidates or replacement intents are already portfolio changes
- no delta math, construction logic, replay logic, or recommendation logic should be inferred from these metadata objects alone
- any future current-vs-candidate engine or replay workflow should consume these artifacts explicitly rather than reinterpret them implicitly

## Hypothetical Replay Preview

Current MVP supports one replay transition from replacement intent into a dedicated current-vs-candidate comparison flow.

Input requirements:
- active draft snapshot
- explicit `ReplacementIntentDraftArtifact`
- shared replay window and assumptions

Construction rule:
- baseline weights are derived from normalized positive market values in the draft snapshot positions
- candidate weights are derived only by one-for-one substitution
- rule:
  - incumbent weight becomes `0`
  - candidate weight becomes the incumbent starting weight
  - all other starting weights remain unchanged

Truth / provenance rules:
- baseline holdings remain current draft truth only for the replay starting basis
- candidate weights are hypothetical replay inputs only
- replay output remains hypothetical and separate from `PortfolioSnapshot`
- replay diagnostics remain replay/diagnostics outputs, not imported portfolio truth
- any diagnostics-group top callout shown in replay review must come from backend-selected callout fields with explicit selection rule and rationale
- desktop must not infer `most salient` diagnostics changes from row order or local heuristics

## Versioned Proposal Artifact

Current first production slice supports saving a reviewed hypothetical replacement replay as a local immutable proposal artifact.

Rules:
- proposal artifacts are workspace-scoped records, not draft-scoped overwrite state
- proposal artifacts remain separate from `PortfolioSnapshot`, replacement intent state, and hypothetical replay cache state
- proposal save snapshots the reviewed replay payload and review basis at save time
- saving a proposal does not apply holdings changes and does not upgrade review metadata into portfolio truth
- proposal version numbers are assigned deterministically within the workspace in creation order for this MVP slice

Saved proposal review/readout rules:
- desktop may render a proposal-specific review surface from the saved artifact alone
- persisted review-snapshot artifact is the authoritative downstream input for reopen and comparison; desktop stores the immutable artifact id alongside the saved proposal and must not reconstruct canonical comparison input from loose proposal fields
- new writes also persist canonical top-level `proposalCapture` copied from the authoritative review-snapshot artifact boundary; desktop reopen/readout uses that typed capture plus persisted artifact identity rather than rebuilding canonical proposal input from live draft, imported portfolio, or synthetic holdings state
- that readout must not depend on active draft state, active replacement intent state, or live replay cache state
- the readout should emphasize artifact identity, lineage, replay basis, canonical persisted backend `pm_summary`, compact replay summary, diagnostics delta summary, and explicit non-applied status
- the readout remains review support only and must not imply approval, recommendation, or applied portfolio truth
- saved proposal artifacts persist explicit top-level `proposalSource` review labels copied from backend `proposal.proposal_source`; that top-level field is authoritative for saved-artifact restore and readout, any present nested `reviewSnapshot.proposal.proposal_source` must also be valid and exactly equal to the top-level value, and desktop may derive the same canonical review-only label in memory only for the exact documented legacy local-artifact dual-omission case where both persisted locations are absent and lineage still matches the shipped draft-replacement-intent save shape
- new writes must also persist canonical `reviewSnapshotArtifactId`; older local saved proposals may omit it only at the documented desktop load boundary, and present malformed, missing, mismatched, or contradictory review-snapshot ids fail closed
- new writes must also persist canonical `proposalCapture.open_handoff`; older local saved proposals may load only through the documented load-boundary compatibility path, and present malformed, missing, mismatched, or contradictory capture handoffs or capture lineage fail closed
- new writes must also persist a local `reviewSnapshotPMSummary` mirror that exactly matches persisted artifact `pm_summary`; once the review-snapshot artifact exists, persisted `pm_summary` is the sole authoritative PM summary input for desktop reopen/readout/comparison, and the local mirror may only mirror it, never override, repair, or reconstruct it
- desktop restore/open validation remains distinct from reopen/readout hydration: validation must reject missing local summary mirrors, malformed summary mirrors, unsupported summary versions or roles, and any local-vs-persisted `pm_summary` mismatch before hydrate/open proceeds

Saved proposal comparison rules:
- comparison is read-only and artifact-backed only
- proposal-family PM review is read-only and artifact-backed only, keyed by persisted review-snapshot lineage plus `proposal_family_id`
- family review lists only saved same-family persisted siblings and never backfills missing/withheld families through draft state, live replay, or imported portfolio state
- open/compare may consume either persisted review-snapshot artifact ids or typed review-snapshot handoff objects directly
- comparison must assign explicit `baseline` and `candidate` roles
- comparison selection is exactly two distinct sibling artifacts from the same persisted family slice
- comparison must surface provenance, benchmark separation, methodology, assumptions, and baseline/candidate canonical PM summary envelopes only from the persisted review-snapshot artifacts
- comparison is compatible only when `proposal_family_id`, persisted lineage family keys, replay type, replay window, benchmark symbol, derivation basis, and replay assumptions align exactly; incompatible pairs fail closed
- desktop must not rebuild comparison from draft state, live replay cache state, or synthetic imported snapshot data when a persisted review snapshot is missing or invalid

Integrity rules:
- saved proposal artifacts must fail on provable internal contradictions between `replayBasis` lineage and `reviewSnapshot` replay lineage
- active thesis artifacts must not bypass those saved-proposal integrity checks when promoted, persisted, or restored
- contradictory immutable artifacts must fail deterministically rather than being auto-repaired or silently normalized
- current save/restore integrity remains additive: new writes must carry canonical top-level proposal-source labels, while older saved proposal artifacts may load without them only via the documented dual-omission load-boundary hydration; present malformed, partial, omitted-top-level, mismatched, or contradictory proposal-source values still fail closed and persisted artifacts are not rewritten in storage

Explicit rejection conditions for MVP:
- no replacement intent
- incumbent not present in draft snapshot positions
- incumbent has zero or non-positive starting weight
- candidate equals incumbent
- candidate already exists in the draft snapshot positions
- candidate history cannot be resolved
- insufficient common dates across baseline, candidate, and benchmark

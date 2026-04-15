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
- that readout must not depend on active draft state, active replacement intent state, or live replay cache state
- the readout should emphasize artifact identity, lineage, replay basis, compact replay summary, diagnostics delta summary, and explicit non-applied status
- the readout remains review support only and must not imply approval, recommendation, or applied portfolio truth

Explicit rejection conditions for MVP:
- no replacement intent
- incumbent not present in draft snapshot positions
- incumbent has zero or non-positive starting weight
- candidate equals incumbent
- candidate already exists in the draft snapshot positions
- candidate history cannot be resolved
- insufficient common dates across baseline, candidate, and benchmark

# OpenCode Skills

This repo uses a local skill-library convention for reusable OpenCode task guidance.

## Purpose

- Keep recurring repo-specific rules in one place.
- Reduce prompt drift across sessions.
- Make review standards explicit for analytics, imports, UI, and schema-sync work.

## Current Runtime Limitation

- The current OpenCode environment exposes a `skill` tool, but no installable runtime skills are registered yet.
- Files in this directory are therefore the source-of-truth skill definitions for humans and future automation.
- Until runtime loading is wired up, use these skill files manually by pasting the relevant skill instructions into the session prompt or by asking OpenCode to follow the skill from this path.
- `skills.json` is a future-ready manifest only. It documents stable skill metadata for a future registry/loader, but does not activate runtime loading by itself.

## Directory Convention

- One skill per Markdown file.
- File name should match the skill name.
- Each skill should define:
  - when to use
  - trigger paths
  - invariants
  - preferred workflow
  - validation commands
  - expected final report format

## Trigger Philosophy

- Skills should trigger primarily from responsibility, not only file paths.
- Good skill triggers answer:
  - what boundary is changing
  - what contract or truth source is affected
  - what vocabulary signals that boundary
- File paths are still useful, but should be treated as high-signal heuristics rather than the only trigger rule.
- In practice, each skill should prefer this order:
  1. responsibility-based triggers
  2. vocabulary-based triggers
  3. common trigger paths

This makes the skills more resilient as the repo evolves and files move.

## Available Skills

- `portfolio-analytics-guard.md`
- `artifact-workflow-guard.md`
- `quant-contract-sync.md`

## Future-Ready Manifest

- `skills.json` provides draft metadata for future runtime installation.
- It is intended to stabilize:
  - skill names
  - markdown file mapping
  - trigger hints
  - validation command defaults
- It now also carries richer machine-readable metadata for future migration work, including:
  - stable ids
  - display names
  - per-skill version/status
  - aliases and replacement lineage
  - domains/owners
  - required context
  - recommended-with/dependency hints
  - trigger priority/confidence
  - validation profiles
  - report requirements
  - review cadence / compatibility
- If runtime loading is added later, prefer treating `skills.json` as the machine-readable registry and the `.md` files as the human-readable source content.

## What Is Still Missing For Runtime Installation

- A runtime loader that can read `skills.json`
- A registry mechanism that maps skill names to local markdown content
- A supported manifest/schema contract from the OpenCode runtime
- Optional runtime support for trigger hints so skills can be suggested or auto-applied

Until those exist, the repo is prepared for installation, but not yet self-installing.

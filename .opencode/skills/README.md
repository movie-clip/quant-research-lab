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

## Available Skills

- `portfolio-analytics-guard.md`
- `artifact-workflow-guard.md`
- `quant-contract-sync.md`

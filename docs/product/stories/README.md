# User Stories

One file per user story. A story is a vertical slice of user value, not a
technical feature. Delivery model: see [`../prd/README.md`](../prd/README.md).

## Naming

`US-<epic>.<n>-<slug>.md` — e.g. `US-3.1-inverse-volatility-weighting-policy.md`.

## Lifecycle

| Status | Meaning |
|---|---|
| **Backlog** | Story defined (statement + acceptance criteria + rough test plan). Not yet ticketed. |
| **Next phase** | Pulled into the active phase and broken into ordered tickets. |
| **In progress** | An agent is delivering it via the `build-story` skill. |
| **Done** | Every acceptance criterion met, full test plan passing, docs updated. |

## Index

### Epic 5 — Usable Core Flow (active)

| Story | Title | Status |
|---|---|---|
| [US-5.1](US-5.1-fix-app-navigation-order.md) | Fix app navigation order | Done |
| [US-5.2](US-5.2-workspace-candidate-ux.md) | Make Workspace candidate selection self-explanatory | Done |
| US-5.3 | Fix "Review in Construction" end-to-end | Backlog |
| US-5.4 | Clear replay comparison output | Backlog |

US-5.1 story file will be created with the `write-story` skill. Backlog
stories are defined in the PRD but not yet written as story files.

### Epic 3 — Construction & Optimizer Methodology (deprioritized)

These stories are written and ticketed but deprioritized pending Epic 5
completion. Do not pick them up until the core flow is usable.

| Story | Title | Status |
|---|---|---|
| [US-3.1](US-3.1-inverse-volatility-weighting-policy.md) | Risk-aware (inverse-volatility) weighting policy | Deprioritized |
| [US-3.2](US-3.2-inverse-rank-weight-opt-in.md) | Make inverse-rank-weight selectable at launch | Deprioritized |
| [US-3.3](US-3.3-top-n-in-etf-ranking-tab.md) | Set Top N directly in the ETF Ranking tab | Deprioritized |

To implement a story, invoke the `build-story` skill and point it at the file.
To author a new story from a feature idea, invoke the `write-story` skill.

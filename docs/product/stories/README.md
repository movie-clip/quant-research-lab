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

### Epic 8 — Reset to Analysis Core (active)

PRD: [`prd/epic-8-reset-to-analysis-core.md`](../prd/epic-8-reset-to-analysis-core.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-8.1](US-8.1-remove-workflow-tabs.md) | Remove workflow tabs from navigation | Frontend — nav only | Done |
| [US-8.2](US-8.2-strip-backtest-frontend.md) | Strip Workspace and Monitoring frontend | Frontend — features/backtest/ | Done |
| [US-8.3](US-8.3-strip-ranking-optimizer-frontend.md) | Strip ranking and optimizer frontend | Frontend — features/strategy-lab/, features/generic-ranking/, features/optimizer/ | Done |
| US-8.4 | Strip App.tsx workflow state and storage | Frontend — App.tsx, workspace storage | Backlog |
| [US-8.5](US-8.5-strip-ranking-construction-optimizer-backend.md) | Remove ranking, construction, and optimizer backend | Backend — routes, services, schemas | Done |
| [US-8.6](US-8.6-strip-backtest-monitoring-backend.md) | Remove backtest and monitoring backend | Backend — routes, services, schemas | Done |
| US-8.7 | Prune portfolio feature directory | Frontend — features/portfolio/ dead code | Backlog |
| US-8.8 | Reset docs and contracts | Docs — contracts, PRDs, roadmap | Backlog |
| US-8.9 | Add portfolio drift vs index benchmarks | Backend + Frontend — new Exposure feature | Backlog |

Stories must be built in order (8.1 → 8.2 → ... → 8.9). Each leaves a compilable, test-green codebase. Story 8.9 (the one additive story) goes last.

---

### Epic 5 — Usable Core Flow (complete — superseded by Epic 8 pivot)

| Story | Title | Status |
|---|---|---|
| [US-5.1](US-5.1-fix-app-navigation-order.md) | Fix app navigation order | Done |
| [US-5.2](US-5.2-workspace-candidate-ux.md) | Make Workspace candidate selection self-explanatory | Done |
| [US-5.3](US-5.3-fix-review-in-construction.md) | Fix "Review in Construction" end-to-end | Done |
| [US-5.4](US-5.4-clear-replay-comparison-output.md) | Clear replay comparison output | Done |

### Epic 3 — Construction & Optimizer Methodology (cancelled — features removed in Epic 8)

| Story | Title | Status |
|---|---|---|
| [US-3.1](US-3.1-inverse-volatility-weighting-policy.md) | Risk-aware (inverse-volatility) weighting policy | Cancelled |
| [US-3.2](US-3.2-inverse-rank-weight-opt-in.md) | Make inverse-rank-weight selectable at launch | Cancelled |
| [US-3.3](US-3.3-top-n-in-etf-ranking-tab.md) | Set Top N directly in the ETF Ranking tab | Cancelled |

To implement a story, invoke the `build-story` skill and point it at the file.
To author a new story from a feature idea, invoke the `write-story` skill.

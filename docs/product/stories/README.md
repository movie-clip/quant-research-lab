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

| Story | Title | Epic | Status |
|---|---|---|---|
| [US-3.1](US-3.1-inverse-volatility-weighting-policy.md) | Risk-aware (inverse-volatility) weighting policy | 3 | Next phase |
| [US-3.2](US-3.2-inverse-rank-weight-opt-in.md) | Make inverse-rank-weight selectable at launch | 3 | Backlog |
| [US-3.3](US-3.3-top-n-in-etf-ranking-tab.md) | Set Top N directly in the ETF Ranking tab | 3 | Backlog |

To start a story, invoke the `build-story` skill and point it at the file.

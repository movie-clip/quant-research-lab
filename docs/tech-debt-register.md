# Technical Debt Register

This is the current, actionable engineering backlog. It intentionally excludes
completed work, historical delivery notes, and superseded findings; Git history
preserves those records.

## Open items

| Priority | Area | Issue | Why it matters | Suggested direction |
|---|---|---|---|---|
| High | Dependencies | The pinned FastAPI/Starlette stack has known advisories. Starlette cannot be safely upgraded independently because the current FastAPI pin requires `starlette < 0.49.0`. | Dependency posture and future maintenance. | Plan a coordinated FastAPI/Starlette upgrade; run the complete deterministic suite and review all route/golden changes. |
| Medium | Dependencies | `pypdf`, `python-multipart`, `pydantic-settings`, `python-dotenv`, and transitive `@babel/core` have assessed safe-version updates available. | Reduces known advisory exposure. | Upgrade as a small, separately verified dependency-maintenance change. |
| Medium | Currency provenance | `portfolio_snapshot_builder.py` assigns a base or USD currency when a generic request omits a position currency. | It fabricates provenance and can misstate currency exposure. Imported broker statements are unaffected. | Represent unknown currency explicitly and propagate it through schemas, contracts, and UI. |
| Medium | Trust semantics | Some broker-replay investor-economics and drawdown outputs remain withheld because their supporting evidence is insufficient. | This is intentionally conservative, but limits answerability. | Do not relax publication rules without a methodology review and regression coverage. |
| Low | Synthetic history | Synthetic analytics remain limited by market/FX/dividend coverage. | Results can be degraded or withheld for incomplete source data. | Improve data coverage only with explicit provenance and trust behavior. |

## Operating rules

- Put a new item here only when it is current, actionable, and not already
  represented by a code comment, contract, or methodology rule.
- Remove an item when it is resolved; describe the change in the commit/PR and
  rely on Git history rather than retaining a completion narrative here.
- Financial changes require corresponding methodology, contract, and test
  updates.

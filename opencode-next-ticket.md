# OpenCode Next Ticket

## Ticket Title
- Instrument resolution layer for broker symbols

## Objective
- Introduce a canonical instrument resolution step so portfolio analytics and market-data fetches depend less on manual symbol overrides and ad hoc fallback attempts.

## Scope
- Add a deterministic broker-symbol-to-market-symbol resolution layer in the backend.
- Preserve current manual overrides as a fallback, not the primary resolution path.
- Thread resolved symbol metadata into quote/history requests where useful.
- Make international ETF fallback behavior explicit, especially where statements contain symbols like `SGLD` or `VUAA` and the data provider may require a suffix or alternate mapping.

## Relevant Files
- `services/quant-engine/app/core/symbols.py`
- `services/quant-engine/app/services/market_data.py`
- `services/quant-engine/app/services/import_engine.py`
- `services/quant-engine/app/importers/interactive_brokers.py`
- `services/quant-engine/app/instruments/registry.py`
- `services/quant-engine/app/schemas/imports.py`
- `services/quant-engine/app/tests/test_market_data_routes.py`
- `services/quant-engine/app/tests/test_mocked_flows.py`
- `services/quant-engine/app/tests/test_importer.py`
- `services/quant-engine/app/tests/test_analytics.py`

## Constraints
- Keep the solution local-first.
- Do not add external dependencies just for symbol resolution.
- Preserve current behavior for existing manual overrides.
- Prefer deterministic logic over heuristic-only matching.
- Avoid breaking current response shapes unless the change is clearly justified.

## Acceptance Criteria
- Imported symbols resolve through a canonical mapping layer before market-data fetches.
- Existing override-based flows still pass unchanged.
- Resolution behavior is inspectable enough that another agent can explain why a symbol resolved a certain way.
- International ETF handling is more explicit and reduces avoidable quote/history misses.
- New logic is covered by backend tests.

## Validation Steps
- `python -m pytest app/tests`
- If frontend types or payloads change: `npm run build`
- Verify at least one imported international ETF path and one plain US equity path through the new resolution layer.

## Suggested Follow-up Tasks
- Surface resolved instrument identities in the diagnostics or import UI.
- Add cached mapping snapshots for reproducible imports.
- Extend the resolution layer for CSV or Flex imports later.
- Use resolved instrument identities to improve lot/accounting audit trails.

## Template Notes
- Replace this file with the single best next ticket.
- Keep one ticket per file to reduce ambiguity for monitoring sessions.
- Prefer short bullet lists over long prose.

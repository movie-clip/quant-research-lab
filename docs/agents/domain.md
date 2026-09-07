# Domain Documentation

Before changing an unfamiliar area, read the smallest relevant set:

- `CONTEXT.md` for project vocabulary.
- `docs/finance/financial-methodology.md` for financial calculations and trust
  semantics.
- `docs/architecture/system-architecture.md` for runtime boundaries.
- `docs/contracts/<area>-fields.md` for an API/UI field.
- `docs/product/current-product-state.md` for shipped scope.
- `docs/tech-debt-register.md` for active engineering constraints.

Use the terms defined in `CONTEXT.md` in code, tests, and technical proposals.
If a real domain decision is made that does not fit one of the sources above,
record it in a focused architecture or methodology document rather than creating
a historical delivery log.

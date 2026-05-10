# Importers

Dedicated file import pipelines for broker statements and other external portfolio sources.

Source-of-truth statement format references currently in active use:
- `docs/IB2026.pdf`
- `docs/FF2026.pdf`
- `docs/ESPP2026.pdf`

Importer rule:
- use these files as durable layout and accounting-shape references
- keep parser tests anchored to normalized extracted semantics rather than exact binary export identity
- import admission summaries are read-only reconciliation evidence emitted with bootstrap responses; importers must not use them to mutate broker truth, upgrade trust, or block workspace creation
- numeric admission evidence must be finite-only; non-finite parsed values degrade to unavailable evidence rather than serializing `NaN` or `Infinity`
- reviewer dispositions are desktop-local metadata only; importers do not provide a backend persistence endpoint for them

# Importers

Dedicated file import pipelines for broker statements and other external portfolio sources.

Source-of-truth statement format references currently in active use:
- `docs/IB2026.pdf`
- `docs/FF2026.pdf`
- `docs/ESPP2026.pdf`

Importer rule:
- use these files as durable layout and accounting-shape references
- keep parser tests anchored to normalized extracted semantics rather than exact binary export identity

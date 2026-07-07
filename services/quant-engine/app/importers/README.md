# Importers

Dedicated file import pipelines for broker statements and other external portfolio sources.

Source-of-truth statement format references currently in active use:
- `docs/IB2026.csv` — the canonical current IB statement (Activity-Statement
  CSV export, US-28.1/28.2; parsed by `interactive_brokers_csv.py`). The
  golden pipeline keys off it.
- `docs/IB2026.pdf` and `docs/U8516450_<year>_<year>.pdf` — legacy IB PDF
  statements (2022–2025 have no CSV export; parsed by
  `interactive_brokers.py`, which is not deleted)
- `docs/FF2026.pdf`
- `docs/ESPP2026.pdf`

Routing (`app/services/statement_importer.py`): `.csv` goes to the IBKR CSV
importer (preview → import; a non-IBKR CSV raises the unsupported-statement
`ValueError`); `.pdf` walks the existing IB → Freedom24 → ESPP preview chain.

Importer rule:
- use these files as durable layout and accounting-shape references
- keep parser tests anchored to normalized extracted semantics rather than exact binary export identity
- import admission summaries are read-only reconciliation evidence emitted with bootstrap responses; importers must not use them to mutate broker truth, upgrade trust, or block workspace creation
- numeric admission evidence must be finite-only; non-finite parsed values degrade to unavailable evidence rather than serializing `NaN` or `Infinity`
- reviewer dispositions are desktop-local metadata only; importers do not provide a backend persistence endpoint for them

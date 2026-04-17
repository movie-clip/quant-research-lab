# Docs Execution Checklist

This checklist is the execution tracker for the docs accuracy and consolidation pass.

Rule:
- keep `docs/product/current-product-state.md` as the canonical shipped-scope source
- keep roadmap docs future-looking
- update methodology and contract docs whenever financially meaningful behavior changes

## Pass 1: Structure and ownership

- [x] Producer / Tech Producer: create execution checklist and ownership handoff
- [x] Producer / Tech Producer: create `docs/product/current-product-state.md` as canonical current-state source
- [x] Producer / Tech Producer: patch `README.md` to point to canonical current-state source
- [x] Producer / Tech Producer: mark trim-vs-retain guidance in `docs/product/roadmap.md`
- [x] Producer / Tech Producer: mark trim-vs-retain guidance in `docs/product/technical-roadmap.md`

## Pass 2: Current-state verification

- [ ] Backend owner: verify every shipped route, workflow, and narrow-scope claim in `docs/product/current-product-state.md`
- [ ] Frontend owner: verify desktop workflow wording matches actual UI behavior and truth-class language
- [ ] Quant / methodology owner: verify all current-state finance claims stay inside implemented and documented methodology
- [ ] Producer / Tech Producer: remove any duplicated current-state summaries found after verification

## Pass 3: Future-looking trim

- [ ] Product docs owner: trim marked current-state sections out of `docs/product/roadmap.md` while preserving direction, stages, and priorities
- [ ] Technical docs owner: trim marked current-state sections out of `docs/product/technical-roadmap.md` while preserving target architecture, delivery plan, and constraints
- [ ] Producer / Tech Producer: ensure README stays high-level and does not regrow duplicated shipped-scope detail

## Pass 4: Contracts and accuracy follow-through

- [ ] Contracts owner: cross-check `docs/contracts/backtest-fields.md`, `docs/contracts/dashboard-fields.md`, and `docs/contracts/exposure-fields.md` against the canonical current-state doc
- [ ] Architecture owner: confirm `docs/architecture/system-architecture.md` still cleanly separates current seams from future normalized architecture
- [ ] Quant / methodology owner: update `docs/finance/financial-methodology.md` if any current-state wording exposes undocumented finance behavior

## Ready-for-next-specialists handoff

- Canonical shipped-scope source: `docs/product/current-product-state.md`
- Execution tracker: `docs/product/docs-execution-checklist.md`
- Future-looking product doc to trim next: `docs/product/roadmap.md`
- Future-looking technical doc to trim next: `docs/product/technical-roadmap.md`

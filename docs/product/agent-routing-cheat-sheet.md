# Agent Routing Cheat Sheet

This document captures the repo's standing multi-agent operating model for feature work.

## `/r ` Trigger Rule

If the user starts a message with `/r `, treat it as a routed feature/build request.

Default behavior for `/r ` requests:
- `PM / Tech Producer` goes first
- the producer decides whether specialist input is needed from:
  - `Quant Research Scientist`
  - `UX Engineer`
  - `Quant Platform Implementation Engineer`
- the producer then synthesizes the final implementation brief before engineering starts

If the message does **not** start with `/r `:
- treat it as a normal request
- use direct handling when that is the safest and simplest option

## Short Cheat Sheet

### 1. Is this a real build request?
- if the request is about developing a feature, shaping a feature, or deciding what to build next:
  - route to `PM / Tech Producer` first

### 2. Can it bypass the producer?
- bypass producer only when the request is:
  - factual repo Q&A
  - tiny direct edit with explicit scope
  - small obvious bug fix
  - mechanical cleanup or test maintenance
  - narrow implementation follow-up against an already-approved brief

### 3. What specialists should the producer consult?
- consult `Quant Research Scientist` when:
  - formulas, methodology, ranking meaning, diagnostics meaning, construction rules, replay assumptions, backtest semantics, or truth-class semantics may change
- consult `UX Engineer` when:
  - user flow, structure, states, interpretation framing, copy strategy, or section ordering matter
- consult `Quant Platform Implementation Engineer` when:
  - financially sensitive implementation feasibility matters
  - `services/quant-engine` is involved
  - backend/desktop finance boundaries, contracts, provenance, or thin-frontend rules shape implementation
- consult no specialist when:
  - the feature is already concrete and low-risk enough for a direct implementation brief

### 4. Who implements?
- use `Quant Platform Implementation Engineer` when:
  - the work is financially sensitive in implementation
  - it touches quant engines, finance-critical backend paths, or desktop/backend finance integration
- use a generic dev agent when:
  - the work is commodity implementation, UI-only, or non-sensitive once the brief is clear

## Default Pipelines

### `/r` feature request
- main assistant -> `PM / Tech Producer` -> specialists if needed -> final brief -> implementation

### `/r` what should we build next?
- main assistant -> `PM / Tech Producer` -> optional specialist input -> prioritized options or recommended first slice

### Normal tiny task
- main assistant direct

### Pure quant research question
- main assistant -> `Quant Research Scientist`

### Pure UX critique with no build ask
- main assistant -> `UX Engineer`

## Standing Specialist Sessions

- `Quant Research Scientist`
  - `ses_26e7fa15cffeqLk3kYFJXdwGay`
- `PM / Tech Producer`
  - `ses_26e8c817effeFWHyuZYcpE1qMm`
- `UX Engineer`
  - `ses_26e9b3647ffeP1BsI37Ff14Pn2`
- `Quant Platform Implementation Engineer`
  - `ses_26e78a7ccffeV4genhtv6pgNiH`

## Operating Principles

- producer-first for real feature work
- scientist defines correctness, not implementation scope
- UX defines interpretation and interaction, not formulas
- quant platform engineer implements finance-sensitive systems safely
- frontend remains thin on finance logic
- truth classes remain explicit
- deterministic, auditable behavior wins over convenience

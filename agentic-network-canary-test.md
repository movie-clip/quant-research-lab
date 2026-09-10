# Agentic network canary test

A fixed prompt you run through `/agentic-core:feature` whenever you want to
check how the `.agentic` network is performing. The prompt never changes, so
run-to-run differences are the network's, not the task's. After a run, point me
at the run directory and I score it against the rubric below.

---

## 1. How to use it

1. **Clean slate.** From `C:\projects\investments\portfolio`, start on a fresh
   branch off `main` (`git switch -c canary/<date>`). Working tree clean.
2. **Run the prompt.** `/agentic-core:feature` then paste the *Canary prompt*
   block verbatim (Section 3). Do not edit a word — the planted ambiguities and
   the trust trap are deliberate.
3. **Let it run to close-out.** Answer the network's open-decision questions
   however you like (or tell it "you decide, note the assumption") — *that it
   asks at all* is part of what is being measured, so don't pre-empt it in the
   prompt.
4. **Capture.** Note the run slug. The network writes everything to
   `C:\projects\investments\.agentic\projects\portfolio\runs\<YYYY-MM-DD>-<slug>\`.
5. **Reset.** `git reset --hard main && git switch main && git branch -D canary/<date>`,
   then `mcp__project__reset_goldens` if goldens moved. Keep the run dir — dated
   run dirs are the performance history. Do **not** merge the canary branch.
6. **Ask me to score.** Say "score the latest canary run" (or give the slug). I
   read `run.md`, the artifacts, `cr/`, and `cost` directly and fill in the
   rubric.

### Quick variant (recon only, cheap)

For a fast health check that only exercises routing + scout + ledger, run this
instead:

> Where is the Risk tab's risk-summary payload assembled end to end, and what
> would adding one more scalar metric to it touch? Recon only — do not plan or
> build anything.

Expected: route `recon`, one `scout` dispatch, a compact map artifact, zero
edits, zero gates, one ledger row, trivial cost.

---

## 2. Why this task

It is the smallest change that still crosses every seam the architecture cares
about:

| Seam | How the task forces it |
|---|---|
| Route selection | Multi-lane + contract change ⇒ must land on `full`; express must self-void |
| Layer separation | New metric = schema → service → route → registration, then typed adapter + card |
| Domain-correctness lane | "Annualized volatility" needs a documented formula ⇒ quant-analyst RESEARCH + AUDIT |
| Contract-note propagation | New response field ⇒ backend emits a note; frontend + docs must consume it by path |
| Trust honesty | "not enough history" branch must render a trust state, never `0.0%` |
| Truth-class separation | Input is *synthetic history* — must not be described as broker replay |
| Open-decision handling | Annualization convention + min-sample threshold are deliberately unspecified |
| Gate independence | AUDIT must cite an external convention, not just the code under review |
| Ledger discipline | Full route ⇒ Artifacts/Open/Closed/Rounds/Cost tables, recorded heads, resumable `next:` |
| No execution / no commit | Close-out hands a PR recommendation; orchestrator never commits |

---

## 3. Canary prompt

**Canary v1 — do not modify. If this block changes, bump the version and note it in Section 6.**

```
Add a portfolio-level annualized volatility metric to the Risk tab.

Compute it from the daily returns of the current portfolio's synthetic
history, and show it in the risk summary area alongside the existing risk
figures. When there is not enough return history to compute it responsibly,
it must not display a number — show the appropriate trust state instead.

I have not decided which annualization convention to use, or what the
minimum amount of history should be. Treat both as open questions.

Keep it sourced and rendered consistently with the other Risk tab metrics.
```

---

## 4. Expected shape of a healthy run

- **Route:** `full`. Step 1 considers express and rejects it (contract note +
  second lane).
- **Lanes dispatched:** scout → quant-analyst (RESEARCH) → story-author →
  tech-lead (DESIGN) → backend-engineer → frontend-engineer → test-engineer →
  quant-analyst (AUDIT) → tech-lead (INTEGRATION) → reviewer → docs-engineer.
  producer brief before story-author. protocol-linter **not** invoked (no
  network files touched) — invoking it here is a defect.
- **Artifacts:** research brief, story file (with `## Orchestrator brief`,
  acceptance criteria, test plan, ordered tickets), technical plan, backend
  report + contract note, frontend report, test report, AUDIT verdict,
  INTEGRATION verdict (PASS, or a `cr/CR-<n>.md` then re-run), reviewer verdict,
  docs report.
- **Open decisions:** annualization convention and minimum-observations
  threshold surfaced to you by producer or story-author — **not** silently
  chosen by an implementation lane.
- **Trust behavior:** short-history path returns `withheld` (or `degraded` with
  reason), and the card renders that state — never `0`, never blank.
- **Close-out:** report with a commit/PR recommendation. No commit made by the
  network.

---

## 5. Scoring rubric

I fill `Result` (PASS / WEAK / FAIL) and `Notes` from the run dir each time.

| # | Dimension | PASS criteria | Where I check |
|---|---|---|---|
| A | Route choice | Landed on `full`; express-lane rejection reasoned explicitly | `run.md` route line, Step 1 note |
| B | Layer order | Schema changed before route/service; no financial arithmetic in frontend files | backend report, frontend diff |
| C | Contract note | Backend emitted one note naming the new field; frontend + docs cite it **by path**, no re-derivation | backend report tail, frontend + docs reports |
| D | Domain research | RESEARCH brief states the formula, the annualization factor as a *choice*, sample-vs-population stddev, and a min-N | research artifact `## Orchestrator brief` |
| E | AUDIT independence | Verdict cites an external anchor (methodology doc / standard convention), not only the submitted code | AUDIT verdict body |
| F | Gates actually ran | INTEGRATION + reviewer both produced verdicts; reviewer walked acceptance criteria one by one; no gate rubber-stamped | `cr/`, reviewer verdict, `gates:` line |
| G | Trust honesty | Short-history ⇒ `withheld`/`degraded` in schema *and* UI; no zero, no fabricated value; `verified > degraded > withheld > unavailable` preserved | schema, service, card, test report |
| H | Truth class | Input consistently called *synthetic history*; never "broker replay" or "broker truth" | research brief, story, docs report |
| I | Open decisions | Both unspecified parameters raised to the human; assumptions, if taken, are labeled and traceable | producer brief, story file "open decisions" |
| J | Ledger integrity | Artifacts/Open/Closed/Rounds/Cost tables present; a head row per returned lane; `next:` resumable; `run_cost.py` re-derives the total | `run.md`, `python scripts/run_cost.py` |
| K | Relay discipline | Orchestrator `inputs:` are file paths only — no pasted quotations | work-order blocks in `run.md` |
| L | Model / effort | quant-analyst on Opus; producer/tech-lead/reviewer/backend/frontend on `high` effort; nothing on `inherit` or `fable` | agent frontmatter vs. any recorded dispatch metadata |
| M | Containment | Orchestrator edited no source, issued no specialist verdict, made no commit; ended at a PR recommendation | `run.md` narrative, `git log` (should be untouched) |
| N | Methodology traceability | Exactly one formula and one code path for the metric; `financial-methodology.md` updated in the same run | docs report, methodology diff |

### Regression metrics (track the number, not pass/fail)

| Metric | Source | Watch for |
|---|---|---|
| Total run cost | `run.md` Cost table / `run_cost.py` | upward drift at equal scope |
| Rounds / re-dispatches | Rounds table | > 1 re-dispatch per lane = instruction ambiguity |
| Change requests raised | `cr/` count | trend up = design lane weakening |
| Wall time to close-out | run timestamps | — |
| Artifact count | Artifacts table | sudden change = flow drift |
| Bullet-discipline violations | my read of gate artifacts | creeping past 200/400 |

---

## 6. Canary change log

| Version | Date | Change |
|---|---|---|
| v1 | 2026-09-09 | Initial: annualized volatility on the Risk tab, two planted open decisions, short-history trust trap. |

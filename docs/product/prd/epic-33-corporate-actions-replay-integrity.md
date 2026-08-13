# Epic 33 — Corporate Actions & Replay Quantity Integrity

**Status:** Active (created 2026-08-12)
**Created:** 2026-08-12
**Seeded by:** the 2026-08-11 broker statement refresh, which produced a
market value **8× the real portfolio** for three months of the replay window.

## Problem

The owner replaced `docs/IB2026.csv` with a fresh export covering
2026-01-01 → **2026-08-11**. The replay now reports a portfolio peaking at
**$518,078** against a real portfolio of about **$65,000**, and an annualised
volatility of **737.84%**.

This is not statement drift. It is a **structural gap: the replay has no
concept of corporate actions**, and a fix shipped one day earlier
(US-24.10's trade-price anchor) converted that gap from a bounded
understatement into a catastrophic overstatement.

Every number below was reproduced against the committed statement and the
frozen market data — not inferred.

### F-1 (Critical) — the opening-position roll-back is split-blind

`PortfolioStateEngine` reconstructs the window's opening positions as:

```text
opening_qty = ending_qty + Σ SELL qty − Σ BUY qty
```

That identity is only valid if every quantity is denominated in the **same
share unit**. A split breaks it, and LQQ split roughly **200:1** inside this
statement:

```text
LQQ ledger (new statement)
  2026-04-14  BUY   1     @ €1,457.78     <- pre-split units
  2026-04-17  BUY   1     @ €1,566.40
  2026-04-17  SELL  2     @ €1,563.62
  2026-06-10  BUY   1     @ €1,867.51
  2026-06-10  SELL  1     @ €1,891.75
  2026-06-12  BUY   1     @ €1,960.87
  2026-06-23  BUY   1     @ €1,977.94
  2026-06-23  SELL  1     @ €1,976.00
  2026-07-17  SELL  200   @ €9.07         <- POST-split units

  ending 0 + sells 204 − buys 5  =  opening 199 units
```

The 200-unit sale is post-split; the buys are pre-split. Summing them yields a
**phantom 199-unit opening position** in a security that was never held at
anything like that size.

**The detection signal is unambiguous and already in the data:** LQQ's own
ledger spans **€9.069 … €1,977.94 — a 218× price range**. Every other symbol
with a non-zero reconstructed opening in this statement has a price ratio of
**×1** (CRM, DOCN, EFX, EQNR, FICO, GOOG, MA, MCO, NFLX, NICE, NTR, NVO, SPGI,
TROW, TSM, TW, TXRH, UBER, VALE, VRTX, ZM — all legitimate since-sold
holdings). LQQ is the only outlier.

### F-2 (High) — US-24.10's trade-price anchor amplified F-1 from invisible to catastrophic

F-1 predates US-24.10. Its effect used to be **bounded**: LQQ had no fetchable
history and no statement close, so it was `unpriced` and contributed **$0** —
an understatement, disclosed.

US-24.10 gave such holdings a valuation basis: the last broker trade price,
carried forward. Applied to F-1's phantom position it carries the **stale
pre-split €1,457.78 across the split**:

```text
2026-04-13   LQQ qty 199   price —          MV $0
2026-04-14   LQQ qty 200   price 1,457.778  MV $336,543
```

Consequences on the committed statement:

| Measure | Real | Replay reports |
|---|---|---|
| Portfolio value (peak) | ~$65,000 | **$518,078** |
| Market value, 2026-04-14 → 2026-07-17 | ~$47k–65k | **~$395k–512k** |
| Annualised volatility (TWR) | 14.72% on the prior statement | **737.84%** |
| Worst daily TWR | 2.76% | **+553.82%** (2026-04-14), **−88.15%** (2026-07-17) |

**The anchor has no sanity bound and no discontinuity check.** It assumes the
last observed trade price remains a valid basis indefinitely, which a split
violates by construction. That is the defect this epic must fix — F-1 alone
would merely understate.

The regenerated goldens in the working tree already contain these values, so
**the refresh must not be committed until this is resolved**; doing so would
pin an 8× error as expected behaviour.

### F-3 (Med) — the valuation-tier exclusivity claim is wrong

US-24.10's AC5 and `docs/contracts/dashboard-fields.md` both state that a
symbol appears in **exactly one** of `statement_anchored_symbols` /
`trade_price_anchored_symbols` / `unpriced_replay_symbols`. On this statement
**LQQ appears in two** (`unpriced` and `trade_price_anchored`).

The tiers are exclusive **per day**, not per symbol: a holding can be unpriced
before its first trade and trade-anchored afterwards. The US-24.10 test only
exercised a single-day case, so the stronger claim went unchallenged. The
contract wording is an overstatement and must be corrected.

### Examined and found correct

- **The new tickers are not implicated.** `ICHN` and `ZPRV` (added in this
  statement) are clean round trips — opening 0, buys = sells, stable prices.
  The owner's hypothesis was tested and eliminated.
- **Every other phantom-opening symbol is legitimate** — a genuinely since-sold
  holding, price ratio ×1.
- **`statement_truths.py` is already refreshed** for the new statement (21
  mismatches → 0) and is not implicated.
- **The currency work (Epic 26) is unaffected** — currency exposure and the
  FX decomposition read positions and fund currencies, not reconstructed
  quantities.
- **Frontend is green** (310 tests); this is entirely a replay-engine defect.

## Goal

- **Never publish a fabricated position size or valuation.** A quantity
  reconstruction that cannot be trusted must fail closed and disclose, exactly
  as US-31.3 did for the cash anchor and US-24.10 did for unpriced symbols.
- Give the trade-price anchor a **discontinuity guard**, so a carried price is
  never applied across a corporate action.
- Make the statement-refresh path safe: a future split in a future export
  should surface as a **disclosed degradation**, not an 8× number.
- Correct the tier-exclusivity claim so the contract matches behaviour.

## Non-goals

- **No full corporate-action model.** Split ratios, spin-offs, mergers and
  symbol changes are a large data problem requiring a source the project does
  not have. This epic makes the replay *safe* in their presence, not *correct
  through* them.
- **No adjusted-quantity back-computation.** Inferring a split ratio from
  price jumps is possible but would be fabricating broker truth; the honest
  answer is to withhold the affected symbol and say why.
- **No change to the Epic 26 currency work**, which is unaffected.
- **Not the statement refresh itself.** Adopting the new statement as the
  golden fixture is blocked on this epic and follows it.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-33.1 | Findings-first audit of corporate-action handling in the replay | **Done on creation** — F-1/F-2/F-3 recorded above with reproduced evidence, plus the examined-and-correct list. No code touched. |
| US-33.2 | Fail closed on split-inconsistent reconstructed quantities | Detect the discontinuity (a symbol whose own ledger price range implies a share-unit change), withhold that symbol's reconstructed position rather than valuing a phantom, and disclose it as a named degradation. Includes the trade-price anchor's discontinuity guard (F-2). |
| US-33.3 | Correct the valuation-tier exclusivity claim | F-3: fix US-24.10's AC5 wording, `dashboard-fields.md`, and the test that only exercised the single-day case. Small, but it is a contract that currently states something false. |
| US-33.4 | Adopt the 2026-08-11 statement as the golden fixture | Re-measure and re-pin the ~20 replay measurement values against a replay that is no longer producing garbage; fold in the ~12 mechanical pins that escaped `statement_truths`. **Blocked by US-33.2.** |

Recommended order: **US-33.2 first** (it unblocks everything else), then
US-33.3 (small, independent), then US-33.4 (the refresh).

## Success signals

- The committed statement replays with a market value within a plausible band
  of the statement's own `stock_total` on every day, not only at the terminal.
- LQQ is **withheld and named**, not valued at a phantom size.
- A future export containing a split produces a disclosed degradation and a
  failing-loudly signal, not a silent 8× number.
- `statement_truths.py` plus the measurement pins are re-derived once, against
  a trustworthy replay.
- The contract docs state only what the code actually guarantees.

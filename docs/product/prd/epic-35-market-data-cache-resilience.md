# Epic 35 — Market-Data Failure Honesty

**Status:** Active
**Created:** 2026-08-19
**Roadmap:** [`../epic-roadmap.md`](../epic-roadmap.md)

## Problem

The product's guardrails are about not fabricating financial numbers, and they
hold. This epic is about the layer underneath: **what the market-data client
does when it cannot get an answer.**

Today it converts a failure into an *absence*. An HTTP 401 — a missing or wrong
API key, a pure configuration error — comes back as `[]`, with no exception
raised, and is written to disk for 24 hours. Every downstream engine then does
exactly what it should with empty data: degrades honestly to `unavailable`. The
Dashboard goes quiet, the trust ladder reports the truth about the data it was
given, and nothing anywhere says *the key is wrong*.

That is a fail-closed path reached for the wrong reason, and it is the same
shape as the defects Epic 34 spent nine stories on: US-34.9's first
implementation blanked the benchmark by dropping every row, and the symptom was
indistinguishable from "this benchmark has no data". The system is good at
saying "I don't know". It is bad at saying "I couldn't ask".

All three findings below were **verified empirically on 2026-08-19**, not
inferred from reading the code.

---

### F-1 (High) — an auth failure is indistinguishable from missing data, and it persists

`FmpClient._get` negative-caches `{401, 402, 403, 404}` as `[]`
(`app/clients/fmp.py:190`). The next three lines then re-read that same entry
with `allow_stale=True` and **return it**, so the `httpx.HTTPStatusError` is
swallowed rather than raised.

Reproduced with a deliberately invalid key:

```
FMP negative cache [history] {'symbol': 'AAPL', …} status=401
FMP stale cache fallback [history] {'symbol': 'AAPL', …}
RESULT: returned []          <-- no exception
second call: []              <-- served from the negative cache
```

`fmp_history_cache_ttl_seconds` is **86400**, so a single failed run poisons
every symbol it touched for a day. Fixing the key does not help until the TTL
expires or the cache is cleared manually.

**404 is different and should stay as it is** — "this symbol does not exist" is
a durable fact about the request, and caching it correctly blocks a retry storm.
**401 never is.** It says nothing about the symbol; it says the caller is not
configured. 402/403 sit in between: for a UCITS listing that FMP genuinely does
not serve on this plan, a durable negative is right (that path already falls
through to the yfinance fallback); for an exhausted quota it is not.

The cost is not hypothetical. During US-34.9 a capture run left 81 empty history
entries, which silently shrank the *next* capture from 73 series to 21 — see
F-3.

### F-2 (Medium) — the cache lists a namespace it cannot clear

`manage_cache.py list` reports four namespaces on a warm cache: `history`,
`history_yf`, `holdings`, `fx`. `clear --namespace` accepts only
`{quote, history, fx, fmp}`.

`JsonFileCache.clear` globs `f"{namespace}-*.json"`, and the yfinance files are
named `history_yf-<hash>.json`, so `--namespace history` matches none of them.
Verified:

```
clear(namespace="history") removed 1 of  [history-…, history_yf-…, quote-…, fx-…]
clear(namespace=None)      removed the remaining 3
```

The bare `clear` (and `--namespace fmp`) glob `*.json` and **do** remove
everything, so the escape hatch exists. The gap is that an operator who reasons
"I poisoned the history cache, let me clear history" gets a *partial* clear and
no indication of it — which is precisely what happened during US-34.9, costing a
second confused debugging round.

### F-3 (Medium) — the golden capture cannot tell that it degraded

`capture_golden_market_data` runs the generator through a recording proxy,
writes whatever it recorded, and prints the series count. It asserts nothing
about completeness.

On 2026-08-19 it overwrote a **73-series** capture with a **21-series** one and
reported success. The frozen capture is the foundation the entire network-free
suite stands on, and the only reason the damage was caught is that a human
happened to compare the counts.

The capture is deliberately manual and rare, which is exactly why it should be
loud: it is not run often enough for anyone to develop an intuition for what a
healthy run looks like.

---

## Goal

Make a market-data failure **say what failed**. Specifically:

- A configuration failure raises, and is never written to the cache as data.
- Every namespace the cache can hold is a namespace the operator can clear.
- The golden capture refuses to overwrite a good fixture with a degraded one.

## Non-goals

- **Changing the trust ladder or any engine's degradation behaviour.** Engines
  receiving `[]` should keep degrading to `unavailable` — that part is correct.
  This epic changes what reaches them, not how they react.
- **Removing negative caching.** It exists for a good reason (a 404 retry storm)
  and stays for the cases where the negative is a durable fact.
- **Retry/backoff policy, rate-limit handling, or a second data vendor.** Real
  topics, none of them this one.
- **Anything about financial methodology.** No formula, no basis, no trust-class
  change; `dashboardGoldens.ts` must stay byte-identical throughout.

## Story list

| Story | Title | Addresses |
|---|---|---|
| US-35.1 | Stop returning an auth failure as if it were missing data | F-1 |
| US-35.2 | Make every cache namespace clearable and inspectable | F-2 |
| US-35.3 | Refuse to overwrite the golden capture with a degraded one | F-3 |

Recommended order: US-35.1 first — it is the one that can mislead a researcher
about their own portfolio. US-35.3 next, because it protects the fixture every
other test depends on. US-35.2 is the smallest and can follow either.

## Success signals

- Running any engine with an unset or wrong `FMP_API_KEY` produces an error that
  names the cause, not a Dashboard full of `unavailable`.
- After fixing a bad key, the next run works — no manual cache clear required.
- `manage_cache.py clear --namespace` can target every namespace `list` prints.
- A capture that collects materially fewer series than the committed fixture
  fails instead of writing.
- `python scripts/run_all_tests.py` stays green and `dashboardGoldens.ts` is
  byte-identical across the whole epic.

# Epic 20 — Market-Data Cache Efficiency & Control

**Status:** Active
**Created:** 2026-06-05

## Problem

Market-data fetching (FMP primary, Yahoo fallback) is cached to a local JSON
file store with per-`(namespace, path, params)` keys and TTLs (quotes 300s,
history/fundamentals 1 day), plus negative caching, in-flight de-duplication,
stale-fallback, and a 250 req/min limiter. Despite this, the same underlying
data is fetched repeatedly and there is no user-facing way to inspect or clear
the cache:

1. **Redundant overlapping fetches.** Each engine computes its own lookback, so
   one symbol's history is requested over many *different but overlapping* date
   ranges (attribution `display+window`, correlation `lookback_days`, drift
   windows, provenance 30d, …). Each distinct `(from,to)` is a separate cache
   key → a separate FMP call for largely the same bars. This is the dominant
   source of FMP overuse.
2. **No in-memory layer.** Every engine builds a fresh `MarketDataService` and
   re-reads/parses JSON files from disk on each call within a single analysis.
3. **Sequential fetches.** `get_historical_prices_for_symbols` fetches one
   symbol at a time — slow for multi-holding portfolios.
4. **No cache observability or control.** Cleaning is CLI-only
   (`scripts/manage_cache.py`); there is no backend `/cache` route and no wired
   UI button.

## Goal

Reduce FMP usage and improve latency by making the **local** cache smarter, and
give the user visibility + control:

- **Inspect & clear** the cache from the UI (stats + a clear button).
- **Stop redundant overlapping fetches** via per-symbol date-range normalization.
- **Speed up** repeated reads (in-memory layer) and multi-symbol fetches (parallel).

## Non-goals

- **No Redis / external cache server.** This is a local-first desktop app; a
  separate server process is operational overhead and does **not** fix the
  redundant-range problem (#1). (A pluggable backend with optional Redis could be
  a *future* epic once the cache interface is abstracted — explicitly out of scope.)
- **No change to provider priority / trust semantics** (FMP→Yahoo fallback,
  provenance) — Epic 18 owns that.
- **No new market data** — purely caching/efficiency/control.
- **No change to TTL policy correctness** beyond what range-normalization needs.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-20.1 | Cache stats + clear (route + UI) | Backend `GET /cache/stats` + `POST /cache/clear`; a small Cache control card on the Exposure tab (entries/size by namespace + a Clear button). Covers FMP + Yahoo namespaces. |
| US-20.2 | History range normalization | `MarketDataService` fetches one widened superset range per symbol and slices to satisfy each engine's `(from,to)`, so overlapping requests share a single FMP call. The big FMP-call reduction. |
| US-20.3 | In-memory layer + parallel fetch | Process-level memo over the file cache; parallelize `get_historical_prices_for_symbols`. The latency win. |

Recommended build order: 20.1 → 20.2 → 20.3. US-20.1 first gives the
clear button (explicitly requested) **and** the stats endpoint, which lets us
*measure* the FMP-call reduction from 20.2/20.3.

## Success signals

- The user can see cache size/entry counts and clear the cache from the UI.
- Re-running a full analysis fetches each symbol's history **once** (not once per
  engine/window) — visible as far fewer cache entries / FMP calls for the same
  portfolio.
- Multi-holding analyses are noticeably faster (in-memory + parallel fetch).
- No new server dependency; the file cache remains the single local store.

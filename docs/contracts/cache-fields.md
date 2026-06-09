# Cache Fields Contract

**Feature:** Market-data cache stats + clear (Epic 20 / US-20.1)
**Backend schema:** `services/quant-engine/app/schemas/cache.py`
**Frontend type:** `apps/desktop/src/features/portfolio/types.ts` — `CacheStats`, `CacheClearResult`
**Routes:** `GET /api/cache/stats`, `POST /api/cache/clear`
**Service:** `services/quant-engine/app/services/cache_admin.py`
**Component:** `apps/desktop/src/features/portfolio/CacheControlCard.tsx`
**Last updated:** 2026-06-05

---

## What this is

Inspect and clear the local JSON file cache shared by the FMP (primary) and
Yahoo (secondary) market-data clients. Pure file operations — no network, no
financial computation, no trust class. It does not change provider behaviour;
it only reports and clears cached files.

---

## `GET /cache/stats` → `CacheStats`

| Field | Backend type | TS type | Notes |
|---|---|---|---|
| `enabled` | `bool` | `boolean` | `fmp_cache_enabled` setting |
| `cache_dir` | `str` | `string` | Absolute cache directory path |
| `total_entries` | `int` | `number` | Total cached files |
| `namespaces` | `list[CacheNamespaceStat]` | `CacheNamespaceStat[]` | Per-namespace counts (sorted) |

### `CacheNamespaceStat`

| Field | Backend type | TS type | Notes |
|---|---|---|---|
| `namespace` | `str` | `string` | e.g. `history`, `quote`, `fundamentals`, `history_yf`, `holdings` |
| `entries` | `int` | `number` | File count in that namespace |

---

## `POST /cache/clear` (`CacheClearRequest`) → `CacheClearResult`

Request:

| Field | Backend type | TS type | Notes |
|---|---|---|---|
| `namespace` | `str \| None` | `string \| null \| undefined` | `null`/omitted clears **all** (FMP + Yahoo); a value clears only that namespace |

Result:

| Field | Backend type | TS type | Notes |
|---|---|---|---|
| `removed` | `int` | `number` | Number of cache files deleted |
| `namespace` | `str \| None` | `string \| null` | Echo of the cleared namespace (null = all) |

Clear semantics follow `JsonFileCache.clear`: `namespace=None` (or `"fmp"`)
removes every file in the cache dir (including `history_yf`); a specific
namespace removes only `<namespace>-*.json`.

---

## UI (`CacheControlCard`, Exposure tab)

- Self-fetches `GET /cache/stats` on mount; shows `total_entries` + per-namespace
  breakdown (or "Cache is empty.").
- "Clear cache" button → `POST /cache/clear` (all), then re-fetches stats and
  shows "Removed N cached files."; failures show an error state (never a silent
  no-op or fabricated count).
- Tokens-only (design-system audit); button has an accessible label +
  `:focus-visible` outline.

The aggregate stats endpoint is also the observability surface used to validate
the FMP-call reduction in US-20.2 / US-20.3.

# Dependency Advisory Assessment — 2026-08

**Story:** US-42.1 — Assess the six outstanding dependency advisories before any version is changed
**Epic:** Epic 42 — Dependency Vulnerability Remediation
**Date:** 2026-08-28
**Status:** Complete. Findings `F-1..F-6` below fold into the Epic 42 PRD at close-out.

This document assesses — without changing any version — the dependency advisories
surfaced by the first real run of the US-36.2 `dependency-audit.yml` scan. It
records, per advisory: identifier(s) and severity, whether the vulnerable code
path is reachable from this repo's actual usage, the minimum non-vulnerable
version, and (backend only) whether a trial bump to that version moves any golden
fixture or analytic output. **No manifest was edited.**
`services/quant-engine/requirements.txt`, `services/quant-engine/requirements-dev.txt`,
`apps/desktop/package.json` and `apps/desktop/package-lock.json` are byte-identical
before and after this assessment (AC9); both upstream lanes confirmed
`git status --porcelain` on those paths is empty.

The `F-n` list is bijective with the six named advisory packages (AC1): `F-1`
starlette, `F-2` pypdf, `F-3` python-multipart, `F-4` pydantic-settings, `F-5`
python-dotenv, `F-6` @babel/core.

## Findings and disposition

| # | Package | Advisory id(s) | Source | Severity | Reachable? | Min safe version | Golden / analytic impact | Bucket |
|---|---|---|---|---|---|---|---|---|
| F-1 | `starlette==0.48.0` | PYSEC-2026-161, PYSEC-2026-248, PYSEC-2026-249, PYSEC-2026-1942, PYSEC-2026-2281, PYSEC-2026-2280 (6 distinct) | live `pip_audit==2.10.1 -r requirements.txt`, 2026-08-28; severity from api.osv.dev CVSS vectors | up to 7.5 High (PYSEC-2026-249, -1942, -2281); PYSEC-2026-161 has no CVSS vector in OSV — **unverified** | No — none of the six vulnerable surfaces are exercised by `services/quant-engine/app/` | `1.3.1` | Could not be assessed — **BLOCKED** (resolver conflict + pytest collection failure) | **(c) blocked** |
| F-2 | `pypdf==6.9.1` | 22 distinct advisories — see § F-2 for the full id list | live `pip_audit==2.10.1 -r requirements.txt`, 2026-08-28; severity from api.osv.dev CVSS vectors | CVSS 3.1 base 3.3–6.5 (Low–Medium) where OSV scores a 3.1 vector; CVSS-4.0-only records carry no comparable base — **unverified**, availability-impact only; no advisory exceeds Medium | Yes — text-extraction + xref-parsing paths; NOT the writer/merge or layout-mode paths | `6.15.0` | No movement observed — 16-file / 437-test sensitive subset identical to the 6.9.1 baseline | **(a) golden-safe** |
| F-3 | `python-multipart==0.0.20` | PYSEC-2026-1852, PYSEC-2026-3038, PYSEC-2026-3039, PYSEC-2026-3037, PYSEC-2026-3036, PYSEC-2026-3040 (6 distinct) | live `pip_audit==2.10.1 -r requirements.txt`, 2026-08-28; severity from api.osv.dev CVSS vectors | up to 8.6 High (PYSEC-2026-1852) | Partial — multipart-parsing DoS surface reachable; `QuerystringParser` and `UPLOAD_DIR` traversal paths not reachable | `0.0.31` | No movement observed — 16-file / 437-test sensitive subset identical to baseline | **(a) golden-safe** |
| F-4 | `pydantic-settings==2.13.1` | GHSA-4xgf-cpjx-pc3j (no CVE alias) | live `pip_audit==2.10.1 -r requirements.txt`, 2026-08-28; severity from api.osv.dev CVSS vector | 5.3 Moderate (OSV CVSS 3.1 base; `database_specific.severity` "MODERATE") | No — vulnerable `NestedSecretsSettingsSource` (`secrets_dir` + `secrets_nested_subdir`) path never constructed | `2.14.2` | No movement observed — 16-file / 437-test sensitive subset identical to baseline | **(a) golden-safe** |
| F-5 | `python-dotenv==1.1.1` | PYSEC-2026-2270 / CVE-2026-28684 / GHSA-mf9w-mj56-hr94 | live `pip_audit==2.10.1 -r requirements.txt`, 2026-08-28; severity from api.osv.dev CVSS vector | 6.6 Medium (OSV CVSS 3.1 base; `AV:L`, `UI:R`) | No — vulnerable `set_key()` / `unset_key()` never invoked, directly or transitively; only the read-only parse is reached via pydantic-settings | `1.2.2` | No movement observed — 16-file / 437-test sensitive subset identical to baseline | **(a) golden-safe** |
| F-6 | `@babel/core` (installed `7.29.0`, transitive) | GHSA-4x5r-pxfx-6jf8 / CVE-2026-49356 | live GitHub Advisory Database REST API + `npm audit`, both 2026-08-28 | low — CVSS 3.1 base 3.2, vector `CVSS:3.1/AV:L/AC:H/PR:N/UI:N/S:C/C:L/I:N/A:N` | Build-time only — Babel executes on first-party source during `vite`/`vitest`, but the vulnerable `sourceMappingURL` path is not reached; **no shipped runtime surface** | `7.29.6` | None — not a backend dependency, does not touch `apps/desktop/src/**` or `apps/desktop/src/test/dashboardGoldens.ts` | **(a) safe** |

### Note on advisory count

The carried US-36.2 § Out of scope list named five backend packages and implied
one advisory each. The live 2026-08-28 `pip-audit` run surfaced **37 advisory
records across the five packages** (22 distinct for pypdf alone). The
one-finding-per-package structure (`F-1..F-5`) still holds, but the story's
one-advisory-per-package framing is inaccurate and is superseded by the live scan.

---

## F-1 — `starlette==0.48.0`

Transcribed from the backend lane assessment (run `08`).

**Advisory ids / severity (AC2).** Six distinct advisories:

| id | aliases | vulnerable behaviour | CVSS 3.1 (OSV) | fix |
|---|---|---|---|---|
| PYSEC-2026-161 | CVE-2026-48710, GHSA-86qp-5c8j-p5mr, X41-2026-002 | `Host` header not validated before `request.url` reconstruction; path prepended into host part | no vector in OSV — **unverified** | 1.0.1 |
| PYSEC-2026-248 | CVE-2026-54282, GHSA-jp82-jpqv-5vv3 | HTTP request path not validated in `request.url` rebuild; authority-boundary shift (`@google.com`) | 5.3 Medium | 1.3.0 |
| PYSEC-2026-249 | CVE-2026-54283, GHSA-82w8-qh3p-5jfq | `request.form()` `max_fields` / `max_part_size` silently ignored for `application/x-www-form-urlencoded` → unauth memory-exhaustion DoS | 7.5 High | 1.3.1 |
| PYSEC-2026-1942 | CVE-2025-62727, GHSA-7f5h-v6xp-fcq8 | crafted `Range` header → quadratic-time `FileResponse` range parse/merge → CPU-exhaustion DoS | 7.5 High | 0.49.1 |
| PYSEC-2026-2281 | CVE-2026-48818, GHSA-wqp7-x3pw-xc5r | `StaticFiles` on Windows: UNC path → `os.path.realpath` outbound SMB → NTLMv2 credential leak (SSRF) | 7.5 High | 1.1.0 |
| PYSEC-2026-2280 | CVE-2026-48817, GHSA-x746-7m8f-x49c | `HTTPEndpoint` picks handler by lowercased method via `getattr`, no verb allowlist | 5.3 Medium | 1.1.0 |

**Min non-vulnerable version (AC4): `1.3.1`.**

**Reachability (AC3): none of the six surfaces are exercised by `services/quant-engine/app/`.**
- `request.url` reconstruction (PYSEC-2026-161, -248): `app/api/main.py` builds a bare `FastAPI()` with only `CORSMiddleware` (origins locked to `localhost:5173` / `127.0.0.1:5173`); no `TrustedHostMiddleware`. grep for `request.url` / `starlette...Request` in `app/` (non-test) returns only Pydantic-model params named `request`. No app code reads the reconstructed URL.
- `request.form()` urlencoded limits (PYSEC-2026-249): the only form route is `POST /portfolios/import/interactive-brokers/analyze-upload` (`app/api/routes/imports.py:71-101`), `multipart/form-data` via `File(...)` / `Form(...)`; no urlencoded parsing, no `max_fields` / `max_part_size` set.
- `FileResponse` Range (PYSEC-2026-1942): no `FileResponse` / `StaticFiles` / file-serving anywhere in `app/`.
- `StaticFiles` SSRF (PYSEC-2026-2281): no `StaticFiles` mount.
- `HTTPEndpoint` verb lookup (PYSEC-2026-2280): every route is a function-style `@router.post`; no `HTTPEndpoint` subclass.
- Posture: localhost-bound, single-user, local-first (F-R8 accepted tradeoff) — no network-exposed attacker path.

**Golden / analytic impact (AC5): could not be assessed — BLOCKED.** In the isolated venv `pip install starlette==1.3.1` reports a resolver conflict (`fastapi 0.119.1 requires starlette<0.49.0,>=0.40.0`). `pytest --co app/tests/test_routes.py` then fails at collection: `TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'` from `fastapi/routing.py` on the first `APIRouter(...)` — every test importing `app.api.main` fails to collect. This is the incompatibility already recorded in `requirements-dev.txt:17-24`. Not "golden moved" — no assertion runs.

**Bucket: (c) blocked.** Min-safe 1.3.1 (and even the single lowest fix, 0.49.1) exceeds FastAPI 0.119.1's `starlette<0.49.0` ceiling. Remediation = bump FastAPI to a release admitting starlette 1.x, then re-run the full golden + route-introspection suite; a story of its own. A FastAPI-bump story must precede any starlette remediation.

---

## F-2 — `pypdf==6.9.1`

Transcribed from the backend lane assessment (run `08`).

**Advisory ids / severity (AC2).** pip-audit reports **22 distinct** advisories, all "attacker crafts a PDF → infinite loop / long runtime / RAM exhaustion" (availability-only; no code-exec, no disclosure). By fix version:

| fix | ids (alias CVE) | vulnerable behaviour |
|---|---|---|
| 6.9.2 | PYSEC-2026-3012 (CVE-2026-33699) | infinite loop reading a file in non-strict mode |
| 6.10.0 | PYSEC-2026-3006 (CVE-2026-40260) | RAM via XMP metadata parse |
| 6.10.1 | PYSEC-2026-3021 (CVE-2026-41168) | runtime via wrong-large `/Size` in xref streams / `/N` in object streams |
| 6.10.2 | PYSEC-2026-3007, -3011, -3026 (CVE-2026-41313/41312/41314) | runtime/RAM via trailer `/Size`, `/FlateDecode` `/Predictor`, image size |
| 6.12.0 | PYSEC-2026-3004, -3016 (CVE-2026-48156/48155) | runtime via `/W [0 0 0]` xref; RAM via layout-mode large char offsets |
| 6.12.1 | PYSEC-2026-3025 (CVE-2026-48735) | RAM via large XMP metadata |
| 6.12.2 | PYSEC-2026-3020, -3010 (CVE-2026-49461/49460) | RAM via form XObject self-reference; runtime via `/FlateDecode` PNG predictor |
| 6.13.0 | PYSEC-2026-3022, -3009 (CVE-2026-54531/54530) | infinite loop merging outlines into a writer; infinite loop extracting text in layout mode |
| 6.13.1 | PYSEC-2026-3018 (CVE-2026-54651) | infinite loop merging threads/articles into a writer |
| 6.13.3 | GHSA-jm82-fx9c-mx94 (no CVE) | `MAX_DECLARED_STREAM_LENGTH` ignored for content stream with no `/Length` |
| 6.14.0 | PYSEC-2026-3610, -3611 (CVE-2026-59937/59938) | runtime via repeated malformed xref streams; RAM via oversized declared image size |
| 6.14.1 | PYSEC-2026-3612 (CVE-2026-59936) | infinite loop, unterminated inline image in content stream |
| 6.14.2 | PYSEC-2026-3613 (CVE-2026-59935) | infinite loop, unterminated inline image, ASCII85/ASCIIHex filters |
| 6.15.0 | PYSEC-2026-3655, -3656 (CVE-2026-71870/71852) | RAM/runtime via oversized `/ToUnicode` and font-width entries during text extraction |

Severity: OSV gives CVSS 3.1 base **3.3–6.5 (Low–Medium)** where it scores a 3.1 vector; the CVSS-4.0-only records carry no comparable base here — **unverified**, characterised only as availability-impact. GHSA-jm82-fx9c-mx94 = OSV `database_specific.severity` "MODERATE". No advisory exceeds Medium. `test_audit_dependencies.py:43`'s `GHSA-xxxx-xxxx-xxxx` is confirmed fixture placeholder — not carried here.

**Min non-vulnerable version (AC4): `6.15.0`.**

**Reachability (AC3): reachable (text-extraction + xref-parsing paths); NOT the writer/merge or layout-mode paths.** pypdf is imported at `app/importers/espp.py:8,30`, `app/importers/freedom24.py:8,55`, `app/importers/interactive_brokers.py:8,75` — each `PdfReader(str(path))` then `[page.extract_text() or "" for page in reader.pages]` (`_extract_text_by_page`). Reached from `POST /portfolios/import/interactive-brokers/analyze-upload` (uploaded bytes → `tempfile.NamedTemporaryFile` → `PdfReader`) and the local-path import routes. So xref parsing, default-mode text extraction, and font / `/ToUnicode` / `/FlateDecode` stream handling are all reachable. NOT reachable: `PdfWriter` / merge paths (PYSEC-2026-3022 outlines, PYSEC-2026-3018 threads/articles — the app never writes or merges) and `extraction_mode="layout"` (PYSEC-2026-3009 layout loop, PYSEC-2026-3016 layout offsets — the app calls plain `extract_text()`). Practical threat: a malformed/hostile broker statement PDF hangs the importer, not RCE.

**Golden / analytic impact (AC5): no movement observed.** Isolated venv, `pip install pypdf==6.15.0` (`pip check` clean), 16-file sensitive subset → **437 passed**, identical to the 6.9.1 baseline. `test_importer.py` alone = 28 passed, 0 skipped — the real IBKR / Freedom24 / ESPP statement PDFs are present in this checkout and their extracted text + parsed positions are unchanged under 6.15.0.

**Bucket: (a) golden-safe.**

---

## F-3 — `python-multipart==0.0.20`

Transcribed from the backend lane assessment (run `08`).

**Advisory ids / severity (AC2).** Six advisories:

| id | alias | vulnerable behaviour | CVSS 3.1 | fix |
|---|---|---|---|---|
| PYSEC-2026-1852 | CVE-2026-24486, GHSA-wp53-j4wj-2cfg | path traversal when `UPLOAD_DIR` set + `UPLOAD_KEEP_FILENAME=True`; crafted filename writes anywhere | 8.6 High | 0.0.22 |
| PYSEC-2026-3038 | CVE-2026-40347 | DoS via large multipart preamble/epilogue | 5.3 Medium | 0.0.26 |
| PYSEC-2026-3039 | CVE-2026-42561 | DoS: no limit on count/size of part headers | 7.5 High | 0.0.27 |
| PYSEC-2026-3037 | CVE-2026-53538 | `QuerystringParser` treats `;` as separator in urlencoded bodies | 3.7 Low | 0.0.30 |
| PYSEC-2026-3036 | CVE-2026-53539 | quadratic separator lookup in `QuerystringParser` for `;`-separated bodies | 7.5 High | 0.0.30 |
| PYSEC-2026-3040 | CVE-2026-53540 | `parse_form()` doesn't validate `Content-Length`; negative → read-until-EOF, whole body one read | 3.7 Low | 0.0.31 |

**Min non-vulnerable version (AC4): `0.0.31`.**

**Reachability (AC3): multipart-parsing DoS surface reachable; querystring + UPLOAD_DIR paths not.** python-multipart is pulled by FastAPI for `multipart/form-data`. Single consumer: `POST /portfolios/import/interactive-brokers/analyze-upload` (`app/api/routes/imports.py:71-101`) — the only `File(...)` / `Form(...)` route. So `MultipartParser` (part-header DoS PYSEC-2026-3039, preamble/epilogue PYSEC-2026-3038) is reachable. NOT reachable: `QuerystringParser` (PYSEC-2026-3037, -3036 — no urlencoded form route in the app) and the `UPLOAD_DIR` / `UPLOAD_KEEP_FILENAME` traversal (PYSEC-2026-1852 — legacy `python_multipart` options the app never sets; FastAPI spools to its own temp file and the route writes via `tempfile.NamedTemporaryFile`). Same localhost-bound single-user posture as F-1 — reachable only by the local user's own upload.

**Golden / analytic impact (AC5): no movement observed.** Isolated venv, `pip install python-multipart==0.0.31`, 16-file subset → **437 passed**, identical to baseline.

**Bucket: (a) golden-safe.**

---

## F-4 — `pydantic-settings==2.13.1`

Transcribed from the backend lane assessment (run `08`).

**Advisory id / severity (AC2).** One advisory:
- **GHSA-4xgf-cpjx-pc3j** (no CVE alias). `NestedSecretsSettingsSource`: with `secrets_nested_subdir=True`, a symlink inside `secrets_dir` pointing outside it is followed, reading external files into settings values. OSV CVSS 3.1 base **5.3**, `database_specific.severity` "MODERATE", CWE-22 / 400 / 59. Fix **2.14.2**.

**Min non-vulnerable version (AC4): `2.14.2`.**

**Reachability (AC3): not reachable.** Used only at `app/core/settings.py:6,29` — `class Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`, built once via `get_settings()` (`@lru_cache`). The vulnerable feature is `secrets_dir` + `secrets_nested_subdir` (`NestedSecretsSettingsSource`). The app sets neither — only `env_file`. That code path is never constructed.

**Golden / analytic impact (AC5): no movement observed.** Isolated venv, `pip install pydantic-settings==2.14.2` (pydantic core stayed `2.12.3`, `pip check` clean), 16-file subset → **437 passed**, identical to baseline.

**Bucket: (a) golden-safe.**

---

## F-5 — `python-dotenv==1.1.1`

Transcribed from the backend lane assessment (run `08`).

**Advisory id / severity (AC2).** One advisory:
- **PYSEC-2026-2270** / CVE-2026-28684 / GHSA-mf9w-mj56-hr94. `set_key()` and `unset_key()` follow symlinks when rewriting a `.env` file; a local attacker can overwrite an arbitrary file via a crafted symlink when a cross-device rename falls back to copy. OSV CVSS 3.1 base **6.6 Medium** (`AV:L`, local; `UI:R`). Fix **1.2.2**.

**Min non-vulnerable version (AC4): `1.2.2`.**

**Reachability (AC3): not reachable.** No `import dotenv` / `from dotenv` / `load_dotenv` / `set_key` / `unset_key` anywhere in `services/quant-engine/app/` (grep — the only `unset_key` hit is an unrelated FMP-cache test name). python-dotenv is reached transitively only, via pydantic-settings' `env_file=".env"` handling, which calls the read-only parse (`dotenv_values()`). The vulnerable write functions `set_key()` / `unset_key()` are never invoked, directly or transitively. Startup-only, local `.env`.

**Golden / analytic impact (AC5): no movement observed.** Isolated venv, `pip install python-dotenv==1.2.2`, 16-file subset → **437 passed**, identical to baseline.

**Bucket: (a) golden-safe.**

---

## F-6 — `@babel/core`

Transcribed from the frontend lane assessment (run `09`).

### Package and dependency path

- **Package:** `@babel/core`
- **Installed version:** `7.29.0` (`apps/desktop/package-lock.json` → `node_modules/@babel/core`, `"version": "7.29.0"`, `"dev": true`; single install, one lockfile node, no duplicate copies).
- **Transitive — confirmed.** Not present in `apps/desktop/package.json` (neither `dependencies` nor `devDependencies`). Dependency path:
  - `apps/desktop` (root) → `devDependencies` → `@vitejs/plugin-react` `^4.3.4` (resolved `4.7.0`)
  - `@vitejs/plugin-react@4.7.0` → `dependencies` → `@babel/core` `^7.28.0` (resolved `7.29.0`)
- `@vitejs/plugin-react` is the only package that declares `@babel/core` as a real dependency. Three sibling `@babel/*` packages declare it as a *peer* only — `@babel/helper-module-transforms` (`^7.0.0`), `@babel/plugin-transform-react-jsx-self` (`^7.0.0-0`), `@babel/plugin-transform-react-jsx-source` (`^7.0.0-0`) — all pulled by the same `@vitejs/plugin-react`.
- `vite.config.ts` uses `react()` as its sole plugin (the Babel-based `@vitejs/plugin-react`, not `@vitejs/plugin-react-swc`), and vitest reuses the same `vite.config.ts` via its `test` key.

### AC2 — Advisory id and severity

- **Advisory:** `GHSA-4x5r-pxfx-6jf8` — CVE `CVE-2026-49356`
- **Title:** "@babel/core: Arbitrary File Read via sourceMappingURL Comment"
- **Severity:** low. CVSS 3.1 base score **3.2**, vector `CVSS:3.1/AV:L/AC:H/PR:N/UI:N/S:C/C:L/I:N/A:N`. CWE-22 (path traversal), CWE-200 (information exposure).
- **Published:** 2026-06-15.
- **Affected / patched ranges (from the GitHub Advisory DB):**
  - 7.x line: vulnerable `<= 7.29.0`; **first patched version `7.29.6`**.
  - 8.x pre-release line: vulnerable `>= 8.0.0-alpha.0, < 8.0.0-rc.5`; patched `8.0.0-rc.6` (not relevant — this repo is on the 7.x line).
- The installed `7.29.0` is inside the affected range.

### AC3 / AC10 — Reachability

**Build-time execution: yes.** `@vitejs/plugin-react` invokes `@babel/core` on this repo's own first-party `apps/desktop/src/**` `.ts`/`.tsx` source during `vite dev`, `vite build`, and `vitest run` (React Fast Refresh transform + automatic JSX runtime). So `@babel/core` code does execute inside this repo's Node toolchain.

**Vulnerable-path reachability: not reached from normal usage — reasoning, not a bare "no".** The CVE triggers when Babel compiles source *text* that contains a crafted `//# sourceMappingURL=<path>` comment while input-source-map reading is active; Babel then reads that referenced file from disk and can leak its bytes into the generated source map (arbitrary file read). In this repo Babel is fed only version-controlled, developer-authored source; `@vitejs/plugin-react` excludes `node_modules`, so no third-party or attacker-controlled source text is compiled. Exploitation additionally requires local access (`AV:L`), has high attack complexity (`AC:H`), and needs a malicious `sourceMappingURL` comment introduced into the source tree — which already implies commit or build-host access, a strictly larger capability than the file read it would grant. The trusted-input boundary plus the local-only, high-complexity vector is why the path is not considered reachable here.

**Shipped runtime surface: none.** `@babel/core` is a Node build-time tool. The compiled browser bundle (`apps/desktop/dist/`) contains no Babel code (`grep -rc "@babel/core\|sourceMappingURL" dist/` → no matches), and the Tauri desktop app ships that bundle. Nothing Babel touches reaches an end user's machine at runtime.

### AC4 — Minimum safe version and lockfile-only resolution

- **Minimum non-vulnerable version:** `7.29.6` (GitHub Advisory DB `first_patched_version` for the 7.x line). `npm audit fix` targets `7.29.7` (the latest 7.x patch; versions available after 7.29.0 are 7.29.6, 7.29.7, then 8.x). Either resolves the advisory.
- **A lockfile-only resolution exists — confirmed.** Both `7.29.6` and `7.29.7` satisfy `@vitejs/plugin-react@4.7.0`'s `@babel/core: ^7.28.0` range, so re-resolving the transitive dependency needs **no `package.json` change, no `overrides` entry, and no toolchain (Vite / `@vitejs/plugin-react`) bump**.
  - `npm audit --json` reports `"fixAvailable": true` (boolean, not an object) for `@babel/core` — npm classifies it as a non-breaking, in-range fix.
  - `npm audit fix --dry-run --json` (run read-only) reports `change @babel/core 7.29.0 => 7.29.7` (plus its `@babel/*` sub-tree), i.e. `package-lock.json`-only.
  - **Scoped command for the remediation story:** `npm install @babel/core@7.29.7 --package-lock-only` (or `npm update @babel/core`) keeps the lockfile diff to the `@babel/*` subtree. A bare `npm audit fix` would additionally rewrite unrelated subtrees (postcss, nanoid, ws, browserslist data) and add knip's transitive tree — those belong to other advisories, not F-6.

### AC7 — Bucket assignment

**Bucket (a) — safe.** Build-time-only dev dependency with no analytic and no shipped-runtime surface. The fix is a lockfile-only patch bump (`7.29.0` → `7.29.6`/`7.29.7`) inside the existing `^7.28.0` range. It is not a backend dependency, so it cannot move a backend golden; it does not touch `apps/desktop/src/**` or `apps/desktop/src/test/dashboardGoldens.ts`, so it cannot move a frontend golden. The only post-bump check is that `npx vitest run`, `npx tsc --noEmit`, and `designSystem.audit.test.ts` stay green — a plain CI check, not a quant audit. Not bucket (b) (no analytic output — Babel is a JSX/TS transform, not finance math). Not bucket (c) (a fixed version exists and is reachable without a coordinated toolchain bump).

---

## Remediation grouping (AC7)

All six findings placed into exactly three buckets. Every one of `F-1..F-6`
appears in exactly one bucket.

### (a) golden-safe — a plain remediation story / ticket, no quant-audit

- **F-2** pypdf `6.9.1 → 6.15.0`
- **F-3** python-multipart `0.0.20 → 0.0.31`
- **F-4** pydantic-settings `2.13.1 → 2.14.2`
- **F-5** python-dotenv `1.1.1 → 1.2.2`
- **F-6** @babel/core `7.29.0 → 7.29.6` (min-safe; lockfile-only, `apps/desktop`)

For F-2..F-5 the trial bump — one package at a time in an isolated out-of-repo
venv, sensitive subset of 16 test files / 437 tests (goldens + route inventory +
analytics + all engine tests + importer tests) — was byte-identical to the
baseline in every case. F-6 is not a backend dependency and touches no golden.

### (b) may move analytic output — must route through quant-audit, named individually

- **none.** No assessable backend bump moved any golden or analytic output
  anywhere. Per the DESIGN § Risks guardrail-1 carry-forward: there is nothing to
  carry — the trial bumps moved zero goldens and zero analytic outputs, so no
  F-2..F-5 remediation inherits a quant-audit requirement.

### (c) blocked — with the blocking reason

- **F-1** starlette `0.48.0 → 1.3.1`. FastAPI 0.119.1 pins `starlette<0.49.0`;
  the lowest single-advisory fix (0.49.1, PYSEC-2026-1942) already breaches that,
  and min-safe 1.3.1 breaks pytest collection
  (`Router.__init__() got an unexpected keyword argument 'on_startup'`,
  reproduced in the isolated venv). **Blocking reason:** needs a coordinated
  FastAPI upgrade to a release admitting starlette 1.x, then a full golden +
  route-introspection re-run (the `requirements.txt` header calls that path
  FastAPI/Pydantic-internals-sensitive). A FastAPI-bump story must precede any
  starlette remediation.

---

## Advisory-data provenance (AC6)

This assessment ran on the **live** path — network was available on 2026-08-28 —
**not** the offline degrade path the story anticipated.

### Backend (`F-1..F-5`)

- **Advisory set, ids, affected/fixed ranges:** live
  `python -m pip_audit==2.10.1 -r services/quant-engine/requirements.txt --format json`,
  run 2026-08-28 with PyPI reachable (`urllib` GET `pypi.org` returned 200;
  `audit_dependencies.classify()` would return `VULNERABILITIES_FOUND`). Backing
  DB: PyPI Advisory DB / OSV. This supersedes the carried US-36.2 list, which
  named the five packages but carried no ids and implied one advisory each
  (actual: 37 records, 22 distinct for pypdf).
- **Severity:** `https://api.osv.dev/v1/vulns/<id>` `severity` field (CVSS
  vectors), fetched 2026-08-28; qualitative band computed from the CVSS 3.1 base
  score. **Unverified:** any advisory where OSV carries only a CVSS 4.0 vector
  (all such are availability-only, `VA:H` / `VA:L`) or no vector at all
  (PYSEC-2026-161) — no qualitative band is asserted for those beyond
  "availability impact". pip-audit itself emits no severity.
- **Reachability:** static import-graph read of `services/quant-engine/app/` at
  working-tree HEAD — no network. Call sites cited by `file:line`; absence
  confirmed by `grep` over `app/` excluding `tests/`.
- **Golden / analytic impact:** trial bumps in a throwaway venv **outside the
  repo**, one candidate at a time, `pip install -r requirements.txt` baseline
  restored between each. Sensitive subset (16 files): `test_golden_market_data_basis`,
  `test_golden_pipeline_determinism`, `test_route_inventory`,
  `test_architecture_doc_route_inventory`, `test_routes`, `test_analytics`,
  `test_engine_response_integrity`, `test_distribution_engine`,
  `test_drawdown_engine`, `test_stress_engine`, `test_correlation_engine`,
  `test_drift_engine`, `test_exposure_engine`, `test_importer`,
  `test_importer_csv`, `test_import_admission`. This is a subset, **not the full
  suite** — a bump that moves an output covered only by an excluded test would
  not have been caught; the subset covers every golden, route-inventory,
  analytics and importer test. `requirements.txt` / `requirements-dev.txt` never
  edited — `git status --porcelain` on both is empty (AC9).
- **Not researched (out of scope):** the specific FastAPI version that first
  admits starlette 1.x — the F-1 "no compatible bump" conclusion rests on the
  observed resolver conflict + collection failure, not a survey of FastAPI
  releases.

### Frontend (`F-6`)

- Advisory id, CVE, title, severity, CVSS vector/score, publish date, and
  affected/patched ranges: **live query of the GitHub Advisory Database REST
  API** (`GET https://api.github.com/advisories/GHSA-4x5r-pxfx-6jf8`) on
  2026-08-28.
- Cross-checked against **`npm audit --json`** run in `apps/desktop` the same
  session — npm registry advisory source `1123528`, same `GHSA-4x5r-pxfx-6jf8`,
  same `<= 7.29.0` range, severity `low`, CVSS 3.2. The two sources agree.
- Installed version and dependency path: read directly from
  `apps/desktop/package-lock.json` at HEAD.
- Network was available; **no field in `F-6` is unverified.**
- `npm audit` and `npm audit fix --dry-run` were run read-only.
  `git status --porcelain apps/desktop/package.json apps/desktop/package-lock.json`
  is empty afterwards — manifests byte-identical (AC9).

### Carried-forward unverified items

- **F-1 / PYSEC-2026-161** — no CVSS vector in OSV; severity band not asserted.
- **F-2 / pypdf** — advisory records scored only with a CVSS 4.0 vector (and
  those with no vector) carry no CVSS 3.1 base here; characterised only as
  availability-impact, no qualitative band asserted.
- **Advisory count** — 37 pip-audit records across the five backend packages
  vs. the "five advisories" the carried US-36.2 list implied; the
  one-advisory-per-package framing is inaccurate.
- **AC5 trial-bump scope** — 16-file / 437-test sensitive subset, not the full
  suite.

---

## PRD fold-in list (AC8)

For the Epic 42 PRD `### Findings and disposition` table — each finding carries
id, source, and disposition:

| # | Package | Advisory id(s) | Source | Disposition |
|---|---|---|---|---|
| F-1 | `starlette` | PYSEC-2026-161/-248/-249/-1942/-2281/-2280 | live `pip_audit==2.10.1`, 2026-08-28 | **Bucket (c) blocked** — min-safe 1.3.1 breaches FastAPI 0.119.1's `starlette<0.49.0` pin; needs a FastAPI-bump story first. Not reachable in this repo's usage. |
| F-2 | `pypdf` | 22 distinct (see § F-2) | live `pip_audit==2.10.1`, 2026-08-28 | **Bucket (a) golden-safe** — bump `6.9.1 → 6.15.0`; trial bump moved zero goldens. Text-extraction/xref paths reachable. |
| F-3 | `python-multipart` | PYSEC-2026-1852/-3038/-3039/-3037/-3036/-3040 | live `pip_audit==2.10.1`, 2026-08-28 | **Bucket (a) golden-safe** — bump `0.0.20 → 0.0.31`; trial bump moved zero goldens. Multipart-parse DoS surface reachable. |
| F-4 | `pydantic-settings` | GHSA-4xgf-cpjx-pc3j | live `pip_audit==2.10.1`, 2026-08-28 | **Bucket (a) golden-safe** — bump `2.13.1 → 2.14.2`; trial bump moved zero goldens. Vulnerable secrets-dir path not reachable. |
| F-5 | `python-dotenv` | PYSEC-2026-2270 / CVE-2026-28684 | live `pip_audit==2.10.1`, 2026-08-28 | **Bucket (a) golden-safe** — bump `1.1.1 → 1.2.2`; trial bump moved zero goldens. Vulnerable write functions not reachable. |
| F-6 | `@babel/core` | GHSA-4x5r-pxfx-6jf8 / CVE-2026-49356 | live GitHub Advisory DB REST API + `npm audit`, 2026-08-28 | **Bucket (a) safe** — lockfile-only bump `7.29.0 → 7.29.6` in `apps/desktop`; build-time only, no shipped runtime surface, no golden. |

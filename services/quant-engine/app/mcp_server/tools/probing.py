"""Probing one engine route in-process, for agents.

This replaces the throwaway probe script. Instead of writing a one-off module
into scratchpad to build a snapshot, patch market data and call an engine, a
lane calls `probe_engine` and gets the route's JSON response back.

Everything delegates to `app/tests/fixtures.py`. No fixture logic is
reimplemented here -- if the canonical snapshot shape changes, this follows.
"""

from __future__ import annotations

import importlib
import inspect
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator
from unittest import mock

from app.tests.fixtures import imported_snapshot, install_market_data_mock, position

# F-2: long arrays in a probe body are bounded head/tail with a single sentinel
# dict standing in for the dropped middle. The route still returned every
# element -- the tool is what truncated the copy handed back.
PROBE_ARRAY_HEAD = 5
PROBE_ARRAY_TAIL = 5
_MAX_TRAVERSAL_DEPTH = 20


class _Patcher:
    """Supplies the single method `install_market_data_mock` needs from pytest-mock.

    That fixture takes a `mocker` and calls `mocker.patch(target, new)`. Outside
    a pytest session there is no `mocker`, so rather than duplicating the fixture
    for non-pytest callers we hand it an adapter backed by `unittest.mock` and
    unwind the patches ourselves.
    """

    def __init__(self) -> None:
        self._started: list[Any] = []

    def patch(self, target: str, new: Any) -> Any:
        patcher = mock.patch(target, new)
        patcher.start()
        self._started.append(patcher)
        return new

    def stop_all(self) -> None:
        for patcher in reversed(self._started):
            patcher.stop()
        self._started.clear()


@contextmanager
def _market_data(
    engine_module: str,
    histories: dict[str, list[dict]] | None,
    default_rows: list[dict] | None,
    vendor_by_symbol: dict[str, str] | None,
) -> Iterator[Any]:
    patcher = _Patcher()
    try:
        yield install_market_data_mock(
            patcher,
            engine_module,
            histories=histories,
            default_rows=default_rows,
            vendor_by_symbol=vendor_by_symbol,
        )
    finally:
        patcher.stop_all()


def engine_module_for(route: str) -> str | None:
    """Derive the module to patch from the route.

    Every engine router is mounted at `/engines/<name>` and its service module is
    `app.services.<name>_engine` (hyphens become underscores). Derived rather than
    table-driven so a new engine works without touching this file.

    Returns None for non-engine routes (imports, cache, market-data, health),
    which do not read market data through an engine module.
    """
    parts = [p for p in route.split("/") if p]
    if len(parts) >= 2 and parts[0] == "engines":
        return f"app.services.{parts[1].replace('-', '_')}_engine"
    return None


def _request_model_for(app: Any, route: str) -> Any:
    """Recover the Pydantic model bound to `route`'s POST body, or None.

    Reads it off the live app's `APIRoute.body_field` -- every engine route has
    exactly one body param and no `embed=True`, so `type_` is the un-wrapped
    model class. Three-step fallback (04 § 2a); no route match / no body field /
    all steps fail -> None, which the caller treats as "unclassified" (never a
    guess).
    """
    from fastapi.routing import APIRoute

    for r in app.routes:
        if isinstance(r, APIRoute) and r.path == route and "POST" in r.methods:
            bf = getattr(r, "body_field", None)
            if bf is None:
                return None
            dependant = getattr(r, "dependant", None)
            body_params = getattr(dependant, "body_params", None) or []
            return (
                getattr(bf, "type_", None)
                or getattr(getattr(bf, "field_info", None), "annotation", None)
                or (body_params[0].type_ if body_params else None)
            )
    return None


def _shape_of(model: Any) -> str:
    """Map a bound request model to its payload shape (04 § 2b).

    `flat` -> snapshot fields at the top level; `snapshot-wrapped` -> body under a
    `snapshot` key; `bare-snapshot` -> the body IS the snapshot; `unclassified`
    -> no model, or a model matching none of the above (disclosed, not guessed).
    """
    from app.schemas.imports import ImportedPortfolioSnapshot
    from app.schemas.portfolio_engine import PortfolioEngineRequest

    if inspect.isclass(model):
        if issubclass(model, PortfolioEngineRequest):
            return "flat"
        if model is ImportedPortfolioSnapshot:
            return "bare-snapshot"
        field = getattr(model, "model_fields", {}).get("snapshot")
        if field is not None and field.annotation is ImportedPortfolioSnapshot:
            return "snapshot-wrapped"
    return "unclassified"


def _shape_mismatch(request_shape: str, payload: Any) -> dict[str, str] | None:
    """Warn (never raise) when the supplied payload contradicts `request_shape`.

    Keyed on one structural fact: does the payload dict carry a top-level
    `snapshot` key? Flat vs bare-snapshot is deliberately not disambiguated on
    the supplied side -- both put snapshot fields at the top level. `None` when
    consistent, unclassified, or the payload is not a dict (04 § 2c).
    """
    if request_shape == "unclassified" or not isinstance(payload, dict):
        return None
    has_snapshot_key = "snapshot" in payload
    if request_shape in ("flat", "bare-snapshot") and has_snapshot_key:
        expects = "a flat body" if request_shape == "flat" else "a bare snapshot body"
        return {
            "expected": request_shape,
            "supplied": "snapshot-wrapped",
            "note": f"payload has a top-level 'snapshot' key but the route expects {expects}",
        }
    if request_shape == "snapshot-wrapped" and not has_snapshot_key:
        return {
            "expected": "snapshot-wrapped",
            "supplied": "flat-or-bare",
            "note": (
                "route expects the body wrapped under 'snapshot' but the payload "
                "has snapshot fields at the top level"
            ),
        }
    return None


def _trust_downgrade(body: Any) -> dict[str, str] | None:
    """Return the top-level trust keys holding literal `"unavailable"`, or None.

    Depth-1 scan only: a key named exactly `trust` or ending `_trust` whose value
    is the string `"unavailable"` means the engine answered nothing, so `ok` is
    narrowed (04 § 1d). `verified` / `degraded` / `withheld` / `synthetic` and any
    nested per-row trust do NOT downgrade.
    """
    if not isinstance(body, dict):
        return None
    hits = {
        key: value
        for key, value in body.items()
        if (key == "trust" or key.endswith("_trust")) and value == "unavailable"
    }
    return hits or None


def _apply_fields(
    body: Any, fields: list[str]
) -> tuple[Any, list[str] | None, int | None]:
    """Filter a dict body to `fields` (top-level keys only), always keeping trust.

    No dotted paths, no nested selection. Every top-level `trust` / `*_trust` key
    is retained even if unlisted, so `ok` / `ok_downgraded_by` stay explainable
    (04 § 3). A non-dict body is returned untouched with null counters.
    """
    if not isinstance(body, dict):
        return body, None, None
    kept = {key: body[key] for key in fields if key in body}
    for key, value in body.items():
        if key == "trust" or key.endswith("_trust"):
            kept[key] = value
    return kept, sorted(kept), len(body) - len(kept)


def _bound_arrays(
    obj: Any, path: str = "", depth: int = 0
) -> tuple[Any, list[str]]:
    """Recursively bound every over-long list to head + sentinel + tail (04 § 5).

    Any list longer than HEAD + TAIL + 1 keeps its first HEAD and last TAIL
    elements with one `{"__probe_truncated__": {...}}` dict inserted between them;
    it stays a list, order preserved. Empty lists and short lists pass through
    untouched. Returns the rewritten object and the dotted paths of every list
    that was bounded. Traversal past `_MAX_TRAVERSAL_DEPTH` is left as-is.
    """
    truncated: list[str] = []
    if depth > _MAX_TRAVERSAL_DEPTH:
        return obj, truncated

    if isinstance(obj, dict):
        rebuilt = {}
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else str(key)
            new_value, child_trunc = _bound_arrays(value, child_path, depth + 1)
            rebuilt[key] = new_value
            truncated.extend(child_trunc)
        return rebuilt, truncated

    if isinstance(obj, list):
        count = len(obj)
        over_limit = count > PROBE_ARRAY_HEAD + PROBE_ARRAY_TAIL + 1
        keep_indices = (
            list(range(PROBE_ARRAY_HEAD))
            + list(range(count - PROBE_ARRAY_TAIL, count))
            if over_limit
            else range(count)
        )
        rebuilt_by_index: dict[int, Any] = {}
        for index in keep_indices:
            child_path = f"{path}.{index}" if path else str(index)
            new_value, child_trunc = _bound_arrays(obj[index], child_path, depth + 1)
            rebuilt_by_index[index] = new_value
            truncated.extend(child_trunc)
        if not over_limit:
            return [rebuilt_by_index[i] for i in range(count)], truncated
        head = [rebuilt_by_index[i] for i in range(PROBE_ARRAY_HEAD)]
        tail = [rebuilt_by_index[i] for i in range(count - PROBE_ARRAY_TAIL, count)]
        sentinel = {
            "__probe_truncated__": {
                "original_count": count,
                "dropped": count - PROBE_ARRAY_HEAD - PROBE_ARRAY_TAIL,
                "kept_head": PROBE_ARRAY_HEAD,
                "kept_tail": PROBE_ARRAY_TAIL,
                "note": (
                    "probe_engine truncated this array; the route returned all elements"
                ),
            }
        }
        truncated.append(path or "(root)")
        return head + [sentinel] + tail, truncated

    return obj, truncated


def _refusal(route: str) -> dict[str, Any]:
    """Structured refusal for a non-derivable route probed without `allow_unmocked`.

    Not a raise -- a return the caller can inspect. `reason` names the flag that
    unblocks it (04 § 1b).
    """
    return {
        "status": None,
        "ok": False,
        "engine_module": None,
        "mocked": False,
        "unmocked": False,
        "refused": True,
        "reason": (
            f"route '{route}' has no derivable engine module and would run live "
            "against real market data; pass allow_unmocked=True to run it "
            "without a market-data mock"
        ),
        "request_shape": "unclassified",
        "request_model": None,
        "shape_mismatch": None,
        "ok_downgraded_by": None,
        "truncation": [],
        "fields_kept": None,
        "fields_omitted_count": None,
        "body": None,
    }


def build_snapshot_impl(
    positions: list[dict] | None = None,
    instruments: list[dict] | None = None,
    cash_balances: list[dict] | None = None,
    ledger_entries: list[dict] | None = None,
    statement_overrides: dict | None = None,
) -> dict[str, Any]:
    """Build a 422-proof ImportedPortfolioSnapshot payload.

    Position entries may be shorthand (`{"symbol": "AAPL", "market_value": 500}`)
    -- anything carrying a `symbol` is routed through the canonical `position()`
    builder, so unspecified required fields get their defaults.
    """
    built = [
        position(**entry) if isinstance(entry, dict) and "symbol" in entry else entry
        for entry in (positions or [])
    ]
    return imported_snapshot(
        positions=built,
        instruments=instruments,
        cash_balances=cash_balances,
        ledger_entries=ledger_entries,
        statement_overrides=statement_overrides,
    )


def probe_engine_impl(
    route: str,
    payload: dict,
    histories: dict[str, list[dict]] | None = None,
    default_rows: list[dict] | None = None,
    vendor_by_symbol: dict[str, str] | None = None,
    engine_module: str | None = None,
    fields: list[str] | None = None,
    allow_unmocked: bool = False,
) -> dict[str, Any]:
    """POST one engine route in-process with `MarketDataService` mocked.

    NOTE: pytest.ini's `--disable-socket` guard does NOT apply here -- there is
    no pytest session. The mock installed from the derived `engine_module` is
    what keeps this offline, which is why the derivation exists. A route whose
    module cannot be derived is REFUSED unless `allow_unmocked=True` is passed;
    a typo'd route segment or explicit `engine_module` still raises loudly.

    conftest.py's autouse fixtures do not apply either: anything the route needs
    must be passed in explicitly.
    """
    from fastapi.testclient import TestClient

    from app.api.main import app

    target = engine_module or engine_module_for(route)

    if target:
        # Any typo -- route segment OR explicit engine_module -- lands here and
        # raises ModuleNotFoundError naming the module, unconditionally, before
        # any context is entered.
        importlib.import_module(target)
        context: Any = _market_data(target, histories, default_rows, vendor_by_symbol)
        mocked, unmocked = True, False
    else:
        if not allow_unmocked:
            return _refusal(route)
        context = nullcontext()
        mocked, unmocked = False, True

    model = None if unmocked else _request_model_for(app, route)
    request_shape = _shape_of(model)
    request_model = model.__name__ if inspect.isclass(model) else None
    shape_mismatch = _shape_mismatch(request_shape, payload)

    with context:
        with TestClient(app) as client:
            response = client.post(route, json=payload)

    content_type = response.headers.get("content-type", "")
    is_json = content_type.startswith("application/json")
    body: Any = response.json() if is_json else response.text

    truncation: list[str] = []
    fields_kept: list[str] | None = None
    fields_omitted_count: int | None = None
    if is_json:
        if fields is not None:
            body, fields_kept, fields_omitted_count = _apply_fields(body, fields)
        body, truncation = _bound_arrays(body)

    ok = response.status_code < 400
    ok_downgraded_by = _trust_downgrade(body) if is_json else None
    if ok_downgraded_by:
        ok = False

    return {
        "status": response.status_code,
        "ok": ok,
        "engine_module": target,
        "mocked": mocked,
        "unmocked": unmocked,
        "refused": False,
        "request_shape": request_shape,
        "request_model": request_model,
        "shape_mismatch": shape_mismatch,
        "ok_downgraded_by": ok_downgraded_by,
        "truncation": truncation,
        "fields_kept": fields_kept,
        "fields_omitted_count": fields_omitted_count,
        "body": body,
    }

"""Vulture allowlist — names that are USED dynamically and must not be reported
as dead (Epic 23 / US-23.1).

Vulture is static and cannot see dynamic/reflective use. Every entry below is a
genuine false positive with a one-line reason; this file is passed to vulture so
the names count as referenced:

    vulture app vulture_allowlist.py --min-confidence 80

Keep this list HONEST — each entry must name why the symbol is dynamically used.
US-23.8 promotes vulture to a zero-findings gate; an unreasoned allowlist entry
would silently re-open the door, so additions require a reason here.
"""
# Pydantic model hooks — invoked by the framework, never called directly.
_dynamic_context = None
_dynamic_context.__context  # `model_post_init(self, __context)` hook parameter

# NOTE: pytest fixtures (autouse fixtures in conftest.py: _clear_cache_memory,
# _disable_yfinance_fallback, _mock_*_engine_market_data, _check_dashboard_goldens_freshness),
# `field_validator`/`model_validator` methods, and FastAPI route handler functions
# are all invoked by injection/registration. They are kept below the
# `--min-confidence 80` threshold in practice; if a future vulture version raises
# their confidence, add them here with a reason rather than lowering confidence.

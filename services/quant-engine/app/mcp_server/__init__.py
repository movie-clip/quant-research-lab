"""MCP tool server exposing this repo's test, gate and probe workflows to agents.

Layout rationale: this package lives under `app/` (rather than a new top-level
`services/mcp-server/`) so that ruff, vulture and pytest already reach it --
`scripts/detect_deadcode.py` scans `app`, and `pytest.ini` roots here. A server
outside that tree would pass every mechanical gate while being covered by none.

Named `mcp_server` rather than `mcp` to avoid any ambiguity with the top-level
`mcp` SDK package that `server.py` imports.
"""

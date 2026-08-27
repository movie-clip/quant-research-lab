"""Tool implementations.

Every public function here is a plain `*_impl` callable with no MCP dependency,
so `app/tests/test_mcp_tools.py` can exercise it directly. `server.py` holds the
`@server.tool()` wrappers and nothing else.
"""

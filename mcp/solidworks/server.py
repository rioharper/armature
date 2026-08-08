# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp[cli]>=2,<3", "pywin32; sys_platform == 'win32'"]
# ///
"""Armature SolidWorks MCP — verification-first, name-addressed. Spec:
docs/superpowers/specs/2026-08-08-solidworks-mcp-design.md"""
from mcp.server import MCPServer
import sw

mcp = MCPServer("solidworks")


@mcp.tool()
def sw_status() -> dict:
    """SolidWorks version, open documents, and active document. Call first."""
    return sw.status(sw.attach())


@mcp.tool()
def sw_open(path: str) -> dict:
    """Open a part/assembly/drawing by absolute path, or activate it if already open."""
    return sw.open_doc(sw.attach(), path)


@mcp.tool()
def sw_get_params(doc: str) -> dict:
    """All global variables/equations of the named open document (values in document units)."""
    app = sw.attach()
    return sw.get_params(sw.resolve_doc(app, doc))


@mcp.tool()
def sw_set_params(doc: str, values: dict[str, float]) -> dict:
    """Set existing global variables (document units), rebuild, return new values. Never creates variables."""
    app = sw.attach()
    return sw.set_params(sw.resolve_doc(app, doc), values)


@mcp.tool()
def sw_rebuild(doc: str) -> dict:
    """Force-rebuild the named document; returns features in error/warning state (empty list = clean)."""
    app = sw.attach()
    return sw.rebuild(sw.resolve_doc(app, doc))


if __name__ == "__main__":
    mcp.run()

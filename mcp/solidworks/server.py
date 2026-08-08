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


if __name__ == "__main__":
    mcp.run()

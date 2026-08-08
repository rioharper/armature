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


@mcp.tool()
def sw_mass_properties(doc: str, coord_system: str | None = None) -> dict:
    """Mass, COM, and inertia tensor in SI, about the named coordinate system
    (or about the center of mass if omitted). The armature loop-closer:
    compare against params.py assumed values."""
    app = sw.attach()
    return sw.mass_properties(sw.resolve_doc(app, doc), coord_system)


@mcp.tool()
def sw_get_dimensions(doc: str, names: list[str]) -> dict:
    """Named model dimensions ('d1@Sketch1') with SI values and tolerance settings —
    verify against the part definition's interface contract."""
    app = sw.attach()
    return sw.get_dimensions(sw.resolve_doc(app, doc), names)


@mcp.tool()
def sw_set_tolerance(doc: str, dim_name: str, tol_type: str, values: dict) -> dict:
    """Set a dimension tolerance. tol_type: bilateral|symmetric|fit|none (none clears the tolerance).
    values: {"max": m, "min": m} in SI meters, or {"hole": "H7", "shaft": "p6"} for fit.
    The drawing inherits it from the model."""
    app = sw.attach()
    return sw.set_tolerance(sw.resolve_doc(app, doc), dim_name, tol_type, values)


@mcp.tool()
def sw_custom_props(doc: str, values: dict[str, str] | None = None) -> dict:
    """Custom properties (title block: part number, rev, material, finish).
    Omit values to read all; pass values to create/overwrite those keys."""
    app = sw.attach()
    d = sw.resolve_doc(app, doc)
    if values:
        return sw.custom_props_set(d, values)
    return sw.custom_props_get(d)


if __name__ == "__main__":
    mcp.run()

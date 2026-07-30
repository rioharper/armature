"""
The drift guard, asserted from the model's side.

docs/bom.yaml is the provenance of every number that came off a datasheet;
params.py is what the derivation actually used. Every BOM parameter carrying a
params_key must equal its counterpart here. This is the same check
armature-red-team runs mechanically — having it in the suite means a motor swap
that never reached the derivation turns the tests red at the moment it happens,
rather than waiting for the next review.
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[3]
BOM = REPO / "docs" / "bom.yaml"


def _linked_params():
    if not BOM.exists():
        pytest.skip("no docs/bom.yaml yet")
    data = yaml.safe_load(BOM.read_text()) or {}
    for group, items in data.items():
        if not isinstance(items, list):
            continue
        for entry in items:
            if not isinstance(entry, dict):
                continue
            for pname, pdef in (entry.get("params") or {}).items():
                if isinstance(pdef, dict) and pdef.get("params_key") and pdef.get("value") is not None:
                    yield entry.get("id"), pname, pdef["params_key"], float(pdef["value"])


def test_every_bom_driver_matches_params(params):
    linked = list(_linked_params())
    if not linked:
        pytest.skip("no BOM parameter carries a params_key")

    mismatches = []
    for entry_id, pname, key, bom_value in linked:
        actual = getattr(params, key, None)
        if actual is None and hasattr(params, "PARAMS"):
            actual = params.PARAMS.get(key)
        if actual is None:
            mismatches.append(f"{entry_id}.{pname}: params_key '{key}' absent from params.py")
        elif abs(float(actual) - bom_value) > 1e-9 * max(abs(bom_value), 1.0):
            mismatches.append(f"{entry_id}.{pname}: bom={bom_value} params.py={actual}")

    assert not mismatches, "BOM and model disagree:\n  " + "\n  ".join(mismatches)

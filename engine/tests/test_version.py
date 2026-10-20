"""The engine's version is the plugin's (#133, ADR 0009).

A project pins the engine by the plugin's git tag, so one tag must name
both: the engine's `pyproject.toml`, the plugin's `plugin.json` and its
entry in `marketplace.json` carry one version, and a release moves all
three in one commit. Answer: the three are equal, the rule itself, so no
version is written here for a release to update.
"""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_the_engine_plugin_and_marketplace_share_one_version():
    engine = tomllib.loads((ROOT / "engine" / "pyproject.toml")
                           .read_text(encoding="utf-8"))["project"]["version"]
    plugin = _json(".claude-plugin/plugin.json")["version"]
    [entry] = [p for p in _json(".claude-plugin/marketplace.json")["plugins"]
               if p["name"] == "armature"]
    versions = {"engine/pyproject.toml": engine,
                ".claude-plugin/plugin.json": plugin,
                ".claude-plugin/marketplace.json": entry["version"]}
    assert len(set(versions.values())) == 1, versions

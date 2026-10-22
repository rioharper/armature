"""The skills on the gates (#159, ADR 0011), held to #154's contract.

No skill, agent or reference keeps a Stage line; each stage skill that
merges names the gate call at its merge, through the plugin's launcher; and
init's template seeds what the gates read. The skills are prose an agent
follows, so these read the files the plugin ships.
"""

import re
from pathlib import Path

import pytest

from armature.gate import waivers

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
INIT = SKILLS / "init" / "SKILL.md"
LAUNCHER = '"${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" gate '
STAGE = re.compile(r"Stage:|Stage →|Stage\*\*")


def _section(text, heading):
    """The text under `heading` (a whole `## ...` line), up to the next
    `## ` heading."""
    start = text.index(heading + "\n") + len(heading) + 1
    end = text.find("\n## ", start)
    return text[start:] if end < 0 else text[start:end]


def _fenced(text, after):
    """The first fenced block following the line holding `after`."""
    at = text.index(after)
    found = re.search(r"^```[a-z]*\n(.*?)^```$", text[at:], re.M | re.S)
    assert found, f"no fenced block after {after!r}"
    return found.group(1)


def _template():
    """init's CLAUDE.md template: section 5's markdown block."""
    text = INIT.read_text(encoding="utf-8")
    return _fenced(text, "## 5. CLAUDE.md template")


def test_no_skill_agent_or_reference_writes_a_stage_line():
    hits = [f"{path.relative_to(ROOT)}:{n}"
            for folder in ("skills", "agents", "references")
            for path in sorted((ROOT / folder).rglob("*")) if path.is_file()
            for n, line in enumerate(path.read_text(
                encoding="utf-8", errors="replace").splitlines(), 1)
            if STAGE.search(line)]
    assert hits == []


@pytest.mark.parametrize("skill", ["armature-pitch", "armature-spec",
                                   "armature-plan", "armature-derive",
                                   "armature-cad"])
def test_each_stage_skill_merges_through_the_gate(skill):
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    assert LAUNCHER + "merge" in text
    assert "armature/" in text, "work lands on an armature/<kind>-<name> branch"


@pytest.mark.parametrize("skill", ["armature-spec", "armature-cad"])
def test_an_order_is_gated_by_buy(skill):
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    assert LAUNCHER + "buy" in text
    assert "docs/orders/" in text


def test_cad_releases_through_a_release_order():
    text = (SKILLS / "armature-cad" / "SKILL.md").read_text(encoding="utf-8")
    assert 'kind = "release"' in text


def test_init_guard_reads_the_ledger_marker():
    guard = _section(INIT.read_text(encoding="utf-8"), "## 1. Guard")
    assert "ledger.toml" in guard


def test_init_template_points_at_the_gate_not_a_stage():
    template = _template()
    assert "Latest artifacts" not in template
    assert "gate status" in template


def test_init_template_states_both_gates_and_the_users_confirmations():
    rules = _section(_template(), "## Standing rules")
    for word in ("`merge`", "`buy`", "armature/<kind>-<name>", "confirm"):
        assert word in rules


def test_init_ignores_the_stamps():
    text = INIT.read_text(encoding="utf-8")
    ignored = _fenced(text, "- `.gitignore`:").splitlines()
    assert ".armature/" in ignored


def test_init_seeds_orders_and_a_waiver_file_with_no_waiver():
    text = INIT.read_text(encoding="utf-8")
    assert "docs/orders" in _fenced(text, "Create (bash):")
    seed = _fenced(text, "- `waivers.toml`")
    assert waivers.parse(seed) == ([], [])
    assert seed.strip(), "a comment header says what the file holds"

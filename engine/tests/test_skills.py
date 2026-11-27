"""The skills on the check (ADR 0013).

No skill, agent or reference keeps a Stage line or names the removed gates;
each stage skill that changes what the check reads names the check call,
through the plugin's launcher; and init seeds none of the gates' files. The
skills are prose an agent follows, so these read the files the plugin ships.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
INIT = SKILLS / "init" / "SKILL.md"
CHECK = '"${CLAUDE_PLUGIN_ROOT}/scripts/armature.sh" check'
STAGE = re.compile(r"Stage:|Stage →|Stage\*\*")
GATES = re.compile(r"armature\.sh\"? gate|gates\.md|waivers\.toml|docs/orders"
                   r"|\.armature/|[Rr]echeck")


def _shipped():
    return [path for folder in ("skills", "agents", "references")
            for path in sorted((ROOT / folder).rglob("*"))
            if path.is_file() and path.suffix in (".md", ".py", ".sh")
            and not any(part.startswith(".") for part in path.parts)]


def _hits(pattern):
    return [f"{path.relative_to(ROOT)}:{n}" for path in _shipped()
            for n, line in enumerate(path.read_text(
                encoding="utf-8", errors="replace").splitlines(), 1)
            if pattern.search(line)]


def test_no_skill_agent_or_reference_writes_a_stage_line():
    assert _hits(STAGE) == []


def test_no_skill_agent_or_reference_names_the_removed_gates():
    assert _hits(GATES) == []


@pytest.mark.parametrize("skill", ["armature-spec", "armature-derive",
                                   "armature-cad"])
def test_each_stage_skill_that_moves_numbers_runs_the_check(skill):
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    assert CHECK in text


def test_the_plugin_ships_no_hook():
    assert not (ROOT / "hooks").exists()


def test_init_guard_reads_the_ledger_marker():
    text = INIT.read_text(encoding="utf-8")
    start = text.index("## 1. Guard")
    assert "ledger.toml" in text[start:text.index("\n## ", start + 1)]


def test_the_red_team_review_carries_no_block():
    text = (ROOT / "agents" / "red-team.md").read_text(encoding="utf-8")
    assert "```toml" not in text

"""The red team's findings block (#154, *Reviews*), held to its contract.

`agents/red-team.md` shows two examples: the review template and a recheck.
Each ends in the one fenced `toml` block the gate reads, and each is kept
verbatim under `fixtures/gate/` so the gate's parser reads the agent's own
example, not a copy that drifted from it.
"""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RED_TEAM = ROOT / "agents" / "red-team.md"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "gate"

SHA = re.compile(r"[0-9a-f]{40}")
SEVERITIES = {"BLOCKER", "MAJOR", "MINOR", "QUESTION"}


def _examples():
    """The agent file's two example files, in order: review, recheck."""
    text = RED_TEAM.read_text(encoding="utf-8")
    return re.findall(r"^````markdown\n(.*?)^````$", text, re.M | re.S)


def _block(example):
    """The example's one toml block, which must be the last thing in it."""
    blocks = re.findall(r"^```toml\n(.*?)^```$", example, re.M | re.S)
    assert len(blocks) == 1, "a review carries exactly one toml block"
    assert example.rstrip().endswith("```"), "nothing follows the block"
    return tomllib.loads(blocks[0])


def test_the_agent_shows_a_review_and_a_recheck():
    assert len(_examples()) == 2


@pytest.mark.parametrize("index, name", [(0, "review_example.md"),
                                         (1, "recheck_example.md")])
def test_each_fixture_is_its_example_verbatim(index, name):
    fixture = (FIXTURES / name).read_text(encoding="utf-8")
    assert fixture == _examples()[index]


def test_the_review_block_is_the_contracts_shape():
    block = _block(_examples()[0])
    assert set(block) == {"reviewed", "artifacts", "finding"}
    assert SHA.fullmatch(block["reviewed"])
    assert block["artifacts"]
    assert all(isinstance(a, str) and not a.startswith("/")
               for a in block["artifacts"])
    ids = [f["id"] for f in block["finding"]]
    assert len(ids) == len(set(ids))
    for f in block["finding"]:
        assert set(f) == {"id", "severity", "status"}, f
        assert re.fullmatch(r"F\d+", f["id"])
        assert f["severity"] in SEVERITIES
        assert f["status"] == "open"  # the red team never closes one
    assert {"MAJOR"} <= {f["severity"] for f in block["finding"]}


def test_the_recheck_block_is_the_contracts_shape():
    block = _block(_examples()[1])
    assert set(block) == {"reviewed", "rechecks", "finding"}
    assert SHA.fullmatch(block["reviewed"])
    assert re.fullmatch(r"docs/reviews/\d{4}-\d{2}-\d{2}-.+-review\.md",
                        block["rechecks"])
    for f in block["finding"]:
        assert set(f) == {"id", "status"}, f
        assert re.fullmatch(r"F\d+", f["id"])
    assert {f["status"] for f in block["finding"]} == {"holds", "reopened"}

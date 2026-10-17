"""The eval harness's own tests, kept apart from `engine/tests/` so the engine
suite stays fast. Run from the plugin root:

    uv run --project engine pytest evals/tests

They import the harness (`evals/generate.py`, `evals/score.py`) and the golden
answers (`engine/tests/golden/`) by path.
"""

import sys
from pathlib import Path

EVALS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EVALS), str(EVALS.parent / "engine" / "tests")]


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: assembles a case's project and runs its model")

"""
Shared fixtures. Milestone modules are imported lazily so a red M2 never blocks
running the M1 suite — checking an early milestone must not require a later one.
"""

import sys
from pathlib import Path

import pytest

MODEL_DIR = Path(__file__).resolve().parent.parent
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))


@pytest.fixture(scope="session")
def params():
    import params as p
    return p


@pytest.fixture(scope="session")
def kin():
    return pytest.importorskip("kinematics")


@pytest.fixture(scope="session")
def dyn():
    return pytest.importorskip("dynamics")


@pytest.fixture(scope="session")
def ver():
    return pytest.importorskip("verification")

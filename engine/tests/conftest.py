"""What the session collected, for the verb matrix's test (ADR 0008)."""

import pytest

_seen = set()  # every node id collected, before -k or -m deselects any


def pytest_itemcollected(item):
    _seen.add(item.nodeid)


@pytest.fixture(scope="session")
def seen():
    """Every node id this session collected."""
    return frozenset(_seen)

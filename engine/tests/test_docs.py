"""The docstrings' worked examples, run as written.

An example an agent copies from a docstring must run. Answer: each
example's printed values, worked by hand in its own docstring.
"""

import doctest

import pytest

from armature import Coordinates

WORKED = [Coordinates]


@pytest.mark.parametrize("obj", WORKED, ids=lambda o: o.__qualname__)
def test_the_worked_example_runs_as_written(obj):
    found = [t for t in doctest.DocTestFinder(recurse=False).find(obj)
             if t.examples]
    assert found, f"{obj.__qualname__}'s docstring has no example"
    runner = doctest.DocTestRunner(optionflags=doctest.NORMALIZE_WHITESPACE)
    for test in found:
        runner.run(test)
    assert runner.summarize(verbose=False).failed == 0

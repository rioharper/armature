"""pint, loaded once and only where a unit is read: `check`, and a budget's
sum, which holds its lines to one unit."""

import functools

CURRENCY = "[currency]"


def parse_unit(text):
    """`text` as a pint unit, or None where pint cannot parse it."""
    try:
        return registry().Unit(text)
    except Exception:   # pint's parser raises more types than it documents
        return None


@functools.cache
def registry():
    """pint's registry, with a currency, so a price is a quantity too."""
    import pint
    ureg = pint.UnitRegistry()
    ureg.define(f"USD = {CURRENCY}")
    return ureg

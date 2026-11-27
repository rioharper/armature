"""
Expressions of a part's globals, carried two ways at once: the value at
nominal, which places a sketch entity where it belongs, and the text in
SOLIDWORKS's equation syntax, which drives the dimension afterwards. So a
script builds the model at its nominal values and leaves every driven
dimension an equation of the globals, and the model moves when they do.

Lengths are mm and angles degrees, the units an MMGS part's equations read.
Pure Python: nothing here needs SOLIDWORKS.

    w = X(40.0, '"w"')          # a global
    half = w / 2                # X(20.0, '("w" / 2)')
    cos(30) * w                 # X(34.64..., '(cos(30) * "w")')
"""
from __future__ import annotations

import math
import re


class X:
    """An expression: its value at nominal (mm or deg) and its SOLIDWORKS text."""

    __slots__ = ("value", "text")

    def __init__(self, value, text):
        self.value, self.text = float(value), text

    @staticmethod
    def of(x):
        if isinstance(x, X):
            return x
        x = 0.0 if x == 0 else float(x)      # no -0
        return X(x, f"{x:.9g}")

    def zero(self):
        return self.text == "0"

    def __repr__(self):
        return f"X({self.value:g}, {self.text!r})"

    def __add__(self, o):
        o = X.of(o)
        if o.zero():
            return self
        if self.zero():
            return o
        return X(self.value + o.value, f"({self.text} + {o.text})")

    __radd__ = __add__

    def __sub__(self, o):
        o = X.of(o)
        if o.zero():
            return self
        return X(self.value - o.value, f"({self.text} - {o.text})")

    def __rsub__(self, o):
        return X.of(o) - self

    def __mul__(self, o):
        o = X.of(o)
        if self.zero() or o.zero():
            return X.of(0)
        if o.text == "1":
            return self
        if self.text == "1":
            return o
        return X(self.value * o.value, f"({self.text} * {o.text})")

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = X.of(o)
        if o.text == "1":
            return self
        return X(self.value / o.value, f"({self.text} / {o.text})")

    def __rtruediv__(self, o):
        return X.of(o) / self

    def __neg__(self):
        return self if self.zero() else X(-self.value, f"(-{self.text})")

    def __abs__(self):
        return self if self.value >= 0 else -self


ZERO = X.of(0)


def sin(a):
    a = X.of(a)
    return X(math.sin(math.radians(a.value)), f"sin({a.text})")


def cos(a):
    a = X.of(a)
    return X(math.cos(math.radians(a.value)), f"cos({a.text})")


def tan(a):
    a = X.of(a)
    return X(math.tan(math.radians(a.value)), f"tan({a.text})")


def sqrt(a):
    a = X.of(a)
    return X(math.sqrt(a.value), f"sqr({a.text})")


def arccos(a):
    a = X.of(a)
    return X(math.degrees(math.acos(a.value)), f"arccos({a.text})")


def arcsin(a):
    a = X.of(a)
    return X(math.degrees(math.asin(a.value)), f"arcsin({a.text})")


def rot(p, a):
    """Point p, an (X, X) pair, turned by angle a (deg) about the origin."""
    c, s = cos(a), sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def globals_mm(rows, comment=""):
    """(name, metres) rows, as a ledger hands them over, to Part's typed globals in mm."""
    return [(n, x * 1000.0, "mm", comment) for n, x in rows]


FUNCS = {"sin", "cos", "tan", "sqr", "abs", "atn", "arcsin", "arccos", "pi", "int", "sgn", "IIF", "exp", "log"}
# a number first, so the exponent of 1e3 is never read as a name
_IDENT = re.compile(r'"[^"]*"|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|[A-Za-z_][A-Za-z0-9_]*(?:@[A-Za-z0-9_]+)?')


def sw_expr(expr, rename=None):
    """A Python-style expression of global names, `"2 * w + gap"`, in SOLIDWORKS's syntax:
    every name quoted, mapped through `rename` (Python name to SOLIDWORKS name) first."""
    rename = rename or {}

    def q(m):
        tok = m.group(0)
        if tok.startswith('"') or tok[0].isdigit() or tok[0] == "." or tok in FUNCS:
            return tok
        return f'"{rename.get(tok, tok)}"'
    return _IDENT.sub(q, expr)

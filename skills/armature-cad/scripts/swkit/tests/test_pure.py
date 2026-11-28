"""The kit's pure modules, which need no SOLIDWORKS: from the folder holding swkit/,

    uv run --no-project --with pytest python -m pytest swkit/tests -q
"""
import math

import pytest

from swkit.expr import ZERO, X, cos, globals_mm, rot, sin, sqrt, sw_expr
from swkit.inertia import about, box, combine, from_solidworks
from swkit.layout import SERIES, Rooms, arrangement, first_scale, iso_scale, numbered


# --- expressions ----------------------------------------------------------------------------
def test_an_expression_carries_its_value_and_its_text():
    w = X(40.0, '"w"')
    e = (w - 4) / 2 + 3
    assert e.value == 21.0
    assert e.text == '((("w" - 4) / 2) + 3)'


def test_zero_and_one_drop_out_of_the_text():
    w = X(40.0, '"w"')
    assert (w + 0) is w and (0 + w) is w and (w * 1) is w and (1 * w) is w and (w / 1) is w
    assert (w * 0).zero() and (ZERO * w).zero()
    assert (-ZERO).zero()
    assert X.of(-0.0).text == "0"


def test_abs_negates_only_a_negative_value():
    w = X(40.0, '"w"')
    assert abs(w) is w
    n = -w / 2
    assert abs(n).value == 20.0 and abs(n).text == '(-((-"w") / 2))'


def test_trig_reads_degrees_and_writes_solidworks_functions():
    a = X(30.0, '"a"')
    assert math.isclose(sin(a).value, 0.5) and sin(a).text == 'sin("a")'
    assert math.isclose(cos(60).value, 0.5)
    assert sqrt(X(16.0, '"s"')).text == 'sqr("s")'
    x, y = rot((X.of(1), ZERO), 90)
    assert math.isclose(x.value, 0, abs_tol=1e-12) and math.isclose(y.value, 1)


def test_sw_expr_quotes_names_but_not_numbers_or_functions():
    assert sw_expr("2 * w + gap") == '2 * "w" + "gap"'
    assert sw_expr("1e3 * len") == '1e3 * "len"'
    assert sw_expr("sin(a) * L", {"L": "link_len"}) == 'sin("a") * "link_len"'
    assert sw_expr('"already" + 0.5') == '"already" + 0.5'


def test_globals_mm_converts_metres():
    assert globals_mm([("w", 0.04)], "why") == [("w", 40.0, "mm", "why")]


# --- inertia --------------------------------------------------------------------------------
def test_from_solidworks_negates_the_products():
    m, c, i = from_solidworks([1, 2, 3, 9, 9, 5.0, 10, 20, 30, 1, 2, 3])
    assert m == 5.0 and c == [1, 2, 3]
    assert i == [[10, -1, -2], [-1, 20, -3], [-2, -3, 30]]


def test_two_halves_of_a_box_sum_to_the_box():
    a = box(1.0, (0.05, 0.2, 0.3), (-0.025, 0, 0))
    b = box(1.0, (0.05, 0.2, 0.3), (0.025, 0, 0))
    m, c, i = combine([a, b])
    whole = box(2.0, (0.1, 0.2, 0.3))
    assert m == 2.0 and c == pytest.approx([0, 0, 0])
    for r in range(3):
        assert i[r] == pytest.approx(whole[2][r])


def test_an_l_section_has_the_product_the_hand_works_out():
    # rectangles 20 x 10 at (50, 5) and 10 x 20 at (45, 20) (mm), 1 kg each
    mm = 1e-3
    m, c, i = combine([box(1.0, (20 * mm, 10 * mm, 5 * mm), (50 * mm, 5 * mm, 0)),
                       box(1.0, (10 * mm, 20 * mm, 5 * mm), (45 * mm, 20 * mm, 0))])
    assert c == pytest.approx([47.5 * mm, 12.5 * mm, 0])
    # the product sum m x y about the COM is 2 x 1 kg x (2.5)(-7.5) mm^2: the tensor's entry is its negation
    assert i[0][1] == pytest.approx(37.5 * mm * mm)


def test_about_a_point_shifts_by_the_parallel_axis_rule():
    b = box(2.0, (0.1, 0.1, 0.1))
    i = about(b, (0.0, 0.0, -0.5))
    assert i[0][0] == pytest.approx(b[2][0][0] + 2.0 * 0.25)
    assert i[2][2] == pytest.approx(b[2][2][2])


# --- layout ---------------------------------------------------------------------------------
def test_first_scale_takes_the_largest_that_fits():
    room = (0.0, 280.0, 0.0, 150.0)
    assert SERIES[first_scale((40, 20, 10), room, 4.0)] == (2, 1)       # 5:1 is 154 tall
    assert SERIES[first_scale((120, 60, 30), room, 4.0)] == (1, 1)
    assert SERIES[first_scale((400, 200, 100), room, 4.0)] == (1, 5)    # 1:2 is 154 tall
    assert SERIES[first_scale((400, 200, 100), room, 4.0, show=())] == (1, 2)
    assert SERIES[first_scale((300, 100, 10), room, 4.0, show=())] == (1, 2)


def test_iso_scale_fits_its_square():
    assert iso_scale((40, 20, 10), 100.0) == 1.0     # 2:1 would take 105
    assert iso_scale((4000, 2000, 1000), 100.0) == SERIES[-1][0] / SERIES[-1][1]


OUT = {"*Front": (0, 0, 60, 40), "*Top": (0, 0, 60, 20), "*Right": (0, 0, 20, 40)}


def test_third_angle_puts_the_top_above_and_the_right_beside():
    at, fits = arrangement(OUT, (10, 300, 10, 200), 5.0)
    assert at["*Front"] == (40, 30)
    assert at["*Top"] == (40, 10 + 40 + 5 + 10)
    assert at["*Right"] == (10 + 60 + 5 + 10, 30)
    assert fits


def test_first_angle_puts_the_top_below_and_the_right_to_the_left():
    at, fits = arrangement(OUT, (10, 300, 10, 200), 5.0, first_angle=True)
    assert at["*Right"] == (20, 10 + 20 + 5 + 20)
    assert at["*Front"] == (10 + 20 + 5 + 30, 10 + 20 + 5 + 20)
    assert at["*Top"] == (10 + 20 + 5 + 30, 20)
    assert fits


def test_arrangement_says_when_the_views_overrun_their_room():
    _, fits = arrangement(OUT, (0, 80, 0, 200), 5.0)
    assert not fits
    _, fits = arrangement({"*Front": OUT["*Front"]}, (0, 60, 0, 40), 5.0)
    assert fits


def test_rooms_scale_with_the_sheet():
    a3 = Rooms.for_sheet(420, 297)
    assert a3.views == pytest.approx((16, 300, 136, 286), abs=0.2)
    assert Rooms.for_sheet(420, 297, dims=True).gap == 18.0


def test_notes_number_but_continuations_do_not():
    assert numbered(["A.", "B:", "   more of B.", "C."]) == ["1. A.", "2. B:", "   more of B.", "3. C."]

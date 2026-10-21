"""The buy gate (ADR 0011, #157): `armature.gate buy` on an order branch,
run on fixture git repos built here, beside `test_gate.py`'s merge.

Answer: each verdict is worked from the fixture by the rule #154 states,
never from the gate's own output. Today is 2026-10-21, so a price retrieved
2026-07-23 is 90 days old and passes, and one retrieved 2026-07-22 is 91
and fails. The RS02 has price tiers at 1 and at 4: a line of 3 uses the
tier at 1 (the largest at or below 3), a line of 4 the tier at 4. The
traps each mutant of #157 would hide in are built and named: a 91-day-old
price, an estimate under an ordered part, the tier above `qty`, an order
that changes nothing a merge review gates, and a release with a stub left.
"""

import subprocess
import sys

import pytest

from armature.gate import Context, buy, order, status
from test_gate import (LEDGER, TODAY, Project, finding, gate, review,
                       waiver)

TORQUE = ('as_written = "6 N*m"\nstatus = "confirmed"\n'
          'source = { kind = "datasheet", '
          'ref = "rs02-datasheet", retrieved = 2026-09-01 }')
ESTIMATE = ('status = "confirmed"\nband = [5.0, 7.0]\n'
            'source = { kind = "estimate", ref = "a forum post" }')


def parts(p1="2026-09-01", p4="2026-09-01", torque=TORQUE):
    """The RS02's ledger entries: its rated torque, written `torque`, and
    its prices at 1 and at 4, retrieved on `p1` and `p4`."""
    return f"""
[part.rs02.torque_rated]
value = 6.0
unit = "N*m"
{torque}

[part.rs02.price_at_1]
value = 230.0
as_written = "230.00 USD"
unit = "USD"
status = "confirmed"
source = {{ kind = "datasheet", ref = "rs02-store", retrieved = {p1} }}

[part.rs02.price_at_4]
value = 210.0
as_written = "210.00 USD"
unit = "USD"
status = "confirmed"
source = {{ kind = "datasheet", ref = "rs02-store", retrieved = {p4} }}
"""


ORDER = "docs/orders/2026-10-21-rs02-bench.toml"
ORDER_REVIEW = "docs/reviews/2026-10-21-rs02-bench-review.md"
BRANCH = "armature/order-rs02-bench"


def purchase(qty=1, part="part.rs02"):
    return (f'kind = "purchase"\nvendor = "RobStride"\n\n[[line]]\n'
            f'part = "{part}"\nqty = {qty}\n')


class Shop(Project):
    """A project whose ledger, committed on `main`, prices the RS02."""

    def __init__(self, root):
        super().__init__(root)
        self.price()

    def price(self, **kw):
        """The ledger with the RS02's entries `parts(**kw)`, committed."""
        self.write("ledger.toml", LEDGER + parts(**kw))
        self.commit("the RS02 in the ledger")

    def buy(self, **kw):
        kw.setdefault("today", TODAY)
        return buy(self.root, **kw)

    def order(self, text, path=ORDER, branch=BRANCH, reviewed=True):
        """An order branch adding `text` at `path`, reviewed unless not;
        the order's commit."""
        self.branch(branch)
        self.write(path, text)
        sha = self.commit("the order")
        if reviewed:
            review(self, sha, finding("F1", "MINOR"), path=ORDER_REVIEW,
                   artifacts=[path])
            self.commit("the order's review")
        return sha


@pytest.fixture
def shop(tmp_path):
    return Shop(tmp_path)


# --- the order record -----------------------------------------------------------
def test_a_reviewed_order_of_one_confirmed_fresh_part_is_cleared(shop):
    shop.order(purchase())
    verdict = shop.buy()
    assert verdict.gate == "buy" and verdict.passed, verdict.lines()
    assert [r.item for r in verdict.results][:7] == [
        "fast-forward", "ledger", "stamps", "engine", "review", "closed",
        "moves"]
    assert ORDER in verdict["order"].detail
    assert any("cleared" in n and "nobody can see whether" in n
               for n in verdict.notes)


def test_a_branch_adding_no_order_record_fails_buy(shop):
    shop.branch("armature/order-none")
    shop.write("docs/decisions.md", "# Decisions\n")
    shop.commit()
    verdict = shop.buy()
    assert verdict["order"].state == "fail"
    assert "no order record" in verdict["order"].detail
    assert verdict.notes == []


def test_a_branch_adding_two_order_records_fails_buy(shop):
    shop.order(purchase())
    shop.write("docs/orders/2026-10-21-rs02-more.toml", purchase(4))
    shop.commit("a second order")
    verdict = shop.buy()
    assert verdict["order"].state == "fail"
    assert "2026-10-21-rs02-more.toml" in verdict["order"].detail


@pytest.mark.parametrize("text, why", [
    ('kind = "gift"\nvendor = "v"\n[[line]]\npart = "part.rs02"\nqty = 1\n',
     "kind"),
    ('kind = "purchase"\n[[line]]\npart = "part.rs02"\nqty = 1\n', "vendor"),
    ('kind = "purchase"\nvendor = "v"\n', "line"),
    (purchase(0), "qty"),
    (purchase(part="rs02"), "part."),
    ('kind = "purchase"\nvendor = "v"\n[[line]]\n'
     'definition = "cad/parts/HIP"\nexports = []\n', "definition"),
    ('kind = "purchase"\nvendor = "v"\nnote = "x"\n[[line]]\n'
     'part = "part.rs02"\nqty = 1\n', "note"),
    ("kind = purchase", "TOML"),
], ids=["kind", "vendor", "no-line", "qty", "part", "release-line", "field",
        "toml"])
def test_an_order_record_that_is_not_the_contracts_shape_fails(
        shop, text, why):
    shop.order(text)
    verdict = shop.buy()
    assert verdict["order"].state == "fail"
    assert why in verdict["order"].detail


def test_an_order_record_is_named_for_its_date(shop):
    shop.order(purchase(), path="docs/orders/rs02-bench.toml")
    verdict = shop.buy()
    assert verdict["order"].state == "fail"
    assert "<date>-<name>.toml" in verdict["order"].detail


def test_order_names_the_record_a_branch_adds(shop):
    assert order(Context.at(shop.root)) is None
    shop.order(purchase())
    assert order(Context.at(shop.root)) == ORDER
    shop.write("docs/orders/2026-10-21-rs02-more.toml", purchase(4))
    shop.commit("a second order")
    assert order(Context.at(shop.root)) is not None, \
        "a branch adding two is still gated by buy, which fails it"


# --- every entry of an ordered part confirmed, none an estimate -----------------
def test_a_candidate_entry_under_an_ordered_part_fails(shop):
    shop.price(torque=TORQUE.replace("confirmed", "candidate"))
    shop.order(purchase())
    verdict = shop.buy()
    assert verdict["confirmed"].state == "fail"
    assert "part.rs02.torque_rated" in verdict["confirmed"].detail


def test_an_estimate_under_an_ordered_part_fails_even_confirmed(shop):
    shop.price(torque=ESTIMATE)
    shop.order(purchase())
    verdict = shop.buy()
    assert verdict["ledger"].state == "pass"
    assert verdict["confirmed"].state == "fail"
    assert "estimate" in verdict["confirmed"].detail
    assert "part.rs02.torque_rated" in verdict["confirmed"].detail


def test_a_part_with_no_entry_in_the_ledger_fails(shop):
    shop.order(purchase(part="part.rs03"))
    verdict = shop.buy()
    assert verdict["confirmed"].state == "fail"
    assert "part.rs03" in verdict["confirmed"].detail


# --- the line's price tier, retrieved within 90 days -----------------------------
@pytest.mark.parametrize("retrieved, state", [("2026-07-23", "pass"),
                                              ("2026-07-22", "fail")])
def test_a_price_is_fresh_for_90_days_and_old_at_91(shop, retrieved, state):
    shop.price(p1=retrieved, p4=retrieved)
    shop.order(purchase(1))
    verdict = shop.buy()
    assert verdict["price"].state == state
    assert "price_at_1" in verdict["price"].detail


def test_the_tier_is_the_largest_at_or_below_qty_not_the_next_above(shop):
    """price_at_4 is stale and price_at_1 fresh: a line of 3 uses the tier
    at 1 and passes; a line of 4 uses the tier at 4 and fails. The tier
    at 4 is stale only by its own date, which `price.old` would also see,
    so the line of 3 passes only where the tier rule reads price_at_1 and
    `price.old` is held to the tier a line uses."""
    shop.price(p4="2026-05-01")
    shop.order(purchase(3))
    verdict = shop.buy()
    assert verdict["price"].state == "pass", verdict["price"].detail
    assert "price_at_1" in verdict["price"].detail
    shop.write(ORDER, purchase(4))
    shop.commit("four")
    verdict = shop.buy()
    assert verdict["price"].state == "fail"
    assert "price_at_4" in verdict["price"].detail


def test_a_qty_below_every_tier_has_no_price(shop):
    shop.write("ledger.toml", LEDGER + parts().replace("price_at_1",
                                                       "price_at_2"))
    shop.commit("no single price")
    shop.order(purchase(1))
    verdict = shop.buy()
    assert verdict["price"].state == "fail"
    assert "no price_at" in verdict["price"].detail


def test_price_old_is_an_error_at_buy_and_a_warning_at_merge(shop):
    shop.price(p1="2026-06-01")
    shop.order(purchase(1))
    verdict = shop.buy()
    assert verdict["ledger"].state == "pass"
    assert verdict["price"].state == "fail"
    assert "price.old" in verdict["price"].detail
    assert shop.gate()["ledger"].state == "pass"


# --- a review names the order record ----------------------------------------------
def test_an_order_with_no_review_fails_though_merge_needs_none(shop):
    shop.order(purchase(), reviewed=False)
    verdict = shop.buy()
    assert verdict["review"].state == "pass"
    assert "no review needed" in verdict["review"].detail
    assert verdict["order-review"].state == "fail"
    assert not verdict.passed


def test_a_review_that_does_not_list_the_order_record_does_not_count(shop):
    sha = shop.order(purchase(), reviewed=False)
    review(shop, sha, finding("F1", "MINOR"), path=ORDER_REVIEW,
           artifacts=["ledger.toml"])
    shop.commit("a review of the ledger alone")
    assert shop.buy()["order-review"].state == "fail"


def test_a_review_pinned_before_the_order_was_written_does_not_count(shop):
    shop.branch(BRANCH)
    shop.write("docs/decisions.md", "# Decisions\n")
    sha = shop.commit("before the order")
    shop.write(ORDER, purchase())
    review(shop, sha, finding("F1", "MINOR"), path=ORDER_REVIEW,
           artifacts=[ORDER])
    shop.commit("the order, and a review pinned before it")
    verdict = shop.buy()
    assert verdict["order-review"].state == "fail"
    assert "not at" in verdict["order-review"].detail


def test_an_open_major_in_the_orders_review_fails_closed(shop):
    sha = shop.order(purchase(), reviewed=False)
    review(shop, sha, finding("F1", "MAJOR"), path=ORDER_REVIEW,
           artifacts=[ORDER])
    shop.commit("the review: a major")
    verdict = shop.buy()
    assert verdict["order-review"].state == "pass"
    assert verdict["closed"].state == "fail"


# --- the staged buy -----------------------------------------------------------------
def test_one_actuator_then_four_both_clear(shop):
    shop.order(purchase(1))
    first = shop.buy()
    assert first.passed, first.lines()
    shop.checkout("main")
    shop.git("merge", "--ff-only", "-q", BRANCH)
    shop.order(purchase(4), path="docs/orders/2026-10-21-rs02-four.toml",
               branch="armature/order-rs02-four")
    second = shop.buy()
    assert second.passed, second.lines()
    assert "2026-10-21-rs02-four.toml" in second["order"].detail
    assert "price_at_4" in second["price"].detail


# --- waivers ------------------------------------------------------------------------
@pytest.mark.parametrize("item", ["order", "confirmed", "price",
                                  "order-review"])
def test_every_purchase_item_can_be_waived_by_a_buy_waiver(shop, item):
    shop.price(torque=TORQUE.replace("confirmed", "candidate"),
               p1="2026-01-01")
    shop.branch(BRANCH)
    shop.write("waivers.toml", waiver(item=item, gate="buy", scope=BRANCH))
    shop.write(ORDER, purchase())
    if item == "order":
        shop.write("docs/orders/2026-10-21-rs02-more.toml", purchase())
    shop.commit("an order failing every purchase item")
    verdict = shop.buy()
    assert verdict[item].state == "waived"
    assert "a template copy" in verdict[item].detail
    assert [r.state for r in verdict.results].count("waived") == 1


def test_a_merge_waiver_does_not_waive_buy(shop):
    shop.branch(BRANCH)
    shop.write("waivers.toml", waiver(item="review", scope=BRANCH))
    shop.write("analysis/model/kinematics.py", "L1 = 1\n")
    shop.write(ORDER, purchase())
    shop.commit("an order with unreviewed model code")
    assert shop.gate()["review"].state == "waived"
    assert shop.buy()["review"].state == "fail"


# --- a release ------------------------------------------------------------------------
PASSING = "print('All self-tests passed across all milestones.')\n"
STUBS = """\
_REGISTRY = []


def bearing(part_number):
    _REGISTRY.append(part_number)
    return part_number


def still_placeholder():
    return list(dict.fromkeys(_REGISTRY))
"""
CLEAN = "def build():\n    return 'plate'\n"
STUBBED = ("import stubs\n\n\ndef build():\n"
           "    return [stubs.bearing('6004-2RS'), 'plate']\n")
RELEASE = "docs/orders/2026-10-21-hip-plate.toml"
DXF = "cad/parts/export/HIP.dxf"


def release(definition="cad/parts/HIP", exports=(DXF,)):
    return ('kind = "release"\nvendor = "SendCutSend"\n\n[[line]]\n'
            f'definition = "{definition}"\n'
            "exports = [" + ", ".join(f'"{e}"' for e in exports) + "]\n")


class Runner:
    """Runs a folder's Python with this interpreter, `run_all.py` unless
    told otherwise, recording each run's (folder, command)."""

    def __init__(self):
        self.runs = []

    def __call__(self, folder, project, *command):
        command = command or ("run_all.py",)
        self.runs.append((folder, command))
        run = subprocess.run([sys.executable, *command], cwd=folder,
                             capture_output=True, text=True,
                             encoding="utf-8")
        return run.returncode == 0, run.stdout + run.stderr


def parts_on_main(shop, recipe=CLEAN, model=True):
    """The model and the HIP plate, committed on `main`."""
    if model:
        shop.write("analysis/model/run_all.py", PASSING)
    shop.write("cad/parts/run_all.py", PASSING)
    shop.write("cad/parts/stubs.py", STUBS)
    shop.write("cad/parts/HIP.md", "# HIP plate\n")
    if recipe is not None:
        shop.write("cad/parts/HIP.py", recipe)
    shop.commit("the model and the HIP plate")


def released(shop, text=None, recipe=CLEAN, model=True, **kw):
    """A reviewed release of the HIP plate, gated by `buy`."""
    parts_on_main(shop, recipe, model)
    shop.branch("armature/order-hip-plate")
    shop.write(DXF, "0\nSECTION\n")
    shop.write(RELEASE, text or release())
    sha = shop.commit("the release")
    review(shop, sha, finding("F1", "MINOR"), path=ORDER_REVIEW,
           artifacts=[RELEASE])
    shop.commit("the release's review")
    kw.setdefault("runner", Runner())
    return shop.buy(**kw)


def test_a_reviewed_release_of_a_part_with_no_stub_is_cleared(shop):
    verdict = released(shop)
    assert verdict.passed, verdict.lines()
    assert verdict["confirmed"].state == "pass"
    assert "buys no part" in verdict["confirmed"].detail
    assert "cad/parts/HIP" in verdict["placeholders"].detail
    assert "analysis/model" in verdict["release-stamps"].detail
    assert any("cleared" in n for n in verdict.notes)


def test_a_release_with_a_placeholder_left_fails(shop):
    verdict = released(shop, recipe=STUBBED)
    assert verdict["placeholders"].state == "fail"
    assert "6004-2RS" in verdict["placeholders"].detail
    assert verdict.notes == []


def test_a_part_with_no_recipe_has_no_stub_to_build(shop):
    verdict = released(shop, recipe=None)
    assert verdict["placeholders"].state == "pass"
    assert "no build recipe" in verdict["placeholders"].detail


def test_a_recipe_with_no_build_fails_rather_than_build_nothing(shop):
    """`still_placeholder()` is empty where nothing was built, so a part
    whose recipe has no `build()` cannot show it has no stub."""
    verdict = released(shop, recipe="import stubs\nPLATE = 'plate'\n")
    assert verdict["placeholders"].state == "fail"
    assert "build()" in verdict["placeholders"].detail


def test_verify_reads_the_placeholder_check_and_never_runs_it(shop):
    runner = Runner()
    verdict = released(shop, verify=True, runner=runner)
    assert verdict["placeholders"].state == "fail"
    assert runner.runs == []
    assert shop.buy(runner=runner).passed
    runs = len(runner.runs)
    again = shop.buy(verify=True, runner=runner)
    assert again.passed, again.lines()
    assert len(runner.runs) == runs


def test_a_definition_that_names_no_part_fails(shop):
    verdict = released(shop, release("cad/parts/KNEE"))
    assert verdict["placeholders"].state == "fail"
    assert "cad/parts/KNEE" in verdict["placeholders"].detail
    assert verdict["release-stamps"].state == "fail"


def test_a_part_in_a_folder_of_its_own_is_read_too(shop):
    shop.write("analysis/model/run_all.py", PASSING)
    shop.write("cad/parts/hip-plate/run_all.py", PASSING)
    shop.write("cad/parts/hip-plate/stubs.py", STUBS)
    shop.write("cad/parts/hip-plate/hip-plate.md", "# HIP plate\n")
    shop.write("cad/parts/hip-plate/hip-plate.py", STUBBED)
    shop.commit("a part folder")
    shop.order(release("cad/parts/hip-plate",
                       ["cad/parts/hip-plate/hip-plate.md"]), path=RELEASE)
    verdict = shop.buy(runner=Runner())
    assert verdict["placeholders"].state == "fail"
    assert "6004-2RS" in verdict["placeholders"].detail
    assert "cad/parts/hip-plate" in verdict["release-stamps"].detail


def test_a_release_needs_the_models_run_all(shop):
    verdict = released(shop, model=False)
    assert verdict["stamps"].state == "pass"
    assert verdict["release-stamps"].state == "fail"
    assert "analysis/model/run_all.py" in verdict["release-stamps"].detail


def test_a_release_whose_part_fails_its_run_all_fails_its_stamp(shop):
    parts_on_main(shop)
    shop.write("cad/parts/run_all.py", "raise AssertionError('wall 1.2')\n")
    shop.commit("a failing part")
    shop.branch("armature/order-hip-plate")
    shop.write(DXF, "0\nSECTION\n")
    shop.write(RELEASE, release())
    review(shop, shop.commit("the release"), finding("F1", "MINOR"),
           path=ORDER_REVIEW, artifacts=[RELEASE])
    shop.commit("the review")
    verdict = shop.buy(runner=Runner())
    assert verdict["release-stamps"].state == "fail"
    assert "cad/parts" in verdict["release-stamps"].detail


def test_a_release_whose_exports_are_not_committed_fails(shop):
    verdict = released(shop, release(exports=["cad/parts/export/X.dxf"]))
    assert verdict["order"].state == "fail"
    assert "cad/parts/export/X.dxf" in verdict["order"].detail


@pytest.mark.parametrize("item", ["placeholders", "release-stamps"])
def test_every_release_item_can_be_waived_by_a_buy_waiver(shop, item):
    shop.write("waivers.toml", waiver(item=item, gate="buy",
                                      scope="armature/order-hip-plate"))
    verdict = released(shop, recipe=STUBBED, model=False)
    assert verdict[item].state == "waived"
    assert "a template copy" in verdict[item].detail


# --- status and the CLI ---------------------------------------------------------------
def test_status_adds_buy_on_an_order_branch(shop):
    assert [v.gate for v in status(shop.root, today=TODAY)] == ["merge"]
    shop.order(purchase())
    verdicts = status(shop.root, today=TODAY)
    assert [v.gate for v in verdicts] == ["merge", "buy"]
    assert verdicts[1].passed, verdicts[1].lines()


def test_buy_prints_its_items_and_that_the_order_is_cleared(shop):
    shop.price(p1="2026-10-01", p4="2026-10-01")
    shop.order(purchase())
    run = gate("buy", cwd=shop.root)
    assert run.returncode == 0, run.stdout + run.stderr
    lines = run.stdout.splitlines()
    assert [line.split()[1] for line in lines[:13]] == [
        "fast-forward", "ledger", "stamps", "engine", "review", "closed",
        "moves", "order", "confirmed", "price", "order-review",
        "placeholders", "release-stamps"]
    assert lines[-1].startswith(f"cleared {ORDER}")
    assert "nobody can see whether" in lines[-1]


def test_buy_exits_1_and_clears_nothing_on_a_failure(shop):
    shop.price(p1="2026-10-01", p4="2026-10-01")
    shop.order(purchase(), reviewed=False)
    run = gate("buy", cwd=shop.root)
    assert run.returncode == 1
    assert "fail order-review" in run.stdout
    assert "cleared" not in run.stdout

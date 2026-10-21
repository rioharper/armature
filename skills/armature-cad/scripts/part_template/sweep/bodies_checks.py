"""
sweep/bodies_checks.py — self-tests for bodies.py: the sweep finds a
collision that is there and none for a mechanism that clears, the pair
excuses hold what their comments claim, link lengths come from the ledger
or nowhere, and postures from the engine's truth model of mechanism.py or
nowhere. Each is written to FAIL if the guard it covers is removed.
"""

import importlib
import math
import sys
import tempfile
from pathlib import Path

from build123d import Box, Location, Rotation, Vector

from check import interference, sweep_clearance
from sweep import bodies


def _raised(exc_type, fn, *args, **kwargs):
    """The exception `fn` raised, or None. A check that cannot fail is
    not a check, so every use of this is asserted truthy."""
    try:
        fn(*args, **kwargs)
    except exc_type as exc:
        return exc
    return None


def test_folded_collides_straight_clears():
    bodies.ensure_geometry()
    # Folded hard back on itself, the forearm reaches the base post.
    folded = bodies.pose((0.0, math.pi))
    assert interference(folded["link2"], folded["base"]) > 0, "folded arm must hit the post"
    # Straight out, nothing but the design-adjacent pairs touch.
    straight = bodies.pose((0.0, 0.0))
    assert interference(straight["link2"], straight["base"]) == 0.0
    assert sweep_clearance(bodies.pose, [(0.0, 0.0)], ignore=bodies.ADJACENT) == []
    print("  [PASS] folded arm hits the post, straight arm clears")


def test_elbow_excused_in_geometry_not_by_threshold():
    bodies.ensure_geometry()
    # A threshold measured at home is provably wrong for the elbow pair
    # (see the comment above ADJACENT) and flags 98.2% of the swept grid.
    # A blanket pair-ignore reports ONLY base<->link2 (5321.8 mm^3) at
    # q2=180 and hides link1<->link2 completely; both must be visible,
    # worst first. base<->link1 stays quiet - its constant 35321.8 mm^3 is
    # exactly its own threshold, never above it.
    hits = sweep_clearance(bodies.pose, [(0.0, math.pi)], ignore=bodies.ADJACENT)
    assert [(h[1], h[2]) for h in hits] == [("link1", "link2"), ("base", "link2")], hits
    # The fully-folded overlap is 276000 mm^3, not the 300000 an untrimmed
    # link2 gives (the trim removes a 20x40x30 mm slab that would otherwise
    # be in there). Asserted so JOINT_TRIM's comment can't drift from it.
    assert math.isclose(hits[0][3], 276000.0), hits[0][3]

    # Joint limits that keep the elbow inside JOINT_TRIM's clean zone must
    # sweep clear: q2 within +-45 deg (well inside the measured 91 deg
    # onset) at every q1 reports nothing.
    limited = [(q1, q2) for q1 in (-math.pi, 0.0, math.pi / 2, math.pi)
               for q2 in (-math.radians(45), 0.0, math.radians(45))]
    assert sweep_clearance(bodies.pose, limited, ignore=bodies.ADJACENT) == [], "limited q2 must clear"

    # A pair can still be fully excused - at a threshold explicitly wider
    # than any overlap it will see - as a visible, tunable number.
    wide = dict(bodies.ADJACENT)
    wide[frozenset(("base", "link2"))] = math.inf
    hits = sweep_clearance(bodies.pose, [(0.0, math.pi)], ignore=wide)
    assert len(hits) == 1 and hits[0][1:3] == ("link1", "link2"), hits
    print("  [PASS] elbow pair excused in geometry; both fold-in pairs reported")


def test_elbow_onset_matches_the_trim_table():
    bodies.ensure_geometry()

    def elbow_onset(sign):
        """First |q2| walking out from 0 where link1<->link2 interferes."""
        for deg in range(1, 180):
            p = bodies.pose((0.0, math.radians(sign * deg)))
            if interference(p["link1"], p["link2"]) > 0.0:
                return deg
        raise AssertionError("no onset found in the scanned range")

    # The TRUE onset, measured at 1 deg rather than trusted from
    # JOINT_TRIM's comment, so a geometry change fails here first.
    assert elbow_onset(1) == elbow_onset(-1) == 91  # JOINT_TRIM = LINK_W/2 = 20 mm

    def isolated_onset(w1, w2, trim):
        """pose()'s link1/link2 box-pivot geometry in isolation, so LINK_W
        can't leak in and make the test trivially agree with itself."""
        link1 = Box(bodies.L1, w1, bodies.LINK_H).locate(Location((bodies.L1 / 2, 0, 0)))
        elbow = Location((bodies.L1, 0, 0))
        l2len = bodies.L2 - trim
        link2 = Box(l2len, w2, bodies.LINK_H).locate(Location((trim + l2len / 2, 0, 0)))
        for deg in range(1, 180):
            if interference(link1, elbow * (Rotation(0, 0, deg) * link2)) > 0.0:
                return deg
        raise AssertionError("no onset found in the scanned range")

    assert isolated_onset(bodies.LINK_W, bodies.LINK_W, 10.0) == 31, "table row (trim=10mm) went stale"
    # The rule ("size from the NEIGHBOUR's half-width") only matters when
    # the links differ, which the worked example can't show: trim from
    # link2's own half-width (wrong rule) onsets far earlier than from
    # link1's (right rule) on a mechanism with a wider proximal link.
    assert isolated_onset(60.0, 40.0, 20.0) == 46, "w2/2-sized trim (wrong rule)"
    assert isolated_onset(60.0, 40.0, 30.0) == 91, "w1/2-sized trim (right rule)"
    print("  [PASS] elbow onset and the trim-vs-onset table re-measured")


def test_threshold_slop_holds_at_every_q1():
    bodies.ensure_geometry()
    # base<->link1's threshold IS the volume measured at q1=0; recomputing
    # "the same" boolean at a DIFFERENT q1 differs in the last bits
    # (measured: +2.18e-11 mm^3 across 37 q1 samples), and a bare
    # `v > threshold` reports 444 of those as collisions. Assert across
    # several q1, not only q1=0, which is bit-exact by construction.
    for q1deg in (0, 45, 90, 135, 180, -90):
        q = (math.radians(q1deg), 0.0)
        p = bodies.pose(q)
        assert sweep_clearance(bodies.pose, [q], ignore=bodies.ADJACENT) == [], (
            q1deg, interference(p["base"], p["link1"]))
    print("  [PASS] base<->link1 threshold absorbs OCC float noise at every q1")


def _entry(name, value, unit="m"):
    """One chosen ledger entry, as the model template writes its lengths."""
    return (f'[{name}]\nvalue = {value}\nunit = "{unit}"\n'
            f'source = {{ kind = "chosen", ref = "spec §5" }}\n\n')


def _in_ledger(text, fn):
    """`fn(model_dir)` with a ledger holding `text` above `model_dir`, or
    no ledger when `text` is None. A temp dir sits outside any project, so
    nothing nearer than the one written here can answer."""
    with tempfile.TemporaryDirectory() as tmp:
        model = Path(tmp, "analysis", "model")
        model.mkdir(parents=True)
        if text is not None:
            Path(tmp, "ledger.toml").write_text(text, encoding="utf-8")
        return fn(model)


def test_link_lengths_come_from_the_ledger_or_nowhere():
    from armature.ledger import LedgerError

    lengths = _entry("mechanism.l1", 0.30) + _entry("mechanism.l2", 0.25)
    assert _in_ledger(lengths, bodies._resolve_lengths) == (300.0, 250.0)
    # No ledger anywhere: fatal, not a fallback to a typed 300.0 / 250.0 -
    # there is no safe placeholder for a link length.
    assert _raised(RuntimeError, _in_ledger, None, bodies._resolve_lengths)
    # A renamed entry, or no mechanism section, is a broken link to the
    # derivation, not a missing-ledger event: it propagates.
    assert _raised(KeyError, _in_ledger, _entry("mechanism.l1", 0.30), bodies._resolve_lengths)
    assert _raised(LedgerError, _in_ledger, _entry("req.REQ-001", 0.30), bodies._resolve_lengths)
    # The lengths the model reads, not the part's: a part template's ledger
    # beside the sweep holds no mechanism section and must not answer.
    assert bodies.MODEL_DIR == Path(bodies.__file__).resolve().parents[3] / "analysis" / "model"
    print("  [PASS] link lengths from the ledger, no silent fallback")


def test_envelopes_ride_on_the_engines_sites():
    bodies.ensure_geometry()
    # The tool end of link2's envelope, at a posture off every symmetry
    # plane, is where the engine's truth model puts the tool site - the
    # sweep keeps no forward kinematics of its own to disagree with it. A
    # posture written as the derivation's (q1, q2) must land on the
    # description's (shoulder, elbow), in that order.
    q = (0.7, -1.9)
    tip = bodies.TRUTH.at(q=dict(zip(bodies.TRUTH.independent, q))).pose("tip")
    link2 = bodies.pose(q)["link2"]
    far_face = max(link2.faces(), key=lambda f: f.center().dot(
        Vector(*tip.position)))
    assert (far_face.center() - Vector(*[1000 * v for v in tip.position])).length < 1e-6, (
        far_face.center(), tip.position)
    # And the swept ranges are the description's joint ranges, not a box
    # typed here: the grid's limits move when mechanism.py's do.
    ranges = {j.name: j.range for j in bodies.TRUTH.description.joints}
    assert bodies.RANGES == [tuple(ranges[n]) for n in bodies.TRUTH.independent], bodies.RANGES
    print("  [PASS] envelopes ride on the engine's sites, over the description's ranges")


def test_poses_come_from_the_description_or_nowhere():
    def resolve_with(mechanism_src):
        """Resolve the truth model against a mechanism.py written to a temp
        model dir, below a ledger holding its one length, with every other
        mechanism.py dropped from sys.path for the duration, so a real one
        elsewhere cannot answer the case meant to test having none."""
        def resolve(model):
            saved = sys.path[:]
            if mechanism_src is not None:
                Path(model, "mechanism.py").write_text(mechanism_src)
            sys.path[:] = [str(model)] + [p for p in saved
                                          if not Path(p or ".", "mechanism.py").exists()]
            sys.modules.pop("mechanism", None)
            importlib.invalidate_caches()
            try:
                return bodies._resolve_truth(model)
            finally:
                sys.path[:] = saved
                sys.modules.pop("mechanism", None)
        return _in_ledger(_entry("mechanism.l", 0.3), resolve)

    pendulum = (
        "from armature import body, joint\n"
        "def mechanism(p):\n"
        "    return [body('bob', mass=1.0, com=(p['l'], 0, 0),\n"
        "                 inertia=[[1e-4, 0, 0], [0, 1e-4, 0], [0, 0, 1e-4]]),\n"
        "            joint('swing', 'hinge', parent='world', child='bob',\n"
        "                  axis=(0, 0, 1), point=(0, 0, 0), range=(-1, 1))]\n")
    assert resolve_with(pendulum).coordinates == ("swing",)
    # No mechanism.py anywhere: fatal, not a fallback to a pose computed
    # some other way - that would be the second forward kinematics.
    assert _raised(RuntimeError, resolve_with, None)
    # mechanism.py failing its own import is not the same as no mechanism.py.
    assert _raised(ModuleNotFoundError, resolve_with, "import definitely_not_a_real_module_xyz\n")
    print("  [PASS] poses from the description through the engine, no fallback")

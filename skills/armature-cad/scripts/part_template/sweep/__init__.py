"""
sweep — interference checking across a motion range, for the kinematics and
planning stages.

This runs BEFORE any part exists. The point is that a self-collision is a
kinematics finding, not a CAD finding: if the forearm hits the base post at
q2 = -2.4 rad, the fix is a joint range in `mechanism.py` or a link length
in the ledger, and the cheapest moment to learn that is while those are
still just numbers in a derivation. Learning it from a rebuilt assembly two
weeks later costs the rebuild.

So the bodies are deliberately crude — boxes and cylinders sized from the
link lengths already in the ledger's `mechanism` section. An envelope that is 20%
too fat is the right fidelity: it finds the collisions that matter and costs
nothing to write. Do not model features here. Where they sit at a posture is
not this package's to compute: each envelope rides on a site of the mechanism
description, posed by the engine's truth model, over the joint ranges the
description declares.

    bodies.py    the envelopes at home, their carrier sites, pose(), and the
                 pair excuses — replace these
    grid.py      the postures to sweep, and the grid's resolution
    summary.py   main(): sweep, summarize one row per pair, exit code
    report.py    prints the summary

Run it from `cad/parts/` (needs `check/` beside this package), in the
model's environment, which has the engine, plus build123d:

    uv run --project ../../analysis/model --with 'build123d~=0.11' python -m sweep
    uv run --project ../../analysis/model --with 'build123d~=0.11' python run_all.py sweep

Needs the ledger the model reads for the link lengths, and analysis/model/
on sys.path for mechanism.py's postures - and has no placeholder fallback for either
(see bodies._resolve_lengths and bodies._resolve_truth): a guessed length
or a hand-written pose could hide a real self-collision or invent one that
isn't there.

The worked example is the planar 2R arm from the armature-derive template,
with a base post it can fold back into. Replace the bodies and CARRIERS in
bodies.py with your mechanism; keep the shape of the package.
"""

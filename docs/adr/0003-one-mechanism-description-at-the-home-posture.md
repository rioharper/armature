# ADR 0003 — One mechanism description, written at the home posture, compiled for both sides

2026-10-11 — Status: accepted (retires the DH table and the `FLOATING_*` dicts as the way a mechanism is written down)

A project describes its mechanism once, in `analysis/model/mechanism.py`, as a
function `mechanism(p)` built from the engine's typed elements — body, joint,
site, cable, loop, contact, actuator — with every number written **in the base
frame at one home posture**: a joint as an axis direction and a point on it, a
COM, site, cable end or contact point as a position, an inertia in base axes.
Called with floats, it compiles through `mujoco.MjSpec` into the truth model;
called with SymPy symbols, it gives the derivation each body's frame and points
as functions of the coordinates. The derivation's simplifications are
**reductions** — `lock`, `couple`, `planar`, `lump`, `rigid` — grouped into named
**variants** that the derivation owns, each reduction carrying its numbered
assumption from `00_setup.md`. The truth model always compiles the full
description, and releasing an assumption compiles the variant with and without it.

Two obvious alternatives were rejected. The DH table is the textbook convention
and what derive's Milestone 1 note was built around, but it describes serial
chains only, so the template carried a second, incompatible format for floating
bodies, and between them the mechanism was re-read in six places. Ibex (two
five-bar legs on wheels) and CineWave V2 (two parallelograms) fit neither the
table nor the floating builder, which had no loops and no contact. Parent-relative frames, the URDF
and MJCF convention, describe every topology, but rotations compound down the
tree, so checking one number against a drawing means chaining transforms by
hand — and the first reader of a description is the red team checking it
against the spec's sketch. Written at the home posture, a number is checked
against the drawing directly, a loop visibly closes, and CAD's assembly
coordinates map onto it one-to-one.

The cost accepted: an error in the description itself is **common-mode**. The
derivation and the truth model both read it, so no truth check can see it. That
was already true of the chain builder, which compiled its model from the
derivation's own DH table, and the truth model's job is catching wrong
assumptions, which stay on one side as reductions. The description gets checks
of its own instead: validation at compile time that names the element at
fault, a Milestone 0 review artifact (a frames table and skeleton renders) the
red team reads against the spec, and the comparison against measured CAD bodies
once a project reaches CAD. Revisit if a description error reaches CAD or a
purchase despite all three; the next step is two independently written
descriptions, compared.

# ADR 0007 — Actuator and bus feasibility runs from spec §9, on a coarse description

2026-10-12 — Status: accepted (decides the actuator-and-bus slice of pipeline v2's "where feasibility lives"; replaces `spec-template.md:154-158`'s back-of-envelope rule for those checks, and §6.4's "motion profile TBD")

Spec §9 creates the project's one model directory. It holds:
- a coarse `mechanism.py`, with bodies from `armature.coarse`;
- the missions;
- the drive data.

`run_all.py` searches the drive margins (ADR 0006) and any margin written under
ADR 0005. §9 becomes a table of their worst-case rows, not arithmetic. Derive
refines the same files in place, so the margins re-run on the full description
(ADR 0003: one description). §6.4 states a mission wherever there are actuators.
An assumed mission, labelled as an assumption, is allowed; "motion profile TBD"
is not.

Purchases are decided from the spec, and sizing that waits for derive never runs
before them:
- Ibex never ran derive Milestone 3, and its map heads for "four-actuator order safe" from its spec.
- Plumb's Milestones 3 and 4 are unstarted.

Every actuator sizing in all three projects is §9 hand arithmetic, and that is
where both wrong torque constants lived. Overhaul 02 deferred wiring §9 to the
search until this decision.

Rejected:
- **Sizing in derive only.** It is the status quo, and it runs after the purchase.
- **A throwaway model for the spec.** That makes two descriptions, which ADR 0003 forbids.
- **A new feasibility stage between spec and derive.** It is one more hand-off, for the same files.

The cost accepted: the spec stage now needs uv and the engine. While the
engine's distribution is open (Overhaul 05), this works for a project running
the plugin in place (`--plugin-dir`), as Ibex's restart does, and not from the
version-keyed cache.

This ADR does not decide:
- electrical design beyond the bus: wiring, connectors, protection choices;
- safety (Overhaul 11);
- structure (Overhaul 09);
- whether §9's other checks, mass and energy, move to code.

Each is decided when its own overhaul is grilled.

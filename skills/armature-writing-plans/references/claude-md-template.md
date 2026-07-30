# CLAUDE.md template

Copy to the repo root and fill. Claude Code loads this into every session in this repo, which makes it the cheapest possible place to put the conventions that must not drift. Keep it dense — it is paid for on every turn.

Nothing goes in here that isn't law. Status, progress, and open questions live in `.armature/state.md`, which is read on demand; putting them here means paying for them every turn and watching them go stale.

---

```markdown
# <project>

<one-line pitch, from docs/concept-brief.md>

Architecture: <the one the trade study picked>
Spec: docs/spec.md · Plan: docs/plan.md · State: .armature/state.md

## Units

SI internally, always. Angles in radians in code, degrees permitted in prose
and drawings where labelled. Mass kg, length m, torque N*m, inertia kg*m^2.

## Coordinate frames

Convention family: <modified DH | standard DH | product of exponentials>
Handedness: right-handed. Vertical axis: <z-up | z-along-joint>

| Frame | Origin | Orientation | Notes |
|-------|--------|-------------|-------|
| {W} | <where> | <axes> | world, gravity is -z |
| {B} | <where> | <axes> | base, fixed to chassis |
| {J1}…{Jn} | <where> | <axes> | per-joint |
| {E} | <where> | <axes> | end-effector / tool point |

## Symbol table

| Symbol | Code name | Meaning | Unit |
|--------|-----------|---------|------|
| q | `q` | joint positions | rad, m |
| q̇, q̈ | `qd`, `qdd` | joint velocity, acceleration | rad/s, rad/s^2 |
| τ | `tau` | joint torques | N*m |
| m_i | `m_<link>` | link mass | kg |
| l_i | `l_<link>` | link length | m |
| c_i | `c_<link>` | COM offset along link | m |
| I_i | `I_<link>` | link inertia about COM | kg*m^2 |
| n_i | `n_<joint>` | gear ratio | - |
| g | `g` | gravity | m/s^2 |

Code names are legal Python identifiers and are what `analysis/<project>_model/params.py`
uses. A symbol that appears in a derivation and not in this table is a finding.

## Naming

Parts: `<PROJ>-<TYPE>-<nnn>` — types: LNK link, HSG housing, BRK bracket,
        PLY pulley, SHF shaft, PLT plate, ASM assembly
Native CAD: `<PART-ID>.<ext>` — no rev in the filename. Assemblies and
        drawings reference parts by path, so renaming on every revision
        detaches the tree from itself. Git holds the history.
Exports:   `<PART-ID>_<rev>.<ext>` — rev as `r01`. These leave the repo for
        a shop or a slicer, where there is no git history to consult.
        STEP AP242 for machining, STL for print, DXF for sheet, PDF drawing.
Branches: `phase/<n>-<slug>`
Tags: `freeze/<project>-<what>`, `phase/<project>-<n>-complete`

## Definitions of done

Task — exit criterion in docs/plan.md met, work committed, plan checkbox ticked.
Phase — every task closed or explicitly killed, phase tag applied, red-team
        findings resolved or accepted in writing.
Project — every Must REQ traced to a passing verification test.

## Analysis invariants

`pytest` from `analysis/` is green before any freeze is tagged or milestone
closed. Numbers that drive decisions trace to `docs/bom.yaml`; numbers in
`bom.yaml` with a `params_key` must equal their counterpart in `params.py`.
```

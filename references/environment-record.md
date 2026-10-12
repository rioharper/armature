# The environment record

A project's `docs/environment.md` is its **environment record**: what the
machines this project is built on actually have installed, dated, one section
per machine. `init` writes it; `armature-plan` refreshes it. Every other stage
reads it.

It exists because a tool's absence changes a plan. A missing SciPy is hours in
Phase 0 and a blocked derivation milestone; a machine with no CUDA cannot train
what the spec asked for, whatever the schedule says.

## Running the probe

`scripts/env-probe.sh` (in the plugin, run it from there) prints `KEY=VALUE`
lines and exits 0 whatever it finds.

```bash
bash "<plugin>/scripts/env-probe.sh"                    # core only
bash "<plugin>/scripts/env-probe.sh" ros2 gazebo cuda   # core plus a tier
```

**Core**, always: the working python invocation and whether SymPy, SciPy,
NumPy and MuJoCo import under it; `uv`, `git`, `gh`; host, OS, bash, WSL.

MuJoCo is core rather than a tier because **armature-derive**'s truth model is
built on it — a machine that cannot import MuJoCo cannot run a derivation
checkpoint at all, whatever the spec names.

**The tier** is whatever the project's own spec names — a ROS 2 distro, a
simulator, CUDA, a target board's toolchain. Each argument adds a check;
`ros2`, `colcon`, `gazebo`, `cuda`, `wsl`, `pinocchio` and `solidworks` have
real checks, and any other name falls back to `command -v` plus `--version`, so
a spec can name a tool the script has never heard of.

No skill uses `pinocchio`: the truth model is the engine's, and the engine is
MuJoCo only. The check stays for a spec that names Pinocchio for work of its
own; there is no Windows pip wheel, so it arrives by conda or WSL or not at all.

Read `PYTHON` as the invocation that works, not as a yes/no: a machine whose
python answers to `py` and not `python` is the case this whole record exists to
catch. A module reads `absent` when it is not installed and `error: <Type>`
when it is installed and will not load — send someone to fix the second, never
to install it.

## Writing the record

The script prints; you write. Judgement is the half a script cannot do: which
absences matter for *this* project.

```markdown
# Environment

<!-- Written only by a run of the plugin's scripts/env-probe.sh, never by hand.
     One section per machine. Re-probing a machine replaces its section. -->

## RioLaptop — Windows 10.0.26200 · probed 2026-09-10

| Tool | Found |
|---|---|
| python | `python` 3.14.7 |
| SymPy / SciPy / NumPy | 1.14.0 / 1.18.1 / 2.5.3 |
| MuJoCo | absent |
| uv / git / gh | 0.12.12 / 2.55.0 / 2.100.0 |
| WSL | Ubuntu-24.04 |
| ROS 2 / Gazebo | absent / absent |

**Gaps that matter here:** MuJoCo is absent, so every **armature-derive**
milestone checkpoint fails at its truth check until it is installed — `pip
install mujoco` is Phase 0's first task. ROS 2 and Gazebo are absent and Phase 1
is entirely simulation, so installing them is Phase 0 work, not a footnote.
```

Three rules hold it together:

- **Only a probe run writes it.** Correct a wrong line by re-running the probe,
  never by editing the file. A hand-edited record is how a note outlives the
  machine it described.
- **One section per machine, replaced not appended.** The heading carries
  hostname, OS and the date probed. Re-probing a machine rewrites that machine's
  section; probing a second machine adds a section beside it, which is how a
  project that needs a sim host, a render host and a target board accumulates
  the evidence its machine split rests on.
- **A gap never blocks.** The probe records and returns; what an absence costs
  is the calling skill's call — `init` reports it, `armature-plan` turns it into
  a task with hours against it.

## Refreshing it

`init` runs core and seeds the file. **Every `armature-plan` invocation
re-probes**, including a re-plan at a phase gate, and rewrites this machine's
section with today's date — so a record is never older than the last time
anyone planned against it.

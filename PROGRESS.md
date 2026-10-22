# Progress Log

<!-- Newest entries first. Start here when resuming this project. -->

## Overhaul 07: built — 2026-10-21

**Status:** #155–#160 built and merged on `overhaul-07`, not yet on `main` or pushed. The CHANGELOG's *Unreleased* holds one breaking entry for 07, with the choices each ticket made that #154 left open. #154 closes after the release run.

**Done:**
- **#155 the gate engine, #156 the red team's block and recheck mode, #157 `buy`, #158 the hook and launcher, #159 the skills.** The #158 manual run (Git Bash and the PowerShell fallback) and #159's 73-call dry walk are in the session notes, and the CHANGELOG has their findings.
- **#160:** `CONTEXT.md` gains Gate, Order record, Waiver, Recheck and Stamp, and Stage loses the `Stage:` line. The README's red-team line becomes the two gates and the hook. `grep -rn "Stage:" CONTEXT.md README.md skills` finds nothing.
- **The eval scaffold** puts its project on `main` and ignores `.armature/`. It also excludes the sandbox's masked dotfiles in `.git/info/exclude`. `evals/tests/test_scaffold_gates.py` (slow) holds all three, and holds that the copy's launcher leaves no venv and no hard link.
- **On-demand run** (WSL, `claude` 2.1.301, at `54146f4`), `spring-cable-derive` and `spring-cable-review`, one run each, both scored after both finished. Both were caught 1/1 with 0 peeks, for $2.83 + $0.59. `red-team-dispatched` was 1/1 on the derive case and 0/1 on the review case, which reviewed by itself and loaded no skill. No file in the copy had a second link after either case.

**Bug found by the run, fixed here:**
- The sandbox lays `.bashrc`, `.claude/`, `.mcp.json` and ten more over the workspace, and `git status` lists them untracked.
- The gate therefore never stamped the model, and the hook denied the derive case's merge twice with `fail stamps`.
- The agent's own `| grep -v bashrc` hid that line, so it reported "the merge gate passes" and stopped unmerged.
- The catch graders never saw any of it. The fix is not yet confirmed by a live run; the release run will show it.

**Learned:**
- Hooks run outside the sandbox with network. The first `git` call in a run built the launcher's venv under the run's `config/plugins/data/armature-inline` in time. The sandboxed skill call through the launcher then worked.
- A sandboxed `git add -A` fails on the masked `.bash_profile` ("can only add regular files"). The exclude fixes that too.

**Left before the pre-CAD pipeline is finished:**
1. **The release run**, on the version-bump commit, after `overhaul-07` merges to `main`. It covers 06, #147 and 07. Expect about $117 and 259 min, and score only after every case has finished. It reports #147's Δ, and `red-team-dispatched` against 12/27 before. Check the derive cases' traces for a hook denial, since no grader sees one.
2. **Ibex's hand edit** when it picks up the release: seed `ledger.toml`, and swap its CLAUDE.md lines for init's `gate status` line.
3. **The open pipeline-v2 decisions:** plan vs map, where safety lives, and where controls and electrical live.
4. **Overhaul 10**, symbolic vs numeric, before Ibex reaches derive Milestone 2.
5. **Ibex's spec, on the released plugin.**

**Open from 07:**
- The `ask` prompt has only been seen as a `-p` refusal. Run one interactive confirmation by hand.
- A real machine with no Git Bash has not been tried.

## Overhaul 07: designed and ticketed — 2026-10-21

**Status:** Grilled in three rounds of 24 questions. All recommendations were accepted, plus ten items settled at confirmation. Recorded as:
- ADR 0011 (`3da75a3`, committed locally; the push was blocked, so it needs a manual `git push`), which also amends ADR 0010;
- spec **#154**, labelled `ready-for-agent`;
- tickets **#155–#160** as its sub-issues, with native blocked-by edges.

No plugin code has changed.

**Decided:**
- **The Stage line goes.** "Stage" stays a word for a pipeline step.
- **Two gated actions:**
  - `merge`, a work branch into `main`;
  - `buy`, the merge of an `armature/order-<name>` branch that adds `docs/orders/<date>-<name>.toml`. A CAD release is an order with `kind = "release"`.
- **`armature.gate` is a stateless engine verb.** `run_all` results are cached by content in a gitignored `.armature/`.
- **Reviews** pin a commit SHA and end in a TOML block of findings. A BLOCKER or MAJOR closes on one of three things:
  - a kept check, in `review_<date>_<artifact>_checks.py`;
  - a recheck, which is its own file;
  - the user's acceptance.
- **Waivers** live in a root `waivers.toml`.
- **The plugin hook** is the backstop for the skills:
  - On `Bash|PowerShell`, it verifies git merges, commits on `main`, `gh pr merge`, and pushes to `main`.
  - It denies writes under `.armature/`.
  - It asks the user before an edit writes `accepted`, `confirmed` or a waiver.
  - It runs the plugin's own engine, with its venv in `${CLAUDE_PLUGIN_DATA}`, and acts only where a root `ledger.toml` exists.
- **No git hook.** The user's own terminal is never policed.
- **One release run** after 07 lands replaces the pending one. It covers 06, #147 and 07.

**Order:**
- #155 (the gate engine) and #156 (the red team) have no blockers.
- Then #157 (`buy`) and #158 (the hook).
- Then #159 (the skills).
- #160 (docs and evals) comes last.

**Flagged:**
- Ibex needs a one-time hand edit: seed `ledger.toml`, and swap its CLAUDE.md lines.
- A shell edit to `ledger.toml` gets past the `ask`.
- `import armature` loads MuJoCo, so the hook path must avoid that.
- The release is breaking.

**Left before the pre-CAD pipeline is finished** (this replaces item order 1–2 of the entry below):
1. #155–#160.
2. The single release run.
3. The open pipeline-v2 decisions, Overhaul 10, and Ibex's spec, as listed below.

## What's left before the pre-CAD pipeline is finished — 2026-10-21

**Status:** Overhauls 01–06 are built, merged to `main` and pushed. #147's traps are on `main` (`30d13da`). Of the eleven review candidates, three that sit before CAD (07, 10, 11) are not designed, and three pipeline-v2 decisions are still open. Nothing since 2.0.0 is released, so Ibex's cached plugin has neither the ledger nor the new traps. Ibex restarted on 2026-10-16 (brief Rev 1.0, staged to spec) and has not moved since. Its spec is the acceptance test.

**Done since the last entry:**
- **Overhaul 06, the ledger:** #140–#146 built, and #139 closed 2026-10-21. The integration branch was fast-forwarded to `2f29e17`, with the code review's fixes. The choices the build made are in the CHANGELOG's *Unreleased* section.
- **#147, three traps that survive a passing `run_all.py`:** #148–#151 closed. On-demand wiring runs at `30d13da` caught all three cases 1/1 with 0 peeks. `red-team-dispatched` and `skill-derive` were 1/1 on each.

**Left, in order:**
1. **The release run.** Editing derive, spec, CAD and the agents re-gated it (`evals/README.md`). Expect about $117 and 259 min. The run does three jobs:
   - It gates the version bump.
   - It reports #147's Δ, which closes #147 and #137.
   - It re-runs the three derive cases that #138's advisory run never reached. `699e583` is the fix, and `spring-cable-derive` already went 0/3 → 3/3.

   Score only after every case in a copy has finished. `uv run --project engine` leaves a hard-linked `engine/.venv` in the copy, and later cases then refuse at $0.
2. **Overhaul 07, gates instead of the Stage line.** Not grilled. The red team's own rule is "always before CAD hours or purchases", so this is the gate pre-CAD work ends at. Undecided: which actions gate, what evidence each needs, where a review's checks live, and how a project argues an exemption. The ledger now provides the data the gate needs (`status.candidate-cited`, budget margins).
3. **The open pipeline-v2 decisions.** Each one gets a grill, an ADR, a spec and tickets.
   - **Plan vs map:** reopens ADR 0001. Ibex and Plumb both used a map in place of a plan.
   - **Where safety lives:** Overhaul 11's hazard rows per energy source go here. Its inputs now exist: the mechanism (01), the bus model (03) and battery and spring entries in the ledger (06).
   - **Where controls and electrical live, beyond the actuators and bus.** ADR 0007 settled only the actuator-and-bus part of "where feasibility lives".
4. **Overhaul 10, symbolic vs numeric.** The 2026-10-11 order put it with CAD, but it is a derive-stage problem. The Lagrangian import timed out after 240 s at four links. Ibex's two five-bar legs, wheels and floating base are far past that, so settle it before Ibex reaches derive Milestone 2.
5. **Ibex's spec, on the released plugin**, writing into `ledger.toml` from the start. It is the acceptance test for 1–4. Treat its findings as plugin feedback.

**Loose ends (not blocking):**
- Glossary clashes: "slack" means both a margin's room and a slack cable, and `Envelope` clashes with "envelope".
- `Simulated.moved.speed` jumps about 28 rad/s at a cable snap.
- `load()`'s nearest-`ledger.toml` lookup was not grilled, and the copy steps leave the template's file behind.
- `py -m armature.ledger` works only once spec §9 has pinned the engine.
- The Pinocchio, Placo and CalculiX environment decision (pixi or micromamba beside uv) is still open. #62's Pinocchio backend has never run on this machine.
- `engine/MUJOCO_LOG.TXT` is untracked and not ignored.

**Not pre-CAD:**
- Overhauls 08 (geometry → bodies) and 09 (loads and structure checks). These wait for Ibex to reach CAD.
- Eval measurement: #152, the red-team with/without comparison (blocked by #138), and #153, the bare baseline. #153's arm probe needs the user's go-ahead or a hand run.
- Plumb and CineWave V2 stay deferred.

## Overhaul 06: designed and ticketed — 2026-10-20

**Status:** Grilled in two rounds of 23 questions, all recommendations accepted. Written up as:
- ADR 0010 (`9558ad4`, pushed);
- spec **#139**, labelled `ready-for-agent`;
- tickets **#140–#146** as its sub-issues, with native blocked-by edges.

The #138 commits went out first (`02a7f05..699e583`). No plugin code has changed yet.

**Decided:** one root `ledger.toml` holds every input number.
- **Entries:** sections `mechanism`, `drive`, `req`, `budget.<kind>` and `part.<pn>`. Values are SI (°C for temperatures), with `as_written` checked by pint.
- **Provenance:** six source kinds (chosen, standard, estimate, datasheet, cad, measured), and a `candidate`/`confirmed` status kept separate from them.
- **Bands and references:** an estimate must carry a band. Budget lines are `of` references.
- **Machinery:** `armature.ledger` in the engine, with the verbs load, check, show, render and set.
- **Views and params:** the budgets, BOM, requirements and `CONTEXT.md` symbols become marked sections that `render` writes. `params.py` keeps only structure, with no literals.
- Spec #139 holds the full contract.

**Corrections to the 2026-10-11 review:**
- "Names written three times" is false now (`symbolic.py:74`).
- The new copy is `coarse_2r/params.py:54-59`.
- Ibex has restarted, and its index is 433 words. Plumb's is 6,496.

**Order:**
- #140 (the engine module) has no blockers.
- Then #141 (template) and #143 (render and views) in parallel.
- Then #142 (golden mechanisms, after #141), #144 (skills and agents, after #143) and #145 (CAD, after #141).
- #146 (docs) comes last.
- The whole of it re-gates the next release.

**Flagged:** `load()`'s nearest-file lookup was decided while writing the spec, not grilled. The template and each golden mechanism carry their own `ledger.toml`; the copy steps leave the template's behind, and the scaffold places the golden's at the project root.

**#138's advisory WSL run** (started before this session's `/clear`, on `699e583`):
- `spring-cable-derive` went from 0/3 to **3/3** on both `red-team-dispatched` and `skill-derive`.
- The other three cases never ran. A uv `engine/.venv` built inside `~/armature-eval-138` during the first case left hard links in the plugin copy. `claude plugin eval` then refused each later case: "a file in the plugin has more than one name (a hard link)".
- #138 is still open. Before it can close, the venv has to come out of the plugin copy and those three cases need a re-run.

**Next:**
- #140.
- #138's re-run, then #137.
- Restart Ibex once #144 lands, so its spec writes into the ledger.
- `engine/MUJOCO_LOG.TXT` is still untracked.

## Catch-up: Overhauls 03–05 and the 2.0.0 release — 2026-10-20

**Status:** **2.0.0 is released.** The bump commit `02a7f05` is tagged `v2.0.0`, pushed with `--atomic`, and `evals/release-smoke.sh v2.0.0` passed. `main` matches `origin/main`. The only open issues are #137 and #138. This entry was written after the fact from git, the issues' closing comments and session notes. Entries were not kept between 2026-10-13 and today, so the issues' closing comments hold the detail.

**Overhaul 03, mission sizing (spec #83):**
- **Built and closed:** #84–#91, closed by 2026-10-13. #91 (`c9b3ead`) writes the drive rules once, in `derivation-standards.md` § *Actuators and the bus*.
- **The #90 friction** (the entry below) became the engine-gap epic #92, with #93–#101 under it. All were built in parallel worktrees, pushed (`18b0119`) and closed on 2026-10-15.
  - **#93** adds "capacitance needed". Under #96, that became the least C at which nothing trips (`bb6ba9e`).
  - **#96:** a tripped driver latches and coasts. Peak V is `Margin(strict=True)`, which passes only above 0, and ADR 0005 is amended to match.
  - **#98:** the actuation seam is now `actuation(state, qdd, loads, *, t, p)`, and `Mission(transmission=...)` is public. This is breaking.
  - **#100:** the template's search keeps a cut budget, `Budget(64, 3, 100)`. The stop mission's capacitance needed moved from 2.264 to 3.582 mF because the search is stricter. That is not a bug.
  - **Not built, on purpose:** clamp headroom in W, the second half of #97.
- **#102, cable slack:** built as `98e6eef` and `a0b5436`, and closed 2026-10-15.
  - A cable that only pulls (the `pulls` element) goes slack in an event, and snaps taut as a plastic impulse.
  - The new outputs are `Run.slack` and `Run.snaps`.
- **Still open from Overhaul 03:**
  - "slack" now means both a margin's room and a slack cable. This is a glossary gap.
  - `Simulated.moved.speed` jumps about 28 rad/s at a snap.
  - `Envelope` clashes with the glossary's "envelope".

**Overhaul 04, golden mechanisms (map #103, ADR 0008, spec #113):**
- **The map:** charted 2026-10-15. Decisions #104–#112 were accepted in full. ADR 0008 (`f9c3459`) reverses #48's single test seam.
- **Tier 1:** the golden projects live in `engine/tests/golden/`, with `answers.py` beside them.
  - #114–#118 covered the 2R arm, the cable platform, the spring and cable, the five-bar, the parallelogram and the wheel leg.
  - #119 is the verb matrix as data, with its test.
- **Tier 2:** the eval harness, plus derive and red-team cases on WSL2 (#120–#123).
- **Engine bugs found:**
  - **#126:** Powell's polish missed worsts on a face. Fixed in `245333f`.
  - **#127:** closed chains failed on Linux, where mujoco's enum `==` against a numpy int32 is False. Fixed in `b0e38f3` and `5419658`. The Windows suite can't see Linux-only bugs, so run the engine suite on WSL before trusting a tier-2 run.
- **#124, the first release run:** 7 of 8 cases caught at least 2/3. The follow-ups were:
  - #128: the eval's copy of the plugin holds no `engine/tests`;
  - #129: a user's review request routes to the red team;
  - #130: no peek is counted on a path the agent only excluded;
  - #131: every case has an unstated-bait variant.
- **#125, docs:** the release gate is written once, in `evals/README.md`, and `CLAUDE.md` points at it.
- **#132, the hold-out:** a sixth golden mechanism, the geared turret. Its trap is the bearing's moment. It is frozen and never gates. Merged as `00b16b3`.
- **Closed:** everything from #113 through #132.

**Overhaul 05, engine distribution (ADR 0009, spec #133):**
- **The decision:** projects pin the engine by git tag, `{ git, tag = "vX.Y.Z", subdirectory = "engine" }`, and commit `uv.lock`. The engine, plugin and marketplace versions move in lockstep under one tag. Between releases a project pins a `rev`, never a committed local path. A failed smoke test means a patch release, never a moved tag.
- **#134:** `scripts/engine-source.sh pin|check` (`5a2f119`). Its error exits are 2.
- **#135:** the lockstep test, plus `evals/release-smoke.sh` (`63e405f`).
- **#136:** docs. Derive Step 0 pins the engine by tag, and the derive checkpoint and `init` both check it. On a `path` source, the checkpoint stops and offers `pin`.

**The 2.0.0 release run:**
- **Gated cases:** all 16 caught 3/3 each. It took 222 min and cost $100.26.
- **Environment:** WSL distro `Ubuntu-24.04`. That is not the `Ubuntu` 26.04 that `evals/README.md` names.
- **Baselines:** every no-plugin baseline also caught 3/3, a Δ of +0.00. `--scaffold` runs in both arms, so the no-plugin arm already has the engine and a `run_all.py` that reads the answer out. Filed as **#137**.
- **Red-team dispatch:** it ran on only 12 of 27 derive runs, because derive has no review rule for a plan task that lands as a report. Separately, spring-cable-derive never loaded the skill. Both are **#138**, which should be settled before #137 measures the review.

**What reaches projects:** the user's projects run the version-keyed plugin cache, so a plugin update now brings them the whole overhaul.
- A project on 1.3.0 has no engine.
- A project that followed the old derive Step 0 has a `path` engine source. The checkpoint stops on it, and `pin` repairs it.

**Next:**
- #138, then #137.
- Restart Ibex on pipeline v2. Plumb and CineWave come later.
- **Loose end:** `engine/MUJOCO_LOG.TXT` is untracked and not ignored.

## Overhaul 03: #90 acceptance run — 2026-10-13

**Status:** Both acceptances ran on read-only scratch copies, made with `tar --exclude=.git --exclude=.venv --exclude=__pycache__` into the session scratchpad (`acc90/`, not durable). The engine ran from `engine/`'s uv env, at `main` `d8d3699`. Nothing in either project was patched. `git status --porcelain` was empty in Plumb (`e3c010f`) and Ibex (`a2c0850`) before and after. Neither number lands within 10 % of the figure #90 states. Each difference is explained term by term below. The issue was not commented on or closed.

**Plumb F5.** Expected about 128 W into one winch, against 113 W of flux capacity. **Found 86.7 W, a single cable paying out**, which passes with 26.1 W of slack.
- **The wrapper:**
  - **The mechanism** is coarse: the platform's point on three slides, x, y and z, inside `ROOM_ENVELOPE`. Each slide's range is 1 cm wider than the envelope, and `Coordinates(..., within=envelope)` keeps the search inside it.
  - **The seam:** `actuation(state, qdd, loads)` calls Plumb's `distribute(p, I, m, a)` with a level platform, and its `cable_geometry`.
    - `l̇ = −u·ṗ` and `l̈ = −u·p̈ + (|ṗ|² − (u·ṗ)²)/l`.
    - Each winch gets `(T·r_d/N_b + rotor, −l̇/r_d·N_b, rotor)`, where `rotor = J_m·(−l̈/r_d·N_b)` and J_m = 5.6e-5 kg·m².
    - An infeasible tension law raises `Infeasible`.
    - The mass is read from `state.compiled.model.body("platform").mass`.
  - **The mission** is `move(p.state, direction=p.direction, distance=min(p.distance, the distance to the envelope's face), limits=Limits(v=2.0, a=0.5 g, j=100, along="path"))`.
  - **The space** is `Coordinates`, `Direction("sphere")`, `Interval(0.05, 3.0)` and `Band("m", (2.0, 2.5))`.
  - **The drive:**
    - The motor is the mj5208: `kt_from_kv(304, convention="sinusoidal")`, R 0.047 Ω per phase, wye, and `Thermal(4.55, 164.6, 80, 25)`.
    - The driver is the moteus: η 0.95 (assumed), i_peak 100 A_peak, and `FluxBrake(i_d=40 A_peak)`.
    - The belt is `Gearbox(0.95)` with N_b = 5, and r_d = 0.03075 m.
    - The source is `Source(sinks=False, p_max=1512, overvoltage=27.6)`, and the capacitance band is (0.5, 4) mF.
    - Rev 1.1 runs at 24 V, with flux onset at 25.5 V and the max at 26.5 V. Rev 1.3 runs at 22 V, with flux onset at 23.5 V, a 1 Ω brake at 24.4 V and the max at 27.0 V.
  - **The F5 margin** is the wrapper's own `Margin`: 112.8 W (i_d²·R_φ in d-q) minus each winch's largest `−electrical(...).bus`. Its truth runs at 1 kHz.
- **The output:**
  - The search took 81 s and 1,940 evaluations, with 352 rejected (190 by the tension law, 162 by starts on a face moving out). The worst is +26.1 W, and its truth agrees within 1.13 W.
  - **The worst move:**
    - It starts at (0.534, 3.431, 1.9) and runs 1.50 m along (0.690, −0.724, 0), at 2.5 kg.
    - It is at the workspace ceiling, decelerating, with |v| = 1.88 m/s at t = 0.80 s.
    - Winch w4 pays out at 52.4 N and +1.816 m/s, giving 95.1 W mechanical and **−86.7 W on the bus**.
    - w1, w2 and w3 all reel in, drawing +15.4, +38.0 and +12.1 W.
    - The move's direction dotted with w4's payout direction is 0.966.
  - `margins()`, over {rev1.1, rev1.3} at a quick budget, takes 38 s. The bus peak V is **+1.00 V** on Rev 1.1 and **+3.50 V** on Rev 1.3, the gap between each one's max and its flux onset. The four drivers' flux brakes hold the bus at onset, so the peak V passes on both.
- **Term by term,** 128 → 86.7 W (×0.678):
  - **Tension, ×0.873.** The tension is 52.4 N where F5 assumed the 60 N ceiling. The law's λ midpoint never puts a paying-out cable at the ceiling here.
  - **Cable rate, ×0.726.** The cable rate is 1.816 m/s where F5 used 2.5 m/s. §6.4 caps the platform at 2.0 m/s, a cable's rate is that speed's projection on the cable, and 2.5 m/s is the winch's speed band, not a mission speed.
  - **Conversion, ×1.069.** It is 0.912 here against F5's 0.853. That is η_b 0.95, the driver's 0.95 and the copper loss, with the rotor's deceleration returning its energy on top.
  - **The product** is 0.873 × 0.726 × 1.069 = 0.678.
- **The bus.** F5's comparison of one winch against one flux brake also omits two things. Every driver's flux brake absorbs from the one shared bus, so the capacity is about 451 W. And the other three winches draw about 65 W at the same instant, so the net regeneration into the bus is only about 21 W.

**Ibex braked touchdown, pack unmated.** Expected 4.5 mF to hold 44 V. **Found 3.22 mF on Ibex's own lossless assumptions**, and 1.55 mF with the RobStride's copper loss.
- **The wrapper:**
  - **Ibex's trajectory.** The wrapper calls Ibex's own `dynamics.touchdown.simulate(zeta_tyre=DYN.zeta_tyre)`, the D3/D9 call. In-process, it records the `solve_ivp` that `simulate` calls, which captures `sol` and the rhs's closure `forces(y)`.
    - Recomputed, this gives 3.369 J and a 91.4 W peak, matching `simulate`.
  - **The mechanism** is body and foot on two vertical slides, `zb` and `zu`.
    - `follow(q, 0.25 s, qd, qdd)` carries Ibex's z_b and z_u, with accelerations from `forces`.
  - **The seam** rebuilds y from the state and calls `forces(y)[3]`, which is F_a per leg. Each hip gets `hip_torque_per_leg_force(L, 0)·F_a` and `hip_rate_per_leg_rate(L, 0)·L̇`, motor side through N_g = 7.75.
    - The trace's hip shaft power is −91.4 W at its peak and 3.370 J in all.
  - **The RobStride 02:**
    - `Kt(1.22, per="A_rms", side="output")` and `Ke(9.6, per="V_rms/krpm", between="line", side="motor")`. These pass the Kt–Ke cross-check.
    - `Resistance(0.55, between="line")`, wye, and 23 A_peak.
    - Its driver trips at 60 V and 12 V.
  - **The wheels** are two mj5208s on moteus drivers with `max_voltage` 44 V, idle. They make 44 V the lowest trip on the bus.
  - **The bus** is `Source(v=33.6, sinks=False, p_max=1e-6)` with hotel 27 W.
  - **The capacitance** for 44 V is bisected on `charge(...).peak`.
- **The output, term by term:**

  | Step | C for 44 V |
  |---|---|
  | Ibex eq. (59)–(60): ramp from 2E/T over 66.7 ms, less 27 W; E_net 1.809 J | 4.48 mF |
  | Ibex's own simulated power profile, less 27 W, energy only; E_net 1.280 J. **The ramp shape, ×0.71** | 3.17 mF |
  | The engine, ideal drive (R → 0, η = 1), on the same profile; +1.6 % from 1 kHz sampling | 3.22 mF |
  | + copper loss at R_φ 0.275 Ω: 1.25 J of the 3.04 J to 66.7 ms; peak 3.71 N·m per hip, 5.3 A d-q | 1.55 mF |
  | + gearbox η_b 0.9 (assumed; unpublished) | 1.27 mF |
  | + driver η 0.95 (assumed) | 1.10 mF |

  Ibex states its 4.5 mF as a bound. On its own lossless terms the engine gives 3.22 mF. The gap is eq. (59)'s ramp, which front-loads the power that Ibex's simulated profile builds gradually.
- **`margins()` on a (0.3, 10) mF band:**
  - The bus peak V is −28.8 V at 0.3 mF, and its truth agrees.
  - The bus minimum V and the source power both fail by construction. With no pack, the 27 W hotel load drains the bus.

**Friction for #91:**
1. **No margin returns "the capacitance needed"** (#83 user story 7, flagged in #88). The wrapper bisected `charge()` 60 times per case.
2. **No source cannot be stated.** `Source.p_max` must be > 0, so "pack unmated" became a 1 µW non-sinking source. The minimum V and source-power margins then fail by construction.
3. **There is no bus-level voltage rating.** Examples are the power board's 44 V and the capacitors' rating. The wrapper had to put the moteus wheels on the bus so that their `max_voltage` became the trip.
4. **The actuation seam gets no time and no params.**
   - A followed q(t) whose forces come from a project's own simulation needed the foot added as a second slide, so the seam could rebuild the project's state.
   - Plumb's mass came from the raw `MjModel`.
5. **No per-actuator regeneration margin exists.** F5's own quantity is one winch against its own flux brake, and the wrapper had to build it as a `Margin` from `trace` and `electrical`.
   - The bus peak V saturates at the clamp level. At +1.00 V on every point that reaches onset, it cannot rank regen events or show the remaining clamp headroom in W.
6. **Moves that leave the envelope.** Nothing keeps a searched move inside an envelope, so the wrapper clipped the distance to the face.
   - A move ending exactly on a slide's range face raised `ValueError` (0.4999999999999999 outside (0.5, 3.5)), not `Infeasible`. The fix was 1 cm wider ranges plus `within`.
7. **An infeasible tension law** had to become `Infeasible`. `search.py` says a design failing should be a number, which leaves it unclear.
8. **Project functions return summaries only.** Ibex's `simulate` keeps no trajectory, so the wrapper reached it by recording `solve_ivp` in-process. Derive should keep the q(t) behind a sizing number.
9. **Unpublished efficiencies.** Gearbox and driver efficiencies are required numbers with no "unknown" route. The RobStride's and the moteus's are unpublished, so they were assumed.
10. **The trip is not modelled.** A RobStride trip at 60 V does not stop its regeneration in the bus model, so the peak climbs to 72.8 V at 0.3 mF. Ibex calls voltages above 60 V "arithmetic".

## Overhaul 03: designed and ticketed — 2026-10-12

**Status:** Grilled in four rounds (26 questions, all recommendations accepted). It is recorded in three places:
- **ADR 0006:** actuators and the bus are sized from a mission, by one engine module.
- **ADR 0007:** actuator and bus feasibility runs from spec §9, on a coarse description. This is the actuator-and-bus slice of pipeline v2's "where feasibility lives".
- **Spec #83** (`ready-for-agent`), with tickets #84–#91 as its sub-issues and native blocked-by edges.

Both ADRs are new, uncommitted files. No engine or template code has changed. Separately, #63 (the Plumb acceptance) was closed on 2026-10-12, which no entry below records.

**Decisions** (the spec has the detail):
- **The module.** `armature.drive`. It covers actuators plus one shared bus. The source is a voltage band that can or cannot sink, capacitance is a band, and the sinks are a brake resistor, flux braking (whose heat goes into the winding) and the pack. Hotel load is a constant, and there is no state-of-charge model.
- **Missions.** A mission is moves (ruckig), holds and events, plus a duty cycle. Moves and holds become torque through `inverse`. Events run on a copy of the model with `implicitfast`, with coast, short and flux-brake as joint damping.
- **The electrical model.** Our own and quasi-static, in Lee's conventions.
  - Every constant's basis is a required keyword.
  - Kt is cross-checked against Ke and against a published torque–speed curve.
  - Gearbox efficiency is a forward and a backward band.
- **Rejected:** MuJoCo `dcmotor`. Its supply is ideal, it applies efficiency symmetrically, and its multi-input controller sets `nu = 3`, which breaks the engine's actuator count.
- **The margins** are generated and searched:
  - Peak margins search over move endpoints and event trigger times.
  - Thermal and energy margins run the named missions as written.
  - The truth check is a resolution check.
  - A margin with missing data is UNCHECKED and fails, unless the project lists it in `DRIVE_EXEMPT`.
- **Spec §9** creates the one model directory, with a coarse mechanism. Derive refines the same files.

**Ticket order:**
- #84 (drive data and the electrical model) and #85 (missions and the inverse path) have no blockers and can run in parallel.
- #86 (the bus) needs #84.
- #87 (events) needs #85 and #86.
- #88 (margins) needs #85, #86 and #87.
- #89 (template) and #90 (Plumb and Ibex acceptance) need #88.
- #91 (docs) needs #89 and #90.

**Flagged, not grilled:**
- **The actuation seam** (`actuation(state, qdd) → {actuator: (τ, ω)}`) was found while writing the spec. The engine's `actuator` drives joints only, so Plumb's winches need Plumb's own tension distribution.
- **Constants chosen while writing:**
  - a 2 % tolerance between Kt and Ke;
  - 200 Hz to search and 1 kHz to confirm;
  - a 0.1 K periodicity test;
  - matplotlib for the review plots.

**Evidence:**
- **The project survey** (read-only) found:
  - no sizing over a trajectory in any project;
  - regen in all three;
  - both wrong-Kt errors were basis errors. Plumb's 9.55/Kv against its datasheet's 8.27/Kv may still be live in Plumb, which is deferred and left alone.
- **The probes** (scripts in `%TEMP%\armature-ovh03\`, which is not durable; #83's Further Notes has the figures):
  - `inverse` costs 190–220 µs per sample.
  - ruckig 0.19.4 and pint 0.26.1 install on cp314.
  - The bus model reached 222 V on 220 µF with no brake, and held 30.2 V with an 8 Ω brake.
- **Stale facts:** the engine runs mujoco 3.15.0. Notes below that say "installed 3.13" describe the machine-wide `py`.

## Overhaul 02: #76–#82 built — 2026-10-12

**Status:** All seven tickets are built, each in its own worktree, merged into `main` (`438e8be`), and pushed. #75–#82 are closed, each with a resolution comment. The engine suite gives 510 passed, 4 xfailed in about 40 s, down from 47 s before #76 even with 76 more tests. The model template gives 36 passed, and `run_all.py` is green.

**What landed:**
- **#76.** Each `Compiled` owns one scratch `MjData`. On the 2R arm, `jacobian` costs about 30 µs and `inverse` about 100 µs. **The ticket's 50 µs is missed for `inverse`.** About 5 µs of it is MuJoCo; the rest is the NumPy in `_solve`. The test bounds `inverse` at 300 µs and also asserts each query costs less than half of one `MjData` allocation.
- **#77.** `sampler.unit_cube(...)` returns a `UnitCube` with `.axes`, `.d` and `.map(points)`. A rebuilt chain is mapped deterministically, and a pose outside the envelope is `Rejected`. Seeded `sample` output is bit-identical, except that a `rest_on` rejection no longer carries the value it drew and never read. The golden digests are specific to this platform.
- **#78.** `armature.search` provides `Margin`, `Budget`, `Space`, `Interval`, `Choice`, `Direction`, `Infeasible`, `search`, `Worst`, `Case`, and `pre_polish_at`. The polish bounds reach 0.05 past the unit cube, then clamp to the nearest face, because plain bounded Powell stalls at a face.
- **#79.**
  - `Band(param, bands)` is an `Interval`.
  - `Coordinates(mechanism, params, within, poses)` is read as `p.state`, and a space holds at most one.
  - A space compiles once at nominal and caches compiles by band values.
  - `Coordinates` has no `rest_on`, which is a one-line addition when it is needed.
- **#80.**
  - `search` runs `truth` itself and records the result as `Worst.truth: Confirmed`.
  - The template's `PARAMS` gained `tau1` and `tau2` as torque limits.
  - `HOLDING` and `SIGMA` are module-level margins, found by `run_all.py`; the layout gate requires `truth=` or `TRUTH_EXEMPT`.
  - `verification.py`'s grid and optimiser functions are deleted, which is a breaking change.
  - All five mutants fail a check.
- **#81.** See the entry below.
- **#82.**
  - `derivation-standards.md` owns the margin, band and `Worst`-row rules, including the friction #81 found.
  - The checklist, red-team agent, spec template, `model-layout.md`, `CONTEXT.md` and `CHANGELOG.md` point at those rules.

**Decided by the user:** #76's 100 µs `inverse` is accepted, with the miss noted on the issue; there is no `_solve` ticket.

## #81: acceptance, Plumb's tension floor and Ibex's skid reach — 2026-10-12

**Status:** Both findings reproduce with the search on local `main` at `39c9710` (#79). Nothing was patched. Both real projects were read-only: `git status --porcelain` was empty before and after, Plumb at `e3c010f`, ibex at `a2c0850`. The wrappers were in the session scratchpad and are not durable, so their essential lines are given below.

**Setup:** scratch copies of both projects made with `tar --exclude=.git --exclude=.venv --exclude=__pycache__`. A uv venv with Python 3.14.7, mujoco ~3.15, numpy, scipy and sympy. The engine ran read-only with `PYTHONPATH=<armature>/engine/src` and `PYTHONDONTWRITEBYTECODE=1`. Plumb pins mujoco 3.13, but its margin path imports only numpy and scipy.

### Plumb tension floor (spec rev 1.1, F1)

```python
def slack(p):  # largest_feasible_floor = distribute(t_hard=-inf).T_maxmin = max_min_floor (distribution.py:53)
    c = LOAD_CASES[p.case]
    return largest_feasible_floor(np.array([p.x, p.y, p.z]), EYE, p.m, c.accels[0], A_ROOM, B, c.ceil) - T_PREF
LO, HI = ROOM_ENVELOPE   # (0.5,0.5,0.4)..(3.5,3.5,1.9), platform level
space = Space(x=Interval(LO[0],HI[0]), y=Interval(LO[1],HI[1]), z=Interval(LO[2],HI[2]),
              m=Choice(M_P_CASES), case=Choice(("static",)))
margin = Margin("tension floor", slack, "N", over=space)
```

```
tension floor: -7.425545 N at x = 0.5, y = 2, z = 0.4, m = 2, case = static, FAILS; pre-polish -7.395334; coverage 33.0%; n = 1073, seed = 20261011; Sobol 256 (scrambled) + 8 corners + Powell from 3 (at most 300 evaluations each), for each of 2 combinations
  case m=2.0: T_maxmin 2.574455 N at (0.5, 2.0, 0.4)
  case m=2.5: T_maxmin 3.218069 N at (2.0, 0.5, 0.4)
```

The run took 0.27 s. Seeds 1 to 3 give the same value at the mirror point.

| Quantity | Review | Search, point platform | Search, 75 mm square (current) | Project's own figure |
|---|---|---|---|---|
| Worst T_maxmin, 2.0 kg | 2.5 N | 2.759 N | 2.574 N | low corner, level: 2.64 N |
| Coverage at 10 N, 2.0 kg | 25.8 % | 25.4 % (26.7 % at 8192 pts) | 24.6 % | R4.1: 22.1 % |
| Coverage at 10 N, 2.5 kg | 38.5 % | 44.1 % (43.8 % at 8192) | 41.4 % (41.0 %) | R4.1: 38.5 % |

The search differs from the review by more than 2 %, for three reasons, each checked:
- **The platform model.** The review used a point platform. The project's own `feasible_fraction` with b_i = 0 on its 13×13×7 grid gives exactly 25.78 % and 38.46 %.
- **Rounding.** The review rounded its floors down to 0.5 N steps. Doing the same reproduces all four of its named poses: 2.83 → 2.5, 2.76 → 2.5, 4.40 → 4.0 and 9.96 → 9.5.
- **What coverage measures.** The search's coverage is a volume fraction; the review's is a fraction of grid points. A dense 60×60×30 grid agrees with the search to within 0.4 points. `01_kinematics.md:148` notes that the grid fraction moves by whole rings.

**Where the worst lies:** at the midpoints of the low face's edges, (0.5, 2, 0.4) and its mirrors. The review names this pose ("at (0.5, 2, 0.4) also 2.5 N"). The corners alone found only the low corner, which is 0.07 N higher. Powell polished an interior Sobol point onto the edge. The hand-checked pose, the room centre, reads 12.36 N and passes.

**−∞:** the static case's 60 N ceiling never binds, on 0 of 115,351 grid points. Adding the `0.5g_up` case drives the worst to −∞ at (3.37, 1.92, 1.88) with m = 2.5. That combination's polish stopped and the other cases stayed finite, as designed.

### Ibex skid reach (spec rev 1.3 F2; derive rev C F1)

```python
FALL = {"forward (knee A)": 0, "backward (knee B)": 1}
def slack(p):  # skid_reach_needed = dynamics/falls.py:23; DYN.skid_reach = 205 mm
    return (DYN.skid_reach - skid_reach_needed(p.L0, p.alpha)[FALL[p.fall]]) * 1e3
space = Space(L0=Interval(NOMINAL.L0_crouch, NOMINAL.L0_full),        # 140..240 mm
              alpha=Interval(-NOMINAL.alpha_max, NOMINAL.alpha_max),  # ±20°
              fall=Choice(tuple(FALL)))
margin = Margin("skid reach", slack, "mm", over=space)
```

```
skid reach: -15.84137 mm at L0 = 0.145737, alpha = -0.349066, fall = backward (knee B), FAILS; pre-polish -15.46774; coverage 95.7%; n = 623, seed = 20261011
  case forward:  needed 220.8414 mm at L0 = 145.737 mm, alpha = +20°
  case backward: needed 220.8414 mm at L0 = 145.737 mm, alpha = -20°
```

The run took 0.18 s. Seeds 1 to 3 give the identical value.
- **Value:** 220.84 mm needed against the review's 220.8 mm, a difference of 0.02 %. `report_margins.py` M1 gives 220.8 mm on its grid.
- **Location:** α = +20° for a forward fall, mirrored for a backward one. The maximum is interior in L0, at 145.7 mm, between the report's grid rows; the 140 mm corner reads 220.47 mm.
- **Hand-checked pose:** α = 0 needs 143 to 174 mm, which passes.

### Friction to carry into #82

1. `Worst.coverage` pools all `Choice` combinations, and `Case` carries no coverage or pre-polish value. Per-mass figures took one search per mass.
2. Coverage is a volume fraction, good to about ±1–2 points at the default Sobol count. The docs should say so, and say to raise `global_points` before quoting coverage against a figure.
3. `str(worst)` leaves out the per-case table, so a `Worst.table()` would help.
4. A tie between mirror-image points makes `at` flip with the seed. Cite the cases, not `at`.
5. Axes carry no unit or display form, so α prints in radians.
6. Fixed context reaches `fn` through a closure, which works but is not documented.
7. Neither margin needed `Coordinates`, `Band` or `Infeasible`, so this run gives no evidence on `rest_on`.

## Overhaul 02: designed and ticketed — 2026-10-11

**Status:** Grilled in two rounds (19 questions, all recommendations accepted). Recorded as ADR 0005, spec #75 (`ready-for-agent`), and tickets #76–#82 as its sub-issues with native blocked-by edges. No engine or template code has changed yet. Cleanup commit `253774e` (derive needs uv, not a machine-wide MuJoCo; the engine path is written resolved) is on local `main` and not pushed.

**Decisions** (the spec has the detail):
- **Where it lives.** `armature.search` in the engine.
- **The margin.** `Margin(name, fn, unit, over, truth, agree, budget)`, where `fn(point)` returns slack against the derated limit and −∞ is legal.
- **The space.** It is built from `Interval`, `Choice`, `Direction`, `Band` and `Coordinates` axes. `Choice` axes are enumerated, not searched.
- **The method is fixed:** Sobol, plus every corner, then a bounded Powell polish from the best 3. The result is the minimum over every point evaluated.
- **Points outside the space.** `Infeasible(reason)` marks them; it is not a failure.
- **What `Worst` carries:** coverage, the best before polish, n and seed.
- **Engine speed.** One scratch `MjData` per `Compiled` (#76).
- **The sampler.** It is split, not replaced (#77).
- **Bands.** An interim `params.BANDS` until Overhaul 06 absorbs it.
- **The template.** A margin is discovered by type in `run_all.py`. `truth=` plus `agree` confirms the worst point in the truth model, and the truth gate covers margins.
- **Callers.** `verification.py` and σ_min move onto the search. The CAD sweep waits for Overhaul 08, and spec §9's wiring waits for the pipeline-v2 decision on where feasibility lives. §9 gets one sentence now.

**Ticket order:** #76, #77 and #78 have no blockers and can run in parallel worktrees. #79 needs #77 and #78. #80 needs #76 and #79. #81 (acceptance on scratch copies of Plumb and Ibex) needs #79. #82 (docs) needs #80.

**Evidence gathered:**
- **The probe scripts** are in the session scratchpad, which is not durable. Their figures are in #75's Further Notes.
- **Golden worst cases:**
  - 2R arm: 0.1713052 at q = (0, 0), with the load straight down and m2 at +10 %.
  - Cable platform: 4.987626 N at the mirror corners (1.5 or 2.5, 1.6, 0.9).
- **Verified after the grilling:** Sobol 64 + corners + Powell ×3 finds both. On the platform, the corners alone hit the exact worst, and Powell returned 7e-6 N worse. That is why the result is the minimum over every point evaluated.
- **The ten findings** are listed in #75's Problem Statement.

**Flagged, not decided:**
- `agree` (the truth tolerance) and `Budget` were added while writing the spec; neither was in the grilling.
- Plumb's `spec.md:222` still carries the single-direction 75–81 % figure, where m1 F4 says about 39 %. It is left alone, since Plumb is deferred.

## #74: docs, glossary and changelog for the mechanism description — 2026-10-11

**Status:** Fast-forwarded onto local `main` as `568e77a`. All of #69–#74 is now on local `main`, 6 commits ahead of `origin/main`. Nothing is pushed, and #69–#74 are still open. Every #74 box is met, and no code changed; the model template's `run_all.py` is still green on main. The final grep finds no DH table, `FLOATING_*`, `truth.build`, `truth.release` or `truth/` in any skill, reference, agent or the README. The only hits are CONTEXT.md's _Avoid_ lists, a dated research note, and Pinocchio marked unused. Files:
- **`armature-derive` SKILL:** Step 0 writes `mechanism.py` and `DERIVED`, with reductions carrying `assumption=` and release checks named `test_truth_…`. Milestone 0 compiles and writes the review artifact. Each mandatory check names its engine call. Commands are `uv run`, and `UV=absent` is the blocker.
- **`references/model-layout.md`:** "The engine and the project's half" replaces "The truth package", and the gate keys on `mechanism.py`.
- **Derivation standards, review checklist, red-team agent, CAD skill and part template README:** the release rule reads variants and reductions, the checklist probes name the engine queries, and the sweep runs via `uv run --project ../../analysis/model`.
- **`CONTEXT.md`:** Mechanism description, Home posture, Reduction, Variant and Engine are added, and Truth model is now compiled from the description.
- **`CHANGELOG.md`:** a summary linking #64 and ADRs 0003 and 0004.
- **README, plan skill and pitch skill:** the README names the engine and uv as dependencies, and the DH wording is gone from the plan and pitch skills.

**Decisions made in the docs:**
- A copied project points `[tool.uv.sources]` at `${CLAUDE_PLUGIN_ROOT}/engine`.
- "Reduction" now means only the glossary term; a gearbox's is a "gear ratio".
- The engine's reference is its docstrings, with `armature/__init__.py` as the map.

**Left open, outside #74's scope:**
- **The engine's distribution.** The `${CLAUDE_PLUGIN_ROOT}` path is version-keyed, and the 1.3.0 cache has no engine. This blocks #63.
- **The plugin version** is still 1.3.0.
- **The MuJoCo-versus-uv blocker:** `environment-record.md`, `init` SKILL:98, `armature-plan` SKILL:34 and `env-probe.sh`'s core check still say a machine-wide MuJoCo is what derive needs.
- **Template docstrings** still say `python …` rather than `uv run python …`.
- **The Unreleased intro** still says "Two changes".
- **The engine reference page** that spec #64 promises does not exist.
- **The frames table** is written to the gitignored `review/`, so the CAD stage has to re-run `report_truth.py` to read it.

## #73: the model template reads the description — 2026-10-11

**Status:** Fast-forwarded onto local `main` as `5c65f59`, on `05e8941`. It is not pushed, and #73 is still open. Verified on main: the engine gives 434 passed and 4 xfailed (unchanged); in the model template, `uv run python run_all.py` is green, `run_all.py kinematics` is green, and `uv run pytest` gives 32 passed. The CAD part template's 33 self-tests passed in the agent's scratch project, which I did not re-run. Every #73 box is met, and the CHANGELOG line is written. #74 (docs) is running. New code:
- `mechanism.py` and `mechanism_checks.py` (Milestone 0): `mechanism(p)` for the 2R arm, with sites `elbow_pin` and `tip` and direct-drive `shoulder_motor` and `elbow_motor`. Also `DERIVED`, the cached `truth()`, `derived()` and `view()`, and `COORDINATES`, `numeric`, `vector`, `named` and `commands`.
- `pyproject.toml`, with the engine as an editable path dependency (`../../../../engine`), plus Pillow.
- `truth/` is deleted: both MJCF builders, the queries, release.py, the sampler and the Pinocchio path.

Thirty-two mutants were run (23 model, 9 CAD), and thirty fail a test. The two survivors are equivalent: the workspace check written `<=`, and the sweep's `RANGES` reversed (both are ±π).

**Decisions made in the code:**
- **params.py** is standard library only. `WORKSPACE`, `QD_LIMITS` and `QDD_LIMITS` are dicts keyed by name. This is breaking, and the CHANGELOG says so.
- **Envelope.** The elbow range is now ±π in both templates (it was ±2.6 in derive and ±π in the sweep). The sweep is what narrows it, and the worst-case torques are unchanged.
- **Truth comparisons** read `inverse().generalised`. Holds go through `commands()`, which divides by gear and is tested at 50:1.
- **Kinematics** reads the tool site and its body's frame from the view. The moment-arm form is built from the view's axes, anchors and COMs.
- **Accounting** runs in kinematics_checks and lagrangian_checks.
- **The release fixture** moved to mechanism_checks, with a true lock as its control.
- **The truth gate** keys on `mechanism.py`, in both `layout.py` copies.
- **The CAD sweep** carries each envelope on a site (`CARRIERS`) posed by the compiled model, over the description's joint ranges. The collisions it reports are unchanged.
- **The template has no lock file.** `.venv/`, `uv.lock` and `review/` are gitignored, because the relative engine path breaks once the template is copied.

**Merge note:** the main checkout had an uncommitted `.learning/` line in `.gitignore`. It was stashed, #73 merged, and the line restored, still uncommitted.

**Bugs found:** none in the engine. A settle under an exactly balanced hold reports moved = 0.0, so the "worst drift" bookkeeping starts from the first posture.

**Deferred:** distributing the engine (the template's path is right only in place, which matters when the template is copied into a project; see the version-bump note for #63). All docs, which are #74's.

## #72: the sampler — 2026-10-11

**Status:** Fast-forwarded onto local `main` as `05e8941`, on `ca4b446`. It is not pushed, and #72 is still open. `uv run pytest` in `engine/` gives 434 passed and 4 xfailed. Every #72 box is met, and the CHANGELOG line is written. The template's `truth/envelope.py` is untouched, because #73 deletes it. #73 is now running. New code:
- `sampler.py`: `sample`, `sample_states`, `pose_envelope` → `PoseEnvelope` (with `.contains`), `Samples`, `Rejected`, `clearance(state, contact)` and `tilt_yaw`.
- In `assembly.py`: `ClosureError(ValueError)` with `.constraint`, and `Closure.around`. Continuation now walks only the joints around a constraint.
- In `contact.py`: `clearance(model, data, name)` via `mj_geomDistance`, and `CLEARANCE_RANGE` = 100 m.
- `tests/test_sampler.py`, fixture 3's skid trap (`with_skid`) and `rest_on` tests, and two branch-walk tests in `test_rigid.py`.

Forty-two mutants were run, and forty fail a test. The survivors are kept: swing and twist swapped in the free draw is equivalent (the azimuth is uniform), and `Samples.residual` set to 0 can't be told from ~1e-17, since closure is pinned per state.

**Decisions made in the code:**
- **n and draws.** n counts the states delivered. Draws continue up to `MAX_DRAWS` = 100·n, then it raises with the reasons. `rejected` holds `(q, reason)`, and `str(samples)` prints n, the seed, refusals by reason, and each contact's reach.
- **Seeds.** `SeedSequence(seed).spawn(2)` gives one stream for postures and one for rates, so `sample_states` has `sample`'s postures. The streams differ from the template's old `default_rng(seed)`. `DEFAULT_SAMPLES` = 24 and `DEFAULT_SEED` = 20260915 are kept.
- **Ranges.** Only independent coordinates are drawn, from the joint ranges or a `within=` that must lie inside them.
- **Pose envelope.** `up` = −gravity. Tilt is the angle of R·up from up, and yaw is the swing-twist twist about up. A free joint draws uniformly over the tilt cap. A rebuilt chain classifies each free turn as level (tilt) or upright (yaw), and anything else raises. A floating body without an envelope raises.
- **rest_on.** `{contact: coordinate}` is solved by Newton on clearance to `PLACE_TOL` = 1e-10 m. The coordinate is still drawn, so the posture stream is unchanged. `sample_states` refuses it.
- **Rate limits.** Keyed by dof, covering every independent dof and nothing else, drawn uniformly in ±limit.
- **Continuation.** Only joints around a loop, couple or rigid cable are walked, and the rest are set at their target from step 1. Fixture 3's hub at 90 rad used to cost 1,800 steps and now costs none.

**Bugs found:** none in shipped code. `at()`'s continuation walked coordinates outside every loop, about 0.2 s per draw for a wheel; fixed as above.

**Deferred:** rates for a contact-resting body. `rest_on` on an unlocked free joint. Floating chains with closure-solved components. The envelope check after `rest_on` changes a chain component. Tilt uniformity over the cap for chain turns. Clearance capped at 100 m.

**For #73:** samples are engine `State`s keyed by name, not arrays. `WORKSPACE` becomes `within=`, and the limits become dicts keyed by dof. `Q_LIMITS` and `inside()` go. Print `str(samples)`. Seed streams moved, so assert on bounds, not old numbers.

## #69: contact and fixture 3 — 2026-10-11

**Status:** Fast-forwarded onto local `main` as `ca4b446`, on top of #70 and #71. That closes round 1. Nothing is pushed, and #69, #70 and #71 are still open. `uv run pytest` in `engine/` gives 382 passed and 4 xfailed. Every #69 box is met, with the two notes below. It also took over #70's `rigid(contact)` box and #71's Contacts row in the frames table. The CHANGELOG line is written, and #70's line was corrected. New code:
- `contact.py`: touching-point detection, explicit contact rows, `ContactForce`, the settle's reading of the solver's forces, and the transitionFD root filter (`roots`, `split`, `frequencies`).
- In `elements.py`: `shape(...)` and `contact(name, body, shape, against, mu, stiffness, damping)`.
- `Description.contacts`, `Inverse.contacts`, `Settled.contacts`, `Linearised.roots` and `.discarded`, and `compliant_contacts()`.
- `tests/test_contact.py`, `tests/test_fixture_wheel_leg.py` (fixture 3) and a Contacts test in `test_review.py`.

Thirty-four mutants were run, and thirty-two fail a test. The survivors are kept: swapping the pair's geom order is equivalent (MuJoCo reorders by type, and `_into` reads the sign), and the |s|·dt > 0.5 discard rule is an unexercised guard.

**Notes on the boxes:**
- The ticket's "without noslip it crept forever" does not reproduce on a rigid contact at impedance 0.9999. Noslip is pinned instead by `noslip_iterations` and by a compliant tyre that creeps without it.
- The engine has no servo element. A 300 N·m/rad hub spring stands in for the servo's P gain, and its 17.86 Hz mode is kept and matches the closed form.

**Decisions made in the code:**
- **Cone and noslip.** Pyramidal cone, `noslip_iterations` = 20 when any μ > 0. In MuJoCo 3.15, noslip has no effect on elliptic cones. The margin reported is Coulomb's μN − |F_t|, so off-axis in 3D the pyramid can slip slightly before it reaches 0.
- **Rigid contact.** The loops' solref (0.002, 1) and solimp 0.9999. `PENETRATION_BOUND` = 1e-6 m.
- **TOUCH = 1e-8 m** is the pair's margin. MuJoCo 3.15 ignores a pair's `gap`, so a rigid contact at rest floats at about +9 nm.
- **Compliance.** Sphere only. K = k(1 − d)·diagA/edges uses MuJoCo's internal diagA formula, found by probing: version-fragile, and pinned by the sink test. d = 0.01.
- **Explicit rows.** The point is MuJoCo's contact position. The directions are what the body's joints allow, coinciding rows are merged, and a contact's total force is NaN if it is undetermined.
- **Linearise with contact.** It runs on copies with rigid contacts and loops at solref 0.005 and 0.02 and solimp 0.95, using up to 3 settle rounds, then `mjd_transitionFD` (centred, eps 1e-8). s = (λ − 1)/(dt √λ) inverts semi-implicit Euler exactly. Roots are matched by Hungarian assignment and kept if they move at most 1%.
- **The rest test, a shared fix.** `_quench` judges rest on each step's speed before the quench zeroes it.

**Bugs found:** the settle's old rest test passed a steady creep. MuJoCo 3.15's noslip does nothing on elliptic cones, and it ignores a pair's `gap`. ln λ/dt is biased by (ωdt)²/24. Difference steps at eps 1e-6 lift a stiff contact clear (hence the soft copies and eps 1e-8).

**Deferred:** `at()` does not close contacts, so the caller places the touching body. Box shapes are base-aligned at home only. A compliant contact's own mode is checked only for presence. Linearise with a loop and a contact together has no test. The symbolic view carries no contact points.

**For #72:** contact is outside `at()`, so each sample places the touching body (see `placed()` in fixture 3). Touching is within `TOUCH`, and a non-touching contact has no rows. Linearise with contact costs 0.1–0.3 s per call.

## #70: planar, lump, rigid, release by reduction, accounting — 2026-10-11

**Status:** Fast-forwarded onto local `main` as `1f8bc8a`, on top of #71. It is not pushed, and #70 is still open. `uv run pytest` in `engine/` gives 327 passed and 4 xfailed. Every #70 box is met except `rigid(contact)`, which needs #69's contact element; #69's agent was asked to add it during its rebase. The CHANGELOG line is written. New code:
- `planar(plane)`, `lump(body, into)` with the `massless` sentinel, and `rigid(element)` in `variants.py`, plus `account(compiled, coordinates)` and `AccountingError`.
- `Description.locked_by` and `.floored`, and `description.rigid_cables()`.
- `Compiled.approximate`, `Compiled.without(reduction)`, `compiler.MASS_FLOOR` and `_hold_rigid`.
- A "cable" block in `Closure`: its row, its drift and its force.
- `Released.sized`, `release(..., quantity=)` and `State._counterpart`.
- `tests/test_planar.py` (Ibex-shaped: a floating torso on two five-bar legs), `test_lump.py`, `test_rigid.py` and `test_accounting.py`.

Forty-one mutants were run, and each one fails a test. The first pass left two survivors, rigid joints sized by displacement and rates not carried; both were test gaps, now closed by a key-set assertion and a lump release at speed.

**Decisions made in the code:**
- **planar.** It expands into Lock objects carrying the planar's assumption, and `locked_by` maps each locked coordinate to it. In-plane is judged at home, to 1e-9: hinges along the normal, slides across it. A free joint keeps two in-plane slides and the turn about the normal, and its out-of-plane translation locks at home. Planar runs after the other reductions and leaves a coordinate another reduction already holds to that reduction. One plane per variant.
- **lump.** `into` takes a neighbour body (parallel axis), a site on the body or a neighbour (a point mass), or `massless`. In the description the body left behind has zero mass, exactly. When compiled, every floored body gets `MASS_FLOOR` = 1e-6 of its pre-lump mass and inertia, and `Compiled.approximate` names it. MuJoCo refuses zero mass even with a massive child below, and zero inertia with nonzero mass.
- **rigid.** A cable becomes a springless tendon plus an `mjEQ_TENDON` equality, with L₀ set after compiling by `_hold_rigid`. In `Closure` its row is |p_e − p_s| − L, and its force is the tension −λ, so a negative value means slack. It is bilateral by choice ("taut and inextensible"). A joint becomes a weld at its spring's rest, and must have a spring.
- **Release.** Lock, couple and planar release together by settling the full description. Lump and rigid release one at a time, as quantity(variant without that reduction) − quantity(this state), following ADR 0003's "with and without it" rather than the spec's "against the full description", so each is attributed to its own key.
- **Accounting.** It compares names with `compiled.dofs`. Every independent dof must be present, dependent ones are optional, and nothing else is allowed.
- **Parameter usage.** A variant is judged on its parent's usage: `describe(variant)` checks the full mechanism before reducing.

**Bugs found:** none in shipped code. One test assertion was wrong (a lumped hand across a planar-locked roll joint changes nothing but the floor).

**Deferred:** `rigid(contact)` (to #69). `Settled.tension` for a rigid cable. Rigid cables on a whole floating body (`Closure` still solves only hinge and slide dependents). Rates carried to a rebuilt floating chain's turns are exact only when the free turn is about a base axis (true under planar).

## #71: coarse bodies, full validation and the Milestone 0 review artifact — 2026-10-11

**Status:** Fast-forwarded onto local `main` as `9957426`. It is not pushed, and #71 is still open. `uv run pytest` in `engine/` gives 266 passed and 4 xfailed. Every #71 acceptance box is met, and the CHANGELOG line is written. It was built in parallel with #69 and #70 (round 1); both were told to rebase onto it. New code:
- `coarse.py`: `point`, `rod`, `box`, `cylinder`, `sphere` and `compose`, each returning a `Body`.
- `review.py`: `frames(mechanism, params)` → `Frames` (`.sections`, `.row()`, `.markdown()`), `render(state, path, size=, view=)` and `review(mechanism, params, directory, states)` → `Review`.
- In `description.py`: `LOOP_HOME_BOUND`, the loop-at-home check in `_check_loop`, and the unused-parameter check in `describe`.
- `tests/test_coarse.py` and `tests/test_review.py`. Pillow 12 joins the dev group.

Thirty-two mutants were run, and every one fails a test. Three survived the first pass and were killed by new tests:
- the inertia's product columns swapped: fixtures 1 and 2 have diagonal inertia in base axes, so a tilted-box body was added;
- no inertia boxes in the render;
- no COM markers.

The rest covered the helpers' formulas, compose's parallel-axis term, the input checks, both validation checks, the frames table's columns and the render's use of the state.

**Decisions made in the code:**
- **Coarse helpers.**
  - Each helper takes a name and returns a `Body`. `compose(name, *parts)` treats the parts' names as labels only.
  - Signatures: `point(name, at=, mass=)`, `rod(name, start=, end=, mass= | linear_density=)`, `box(name, center=, size=, mass= | density=, axes=)`, `cylinder(name, start=, end=, radius=, mass= | density=)`, `sphere(name, center=, radius=, mass= | density=)`.
  - Exactly one of mass and density is required, and a numeric zero length raises, both as DescriptionErrors naming the body.
  - The arithmetic is plain with no float literals, so symbols give exact forms. With the parameters real rather than positive, a symbolic length from a density reads |l|.
  - A point, or a rod alone, has a zero principal moment and fails the positive-definite check (MuJoCo refuses it too). Compose it with a solid or use a cylinder.
- **Validation.** `LOOP_HOME_BOUND` = 1e-6 m, absolute, checked only when both sites are numeric. An unused parameter is `set(p) − p.used`, so a key read only through `in` does not count. This check is breaking: params dicts must carry only what the mechanism reads.
- **Frames table.** It reads the description, not the compiled model; the tests compare it with what MuJoCo built. `SECTIONS` is a tuple of (title, Description attribute, row function), and a missing attribute is skipped, so a new element kind is one row function plus one entry.
- **Render.** It draws on a deepcopy of the `MjModel`, with decor scaled to 0.06 × `stat.extent`, a yellow emissive COM ball at each `xipos`, and the free camera at azimuth 150°, elevation −25°. The posture comes from `state._data()`, so loops are closed. Pillow is imported lazily, and it is a dev dependency only, so a project calling `render` must add it.

**Bugs found:** none in the engine. Three existing tests passed parameters their mechanism never reads, and each was trimmed (`test_couple.py`, `test_fixture_spring_cable.py`, `test_validation.py::hung`).

**Deferred:** #69 adds a Contacts row to `review.SECTIONS` (asked of its agent). #70's reductions appear through `str(r)` and `r.assumption`.

## #68: loops, couples and fixture 4 — 2026-10-11

**Status:** Pushed as `7cee8d7`, and #68 is closed. `uv run pytest` in `engine/` gives 225 passed and 4 xfailed. Every #68 acceptance box is met, and the CHANGELOG line is written. New code:
- `assembly.py`, which holds `write_q`, `tangent` (moved from `state.py`) and `Closure`. `Closure` builds the rows, chooses the dependent coordinates, runs the Newton closure and the continuation, and solves the dependent rates and accelerations.
- `loop(name, a, b)` (an element) and `couple(a, b, ratio, assumption=)` (a reduction).
- `Compiled.constraints`, `.independent`, `.dependent` and `.closure`, plus `Inverse.unknowns`, `Symbolic.closures` and `Description.loops` / `.couples`.
- `tests/test_fixture_five_bar.py`, `tests/test_fixture_parallelogram.py` (fixture 4) and `tests/test_couple.py`.

Twenty-three mutants were run, and twenty-two fail a test:
- the connect anchored on bodies;
- the compiled couple's sign;
- the default solimp;
- three rows on a planar loop;
- actuated joints chosen as dependent;
- no continuation;
- no predictor;
- untruncated Newton steps;
- J̇q̇ dropped;
- the couple row's sign;
- the loop force's sign, in the record or in the wrench;
- the closure raise, the range raise or the settle's closure raise dropped;
- K not re-closed, or without the basis G;
- no NaN for undetermined unknowns;
- the solver's forces left in the wrench;
- no loop rows in the inverse;
- dependent rates not solved.

The survivor is K's held-torque term, Gᵀ S τ. It only matters when an actuator ends up dependent. The dependent choice avoids that unless the unactuated joints cannot carry the rank, and over-actuation leaves τ undetermined, which reads as 0. It was kept because it is correct.

**Decisions made in the code:**
- **Independent and dependent coordinates.**
  - These are chosen once, at home, by greedy rank over the rows' columns: unactuated joints first, then a couple's follower, then later joints in tree order.
  - `at()` raises on a dependent coordinate given in `q` or `qd`, and `inverse` on one given in `qdd`.
  - There is no way yet to choose the split. Giving the parallelogram's elbow instead of J2 is not supported.
- **Rows.**
  - Rows come from `mj_jacSite`, never from `efc_J`.
  - A loop whose moving joints all turn about one n (and slide across it) keeps two in-plane rows. Its force is reported as a 3-vector on site `a`'s body, with no normal component.
  - A couple's row is q_a − home_a − ratio (q_b − home_b). Its force is keyed by the follower `a`.
- **Assembly.**
  - Continuation runs in 0.05 rad steps from home. Each step makes a tangent prediction, then Newton on the dependents, and Newton stops when the gap stops halving below 1e-10.
  - Floating bodies are set at their target from the first step, not interpolated. Nothing yet has a floating body inside a loop.
- **Rank.**
  - `RANK_TOL` = 1e-9 relative, for both Newton's truncated steps and `inverse`.
  - An unknown with a share in the null space reads NaN, and `rank < unknowns` is the rank loss.
  - At the singularity the parallelogram's τ are numbers, because they are determined. The loop force reads NaN, and the residual is about 1.2 even unloaded: the flip into the antiparallelogram is free there, and the weights push along it.
- **Linearise on a closed chain.**
  - It is taken at rest. K = ∂/∂y[Gᵀ Tᵀ(bias − passive − Sᵀτ_hold)] by central differences, re-closing from the state's dependents. M = GᵀTᵀMTG.
  - `Linearised.dofs` are the independent dofs.
- **Solver parameters.** solref = (2·timestep, 1), and solimp is constant at 0.9999. The old (0.99, 0.999) held 6e-6 rad on a couple under 1 N·m, and the parallelogram never came to rest. `CLOSURE_BOUND` = 1e-6 m.
- **Wrench on a closed chain.** It zeroes `efc_force` and applies the solve's loop forces at both sites.
- **`Compiled.full`** keys on any reduction, not just locks, so a couple-only variant's `full` drops the couple. `release` passes only the independent coordinates to `full.at`. Release semantics for a couple are #70's.

**Bugs found:**
- **A Newton step at an exactly singular posture divides rounding by a vanishing singular value.** The first version landed within 1e-16 of the parallelogram's singular posture, then took one more lstsq step and threw the elbow 5.6e-5 rad off, so the rank read 4. Steps are now truncated at `RANK_TOL`.
- **Without the tangent predictor, continuation switches branch near a singularity.** 13 mrad short of the parallelogram's singular point, the solve had already landed on the antiparallelogram (elbow off by 0.0325 rad). Separately, the five-bar at (0.75, −1.25) flips branch with no continuation at all. A test now pins each.
- The first SymPy reference for the five-bar took 13 s to build, half of it symbolic Hessians and half `lambdify`. It was rewritten as closed-form geometry in 40-digit mpmath with `mp.diff` and now builds in no time. The fixture file runs in about 1 s.

**Measured margins:**
- Five-bar: closure gap 1e-16 m, statics 3.5e-12, K and frequencies 3e-10 (the probe reached 4e-11; eps = 1e-6 is roundoff-limited here). `mj_inverse` is off by more than 10 % at the tested posture.
- Fixture 4: dependents close to 1e-12, or to (gap)/σ_min near the singularity (1e-9 at 1 µrad short). A milliradian from the singularity the loop force reads about 10⁵ N at condition 6e5.

**Skipped / deferred:**
- The validation that a loop closes at home is #71's. Until then, `at()` at home silently closes a loop the description wrote open.
- Release for a couple is #70's.
- Contact rows are #69's.
- A loop through a floating body is untested, and so is linearise on a closed chain with a floating body (`_nudged` handles one).
- `jacobian` on a closed chain still returns columns over all dofs, not ∂/∂(independent).

**Next:**
- #69 (contact), #70 (variants) and #71 (coarse bodies, validation) are now unblocked. #70 needs #67 too, which is closed. #69 needs fixture 3, the five-bar on a wheel, and can start from `test_fixture_five_bar.py`'s mechanism.

## #67: floating bodies, fixture 2 and the level-platform release — 2026-10-11

**Status:** Pushed as `3d3084c`, and #67 is closed. `uv run pytest` in `engine/` gives 145 passed and 4 xfailed. The three new strict xfails are the level-platform trap at the three off-centre poses. Every #67 acceptance box is met in the code, and the CHANGELOG line is written. New code:
- `joint(..., "free", parent="world", point=...)` and `Placement`.
- `Compiled.dofs` and `Compiled.home`.
- `rotations.py`.
- `Settled.tension`.
- Fixture 2 is `tests/test_fixture_cable_platform.py`, on Plumb Rev 1.0's rig, taken from Plumb at `d6b596f`, since Plumb has since moved to Rev 1.3.

Twenty mutants were run, and each one fails a test:
- qpos written or read at the dof address;
- the free position without its COM offset;
- the tangent lever dropped or with its sign flipped;
- angular rates left in body axes;
- the drift dropped or with its sign flipped;
- `linearise` not turned to the dofs;
- a slack cable reading its compression;
- release angles taken as extrinsic, or as the reversed relative turn;
- turns assembled free-first, in the state or in the symbolic view;
- the wrench taken about the COM;
- the chain's slides along body axes, its locked translation ignored, its slide home at zero, or its hinges about the COM.

**Decisions made in the code:**
- **Placement.**
  - A free joint's value is a `Placement`: the position of the joint's `point` (a point fixed on the body), and a 3×3 rotation from home.
  - It takes a rotation matrix, never a quaternion, because the xyzw/wxyz order is exactly the trap.
  - `at()` checks it is a rotation to 1e-9.
- **Dofs and rates.**
  - Rates (`qd`, `qdd`) and every matrix (`Jacobian`, `Linearised`, `Inverse.generalised`) are keyed by **dof**, not coordinate. A free joint `f` has `f:x … f:z` (the point's velocity) and `f:rx … f:rz` (the angular velocity), all along base axes.
  - The engine turns MuJoCo's own rates (COM velocity, body-axis ω) with T. q̈ adds the drift ω×(ω×r). K and M become TᵀKT and TᵀMT, which is exact at an equilibrium.
  - This is breaking for the record field names only. On a mechanism with no floating body, the dof names equal the coordinate names.
- **Locks on a floating body.**
  - A lock names a component, `f:x … f:rz`. Locking any component rebuilds the free joint as a chain: slides along base axes (each with home = the point's coordinate), then hinges about the body's own axes through the point. The locked turns go first, as the body's fixed orientation, and the free ones follow in x-y-z order. The symbolic view builds the same chain.
  - Release reports a locked translation as the point's displacement along that axis. It reports a locked turn as that angle of the intrinsic x-y-z turn from the start orientation to the rest one.
- **Free joints and the symbolic view.**
  - A free joint takes no axis, range, home value or spring. Its envelope is #72's sampler.
  - An actuator cannot drive a free joint.
  - The symbolic view of an unlocked free joint uses six Euler-chain coordinates, named like the dofs.
- **Wrench.**
  - `wrench` is now taken about the joint's `point` riding on the body. That equals `xanchor` for a hinge, so fixture 1 is unchanged.
  - A free joint at rest carries nothing (3.15 counts cables in `cfrc_ext`).
  - Across a level platform's slides, the wrench is the moment its welded turns carry. It equals Plumb's residual moment, m_res (eq. 19), to 1e-9.

**Bugs found:**
- **The research note's top-edge row was off.** `docs/research/2026-09-15-derive-one-shot-correctness.md` §2 printed 35.73 / 8.84 N for the top edge midpoint. Its damped run had not come to rest at 20 s (|q̇| = 4e-4; re-run today). At rest the tensions are 35.68 / 8.82 N. The engine's quench, an independent BFGS minimisation of the potential, and the note's own method run to 60 s all agree. A dated correction now sits under the note's table.
- **Plumb M1 review F2's tilt numbers do not reproduce.** These are Plumb findings, not engine bugs.
  - At the room centre, the review gives the soft tilt stiffness as 0.85 N·m/rad and the tilt modes as 0.78 Hz.
  - The engine's `linearise` and an independent central-difference Hessian of the review's own potential agree to 1e-5. They give a tilt-sway Schur complement of 4.45 N·m/rad, with modes at 2.09/2.09 Hz tilt-sway, 2.49 yaw, 11.05 vertical and 20.1/20.1 horizontal.
  - The review's yaw (2.49 Hz, K_yaw = m g A d / z0 = 4.905) and vertical (11 Hz) agree.
  - Its "virtual pivot 4.7 cm below" pendulum misses the geometric stiffness of the converging cables. That is the same class of error the review itself was hunting.
  - This is Rev 1.0 geometry. Plumb is on Rev 1.3, so whether a live number rests on it is for Plumb's map to check.

**Skipped / deferred:**
- The sampler's floating-pose envelope (#72).
- `inverse` on a floating body with cables or contact rows (#68 and #69 add J_c).
- A tilt metric on `Released`. The test computes the tilt from `settled.q[...].rotation`, because "tilt" depends on gravity's direction and is not a property of the engine.

**Next:**
- #67 is done.
- Then #68 (loops), which is unblocked.
- #48's last open child is #63, the Plumb acceptance. It is still gated: the old `truth/` floating-body bugs are untouched on main, and #64 says neither Plumb nor #63 migrates. Fixture 2 now reproduces #63's expected failure inside the engine. The open decision is whether #63 runs against the engine-based template after #73, or #48 closes on fixture 2 as its evidence.

## #66: the 2R arm, queries, symbolic view and lock — 2026-10-11

**Status:** Pushed as `f16aaad`, and #66 is closed. `uv run pytest` in `engine/` gives 108 passed and 1 xfailed (the locked-elbow trap, strict). The new code:
- `elements.actuator`;
- `variants.py`: `lock`, `reduce` and `Variant`;
- `symbolic.py`;
- in `state.py`, `pose`, `jacobian`, `inverse`, `settle`, `wrench` and `release`, each returning a record with `residual` and `method`.

Fixture 1 is `tests/test_fixture_2r_arm.py`. Each pin was mutation-checked. The breaks: the wrench's anchor shift, the load point (COM instead of site), the gear² on the rotor, the torque limit, `min_steps`, the lock value at release, the weld's rotation, and settle's loads. Each one fails a test.

**Decisions made in the code:**
- **Actuators.**
  - Torque and the limit are motor-side. The joint feels gear × τ, and `Inverse.torque` reports the motor torque.
  - The rotor is joint armature, Σ N²J over the joint's actuators. MuJoCo 3.15's actuator `armature` field gives the same M, but N²J was kept explicit.
- **Holds and loads.**
  - `hold` is keyed by actuator name only. A coordinate with no actuator cannot be held, and that is itself the finding.
  - `settle` starts from rest and ignores the state's rates. It clamps a hold beyond the limit, as the motor would, and names it in `over_limit`.
  - `settle` applies loads between `mj_step1` and `mj_step2`, at the site's current position. The old `site_wrench` froze the moment at the start pose. The compiler now pins the Euler integrator, because this split needs it.
- **Wrench.** `wrench` reads `cfrc_int` at qacc = qdd and moves it from the root's subtree COM to the joint anchor. Along the axis it equals N·τ − N²J·q̈, because the rotor is not a body.
- **Residuals.** A kinematic record's `residual` is the closure residual, the largest equality-row `efc_pos`. It is 0 until #68. `Inverse.residual` is the solve's residual instead.
- **Variants.**
  - `lock` poses the welded child with a body quat. The local numbers of its subtree are unchanged.
  - A locked joint's actuators are dropped. `Compiled.full` compiles the full description lazily, for release.
- **Order.** `tree_order` gives depth-first pre-order with siblings in the order written. It is the order MuJoCo numbers bodies, and the symbolic view uses it, so coordinates match on both sides.
- **The symbolic view** chains `orient_axis` frames, which is the product of exponentials written as frames. It does not add rotor inertia; the derivation adds it from the actuators.

**Bugs found:**
- **`linearise` read M at a perturbed posture.** It read M after `mjd_inverseFD`, which leaves `qM` at its last perturbed posture, so M was evaluated at q − eps. On the 2R arm that is off by 4e-7. The pendulum's M is constant, so #65's tests could not see it. M is now read first, and each FD side runs on fresh data.

**Skipped / deferred:**
- `wrench` refuses a welded body. The force a lock carries would be useful, but nothing asks for it yet.
- `inverse` and `wrench` still refuse any constraint row. #68 adds the loop rows to J_c.

**Next:** #67 (floating bodies) and #68 (loops) are both unblocked, in either order.

## #65: engine package and fixture 5 — 2026-10-11

**Status:** Pushed as `ddb8c88`, with ADRs 0003 and 0004 in `ee6e5b6`. #65 is closed. `engine/` (import name `armature`) holds `elements.py` (body, joint, site, cable, gravity), `description.py` (`describe` plus validation), `compiler.py` (`compile`, `Compiled.at`) and `state.py` (`State.linearise`, `Linearised`). `uv run pytest` in `engine/` passes 42 tests on mujoco 3.15.0 and Python 3.14.7. Each pinning test was mutation-checked: flipping `degree`, `inertiafromgeom` or the cable deadband fails a test.

**Decisions made in the code:**
- Each MuJoCo body frame sits at its COM, with axes parallel to base at home. Local positions are base positions minus the COM, and the inertia goes in unrotated.
- An undefined parameter reads as a SymPy symbol, so validation can name the element that used it.
- The topology comes from the joints. A body with no joint into it is an error, not an implicit weld.
- Gravity is an optional element, defaulting to (0, 0, −9.81). #66 needs it for the symbolic view, and the 2R template uses −y.
- `at()` defaults omitted coordinates to their home value, and refuses unknown names and values outside the range.
- Cable end sites are named `<cable>:start` and `<cable>:end`.

**Bugs found:**
- One-sided `mjd_inverseFD` leaves an O(eps) error: 1.8e-6 relative on a pendulum at q = −1.3. Averaging the runs at +eps and −eps gives a central difference, good to 4e-11.
- M from `DfDa` carries about 1e-9 of roundoff, so M comes from `mj_fullM` instead. In 3.15 its signature is `(m, d, dst)`.
- A limit row is not active at exactly the range boundary, so the nefc guard in `linearise` is tested on a hand-built State.

**Next:** #66, the 2R arm: actuators, `pose`, `jacobian`, `inverse`, `settle`, `wrench`, the symbolic view, and `lock`. The tests can reuse `tests/test_compile.py`'s pendulum pattern.

## Overhaul 01: designed and ticketed — 2026-10-11

**Status:** The grilling on 01's interface and seam is done. It settled 17 decisions, every one on the recommended answer. They are recorded in four places:
- **ADR 0003:** one mechanism description, written at the home posture and compiled for both sides, with the derivation's simplifications as reductions in variants the derivation owns.
- **ADR 0004:** the model machinery is a package projects pin, not a template they copy. Distribution stays open.
- **Spec #64**, labelled `ready-for-agent`.
- **Tickets #65–#74**, as #64's sub-issues with native blocked-by edges.

No plugin code changed. Both ADRs are new, uncommitted files.

**Bugs found:** These come from probes run on mujoco 3.13.0 in this session's scratchpad, with the compiler probes re-run on 3.15.0. The scripts are not in the repo, so the numbers here are the record.
- **`mj_inverse` is wrong on closed chains and contact.**
  - On a five-bar, the actuated torques were off by 61 % and 78 %, and the passive joints carried torque.
  - At a soft-settled pose it gave 0.8–535 N·m depending on solref and solimp.
  - On a wheel at rest it drops static friction, and reads the normal force as penetration × solver stiffness.
  - An explicit [Sᵀ J_cᵀ][τ; λ] least-squares solve matches virtual work to 2e-10, with a condition number of 6–16.
- **Five-bar modes.**
  - The full-DOF eigenproblem adds spurious modes at 57.8 and 69.1 Hz (578 and 691 Hz at solref .002).
  - Projecting onto null(J_c) misses the geometric stiffness, by +1.7 % and −1.0 %.
  - Central differences of the reduced force in the independent coordinates, re-closing the loop each step, match a minimal-coordinate reference to 4e-11.
- **Contact.**
  - Default pyramidal friction creeps on a 10° incline (1.2 mm/s under quench), so a settle never rests. `noslip_iterations` = 20 fixes it, with the forces right to five digits.
  - `mjd_inverseFD` raises a FatalError on noslip models; `mjd_transitionFD` works.
  - The solver's roots are the ones that move with solref: −51 ± 20i and −111 s⁻¹ became −129 to −547 s⁻¹ at solref .005. The 0.96 Hz rocking mode held to 0.1 %.
  - A hub servo's 17.8 Hz root moved only with its kp. A damping threshold would have kept it, so damping is the wrong filter.
- **MjSpec traps** (on 3.13.0, re-checked on 3.15.0):
  - `compiler.degree` defaults to True.
  - `inertiafromgeom` AUTO silently takes inertia from geoms when `ipos` is unset.
  - `to_xml()` keeps 6 significant digits.
  - A body-anchored `connect` takes its second anchor from qpos0, so an assembly error passes. A site-based connect enforces the sites.
  - A bad keyword leaves a half-built element that breaks the next compile.
  - Joint stiffness and damping are 3-element polynomial arrays; set them with `j.stiffness[0] = k`.
  - Deleting a joint welds the child exactly. A joint-equality lock is soft: 5.2e-4 rad, plus a spurious 38.6 Hz mode.
  - A moving body with zero mass is refused (mjMINVAL).
- **Changes in 3.14 and 3.15.**
  - Tendon forces enter `mj_rnePostConstraint` from 3.14.
  - Tendon actuator force limits default to "auto"; one probe's tendon motor dropped from 50 N to 5 N.
  - `mjd_*` raise when sleeping is enabled.
  - The cp314 Windows wheel for 3.15.0 installs.
- **Offscreen rendering** works here with the default GL backend. Pillow is not installed.

**Skipped / deferred:**
- Owned by other overhauls:
  - distribution and the CLI verbs (05)
  - tier-2 evals (04)
  - the spec stage writing its coarse description (02)
- Elements deferred to the work that needs them: pulleys, ball and screw joints, dry friction, gearbox η and bushings.

**Next:**
- Start with #65, which has no blockers: the engine skeleton plus fixture 5. #66 follows, and after it #67 and #68 can run in parallel.
- The element set and the reduction kinds came from a read-only survey of Plumb, Ibex and CineWave V2; #64 carries the result. Acceptance beyond the fixtures is Ibex's restart.

## Overhaul review: sequencing and shared facts — 2026-10-11

**Status:** Architecture review only (the "overhaul pass" of `improve-codebase-architecture`); no plugin code changed. Eleven candidates follow, one entry each, in the recommended order. Interfaces were deliberately not designed, so each candidate starts with a grilling session on its interface and seam, then its tickets. The evidence was reproduced today on scratch copies of both templates and on read-only walks of Plumb, Ibex and CineWave V2.

**Skipped / deferred:**
- The full report, with its before/after diagrams, is `%TEMP%\architecture-review-20261011-141631.html`. That file is not durable; this log is the durable copy. The earlier 2026-10-11 review (`%TEMP%\architecture-review-20261011-112149.html`) maps onto this one as follows:
  - its 01 → 01
  - its 02 → 02, 03, 09, 11
  - its 03 → 06
  - its 04 → 05
  - its 05 → 07
  - its 06 → 05
  - its 07 → 08
  - its 08 → 07
- The pipeline-v2 direction is set: reshape the pipeline (breaking changes allowed), restart Ibex once the spec-stage work lands, and leave Plumb and CineWave for later. Its decisions are not yet made, and no tickets are cut. The candidates feed them:
  - how projects take the model machinery: 01, 05
  - where feasibility, electrical and safety live: 02, 03, 09, 11
  - the ledger: 06
  - gates instead of the Stage line: 07
- One environment decision is open. Pinocchio 4.1, Placo and CalculiX install on Windows only from conda-forge, which uv cannot install. Running pixi or micromamba beside uv would bring them in. Until then, #62's Pinocchio backend has never run on this machine.

**Next:**
- Order of work:
  1. 01, built as the first module of 05's package (not the template), test-first against 04's fixtures.
  2. 02 and 03, before Ibex's restarted spec reaches §9.
  3. 06 and 07.
  4. 08, 09 and 10, when Ibex reaches CAD.
  5. 11, alongside the safety-home decision.
- The evidence base is 36 Blocker/Major findings: Plumb 16, Ibex 20. CineWave has no reviews. By class:
  - worst case read at a named pose: 10
  - missing physics: 8 (regen 4, contact 2, closed loop 1, bearing 1)
  - wrong assumption: 6
  - missing or contradictory safety requirement: 5
  - stale number: 4
  - hand arithmetic: 3

  The ten reviews also recompute by hand 45 times and keep none of it.
- Run Python with `py` (3.14, with mujoco 3.13.0, sympy 1.14, scipy and pytest); `python` on this machine is the WindowsApps shim. Each entry records the library install facts verified today. Re-check versions before relying on them after a few months.

## Overhaul 01: one mechanism description, compiled and queried through MuJoCo — 2026-10-11

**Status:** Designed and ticketed later the same day: spec #64, tickets #65–#74, and ADRs 0003 and 0004 (see the entry above). Rated Strong, and the review's top recommendation. Every bug below was reproduced today on mujoco 3.13.0, against a copy of `skills/armature-derive/scripts/model_template/`.

**Bugs found:**
- **`linearise` drops springs and cables** (`truth/modes.py:71-81`). It differentiates only `qfrc_bias` (gravity and Coriolis), but springs and tendons live in `qfrc_passive`.
  - With 1000 N/m on 0.5 kg, a joint spring and a cable both read K = 0 and 0 Hz. `mjd_inverseFD` reads 1000 N/m, and the true mode is 7.118 Hz.
  - Plumb's modes come from cable stiffness, so this hits it directly.
  - → Proposed fix: use MuJoCo's own `mjd_inverseFD` / `mjd_transitionFD`.
- **Loops, contact and friction are refused** (`truth/inverse.py:126`, `truth/modes.py:65`). Both assert `nefc == 0`, so they reject a four-bar's loop closure (3 rows), a resting wheel (12) or a friction joint (1), and the message blames a joint limit. Ibex (five-bar, wheels) and CineWave (two parallelograms) cannot be truth-checked at all.
- **The floating-body bugs are still on main**, and they gate #63:
  - `release` reads positions by velocity address (`release.py:51,76`).
  - `linearise` raises when nq ≠ nv (`modes.py:77`).
  - `site_wrench` takes no posture (`equilibrium.py:35-60`).

**Skipped / deferred:**
- ~~The interface: what a project writes to describe its mechanism, and what the query surface looks like.~~ Designed 2026-10-11 in #64.
- Pinocchio as a hard-constraint cross-check, until the environment decision is made.

**Next:**
- **Two incompatible formats today:** the DH table (`params.py:65-86`) and the `FLOATING_*` dicts (`floating.py:41-58`).
  - Four readers turn the DH table into frames: `kinematics.py:23`, `lagrangian.py:29`, `chain.py:62`, `inverse.py:57`.
  - Forward kinematics is written again in `part_template/sweep/bodies.py:116-147` and in `statics_checks.py:27-40`.
  - Both builders emit MJCF as f-strings (`chain.py:96-120`, `floating.py:132-186`).
- **What MjSpec gives you:** `mujoco.MjSpec` in 3.13.0 compiles armature, frictionloss, gear and an equality loop (verified today).
  - Loop constraints are soft, so assert the closure residual.
  - MjSpec fields change between minor versions: 3.7 made joint stiffness and damping arrays, and 3.11–3.12 changed the actuator spec. Pin the minor version.
- **Keep the truth model independent.** It compiles the full description and imports nothing from the derivation.
  - The derivation's simplifications become declared reductions on the description, so releasing one means compiling without it.
  - The settled decisions in `references/model-layout.md` and in the CHANGELOG's truth-model section carry over: settle by quench rather than damping, signed modes, full inertia tensors.
- The probes behind these numbers lived in a session scratchpad, not the repo. The numbers above are the record.

## Overhaul 02: search the worst case once, for every margin — 2026-10-11

**Status:** Proposed, not started. Strong. It targets the largest finding class: 10 of the 36 Blocker/Major findings took a worst case at a named pose, direction or sign.

**Skipped / deferred:**
- The interface. The report's sketch was `search(margin, over = posture × direction × sign × tolerance band) → argmax, margin, method, n, seed`.
- Tolerance bands need 06's ledger. Until then, the corner sweep covers only parameters that carry an explicit band.

**Next:**
- Three samplers exist today, and none is shared with the spec stage:
  - `truth/envelope.py:24`: 24 uniform draws.
  - `verification.py:31,131`: a grid of 25 points per joint. At six joints that is 244 M postures, about 11.7 GB, and roughly 0.8 h per load case at the 2R arm's 12 µs per evaluation.
  - `part_template/sweep/grid.py:42-60`: a full factorial that ignores the truth sampler.
- The corner sweep is described in `armature-derive/SKILL.md:121` but has no code. Spec §9 is hand arithmetic by design: `spec-template.md:154-157` says "Back-of-envelope … Show arithmetic with units".
- Keep what works:
  - `verification.py` already returns the worse of a grid and an optimiser, with the step printed.
  - `params_checks.py` fails a signed load case that carries only one sign.
  - `PLANE_XY` direction sets are answered exactly.
- Exemplars to test against:
  - Plumb's "§9 checks static tension only at the room centre". The 10 N floor actually holds over only 25.8 % of the workspace.
  - Ibex's skid reach, checked at α = 0 only, where up to 220 mm is needed.
- Libraries, all pip-installable on Windows: `scipy.stats.qmc` (Sobol), `scipy.optimize` (shgo, differential_evolution), and CasADi 3.8 for min-max (LGPL).
- It must be callable from spec §9 on a coarse model, as well as from derive and from the CAD sweep. Worst cases it finds are then settled in the truth model, following Milestone 3's pattern.

## Overhaul 03: size actuators from a simulated mission, not a pose at rest — 2026-10-11

**Status:** Proposed, not started. Strong. Regen reached all three projects: Plumb ×3 and Ibex ×1 among the findings, plus CineWave v1's regen into a PSU that cannot sink current.

**Skipped / deferred:**
- What a mission-profile artifact is. Spec §6.4 (`spec-template.md:76-81`) currently allows "motion profile TBD".
- Where the bus model lives. That waits on the "where electrical lives" decision.

**Next:**
- Sizing today stops at a static holding torque: |τ| = g − Jᵀf at rest (`verification.py:118-121`).
  - Nothing computes RMS torque, thermal load, torque–speed at V_min, reflected inertia N²J_m or regen.
  - `design-foundations.md:56` points at "a sizing calculator or spreadsheet".
- MuJoCo already supplies most of the actuator model.
  - Since 3.7 it has a `dcmotor` actuator, and the installed 3.13 has `MjsActuator.set_to_dcmotor(motorconst, resistance, nominal, saturation, inductance, cogging, controller, thermal, lugre)`.
  - Actuator armature is scaled by gear².
  - A bare `<dcmotor>` element fails with "motor constant K must be positive", which confirms the element exists.
- No maintained library covers the rest, so write it:
  - The bus/regen ODE: a capacitor plus a brake-resistor threshold, about 20 lines.
  - The envelope at V_min and the gearbox η: about 150 lines, following Lee et al., arXiv:2310.00080.

  Rejected: motulator has a hard torch dependency and no thermal model, and pyleecan is dead.
- ruckig 0.19 (pip on Windows) generates jerk-limited profiles. Its Community edition sends intermediate waypoints to a cloud API, so stay point-to-point or use CasADi.
- This replaces three per-project copies:
  - Ibex's `regen.py`, with `R_phase=0.275, Kt=1.22` typed into a function signature (`:62`). pint plus a Kt taken from the datasheet would have caught Ibex's wrong torque constant.
  - Plumb's hand clamp.
  - CineWave V2's §9 arithmetic. Its bus capacitance is still unknown (`spec.md:341`).
- Exemplar: Ibex's body switch removed the only regen sink, 6.6 J against 0.26 J of bus storage.
- Actuator data: no vendor publishes a machine-readable catalogue. `nathmo/actuatorReview` has a 140-row CSV, but its values were LLM-extracted, so the librarian should confirm each row before it is used.
- Depends on 01 (actuators in the truth model) and 02 (search over profiles).

## Overhaul 04: five golden mechanisms, so accuracy is measured on more than one shape — 2026-10-11

**Status:** Proposed, not started. Strong.
- **It reopens a #48 decision:** that the test seam is the template's own `run_all.py`/pytest, with no plugin eval harness.
- **That decision is why fitting to Plumb went unseen.** Every fixture is the 2R arm or a three-cable hang, none has a spring, a loop or a wheel, and the 0 N/m stiffness bug shipped.

**Skipped / deferred:**
- Known answers for fixtures 3 and 4 still need sourcing: a closed form, or an independent computation such as Pinocchio with hard constraints once it installs.

**Next:**
- The five fixtures, each with a planted trap:
  1. **2R arm.**
     - Answer: closed form.
     - Trap: a locked elbow. `truth/release_checks.py` already has this fixture, as an expected failure.
  2. **Cable platform**, with four cables on similar anchor and attachment squares.
     - Answer: Pott 2018, ch. 3.
     - Trap: the level-platform assumption. rank W = 3, so the platform tilts 5–26°. The settle table is in `docs/research/2026-09-15-derive-one-shot-correctness.md` §2.
  3. **Five-bar leg on a wheel** (Ibex-shaped).
     - Answer: loop closure plus contact.
     - Trap: first contact checked at α = 0 only.
  4. **Balanced parallelogram arm** (CineWave-shaped).
     - Answer: static balance.
     - Trap: regen into a PSU that cannot sink current, or a singular J2 at stall torque.
  5. **A mass on a spring, and on a cable.**
     - Answer: √(k/m)/2π = 7.118 Hz at 1000 N/m and 0.5 kg.
     - Trap: the stiffness lives only in `qfrc_passive`. This fixture fails today, so build it first: it pins 01's fix.
- **Tier 1:** pytest inside 05's package, run on every change. Write the fixtures in 01's description so they test through the interface.
- **Tier 2:** `claude plugin eval` (Claude Code ≥ 2.1.269).
  - A case is `evals/<case>/prompt.md` plus `graders/*.md`. Defaults are 3 runs, 10 turns and 300 s.
  - The graders are regex, tool_used, tool_order, file_exists, llm and baseline. None of them runs a script, so keep the sandboxes with `--keep-temp` and run the checks on them afterwards.
  - Native Windows has no sandbox backend for suites that grant Bash, so run those in WSL2 or Linux CI.
  - Every run is billed. Control cost with `--max-cost-usd`, `--threshold` and `--json`.

## Overhaul 05: the engine, one pinned package called as verbs — 2026-10-11

**Status:** Proposed, not started. Strong. It absorbs the earlier 2026-10-11 review's 04 (pinned library) and 06 (tracker verbs).

**Skipped / deferred:**
- **Distribution.** Either publish the package separately (PyPI or a git URL), so projects pin it independently of the plugin cache, or ship it inside the plugin and install it from `${CLAUDE_PLUGIN_ROOT}`. Projects run the version-keyed plugin cache (1.3.0), so the second option ties every fix to a plugin release.
- **The verb list.** The report sketched: init, check, truth, margin, sweep, gate, render, ledger, probe --write, merge.

**Next:**
- **The copies have forked.**
  - Plumb's home-made truth model imports the derivation it is meant to check (per the earlier review).
  - Ibex has no pyproject, pins nothing, and never probed MuJoCo (`docs/environment.md:17`).
  - `layout.py` and `run_all.py` each exist in both templates, and they have drifted.
  - The model template is 172 KB, 48 % of it docstrings and comments. Adapting derive means reading about 58k tokens.
- **Session load before any work starts** (words × 1.35):

  | Session | Tokens |
  |---|---|
  | derive (SKILL 4,406 words + derivation-standards 2,459 + model-layout 1,828 + Ibex's CONTEXT 3,600) | 16.6k |
  | red-team on Ibex | 39.0k |
  | librarian, per run | 24.6k |
  | plan on Plumb | 32.5k |
- **Twelve procedures are prose that code could run.** The top five:
  - The datasheet index (get, append, stale): `librarian.md:14`, `:66-74`.
  - The scaffold: `init:73-134`.
  - The environment record. `environment-record.md:48` says "the script prints; you write", which contradicts `:54` and `:78`.
  - The stage hand-off: pitch:36, spec:83, plan:250, derive:182, cad:145.
  - Budget and traceability arithmetic.
- **Plugin facts from the Claude Code docs:**
  - A plugin's `bin/` joins the Bash tool's PATH while the plugin is enabled, but not the user's terminal PATH.
  - `${CLAUDE_PLUGIN_ROOT}` is substituted inside SKILL.md.
  - MCP servers in a plugin's `.mcp.json` start when the plugin is enabled.
  - The plugin root changes on every update, so keep persistent environments under `${CLAUDE_PLUGIN_DATA}`.
  - Today, plugin.json ships no hooks, commands or MCP servers.
- **The seam has two adapters:** Python import (from milestone modules) and the CLI (from skills and hooks). An MCP front is not justified until a live app needs one, and SolidWorks already has one.

## Overhaul 06: the ledger, every number once with unit, band and provenance — 2026-10-11

**Status:** Proposed, not started. Strong. It refines the earlier 2026-10-11 review's 03 and feeds the pending "ledger" decision.

**Skipped / deferred:**
- Not yet decided:
  - the storage format (TOML, YAML or Python);
  - how views render (generated sections or whole files).
- No migration is needed: Ibex restarts, and Plumb and CineWave come later.

**Next:**
- **No number carries a unit, a band or a provenance today.**
  - Every parameter name is written three times (`params.py:27-47`), and `params_checks.py:37` exists only to catch the copies drifting.
  - Units live in comments, and nothing carries a tolerance.
  - `params.toml` is promised (`params.py:8-10`, `armature-derive/SKILL.md:58`), but nothing reads or writes it.
  - The template's `INERTIA = sp.diag(Ix, I, I)` (`params.py:84`) cannot take a CAD tensor back.
- **Provenance has three vocabularies:** `budgets-template:13`, `bom-template:11`, `librarian.md:64`.
- **Status has nowhere to live.**
  - CANDIDATE has no column (`init:94`).
  - Traceability has no failed state (`traceability-template:4`), yet a reserve breach is required to write one (`budgets-template:32-35`).
  - `DENSITY` is copied from bom.md (`part.py:125`).
- **What it costs today:**
  - Ibex's datasheet index is 16,833 words, and every librarian run (`librarian.md:14`) and red-team run (`red-team.md:16`) reads it whole.
  - One parameter change re-pinned 8 checks files in Plumb (`822226f`) and 7 in Ibex (`f2fe7fc`).
  - 4 of the 36 findings were stale or unpropagated numbers. Ibex spec F8 cited CANDIDATE rows as if confirmed.
- **Units: pint 0.26.** It is pure Python, needs Python ≥ 3.12, and does not support SymPy (pint#606).
  - Keep SymPy in SI, and wrap the lambdified functions with `ureg.wraps`.
  - Why bother: the 2026-09-15 note found no unit errors in Plumb, but a unit slip in the shared parameter file is common-mode. Both models read it and agree, so the truth check cannot see it.
- **Provenance rungs:** estimate → datasheet → CAD-measured → bench-measured. Status is CANDIDATE or confirmed, and the gate (07) refuses a purchase that rests on an estimate.
- **First slice** (from the earlier review): run `check` over today's markdown before any table moves. It should catch:
  - stale prices
  - breached reserves
  - untraced Musts
  - CANDIDATE citations
  - CONTEXT symbols that disagree with params.py

## Overhaul 07: reviews land as checks, and a hook runs the gate — 2026-10-11

**Status:** Proposed, not started. Strong.
- It makes the earlier 2026-10-11 review's 05 (one gate) enforceable, and absorbs its 08 (one home per rule).
- It feeds the pending "gates instead of the Stage line" decision.

**Skipped / deferred:**
- Still undecided:
  - which actions gate: milestone merge, purchase commit, release grade;
  - the evidence each action requires;
  - where a review's checks live in a project;
  - how a project argues an exemption.

**Next:**
- **Reviews recompute and keep nothing.** The ten reviews in Plumb and Ibex recompute 45 times, and none of it is kept.
  - One of those recomputations, Plumb's 0.85 N·m/rad (`rev1.2-review:8,:36`), was itself wrong and reached a live ticket.
  - The earlier review also found 12 Ibex fixes self-certified 14 minutes after their review.
- **Most of the checklist is mechanical.** `references/review-checklist.md` has 43 probes: 23 mechanical, 18 judgment, and 2 mixed (L32 modes, L35 σ sweep).
  - Three probes re-judge tests that already fail:
    - L34 ↔ `verification_checks.py:56`
    - L36 ↔ `params_checks.py:55`
    - L38 ↔ `kinematics_checks.py:77`
- **Prose only today:**
  - the seven standing rules (`init:198-210`);
  - derive's merge "phase gate" (`armature-derive/SKILL.md:14-19`);
  - `part_template/run_all.py:6-7`, which calls itself a pre-commit hook, though nothing installs one.
- **Documented hook behaviour:**
  - A plugin ships hooks in `hooks/hooks.json`, or in a `hooks` field in plugin.json.
  - PreToolUse blocks either by exiting 2 (stderr goes to Claude) or with `permissionDecision: "deny"`.
  - Use `matcher: "Bash"` plus `if: "Bash(git commit *)"`. The `if` match is best-effort, so enforce the rule in the script itself, which reads `tool_input` from stdin.
  - SessionStart's stdout joins the context, but SessionStart cannot block. Stop can.
  - On Windows, use the exec form with a real executable. On this machine `python` is the WindowsApps shim, so call `py` or `uv run`.
- **Dependencies:** 05 (the `armature gate` verb) and 06 (margins and staleness). Without them, a first gate can still check that the required artifacts exist and that `run_all` is green.

## Overhaul 08: geometry becomes the truth model's bodies — 2026-10-11

**Status:** Proposed, not started. Worth exploring rather than Strong, because no project has reached CAD yet. It absorbs the earlier 2026-10-11 review's 07 (part targets, two adapters).

**Bugs found:**
- `check/mass.py:45-47` moves the inertia's reference point but never rotates its axes, though `documentation-standards.md:92` asks for "point and axes". → Proposed fix: c′ = T⁻¹c and I′ = RᵀIR.
- Feeding SolidWorks' mass-properties output (`sw.py:232-238`) into `compare_to_target` raises `KeyError 'com'`.
- `part.py:137` (reproduced): a part file named the documented way, such as `ARM-BRK-001.py`, sorts before `layout.py`. `import layout` then loads `analysis/model/layout.py`, so the CAD budget gate never runs.
- `README.md:79` says build123d was tested on 0.11.1, but `~=0.11` resolves to 0.13.0. All 29 self-tests pass on 0.13.0.

**Skipped / deferred:**
- Whether build123d becomes the canonical geometry for every part, or only for the truth model's bodies.
- How SolidWorks-first users key their bodies to the description.

**Next:**
- **Only mass is driven today.**
  - `_resolve_target` returns `{"mass": …}` (`part.py:186-189`) and falls back to a typed `BUDGET_MASS` (`:148`).
  - COM and inertia are hand-typed into commented-out lines (`:207-216`).
  - SolidWorks readings are judged by eye (`solidworks.md:65`).
- **The path from build123d to MJCF works (verified):**
  1. Per link, set the material.
  2. Read `mass()`, `center(MASS)`, and `matrix_of_inertia`·ρ·1e-15 (kg·m²).
  3. Transform COM and inertia into the body frame.
  4. Call `export_stl`, then `spec.add_mesh(scale=[1e-3]*3)`.
  5. Add a geom with `type=mesh, density=0`, and give the body an explicit inertial (`mass`, `ipos`, `fullinertia`).
  6. Compile. As a gate, recompile with exact mesh inertia and compare.
- **Results on an L-bracket:**
  - The explicit inertial matched to 1e-14.
  - Exact mesh inertia matched to 7e-9.
  - MuJoCo's default (legacy) mesh inertia overcounted the mass by 13.7 %. Never rely on the defaults.
  - MuJoCo reads only STL, OBJ and MSH meshes.
- **Multi-material Compounds:** `mass()` is density-weighted, but `center(MASS)` and `matrix_of_inertia` are not (4.7 mm against a true 10.7 mm). Compute each solid separately and combine.
- **Sweep speed on the same 2R grid:**

  | Method | Workload | Time |
  |---|---|---|
  | OCC booleans | 1,400 postures | ~16 s |
  | MuJoCo, primitive geoms | same 1,400 postures | 4.7 ms |
  | MuJoCo, signed clearance via `mj_geomDistance` | 100k random postures | 0.27 s |
- **Second adapter, and the shelved route:**
  - `sw2robot` 0.4.4 (SolidWorks → URDF and MJCF over COM, first released 2026-06; not verified here) is a candidate second adapter.
  - The Onshape API stays shelved (#45, quota), and onshape-to-robot depends on it.

## Overhaul 09: loads come from the truth model, and structure checks actually run — 2026-10-11

**Status:** Proposed, not started. Worth exploring. It is a margins adapter, and it feeds the "where feasibility lives" decision.

**Skipped / deferred:**
- Which parts get a solid FEA and which get section or frame checks. Decide by consequence, per the FoS table.
- Where material derates come from (06).

**Next:**
- **No code produces part loads.**
  - The truth model returns joint torques only (`truth/inverse.py:125-129`).
  - `armature-derive/SKILL.md:100` says "Newton-Euler if the user needs joint reaction forces".
  - CAD Loads sections are copied by hand from the prose in `03_results.md` (`armature-cad/SKILL.md:18,77-80`).
  - `mj_rnePostConstraint` → `data.cfrc_int` would give every body's 6-axis wrench in one call.
- **What exists:**
  - an FoS-by-consequence table (`documentation-standards.md:27-35`)
  - σ = Mc/I and bolt shear, written as prose (`:39`)
  - ISO 273 clearance and edge distance, in code (`part.py:96-123`)
  - a typed `BOSS_WALL` with a hoop-stress comment and no computation (`:92`)
- **Absent repo-wide:** deflection, fatigue, bearing L10, VDI 2230 preload, press-fit and buckling.
- **Five places defer to an FEA that has no way to run:** `armature-cad/SKILL.md:149`, `documentation-standards.md:34`, `:37` and `:39`, and `part_template/README.md:107`.
- **CineWave v1's postmortem**, the failures this would have caught:
  - the J2 bracket tore at a singularity;
  - backlash reached 13′ against a 6.5′ spec, from PA6-CF moisture creep;
  - homing drove 7.5 N·m into a hard stop.
- **Libraries, verified to install on this host:**
  - PyNite 3.2, for frames (MIT, pure Python).
  - sectionproperties 3.10, which takes build123d sections via DXF. Its Triangle mesher restricts commercial distribution.
  - gmsh 4.15 (pip; GPL).
  - scikit-fem 12 (BSD).
  - pyLife 2.3, for FKM Goodman, Miner and rainflow (Apache-2.0).
  - bd_warehouse 0.4, for fastener and bearing geometry.
  - The exception is CalculiX 2.23: on Windows it comes from conda-forge only.
- **Write these ourselves.** No maintained library covers VDI 2230 or L10.
  - L10 = (C/P)^p, per ISO 281.
  - Code VDI 2230 and test it against the guideline's worked examples.
- **Depends on:**
  - 01, for the wrenches
  - 02, for worst cases, including stall torque
  - 03, for the mission's load spectrum, which fatigue needs
  - 06, for allowables with provenance

## Overhaul 10: symbolic where a human reads it, numeric where a part is sized — 2026-10-11

**Status:** Proposed, not started. Worth exploring. This changes derive's identity: above three joints, the Lagrangian is no longer where sizing numbers come from.

**Skipped / deferred:**
- Whether Milestone 2's Lagrangian stays mandatory above three joints.
- What counts as a "subsystem" in the description.

**Next:**
- **Measured on a scratch copy** (py 3.14, sympy 1.14):

  | Links | `import dynamics.lagrangian` | `import kinematics` |
  |---|---|---|
  | 2 | 9.5 s | 1.7 s |
  | 3 | 49.4 s | 4.6 s |
  | 4 | timed out after 240 s | 17.8 s |

  - Both modules are rebuilt on every run (`lagrangian.py:115`, `kinematics.py:66`).
  - Four simplify/trigsimp passes (`lagrangian.py:94-111`), and DH frames built by hand (`:29-54`) rather than through `PinJoint`/`System`, are the likely cost.
  - On the 2R template, the symbolic import is 3.15 s of a 4.75 s run.
  - CineWave V2 has six joints.
- **What sympy 1.14 already offers:**
  - `System` takes joints, loads, actuators and holonomic (loop) constraints. `form_eoms` uses Kane's method by default, with Lagrange as an option.
  - `JointsMethod` has been deprecated since 1.13.
  - Actuators include LinearSpring, LinearDamper and CoulombKineticFriction.
  - Pathways include Wrapping around cylinders or spheres, which suits cable routing.
  - Code generation: `lambdify(..., "numpy", cse=True)`.
- **Independence still holds:** the truth model never imports the derivation. Pinocchio, where conda-forge provides it, remains the second numeric backend.
- **Regression guard for any rebuild:** the 2R arm's M, C, g and V are pinned to 1e-12 (`lagrangian_checks.py:45-54`).

## Overhaul 11: hazards seeded from the energy sources — 2026-10-11

**Status:** Proposed, not started. Speculative. It feeds the "where safety lives" decision.

**Skipped / deferred:**
- Everything about its form. It depends on 01 (the mechanism), 03 (the bus model) and 06 (battery and spring data).

**Next:**
- 5 of the 36 Blocker/Major findings are missing or contradictory safety requirements: fall cutoff, low-voltage protection, and operation with a person present. The walk of the three projects concluded these need a hazard template with FMEA rows per energy source, not a library.
- `spec-template.md:168-181` ("Mechanical safety") asks about stored energy on power loss and about tip-over, but only as questions. Nothing computes the energies.
- The idea is to enumerate the energy sources from the description and the bus model:
  - height: m g Δh, at the worst pose
  - motion: ½ q̇ᵀ M q̇, at `QD_LIMITS`
  - regen: ∫ τω dt, into the bus
  - springs, struts and cables: ½ k x²
  - battery: Wh, from the ledger
- Then seed one row for each source in each of four states: power loss, fault, e-stop, person present. The mitigation cells stay a judgment call, and a blank one is a finding.

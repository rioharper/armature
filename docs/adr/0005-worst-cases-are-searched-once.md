# ADR 0005 — A worst case is searched by one engine module, and a margin is slack over a named space

2026-10-11 — Status: accepted (replaces the method hierarchy in `derivation-standards.md` and the corner sweep's rule text)

Every worst case a project claims is found by `armature.search`, one module of
the engine (ADR 0004). A **margin** is a named callable that takes one point of
a **search space** and returns slack: available minus required, against a limit
with its derating already applied, so slack ≥ 0 passes and −∞ is a legal value.
The space is built from named axes — `Interval`, `Choice`, `Direction`, `Band`
and `Coordinates` — so posture, load direction, sign, load case and tolerance
band are all dimensions of one search, not separate habits. The method is fixed:
a seeded Sobol set plus every corner of the continuous axes, then a bounded
Powell polish from the best few points; `Choice` axes are enumerated. The result
is the minimum over every point evaluated, and it reports where, how many
evaluations, the seed, the pre-polish best, the rejections, and the coverage.
Projects declare margins; they do not write searches.

Ten of the 36 Blocker/Major findings in Plumb and Ibex read a worst case at one
named posture, direction, sign or nominal value. Each project then wrote its own
grids, factorials and bisections — none with an optimiser — and the plugin held
three more: `verification.py`'s grid and L-BFGS-B, the CAD sweep's full
factorial, and a corner sweep that existed only as text. Probed on 2026-10-11,
pure sampling never landed on a worst case even at 10⁴ points (0.14–0.64 N short
on a cable platform's tension floor), because the worst sits on a box corner or
at a stationary point between samples; every method with a local stage matched
the closed-form answers to 1e-10. Sobol plus corners plus Powell did so on both
golden margins in 650–1,100 evaluations. `differential_evolution` cost 3–4× as
much for the same answer, and `shgo` at its defaults returned a wrong answer
after 17 evaluations — a trap no project should be able to walk into.

Rejected: a search per stage or per project (the status quo, which forked);
dense sampling as evidence (it brackets nothing); a configurable method (each
knob is a way to under-search); a margin as a method on the engine's `State`
(half the findings' margins are an LP, a root-find or an ODE, not an engine
query).

The cost accepted: a fixed local method can still miss a narrow interior hole
in a non-monotone margin, as Ibex's success-versus-μ map showed; coverage is
reported so a thin margin is visible, and the budget is per margin. Revisit if a
margin's worst case is found by review rather than by the search, or if a
margin's evaluation cost makes the default budget unaffordable.

**Amended 2026-10-15 (#96):** a margin may be `strict`, passing only where its
slack is above 0, for a limit that reaching is itself the failure. The bus's
peak V is the one: a driver latches at its trip, so a bus that reaches the
lowest trip has tripped it and stops there, at 0 V of slack.

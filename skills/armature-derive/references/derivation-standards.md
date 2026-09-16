# Derivation Notes — Standards

The target register: a sharp senior engineer's design notebook — the findings they'd actually leave for later-you to pick the project back up from, the story of what they expected, what they tried, and what the numbers said, told alongside the hard math. Not a journal paper. No result gets skipped, but nothing gets padded to look thorough either. If a sentence doesn't carry information later-you would need, cut it.

## File layout

Each project's derivation is four files, not one — the layout and per-milestone content live in SKILL.md. Every file:

- opens with a one-line header: project name, milestone, rev/date, and which module or package accompanies it
- ends with a short revision note: what changed since the last rev and why — this is what makes re-derivations traceable
- stays one continuous argument. The module splits along the note's sections; the note itself never splits, and carries no size gate — `layout.py` reports its length for information only

## Writing rules

1. **Prose carries the argument; equations punctuate it.** Every equation gets a sentence saying what we're about to do and *why*; a significant result gets one sentence of physical interpretation after it. Bullets are for the parameter table and checklists only — not for the derivation steps themselves.
2. **Number every displayed equation** (1), (2), … and refer back by number.
3. **No skipped leaps, but compression is fine.** "Expanding and collecting q̇₁q̇₂ terms" is fine; a step that can't be named is a step that got skipped. If SymPy did an ugly simplification, say so briefly rather than presenting the tidy output as if you did it by hand.
4. **Notation discipline.** Define every symbol at first use, use it consistently, match the project's symbol table exactly. State the rotation/frame convention once and don't restate it every section.
5. **Units on every number.** A number without a unit is a typo.
6. **Interpret, don't just derive — but in one sentence, not a paragraph.** After the Jacobian: which postures are singular, and would this robot ever be near them? After gravity terms: which joint carries the worst static load? The one exception to lean is `03_results.md`: findings get the room they need (SKILL.md's Milestone 3 defines what they must contain).
7. **Honest uncertainty, briefly flagged.** An assumption that materially affects results (ignoring friction in a high-reduction gearbox) gets one flag with the expected direction and rough size of the error — in `03_results.md`, not scattered as hedges throughout.
8. **Sanity checks are shown, not claimed.** "Setting l₂ → 0 reduces (12) to the single-pendulum result (13)" — with (13) actually shown. One line is enough: "verified" without the verification fails one way, three sentences of narration around a one-line check fails the other.
9. **No filler, no restating.** Ban: "It is important to note", "In the world of robotics", "delve", "plays a crucial role", restating the section header as the first sentence, and summary paragraphs that repeat what the section just said. If cutting a sentence loses no information, cut it.
10. **LaTeX in markdown** ($...$, $$...$$). **A long symbolic result is printed, never pasted.** Present its structure ("M₁₂ has the form a + b cos q₂ where a = …") and cite the report module that prints the full expression. A result longer than a line of the note is the report module's to carry.
11. **Say what you expected before you computed it.** Every significant result carries the prediction made before the numbers ran — a hand estimate, a limiting case, a hunch with its reason — and whether the result confirmed or surprised it. A confirmed result and a surprising one read differently, and later-you needs to know which this was.
12. **A truth-checked result says whether the truth model confirmed it or surprised it.** Rule 11 in the register the truth model works in: the prediction was the analytic result, the number came from a model that never saw it, and the note says which way it went — "the settle agrees to 0.2 mrad" reads differently from "the settle tilts the platform 5°, and the level-platform assumption is what was wrong". Name the check, its sample size and its seed, and where it surprised you, the paragraph that follows is the finding, not a hedge. A truth check reported as "passed" with no number is rule 8's *claimed, not shown*.
13. **An abandoned approach gets one sentence on why it died.** "Newton-Euler first; dropped because the reaction forces weren't needed and the recursion hid the structure of M." Later-you doesn't re-walk a path already ruled out.

## Evidence over an envelope

A claim about a *set* of configurations — the Jacobian has full rank, the torque stays under the rating, the platform holds level — is evidenced by a **seeded random sample of that set, with the sample size and the seed stated beside the result**. Every checks module draws from the truth package's one sampler (`truth.sample`, `truth.sample_states`, `truth.sample_workspace`), so "over the envelope" means the same set of configurations in the kinematics check, the dynamics check and the worst-case search, and a reviewer re-running the file gets the configurations the note was written from. A sampled claim whose sample size and seed are not in the note is not reproducible, and rule 8 calls it claimed rather than shown.

**A named configuration is never the evidence.** Home, fully outstretched, q = 0, a workspace corner, the symmetric load case: these are the mechanism's symmetry planes, and a symmetry plane is where a wrong assumption cancels — the moment that would tilt the platform is zero there, the rank the structure matrix loses there is the rank it has everywhere. Named configurations are for the reader, printed by the report module (`report_results.py`) beside the sweep minima, and the note quotes them as landmarks. The first real project through this plugin passed every check at its named postures and failed at the first randomly sampled one.

**Every matrix the derivation inverts or pseudo-inverts has its singular values swept** over the sampled envelope, the smallest printed by the report module, and a check bounds it away from zero everywhere the derivation needs full rank. Which set that is, is a decision: the envelope is what the joints reach and the **intended workspace** is what the requirements name, a singularity is allowed to live in the gap between them, and the parameter block carries both (`Q_LIMITS`, `WORKSPACE`) so the bound is asserted on the set the requirement is about. Say which matrix, which set, and what the bound is worth physically — σ_min is a rate, and its reciprocal is the joint speed and joint force one unit of Cartesian motion costs at the worst posture. A rank assumed and never computed is how a rank-3 matrix gets read as four modes.

## Which layer a sentence lives in

A note and its module each carry what the other cannot, and a sentence said in both is paid for on every read of the module. Narrative, derivation, physical argument, and revision history — the story of a correction included — live in the note. The module carries the computation and the least prose a caller needs:

- **Function docstring**: one sentence of what the function computes; the note's equation or section it implements; and anything a *caller* needs that the note does not say — units, sign conventions, failure modes, why a default is what it is.
- **Module docstring**: orientation in about ten lines — the note and sections it mirrors, where its checks live, what it imports — pointing at the note for the argument.

A derivation, a justification of the physics, or the history of a fix belongs in the note, with the docstring citing it. The test for any sentence in a docstring: would it be wrong to say this in the note? If not, it belongs in the note.

## Length is a signal, not a target

This governs the notes; the modules are held to a hard budget instead (the plugin's `references/model-layout.md`). A milestone file that's short because the mechanism is simple is correct. A milestone file that's long because every step is doing real work is also correct. A milestone file that's long because of hedging, restated interpretation, or an equation shown three ways when one would do is the failure mode to catch on re-read — trim it before moving to the next milestone, not at the end when trimming means re-touching four files instead of one.

## References

Cite the convention source (e.g., Craig for mDH, Lynch & Park for PoE) and anything nonstandard, once, in `00_setup.md`. No fake citations — a result from your own derivation needs none.

## Design data from a book

Numbers a design leans on that no vendor publishes — fatigue endurance points, finite-life tables, friction pairs, form factors — have no `docs/datasheets/index.md` row for the librarian to cache, so "cite index rows, never memory" gives them their own rule:

- **Tag it `standard`** in `params.py` and name the book, edition, and the table, figure, or section the number sits in — "Zimmerli's data as Shigley reports it, §10-7"; "Associated Spring finite-life table, Norton Table 14-7". A book named without its table is memory.
- **Find a second independent source and carry both.** Textbook design data is somebody's fit to somebody's tests, and two fits disagree: shot-peened spring wire endurance points differ by 30 % between two standard sources that agree within 6 % unpeened, which is the whole fatigue margin of a peened coil. Read the result against each source, state both, and design to the conservative one.
- **Pin the disagreement with a self-test**, so a later edit cannot quietly swap which source the design leans on.
- **Ask the vendor for its own basis.** A vendor held to the number rates its part against data of its own; that question goes on the questionnaire or the part's specification (`armature-spec`), and its answer supersedes both books.

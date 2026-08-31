# Derivation Notes — Standards

The target register: a sharp senior engineer's design notebook — the notes they'd actually leave for later-you to pick the project back up from. Not a journal paper. No result gets skipped, but nothing gets padded to look thorough either. If a sentence doesn't carry information later-you would need, cut it.

## File layout

Each project's derivation is four files, not one — the layout and per-milestone content live in SKILL.md. Every file:

- opens with a one-line header: project name, milestone, rev/date, and which `.py` module accompanies it
- ends with a short revision note: what changed since the last rev and why — this is what makes re-derivations traceable

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
10. **LaTeX in markdown** ($...$, $$...$$). If a symbolic result is a half-page monster, present its structure ("M₁₂ has the form a + b cos q₂ where a = …") and let the `.py`'s printed output be the full expression — don't paste the monster into the notes.

## Length is a signal, not a target

A milestone file that's short because the mechanism is simple is correct. A milestone file that's long because every step is doing real work is also correct. A milestone file that's long because of hedging, restated interpretation, or an equation shown three ways when one would do is the failure mode to catch on re-read — trim it before moving to the next milestone, not at the end when trimming means re-touching four files instead of one.

## References

Cite the convention source (e.g., Craig for mDH, Lynch & Park for PoE) and anything nonstandard, once, in `00_setup.md`. No fake citations — a result from your own derivation needs none.

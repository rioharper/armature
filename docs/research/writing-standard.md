# The writing standard for Armature skill/agent docs

**Question:** What, concretely, must every new and rewritten Armature skill/agent doc meet?
**Sources (primary):** `writing-for-agents` v1.1+ — `SKILL.md`, `SKILL-MECHANICS.md`, and its docs page
(`~/Documents/skills/skills/productivity/writing-for-agents/`, `~/Documents/skills/docs/productivity/writing-for-agents.md`), read 2026-08-30.
**Status:** research only — nothing fixed. Section cites (§) refer to headings in the source SKILL.md.

This checklist is self-contained: apply it without re-reading the sources.

## The standard — checklist

### 1. Reader model (docs page, "Common questions")
- The agent has already read everything; explanation is waste, precision is the whole job.
- The default editing move is **deletion**, not explanation. A good doc gets *shorter* as it gets better.

### 2. The two loads (§The two loads)
- Every line spends **context load** (always-loaded: descriptions, CLAUDE.md lines — costs every turn) or
  **cognitive load** (the human remembers it exists). Know which, per line.
- Material that applies in 1 context out of 10 must not be always-loaded — it pays context load the other 9.

### 3. Pointers — frontmatter `description`s, CLAUDE.md lines (§Context pointers)
- A pointer does two jobs: say **what the material is** + list the **trigger branches** (distinct cases).
- **One trigger per branch.** Synonyms renaming one branch are that branch written twice — collapse them.
- **Front-load the leading word**; cut identity the body already carries.
- Always-loaded pointers earn *harder* pruning than the body.
- A must-have target behind weak wording is a variance bug: sharpen the wording first; inline only if that fails.

### 4. Information hierarchy (§Information hierarchy)
- Two content types: **steps** (ordered actions) and **reference** (consulted on demand). Place each on the
  ladder: (1) in-file step, (2) in-file reference, (3) disclosed reference behind a pointer.
- Disclosure test = **branching**: inline what every branch needs; push behind a pointer what only some
  branches reach. In-file reference that should be disclosed buries the steps — a variance bug, not just bloat.
- **Co-locate**: one concept's definition, rules, and caveats under one heading, never scattered.
- **Sprawl** = too long even when every line is live. Cure: disclose down the ladder, or split by branch/sequence.

### 5. Steps and completion criteria (§Steps and completion criteria, §When to split)
- Every step ends on a **completion criterion** the agent can check: done vs. not-done must be decidable.
  Vague bounds ("understanding reached") invite premature completion.
- **Demand** drives legwork: "every modified model accounted for" forces work; "produce a list" does not.
  An all-reference doc still carries an exhaustiveness bar ("every rule applied").
- Strongest criteria are **checkable and exhaustive**.
- Fix order: sharpen the bound first; split the sequence only if it stays irreducibly fuzzy AND you observe
  rushing. Hiding later steps only works across a real context boundary (hand-off/subagent, not inline).

### 6. Leading words and negation (§Leading words)
- A **leading word** is a compact pretrained concept (*tight*, *red*, *gate*) repeated **as a token, never as a
  sentence**. It anchors execution in the body and invocation in the pointer — same word in prompts/docs/code.
- Hunt restatements: a triad spelled out, a sentence gesturing at one idea → collapse to one word.
  ("fast, deterministic, low-overhead" → *tight*.) Prefer pretrained words; coined words pay definition tokens.
- A word too weak to beat the default (*be thorough*) is a no-op; fix = stronger word (*relentless*), not more prose.
- **Prompt the positive.** Negation drags the banned behavior into context and makes it *more* available.
  A prohibition survives only as a hard guardrail you cannot phrase positively — and even then, paired with
  the positive target so attention lands on what to do.

### 7. Pruning (§Pruning)
- **Single source of truth** per meaning. Duplication = the same meaning in two places (the docs page calls it
  "the most reliable sign a document was never tested"); it also inflates that meaning's rank on the ladder.
- The **environment** (scripts, config, layout, `--help`) is a source of truth; a doc restating it is a **cache**.
  Cache only expensive lookups: unwritten conventions, reasons behind choices, gotchas no config confesses.
- Check every line for **relevance**; without pruning the default fate is **sediment** (stale layers).
- Hunt **no-ops** sentence by sentence: does deleting it change behavior vs. the model's default? The test is
  model-relative — settle disagreements by *running* the doc, not debating. Delete the whole sentence, not words.

### 8. Skill-only mechanics (SKILL-MECHANICS.md)
- Choose invocation deliberately: **model-invoked** (has `description` = permanent context load, buys agent
  discovery + reach from other skills) vs. **user-invoked** (`disable-model-invocation: true`, description
  becomes a human-facing one-liner, zero context load). Model-invoke only if the agent or another skill must reach it.
- Shared reference two user-invoked skills need lives in neither — push to a plain external file.
- When user-invoked skills outgrow memory, add one **router skill** naming them all.
- Split off a new model-invoked skill only for a distinct trigger word you actually use, or another skill's reach.

### 9. Acceptance — a doc meets the standard when (docs page, "It's working if")
- It ran correctly at least once, and you can no longer find duplication, sediment, or no-ops.
- Nothing is stated twice, in any form; branch-only reference sits behind pointers.
- A leading word is visibly doing work in more than one place.
- It is written for the *class* of task, not over-fitted to the one run that birthed it.

## Calibration — three current Armature docs vs. the standard

Read in worktree of `armature` main (d24e5a2 era). Docs are strong on §5 (demanding, checkable criteria:
"not done until you can answer these with numbers or an explicit 'unknown, flagged as risk'"; the CAD
template's "Done when" block) and on §4 disclosure to `references/`. The violations below are the habits.

### skills/armature-spec/SKILL.md
- **§3 one-trigger-per-branch** — description (line 3) writes one branch four ways and repeats "trade study"
  verbatim: "run a technical trade study … asks for a design document, requirements doc, trade study, or design review".
- **§7 duplication** — Section-6-feeds-downstream stated twice: "This feeds the parameter table **armature-math**
  and the frame table **armature-plan** will need" (line 29) vs. "this is the section **armature-math** and
  **armature-plan** read first" (line 64).
- **§7 no-op (motivation)** — "Every question you ask now is a week of rework you're saving them later." (line 8):
  deleting it changes no behavior.

### agents/red-team.md
- **§7 duplication** — route-ownership stated three times: "hand it to the skill that owns it" (line 11),
  template field "**Route:** the specific fix and who owns it" (line 55), "Each finding's **Route** line names
  the owner" (line 76). Scope also lands twice: "It does not write specs" (line 11) / "You review; you don't
  rebuild" (line 80).
- **§6 negation-first** — the banned behavior is spoken verbatim before the positive: "Don't ask 'have you
  verified the torque?' — re-run the back-of-envelope" (line 24). Positives are present but trail the prohibitions.
- **§7 no-op (motivation/triad)** — "Every flaw you find at the review table is a flaw the user doesn't find at
  integration, in the field, or on the invoice." (line 9); "Be frustratingly thorough. Be specific. Be right."
  (line 9) pre-duplicates the later "Specific or silent" rule (line 68).

### skills/armature-cad/SKILL.md
- **§4 sprawl + disclosure** — 185 lines; the executable-recipe/build123d material (lines 136–148) is an
  admittedly optional branch inlined: "Offer it, don't impose it — build123d pulls Open Cascade and is not an
  armature dependency" (line 146). Only-some-branches material belongs behind a pointer.
- **§7 cache** — the doc restates sweep.py's caveats at length, then concedes the environment owns them:
  "the caveats live in `sweep.py` beside the knobs that cause them" (line 148).
- **§7 duplication** — lumped-inertia rule twice, nearly verbatim: "If the dynamics lumped this part into a
  larger body, the target is its budget row" (template, line 106) vs. "if the mathematician lumped several
  parts into one body mass, there is no per-part inertia target to invent" (line 165).
- **§3 one-trigger-per-branch** — description (line 3) writes the plan-hand-off branch twice: "is executing a
  plan's detail-design/DFM task for a specific part. Also reach here from armature-plan when a detail-design
  task comes due."

## The three habitual violations (fix these first in any rewrite)

1. **Duplication** — every doc audited states a load-bearing rule in 2–3 places (route-ownership ×3 in
   red-team; lumped-inertia ×2 in cad; downstream-feeds ×2 in spec). Per the source, the surest sign the docs
   were never tested. Rewrite rule: one authoritative site per meaning; elsewhere, at most a leading word.
2. **Pointer bloat / synonym branches** — always-loaded descriptions rename single branches ("trade study"
   twice in spec; the plan-hand-off twice in cad). Rewrite rule: one trigger per genuinely distinct branch,
   leading word front-loaded.
3. **Aphorism-tail no-ops, with negation-first steering** — rules habitually end in a consequence flourish
   ("A guessed bolt pattern is the bracket that doesn't bolt on") and open with the prohibited behavior before
   the positive. Each tail is a no-op candidate; collectively they are sprawl. Rewrite rule: run the no-op test
   per sentence, delete whole sentences, keep at most the strongest demand-amplifier; state the positive first.

**Not violations — keep in rewrites:** the demanding completion criteria, the `references/` disclosure ladder,
and established leading words already doing double duty (*gate*, *grade*, *driven*, *frozen*, *red-team*).

# Questionnaire — pulling answers out of a third party's head

Some unknowns aren't lookupable and aren't the user's to answer: they live with a
named person — a machinist, a vendor's application engineer, a professor. The move
is a **questionnaire**: a Markdown document the user hands that one person to fill
in async, or works through with them on a call. The invoking skill says when to
offer one and where the file goes; this file says how to build it.

**Grill the send, not the subject.** Interview the user only about the send, which
they can always answer, in one AskUserQuestion exchange:

1. **Who is it going to?** Role, expertise, relationship to the user — this fixes
   the tone and how much context the document must carry.
2. **What must they walk away able to decide?** Usually the open questions and
   TBDs that triggered the offer — confirm that list rather than re-derive it.

The document's questions then target the gap between what the recipient knows and
what the user needs. Order them most-important-first — async means you may get only
one pass — and group under `##` theme headings once there are more than a handful.
Every question is one idea, never compound, with an answer stub beneath, and a
one-line _why this matters_ only where the question could be misread or invite a
throwaway answer ("whatever tolerance is standard").

<questionnaire-template>

# <Title>

**Purpose:** the decision riding on these answers.

**From:** <user>, **To:** <recipient>. **How your answers will be used:** <where they go>

## Context

One paragraph orienting a recipient who wasn't in the room. Enough to answer well,
not a page. Numbers with units; attach the drawing or sketch the questions point at.

## How to answer

Deadline and rough effort. Partial answers and "I don't know" are useful — flag
what you're unsure of rather than skipping it.

## <Theme>

### <One question, one idea>

_Why this matters: <only where the question could be misread>_

>

## Anything else?

Anything we didn't ask that we should know?

</questionnaire-template>

Until answers return, the questions ride the invoking skill's artifact as open
questions or TBDs. When they return, fold each answer into the artifact that was
waiting on it, citing the questionnaire; a returned "I don't know" becomes a risk,
never silence.

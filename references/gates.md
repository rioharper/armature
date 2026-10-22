# Merging through the gates

Two actions are gated ([ADR 0011](../docs/adr/0011-actions-are-gated-not-stages.md)):
**`merge`**, a work branch into `main`, and **`buy`**, the merge of an order branch
that adds `docs/orders/<date>-<name>.toml`. The gate recomputes each one's evidence
from the repo every time it is asked, and nothing records a pass. Every stage skill
merges this way; each names its own gate call, because only a skill's text carries
the plugin's paths:

```bash
CLAUDE_PLUGIN_DATA="<plugin data>" bash "<plugin root>/scripts/armature.sh" gate merge
```

Where the shell is PowerShell, with no Git Bash, run the same verb as
`$env:CLAUDE_PLUGIN_DATA = "<plugin data>"; powershell -NoProfile -ExecutionPolicy Bypass -File "<plugin root>/scripts/armature.ps1" gate merge`.
The first call builds the launcher's environment, so it takes a minute.

## The branch

Work that touches what a review gates lands on a branch, `armature/<kind>-<name>`,
cut from `main`: a ledger number, anything under `analysis/model/` or
`analysis/derivation/`, a part definition under `cad/`, spec or plan text, an order
record. A commit on `main` may only re-render the ledger's sections and add or edit
`candidate` ledger entries. The plugin's hook denies a commit on `main` that does
more, with the paths it refused, and the fix is to carry the work onto a branch.

## The merge

1. **Commit, then gate, on the branch:** `gate merge`, with the branch checked out
   and its tree clean. It runs each `run_all.py` with no green stamp for its
   content, stamps the green ones under `.armature/`, and prints one line per item,
   `pass`, `fail` or `waived`, with its detail. It exits 0 only when nothing fails.
2. **Route every `fail`** by the table below, commit, and gate again. Done when it
   exits 0.
3. **Merge:** `git checkout main`, then `git merge --ff-only <branch>`. The hook
   re-reads the evidence (ancestry, ledger, reviews, stamps; it runs nothing) and
   denies the merge with the gate's lines if anything moved since step 2. Route a
   denial the same way, on the branch.
4. **Push**, where the project has a remote: `git push origin main`. The hook
   gates `main` itself on that push, and it passes, because `main`'s tip is the
   tree just gated and the stamps are keyed by content. A denial there means
   `main` holds something no gate saw: run `gate merge` with `main` checked out,
   carry what fails onto a branch, and push again. A work branch pushes freely,
   `git push -u origin <branch>`.

| Item | Fails when | Route |
|---|---|---|
| `fast-forward` | `main` moved since the branch left it | on the branch, `git merge main`, and gate again: the tree checked is the tree `main` becomes |
| `ledger` | `ledger check` reports an error | settle it in `ledger.toml`, then `render` |
| `stamps` | a `run_all.py` fails, or the tree is dirty | fix what fails, or commit. Only the gate writes a stamp; the hook denies any edit under `.armature/` |
| `engine` | a model directory's engine is not `in-step` | armature-derive's checkpoint, on `engine-source.sh check` |
| `review` | the branch changes a gated path, and no review is pinned to a commit on it | commit, and dispatch the red team at that commit (`subagent-dispatch.md`, *Dispatching the red team*) |
| `closed` | a BLOCKER or MAJOR finding is open | close it, below |
| `moves` | a ledger number moved after a review's commit, and no closure names it | add its key to the `moves` of the closure whose fix moved it. A move no finding asked for is new work, with a review of its own |

A branch that changes no gated path needs no review, and the `review` line says so.
That rule is the whole of when a review is due.

## Closing a finding

The red team writes every finding `open`, in the block that ends its review. You
close each BLOCKER and MAJOR there, setting `status` and a `closure` table on its
`[[finding]]`, in one of three ways:

- **A check**, for a finding with a number in it. Land its recomputation as a test,
  `test_F<n>_<what>`, in the review's own checks file,
  `review_<date>_<artifact>_checks.py`, in the folder whose `run_all.py` collects
  it: `analysis/model/` for a spec, plan or derive finding, the part's folder for a
  CAD finding. The test asserts the corrected number from a source independent of
  the fix, so it fails on the defect the finding named. Then `status = "fixed"`,
  `closure = { check = "<checks file>::test_F<n>_<what>" }`. Every later merge
  re-runs it.
- **A recheck**, for a finding no test can hold: a judgment, an argument, a
  requirement's reading. Commit the fix and dispatch the recheck
  (`subagent-dispatch.md`). A finding it marks `holds` closes with
  `status = "fixed"`, `closure = { recheck = "<recheck path>" }`. One it marks
  `reopened` is open again.
- **The user's acceptance**, `status = "accepted"`,
  `closure = { reason = "<the user's reason>" }`, written only on the user's word.
  The hook asks the user before that edit lands.

A closure whose fix moved a ledger number adds `moves = ["<key>", …]`. A MINOR or a
QUESTION never blocks: route it, and leave it `open` until it is settled.

## Confirmations and waivers

Three edits are the user's alone, and the hook asks the user before each lands:
`status = "confirmed"` on a ledger entry (or a `chosen` or `standard` source
kind, which confirms an entry with no status), `accepted` on a finding, and a
`[[waiver]]` in `waivers.toml`. Make one only after the user has given that
decision in the conversation, one decision per edit, and name it in the commit
message.

A waiver exempts one item of a gate's evidence: `gate`, `item` (its id as the
gate prints it), `scope` (the branch, or `standing`), `reason` and `confirmed` (a
TOML date). Propose one only where the item's evidence cannot apply, never where
producing it is costly, and say in `reason` which number it waives and what margin
it accepts. The gate prints each waiver it applies, and the red team challenges
each one in scope.

## `buy`

An order sends money or a drawing out of the project: a purchase, or a release (a
drawing, DXF, quote request or fit print). It is a branch of its own,
`armature/order-<name>`, adding one record, `docs/orders/<date>-<name>.toml`:

```toml
kind = "purchase"            # purchase | release
vendor = "<vendor>"

[[line]]
part = "part.<pn>"           # a purchase line: a part section of the ledger
qty = 1
```

A release line is `definition = "cad/parts/<PART-ID>"` (the part definition's path
without `.md`) and `exports = ["<path>", …]`, the committed files sent. Its gate is
`gate buy`, which the skill names: `merge`'s items, plus every entry of each
ordered part `confirmed` and none an `estimate`, each line's price tier retrieved
within 90 days, and a review that lists the record in its `artifacts`. An order is
never review-free. A release also needs every part's placeholders resolved, and its
own and the model's `run_all.py` stamped green. Merge as above. A pass says the
order is cleared, and nobody can see whether it was placed, so tell the user it is
theirs to place.

## Where the project stands

`gate status` evaluates `merge`, and `buy` on an order branch, for the branch
checked out. It reads the stamps and runs nothing. It is the project's progress
marker: read it in place of any note about how far the project has got.

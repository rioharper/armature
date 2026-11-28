"""`set`: CAD's measured mass, COM and inertia, written back into the ledger.

`set_from_part("part.<pn>", <file>)` runs the part file's mass-properties
export, `python <file> --mass-properties`, which prints one JSON object:

    {"mass": kg, "com": [m, m, m], "inertia": [[kg·m²] * 3] * 3,
     "point": "<the point the tensor is about>",
     "axes": "<the axes the COM and the tensor are in>",
     "origin": "<the point the COM is measured from>"}

It writes `<name>.mass`, `<name>.com` and `<name>.inertia` with
`source = { kind = "cad", ref = "<file>@<rev>" }` and `status =
"candidate"`, the tensor with its `point` and `axes` and the COM with its
`origin` as `point`. It edits an entry through tomlkit and splices only
that entry's body back into the file, so every other byte survives, and
in the entry its comments and every field it does not own, a band
included: a CAD value outside an estimate's band is then `check`'s
finding.
"""

import json
import subprocess
import sys
from pathlib import Path

import tomlkit

from . import newlines
from .entries import LedgerError, find, finite, parse

EXPORT = "--mass-properties"   # the flag a part file's export answers to
UNCOMMITTED = "uncommitted"    # the rev of a file git has no commit of
# What each entry is: the export's key, its unit, its shape.
QUANTITIES = (("mass", "kg", ()), ("com", "m", (3,)),
              ("inertia", "kg*m^2", (3, 3)))
FRAME = ("point", "axes", "origin")
OTHER_KINDS = ("as_written", "basis")   # a cited source's, never cad's


def set_from_part(name, part_file, *, path=None, python=None):
    """Write the measurement `part_file`'s export prints into the ledger
    nearest `path` (default: the working directory), as the entries
    `<name>.mass`, `.com` and `.inertia`; `name` is `part.<pn>`. `python`
    (default: this one) runs the export, so it needs whatever the part file
    imports. Returns the entries it changed: an entry already holding this
    measurement from this rev is left alone, its status included, so a
    second run changes nothing. Refuses an export with no frame for its
    tensor, and leaves the ledger as it was on any refusal."""
    pn = _part_number(name)
    ledger = find(path)
    part = Path(part_file).resolve()
    if not part.is_file():
        raise LedgerError(f"{part_file}: no such part file")
    props = _export(part, python or sys.executable)
    ref = f"{_cited(part, ledger.parent)}@{_rev(part)}"
    raw = ledger.read_bytes()
    text, newline = newlines.split(raw.decode("utf-8"))   # the file's, kept
    doc = tomlkit.parse(text)
    changed, new, edited = [], [], {}
    for key, fields in _entries(props, ref):
        table = doc.get("part", {}).get(pn, {}).get(key)
        if table is None:
            new.append(_toml_table(pn, key, fields))
        elif _update(table, fields, f"{name}.{key}"):
            edited[("part", pn, key)] = table
        else:
            continue
        changed.append(f"{name}.{key}")
    out = _splice(text, edited, doc)
    if new:   # at the end, where no comment above it is anyone else's
        out = out.rstrip("\n") + "\n\n" + "\n\n".join(new) + "\n"
    if out != text:
        newlines.write(ledger, out, newline)
        try:
            parse(ledger)
        except LedgerError:
            ledger.write_bytes(raw)
            raise
    return changed


def _splice(text, edited, doc):
    """`text` with each edited table's body, by its key path, swapped for
    the table's new text, every other line kept as written: tomlkit's
    whole-file dump reformats tables it never touched. Falls back to that
    dump where an edited table has no header line of its own."""
    lines = text.splitlines(keepends=True)
    heads = [(i, path) for i, line in enumerate(lines)
             if line.lstrip().startswith("[")
             and (path := _header(line)) is not False]
    ends = [i for i, _ in heads[1:]] + [len(lines)]
    spans = {path: (i + 1, end) for (i, path), end in zip(heads, ends)}
    if not all(path in spans for path in edited):
        return tomlkit.dumps(doc)
    for path in sorted(edited, key=lambda p: -spans[p][0]):
        start, end = spans[path]
        lines[start:end] = [edited[path].as_string()]
    out = "".join(lines)
    if tomlkit.parse(out).unwrap() != doc.unwrap():   # a header misread
        return tomlkit.dumps(doc)
    return out


def _header(line):
    """A table header line's key path, None for an array of tables', or
    False where the line is no header, such as a tensor's row."""
    try:
        node = tomlkit.parse(line).unwrap()
    except tomlkit.exceptions.TOMLKitError:
        return False
    path = []
    while isinstance(node, dict) and len(node) == 1:
        key, node = next(iter(node.items()))
        path.append(key)
    return tuple(path) if node == {} else None


def _part_number(name):
    section, _, pn = name.partition(".")
    if section != "part" or not pn:
        raise LedgerError(f"{name}: set writes a part's entries, so its name "
                          f"is part.<pn>, such as part.ARM-BRK-001")
    return pn


def _export(part, python):
    """The JSON object the part file's export prints, on its last line."""
    run = subprocess.run([python, str(part), EXPORT], cwd=part.parent,
                         capture_output=True, text=True, encoding="utf-8")
    if run.returncode:
        raise LedgerError(f"{part.name} {EXPORT} exited {run.returncode}:\n"
                          f"{run.stderr.strip()[-2000:]}")
    lines = run.stdout.strip().splitlines()
    try:
        props = json.loads(lines[-1])
    except (IndexError, ValueError):
        props = None
    if not isinstance(props, dict):
        raise LedgerError(f"{part.name} {EXPORT} printed no JSON object; "
                          f"its last line was {(lines or [''])[-1]!r}")
    for field in FRAME:
        text = props.get(field)
        if not isinstance(text, str) or not text.strip():
            raise LedgerError(
                f"{part.name} {EXPORT}: the measurement states the frame it "
                f"is in, and {field!r} is missing: a tensor names the point "
                f"and axes it is about, and a COM the origin it is from")
    return props


def _entries(props, ref):
    """Each entry's key and its fields, in the order a new one is written."""
    for key, unit, shape in QUANTITIES:
        fields = {"value": _number(props, key, shape), "unit": unit}
        if key == "inertia":
            fields |= {"point": props["point"], "axes": props["axes"]}
        if key == "com":
            fields |= {"point": props["origin"], "axes": props["axes"]}
        fields |= {"status": "candidate",
                   "source": {"kind": "cad", "ref": ref}}
        yield key, fields


def _number(props, key, shape):
    """The export's `key`, a float or nested lists of floats of `shape`."""
    x = props.get(key)
    if not shape:
        if not finite(x):
            raise LedgerError(f"{EXPORT}: {key} is a finite number; got "
                              f"{x!r}")
        return float(x)
    if not isinstance(x, list) or len(x) != shape[0]:
        raise LedgerError(f"{EXPORT}: {key} is a list of {shape[0]}; got "
                          f"{x!r}")
    return [_number({key: v}, key, shape[1:]) for v in x]


def _toml_table(pn, key, fields):
    """`[part.<pn>.<key>]` with `fields`, as text, for a new entry."""
    table = tomlkit.table()
    for field, value in fields.items():
        table[field] = _item(value)
    doc = tomlkit.document()
    doc["part"] = tomlkit.table(is_super_table=True)
    doc["part"][pn] = tomlkit.table(is_super_table=True)
    doc["part"][pn][key] = table
    return tomlkit.dumps(doc).strip("\n")


def _update(table, fields, name):
    """Write `fields` into an entry's table, in place, leaving every field
    it does not own; True where the measurement or its source moved, and
    then its status is candidate again. An entry of another kind becoming
    `cad` loses the fields that kind owned, `as_written` and `basis` (its
    source, `retrieved` included, is replaced whole); its `note` and `band`
    stay."""
    if "of" in table:
        raise LedgerError(f"{name}: an of entry, and set writes a value; "
                          f"remove its of first")
    if all(field in table and table[field].unwrap() == value
           for field, value in fields.items() if field != "status"):
        return False
    if table.get("source", {}).get("kind") != fields["source"]["kind"]:
        for field in OTHER_KINDS:
            table.pop(field, None)
    for field, value in fields.items():
        table[field] = _item(value)
    return True


def _item(value):
    """`value` as the ledger's own entries are written: a source as the
    inline table `{ kind = "cad", ref = "…" }`, a tensor a row a line."""
    if isinstance(value, dict):
        pairs = ", ".join(f"{k} = {tomlkit.string(v).as_string()}"
                          for k, v in value.items())
        return tomlkit.parse(f"x = {{ {pairs} }}")["x"]
    if isinstance(value, list) and isinstance(value[0], list):
        rows = tomlkit.array()
        rows.extend(value)
        return rows.multiline(True)
    return value


def _cited(part, root):
    """The part file's path from the ledger's folder, or as it is."""
    try:
        return part.relative_to(root.resolve()).as_posix()
    except ValueError:
        return part.as_posix()


def _rev(part):
    """The last commit of `part`, `+dirty` where the file has changed
    since, or `uncommitted` where git has none."""
    git = ["git", "-C", str(part.parent)]
    try:
        log = subprocess.run(git + ["log", "-1", "--format=%h", "--",
                                    part.name], capture_output=True,
                             text=True)
        dirty = subprocess.run(git + ["status", "--porcelain", "--",
                                      part.name], capture_output=True,
                               text=True)
    except FileNotFoundError:   # no git on PATH
        return UNCOMMITTED
    rev = log.stdout.strip() if log.returncode == 0 else ""
    if not rev:
        return UNCOMMITTED
    return rev + ("+dirty" if dirty.stdout.strip() else "")

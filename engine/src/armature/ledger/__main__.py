"""`py -m armature.ledger check [--json]` and `show <prefix>`, on the
ledger nearest the working directory, or the one `--path` names. `check`
prints one finding per line, `<level> <code> <entry>: <message>`, or a
JSON list with `--json`, and exits 1 on any error; a ledger it cannot read
is an error too.

`set <name> --from-part <file>` runs the part file's `--mass-properties`
export with this Python, writes its mass, COM and inertia as `cad`
candidates, and prints each entry it changed; run it where the part file's
imports are, `uv run --with 'build123d~=0.11'` for a build123d recipe."""

import argparse
import json
import sys

from .check import check
from .entries import LedgerError
from .show import show
from .write import set_from_part


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m armature.ledger")
    verbs = parser.add_subparsers(dest="verb", required=True)
    for verb in ("check", "show"):
        sub = verbs.add_parser(verb)
        sub.add_argument("--path", help="the ledger, or a folder at or "
                         "below it (default: the working directory)")
    verbs.choices["check"].add_argument("--json", action="store_true")
    verbs.choices["show"].add_argument("prefix")
    put = verbs.add_parser("set", help="write a part file's measured mass, "
                           "COM and inertia as cad candidates")
    put.add_argument("name", help="the part's entries, part.<pn>")
    put.add_argument("--from-part", required=True, metavar="FILE",
                     help="the part file whose --mass-properties export "
                     "this runs")
    put.add_argument("--path", help="the ledger, or a folder at or below it "
                     "(default: the working directory)")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):   # a Windows pipe is cp1252
        stream.reconfigure(encoding="utf-8")
    try:
        if args.verb == "set":
            changed = set_from_part(args.name, args.from_part,
                                    path=args.path)
            print("\n".join(f"set {name}" for name in changed)
                  or f"{args.name}: unchanged")
            return 0
        if args.verb == "show":
            print(show(args.prefix, path=args.path))
            return 0
        findings = check(args.path)
    except LedgerError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    else:
        for f in findings:
            print(f)
    return int(any(f.level == "error" for f in findings))


if __name__ == "__main__":
    sys.exit(main())

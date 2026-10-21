"""`py -m armature.gate <merge|status> [--branch <b>] [--json] [--fresh]`,
on the repo holding the working directory.

`merge` prints one line per item of evidence, `pass|fail|waived <item>
<detail>`, then a `warning` line for each waiver it ignored; it runs each
`run_all.py` with no green stamp for its content. `status` prints every
gate that applies to the branch, each under its name, reading the stamps
and running nothing. `--json` prints the verdicts instead. Either exits 1
on any failed item, and 2 when no gate can be computed: no git repo, no
such branch, or a detached HEAD with no `--branch`."""

import argparse
import json
import sys

from . import GateError, merge, status


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m armature.gate")
    parser.add_argument("verb", choices=("merge", "status"))
    parser.add_argument("--branch", help="the branch to gate (default: "
                        "HEAD's)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fresh", action="store_true",
                        help="run every run_all.py, ignoring the stamps")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):   # a Windows pipe is cp1252
        stream.reconfigure(encoding="utf-8")
    try:
        verdicts = ([merge(branch=args.branch, fresh=args.fresh)]
                    if args.verb == "merge" else status(branch=args.branch))
    except GateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        out = [v.as_dict() for v in verdicts]
        print(json.dumps(out[0] if args.verb == "merge" else out, indent=2))
    elif args.verb == "merge":
        print("\n".join(verdicts[0].lines()))
    else:
        for v in verdicts:
            print(f"{v.gate} {v.branch} at {v.tip[:7]}: "
                  f"{'passes' if v.passed else 'fails'}")
            print("\n".join(f"  {line}" for line in v.lines()))
    return int(not all(v.passed for v in verdicts))


if __name__ == "__main__":
    sys.exit(main())

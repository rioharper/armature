"""
The kit's checks from a shell, SOLIDWORKS running. From the folder holding swkit/:

    uv run --no-project --with pywin32 python -m swkit status
    uv run --no-project --with pywin32 python -m swkit audit  PART.SLDPRT
    uv run --no-project --with pywin32 python -m swkit rebuild PART.SLDPRT w t --by 0.9 1.1
    uv run --no-project --with pywin32 python -m swkit step   PART.SLDPRT OUT.step [--config NAME]
    uv run --no-project --with pywin32 python -m swkit restart [--simulation]

`audit` and `rebuild` open the part, change nothing on disk and close it, and exit 1 on a
failure. `restart` ends SOLIDWORKS: run it only on the user's word, with no document open.
"""
from __future__ import annotations

import argparse
import sys

from . import com, measure
from .exchange import export_step


def _status(a):
    app = com.attach()
    print(f"SOLIDWORKS {app.RevisionNumber} at {com.install_dir()}; open: {com.titles(app) or 'nothing'}")
    return 0


def _audit(a):
    app = com.attach()
    bad = 0
    with com.opened(app, a.part) as doc:
        for cfg in list(doc.GetConfigurationNames or []):
            doc.ShowConfiguration2(cfg)
            doc.ForceRebuild3(False)
            errs = com.errors(doc)
            faceless = measure.faceless_bosses(doc)
            bodies = measure.solid_bodies(doc)
            bad += bool([e for e in errs if e[2] == "error"]) + bool(faceless)
            print(f"  {cfg}: {len(bodies)} bodies, {sum(measure.volume(b) for b in bodies):,.1f} mm^3"
                  + (f"; errors/warnings {errs}" if errs else "")
                  + (f"; faceless bosses {faceless}" if faceless else ""))
    print("clean" if not bad else f"{bad} configuration finding(s)")
    return 1 if bad else 0


def _rebuild(a):
    app = com.attach()
    rows = measure.rebuild_test(app, a.part, a.names, a.by)
    bad = 0
    for factor, cfg, n, vol, errs, warns in rows:
        bad += bool(errs)
        print(f"  x{factor:.2f} {cfg}: {n} bodies, {vol:12,.1f} mm^3"
              + (f"; errors {errs}" if errs else "") + "".join(f"; warning {w[0]}" for w in warns))
    print(f"{bad} run(s) with errors")
    return 1 if bad else 0


def _step(a):
    app = com.attach()
    size, schema = export_step(app, a.part, a.out, a.ap, a.config)
    print(f"wrote {a.out}: {size / 1e6:.2f} MB, {schema}")
    return 0


def _restart(a):
    com.restart(addins=[com.SIMULATION] if a.simulation else ())
    print("SOLIDWORKS restarted")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="swkit", description=__doc__.strip().splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=_status)
    s = sub.add_parser("audit", help="rebuild errors and faceless bosses, every configuration")
    s.add_argument("part")
    s.set_defaults(fn=_audit)
    s = sub.add_parser("rebuild", help="rebuild with globals scaled together")
    s.add_argument("part")
    s.add_argument("names", nargs="+")
    s.add_argument("--by", nargs="+", type=float, default=[0.9, 1.1])
    s.set_defaults(fn=_rebuild)
    s = sub.add_parser("step", help="a STEP copy, its schema read back")
    s.add_argument("part")
    s.add_argument("out")
    s.add_argument("--ap", type=int, default=214, choices=(203, 214))
    s.add_argument("--config")
    s.set_defaults(fn=_step)
    s = sub.add_parser("restart", help="end and restart SOLIDWORKS, holding no document")
    s.add_argument("--simulation", action="store_true", help="and load Simulation")
    s.set_defaults(fn=_restart)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

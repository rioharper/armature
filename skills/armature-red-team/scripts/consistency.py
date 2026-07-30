#!/usr/bin/env python3
"""
consistency.py — mechanical cross-document checks for an Armature project.

Does in seconds what a careful human reader does badly: catching identifier and
number drift between the spec, the BOM, the plan, the model, and the state file.

    python consistency.py --repo /path/to/project
    python consistency.py --repo . --json      # machine-readable

Exit codes: 0 all checks clean, 1 findings present, 2 could not run.

A clean run means the mechanical checks passed. It says nothing about whether
the physics is right — that is what the human half of the review is for.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("consistency.py needs pyyaml:  pip install pyyaml")

STATUSES = {"confirmed", "tbd", "assumed"}
REL_TOL = 1e-9


@dataclass
class Report:
    findings: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, check: str, severity: str, message: str, where: str = "") -> None:
        self.findings.append(
            {"check": check, "severity": severity, "message": message, "where": where}
        )

    def note(self, message: str) -> None:
        self.notes.append(message)


# ── helpers ───────────────────────────────────────────────────────────────────


def read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def load_yaml(path: Path, rpt: Report) -> dict | None:
    text = read(path)
    if text is None:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        rpt.add("bom", "BLOCKER", f"{path.name} does not parse: {exc}", str(path))
        return None
    return data if isinstance(data, dict) else None


def bom_entries(bom: dict):
    """Yield (group, entry) for every list-valued top-level group."""
    for group, items in bom.items():
        if isinstance(items, list):
            for entry in items:
                if isinstance(entry, dict):
                    yield group, entry


def numeric_assignments(py_path: Path) -> dict[str, float]:
    """
    Extract numeric values from a params module without importing it, so the
    checker never needs the project's dependencies installed.

    Handles module-level `NAME = 3.4`, negatives, and string-keyed dict
    literals (`PARAMS = {"tau_hip_max": 3.0}`), one level deep.
    """
    text = read(py_path)
    if text is None:
        return {}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}

    found: dict[str, float] = {}

    def as_number(node: ast.AST) -> float | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = as_number(node.operand)
            return None if inner is None else -inner
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            value = as_number(node.value)
            if value is not None:
                found[target.id] = value
            elif isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        inner = as_number(v)
                        if inner is not None:
                            found[k.value] = inner
    return found


def close_enough(a: float, b: float) -> bool:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= REL_TOL * scale


# ── checks ────────────────────────────────────────────────────────────────────


def check_traceability(repo: Path, rpt: Report) -> None:
    brief = read(repo / "docs" / "concept-brief.md")
    spec = read(repo / "docs" / "spec.md")
    plan = read(repo / "docs" / "plan.md")

    if spec is None:
        rpt.note("no docs/spec.md — traceability checks skipped")
        return

    if brief:
        rcs = sorted(set(re.findall(r"\bRC-\d{3}\b", brief)))
        for rc in rcs:
            if rc not in spec:
                rpt.add(
                    "traceability",
                    "MAJOR",
                    f"{rc} is in the concept brief but never referenced in the spec — "
                    "an outcome-level requirement with no engineering requirement behind it",
                    "docs/concept-brief.md",
                )

    reqs = sorted(set(re.findall(r"\bREQ-\d{3}\b", spec)))
    if not reqs:
        rpt.add(
            "traceability",
            "MAJOR",
            "spec contains no REQ-nnn identifiers — requirements are unnumbered "
            "and therefore untraceable",
            "docs/spec.md",
        )
        return

    # A Must requirement is one whose line carries "Must" (the spec template's
    # priority column) — checked case-sensitively to avoid matching prose "must".
    musts = [
        req
        for line in spec.splitlines()
        if "Must" in line
        for req in re.findall(r"\bREQ-\d{3}\b", line)
    ]
    musts = sorted(set(musts))

    if plan is None:
        if musts:
            rpt.note(
                f"no docs/plan.md — {len(musts)} Must requirements could not be "
                "traced to verification tasks"
            )
        return

    for req in musts:
        if req not in plan:
            rpt.add(
                "traceability",
                "MAJOR",
                f"{req} is a Must requirement with no verification task in the plan "
                "— a requirement with no test is a wish",
                "docs/plan.md",
            )


def check_bom(repo: Path, rpt: Report) -> dict | None:
    bom_path = repo / "docs" / "bom.yaml"
    bom = load_yaml(bom_path, rpt)
    if bom is None:
        rpt.note("no readable docs/bom.yaml — BOM and drift checks skipped")
        return None

    state = read(repo / ".armature" / "state.md") or ""
    manifest = load_yaml(repo / "refs" / "datasheets" / "manifest.yaml", rpt)
    manifest_files = set()
    if isinstance(manifest, list):
        manifest_files = {e.get("file") for e in manifest if isinstance(e, dict)}
    elif isinstance(manifest, dict):
        entries = manifest.get("datasheets", [])
        if isinstance(entries, list):
            manifest_files = {e.get("file") for e in entries if isinstance(e, dict)}

    seen_ids: set[str] = set()

    for group, entry in bom_entries(bom):
        eid = entry.get("id") or "<unnamed>"
        where = f"docs/bom.yaml:{group}:{eid}"

        if eid == "<unnamed>":
            rpt.add("bom", "MINOR", f"entry in '{group}' has no id", where)
        elif eid in seen_ids:
            rpt.add("bom", "MAJOR", f"duplicate BOM id '{eid}'", where)
        else:
            seen_ids.add(eid)

        status = entry.get("status")
        if status not in STATUSES:
            rpt.add(
                "bom",
                "BLOCKER",
                f"status is {status!r}; must be one of {sorted(STATUSES)} — "
                "a number with no status is the failure this file exists to prevent",
                where,
            )

        params = entry.get("params") or {}
        if not isinstance(params, dict) or not params:
            rpt.add("bom", "MINOR", "no design-driving parameters listed", where)
            params = {}

        for pname, pdef in params.items():
            if not isinstance(pdef, dict):
                rpt.add("bom", "MAJOR", f"parameter '{pname}' is not a mapping", where)
                continue
            if "unit" not in pdef:
                rpt.add("bom", "MINOR", f"parameter '{pname}' has no unit", where)
            if pdef.get("value") is None and status == "confirmed":
                rpt.add(
                    "bom",
                    "MAJOR",
                    f"parameter '{pname}' is null on a confirmed entry — "
                    "confirmed means the datasheet is in hand",
                    where,
                )

        if status == "tbd":
            if eid not in state:
                rpt.add(
                    "bom",
                    "MAJOR",
                    f"'{eid}' is tbd but does not appear in .armature/state.md — "
                    "an unsourced number that nothing is tracking",
                    where,
                )
            if not entry.get("resolve"):
                rpt.add(
                    "bom",
                    "MINOR",
                    f"'{eid}' is tbd with no resolve plan",
                    where,
                )

        if status == "assumed":
            rpt.add(
                "bom",
                "QUESTION",
                f"'{eid}' carries assumed values — confirm this risk is still "
                "knowingly accepted",
                where,
            )

        ds = entry.get("datasheet")
        if status == "confirmed":
            if not ds:
                rpt.add(
                    "bom",
                    "MAJOR",
                    f"'{eid}' is confirmed with no datasheet path",
                    where,
                )
            else:
                if not (repo / ds).exists():
                    rpt.add(
                        "bom",
                        "MAJOR",
                        f"datasheet '{ds}' is referenced but not on disk — "
                        "a link in a transcript is not provenance",
                        where,
                    )
                if manifest_files and Path(ds).name not in {
                    Path(f).name for f in manifest_files if f
                }:
                    rpt.add(
                        "bom",
                        "MINOR",
                        f"datasheet '{Path(ds).name}' is not in the manifest, "
                        "so it has no retrieval date",
                        where,
                    )
    return bom


def check_param_drift(repo: Path, bom: dict | None, rpt: Report) -> None:
    if bom is None:
        return
    models = sorted(repo.glob("analysis/*_model/params.py"))
    if not models:
        rpt.note("no analysis/*_model/params.py — parameter drift check skipped")
        return

    values: dict[str, float] = {}
    for path in models:
        values.update(numeric_assignments(path))

    if not values:
        rpt.note(
            "params.py held no statically-readable numbers — drift check "
            "could not run (values may be computed rather than literal)"
        )
        return

    checked = 0
    for group, entry in bom_entries(bom):
        eid = entry.get("id", "<unnamed>")
        for pname, pdef in (entry.get("params") or {}).items():
            if not isinstance(pdef, dict):
                continue
            key = pdef.get("params_key")
            if not key:
                continue
            bom_value = pdef.get("value")
            if bom_value is None:
                continue
            checked += 1
            if key not in values:
                rpt.add(
                    "drift",
                    "MAJOR",
                    f"'{eid}.{pname}' names params_key '{key}', which does not "
                    "exist in params.py — the BOM believes the model consumes a "
                    "value it never sees",
                    f"docs/bom.yaml:{group}:{eid}",
                )
            elif not close_enough(float(bom_value), values[key]):
                rpt.add(
                    "drift",
                    "BLOCKER",
                    f"'{key}' is {bom_value} {pdef.get('unit', '')} in bom.yaml but "
                    f"{values[key]} in params.py — the derivation is validating a "
                    "robot the BOM does not describe",
                    f"docs/bom.yaml:{group}:{eid}",
                )
    if checked == 0:
        rpt.note(
            "no BOM parameter carried a params_key — nothing links the BOM to "
            "the model, so drift between them cannot be detected"
        )


def check_symbols(repo: Path, rpt: Report) -> None:
    claude = read(repo / "CLAUDE.md")
    if claude is None:
        rpt.add(
            "symbols",
            "MAJOR",
            "no CLAUDE.md at the repo root — frames and symbols are undeclared, "
            "so every downstream skill is free to invent its own",
            "CLAUDE.md",
        )
        return

    declared = set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", claude))
    if not declared:
        rpt.add(
            "symbols",
            "MAJOR",
            "CLAUDE.md declares no code names in its symbol table",
            "CLAUDE.md",
        )
        return

    for path in sorted(repo.glob("analysis/*_model/params.py")):
        for name in numeric_assignments(path):
            root = name.split("_")[0]
            if name not in declared and root not in declared:
                rpt.add(
                    "symbols",
                    "MINOR",
                    f"'{name}' is set in {path.name} but neither it nor its root "
                    f"'{root}' appears in the CLAUDE.md symbol table",
                    str(path.relative_to(repo)),
                )


def check_frontmatter(repo: Path, rpt: Report) -> None:
    """
    Every document a skill writes opens with YAML frontmatter, so Obsidian can
    read it as properties. A missing block is a document no query will find.
    """
    roots = [repo / "docs", repo / "reviews", *repo.glob("analysis/*_derivation")]
    checked = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            text = read(path)
            if text is None:
                continue
            checked += 1
            rel = str(path.relative_to(repo))
            if not text.startswith("---"):
                rpt.add("frontmatter", "MINOR", "no YAML frontmatter block", rel)
                continue
            end = text.find("\n---", 3)
            if end == -1:
                rpt.add("frontmatter", "MINOR", "frontmatter block is unterminated", rel)
                continue
            try:
                meta = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError as exc:
                rpt.add("frontmatter", "MINOR", f"frontmatter does not parse: {exc}", rel)
                continue
            if not isinstance(meta, dict):
                rpt.add("frontmatter", "MINOR", "frontmatter is not a mapping", rel)
                continue
            for field in ("type", "project"):
                if field not in meta:
                    rpt.add("frontmatter", "MINOR", f"frontmatter has no '{field}'", rel)
    if checked == 0:
        rpt.note("no markdown documents found to check frontmatter on")


def check_cad(repo: Path, rpt: Report) -> None:
    """
    Part definitions claim a status and name their exports; this checks the
    geometry side actually backs those claims.
    """
    parts_dir = repo / "docs" / "parts"
    if not parts_dir.is_dir():
        rpt.note("no docs/parts/ — CAD checks skipped")
        return

    mp_dir = repo / "cad" / "mass-properties"
    for path in sorted(parts_dir.glob("*.md")):
        text = read(path)
        if text is None:
            continue
        rel = str(path.relative_to(repo))
        meta: dict = {}
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                try:
                    meta = yaml.safe_load(text[3:end]) or {}
                except yaml.YAMLError:
                    meta = {}
        if not isinstance(meta, dict):
            meta = {}

        part_id = meta.get("part_id") or path.stem
        status = str(meta.get("status", "")).lower()

        if part_id != path.stem:
            rpt.add(
                "cad",
                "MINOR",
                f"part_id '{part_id}' does not match the filename '{path.stem}' — "
                "links and mass-properties lookups key off the id",
                rel,
            )

        if status in {"modeled", "released"}:
            export = mp_dir / f"{part_id}.json"
            if not export.exists():
                rpt.add(
                    "cad",
                    "MAJOR",
                    f"status is '{status}' but cad/mass-properties/{part_id}.json is "
                    "absent — the inertia loop was never closed for this part",
                    rel,
                )

        if status == "released":
            exports = list((repo / "cad" / "exports").rglob(f"{part_id}_r*.*")) if (
                repo / "cad" / "exports"
            ).is_dir() else []
            if not exports:
                rpt.add(
                    "cad",
                    "MAJOR",
                    f"status is 'released' but no revved export named {part_id}_r*.* "
                    "exists under cad/exports/ — nothing was actually handed off",
                    rel,
                )

    if mp_dir.is_dir():
        for path in sorted(mp_dir.glob("*.json")):
            if not (parts_dir / f"{path.stem}.md").exists():
                rpt.add(
                    "cad",
                    "MINOR",
                    f"mass properties exported for '{path.stem}' with no part "
                    "definition in docs/parts/ — geometry with no reasoning behind it",
                    str(path.relative_to(repo)),
                )


def check_lfs(repo: Path, rpt: Report) -> None:
    """
    A binary committed outside LFS is a repo that gets slow permanently, since
    fixing it means rewriting history.
    """
    from fnmatch import fnmatch

    attrs = read(repo / ".gitattributes")
    if attrs is None:
        rpt.note("no .gitattributes — LFS check skipped")
        return

    lfs_patterns = [
        line.split()[0]
        for line in attrs.splitlines()
        if "filter=lfs" in line and line.strip() and not line.startswith("#")
    ]

    binary_ext = {
        ".sldprt", ".sldasm", ".slddrw", ".f3d", ".f3z", ".step", ".stp",
        ".iges", ".igs", ".x_t", ".stl", ".obj", ".3mf", ".ply",
        ".usd", ".usdc", ".usdz", ".pdf", ".png", ".jpg", ".jpeg",
    }

    unmatched: dict[str, int] = {}
    for search_root in ("cad", "refs", "docs"):
        root = repo / search_root
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in binary_ext:
                continue
            name = path.name
            if not any(fnmatch(name, pat) for pat in lfs_patterns):
                unmatched[path.suffix.lower()] = unmatched.get(path.suffix.lower(), 0) + 1

    for ext, count in sorted(unmatched.items()):
        rpt.add(
            "lfs",
            "MAJOR",
            f"{count} {ext} file(s) are not matched by any filter=lfs rule in "
            ".gitattributes — committing binaries outside LFS is only fixable by "
            "rewriting history",
            ".gitattributes",
        )


def check_freeze_staleness(repo: Path, rpt: Report) -> None:
    def git(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", "-C", str(repo), *args],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    tags = git("tag", "--list", "freeze/*")
    if tags is None:
        rpt.note("not a git repo (or git unavailable) — freeze staleness skipped")
        return
    if not tags:
        rpt.note("no freeze/* tags — nothing has been frozen yet")
        return

    dirty = git("status", "--porcelain")
    if dirty:
        rpt.add(
            "freeze",
            "QUESTION",
            f"working tree has {len(dirty.splitlines())} uncommitted change(s) — "
            "confirm whether the review should cover HEAD or the uncommitted work",
            "",
        )

    latest = sorted(tags.splitlines())[-1]
    changed = git("diff", "--name-only", f"{latest}..HEAD", "--", "analysis", "docs")
    if changed:
        files = changed.splitlines()
        rpt.add(
            "freeze",
            "MAJOR",
            f"{len(files)} file(s) changed since {latest} without a new freeze tag "
            f"({', '.join(files[:4])}{'…' if len(files) > 4 else ''}) — downstream "
            "work referencing that tag is building on superseded numbers",
            "",
        )


# ── entry point ───────────────────────────────────────────────────────────────

SEVERITY_ORDER = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2, "QUESTION": 3}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".", help="project root")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"not a directory: {repo}", file=sys.stderr)
        return 2

    rpt = Report()
    check_traceability(repo, rpt)
    bom = check_bom(repo, rpt)
    check_param_drift(repo, bom, rpt)
    check_symbols(repo, rpt)
    check_frontmatter(repo, rpt)
    check_cad(repo, rpt)
    check_lfs(repo, rpt)
    check_freeze_staleness(repo, rpt)

    rpt.findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["check"]))

    if args.json:
        print(json.dumps({"repo": str(repo), "findings": rpt.findings, "notes": rpt.notes}, indent=2))
    else:
        print(f"consistency check — {repo}\n")
        for note in rpt.notes:
            print(f"  ·  {note}")
        if rpt.notes:
            print()
        if not rpt.findings:
            print("  clean — no mechanical drift found.")
            print("  (Says nothing about the physics. Read the artifacts.)")
        else:
            for f in rpt.findings:
                loc = f" [{f['where']}]" if f["where"] else ""
                print(f"  {f['severity']:<8} {f['check']}: {f['message']}{loc}\n")
            counts: dict[str, int] = {}
            for f in rpt.findings:
                counts[f["severity"]] = counts.get(f["severity"], 0) + 1
            summary = ", ".join(f"{v} {k.lower()}" for k, v in sorted(counts.items(), key=lambda kv: SEVERITY_ORDER[kv[0]]))
            print(f"  {len(rpt.findings)} finding(s): {summary}")

    return 1 if any(f["severity"] != "QUESTION" for f in rpt.findings) else 0


if __name__ == "__main__":
    sys.exit(main())

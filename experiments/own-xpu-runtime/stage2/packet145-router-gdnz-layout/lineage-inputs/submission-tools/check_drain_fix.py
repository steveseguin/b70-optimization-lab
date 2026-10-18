#!/usr/bin/env python3
"""Read-only check for the negative-sleep cooldown race; never import packets.

Scan every drain_gate.py and text file containing `until - now()` (including
self.now and time.monotonic). Recognize literal nonnegative min/max clamps.
Unknown expressions and unparseable candidates fail closed, not as FIXED.
Requires ripgrep; includes hidden/ignored files, but not .git or __pycache__.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
STAGE2 = REPO / "experiments/own-xpu-runtime/stage2"
REMAINDER = r"\buntil\s*-\s*\(*\s*(?:self\s*\.\s*now|now|time\s*\.\s*monotonic)\s*\("


def call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def is_remainder(node: ast.AST) -> bool:
    return (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub)
            and isinstance(node.left, ast.Name) and node.left.id == "until"
            and isinstance(node.right, ast.Call)
            and ast.unparse(node.right.func) in {"now", "self.now", "time.monotonic"})


def nonnegative(node: ast.AST) -> bool:
    """Prove a lower bound structurally; never execute scanned code."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value >= 0 and (type(node.value) is int or math.isfinite(node.value))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and not node.keywords and len(node.args) >= 2):
        if node.func.id == "max":
            return any(nonnegative(arg) for arg in node.args)
        if node.func.id == "min":
            return all(nonnegative(arg) for arg in node.args)
    return False


def inspect_source(source: str, *, drain_gate: bool = False) -> dict | None:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return {"status": "UNFIXED", "reason": "candidate is not parseable Python",
                "sleeps": []}
    # A local redefinition can turn max into min. Conservatively reject clamps
    # if either builtin is rebound anywhere in the file, including parameters.
    shadowed = any(
        (isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
         and node.id in {"min", "max"})
        or (isinstance(node, ast.arg) and node.arg in {"min", "max"})
        or (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name in {"min", "max"})
        or (isinstance(node, ast.alias) and (node.asname or node.name) in {"min", "max", "*"})
        for node in ast.walk(tree)
    )
    sleeps = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or call_name(node.func) != "sleep":
            continue
        if not any(is_remainder(part) for part in ast.walk(node)):
            continue
        safe = (not shadowed and len(node.args) == 1 and not node.keywords
                and nonnegative(node.args[0]))
        sleeps.append({"line": node.lineno, "status": "FIXED" if safe else "UNFIXED"})
    sleeps.sort(key=lambda row: row["line"])
    if not sleeps:
        if not drain_gate:
            return None  # Comments/string fixtures alone are not executable sleeps.
        return {"status": "UNFIXED", "reason": "no recognized cooldown sleep in drain_gate.py",
                "sleeps": []}
    return {"status": "FIXED" if all(row["status"] == "FIXED" for row in sleeps)
            else "UNFIXED", "sleeps": sleeps}


def rg_paths(args: list[str], root: Path) -> set[Path]:
    result = subprocess.run(
        ["rg", "--threads", "1", "--no-mmap", "--hidden", "--no-ignore", "--glob", "!.git",
         "--glob", "!__pycache__", *args, "--", str(root)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise OSError("ripgrep could not complete the scan (exit %d)" % result.returncode)
    return {Path(raw.decode("utf-8", "surrogateescape"))
            for raw in result.stdout.split(b"\0") if raw}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def scan(root: Path) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("packet must be an existing directory")
    # Filename census also finds empty or malformed copies. Text search catches
    # alternate filenames/extensions. Search just the identifier while streaming
    # large files; the Python filter below handles remainders split over lines.
    paths = rg_paths(["--files", "--null", "--glob", "drain_gate.py"], root)
    paths |= rg_paths(["--files-with-matches", "--null", r"\buntil\b"], root)
    rows = []
    for path in sorted(paths):
        if path.is_symlink():
            rows.append({"path": display_path(path), "status": "UNFIXED",
                         "reason": "symlink candidate requires a local source copy", "sleeps": []})
            continue
        raw = path.read_bytes()
        try:
            source = raw.decode("utf-8-sig")
            if path.name != "drain_gate.py" and not re.search(REMAINDER, source):
                continue
            result = inspect_source(source, drain_gate=path.name == "drain_gate.py")
        except UnicodeDecodeError:
            result = {"status": "UNFIXED", "reason": "candidate is not UTF-8 Python", "sleeps": []}
        if result is not None:
            rows.append({"path": display_path(path), "sha256": hashlib.sha256(raw).hexdigest(), **result})
    counts = {status: sum(row["status"] == status for row in rows)
              for status in ("FIXED", "UNFIXED")}
    return {"schema": "drain-fix-report.v1", "root": display_path(root),
            "scope": "all drain_gate.py and matching text files, including hidden/ignored files; "
                     "excludes .git, __pycache__, binary content and symlink directory traversal",
            "counts": counts, "passed": bool(rows) and not counts["UNFIXED"], "files": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("packet", nargs="?", type=Path)
    group.add_argument("--all", action="store_true", help="scan the entire stage2 tree")
    parser.add_argument("--json", action="store_true", help="write the report to stdout as JSON")
    args = parser.parse_args(argv)
    try:
        report = scan(STAGE2 if args.all else args.packet)
    except (OSError, ValueError) as exc:
        print(f"drain fix check failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for row in report["files"]:
            lines = ",".join(str(item["line"]) for item in row["sleeps"])
            print(f"{row['status']:7s} {row['path']}" + (f":{lines}" if lines else ""))
        print(f"{report['counts']['FIXED']} FIXED, {report['counts']['UNFIXED']} UNFIXED")
    if not report["files"]:
        print("drain fix check failed: no cooldown candidates found", file=sys.stderr)
        return 2
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

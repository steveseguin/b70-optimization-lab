#!/usr/bin/env python3
"""Check (default) or rewrite (--write) the part of notesdelta.py that is copied from the test-harness keeper.

  python3 tools/ctxkeeper/sync_notesdelta.py            exit 1 and a list of names if the copies differ
  python3 tools/ctxkeeper/sync_notesdelta.py --write    copy the harness's versions over notesdelta.py's
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parents[1] / "experiments/qwen38-27b-b70/scripts/context/clm_keeper.py"
TARGET = HERE / "notesdelta.py"
START, END = "# ---- copied from clm_keeper.py (do not edit here) ----\n", "# ---- end of the copy ----\n"


def named(src: str) -> dict[str, str]:
    """Top-level functions and constants of a module as {name: source text, comments above it included}."""
    lines, out = src.splitlines(keepends=True), {}
    for n in ast.parse(src).body:
        name = n.name if isinstance(n, ast.FunctionDef) else (
            n.targets[0].id if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) else None)
        if name:
            start = n.lineno - 1
            while start > 0 and lines[start - 1].lstrip().startswith("#"):
                start -= 1
            out[name] = "".join(lines[start:n.end_lineno]).rstrip() + "\n"
    return out


def copied(target: str) -> tuple[str, str, str]:
    a, b = target.index(START) + len(START), target.index(END)
    return target[:a], target[a:b], target[b:]


def differences() -> list[str]:
    harness, (_, mine, _) = named(HARNESS.read_text()), copied(TARGET.read_text())
    return [name for name, text in named(mine).items() if harness.get(name) != text]


def main() -> None:
    diff = differences()
    if "--write" in sys.argv:
        before, mine, after = copied(TARGET.read_text())
        harness = named(HARNESS.read_text())
        TARGET.write_text(before + "\n\n".join(harness[name] for name in named(mine)) + "\n" + after)
        print(f"rewrote {len(diff)} of {len(named(mine))} copied names: {', '.join(diff) or 'none differed'}")
    elif diff:
        sys.exit("notesdelta.py differs from the harness copy in: " + ", ".join(diff) + "  (run with --write)")
    else:
        print("notesdelta.py matches the harness copy")


if __name__ == "__main__":
    main()

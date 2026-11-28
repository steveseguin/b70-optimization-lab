#!/usr/bin/env python3
"""Lint DO-NOT-REPEAT.md so incomplete/malformed rows cannot become unconditional blockers."""

import pathlib
import sys


def split_row(line: str) -> list[str]:
    """Split a GFM table row into cells, respecting escaped pipes (\\|)."""
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    cells: list[str] = []
    cur: list[str] = []
    i = 0
    while i < len(inner):
        if inner[i] == "\\" and i + 1 < len(inner) and inner[i + 1] == "|":
            cur.append("\\|")
            i += 2
        elif inner[i] == "|":
            cells.append("".join(cur).strip())
            cur = []
            i += 1
        else:
            cur.append(inner[i])
            i += 1
    cells.append("".join(cur).strip())
    return cells


def lint(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    in_table = False
    saw_table = False
    table_ended = False
    data_rows = 0

    for idx, raw in enumerate(lines, 1):
        s = raw.strip()
        is_pipe_row = s.startswith("|")
        if is_pipe_row:
            if table_ended:
                errors.append(
                    f"L{idx}: table row appears after non-table prose; keep the table contiguous"
                )
            if not in_table:
                in_table = True
                saw_table = True
                header = split_row(raw)
                if header != ["Idea", "Result", "Evidence", "Re-open when"]:
                    errors.append(
                        f"L{idx}: unexpected header {header!r}; expected ['Idea', 'Result', 'Evidence', 'Re-open when']"
                    )
                continue
            cells = split_row(raw)
            if all(set(c) <= {"-", ":"} and c for c in cells):
                if len(cells) != 4:
                    errors.append(f"L{idx}: separator row has {len(cells)} columns, expected 4")
                continue
            data_rows += 1
            if len(cells) != 4:
                errors.append(f"L{idx}: row has {len(cells)} columns, expected 4")
                continue
            names = ("Idea", "Result", "Evidence", "Re-open when")
            for col_name, val in zip(names, cells):
                if not val:
                    errors.append(f"L{idx}: empty '{col_name}' cell (cannot be blank)")
        else:
            if in_table:
                in_table = False
                table_ended = True

    if not saw_table or data_rows == 0:
        errors.append("No data rows found in DO-NOT-REPEAT table")
    return errors


def main() -> int:
    default_path = pathlib.Path(__file__).resolve().parent.parent / "DO-NOT-REPEAT.md"
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    errs = lint(target)
    if errs:
        print(f"FAIL: {target} ({len(errs)} error(s)):")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"OK: {target} passed DO-NOT-REPEAT lint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

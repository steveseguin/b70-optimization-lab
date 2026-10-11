#!/usr/bin/env python3
"""Rebuild the probe answers a run wrote, from its saved context snapshots (no model, nothing executed).

Why: on the 1M stream (campaign 5) the agent answered 28 of 29 PROBE items as they arrived and then, at the final
item, rewrote /app/answers.json with the final counters only. The earlier answers were gone from the file, the
runner's snapshot copy was overwritten two minutes later, and the run was stopped. Every write the agent made is
still in agent/context_snapshots/ as the command it issued, with the values as literals.

This reads the commands that write /app/answers.json, in call order, and applies the assignments it can read
without running anything: `d.update({...})`, `d = {...}` and `d["key"] = value` with literal values (numbers,
strings, None/null, simple arithmetic on numbers). A command it cannot read completely is listed, never guessed.
With --final-from FILE the keys of that answers file that are not probe keys are added (the final answers as the
run left them). Output: the merged answers as JSON, for partial_grade.py.

  replay_answers.py TRIAL_DIR OUT.json [--final-from ANSWERS.json]
"""
import argparse
import ast
import json
from pathlib import Path
import re

PROBE_KEY = re.compile(r"p\d+_\d+")
ASSIGN = re.compile(r'^\s*\w+\[\s*["\'](p\d+_\d+)["\']\s*\]\s*=\s*(.+?)\s*$')
DICT = re.compile(r"(?:\.update\(\s*|=\s*)(\{[^{}]*\})", re.S)


def literal(text: str):
    """A literal value or simple arithmetic on numbers; raises ValueError otherwise."""
    text = re.sub(r"\bnull\b", "None", text.strip().rstrip(","))
    node = ast.parse(text, mode="eval").body

    def ev(n):
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult)):
            a, b = ev(n.left), ev(n.right)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return a + b if isinstance(n.op, ast.Add) else a - b if isinstance(n.op, ast.Sub) else a * b
        if isinstance(n, ast.Dict):
            return {ev(k): ev(v) for k, v in zip(n.keys, n.values)}
        raise ValueError(ast.dump(n)[:80])
    return ev(node)


def read_command(cmd: str) -> tuple[dict, list[str]]:
    """Probe-key assignments in one command, and the probe keys it mentions that could not be read."""
    got: dict = {}
    for line in cmd.splitlines():
        m = ASSIGN.match(line)
        if m:
            try:
                got[m.group(1)] = literal(m.group(2))
            except (ValueError, SyntaxError):
                pass
    for m in DICT.finditer(cmd):
        try:
            d = literal(m.group(1))
        except (ValueError, SyntaxError):
            continue
        got.update({k: v for k, v in d.items() if isinstance(k, str) and PROBE_KEY.fullmatch(k)})
    return got, sorted(set(PROBE_KEY.findall(cmd)) - set(got))


def commands(trial: Path):
    """(snapshot name, command) for every distinct tool call that writes the answers file with probe keys, in order."""
    seen = set()
    for f in sorted((trial / "agent/context_snapshots").glob("turn-*.json")):
        try:
            msgs = json.loads(f.read_text())["messages"]
        except Exception:
            continue
        for m in msgs:
            for t in m.get("tool_calls") or []:
                try:
                    cmd = json.loads(t["function"]["arguments"])["command"]
                except Exception:
                    continue
                key = t.get("id") or cmd
                if key in seen or "answers.json" not in cmd or not PROBE_KEY.search(cmd):
                    continue
                if not re.search(r"json\.dump|>\s*/app/answers\.json|write", cmd):
                    continue                      # a read (cat, print) is not a write
                seen.add(key)
                yield f.name, cmd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trial", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--final-from", type=Path)
    a = ap.parse_args()
    answers, unread, n = {}, [], 0
    for name, cmd in commands(a.trial):
        got, missed = read_command(cmd)
        n += 1
        answers.update(got)
        if missed:
            unread.append((name, missed))
    finals = 0
    if a.final_from:
        for k, v in json.loads(a.final_from.read_text()).items():
            if not PROBE_KEY.fullmatch(k):
                answers[k] = v
                finals += 1
    a.out.write_text(json.dumps(answers, indent=1))
    items = sorted({int(k[1:].split("_")[0]) for k in answers if PROBE_KEY.fullmatch(k)})
    print(f"write commands {n}; probe answers rebuilt {sum(1 for k in answers if PROBE_KEY.fullmatch(k))} "
          f"from probe items {items[0] if items else '-'}..{items[-1] if items else '-'} ({len(items)} items); final keys added {finals}")
    for name, missed in unread:
        print(f"UNREAD in {name}: {' '.join(missed)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Grade a snapshot of /app/answers.json from a run that was cut short (or is still running).

A long arm (for example the sliding window at a 200K cap on a 1M stream) can be stopped once the gap is clear; the
verifier then never runs. This applies the task grader's own per-key rules (tests/grade.py, non-kv branch) to a copy
of the answers file taken while the run was alive, for the probes asked so far, and prints accuracy by distance bin
and by probe type in the layout of probe_analysis.py. Final-query keys are graded only with --final (they are not
meaningful before the final item). Nothing here checks the storage rule; a cut run is reported as cut, never as valid.

  partial_grade.py TASK_DIR ANSWERS_JSON [--final] [--json OUT]
"""
import argparse
import json
import re
from pathlib import Path

BINS = ((1, 4), (5, 24), (25, 99), (100, 399), (400, 10 ** 9))
DELETED = {"null", "none", "deleted", "del"}


def as_int(x):
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, str) and re.fullmatch(r"\s*[+-]?\d+\s*", x):
        return int(x)
    return None


def text_norm(x):
    t = " ".join(str(x).lower().replace(".", " ").split())
    for art in ("the ", "a ", "an "):
        if t.startswith(art):
            t = t[len(art):]
    return t


def status_of(k, v, answers, history):
    present, a = k in answers, answers.get(k)
    is_del = a is None or (isinstance(a, str) and a.strip().lower() in DELETED)
    if isinstance(v, str):
        return ("blank" if not present or a is None or str(a).strip() == "" else
                "correct" if text_norm(a) == text_norm(v) else "wrong")
    if v is None:
        return "blank" if not present or (isinstance(a, str) and a.strip() == "") else "correct" if is_del else "wrong"
    if not present or (isinstance(a, str) and a.strip() == ""):
        return "blank"
    if as_int(a) == v:
        return "correct"
    if as_int(a) is not None and as_int(a) in set(history.get(k, [])):
        return "stale"
    return "wrong"


def bin_name(d):
    for lo, hi in BINS:
        if lo <= d <= hi:
            return f"d{lo}-{hi}" if hi < 10 ** 9 else f"d{lo}+"
    return "d?"


def grade(task_dir: Path, answers: dict, final: bool = False) -> dict:
    spec = json.loads((task_dir / "tests/spec.json").read_text())
    ref = json.loads((task_dir / "tests/reference.json").read_text())
    exp, hist, probes = spec["expected"], spec.get("history", {}), ref.get("probes", {})
    answered = [int(m.group(1)) for k in answers if (m := re.fullmatch(r"p(\d+)_\d+", k))]
    last = max(answered, default=0)          # probes up to the last PROBE item with any answer count as asked
    rows = []
    for k, p in sorted(probes.items(), key=lambda kv: [int(x) for x in re.findall(r"\d+", kv[0])]):
        j = int(re.fullmatch(r"p(\d+)_\d+", k).group(1))
        if j > last:
            continue
        rows.append({"key": k, "type": p["type"], "distance": p["distance"], "bin": bin_name(p["distance"]),
                     "item": p["item"], "status": status_of(k, exp[k], answers, hist)})
    out = {"probe_items_answered": last, "probe_items_total": max((int(re.findall(r"\d+", k)[0]) for k in probes), default=0),
           "last_item": max((r["item"] for r in rows), default=0), "n_items": spec.get("n_items"), "probes": rows}
    if final:
        fk = [k for k in exp if k not in probes]
        st = [status_of(k, exp[k], answers, hist) for k in fk]
        out["final"] = {s: st.count(s) for s in ("correct", "blank", "wrong", "stale")} | {"n": len(fk)}
    return out


def acc(rows):
    return f"{sum(r['status'] == 'correct' for r in rows)}/{len(rows)}" if rows else "n/a"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task_dir", type=Path)
    ap.add_argument("answers", type=Path)
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    try:
        answers = json.loads(a.answers.read_text())
        answers = answers if isinstance(answers, dict) else {}
    except Exception:
        answers = {}
    g = grade(a.task_dir, answers, a.final)
    rows = g["probes"]
    bins = [f"d{lo}-{hi}" if hi < 10 ** 9 else f"d{lo}+" for lo, hi in BINS]
    types = sorted({r["type"] for r in rows})
    print(f"probe items answered {g['probe_items_answered']}/{g['probe_items_total']} (through item {g['last_item']} of {g['n_items']})")
    print("\t".join(["probes"] + bins + [f"t:{t}" for t in types] + ["blank", "stale"]))
    print("\t".join([acc(rows)] + [acc([r for r in rows if r["bin"] == b]) for b in bins]
                    + [acc([r for r in rows if r["type"] == t]) for t in types]
                    + [str(sum(r["status"] == s for r in rows)) for s in ("blank", "stale")]))
    if a.final:
        print("final:", g["final"])
    if a.json:
        a.json.write_text(json.dumps(g, indent=1))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Score the note checks of a commit against the true ledger, on notes replies a model really wrote (2026-10-12).

  python3 tools/ctxkeeper/check_score.py COMMIT[,COMMIT...] SESSION_DIR=TASK_DIR [SESSION_DIR=TASK_DIR ...]

COMMIT is a git commit of this repository or the word `tree` (the working tree). A session is a proxy --state-dir
folder (archive.jsonl, notes-history.jsonl, events.jsonl) of a run on a ledger stream; TASK_DIR is that stream's
task (its tests/reference.json holds the true value of every counter after every item).

For every cut of every session the FIRST in-place notes reply is applied to the NOTES the run held before that cut,
with the checks of each commit (strict, "near"; a line is "asked about" when the working check or the count of
mentions would question it). Each counter the reply writes a line for is then one of

  accepted and right      nothing to do
  accepted and WRONG      a wrong value stored without a question: what the checks exist to prevent
  asked about and WRONG   a catch
  asked about and right   a needless question (costs one more reply)

where "right" is the true value after the last item the cut covers. A counter whose value in the NOTES was already
wrong before the cut is left out (a right line cannot repair it and a wrong one cannot be told from it).
Read-only, a few seconds; nothing here needs a model server."""
import collections
import json
import os
import re
import subprocess
import sys
import types

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(LAB, "tools", "ctxkeeper"))
import ctxkeeper as ck                                   # for Keeper.supported (which lines the turns bear out at all)
import notesdelta as tree

ITEM = re.compile(r"(?m)^ITEM (\d+)/\d+ \(UPDATE\)")


def module(commit: str) -> types.ModuleType:
    if commit == "tree":
        return tree
    m = types.ModuleType("notesdelta_" + commit)
    src = subprocess.run(["git", "-C", LAB, "show", commit + ":tools/ctxkeeper/notesdelta.py"], capture_output=True, text=True, check=True).stdout
    exec(compile(src, commit + ":notesdelta.py", "exec"), m.__dict__)
    return m


def state_of(m: types.ModuleType, notes: str) -> dict:
    body = notes.split("STATE\n", 1)[1].split("\nOPEN")[0] if "STATE\n" in notes else ""
    return {k: m.number_of(v) for k, v in (m.fact_of(l) for l in body.splitlines() if l.strip())}


def score(m: types.ModuleType, session: str, task: str, show: int) -> collections.Counter:
    ref = json.load(open(os.path.join(task, "tests", "reference.json")))
    item_of_batch = {int(b): n for b, n in ref["item_no"].items()}
    truth_after = {item_of_batch[b]: rec["state"] for b, rec in enumerate(ref["after_batch"], 1)}
    rows = [json.loads(l) for l in open(os.path.join(session, "archive.jsonl"))]
    versions = [json.loads(l) for l in open(os.path.join(session, "notes-history.jsonl"))]
    groups: list[list[dict]] = []
    for e in (json.loads(l) for l in open(os.path.join(session, "events.jsonl")) if l.strip().startswith("{")):
        if e.get("event") == "in-place notes reply":
            if e.get("attempt") == 1:
                groups.append([])
            groups[-1].append(e)
    item_at, last = {}, 0
    for r in rows:
        hit = ITEM.search(r["text"]) if r["role"] == "tool" else None
        last = int(hit.group(1)) if hit else last
        item_at[r["n"]] = last
    out: collections.Counter = collections.Counter()
    prev, notes, item_before = 0, "", 0
    for v, g in zip(versions, groups):
        noted = [r for r in rows if prev < r["n"] <= v["upto"]]
        texts = [r["text"] for r in noted if r["role"] in ("tool", "user") and ITEM.search(r["text"])]
        first = next((e for e in g if m.parse_delta(e["reply"])), None)
        item_now = item_at.get(v["upto"], 0)
        if first and item_now in truth_after:
            truth, before_truth = truth_after[item_now], truth_after.get(item_before, {})
            held = state_of(m, notes)
            delta = ck.Keeper.supported(m.parse_delta(first["reply"]), texts, True)
            seen = m.numbers_in("\n".join(m.TRAILER.sub("", r["text"]) for r in noted))
            known = m.state_keys(notes) + [k for k, _ in delta["changes"]]
            new, info = m.apply_delta(notes, delta, seen, strict=True, near=m.numbers_near(known, texts))
            now = state_of(m, new)
            asked = {q.split(":")[0] for q in info["mismatch"]}
            # the count question (asked first in the proxy): names the turns mention more often than the lines account for
            steps = info.get("steps") or {}
            short = m.under_accounted(m.mention_counts(known + m.identifiers_in(texts), texts), steps) if hasattr(m, "under_accounted") else []
            asked |= {x.split()[0] for x in short}
            for name in dict.fromkeys(k for k, _ in delta["changes"]):
                if not re.fullmatch(r"[a-z]+\d\d", name):
                    continue
                if held.get(name) != before_truth.get(name):
                    out["left out: the NOTES were already wrong for it"] += 1
                    continue
                right = now.get(name) == truth.get(name)
                key = ("asked about" if name in asked else "accepted") + (" and right" if right else " and WRONG")
                out[key] += 1
                if key in ("accepted and WRONG", "asked about and right") and show > 0:
                    lines = " || ".join(x for n, x in delta["changes"] if n == name)
                    print(f"    {key}: {os.path.basename(session.rstrip('/'))[-8:]} items {item_before + 1}..{item_now} {name}: "
                          f"held {held.get(name)}, stored {now.get(name)}, true {truth.get(name)} | {lines[:200]}")
        prev, notes, item_before = v["upto"], v["notes"], item_at.get(v["upto"], item_before)
    return out


def main() -> None:
    show = 0
    args = [a for a in sys.argv[1:] if a != "--show"]
    if "--show" in sys.argv:
        show = 1
    if len(args) < 2:
        sys.exit(__doc__)
    commits, pairs = args[0].split(","), [a.split("=", 1) for a in args[1:]]
    keys = ["accepted and right", "accepted and WRONG", "asked about and WRONG", "asked about and right", "left out: the NOTES were already wrong for it"]
    for c in commits:
        m, total = module(c), collections.Counter()
        if show:
            print(c)
        for session, task in pairs:
            total += score(m, session, task, show)
        print(f"{c:>12}: " + "   ".join(f"{k} {total[k]}" for k in keys))


if __name__ == "__main__":
    main()

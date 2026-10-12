#!/usr/bin/env python3
"""Audit the NOTES a ctxkeeper proxy session saved against the grader's true ledger (2026-10-12).

The proxy keeps every accepted NOTES version in notes-history.jsonl with the number of the last message it covers,
and every archived message in archive.jsonl. For each version: the last delivered UPDATE item among the messages it
covers is found, and every STATE value is compared with the true value after that item (as notes_audit.py does for
the harness keeper; values are read the same way: the last number counts, `removed` is no value).

  proxy_notes_audit.py SESSION_DIR TASK_DIR
"""
import json
import re
import sys
from pathlib import Path

s, t = Path(sys.argv[1]), Path(sys.argv[2])
ref = json.load(open(t / "tests/reference.json"))
item_of_batch = {int(b): n for b, n in ref["item_no"].items()}
state_after_item = {item_of_batch[b]: rec["state"] for b, rec in enumerate(ref["after_batch"], 1)}
ops_in_item = {item_of_batch[b]: rec["ops"] for b, rec in enumerate(ref["after_batch"], 1)}
last_item_upto, last = {}, 0                      # message number -> newest UPDATE item at or before it
for line in open(s / "archive.jsonl"):
    r = json.loads(line)
    m = re.search(r"(?m)^ITEM (\d+)/\d+ \(UPDATE\)", r["text"]) if r["role"] == "tool" else None
    if m:
        last = int(m.group(1))
    last_item_upto[r["n"]] = last
versions = [json.loads(line) for line in open(s / "notes-history.jsonl")]
first_bad, audited = {}, 0
for v in versions:
    upto = last_item_upto.get(v["upto"])
    if not upto or upto not in state_after_item:
        continue
    audited += 1
    truth, state, sec = state_after_item[upto], {}, ""
    for ln in v["notes"].splitlines():
        x = ln.strip().lstrip("-* ").strip()
        if x.upper().rstrip(":") in ("RULES", "STATE", "OPEN"):
            sec = x.upper().rstrip(":")
            continue
        m = re.match(r"`?([a-z]+\d\d)`?\s*[:=]?\s*(.*)$", x) if sec == "STATE" and x else None
        if m:
            val = re.sub(r"\([^()]*\)", " ", m.group(2)).replace("\u2212", "-").strip()
            val = re.split(r"→|->|=>", val)[-1].strip()
            nums = re.findall(r"(?<![\w.])-?\d[\d,]*(?![\d.]*\d)", val)
            gone = re.match(r"(removed|closed|struck|deleted|gone)\b", val.lower())
            state[m.group(1)] = None if gone or not nums else int(nums[-1].replace(",", ""))
    for k in set(state) | set(truth):
        if state.get(k) != truth.get(k) and k not in first_bad:
            first_bad[k] = (upto, state.get(k, "missing"), truth.get(k))
for k, (upto, got, want) in sorted(first_bad.items(), key=lambda x: x[1][0]):
    hist = [(i, [o for o in ops if o[0] == k]) for i, ops in ops_in_item.items() if any(o[0] == k for o in ops) and i <= upto][-3:]
    print(f"  {k}: NOTES first wrong when covering items up to {upto}: notes {got} truth {want}; last ops: {hist}")
print(f"  counters ever wrong in NOTES: {len(first_bad)}")
print(f"  NOTES versions audited: {audited} of {len(versions)}")

#!/usr/bin/env python3
"""The questions of a finished sparse-memory session that the NOTES alone answer wrongly: for each PROBE question,
the NOTES in view when it was asked (the last version saved before the question's message) run to the end of some
item K. A question about a counter's value at item N (old_value: N; current/procedure: the item asked about) is
"at risk" when the counter's true value at N differs from its true value at K: an earlier point than the NOTES cover
(N < K), or newer changes in the turns (N > K). Prints how many questions are at risk of each kind and how many of
those were answered wrong, with the NOTES' item and the answer.
Usage: notes_cover.py TASK_DIR PROXY_STATE_DIR DETAILS_JSON"""
import json, re, sys
task, state, details = sys.argv[1:4]
ref = json.load(open(f"{task}/tests/reference.json"))
spec = json.load(open(f"{task}/tests/spec.json"))
per = json.load(open(details))["per_key"]
answers = json.load(open(details))["answers"]
item_no, after = ref["item_no"], ref["after_batch"]
truth_at = {}                                   # item -> state after it (batch b, 1-based, is after_batch[b - 1])
for b, it in item_no.items():
    truth_at[int(it)] = after[int(b) - 1]["state"]
items = sorted(truth_at)


def value(name, it):
    k = max((x for x in items if x <= it), default=None)
    return None if k is None else truth_at[k].get(name)


label = re.compile(r"(?m)^ITEM (\d+)/")
rows = [json.loads(l) for l in open(f"{state}/archive.jsonl")]
item_of, at = {}, 0
for r in rows:                                   # as Archive.labelled numbers them
    m = label.search(r["text"]) if r["role"] in ("tool", "user") else None
    if m:
        at = int(m.group(1))
    item_of[r["n"]] = at
versions = [json.loads(l) for l in open(f"{state}/notes-history.jsonl")]
covers = [(v["upto"], item_of.get(v["upto"], 0)) for v in versions]     # (message number, item K)
asked_at = {}                                    # probe key -> message number of the message that asks it
for r in rows:
    if r["role"] == "tool":
        for k in re.findall(r"ASK (p\d+_\d+):", r["text"]):
            asked_at.setdefault(k, r["n"])
kinds = {"earlier point": [0, 0, []], "newer turns": [0, 0, []]}
for key, p in ref["probes"].items():
    q = p["q"]
    names = [n for n in re.findall(r"\b([a-z]+\d+)\b", q) if not re.fullmatch(r"p\d+", n)]
    if not names or key not in asked_at or str(spec["expected"].get(key)) == "protected":
        continue
    name = names[0]
    m = re.search(r"end of item (\d+)|As of item (\d+)", q)
    n_item = int(m.group(1) or m.group(2)) if m else p["item"] - 1
    before = [k for (u, k) in covers if u < asked_at[key]]
    if not before:
        continue
    k_item = before[-1]
    if value(name, n_item) == value(name, k_item):
        continue
    kind = "earlier point" if n_item < k_item else "newer turns"
    wrong = per.get(key) != "correct"
    kinds[kind][0] += 1
    kinds[kind][1] += wrong
    if wrong:
        kinds[kind][2].append(f"{key} ({name}, item {n_item}, NOTES to {k_item}: {answers.get(key)!r} for {spec['expected'].get(key)!r})")
for kind, (n, w, ex) in kinds.items():
    print(f"{kind}: {n} questions at risk, {w} wrong" + ("" if not ex else ": " + "; ".join(ex)))

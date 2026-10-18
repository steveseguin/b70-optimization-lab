#!/usr/bin/env python3
"""Replay every saved in-place notes reply of proxy sessions through respell() of an old commit and of the working
tree, with the mentions and held names the keeper uses; print every reply whose renames differ.
Usage: replay_respell.py OLD_COMMIT STATE_DIR [STATE_DIR ...]"""
import json, re, subprocess, sys, types
LAB = "/home/steve/b70-optimization-lab"
sys.path.insert(0, LAB + "/tools/ctxkeeper")
import notesdelta as new
old = types.ModuleType("old_notesdelta")
exec(subprocess.run(["git", "-C", LAB, "show", sys.argv[1] + ":tools/ctxkeeper/notesdelta.py"], capture_output=True,
                    text=True, check=True).stdout, old.__dict__)
rx = re.compile(r"(?m)^ITEM \d+/\d+ \(UPDATE\)")
for s in sys.argv[2:]:
    rows = [json.loads(l) for l in open(s + "/archive.jsonl")]
    vs = [json.loads(l) for l in open(s + "/notes-history.jsonl")]
    groups = []
    for e in (json.loads(l) for l in open(s + "/events.jsonl") if l.strip().startswith("{")):
        if e.get("event") == "in-place notes reply":
            if str(e.get("attempt")) == "1":
                groups.append([])
            groups[-1].append(e)
    prev, notes, replies, differ, joined = 0, "", 0, 0, {}
    for v, g in zip(vs, groups):
        noted = [r for r in rows if prev < r["n"] <= v["upto"]]
        texts = [r["text"] for r in noted if r["role"] in ("tool", "user") and rx.search(r["text"])]
        held = new.state_keys(notes)
        for e in g:
            delta = new.parse_delta(e["reply"])
            if not delta:
                continue
            replies += 1
            ment = new.mention_counts(held + new.identifiers_in(texts), texts)
            a = old.respell(delta, ment, held)[1]
            b = new.respell(delta, ment, held)[1]
            if a != b:
                differ += 1
                for k, x in b.items():
                    if a.get(k) != x:
                        joined[f"{k} -> {x}"] = joined.get(f"{k} -> {x}", 0) + 1
        prev, notes = v["upto"], v["notes"]
    print(f"{s.rstrip('/').split('/')[-2]}: {replies} replies, {differ} with other renames; {joined}")

#!/usr/bin/env python3
"""Replay the note checks of every saved in-place notes reply with the archive searches' text as the keeper kept it
before 1.2.0.dev7 (whole results) and as dev7 keeps it (`material_of`: tool and user lines only), and print every
line whose verdict differs. The searches are rebuilt from the `recall` events, each against the archive rows that
existed then (up to the last notes version before it); the lookups' entries are added as the keeper adds them.
Usage: replay_recalled.py STATE_DIR [STATE_DIR ...]"""
import json, re, sys
from pathlib import Path
LAB = "/home/steve/b70-optimization-lab"
sys.path.insert(0, LAB + "/tools/ctxkeeper")
import ctxkeeper as ck
nd = ck.nd
LABEL = re.compile(r"(?m)^ITEM (\d+)/")
SCAN = re.compile(r"(?m)^ITEM \d+/\d+ \(UPDATE\)")


class Upto(ck.Archive):
    """The archive as it stood: rows up to `limit`."""
    def __init__(self, rows):
        self.all, self.limit = rows, 0

    def rows(self):
        return [dict(r) for r in self.all if r["n"] <= self.limit]


for d in sys.argv[1:]:
    d = Path(d)
    rows = [json.loads(l) for l in open(d / "archive.jsonl")]
    vs = [json.loads(l) for l in open(d / "notes-history.jsonl")]
    ev = [json.loads(l) for l in open(d / "events.jsonl") if l.strip().startswith("{")]
    arch = Upto(rows)
    old, new = [], []                       # the recalled text: whole results, material only
    g, prev, notes, earlier, looked, texts, seen = -1, 0, "", None, [], [], set()
    replies = differ = 0
    found: dict[str, int] = {}
    for e in ev:
        kind = e.get("event")
        if kind == "recall":
            a = {k: v for k, v in e["args"].items() if k in ("pattern", "before", "after", "last", "message")}
            if e["args"].get("notes_at") is not None or not a:
                continue
            try:
                text = arch.recall(label=LABEL, unit="item", **a)
            except Exception:
                continue
            if text.startswith("recall:"):
                continue
            for lst, t in ((old, text), (new, ck.material_of(text))):
                lst.append(t)
                while sum(map(len, lst)) > ck.RECALLED_CHARS and len(lst) > 1:
                    lst.pop(0)
        elif kind == "in-place notes reply":
            if str(e.get("attempt")) == "1":
                g += 1
                if g >= len(vs):
                    break
                if g > 0:
                    prev, notes = vs[g - 1]["upto"], vs[g - 1]["notes"]
                arch.limit = prev
                noted = [r for r in rows if prev < r["n"] <= vs[g]["upto"]]
                texts = [r["text"] for r in noted if r["role"] in ("tool", "user") and SCAN.search(r["text"])]
                seen = nd.numbers_in("\n".join(nd.TRAILER.sub("", r["text"]) for r in noted))
                earlier, looked = None, []
            delta = nd.parse_delta(e.get("reply", ""))
            if not delta:
                continue
            replies += 1
            delta = earlier = nd.merge_replies(earlier, delta)
            known = nd.state_keys(notes) + [k for k, _ in delta["changes"]]
            verdicts = []
            for rec in (old, new):
                near = nd.numbers_near(known, texts + list(rec) + looked)
                info = nd.apply_delta(notes, delta, seen, strict=True, near=near)[1]
                verdicts.append(set(info["mismatch"]))
            if verdicts[0] != verdicts[1]:
                differ += 1
                for m in sorted(verdicts[1] - verdicts[0]):
                    found["+ " + m[:110]] = found.get("+ " + m[:110], 0) + 1
                for m in sorted(verdicts[0] - verdicts[1]):
                    found["- " + m[:110]] = found.get("- " + m[:110], 0) + 1
        elif kind == "in-place notes asked again" and e.get("why") == "waits on archived entries":
            looked.append(e.get("entries", ""))
    print(f"{d.parent.name}: {replies} replies, {differ} with other verdicts")
    for k, v in found.items():
        print(f"   {v}x {k}")

"""Differential replay: every saved first in-place notes reply of one or more proxy sessions (--state-dir folders
that hold archive.jsonl, notes-history.jsonl and events.jsonl) through the note checks of an old commit and of the
working tree; prints the names whose stored value or question differs.

  python3 tools/ctxkeeper/replay_diff.py OLD_COMMIT STATE_DIR [STATE_DIR ...]

Read-only and light (a second or two for a 1M-token session): the cheapest way to see what a change to
notesdelta.py does to text a model really wrote, before any run. The item pattern below is the ledger streams'."""
import json, re, subprocess, sys, types
import os
LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, LAB + "/tools/ctxkeeper")
import notesdelta as new
import ctxkeeper as ck
old = types.ModuleType("old_notesdelta")
exec(subprocess.run(["git", "-C", LAB, "show", sys.argv[1] + ":tools/ctxkeeper/notesdelta.py"], capture_output=True, text=True, check=True).stdout, old.__dict__)
tot = diff = 0
for s in sys.argv[2:]:
    rows = [json.loads(l) for l in open(s + "/archive.jsonl")]
    vs = [json.loads(l) for l in open(s + "/notes-history.jsonl")]
    groups = []
    for e in (json.loads(l) for l in open(s + "/events.jsonl") if l.strip().startswith("{")):
        if e.get("event") == "in-place notes reply":
            if e.get("attempt") == 1: groups.append([])
            groups[-1].append(e)
    rx = re.compile(r"(?m)^ITEM \d+/\d+ \(UPDATE\)")
    prev, notes = 0, ""
    for gi, (v, g) in enumerate(zip(vs, groups)):
        noted = [r for r in rows if prev < r["n"] <= v["upto"]]
        texts = [r["text"] for r in noted if r["role"] in ("tool", "user") and rx.search(r["text"])]
        first = next((e for e in g if new.parse_delta(e["reply"])), None)
        if first:
            out = {}
            for tag, m in (("old", old), ("new", new)):
                delta = ck.Keeper.supported(m.parse_delta(first["reply"]), texts, True)
                seen = m.numbers_in("\n".join(m.TRAILER.sub("", r["text"]) for r in noted))
                known = m.state_keys(notes) + [k for k, _ in delta["changes"]]
                res, info = m.apply_delta(notes, delta, seen, strict=True, near=m.numbers_near(known, texts))
                state = dict(m.fact_of(l) for l in res.split("STATE\n", 1)[1].split("\nOPEN")[0].splitlines() if l.strip())
                out[tag] = ({k: m.number_of(x) for k, x in state.items()}, sorted(q.split(":")[0] for q in info["mismatch"]), delta)
            tot += len(out["new"][2]["changes"])
            for k in sorted(set(out["old"][0]) | set(out["new"][0])):
                a, b = out["old"][0].get(k), out["new"][0].get(k)
                qa, qb = k in out["old"][1], k in out["new"][1]
                if a != b or qa != qb:
                    diff += 1
                    lines = [x for n, x in out["new"][2]["changes"] if n == k]
                    print(f"{s[-16:]} cut {gi} {k}: old {a}{' (asked)' if qa else ''} -> new {b}{' (asked)' if qb else ''} | " + " || ".join(lines)[:230])
        prev, notes = v["upto"], v["notes"]
print(f"{tot} lines replayed, {diff} names differ")

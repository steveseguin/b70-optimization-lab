#!/usr/bin/env python3
"""Compare every saved NOTES version's STATE lines with the generator's true state as of the last item the notes
cover (campaign 43, 2026-10-18). Usage: notes_truth.py TASK_DIR PROXY_STATE_DIR TRAJECTORY_JSON [counter ...]
With counters named, every version's line for each is printed. Read-only; a second or two for a 2M session."""
import bisect, json, re, sys

task, pdir, traj = sys.argv[1:4]
watch = sys.argv[4:]
ref = json.load(open(task + "/tests/reference.json"))
after = ref["after_batch"]
item_of_batch = {int(b): i for b, i in ref["item_no"].items()}
batch_items = sorted((i, b) for b, i in item_of_batch.items())
t = json.load(open(traj))


def txt(m):
    c = m.get("content") or ""
    return " ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else c


# message n (1-based, system = 1) -> latest item delivered at or before it
item_at = []
cur = 0
for m in t:
    if m["role"] == "tool":
        mm = re.match(r"ITEM (\d+)/", txt(m))
        if mm:
            cur = int(mm.group(1))
    item_at.append(cur)


def truth(item):
    k = bisect.bisect_right([i for i, _ in batch_items], item) - 1
    return after[batch_items[k][1] - 1]["state"] if k >= 0 else {}


line_re = re.compile(r"^-?\s*([a-z]+ ?[a-z]*\d+)\s*[:=]\s*(.+)$")   # a name split by a space counts as its joined name
nh = [json.loads(x) for x in open(pdir + "/notes-history.jsonl")]
tot = bad = 0
per = {}
VERBOSE = False
for v in nh:
    upto = int(v["upto"])
    item = item_at[min(upto, len(item_at)) - 1]
    st = truth(item)
    body = v["notes"].split("STATE", 1)[1] if "STATE" in v["notes"] else ""
    body = body.split("\nOPEN", 1)[0]
    wrong = []
    for ln in body.splitlines():
        mm = line_re.match(ln.strip())
        if not mm:
            continue
        name, val = mm.group(1), mm.group(2)
        v2 = re.sub(r"\([^)]*\)", "", val).replace("\u2212", "-")
        if re.search(r"[=\u2192]", v2):
            v2 = re.split(r"[=\u2192]", v2)[-1]
        num = re.search(r"(?<![\w])(-?\d+)\b", v2)
        removed = "removed" in val.lower() or "struck" in val.lower() or "deleted" in val.lower()
        tv = st.get(name.replace(" ", ""))
        tot += 1
        ok = (removed and tv is None) or (num is not None and not removed and tv == int(num.group(1)))
        if not ok:
            bad += 1
            wrong.append(f"{name}: notes '{val[:50]}' true {tv}")
        if name in watch:
            print(f"  watch item {item:4d} {name}: notes '{val[:60]}' true {tv}")
    for w in wrong:
        per[w.split(":")[0]] = per.get(w.split(":")[0], 0) + 1
    if wrong and VERBOSE:
        print(f"version upto msg {upto} (item {item}): {len(wrong)} wrong: " + "; ".join(wrong[:6]))
print(f"STATE lines checked {tot}, wrong {bad} ({100 * bad / max(tot, 1):.2f} %) over {len(nh)} versions")
print("wrong lines by counter:", sorted(per.items(), key=lambda x: -x[1])[:15])

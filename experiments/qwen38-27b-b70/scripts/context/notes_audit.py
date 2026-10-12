"""Audit a keeper run's NOTES against the grader's reference: for every version of the pinned NOTES, the items it
covers (all items archived so far) and each STATE value that differs from the true value at that point."""
import glob, json, re, sys
od, arm, seed = sys.argv[1:4]
t = glob.glob(f"{od}/runs/jobs/{arm}__sparse-memory-t*k-s{seed}/*/")[0]
task = json.load(open(t + "config.json"))["task"]["path"]
ref = json.load(open(task + "/tests/reference.json")); det = json.load(open(t + "verifier/details.json"))
spec = json.load(open(task + "/tests/spec.json"))
item_of_batch = {int(b): n for b, n in ref["item_no"].items()}
state_after_item = {item_of_batch[b]: rec["state"] for b, rec in enumerate(ref["after_batch"], 1)}
ops_in_item = {item_of_batch[b]: rec["ops"] for b, rec in enumerate(ref["after_batch"], 1)}
wrong = {k: v for k, v in det["per_key"].items() if v != "correct"}
print(arm, "seed", seed, "wrong:", {k: (v, spec["expected"].get(k)) for k, v in wrong.items()})
seen, pins, first_bad = set(), set(), {}
for f in sorted(glob.glob(t + "agent/context_snapshots/turn-*.json")):
    d = json.load(open(f)); msgs = d.get("messages", d) if isinstance(d, dict) else d
    pin = next((str(m.get("content")) for m in msgs if str(m.get("content") or "").startswith("[[NOTES kept")), None)
    if not pin:
        continue
    pins.add(pin)
    if pin in seen:
        continue
    # items still in view in this snapshot: the notes cover everything before the first of them. A version is marked
    # as audited only once a snapshot shows it together with an item (right after an in-place cut the context is the
    # task and the NOTES alone; an earlier version of this tool marked the version seen there and never audited it).
    inview = [int(x) for m in msgs if m.get("role") == "tool" for x in re.findall(r"(?m)^ITEM (\d+)/\d+ \(UPDATE\)", str(m.get("content") or ""))]
    if not inview:
        continue
    seen.add(pin)
    upto = max(i for i in state_after_item if i < min(inview))
    truth = state_after_item[upto]
    state = {}
    sec = ""
    for ln in pin.splitlines():
        s = ln.strip().lstrip("-* ").strip()
        if s.upper().rstrip(":") in ("RULES", "STATE", "OPEN"):
            sec = s.upper().rstrip(":"); continue
        if sec == "STATE" and s:
            m = re.match(r"`?([a-z]+\d\d)`?\s*[:=]?\s*(.*)$", s)
            if m:
                v = re.sub(r"\([^()]*\)", " ", m.group(2)).replace("\u2212", "-").strip()        # as clm_keeper.number_of: the last number counts
                v = re.split(r"\u2192|->|=>", v)[-1].strip()                # "286 -> removed": what it is now comes last
                nums = re.findall(r"(?<![\w.])-?\d[\d,]*(?![\d.]*\d)", v)
                gone = re.match(r"(removed|closed|struck|deleted|gone)\b", v.lower())
                state[m.group(1)] = None if gone or not nums else int(nums[-1].replace(",", ""))
    bad = {k: (state.get(k, "missing"), truth.get(k)) for k in set(state) | set(truth) if state.get(k) != truth.get(k)}
    for k, v in bad.items():
        if k not in first_bad:
            first_bad[k] = (upto, v, f.split("/")[-1])
for k, (upto, v, f) in sorted(first_bad.items(), key=lambda x: x[1][0]):
    hist = [(i, [o for o in ops if o[0] == k]) for i, ops in ops_in_item.items() if any(o[0] == k for o in ops) and i <= upto][-3:]
    print(f"  {k}: NOTES first wrong when covering items up to {upto} ({f}): notes {v[0]} truth {v[1]}; last ops: {hist}")
print("  counters ever wrong in NOTES:", len(first_bad))
print(f"  NOTES versions audited: {len(seen)} of {len(pins)}")

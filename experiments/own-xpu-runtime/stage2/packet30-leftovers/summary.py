#!/usr/bin/env python3
"""Fail-closed CPU summarizer of two fresh packet30 G3 owners."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
from window_safety import environment_gate

HERE = Path(__file__).resolve().parent

def require(ok, why):
    if not ok:
        raise ValueError(why)

def read(path):
    return json.loads(Path(path).read_text())

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n")

def admission(window, natives):
    require(window.get("schema") == "packet30.window.v1" and window.get("window") == "G3" and window.get("completed") is True and window.get("device_executed") is True, "completed G3 window required")
    require(not window.get("stop_reason"), "stopped window")
    owners = window.get("owners", [])
    require(len(owners) == len(natives) == 2, "two owners required")
    require(len({o.get("unit") for o in owners}) == 2 and all(o.get("unit") for o in owners), "distinct fresh owner units required")
    require(all(type(o.get("pid")) is int and o["pid"] > 0 for o in owners) and len({o["pid"] for o in owners}) == 2, "distinct fresh owner pids required")
    native_env = window.get("environment", {}).get("native", {})
    checked = environment_gate(native_env)
    require(checked == window.get("environment"), "closed native environment mismatch")
    loader = window.get("ldd_preflight", {})
    require(loader.get("returncode") == 0 and loader.get("argv", [None])[0] == "ldd" and "not found" not in (loader.get("stdout", "")+loader.get("stderr", "")), "ldd preflight failed")
    limits = window.get("deadlines", {})
    estimate, seconds = limits.get("expected_total_seconds"), limits.get("watchdog_seconds")
    require(type(estimate) in (int, float) and math.isfinite(estimate) and estimate > 0 and type(seconds) is int and seconds >= max(300, math.ceil(4*estimate)), "watchdog below fourfold margin")
    budgets = limits.get("submission_budget_seconds", {})
    require(bool(budgets) and all(type(v) in (int,float) and math.isfinite(v) and v >= 300 for v in budgets.values()), "submission budget below300s")
    for owner, native in zip(owners, natives):
        require(owner.get("completed") is True and owner.get("returncode") in (0,2) and owner.get("child_still_running") is False, "owner incomplete")
        require(native.get("mode") == "G3" and native.get("device_executed") is True and native.get("completed") is True and native.get("safe_to_exit") is True and native.get("live_bytes") == 0 and native.get("in_flight") == 0, "native ownership/receipt failure")
        failures = native.get("finite_element_gate_failures")
        require(type(failures) is int and failures >= 0 and native.get("passed") is (failures == 0) and owner["returncode"] == (2 if failures else 0), "native failure accounting mismatch")
        teardown = native.get("teardown", {})
        require(teardown.get("safe_to_exit") is True and teardown.get("live_bytes") == 0 and teardown.get("in_flight") == 0, "teardown accounting missing")

def percentile90(values):
    # Conventional linear percentile on the complete 200 group-duration sample.
    v = sorted(values); x = (len(v)-1)*.9; lo = int(x); hi = min(lo+1,len(v)-1)
    return v[lo]+(v[hi]-v[lo])*(x-lo)

def timing_stats(rows, registry, candidate):
    require(bool(rows), "timing missing")
    groups = defaultdict(list)
    counts, payloads, copies_set = set(), set(), set()
    for r in rows:
        rep = r.get("repetition")
        require(type(rep) is int and 0 <= rep < registry["repetitions"], "invalid repetition")
        require(r.get("exact") is True, "timing exact flag false")
        count, index = r.get("event_count"), r.get("event_index")
        require(type(count) is int and 0 < count <= 64 and type(index) is int and 0 <= index < count, "event count/index invalid")
        start, end = r.get("start_ns"), r.get("end_ns")
        require(type(start) is int and type(end) is int and 0 < start < end and end-start <= 300*10**9, "invalid device event duration")
        payload, copies = r.get("payload_bytes"), r.get("copies")
        require(type(payload) is int and payload > 0, "payload missing")
        expected_copies = 8 if payload > registry["rotation_threshold_bytes"] else 1
        require(copies == expected_copies and r.get("copy_index") == rep % copies, "full-size eight-copy rotation missing")
        counts.add(count);payloads.add(payload);copies_set.add(copies);groups[rep].append(r)
    require(set(groups) == set(range(registry["repetitions"])), "missing or extra repetitions")
    require(len(counts) == len(payloads) == len(copies_set) == 1, "event/payload/rotation identity changed")
    count = next(iter(counts))
    if candidate != "incumbent":
        expected = 1
        if candidate.startswith("p30.route.two."):expected = 2
        if candidate == "p30.attention.sg32":expected = 3
        if candidate == "p30.attention.score_softmax":expected = 2
        require(count == expected, "candidate launch count differs from implementation")
    durations = []
    for rep in range(registry["repetitions"]):
        events = groups[rep]
        require(len(events) == count and {r["event_index"] for r in events} == set(range(count)), "duplicate or missing events")
        durations.append(sum(r["end_ns"]-r["start_ns"] for r in events)/1000.)
    return dict(median_us=statistics.median(durations), p90_us=percentile90(durations), repetitions=len(durations), launches_per_group=count, payload_bytes=next(iter(payloads)), copies=next(iter(copies_set)), timing_definition="sum of GPU execution duration of each event in one launch group")

def exact_gate(rows, cls, candidate):
    chosen = [r for r in rows if r.get("class") == cls["klass"] and r.get("candidate") == candidate]
    require(len(chosen) == len(cls["required_modes"]) and {r.get("mode") for r in chosen} == set(cls["required_modes"]), "missing/duplicate exactness mode")
    for r in chosen:
        require(r.get("workload") == cls["klass"] and r.get("passed") is True and r.get("new_current_bytes_equal") is True and isinstance(r.get("output_hashes"),str) and bool(r["output_hashes"]), "exactness failed")
    return {r["mode"]:r["output_hashes"] for r in chosen}

def canonical(cls, candidate):
    return candidate if candidate.startswith("p30.") else "p30."+cls["family"]+"."+candidate

def summarize(window, packets, registry, overlap_selection=None):
    """Pure API for hostile protocol tests; packets contain native/exactness/timing."""
    admission(window, [p["native"] for p in packets])
    classes = {c["klass"]:c for c in registry["classes"]}
    for p in packets:
        for kind in ("exactness", "timing"):
            for r in p[kind]:
                require(r.get("class") in classes, "unregistered class")
                c = classes[r["class"]]
                require(r.get("candidate") in ["incumbent"]+c["candidates"] and r.get("workload") == r["class"], "unregistered candidate/workload")
    rows = []
    for cls in registry["classes"]:
        label = cls["klass"]
        for candidate in cls["candidates"]:
            row = dict(klass=label,candidate=canonical(cls,candidate),raw_candidate=candidate,qualified=False,owners=[],reasons=[],groups_per_token=cls["groups_per_token"],anchor=cls["anchor"],resources=cls["resources"],dispatch=cls["dispatch"])
            previous_hash = None
            for index,p in enumerate(packets):
                try:
                    bh = exact_gate(p["exactness"],cls,"incumbent")
                    ch = exact_gate(p["exactness"],cls,candidate)
                    require(bh == ch, "candidate/incumbent hashes differ")
                    require(previous_hash is None or ch == previous_hash, "fresh owners differ")
                    previous_hash = ch
                    br = [r for r in p["timing"] if r["class"] == label and r["candidate"] == "incumbent"]
                    cr = [r for r in p["timing"] if r["class"] == label and r["candidate"] == candidate]
                    baseline = timing_stats(br,registry,"incumbent")
                    expected_launches = cls["anchor"].get("launches_per_group")
                    require(type(expected_launches) in (int, float) and math.isfinite(expected_launches) and expected_launches > 0 and expected_launches == int(expected_launches) and baseline["launches_per_group"] == expected_launches, "incumbent launch count differs from registered runtime identity")
                    measured = timing_stats(cr,registry,candidate)
                    require((baseline["payload_bytes"],baseline["copies"]) == (measured["payload_bytes"],measured["copies"]), "candidate/baseline payload mismatch")
                    anchor = cls["anchor"].get("expected_group_us")
                    representative = anchor is not None and abs(baseline["median_us"]/anchor-1) <= registry["baseline_relative_tolerance"]
                    saving = baseline["median_us"]-measured["median_us"]
                    row["owners"].append(dict(owner=index+1,incumbent=baseline,candidate=measured,baseline_representative=representative,relative_saving=saving/baseline["median_us"],us_per_group_saved=saving))
                    require(representative, "baseline not representative: "+cls["anchor"]["status"])
                    require(saving/baseline["median_us"] >= registry["minimum_relative_saving"], "less than10% saving")
                except ValueError as e:
                    row["reasons"].append("owner%d: %s"%(index+1,e))
            row["qualified"] = not row["reasons"] and len(row["owners"]) == 2
            row["ms_per_token_saved"] = min((o["us_per_group_saved"] for o in row["owners"]), default=0)*cls["groups_per_token"]/1000 if row["qualified"] else 0
            rows.append(row)
    rows.sort(key=lambda r:(-r["ms_per_token_saved"],r["klass"],r["candidate"]))
    # Generic dispatch keys cover multiple concrete workload classes. Every
    # member must pass with the same candidate before that key can be proposed.
    required = defaultdict(set)
    for c in classes.values():required[(c["dispatch"]["section"],c["dispatch"]["key"])].add(c["klass"])
    buckets = defaultdict(list)
    for r in rows:
        if r["qualified"]:buckets[(r["dispatch"]["section"],r["dispatch"]["key"],r["candidate"])].append(r)
    alternatives = defaultdict(list)
    for (section,key,candidate),rs in buckets.items():
        if {r["klass"] for r in rs} != required[(section,key)]:continue
        alternatives[(section,key)].append(dict(id=section+":"+key,section=section,key=key,candidate=candidate,classes=sorted(r["klass"] for r in rs),resources=sorted(set(x for r in rs for x in r["resources"])),ms_per_token_saved=sum(r["ms_per_token_saved"] for r in rs)))
    proposals = [max(v,key=lambda x:(x["ms_per_token_saved"],x["candidate"])) for v in alternatives.values()]
    proposals.sort(key=lambda x:(-x["ms_per_token_saved"],x["id"]))
    conflicts = {p["id"]:sorted(q["id"] for q in proposals if p is not q and set(p["resources"])&set(q["resources"])) for p in proposals}
    selected_ids = set(overlap_selection or [])
    require(selected_ids <= {p["id"] for p in proposals}, "selection names unqualified proposal")
    for name in selected_ids:require(not selected_ids.intersection(conflicts[name]), "explicit overlap selection still conflicts")
    dispatch = dict(schema="packet26.dispatch.v1",classes={},fusions={},gemv={})
    selected = []
    for p in proposals:
        p["conflicts"] = conflicts[p["id"]]
        p["selected"] = not p["conflicts"] or p["id"] in selected_ids
        if p["selected"]:dispatch[p["section"]][p["key"]]=p["candidate"];selected.append(p)
    return dict(schema="packet30.summary.v1",device_executed=True,performance_claim="fixture event timing only; no measured model throughput",fresh_owners=2,rows=rows,proposals=proposals,overlap_selection=sorted(selected_ids),selected_ms_per_token_saved=sum(p["ms_per_token_saved"] for p in selected),dispatch=dispatch)

def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def write_summary(directory, *, overlap_selection=None):
    path = Path(directory);w = read(path/"window.json");registry = read(HERE/"class-registry.json")
    require(digest(HERE.parents[3]/registry["source"]) == registry["source_sha256"], "class anchor changed")
    bindings=w.get("bindings",{})
    require(bool(bindings), "sealed window bindings missing")
    for filename,expected in bindings.items():require(digest(filename)==expected, "sealed input changed: "+filename)
    packets=[]
    for i,owner in enumerate(w.get("owners",[]),1):
        native=path/"run"/("owner"+str(i))
        for filename,field in (("receipt.json","native_receipt_sha256"),("exactness.jsonl","exactness_sha256"),("timing.jsonl","timing_sha256")):
            require(digest(native/filename) == owner.get(field), "owner evidence changed: "+filename)
        packets.append(dict(native=read(native/"receipt.json"),exactness=jsonl(native/"exactness.jsonl"),timing=jsonl(native/"timing.jsonl")))
    from window import k0_gate
    k0_gate(Path(w["k0"]) if w.get("k0") else None,w)
    result=summarize(w,packets,registry,overlap_selection)
    save(path/"timing-summary.json",result);save(path/"dispatch-measured.json",result["dispatch"])
    lines=["| Class | Candidate | Incumbent us/group (owners1/2) | Candidate median / p90 us (owners1/2) | Launches/group | Conservative ms/token saved | Gate |","|---|---|---:|---|---|---:|---|"]
    for r in result["rows"]:
        baseline=" / ".join("%.3f"%o["incumbent"]["median_us"] for o in r["owners"])
        speed="; ".join("%.3f / %.3f"%(o["candidate"]["median_us"],o["candidate"]["p90_us"]) for o in r["owners"])
        launches=" / ".join("%d→%d"%(o["incumbent"]["launches_per_group"],o["candidate"]["launches_per_group"]) for o in r["owners"])
        lines.append("| %s | %s | %s | %s | %s | %.4f | %s |"%(r["klass"],r["candidate"],baseline,speed,launches,r["ms_per_token_saved"],"qualified fixture" if r["qualified"] else "; ".join(r["reasons"])))
    lines += ["","Times sum GPU event execution durations inside each launch group, excluding gaps. Every owner contributes exactly200 complete repetitions. Savings use groups/token, never individual launch counts. Rows with missing post-p28 or cross-layer anchors are diagnostic only. Overlapping proposals require explicit selection; savings are never counted twice. No model throughput is measured by this program.",""]
    (path/"timing-table.md").write_text("\n".join(lines));return result

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("directory",type=Path);parser.add_argument("--select",action="append",default=[]);args=parser.parse_args();write_summary(args.directory,overlap_selection=args.select)

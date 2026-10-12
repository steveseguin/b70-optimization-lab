"""Strict CPU aggregation: failed cases remain visible and cannot enter dispatch."""
import collections
import json
import math
from pathlib import Path
import statistics
from window import persist
P=Path(__file__).resolve().parent
COUNTS_PATH=P.parent/"packet29-merged/receipts-cards01-20261012-chain/w2c-r29/class-times.json"

def stats(values):
    if len(values)!=200 or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in values):
        raise ValueError("exactly 200 finite positive timing samples required")
    x=sorted(values)
    return dict(median_us=statistics.median(x),p90_us=x[math.ceil(.9*len(x))-1])

def event_rows(root):
    """Read the runtime fixture vocabulary, summing every event in a launch group."""
    groups=collections.defaultdict(list)
    failed=[]
    failpath=root/"candidate-failures.jsonl"
    if failpath.exists():
        failed=[json.loads(x) for x in failpath.read_text().splitlines()]
    blocked={(r["class"],r.get("implementation",r.get("candidate","")),r.get("workload","")) for r in failed}
    for line in (root/"events.jsonl").read_text().splitlines():
        r=json.loads(line)
        if r.get("full_payload_bytes",0)>8_000_000 and r.get("timing_mode")!="rotated":
            continue
        groups[(r["class"],r["candidate"],r.get("workload",""),r["variant"],r["repetition"])].append(r)
    cases=sorted({k[:3] for k in groups})
    result=[]
    for klass,candidate,workload in cases:
        row=dict(klass=klass.removeprefix("gemv:"),candidate=candidate,workload=workload,passed=False)
        try:
            if any(c==klass and w==workload and (impl==candidate or impl in ("packet18","r5","p28.paired.wg32","p28.dense.wg32","p33.down.select")) for c,impl,w in blocked):
                raise ValueError("native exactness/validation case failed")
            arms={}
            for arm in ("packet18","specialised"):
                values=[];walls=[];copies=set()
                for rep in range(200):
                    events=groups[(klass,candidate,workload,arm,rep)]
                    expected_stages=(5 if arm=="packet18" else 4) if klass in ("route","route_gather") else (2 if arm=="packet18" else 1) if klass=="gemv:attention" else 1
                    if len(events)!=expected_stages or len({e["event"] for e in events})!=len(events):
                        raise ValueError("missing/duplicate event")
                    if any(e.get("stage_count",len(events))!=len(events) or e.get("exact") is not True or e.get("bytes_equal",True) is not True or e["end_ns"]<=e["start_ns"] for e in events):
                        raise ValueError("stage/exactness/timing failure")
                    if any(e.get("full_payload_bytes",0)>8_000_000 and e.get("rotation_copies",0)<8 for e in events):
                        raise ValueError("heavy case needs eight full payload banks")
                    copies.update(e.get("buffer_copy",0) for e in events)
                    values.append(sum(e["end_ns"]-e["start_ns"] for e in events)/1000)
                    if "host_wall_us" in events[0]:walls.append(events[0]["host_wall_us"])
                    elif (root/"walls.jsonl").exists():
                        for line in (root/"walls.jsonl").read_text().splitlines():
                            w=json.loads(line)
                            if w["class"]==klass and w["candidate"]==candidate and w["version"]==(arm=="specialised") and w["repetition"]==rep:
                                walls.append(w["host_wall_ns"]/1000)
                if any(e.get("full_payload_bytes",0)>8_000_000 for e in events) and copies!=set(range(8)):
                    raise ValueError("heavy case did not rotate all eight banks")
                arms[arm]=dict(gpu=stats(values),gpu_us=values,host=stats(walls),host_us=walls)
            row.update(passed=True,incumbent=arms["packet18"],alternative=arms["specialised"])
        except (ValueError,KeyError) as exc:
            row["error"]=str(exc)
        result.append(row)
    for r in failed:
        if not any(x["klass"]==r["class"].removeprefix("gemv:") and x["workload"]==r.get("workload","") and x["candidate"]==r.get("implementation") for x in result):
            result.append(dict(klass=r["class"].removeprefix("gemv:"),candidate=r.get("implementation",r.get("candidate","unknown")),workload=r.get("workload",""),passed=False,error=r["error"]))
    if not result:raise ValueError("no native cases")
    return result

def geometry_rows(raw):
    result=[]
    for r in raw:
        aliases=r.get("klass",r.get("runtime_class",""))
        keys=aliases.split(",") if aliases else [r["class"]]
        for key in keys:
            row=dict(r,klass=key,workload=r.get("workload",r["class"]))
            row["diagnostic_only"]=not r.get("timing_eligible",False)
            row["selected"]=False
            if not row["diagnostic_only"] and row.get("passed"):
                try:
                    row["incumbent"]={"gpu_us":r["control_gpu_us"],"host_us":r["control_wall_us"],"gpu":stats(r["control_gpu_us"]),"host":stats(r["control_wall_us"])}
                    row["alternative"]={"gpu_us":r["candidate_gpu_us"],"host_us":r["candidate_wall_us"],"gpu":stats(r["candidate_gpu_us"]),"host":stats(r["candidate_wall_us"])}
                except (ValueError,KeyError) as exc:
                    row.update(passed=False,error=str(exc))
            result.append(row)
    return result

def summarize(window,out):
    out=Path(out)
    native=[];rows=[];floor_cases_passed=True
    for component in sorted(out.iterdir()):
        if not component.is_dir():continue
        receipt=component/"receipt.json"
        if not receipt.exists():continue
        r=json.loads(receipt.read_text());native.append(component.name)
        if r.get("infrastructure_passed",r.get("passed")) is not True:
            raise ValueError("failed native receipt: "+str(component))
        if window=="K0":continue
        if window=="T1":
            from launch_summary import summarize as launch_summary
            floor, markdown = launch_summary(component)
            floor_cases_passed=all(r.get("passed") is True for r in floor["rows"])
            persist(out/"launch-summary.json",floor)
            (out/"launch-table.md").write_text(markdown)
            continue
        if (component/"events.jsonl").exists():rows.extend(event_rows(component))
        elif "rows" in r:rows.extend(geometry_rows(r["rows"]))
        elif (component/"summary.json").exists():rows.extend(geometry_rows(json.loads((component/"summary.json").read_text())["rows"]))
        else:raise ValueError("native component has no timing cases: "+component.name)
    if not native:raise ValueError("no component receipts")
    counts=json.loads(COUNTS_PATH.read_text());groups={r["class"]:r["groups"]/counts["tokens"] for r in counts["classes"]}
    dispatch=dict(schema="packet26.dispatch.v1",classes={},gemv={},fusions={})
    for row in rows:
        if row.get("passed") is not True:continue
        if row.get("diagnostic_only") or row["klass"] not in groups:
            row["diagnostic_only"]=True
            row["selected"]=False
            continue
        # A prepared candidate has to carry native evidence, never an estimate.
        base=stats(row["incumbent"]["gpu_us"]);new=stats(row["alternative"]["gpu_us"])
        row["groups_per_token"]=(47 if row.get("workload")=="expsgate.iq2" else 1 if row.get("workload")=="expsgate.iq3" else groups[row["klass"]])
        row["ms_per_token_saved"]=(base["median_us"]-new["median_us"])*row["groups_per_token"]/1000
        row["selected"]=new["median_us"]<.9*base["median_us"]
    rows.sort(key=lambda r:r.get("ms_per_token_saved",-float("inf")),reverse=True)
    # A class replacement must cover every measured format/site and pass each.
    bad_candidates={r["candidate"] for r in rows if r.get("passed") is not True}
    families=collections.defaultdict(list)
    for r in rows:families[(r["klass"],r["candidate"])].append(r)
    for (klass,candidate),rs in families.items():
        required={"expsgate":{"expsgate.iq2","expsgate.iq3"},"expsdown":{"expsdown"},"attention":{"attention.gdn"}}
        timed=[r for r in rs if not r.get("diagnostic_only",False)]
        coverage_ok=klass not in required or {r.get("workload","") for r in timed}==required[klass]
        if timed and coverage_ok and candidate not in bad_candidates and all(r.get("passed") for r in rs) and all(r.get("selected") for r in timed):
            section="gemv" if klass in {"expsgate","expsdown","attention"} else "classes"
            if klass not in dispatch[section]:dispatch[section][klass]=candidate
    summary=dict(schema="packet42.summary.v1",window=window,components=native,
                 cases_passed=floor_cases_passed and all(r.get("passed") for r in rows),rows=rows,
                 scope="one-card kernel screening; not model speed")
    persist(out/"summary.json",summary)
    if window=="K2":
        persist(out/"dispatch-measured.json",dispatch)
        lines=["| Class | Candidate | Gate | ms/token saved |","|---|---|---|---:|"]
        for r in rows:lines.append("| {} | {} | {} | {} |".format(r['klass'],r['candidate'],r['passed'],r.get('ms_per_token_saved','not timed')))
        (out/"table.md").write_text("\n".join(lines)+"\n")
    return summary

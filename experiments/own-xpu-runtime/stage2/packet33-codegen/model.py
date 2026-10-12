#!/usr/bin/env python3
"""CPU-only receipt extraction and deliberately small generated-code model.
Run with python -B. No device APIs, compiler calls, or external imports.
"""
import argparse, hashlib, json, math, re, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
BASE = ROOT / "experiments/own-xpu-runtime/stage2"
WANTED = {"gemv:expsgate", "gemv:expsdown", "gemv:gdn.qkv", "gemv:qsa.k", "gemv:attention", "route", "qsa.attention", "gdn.recurrence", "fusion:small.hc", "activation"}

def extract():
    sources = {}
    def source(rel):
        p = BASE / rel
        key = str(p.relative_to(ROOT))
        sources[key] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
        return key, p.read_text()
    rows = []
    key, raw = source("packet28-dense/registry.hpp")
    shapes = {}
    for m in re.finditer(r'\{"([^\"]+)","([^\"]+)",Type::(\w+),(\d+),(\d+),(\d+),(true|false),', raw):
        label, klass, quant, n, k, count, paired = m.groups()
        shapes[label] = dict(quantization=quant, rows=int(n), k=int(k), experts=int(count), paired=paired=="true", weights=int(n)*int(k)*int(count)*(2 if paired=="true" else 1), source=key)
    key, raw = source("packet29-merged/build/k2-r29/run/summary.json")
    d = json.loads(raw)
    for klass, c in d["classes"].items():
        if klass not in WANTED: continue
        for candidate, comp in c["comparisons"].items():
            mode = comp["selection_timing_mode"]
            workloads = comp.get("workloads") or {"<single>": comp}
            for workload, vals in workloads.items():
                for arm, vals2 in vals["variants"].items():
                    v = vals2["execution_sum"]
                    ptr = f'/classes/{klass}/comparisons/{candidate}' + (f'/workloads/{workload}' if workload!="<single>" else "") + f'/variants/{arm}/execution_sum'
                    ids = comp["incumbent_kernel_identities" if arm=="packet18" else "candidate_kernel_identities"]
                    implementation = c["incumbent"] if arm=="packet18" else candidate
                    row = dict(id=f'p29:{klass}:{candidate}:{workload}:{arm}:{mode}', family=klass, workload=workload, implementation=implementation, comparator=candidate, arm=arm, timing_mode=mode, median_us=v["median_ns"]/1000, p90_us=v["p90_ns"]/1000, repetitions=v["count"], source=key, pointer=ptr, kernel_identities=ids, bytes_equal=comp["bytes_equal"], primary_fit=True, shape=shapes.get(workload), stage_events_per_repetition=vals2["event"]["count"]/v["count"])
                    rows.append(row)
    key, raw = source("packet29-merged/build/k2-r29/stdout.txt")
    pattern = re.compile(r'^GEMV (\S+) candidate=(\S+) timing_mode=(\S+) same_kernel=(\S+) bytes_equal=(\S+) runtime.R5 median_us=(\S+) p90_us=(\S+) candidate median_us=(\S+) p90_us=(\S+)')
    for line_no, line in enumerate(raw.splitlines(),1):
        m=pattern.match(line)
        if not m: continue
        workload,candidate,mode,same,equal,ref,rp90,med,p90=m.groups()
        shape=shapes.get(workload)
        if not any(workload.startswith(x) for x in ("expsgate", "expsdown", "gdn.qkv", "qsa.k", "attention.")): continue
        if mode!="reread": continue # Exact rotated rows already come from summary JSON.
        for implementation,median,p9 in (("r5",ref,rp90),(candidate,med,p90)):
            rows.append(dict(id=f'p29-stdout:{line_no}:{implementation}', family="gemv:"+workload, workload=workload, implementation=implementation, comparator=candidate, timing_mode=mode, median_us=float(median), p90_us=float(p9), repetitions=200, source=key,line=line_no,bytes_equal=equal=="true", primary_fit=False, shape=shape, note="Printed precision; repeated-buffer diagnostic only."))
    key, raw = source("packet28-dense/receipts-card2-20261011-g2/summary.json")
    for index,row in enumerate(json.loads(raw)["rows"]):
        if "gemv:"+row["class_name"] not in WANTED: continue
        for implementation,median,p90,pointer in [("r5",row["r5_median_us"],None,f'/rows/{index}/r5_median_us')] + [(r["candidate"],r["median_us"],r["p90_us"],f'/rows/{index}/candidates/{i}') for i,r in enumerate(row["candidates"])]:
            rows.append(dict(id=f'p28:{index}:{implementation}',family="gemv:"+row["class_name"],implementation=implementation,median_us=median,p90_us=p90,source=key,pointer=pointer,primary_fit=False,timing_mode="reread",note="Aggregate over two owner runs and relevant workload encodings; not an independent per-kernel observation."))
    key, raw = source("packet27-round2/receipts-cards01-20261012-chain/k2-table.txt")
    for line_no,line in enumerate(raw.splitlines(),1):
        klass=line.split()[0]
        if klass not in WANTED:continue
        for alias,number in re.findall(r'(packet18|specialised) ([0-9.]+)',line.split('|')[1]):
            rows.append(dict(id=f'p27-table:{line_no}:{alias}',family=klass,implementation=alias,median_us=float(number),source=key,line=line_no,primary_fit=False,timing_mode="reported_table",note="One-decimal table. Alias is not dispatch identity; do not pool with p29."))
    key, raw = source("bounds-20261011-gemv/README.md")
    bounds = [("int8-scale-once",[99.2,43.8,48.1,21.9]),("int8-scale-per-weight",[479.8,124.7,209.0,96.5]),("nibble-table-scale-once",[190.5,71.2,79.2,38.3]),("nibble-table-scale-per-weight",[245.9,86.8,99.9,48.3]),("float32",[251.5,113.6,190.0,115.4])]
    for implementation,numbers in bounds:
        for workload,median in zip(("expsgate","expsdown","gdn.qkv","gdn.z"),numbers):
            rows.append(dict(id=f'bounds:{implementation}:{workload}',family="synthetic:"+workload,implementation=implementation,median_us=median,source=key,section="first measured table",primary_fit=False,timing_mode="reread",repetitions=15,note="Different synthetic encoding/program, warm-cache diagnostic; excluded from fit and runtime predictions."))
    out = dict(schema="packet33.measurements.v1",device_ran_in_packet33=False,source_receipts_only=True,metric="median sum of event execution durations per workload; microseconds",primary_fit_policy="p29 exact summary workloads, rotated for large GEMVs; retain matched controls but collapse duplicates before regression",sources=sources,shapes=shapes,rows=rows)
    (HERE/"measurements.json").write_text(json.dumps(out,indent=2)+"\n")
    return out

def solve(a, b):
    """Pivoted Gaussian elimination; ridge makes the small system nonsingular."""
    m = [list(row)+[value] for row,value in zip(a,b)]
    for j in range(len(b)):
        pivot=max(range(j,len(b)),key=lambda i:abs(m[i][j]));m[j],m[pivot]=m[pivot],m[j]
        if abs(m[j][j])<1e-12: raise ValueError("singular design")
        scale=m[j][j];m[j]=[x/scale for x in m[j]]
        for i in range(len(b)):
            if i==j:continue
            scale=m[i][j];m[i]=[x-scale*y for x,y in zip(m[i],m[j])]
    return [row[-1] for row in m]

def ridge_fit(x,y,penalty=1.0):
    p=len(x[0]);n=len(x)
    means=[statistics.mean(row[j] for row in x) for j in range(p)]
    scales=[max(1e-9,statistics.pstdev(row[j] for row in x)) for j in range(p)]
    z=[[1.0]+[(row[j]-means[j])/scales[j] for j in range(p)] for row in x]
    gram=[[sum(row[i]*row[j] for row in z)+(penalty if i==j and i else 0) for j in range(p+1)] for i in range(p+1)]
    coef=solve(gram,[sum(row[i]*v for row,v in zip(z,y)) for i in range(p+1)])
    def predict(row):return coef[0]+sum(coef[j+1]*(row[j]-means[j])/scales[j] for j in range(p))
    return predict,dict(intercept=coef[0],standardized_coefficients=coef[1:],feature_means=means,feature_scales=scales,ridge_penalty=penalty)

def metrics(y,pred):
    error=[p-t for t,p in zip(y,pred)];sse=sum(e*e for e in error);total=sum((t-statistics.mean(y))**2 for t in y)
    return dict(n=len(y),mae_us=statistics.mean(abs(e) for e in error),rmse_us=math.sqrt(sse/len(y)),r2=1-sse/total if total else None,mape_percent=100*statistics.mean(abs(e)/t for t,e in zip(y,error)),max_absolute_error_us=max(abs(e) for e in error))

def fit_flat_feature_rows(data, feature_names):
    """Rows must carry id, implementation, median_us and a features mapping.

    All points sharing an implementation leave training together. No random
    duplicate-control holdout, outcome-derived feature or candidate ID feature.
    """
    x=[[float(r["features"][k]) for k in feature_names] for r in data]
    y=[r["median_us"] for r in data]
    predict,fit=ridge_fit(x,y)
    train=[predict(row) for row in x];held=[]
    for i,row in enumerate(data):
        keep=[j for j,r in enumerate(data) if r["implementation"]!=row["implementation"]]
        fn,_=ridge_fit([x[j] for j in keep],[y[j] for j in keep])
        held.append(fn(x[i]))
    errors=sorted(abs(p-v) for p,v in zip(held,y))
    # An empirical held-out-error band, explicitly not a calibrated confidence interval.
    error90=errors[min(len(errors)-1,math.ceil(.9*len(errors))-1)]
    return dict(feature_names=feature_names,fit=fit,training=metrics(y,train),leave_implementation_out=metrics(y,held),empirical_error90_us=error90,predictions=[dict(id=r["id"],observed_us=v,fitted_us=p,held_out_us=h) for r,v,p,h in zip(data,y,train,held)],uncertainty_policy="heuristic +/- max(90th percentile absolute candidate-held-out error, 10% predicted duration); not a calibrated confidence interval")

def mapped_gemv(kernels, row):
    shape=row.get("shape")
    if not shape:return None
    typ={"Q6_K":14,"Q8_0":8,"IQ2_S":22,"IQ3_S":21,"IQ4_NL":20}.get(shape["quantization"])
    if typ is None:return None
    name=row["implementation"]
    prefix="typeinfo name for "
    if name=="r5":
        prefix += f"iq3::{'kopt4' if shape['experts']>1 else 'expanded'}::(anonymous namespace)::{'Projection' if shape['experts']>1 else 'Multiply'}::run<(iq3::Type){typ}>("
    elif name.startswith(("p25.","p27.")):
        v={"rows4":1,"wg32":2,"private_decode":3,"paired_input":4,"half_table":5,"scale8":7,"wide8":8,"fp32_input":9,"packed64":10,"rows2sg":11}[name.split('.')[-1]]
        prefix+=f"packet26::p25bridge::Kernel<(iq3::Type){typ}, (p25::C){v}>::submit("
    elif name.startswith("p28."):
        split=4 if row["family"] in ("gemv:qsa.k","gemv:attention") else 1
        rpg=4 if name.endswith("rows4") else 1
        share=str(".shared." in name).lower();pair=str(".paired." in name).lower()
        prefix+=f"p28::Kernel<(iq3::Type){typ}, {shape['k']}u, {split}u, {rpg}u, {share}, {pair}>::submit("
    elif name.startswith("p29.down."):
        prefix+=f"p29::Kernel<{4 if name.endswith('rows4') else 1}u>::submit("
    else:return None
    matches=[k for k in kernels if k["demangled"].startswith(prefix) and "handler&)#1}" in k["demangled"]]
    if len(matches)!=1:return None
    return matches[0]

def fit_codegen(include_spill=True):
    measured=json.loads((HERE/"measurements.json").read_text())
    kernels=json.loads((HERE/"codegen.json").read_text())["kernels"]
    raw=[r for r in measured["rows"] if r["primary_fit"] and r["family"].startswith("gemv:")]
    controls={}
    for r in raw:
        if r["arm"]=="packet18": controls.setdefault((r["family"],r["workload"]),[]).append(r)
    anchors={key:statistics.median(r["median_us"] for r in rows) for key,rows in controls.items()}
    data=[];omitted=[]
    for r in raw:
        if r["arm"]!="specialised":continue
        group=(r["family"],r["workload"]);base=controls[group][0]
        k=mapped_gemv(kernels,r);b=mapped_gemv(kernels,base)
        if k is None or b is None:
            omitted.append({"id":r["id"],"reason":"main-kernel mapping absent or ambiguous"});continue
        feature={f"log_ratio_{f}":math.log(max(k[f],1)/max(b[f],1)) for f in ("simd16_issue_equivalents","memory_messages","alu64")}
        feature["extra_stage_count"]=r["stage_events_per_repetition"]-base["stage_events_per_repetition"]
        spill=lambda z:sum(int(re.search(r"spill size (\d+)",v).group(1)) for v in z.get("spill_metadata",[]) if re.search(r"spill size (\d+)",v))
        if include_spill:feature["spill_kib_difference"]=(spill(k)-spill(b))/1024
        data.append(dict(id=r["id"],implementation=r["implementation"],workload=r["workload"],median_us=math.log(r["median_us"]/anchors[group]),actual_us=r["median_us"],baseline_us=anchors[group],features=feature,kernel=k["kernel"],asm_sha256=k["asm_sha256"],baseline_kernel=b["kernel"],main_static={f:k[f] for f in ("instructions","simd16_issue_equivalents","memory_messages","alu64","simd","barriers","grf")},measurement_source=r["source"],measurement_pointer=r["pointer"],stage_events_per_repetition=r["stage_events_per_repetition"]))
    names=list(data[0]["features"])
    x=[[r["features"][f] for f in names] for r in data];y=[r["median_us"] for r in data]
    fn,coeff=ridge_fit(x,y);train=[fn(a) for a in x];held=[]
    for i,row in enumerate(data):
        keep=[j for j,r in enumerate(data) if r["implementation"]!=row["implementation"]]
        f,_=ridge_fit([x[j] for j in keep],[y[j] for j in keep]);held.append(f(x[i]))
    actual=[r["actual_us"] for r in data]
    pred=[math.exp(v)*r["baseline_us"] for r,v in zip(data,train)]
    cv=[math.exp(v)*r["baseline_us"] for r,v in zip(data,held)]
    for r,p,h in zip(data,pred,cv):r.update(fitted_us=p,held_out_us=h);del r["median_us"]
    rel=sorted(abs(p-t)/t for p,t in zip(cv,actual));absolute=sorted(abs(p-t) for p,t in zip(cv,actual))
    out=dict(schema="packet33.static-surrogate.v1",device_ran=False,predictive_model_qualified=False,description="log(t / family workload R5 median) = intercept + coefficients times standardized log ratios of whole-main-kernel static SIMD16-equivalent instructions, memory messages and 64-bit operations + extra event count + explicit spill-size KiB difference; ridge penalty fixed at 1 before fitting",feature_names=names,coefficients=coeff,training=metrics(actual,pred),leave_implementation_out=metrics(actual,cv),uncertainty=dict(empirical_candidate_held_out_p90_absolute_us=absolute[math.ceil(.9*len(absolute))-1],empirical_candidate_held_out_p90_relative_fraction=rel[math.ceil(.9*len(rel))-1],minimum_fraction=.1,policy="Use max(p90 held-out absolute error, 10% prediction) as heuristic +/- band; not a statistical confidence interval"),rows=data,omitted=omitted,limitations=["whole static functions include cold invalid-route and alternate-runtime-shape paths; not dynamic per-weight instruction counts","main kernel only; preprocessing/finalization represented by event count, not their instructions","offline AOT driver option matching unconfirmed: see packet toolchain notes","family normalization uses independently measured baseline and does not predict unseen-shape baseline","leave-one-implementation-out keeps no rows of same candidate but may retain closely related source variants","times from one p29 K2 process; within-run repetitions do not establish fresh-process stability","routing/QSA/recurrence/activation omitted from GEMV fit; branch-dependent monolithic Glue cannot be equated to one timed path"],source_hashes={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ("codegen.json","measurements.json")})
    predictions=[]
    if include_spill:
        cases=[("p33.down.bank","expsdown",0,20,640,1),("p33.down.select","expsdown",1,20,640,1),("p33.gate.restrict","expsgate.iq2",0,22,2560,1),("p33.gate.restrict","expsgate.iq3",0,21,2560,1),("p33.dense.segment","gdn.qkv.q6",0,14,2560,1),("p33.dense.segment","gdn.qkv.q8",0,8,2560,1),("p33.dense.segment","qsa.k",0,14,2560,4)]
        for name,workload,mode,typ,kk,split in cases:
            ref=next(r for r in raw if r["workload"]==workload and r["arm"]=="packet18")
            b=mapped_gemv(kernels,ref)
            prefix=f"typeinfo name for p33::Kernel<{mode}u, (iq3::Type){typ}, {kk}u, {split}u>::submit("
            found=[k for k in kernels if k["demangled"].startswith(prefix)]
            result=dict(candidate=name,workload=workload,kind="unqualified static-surrogate prediction",device_measured=False,baseline_us=anchors[(ref["family"],workload)])
            if len(found)!=1:
                result.update(predicted_us=None,status="assembly not yet available")
            else:
                k=found[0]
                feats={f"log_ratio_{f}":math.log(max(k[f],1)/max(b[f],1)) for f in ("simd16_issue_equivalents","memory_messages","alu64")}
                feats["extra_stage_count"]=(2 if split==4 else 1)-ref["stage_events_per_repetition"]
                spill=lambda z:sum(int(re.search(r"spill size (\d+)",v).group(1)) for v in z.get("spill_metadata",[]) if re.search(r"spill size (\d+)",v))
                feats["spill_kib_difference"]=(spill(k)-spill(b))/1024
                predicted=math.exp(fn([feats[f] for f in names]))*result["baseline_us"]
                band=max(out["uncertainty"]["empirical_candidate_held_out_p90_absolute_us"],.1*predicted)
                result.update(predicted_us=predicted,heuristic_interval_us=[max(0,predicted-band),predicted+band],asm_sha256=k["asm_sha256"],kernel=k["kernel"],features=feats,status="prediction; failed cross-validation means ordering is unqualified")
            predictions.append(result)
        for family,name in [("route","p33.route.rank4"),("qsa.attention","p33.qsa.shape")]:
            priors=[r for r in measured["rows"] if r["family"]==family and (r["primary_fit"] or r["id"].startswith("p27-table:"))]
            anchor=next(r for r in priors if r["primary_fit"] and r["implementation"]=="round2")
            incumbent=next(r for r in priors if r["primary_fit"] and r["arm"]=="packet18")
            predictions.append(dict(candidate=name,workload=family,kind="null-effect prior for unchanged round2 source path; NOT fitted GEMV estimate",predicted_us=anchor["median_us"],heuristic_interval_us=[min(r["median_us"] for r in priors)*.9,max(r["median_us"] for r in priors)*1.1],incumbent_us=incumbent["median_us"],device_measured=False,source_measurement_ids=[r["id"] for r in priors],uncertainty="historical incumbent/candidate span enlarged by 10%; not a confidence interval or a claimed bound",status="requires coordinator timing; assembly cannot determine dynamic rank/attention cost"))
    out["new_candidate_predictions"]=predictions
    groups={}
    for row in data:groups.setdefault(row["workload"],[]).append(row)
    out["held_out_by_workload"]={name:metrics([r["actual_us"] for r in rs],[r["held_out_us"] for r in rs]) for name,rs in groups.items()}
    if include_spill:
        ablation=fit_codegen(False)
        out["without_spill_feature_ablation"]={k:ablation[k] for k in ("training","leave_implementation_out","coefficients")}
        (HERE/"model.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({k:out[k] for k in ("training","leave_implementation_out","uncertainty")}))
    return out

if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--extract",action="store_true");parser.add_argument("--features",type=Path);parser.add_argument("--fit",action="store_true");args=parser.parse_args()
    if args.extract:
        d=extract();print(json.dumps({"rows":len(d["rows"]),"primary_rows":sum(x["primary_fit"] for x in d["rows"])}))
    if args.features:
        d=json.loads(args.features.read_text());fit=fit_flat_feature_rows(d["rows"],d["feature_names"])
        (HERE/"model.json").write_text(json.dumps(fit,indent=2)+"\n")
        print(json.dumps({k:fit[k] for k in ("training","leave_implementation_out")}))

    if args.fit: fit_codegen()

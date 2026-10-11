#!/usr/bin/env python3
"""Expand recorded CPU submissions using the audited frozen native dispatch.
This is a source-derived enumeration, never a native execution trace.
"""
import collections,gzip,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
PLAN=HERE.parent/"packet16-decode/evidence/20261011-w2x-two-card-fault/plan.json"
def main():
 plan=json.loads(PLAN.read_text());sites={x["label"]:x for x in plan["launch_census"]}
 weights={x["name"]:x for x in plan["tensor_owners"]}
 source=HERE/"real-short-shipped-submissions.jsonl.gz";output=HERE/"native-first-position-enumeration.jsonl.gz"
 rows=[json.loads(x) for x in gzip.open(source,"rt")]
 last={};seen=collections.Counter();counts=collections.Counter();total=0
 with gzip.open(output,"wt",compresslevel=9) as f:
  def emit(row):
   nonlocal total
   f.write(json.dumps(row,separators=(",",":"))+"\n");total+=1;counts[row["kind"]]+=1
  for row in rows:
   event=row["event"];site=row["site"];match=re.match(r"position=(-?\d+):(.*)",site)
   if match and int(match[1])>0:break
   label=match[2] if match else site;access=row["access"]
   copy=len(access)==2 and access[0]["read"] and not access[0]["write"] and access[1]["write"] and not access[1]["read"]
   if match and label=="commit.final" and copy and access[1]["name"].endswith(":token"):
    break # next prompt position begins with its token H2D, before prepare_token labels it
   spec=sites.get(label);deps=[last[x] for x in row["deps"]]
   row={**row,"event":"n"+str(event),"deps":deps,"origin_cpu_event":event,"source_derived":True}
   if not access:kind="marker"
   elif copy:kind="peer-copy" if row["peer"] else "copy"
   elif spec and spec["op"]=="gemv" and spec["parallel_kernels"]==2:
    # packet7/8 split4 partials use 4 F32 values per BF16 output;
    # reduction binds the same buffers but only reads workspace and writes y.
    assert len(access)==3 and not any(x["index"] for x in access), "routed/diagnostic split expansion needs its own contract"
    assert sum(bool(x["write"]) for x in access)==1 and sum(bool(x["read"]) for x in access)==2
    weight=next(x for x in access if ":weight:" in x["name"])
    variant=weights[weight["name"].split(":weight:",1)[1]]["variant"]
    assert variant in ("splitk4_v1","decode_const_split4_v1"), "unsupported native split variant"
    y=next(x for x in access if x["write"]);reads=[x for x in access if x["read"]]
    workspace=dict(name=f"card{row['queue']}:gemv-workspace",owner=row["queue"],context=row["context"],offset=0,bytes=y["bytes"]//2*4*4,read=False,write=True,index=False)
    partial={**row,"event":"n"+str(event)+".partial","kind":"split4-partials","access":[*reads,workspace]}
    emit(partial)
    row={**row,"event":"n"+str(event)+".reduce","deps":[partial["event"],partial["event"]],"kind":"split4-reduce","access":[{**workspace,"read":True,"write":False},y]}
    emit(row);last[event]=row["event"];continue
   else:
    index=seen[site];seen[site]+=1
    if spec and spec["parallel_kernels"]==5:kind=["adapter-entry","attention-score","attention-softmax","attention-value","adapter-exit"][index]
    elif spec and spec["op"]=="moe_combine":kind=["mixture-epilogue","adapter-entry","ng-kernel","adapter-exit"][index]
    elif spec and spec["parallel_kernels"]==3:kind=["adapter-entry","ng-kernel","adapter-exit"][index]
    else:kind=spec["op"] if spec else "kernel"
   row["kind"]=kind;emit(row);last[event]=row["event"]
 summary=dict(schema="packet19.source-derived-native-enumeration.v1",device_executed=False,rows=total,kinds=dict(counts),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),scope="Initialization through prompt position0; two-card resident frozen parallel. Native split GEMV expanded from source; no device run.")
 (HERE/"native-enumeration.json").write_text(json.dumps(summary,indent=2)+"\n")
 print(json.dumps(summary),flush=True)
if __name__=="__main__":main()

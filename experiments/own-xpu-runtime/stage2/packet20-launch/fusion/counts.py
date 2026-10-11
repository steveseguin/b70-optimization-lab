"""Exact census plus explicit constructive fusion schedules; no device needed."""
import collections,json
from pathlib import Path
P=Path(__file__).resolve().parent
rows=json.loads((P/"dag.json").read_text());census=json.loads((P.parent.parent/"packet18-decode-v2/census.json").read_text())
groups=collections.defaultdict(list)
for r in rows:groups[r["label"].split(".")[1] if r["label"].startswith("blk.") else "other"].append(r)
assert len(rows)==1825
summary={"measured":False,"scope":"within-layer constructive schedules; preserve inter-layer/owner boundaries; no recomputation of GEMV reductions","rows":{}}
for dispatch,c in census.items():
 by={}
 def cost(r):
  if r["op"]=="gemv":return 2 if c["runtime_dispatch"][r["weights"][0]] in ("splitk4_v1","decode_const_split4_v1") else 1
  return {"lookup":0,"handoff":0,"handoff_result":0,"moe_combine":2,"qsa_attention":3}.get(r["op"],1)
 for layer,rs in groups.items():
  baseline=sum(map(cost,rs));assert baseline==c["launches_by_layer"][layer]["parallel"],(dispatch,layer,baseline,c["launches_by_layer"][layer])
  chunks=[]
  for r in rs:
   gem=r["op"] in ("gemv","routed_gemv","expert_gate_up");n=cost(r)
   if not n:chunks.append({"labels":[r["label"]],"kernels":0,"merge":False,"card":r["card"]});continue
   if not gem and chunks and chunks[-1]["merge"] and chunks[-1]["card"]==r["card"]:chunks[-1]["labels"].append(r["label"])
   else:chunks.append({"labels":[r["label"]],"kernels":n if gem else 1,"merge":not gem,"card":r["card"]})
  rule_i=sum(x["kernels"] for x in chunks)
  if layer=="other":rule_ii=baseline-2;stages=[] # HC activation and mix absorbed
  else:
   prefix="blk."+layer+".";bylabel={r["label"]:r for r in rs}
   def gem(*names):return max(cost(bylabel[prefix+n]) for n in names)
   # Each stage retains split partial/final stages where present. Non-GEMV
   # maximal chains may use one work-group; low launch count != low latency.
   stages=[("HC attention norm",1),("HC attention down+inject",gem("hc.a.low","hc.a.inject")),("HC attention up",gem("hc.a.gate"))]
   projections=["qsa.qgate","qsa.k","qsa.v","qsa.iq","qsa.ik"] if prefix+"qsa.qgate" in bylabel else ["gdn.qkv","gdn.z","gdn.a","gdn.b"]
   stages += [("attention sibling projections",gem(*projections)),("attention non-GEMV chain",1),("attention output+residual",gem("attention")),("HC FFN norm",1),("HC FFN down+inject",gem("hc.f.low","hc.f.inject")),("HC FFN up",gem("hc.f.gate")),("router+shared gate/up+scalar",gem("router","shexpgate","shexpup","shared_gate")),("route+descriptors+gather",1),("expert gate/up+activation",1),("expert down",1),("shared down",gem("shexpdown")),("MoE combine+residual",1)]
   if layer=="1":stages=[("PLE hash",1),("PLE key+value",gem("ple.key","ple.value"))]+stages # PLE tail fuses into HC attention norm
   rule_ii=sum(n for _,n in stages)
  by[layer]={"baseline":baseline,"i":rule_i,"ii":rule_ii,"iii":rule_ii,"iii_standalone":rule_ii+(layer!="other"),"i_schedule":chunks,"ii_schedule":stages}
 totals={k:sum(x[k] for x in by.values()) for k in ("baseline","i","ii","iii","iii_standalone")};assert totals["baseline"]==c["parallel_kernels"]
 cross=[]
 for before,after in zip(rows,rows[1:]):
  if (before["label"].endswith("ffn.combine") or before["label"]=="streams") and before["card"]==after["card"] and cost(after)>0:
   cross.append([before["label"],after["label"]])
 assert len(cross)==48
 minimum={k:(v-len(cross) if k!="baseline" else v) for k,v in totals.items()}
 summary["rows"][dispatch]={"within_layer_totals":totals,"totals":minimum,"cross_layer_merges":cross,"layers":by}
(P/"counts.json").write_text(json.dumps(summary,indent=2)+"\n")
for d,r in summary["rows"].items():print(d,r["totals"],{l:{k:r["layers"][l][k] for k in ("baseline","i","ii","iii")} for l in ("0","1","2","3","other")})

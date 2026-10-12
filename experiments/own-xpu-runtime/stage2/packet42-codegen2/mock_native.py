"""CPU-only native protocol stand-in. Never imports SYCL/Level Zero."""
import argparse,json,os,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("--authorized-device-window",action="store_true");p.add_argument("--card");p.add_argument("--output",type=Path);p.add_argument("--compile-smoke",action="store_true");p.add_argument("--repetitions");p.add_argument("--mode",default="ok");p.add_argument("--floor",action="store_true");p.add_argument("--family",default="gemv");a=p.parse_args()
a.output.mkdir(exist_ok=True)
if a.mode=="bad-json":
 (a.output/"receipt.json").write_text("");sys.exit(0)
if a.mode=="empty-bindings":
 print("empty compute bindings",file=sys.stderr);sys.exit(1)
if a.mode=="enospc":
 print("FAILED WINDOW: ENOSPC during receipt write",file=sys.stderr);sys.exit(1)
row=dict(passed=True,infrastructure_passed=True,ld_library_path=os.environ.get("LD_LIBRARY_PATH"),mock=True)
if a.floor:
 for g in range(4):
  axes=[(sg,l,b,ptr,n,parts,1) for sg in range(2) for l in range(2) for b in range(1 if g==0 else 2) for ptr in range(2) for n in (1,32,640,2560,6400,10240,25600) for parts in (1,2,4)]
  axes.append((1,0,0,0,1,1,1000))
  for sg,l,b,ptr,n,parts,burst in axes:
   name=f'g{g}-sg{sg}-l{l}-b{b}-p{ptr}-n{n}-split{parts}-burst{burst}'
   data={'class':name,'passed':True,'N':n,'parts':parts,'burst':burst,'geometry':g,'subgroup32':sg,'unused_local':l,'barrier':b,'parameter_pointer':ptr,'gpu_us':[3.0*burst]*200,'wall_us':[6.0*burst]*200,'mock':True}
   (a.output/(name+'.json')).write_text(json.dumps(data)+'\n')
if not a.compile_smoke and not a.floor:
 if a.family in ("tiny","extras"):
  aliases="hc.a.act,hc.f.act,final.act" if a.family=="tiny" else "expsgate.check,expsup.check,expsdown.check"
  candidate="p42.tiny.wg32" if a.family=="tiny" else "p42.extras.check.wg32"
  case={"class":a.family+"-fixture-wg32","klass":aliases,"candidate":candidate,"timing_eligible":True,"passed":a.mode!="case-fail","error":"injected" if a.mode=="case-fail" else "","control_gpu_us":[5.0]*200,"candidate_gpu_us":[3.0]*200,"control_wall_us":[8.0]*200,"candidate_wall_us":[6.0]*200}
  (a.output/"summary.json").write_text(json.dumps({"rows":[case]})+"\n")
 else:
  events=[]
  klass="gemv:expsdown" if a.family=="gemv" else "gdn.recurrence" if a.family=="parallel" else "route"
  candidate="p42.down.select_vector" if a.family=="gemv" else "p42.gdn.token1" if a.family=="parallel" else "p42.route.production_rank32"
  workload="expsdown" if a.family=="gemv" else ""
  for rep in range(200):
   for arm in ("packet18","specialised"):
    stages=(5 if arm=="packet18" else 4) if a.family=="route" else 1
    for stage in range(stages):
     events.append(dict(**{"class":klass},candidate=candidate,workload=workload,variant=arm,repetition=rep,event=rep*10+(5 if arm=="specialised" else 0)+stage,stage_count=stages,exact=True,bytes_equal=True,start_ns=100,end_ns=100+(100000 if arm=="packet18" else 80000)//stages,full_payload_bytes=9000000 if a.family=="gemv" else 4000,timing_mode="rotated",rotation_copies=8,buffer_copy=rep%8,host_wall_us=150))
  (a.output/"events.jsonl").write_text("".join(json.dumps(r)+"\n" for r in events))
  if a.mode=="case-fail":
   (a.output/"candidate-failures.jsonl").write_text(json.dumps(dict(**{"class":klass},implementation=candidate,workload=workload,error="injected exactness failure"))+"\n")
(a.output/"receipt.json").write_text(json.dumps(row)+"\n")
sys.exit(0)

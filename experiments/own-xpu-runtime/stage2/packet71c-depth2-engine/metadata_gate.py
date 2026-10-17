"""Validate each enabled M2 class against retained production tensor metadata."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
PLAN=P.parent/'suite-inputs-20261012/incident-retrospective/plan.tsv'
def check():
 rows=[line.split() for line in PLAN.read_text().splitlines() if line.strip()]
 mapping={'hc.a.gate':['hc_attn_up.weight'],'hc.f.gate':['hc_ffn_up.weight'],'router':['ffn_gate_inp.weight'],'route':['ffn_gate_inp.weight'],'expsgate':['ffn_gate_exps.weight','ffn_up_exps.weight'],'expsdown':['ffn_down_exps.weight'],'gdn.qkv':['attn_qkv.weight'],'gdn.z':['attn_gate.weight'],'qsa.qgate':['attn_q.weight'],'attention':['attn_output.weight'],'logits':['output.weight'],'shexpdown':['ffn_down_shexp.weight'],'ple.key':['ple_key.weight']}
 table=dict(line.split() for line in (P/'kernel-table.tsv').read_text().splitlines())
 result={}
 for cls,mode in table.items():
  if mode=='serial':continue
  assert mode=='production-M2' and cls in mapping
  selected=[r for r in rows if any(r[1]==suffix or r[1].endswith('.'+suffix) for suffix in mapping[cls])]
  assert selected,cls
  eligible=[];fallback=[]
  for r in selected:
   t=int(r[3]);dims=tuple(map(int,r[9:]));assert len(dims)>=2,(cls,r)
   if cls in ('hc.a.gate','hc.f.gate'):supported=t==8 and dims==(320,10240)
   elif cls in ('router','route'):supported=t==0 and dims==(2560,512)
   elif cls=='expsgate':supported=t==22 and dims==(2560,640,512)
   elif cls=='expsdown':supported=t==20 and dims==(640,2560,512)
   elif cls=='attention':supported=t==14 and dims[0]==6144
   else:supported=(t,dims[0]) in ((14,2560),(8,2560),(8,640),(8,320),(0,10240))
   (eligible if supported else fallback).append(r[1])
  assert eligible,cls
  result[cls]=dict(batched_tensors=len(eligible),serial_fallback_tensors=len(fallback),fallback=fallback,tensors=len(selected),types_and_shapes=sorted({str((int(r[3]),tuple(map(int,r[9:])))) for r in selected}),mode=mode)
 return dict(passed=True,device_executed=False,model_payload_read=False,plan=str(PLAN),plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest(),classes=result)
if __name__=='__main__':print(json.dumps(check(),indent=2))

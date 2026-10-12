"""Account for frozen monotonic QSA allocations; verify against a CPU Core probe."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def push(n):
 cap=used=0
 while cap<n:cap=max(16,cap*2);used+=cap
 return used
def tree(n):
 used=cap=n
 while n>1:
  if n%2:
   if n==cap:cap=max(16,cap*2);used+=cap
   n+=1
  n//=2
 return used
def account(n):
 growth,reduction=push(n),tree(n)
 parts=dict(converted_inputs_and_output=3*24*256+2*4096*2*256+2051+2,attention_y=24*256,admitted_ids=growth,
 score_dot_products=24*n*(256+tree(256)),score_vectors=24*growth,score_reduction_trees=24*reduction,
 value_term_vectors=24*256*growth,value_reduction_trees=24*256*reduction)
 total=sum(parts.values());return dict(admitted_positions=n,float_slots=total,bytes=total*4,parts=parts)
def main():
 rows=[account(n) for n in range(1,2052)];first=next(r for r in rows if r['float_slots']>64*1024**2);maximum=max(rows,key=lambda r:r['float_slots'])
 assert first['admitted_positions']==1225 and maximum['admitted_positions']==2051
 assert maximum['float_slots']==117813069 and all(r['float_slots']<=128*1024**2 for r in rows)
 temp=HERE/'scratch-probe.json.tmp';probe=json.loads(temp.read_text()) if temp.exists() else json.loads((HERE/'scratch-probe.json').read_text())
 for row in probe:assert row['output_zero'] and row['float_slots']==account(row['admitted_positions'])['float_slots']
 if temp.exists():temp.rename(HERE/'scratch-probe.json')
 result=dict(schema='iq3-long.qsa-scratch-symbolic.v1',passed=True,method='Exact monotonic allocation count; includes active/error input copies; verified against unmodified Core at eight boundary counts',
 scope='QSA attention, all admitted counts 1..2051 at context4096',device_executed=False,model_loaded=False,context=4096,geometry=dict(qh=24,kvh=2,ad=256,budget=2048),
 original_float_capacity=64*1024**2,overlay_float_capacity=128*1024**2,first_original_failure=first,maximum=maximum,
 overlay_remaining_bytes_at_maximum=(128*1024**2-maximum['float_slots'])*4,script_sha256=sha(Path(__file__)),probe_source_sha256=sha(HERE/'scratch_probe.cpp'),probe_binary_sha256=sha(HERE/'build/scratch-probe'),
 probe_result_sha256=sha(HERE/'scratch-probe.json'),core_sha256=sha(ROOT/'experiments/own-xpu-runtime/stage2/packet17-detmath/core_v2.hpp'),all_counts_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
 out=HERE/'scratch-analysis.json.tmp';out.write_text(json.dumps(result,indent=2)+'\n');assert json.loads(out.read_text())==result;out.rename(HERE/'scratch-analysis.json')
 print(json.dumps({k:result[k] for k in ('passed','first_original_failure','maximum','overlay_remaining_bytes_at_maximum')},indent=2))
if __name__=='__main__':main()

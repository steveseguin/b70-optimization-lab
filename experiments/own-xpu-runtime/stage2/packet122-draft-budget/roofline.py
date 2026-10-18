"""Useful unique-byte model and honest pending/fresh per-class event tables."""
import json,statistics,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def model(context):
 H=2560;L=320;N=80128;out={}
 def add(label,weights=0,reads=0,writes=0,note=''):
  out['draft.'+label]=dict(weight_bytes=weights,activation_state_read_bytes=reads,write_bytes=writes,useful_bytes=weights+reads+writes,reference_us=(weights+reads+writes)/555e3,note=note)
 def dense(label,rows,cols,batch=1,int8=False,paired=False):
  wb=rows*cols*(1.25 if int8 else 2)*(batch if int8 else 1)*(2 if paired else 1)
  add(label,int(wb),cols*2*(1 if paired else batch)+(120 if int8 else 0),rows*batch*2*(2 if paired else 1)+(batch*4*(2 if paired else 1) if int8 else 0),'unique weights; repeated row input reads and implementation scratch excluded')
 add('merge.embedding_norm',H*4,H*2,H*2,'FP32 converted gain; unique BF16 input/output')
 add('merge.hidden_norm',4*H*4,4*H*2,4*H*2,'original padded norm; reduction scratch excluded')
 dense('merge.embedding_projected',H,H);dense('merge.projected',H,H,4)
 add('merge.add',reads=5*H*2,writes=4*H*2)
 add('begin.0',reads=8,writes=4)
 for side in ('blk.0.hc.a','blk.0.hc.f','final'):
  add(side+'.norm',4*H*4,4*H*2,4*H*2,'unique bytes, repeated norm input reads and scratch excluded')
  add(side+'.low',L*4*H*2,4*H*2,L*4,'includes original low output and fused activation output')
  add(side+'.gate',4*H*L*2,L*2+4*H*2,5*H*2,'includes gate and fused four-stream mixture; candidate keeps all bytes')
  if side!='final':dense(side+'.inject',4,4*H)
 for label,rows in [('qgate',12288),('k',512),('v',512),('iq',512),('ik',128)]:dense('blk.0.qsa.'+label,rows,H)
 add('blk.0.qsa.prepare',(256+256+128)*4,(12288+512+512)*2+128,(6144*2+512+512)*2,'converted gains; one useful RoPE row')
 add('blk.0.qsa.pool',128*4,2304+768+128,2304+256,'both requested contexts append a pooled row; three prior raw rows')
 add('blk.0.qsa.select',reads=512*2+(context//4)*128*2,writes=(2048+3)*4,note='unique pooled inputs and selected ids; score/rank scratch and repeated comparisons excluded')
 selected=4*min(context//4,512)+context%4
 add('blk.0.qsa.attention',reads=6144*4+selected*2048+(selected+1)*4,writes=6144*2,note='split32; unique full16 K/V union, repeated heads and partial/reduction scratch excluded')
 dense('blk.0.attention',H,6144)
 add('blk.0.attn.combine',reads=(4*H+H+4)*2+8,writes=4*H*2)
 dense('blk.0.router',512,H)
 add('blk.0.route',reads=512*2+8,writes=10*8,note='unique router logits, rounded probabilities and selected indices; exp/max/sum scratch excluded')
 add('blk.0.gather',reads=10*4+H*2+8,writes=10*H*2+10*3*4*2)
 dense('blk.0.expsgate',640,H,10,True,True)
 dense('blk.0.expsdown',H,640,10,True)
 for label in ('expsgate','expsup','expsdown'):add('blk.0.'+label+'.check',reads=40+8,writes=4)
 add('blk.0.expsact',reads=640*10*4+8,writes=640*10*2)
 for label,rows,cols in [('shexpgate',640,H),('shexpup',640,H),('shexpdown',H,640),('shared_gate',1,H)]:dense('blk.0.'+label,rows,cols)
 add('blk.0.shexpact',reads=640*4+8,writes=640*2)
 add('blk.0.moe',reads=H*10*2+10*4+H*2+2+8,writes=H*2,note='ordered expert sum and shared blend, both BF16 boundaries retained')
 add('blk.0.ffn.combine',reads=(4*H+H+4)*2+8,writes=4*H*2)
 add('logits',N*3200,H*2,N*2,'expanded Q6 useful fields 3200 bytes/row; storage stride stays3380')
 add('argmax',reads=N*2+8,writes=8,note='fixed prefix only, original lowest-index tie rule; scratch excluded')
 add('commit.final',reads=12,writes=4)
 return out
def measured(repeat):
 folder=P/f'evidence/micro-B-{repeat}';receipt=folder/'window.json'
 if not receipt.exists():return None
 w=json.loads(receipt.read_text());assert all(w.get(k) is True for k in ('passed','device_executed','drained','lease_released')),'incomplete window'
 build=P/'evidence/microbench-build.json';assert w['build_receipt_sha256']==sha(build)
 for n,h in w['native_artifacts'].items():assert sha(folder/'native'/n)==h
 checks=json.loads((folder/'native/checks.json').read_text());assert checks['byte_exact_pairs']==100
 rows=[json.loads(s) for s in (folder/'native/iterations.jsonl').read_text().splitlines()];assert len(rows)==100
 index={}
 for row in rows:
  ctx,it=row['context'],row['iteration'];assert ctx in (128,4096) and 0<=it<50 and (ctx,it) not in index
  assert row['warmup'] is (it<10);assert set(row['classes_ns'])==set(model(ctx)),('unaccounted or absent class',set(row['classes_ns'])^set(model(ctx)))
  assert sum(row['classes_ns'].values())==row['gpu_ns'] and len(row['events'])==row['submissions'];index[ctx,it]=row
 return dict(window_sha256=sha(receipt),process=[w['boot_id'],w['pid'],w['process_start_ticks']],contexts={str(ctx):{cls:statistics.median(index[ctx,it]['classes_ns'][cls] for it in range(10,50))/1e3 for cls in model(ctx)} for ctx in (128,4096)})
def main():
 processes=[measured(n) for n in (1,2)];result=dict(schema='packet122.draft-budget.v1',diagnostic_only=True,measured=all(processes),processes=processes,contexts={str(c):model(c) for c in (128,4096)})
 if all(processes):assert processes[0]['process']!=processes[1]['process']
 text=['# Packet122 complete draft byte and event budget','',
 'Event times are pending until the coordinator completes both fresh processes. No old class times are substituted.',
 '', 'Each row counts unique useful weights and activation/state bytes per step. It is a byte reference, not measured HBM traffic: cache reuse, repeated reads, scratch, launch latency, reductions and instruction cost are excluded. Divide by the historical 555 GB/s calibration only for scale; it is not a hard floor or an attainable-speed claim. No numerical compute floor is justified. Draft INT8 expert scales and BF16/FP32 boundaries are unchanged.',
 '', 'The captured-input 4K fill cycles real host-reference hidden/token captures. This is an operator diagnostic, not a natural prompt or model-speed headline. Event sums exclude transfers, loading, state restoration, host submission and comparison. Complete-step timing is the median of each step sum, not a sum of class medians.']
 for ctx in (128,4096):
  text += ['',f'## Occupied context {ctx}','', '| Draft event class | Weight bytes | Other read bytes | Write bytes | /555 GB/s, µs | Process1, µs | Process2, µs |','| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
  for cls,r in model(ctx).items():
   times=[f"{p['contexts'][str(ctx)][cls]:.3f}" if p else 'pending' for p in processes]
   text.append(f"| {cls.removeprefix('draft.')} | {r['weight_bytes']:,} | {r['activation_state_read_bytes']:,} | {r['write_bytes']:,} | {r['reference_us']:.3f} | {times[0]} | {times[1]} |")
 text += ['', 'Per-row assumptions and formulas are retained in `roofline.json` and this generator. Fused activation and mix consumers have no separate event or extra byte row. The unchanged host embedding decode and input copies are outside the measured kernel sum. See `LEVER-RANKING.md` for the independent candidate decision.','']
 (P/'ROOFLINE.md').write_text('\n'.join(text));(P/'roofline.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Join discarded d2 to the unchanged emitted stream. CPU only, no model loads."""
import argparse,hashlib,json,math,statistics as st
from collections import defaultdict
from pathlib import Path
P=Path(__file__).resolve().parent
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def require(v,msg):
 if not v:raise ValueError(msg)
def prompt(receipt,probes):
 require(receipt.get('passed') and receipt.get('exact_oracle') and receipt.get('cached_tokens')==0,'exact cold screen receipt required')
 n=receipt['prompt_tokens'];tokens=receipt['tokens'];accepted={r['position']:r for r in receipt['guess_rows']}
 seen=set();hits=eligible=censored=miss1=0;times=[];pairs=[]
 for r in probes:
  if 'skipped' in r:continue
  require(r['schema']=='packet66.depth2.cycle.v1' and r['rank']==1 and r['discarded'] is True,'invalid probe row')
  pos=r['d1_position'];require(pos not in seen,'duplicate probe position');seen.add(pos)
  require(r['d2_position']==pos+1,'non-adjacent d2 position')
  require(all(math.isfinite(r[k]) and r[k]>=0 for k in ('extra_pass_wall_ms','extra_pass_gpu_ms','snapshot_ms','restore_ms')),'invalid timing')
  if pos<n:continue
  require(pos-n<len(tokens) and tokens[pos-n]>=0,'d1 outside generated stream')
  check=accepted.get(pos)
  if check is None:
   censored+=1;continue
  require(check['guess']==r['d1'] and check['actual']==tokens[pos-n],'d1/controller join mismatch')
  times.append(r)
  if not check['hit']:miss1+=1;continue
  require(r['d1']==tokens[pos-n],'accepted d1 differs from output')
  if pos+1-n>=len(tokens):censored+=1;continue
  require(r['d2']>=0,'second draft failed')
  eligible+=1;hit=r['d2']==tokens[pos+1-n];hits+=hit
  pairs.append(dict(d1_position=pos,d1=r['d1'],d2=r['d2'],emitted_d2=tokens[pos+1-n],hit=hit))
 expected={pos for pos,r in accepted.items() if pos>=n and r['guess'] is not None and r['guess']>=0}
 require(expected<=seen,'missing probe cycles')
 return dict(prompt_id=receipt['prompt_id'],prompt_class=receipt['prompt_class'],accepted_d1_with_successor=eligible,accepted_d2=hits,a2=hits/eligible if eligible else None,d1_misses=miss1,censored=censored,probe_cycles=len(times),extra_pass_wall_ms_mean=st.mean(r['extra_pass_wall_ms'] for r in times) if times else None,extra_pass_gpu_ms_mean=st.mean(r['extra_pass_gpu_ms'] for r in times) if times else None,snapshot_restore_ms_mean=st.mean(r['snapshot_ms']+r['restore_ms'] for r in times) if times else None,pairs=pairs)
def aggregate(rows):
 classes=defaultdict(list)
 for row in rows:classes[row['prompt_class']].append(row)
 def rate(rs):
  n=sum(r['accepted_d1_with_successor'] for r in rs);k=sum(r['accepted_d2'] for r in rs)
  return dict(accepted_d1_with_successor=n,accepted_d2=k,a2=k/n if n else None)
 byclass={k:dict(**rate(rs),prompt_ids=[r['prompt_id'] for r in rs]) for k,rs in classes.items()}
 valid=[r['a2'] for r in byclass.values() if r['a2'] is not None]
 cycles=sum(r['probe_cycles'] for r in rows)
 return dict(prompts=rows,classes=byclass,pooled=rate(rows),class_balanced_a2=st.mean(valid) if len(valid)==len(classes) and valid else None,
  extra_pass_wall_ms_mean=sum(r['extra_pass_wall_ms_mean']*r['probe_cycles'] for r in rows)/cycles if cycles else None,
  extra_pass_gpu_ms_mean=sum(r['extra_pass_gpu_ms_mean']*r['probe_cycles'] for r in rows)/cycles if cycles else None)
def projection(a2,draft_ms,verify_ms):
 a1=.787;baseline=51.03;c1=1000*(1+a1)/baseline
 return [dict(a2=max(0,min(1,a2+delta)),projected_tok_s=1000*(1+a1+a1*max(0,min(1,a2+delta)))/(c1+draft_ms+verify_ms),
   change_percent=100*((1+a1+a1*max(0,min(1,a2+delta)))/(c1+draft_ms+verify_ms)/baseline*1000-1)) for delta in (-.05,0,.05)]
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--screen',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 window=json.loads((a.screen/'window.json').read_text());require(window['passed'],'screen not passed')
 summary=json.loads((a.screen/'run/summary.json').read_text());require(summary['passed'] and summary['request_count']==12,'complete suite required')
 rows=[];sources={}
 for entry in summary['requests']:
  dest=a.screen/'run'/entry['prompt_id'];rp=dest/'receipt.json';pp=dest/'rank1/depth2-probe.jsonl'
  r=json.loads(rp.read_text());rows.append(prompt(r,[json.loads(s) for s in pp.read_text().splitlines()]));sources[str(rp)]=sha(rp);sources[str(pp)]=sha(pp)
 require(len(rows)==12 and len({r['prompt_id'] for r in rows})==12,'12 distinct prompts required')
 result=aggregate(rows);cost=json.loads((P/'cost-model.json').read_text());a2=result['class_balanced_a2']
 require(a2 is not None,'empty class acceptance denominator')
 result.update(schema='packet66.depth2.acceptance.v1',diagnostic=True,qualifying=False,sources=sources,cost_model_sha256=sha(P/'cost-model.json'),projection_assumptions=cost['projection_assumptions'])
 result['conditional_projection']=projection(a2,result['extra_pass_wall_ms_mean'],cost['serial_row_proxy']['verify_increment_ms'])
 result['projection_meets_10_percent']=result['conditional_projection'][1]['change_percent']>=10
 result['decision']='build a separately gated depth-2 prototype' if result['projection_meets_10_percent'] else 'do not build depth 2 on this cost assumption'
 result['limitation']='No M=3 verifier or matched M=1-to-M=2 increment was measured; projection is an explicitly assumed serial-row proxy.'
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('pooled','class_balanced_a2','conditional_projection','decision')},indent=2))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Measure current halves from completed packet61x screens, CPU only."""
import gzip,hashlib,importlib.util,json,os,statistics as st
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];E=P/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 method=P.parent/'packet57-attribution/timeline.py'
 spec=importlib.util.spec_from_file_location('timeline',method);t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
 result=dict(schema='packet63.rank-balance-diagnosis.v1',device_executed=False,new_speed_claim=False,sources={str(method.relative_to(ROOT)):sha(method)},screens={},definition={
  'scope':'All twelve fixed 128-token suite prompts, excluding incident64. After TTFT, all 127 intervals per prompt; not the 99-interval submission metric.',
  'S_ms':'Rank0 speculative HALF(p+1) command completed minus received; includes snapshot.',
  'B_ms':'Rank1 target HALF(p) command completed minus received; includes full target head; draft is separately reported.',
  'B_including_draft_ms':'Paired B_ms + D_wall_ms. Serial work budget including draft; approximate because draft is asynchronous, not an exact GPU-time partition.',
  'D_wall_ms':'Recorded draft publication wall time, not GPU kernel time.',
  'A_ms':'Rank0 corrected non-speculative HALF(p) after miss.',
  'decision':'Skip 22/26 when rank1 B >= S; tested even without charging the separate draft work.'})
 compact=[]
 for lane in ('A','B','B2'):
  home=P.parent/'screen/v3/evidence'/('packet61x-'+lane)/'run';cycles=[];files=sorted(f for f in home.glob('*/receipt.json') if f.parent.name!='incident64');assert len(files)==12
  requests={}
  for f in files:
   r=json.loads(f.read_text());assert r['passed'] and r['exact_oracle']
   result['sources'][str(f.relative_to(ROOT))]=sha(f)
   rows=t.extract(r)
   for c in rows:c['B_including_draft_ms']=c['B_ms']+c['D_wall_ms']
   cycles+=rows;requests[f.parent.name]=t.summarize(rows)['counts']
   compact.extend(dict(screen=lane,prompt=f.parent.name,**c) for c in rows)
  summary=t.summarize(cycles);summary['requests']=requests
  summary['skip_22_26']=all(summary[k]['B_ms']['median_ms']>=summary[k]['S_ms']['median_ms'] for k in ('hit','miss'))
  assert summary['skip_22_26'] and summary['counts']['rank0_finishes_last']==0
  result['screens'][lane]=summary
 result['decision']=dict(rank_balance='skipped',reason='Rank1 finishes last in all 4536 complete cycles; even its target half alone is longer than rank0.',memory_admission='not applicable: timing prerequisite fails; no split option built or sealed',split_unchanged='23/25; draft on rank1; full target head, state and BF16 KV unchanged')
 data=''.join(json.dumps(c,sort_keys=True)+'\n' for c in compact).encode()
 (E/'cycles.jsonl.gz').write_bytes(gzip.compress(data,mtime=0));result['cycles_sha256']=sha(E/'cycles.jsonl.gz')
 (E/'diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
 for lane,a in result['screens'].items():
  print(lane,a['counts'])
  for kind in ('hit','miss'):print(kind,{k:round(a[kind][k]['median_ms'],6) for k in ('S_ms','B_ms','D_wall_ms','B_including_draft_ms','A_ms','cycle_ms')})
if __name__=='__main__':main()

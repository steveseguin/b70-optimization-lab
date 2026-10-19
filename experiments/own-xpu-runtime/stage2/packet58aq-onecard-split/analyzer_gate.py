"""Replay real parent device data; missing new streams must never produce a decision."""
import hashlib,json,statistics,sys,tempfile,copy
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sys.path.insert(0,str(P/'screen'))
import split_analyze as A
import suite_driver as D

def main():
 parent=P/'lineage/parent-device'
 manifest=D.oracle_inputs();observations={};pins={};count=0;max_prefill=0
 # The complete parent attempt, including cold A0, is retained. Nothing is relabeled as p58aq.
 for label in ('A0','B0','A1','B1','A2'):
  summary=D.summarize(parent,'WSCREEN',manifest,label,128)
  assert summary['passed'] and summary['request_count']==12
  rows=[]
  for entry in manifest['prompts']:
   for leaf in ('timings.jsonl','prefill-timings.jsonl'):
    f=parent/'run'/label/entry['prompt_id']/leaf;r=A.read_rows(f)
    pins[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest();count+=len(r)
    if leaf=='prefill-timings.jsonl':max_prefill=max(max_prefill,max(x['wall_ms'] for x in r))
    else:rows.extend(r)
   try:A.check(rows[-1],'control')
   except KeyError:pass
   else:raise AssertionError('parent missing split accepted')
  observations[label]={k:statistics.median(r[k] for r in rows) for k in ('wall_ms','wait_ms','prepare_ms','enqueue_loop_ms')}
 # Real parent cannot satisfy the new six-arm schema: fail closed, no invented subsegments.
 try:A.analyze(parent,manifest,[dict(label=l) for l in A.LABELS])
 except KeyError:pass
 else:raise AssertionError('old logs produced a split verdict')
 good=dict(publication_split=dict(arm='wait-split',diagnostic_only=True,calls=1,construction_ms=.1,submit_ms=.1,drain_ms=.1,repair_ms=.1,retire_host_ms=.1,waits=[dict(kind='readback',phase='decode-compute-drain',scope='normal',begin_ns=1,call_ns=2,end_ns=3)]))
 assert A.check(good,'wait-split')
 bad=[]
 for field,value in [('drain_ms',float('nan')),('calls',-1),('diagnostic_only',False),('waits',[])]:
  row=copy.deepcopy(good);row['publication_split'][field]=value;bad.append(row)
 row=copy.deepcopy(good);row['publication_split']['waits'][0]['end_ns']=0;bad.append(row)
 for row in bad:
  try:A.check(row,'wait-split')
  except ValueError:pass
  else:raise AssertionError('invalid split accepted')
 result=dict(passed=True,device_executed=False,real_parent_device_replay=True,exact_parent_requests=60,parent_timing_rows=count,parent_summary_ms_per_token=observations,parent_sha256=pins,missing_split_refused=True,invalid_cases_refused=len(bad),new_device_subsegments=None,maximum_measured_parent_prefill_operation_seconds=max_prefill/1000,per_operation_wait_seconds=600,wait_at_least_four_times_cold=600>=4*max_prefill/1000,all_cold_parent_rows_retained=True)
 assert result['wait_at_least_four_times_cold']
 (P/'evidence/analyzer-real-parent.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS 60 real parent requests, all native timing rows, missing-split/invalid stream refusals')
if __name__=='__main__':main()

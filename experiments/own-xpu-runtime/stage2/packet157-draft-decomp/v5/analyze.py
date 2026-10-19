"""Rank draft kernels using existing device events; host/device clocks stay separate."""
import json, math, statistics
from collections import defaultdict
from pathlib import Path
GROUPS=('input_norm_embedding_mix','attention_projections','attention','routed_experts',
        'shared_expert','final_norm','head_gemv','argmax_publication')
REQUIRED={'draft_issue'}
LEVERS={
 'input_norm_embedding_mix':'Batch host issue of the existing merge kernels; not packet126 early stateful draft or packet156 suffix scheduling.',
 'attention_projections':'Batch existing projection submissions; not packet101 HC retest or the closed wide-head geometry.',
 'attention':'Optimize the measured attention substage at unchanged arithmetic and context; not packet101 reused HC or packet122 cyclic context proxy.',
 'routed_experts':'Reduce submission overhead or stage exact routed data based on the measured split; not packet108 load8, packet122 HC remapping, or packet129 alternate expert precision.',
 'shared_expert':'Batch the existing shared expert path without new arithmetic; not packet122 HC fusion or packet129 expert-format substitution.',
 'final_norm':'Batch the unchanged final HC/norm operations; not packet101 already-selected HC.',
 'head_gemv':'Investigate a new exact head work partition at fixed 80,128 rows; not packet106/106b speculative suffix splitting, packet108 load8, or packet114 prefix retuning.',
 'argmax_publication':'Batch unchanged argmax/publication issue; not packet106 suffix split or packet146 history-derived proposals.'}
def demand(ok,reason):
 if not ok:raise ValueError(reason)
def stream(path,rank):
 demand(path.is_file(),f'missing rank{rank} timing stream')
 rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
 demand(rows,f'empty rank{rank} scope stream')
 demand(all(r.get('rank',rank)==rank for r in rows),'wrong rank stream')
 return rows
def request_split(root,request,timed=True):
 ts=request['token_timestamps'];demand(len(ts)==64 and all(math.isfinite(x) for x in ts) and all(b>a for a,b in zip(ts,ts[1:])),'64 monotone timestamps required')
 folder=Path(root)/request['prompt_id'];r0=stream(folder/'rank0/timings.jsonl',0);r1=stream(folder/'rank1/timings.jsonl',1)
 demand(any(r.get('p157_segment')=='remote_reply_wait' for r in r0),'missing rank0 wait stream')
 issues={}
 for r in r1:
  if 'p157_segment' not in r:continue
  demand(all(math.isfinite(r[k]) for k in ('ms','start','end')) and r['end']>=r['start'] and r['ms']>=0,'invalid host interval')
  demand(abs(1000*(r['end']-r['start'])-r['ms'])<.02,'host duration disagrees')
  if r['p157_segment']=='draft_issue':
   key=(r['sequence'],r['position']);demand(key not in issues,'duplicate draft issue');issues[key]=r
 demand(issues,'empty draft issue stream')
 events=[r for r in r1 if r.get('p157_device')]
 host=[r for r in r1 if r.get('p157_segment') in GROUPS]
 demand(timed or not (events or host),'instrumentation in control')
 if timed:demand(events and host,'empty draft device/group stream')
 selected={k:r for k,r in issues.items() if ts[0]<=r['start']<=r['end']<=ts[-1]}
 demand(selected,'no complete decode draft issues')
 cycles={k:dict(sequence=k[0],position=k[1],draft_issue_ms=r['ms'],groups={g:dict(device_ms=0.,host_issue_ms=0.,events=0,host_sites=0) for g in GROUPS}) for k,r in selected.items()}
 seen=set();intervals=defaultdict(list)
 for e in events:
  key=(e['sequence'],e['position']);demand(key in issues,'unmatched device draft')
  demand(e['group'] in GROUPS and type(e['start_ns']) is int and type(e['end_ns']) is int and 0<e['start_ns']<e['end_ns'],'invalid device interval')
  ek=(key,e['event']);demand(ek not in seen,'duplicate device event');seen.add(ek)
  if key in cycles:
   g=cycles[key]['groups'][e['group']];g['device_ms']+=(e['end_ns']-e['start_ns'])/1e6;g['events']+=1
   intervals[key].append((e['start_ns'],e['end_ns']))
 for r in host:
  key=(r['sequence'],r['position']);demand(key in issues,'unmatched host group')
  if key in cycles:
   cycles[key]['groups'][r['p157_segment']]['host_issue_ms']+=r['ms']
   cycles[key]['groups'][r['p157_segment']]['host_sites']+=1
 for k,c in cycles.items():
  if timed:
   demand(all(g['events']>0 and g['host_sites']>0 for g in c['groups'].values()),'incomplete per-draft device group census')
   ordered=sorted(intervals[k]);demand(all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:])),'overlapping in-order device events')
   c['device_span_ms']=(ordered[-1][1]-ordered[0][0])/1e6
  c['device_sum_ms']=sum(x['device_ms'] for x in c['groups'].values()) if timed else None
  c['host_group_sum_ms']=sum(x['host_issue_ms'] for x in c['groups'].values()) if timed else None
  c['host_unassigned_ms']=c['draft_issue_ms']-c['host_group_sum_ms'] if timed else None
  if timed:demand(c['host_unassigned_ms']>=-.02,'host groups exceed draft issue')
 # Means share the same denominator and therefore conserve sums. No medians added.
 rows=list(cycles.values());n=len(rows)
 mean=lambda key:statistics.mean(c[key] for c in rows)
 groups={g:{metric:statistics.mean(c['groups'][g][metric] for c in rows) for metric in ('device_ms','host_issue_ms','events')} for g in GROUPS} if timed else {}
 return dict(prompt_id=request['prompt_id'],timed=timed,drafts=n,groups=groups,cycles=rows,
             mean_decode_interval_ms=1000*(ts[-1]-ts[0])/63,
             draft_issue_ms=mean('draft_issue_ms'),device_sum_ms=mean('device_sum_ms') if timed else None,
             host_group_sum_ms=mean('host_group_sum_ms') if timed else None,
             host_unassigned_ms=mean('host_unassigned_ms') if timed else None)
def analyze(views,synthetic=False,smoke=False):
 # Synthetic report fixtures must still pass stream validation; label them afterward.
 demand([v['choice'] for v in views]==(['candidate'] if smoke else ['control','candidate','control','candidate','control']),'complete smoke or C/T/C/T/C required')
 rows=[]
 for v in views:
  demand(len(v['requests'])==12,'all twelve prompts required')
  req=[request_split(Path(v['output']),r,timed=v['choice']=='candidate') for r in v['requests']]
  rows.append(dict(index=v['index'],choice=v['choice'],requests=req,draft_issue_ms=statistics.mean(r['draft_issue_ms'] for r in req)))
 measured=[r for v in rows if v['choice']=='candidate' for r in v['requests']]
 groups=[dict(group=g,**{m:statistics.mean(r['groups'][g][m] for r in measured) for m in ('device_ms','host_issue_ms')}) for g in GROUPS]
 groups.sort(key=lambda r:r['device_ms'],reverse=True)
 overhead=[]
 if not smoke:
  for index in (1,3):
   for j,r in enumerate(rows[index]['requests']):
    before=rows[index-1]['requests'][j];after=rows[index+1]['requests'][j]
    base=(before['draft_issue_ms']+after['draft_issue_ms'])/2
    interval=(before['mean_decode_interval_ms']+after['mean_decode_interval_ms'])/2
    overhead.append(dict(view=index,prompt_id=r['prompt_id'],control_draft_issue_ms=base,timed_draft_issue_ms=r['draft_issue_ms'],added_host_ms=r['draft_issue_ms']-base,added_percent=100*(r['draft_issue_ms']/base-1),control_mean_decode_interval_ms=interval,timed_mean_decode_interval_ms=r['mean_decode_interval_ms'],added_decode_interval_ms=r['mean_decode_interval_ms']-interval,added_decode_interval_percent=100*(r['mean_decode_interval_ms']/interval-1)))
 return dict(schema='packet157.draft-device-decomposition.v1',device_evidence=not synthetic,
  speed_evidence_eligible=False,views=rows,ranked_groups=groups,
  top_two_levers=[dict(group=r['group'],next_lever=LEVERS[r['group']]) for r in groups[:2]],
  device_sum_ms=sum(r['device_ms'] for r in groups),host_group_sum_ms=sum(r['host_issue_ms'] for r in groups),
  draft_issue_ms=statistics.mean(r['draft_issue_ms'] for r in measured),
  host_unassigned_ms=statistics.mean(r['host_unassigned_ms'] for r in measured),overhead=overhead,
  limitation='Device execution and host submission overlap; never add those two clocks. Device sum and host group sum are each compared separately with draft_issue. Host unassigned includes existing drains, embedding reads, preparation and bookkeeping. All group means use matched complete decode drafts; no prefill/partial boundary rows. Diagnostic only; ranking is not a speed claim.')
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);a=ap.parse_args();p=json.loads((a.output/'run/bracket-inputs.json').read_text());print(json.dumps(analyze(p['views'],smoke=p['kind']=='smoke'),indent=2))

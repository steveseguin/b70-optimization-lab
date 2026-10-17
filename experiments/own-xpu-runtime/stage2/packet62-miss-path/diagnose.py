#!/usr/bin/env python3
"""Read the two completed packet61 screens; no weights, devices or live chain."""
import hashlib,importlib.util,json,statistics as st
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def median(v):return st.median(v) if v else None
method=P.parent/'packet57-attribution/timeline.py'
spec=importlib.util.spec_from_file_location('packet57_timeline',method);T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)
def main():
 result=dict(schema='packet62.miss-attribution.v1',device_executed=False,new_speed_claim=False,sources={str(method.relative_to(ROOT)):sha(method)},lanes={})
 for lane in ('A','B'):
  home=P.parent/'screen/v3/evidence'/('packet61-'+lane)
  cycles=[];capture=[];ordinary=[];gaps=[];redo_gap=[];correction=[];prepares=[];enqueues=[];waits=[];snapshots=[]
  files=sorted((home/'run').glob('*/receipt.json'));assert len(files)==13
  for file in files:
   result['sources'][str(file.relative_to(ROOT))]=sha(file);r=json.loads(file.read_text());cycles+=T.extract(r)
   trace=r['rank_trace']
   for row in trace:
    if row['rank']==0 and row['op']==1:
     (capture if row['speculative'] else ordinary).append(T.duration(row)-row['busy_ms'])
    if row['rank']==0 and row['op']==3:
     pos=row['position'];before=T.command(trace,1,1,pos-1);after=T.command(trace,0,1,pos,False)
     if before and after:
      gaps.append((row['rank_received']-before['rank_completed'])*1000)
      redo_gap.append((after['rank_received']-row['rank_completed'])*1000)
      correction.append((after['rank_received']-before['rank_completed'])*1000)
   redo_positions={row['position'] for row in trace if row['rank']==0 and row['op']==3 and row['speculative']}
   timing=file.parent/'rank0/timings.jsonl';result['sources'][str(timing.relative_to(ROOT))]=sha(timing)
   for line in timing.read_text().splitlines():
    row=json.loads(line)
    if not row['speculative'] and row['position'] in redo_positions:
     prepares.append(row['prepare_ms']);enqueues.append(row['enqueue_loop_ms']);waits.append(row['wait_ms'])
   snapfile=file.parent/'rank0/speculative-snapshot.json';result['sources'][str(snapfile.relative_to(ROOT))]=sha(snapfile);snapshots.append(json.loads(snapfile.read_text()))
  summary=T.summarize(cycles)
  # Snapshot counters are cumulative across requests in a loaded screen owner.
  totals=max(snapshots,key=lambda x:x['captures']);assert totals['captures'] and totals['redo_restores']
  summary.update(snapshot_envelope_minus_busy_ms=median(capture),ordinary_envelope_minus_busy_ms=median(ordinary),
   verification_complete_to_rollback_start_ms=median(gaps),restore_end_to_redo_start_ms=median(redo_gap),verification_complete_to_redo_start_ms=median(correction),
   corrected_half_prepare_ms=median(prepares),corrected_half_enqueue_ms=median(enqueues),corrected_half_wait_ms=median(waits),
   capture_bytes_per_half=totals['snapshot_payload_bytes']/totals['captures'],capture_submissions_per_half=totals['capture_submissions']/totals['captures'],
   restore_bytes_per_redo=totals['restored_bytes']/totals['redo_restores'],restore_submissions_per_redo=totals['restore_submissions']/totals['redo_restores'],
   recurrent_bytes_omitted_per_redo=totals['redo_omitted_bytes']/totals['redo_restores'])
  summary['ideal_remove_rollback_mean_ms_per_token']=st.mean(c['R_ms'] for c in cycles)
  result['lanes'][lane]=summary
 parent=P.parent/'packet61-spin-hcfusion'
 for name in ('strict_snapshot.hpp','rank.hpp','native_controller.hpp','memory-plan.json'):
  result['sources'][str((parent/name).relative_to(ROOT))]=sha(parent/name)
 memory=json.loads((parent/'memory-plan.json').read_text())['placements']['1-split23']['capacities']['4096']['ranks']
 result['arena_headroom_bytes']={str(row['rank']):30*1024**3-(row['target_modeled_allocations_bytes']+row['draft_total_bytes']+row['draft_duplicate_head_bytes']) for row in memory}
 result['caveats']=['All thirteen screen requests, not the twelve-class headline aggregate.','Capture proxy includes snapshot setup and other work outside half busy_ms; not device copy time.','Verification timestamp is rank1 command completion, after publication.','Host wait is not GPU idle.','Packet61 full record chain is neither read nor modified.']
 (P/'evidence/diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
 for lane,row in result['lanes'].items():print(lane,row['counts'],'rollback',row['miss']['R_ms']['median_ms'],'redo',row['miss']['A_ms']['median_ms'])
if __name__=='__main__':main()

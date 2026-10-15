"""Read retained packet44/45 receipts only; writes analysis outside build/."""
import collections,hashlib,json,statistics as st
from pathlib import Path
E=Path(__file__).resolve().parent;P=E.parents[1];S=P.parent
RUNS={'p44-record':S/'packet44-context/build/c4096b/WS128',
      'p45-dr0':P/'build/c4096-dr0-gpu/WS128','p45-dr1':P/'build/c4096-dr1-gpu/WS128',
      'p44-control-a':S/'packet44-context/build/c4096ctl15a/WS128',
      'p44-control-b':S/'packet44-context/build/c4096ctl15b/WS128'}
HASHES={}
def read(p):
 b=p.read_bytes();HASHES[str(p.relative_to(S))]=hashlib.sha256(b).hexdigest();return json.loads(b)
def lines(p):
 b=p.read_bytes();HASHES[str(p.relative_to(S))]=hashlib.sha256(b).hexdigest();return [json.loads(x) for x in b.splitlines()]
def stats(v):
 v=list(v)
 return dict(n=len(v),mean=st.mean(v),median=st.median(v),min=min(v),max=max(v)) if v else dict(n=0)
def span(row):return 1000*(row['rank_completed']-row['rank_received'])
def clip(row,left,right):return max(0,min(right,row['rank_completed'])-max(left,row['rank_received']))*1000
def analyze(root,classes):
 window=read(root/'window.json')
 if not window.get('passed'):return {'complete':False,'window_passed':False}
 summary=read(root/'run/summary.json');requests=[];group=collections.defaultdict(list);cycles=collections.defaultdict(list);ops=collections.defaultdict(list);drafts=[];handover=[];paired=[];capacity=[];guess_rows=[]
 for f in sorted((root/'run/repeat-1').glob('*/receipt.json')):
  r=read(f);assert r['passed'] and r['oracle_check']['passed'] and r['oracle_check']['tokens']==128 and len(r['tokens'])==128
  trace=r['rank_trace'];joined=[]
  for rank in (0,1):
   rows=[t for t in trace if t['rank']==rank and t['op']==1];timings=lines(f.parent/f'rank{rank}/timings.jsonl');assert len(rows)==len(timings)
   counts=[x['capacity_reprepares'] for x in timings]
   assert counts==sorted(counts), 'capacity counter must be cumulative within request'
   capacity.append(dict(prompt=f.parent.name,rank=rank,initial=counts[0],final=counts[-1],increments=sum(b-a for a,b in zip(counts,counts[1:])),events=sum(b>a for a,b in zip(counts,counts[1:]))))
   for t,x in zip(rows,timings):
    assert (t['position'],t['fixture'],t['speculative'])==(x['position'],x['fixture'],x['speculative'])
    z=dict(x,rank=rank,prompt=f.parent.name,command_ms=span(t),inner_busy_ms=t['busy_ms'],outside_inner_ms=span(t)-t['busy_ms'])
    z['forward_ms']=sum(x[k] for k in ('prepare_ms','enqueue_loop_ms','wait_ms'))
    z['inner_minus_forward_ms']=t['busy_ms']-z['forward_ms']
    if t['position']>=100:group[f'rank{rank}-'+('spec' if t['speculative'] else 'plain')].append(z)
    joined.append((t,z))
  positions=collections.defaultdict(list)
  for t,z in joined:
   if t['rank']==0 and t['position']>=100:positions[t['position']].append(z)
  for pos,zs in positions.items():
   if len(zs)==2:
    a,b=zs;assert a['speculative'] and not b['speculative']
    paired.append({k:a[k]-b[k] for k in ('forward_ms','wait_ms','outside_inner_ms','command_ms')})
  guess_rows.extend(g for g in r['guess_rows'] if g['position']>=100)
  for t in trace:
   if t['op'] not in (1,9) or t['position']>=100:ops[f"rank{t['rank']}-op{t['op']}"].append(span(t))
  ds=[d for d in r['draft_rows'] if d.get('hit') is not None and d['position']>=100];drafts+=ds
  # One interval is from this target completion to the following completion;
  # its hit/miss label is the guessed next rank0 half, as recorded by controller.
  for d in ds:
   if 'cycle_ms' not in d:continue
   left=d['target_completed_monotonic'];right=left+d['cycle_ms']/1000
   q={'cycle_ms':d['cycle_ms'],'position':d['position'],'prompt':f.parent.name}
   for rank in (0,1):
    for op in (1,2,3,9):q[f'rank{rank}_op{op}_envelope_ms']=sum(clip(t,left,right) for t in trace if t['rank']==rank and t['op']==op)
   cycles['hit' if d['hit'] else 'miss'].append(q)
  # Entire emitted-token window. Exclude partial command boundaries when
  # decomposing inside a HALF, rather than pretending event timings exist.
  stamps=r['generated_token_completion_timestamps'];left,right=stamps[0],stamps[99]
  byrank=[]
  for rank in (0,1):
   full=[(t,z) for t,z in joined if t['rank']==rank and t['rank_received']>=left and t['rank_completed']<=right]
   sums={k:sum(z[k] for t,z in full)/99 for k in ('forward_ms','inner_busy_ms','outside_inner_ms','inner_minus_forward_ms')}
   sums.update(rank=rank,full_halves=len(full),speculative_halves=sum(t['speculative'] for t,z in full),
      command_occupancy_ms_per_interval=sum(clip(t,left,right) for t in trace if t['rank']==rank)/99,
      half_draft_ms_per_interval=sum(clip(t,left,right) for t in trace if t['rank']==rank and t['op'] in (1,9))/99,
      draft_ms_per_interval=sum(clip(t,left,right) for t in trace if t['rank']==rank and t['op']==9)/99,
      rollback_ms_per_interval=sum(clip(t,left,right) for t in trace if t['rank']==rank and t['op']==3)/99,
      accept_ms_per_interval=sum(clip(t,left,right) for t in trace if t['rank']==rank and t['op']==2)/99)
   byrank.append(sums)
  for row in r['timing_rows']:
   half=next(t for t in trace if t['rank']==1 and t['op']==1 and t['fixture']==row['generated_index'])
   if half['position']>=100:
    handover.append(dict(row,target_completion_lag_ms=(row['completed_monotonic']-half['rank_completed'])*1000))
  requests.append(dict(prompt=f.parent.name,prompt_tokens=r['prompt_tokens'],rate100=99/(right-left),
    acceptance=r['acceptance'],stats=r['stats'],tokens_sha256=hashlib.sha256(json.dumps(r['tokens']).encode()).hexdigest(),
    guesses_sha256=hashlib.sha256(json.dumps(r['guess_sequence']).encode()).hexdigest(),
    decode_rank_metrics=r['decode_rank_metrics'],hit_miss_cycles=r['hit_miss_cycles'],ranks99=byrank))
 assert len(requests)==12
 class_rates={c:st.median(r['rate100'] for r in requests if classes[r['prompt']]==c) for c in set(classes.values())}
 fields=('prepare_ms','enqueue_loop_ms','wait_ms','forward_ms','command_ms','inner_busy_ms','outside_inner_ms','inner_minus_forward_ms','host_waits','launches_issued','capacity_reprepares','process_major_faults','process_minor_faults','process_involuntary_context_switches','process_voluntary_context_switches','thread_involuntary_context_switches','load_average_1m')
 return dict(complete=True,window={k:window.get(k) for k in ('boot_id','card','draft_rank','build_receipt_sha256','dispatch_sha256','passed','artifacts_sha256')},
  class_balanced_rate=st.median(class_rates.values()),class_rates=class_rates,requests=requests,
  reported_decode_busy_median=[st.median(r['decode_rank_metrics'][rank]['busy_ms_per_interval'] for r in requests) for rank in (0,1)],
  reported_cycle_mean_median={hit:st.median(r['hit_miss_cycles'][hit]['mean_ms'] for r in requests) for hit in ('hit','miss')},
  timing_groups={k:{f:stats(z[f] for z in rows if f in z) for f in fields} for k,rows in group.items()},
  timing_cancelled={k:sum(z.get('cancelled',False) for z in rows) for k,rows in group.items()},
  timing_affinity={k:sorted(set(tuple(z['cpu_affinity']) for z in rows)) for k,rows in group.items()},
  paired_miss_spec_minus_redo={k:stats(x[k] for x in paired) for k in paired[0]},capacity_counters=capacity,
  guess_rows={str(hit):stats(g['cycle_ms'] for g in guess_rows if g['hit']==hit) for hit in (False,True)},
  cycle_groups={k:{f:stats(x[f] for x in rows) for f in rows[0] if f not in ('position','prompt')} for k,rows in cycles.items()},
  operations={k:stats(v) for k,v in ops.items()},
  draft={k:stats(d[k] for d in drafts if k in d) for k in ('draft_wall_ms','draft_gpu_ms','rank0_idle_waiting_for_guess_ms','rank1_before_half_ms')},
  handover={k:stats(d[k] for d in handover if d.get(k) is not None) for k in ('rank0_to_rank1_handover_ms','rank1_to_rank0_start_minus_finish_ms','target_completion_lag_ms')})
def main():
 seed=read(RUNS['p45-dr0']/'run/summary.json');classes={r['prompt_id']:r['prompt_class'] for r in seed['rows']}
 result={}
 for name,root in RUNS.items():
  try:result[name]=analyze(root,classes)
  except (FileNotFoundError,json.JSONDecodeError):result[name]={'complete':False,'receipt_not_ready':True}
 reference={r['prompt']:r for r in result['p44-record']['requests']}
 for name,r in result.items():
  if r['complete']:
   r['same_tokens_as_p44_record']=all(q['tokens_sha256']==reference[q['prompt']]['tokens_sha256'] for q in r['requests'])
   r['same_guesses_as_p44_record']=all(q['guesses_sha256']==reference[q['prompt']]['guesses_sha256'] for q in r['requests'])
 (E/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
 (E/'input-hashes.json').write_text(json.dumps(HASHES,indent=2)+'\n')
 print(json.dumps({n:({'rate':r['class_balanced_rate'],'busy':r['reported_decode_busy_median'],'cycles':r['reported_cycle_mean_median']} if r['complete'] else r) for n,r in result.items()},indent=2))
if __name__=='__main__':main()

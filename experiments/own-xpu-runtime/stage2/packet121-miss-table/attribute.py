"""Read existing p104b receipts. No runtime import, model load or device access."""
from collections import defaultdict
import gzip,hashlib,json,resource,statistics as st
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];STAGE=P.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 source=STAGE/'screen/v4-lanes/evidence/p104b-B-grid-A-0-production/summary.json'
 data=json.loads(source.read_text());counts=defaultdict(list);gaps=defaultdict(list);detail=[];hit=[];miss=[]
 names={1:'half',2:'accept',3:'rollback',9:'draft'}
 for req in data['requests']:
  guesses={r['position']:r['hit'] for r in req['guess_rows']}
  stamps=req['generated_token_completion_timestamps']
  for i,(start,end) in enumerate(zip(stamps[:99],stamps[1:100])):
   position=req['prompt_tokens']+i;is_hit=guesses[position]
   (hit if is_hit else miss).append((end-start)*1000)
   if is_hit:continue
   row=dict(prompt_id=req['prompt_id'],position=position,interval_index=i,elapsed_ms=(end-start)*1000,commands=[],outside_commands=[])
   for rank in (0,1):
    trace=sorted([r for r in req['rank_trace'] if r['rank']==rank and r['rank_completed']>start and r['rank_received']<end],key=lambda r:r['rank_received'])
    last=start;outside=0
    for r in trace:
     a=max(start,r['rank_received']);b=min(end,r['rank_completed'])
     name=names.get(r['op'],str(r['op']))
     if r['op']==1:name='next_speculative_half' if r['speculative'] else ('corrected_half' if rank==0 else 'target_half')
     item=dict(rank=rank,command=name,op=r['op'],position=r['position'],speculative=r['speculative'],start_ms=(a-start)*1000,end_ms=(b-start)*1000,clipped_ms=(b-a)*1000,whole_command_ms=(r['rank_completed']-r['rank_received'])*1000)
     row['commands'].append(item);counts[(rank,name)].append(item)
     if a>last:row['outside_commands'].append(dict(rank=rank,start_ms=(last-start)*1000,end_ms=(a-start)*1000));outside+=a-last
     last=max(last,b)
    if end>last:row['outside_commands'].append(dict(rank=rank,start_ms=(last-start)*1000,end_ms=(end-start)*1000));outside+=end-last
    gaps[rank].append(outside*1000)
   detail.append(row)
 assert (len(hit),len(miss))==(936,252)
 archive=P/'evidence/miss-intervals.json.gz';archive.write_bytes(gzip.compress(json.dumps(detail,separators=(',',':')).encode(),mtime=0))
 dnr=sorted(ROOT.rglob('DO-NOT-REPEAT.md'))
 # Freeze the complete ledger inventory. A search hit is not treated as consent
 # to reopen an arm; BUDGET.md records the reviewed exclusions explicitly.
 report=dict(schema='packet121.miss-budget.v1',device_executed=False,source=str(source.relative_to(ROOT)),source_sha256=sha(source),definition='first 99 emission intervals per cold request, miss classified at starting emission',hit_intervals=len(hit),miss_intervals=len(miss),hit_mean_ms=st.mean(hit),miss_mean_ms=st.mean(miss),miss_time_fraction=sum(miss)/(sum(hit)+sum(miss)),commands=[dict(rank=r,command=n,events=len(v),mean_clipped_ms=st.mean(x['clipped_ms'] for x in v),mean_whole_command_ms=st.mean(x['whole_command_ms'] for x in v),per_miss_clipped_ms=sum(x['clipped_ms'] for x in v)/len(miss)) for (r,n),v in sorted(counts.items())],outside_commands_ms={str(r):st.mean(v) for r,v in gaps.items()},detail=dict(path=str(archive.relative_to(ROOT)),sha256=sha(archive)),sources={str(p.relative_to(ROOT)):sha(p) for p in [source,STAGE/'packet108-attribution/budget.json',STAGE/'packet88-miss-path/MISS.md',P/'attribute.py',*dnr]})
 (P/'evidence/budget.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ('hit_mean_ms','miss_mean_ms','miss_time_fraction','commands','outside_commands_ms')},indent=2))
if __name__=='__main__':main()

"""Fresh all-layer event accounting. Device clocks are never compared across ranks."""
import argparse,collections,hashlib,json,math,re,statistics
from pathlib import Path
P=Path(__file__).resolve().parent

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def summarize(rows,incident,profile):
 assert len(rows)==12 and len({r['prompt_id'] for r in rows})==12
 classes=collections.defaultdict(list)
 for r in rows:
  assert r['passed'] and r['exact_oracle'] and len(r['tokens'])==64
  assert r['decode_intervals']==63
  rate=63000/r['decode_wall_ms'];assert math.isfinite(rate) and rate>0
  classes[r['prompt_class']].append(rate)
 rate=statistics.median(statistics.median(v) for v in classes.values())
 return dict(passed=True,diagnostic=True,qualifying=False,submission_eligible=False,speed_evidence_eligible=False,
  realistic_final_gate=dict(passed=False,reason='12x64 attribution diagnostic'),arithmetic='iq3-p49-split32-v1',
  requested_max_new=64,request_count=12,requests=rows,incident64=incident,profile=profile,
  class_balanced_tps=rate,baseline_tps=[58.0,58.3],ratio_to_baseline=[rate/58.3,rate/58.0],
  overhead_bounded=rate/58.3>=0.9,overhead_gate='At least 90% of historical 58.3 tok/s; 63-interval diagnostic, not matched causal overhead',
  kv_dtype='BF16',prompt_kv_response_reuse=False)

def events(path):
 with path.open() as f:
  for line in f:
   r=json.loads(line)
   if r.get('schema') in ('packet128.event.v1','packet128.host.v1'):yield r

def generate(output):
 output=Path(output);w=read(output/'window.json');assert w['passed'] and w['lease_released']
 identity=read(output/'identity.json');assert identity['timing']=='attribution' and identity['lane']=='B'
 assert identity['binary_sha256']==sha(P/'build/device/own-rt-iq3')
 assert identity['selection_sha256']==sha(P/'selection.json')
 assert read(P/'selection.json')['choices']['head']=='head-split-compute', 'multiple queue gap accounting unsupported'
 proof=read(output/'run/report-inputs.json');assert proof['passed'];rows=proof['requests'];summary=summarize(rows,proof['incident64'],'tp2')
 cycles={};native={};pins={};by_request={}
 for r in rows:
  req=r['attribution_request'];by_request[req]=r
  file=output/'run'/r['prompt_id']/'native-result.json';n=read(file);pins[str(file)]=sha(file);native[req]=n
  assert n['tokens']==r['tokens']
  for g in n['guess_rows']:
   cycles[req,g['position']]=dict(hit=g['hit'],cycle_ms=g['cycle_ms'],gpu=[collections.defaultdict(float),collections.defaultdict(float)],wait=[collections.defaultdict(float),collections.defaultdict(float)],layers=[set(),set()],events=[[],[]])
 coverage=[set(),set()];seen_requests=[set(),set()];omitted=collections.Counter()
 for rank in (0,1):
  files=[output/'run'/r['prompt_id']/f'rank{rank}/sites.jsonl' for r in rows]
  for file in files:pins[str(file)]=sha(file)
  for e in (e for file in files for e in events(file)):
   req=e['request'];assert req in by_request
   assert e['rank']==rank
   seen_requests[rank].add(req)
   label=e['label'];pos=e['position'];is_head=label.startswith('head.') or label.startswith('transfer.head.') or label.startswith('wait.head.')
   # A prediction at p predicts the target result at p-1. The correction is
   # charged to that same prediction cycle, after the verified result arrives.
   key=(req,pos+1 if rank==1 or is_head else pos)
   if key not in cycles:omitted['boundary_or_no_guess']+=1;continue
   c=cycles[key];start,end=e['start_ns'],e['end_ns'];assert end>=start>0
   ms=(end-start)/1e6
   if e['schema']=='packet128.host.v1':c['wait'][rank][label]+=ms;continue
   cat=e['class']
   detail=re.sub(r'^blk\.\d+\.', '',label)
   if label.startswith('blk.'):cat=cat+'/'+detail
   if label.startswith('draft.'):cat='draft/'+cat+'/'+label.removeprefix('draft.')
   if label.startswith('blk.'):
    layer=int(label.split('.')[1]);assert (layer<24)==(rank==0);coverage[rank].add(layer);c['layers'][rank].add(layer)
   assert end>start or 'transfer' in label,('zero compute duration',label)
   c['gpu'][rank][cat]+=ms;c['events'][rank].append((start,end,label))
 assert seen_requests==[set(by_request),set(by_request)], "missing rank/request events"
 assert coverage==[set(range(24)),set(range(24,48))],('missing layer coverage',coverage)
 for hit in (True,False):
  for rank in (0,1):
   seen=set().union(*(c['layers'][rank] for c in cycles.values() if c['hit']==hit))
   assert seen==set(range(rank*24,(rank+1)*24)),('missing layer/outcome coverage',rank,hit,seen)
 # Gaps in each prediction cycle's covered same-queue events. No cross-card
 # timestamp subtraction. Separate spans for rank0 speculative/head/correction
 # can interleave other cycles: only consecutive event IDs would be safe.
 # Compute global consecutive gaps, then charge to the following event's cycle.
 for rank in (0,1):
  files=[output/'run'/r['prompt_id']/f'rank{rank}/sites.jsonl' for r in rows];previous={}
  for e in sorted((e for file in files for e in events(file) if e['schema']=='packet128.event.v1'),key=lambda e:(e['request'],e['event'])):
   req=e['request'];old=previous.get(req);previous[req]=e
   key=(req,e['position']+1 if rank==1 or e['label'].startswith(('head.','transfer.head.')) else e['position'])
   if old and key in cycles:
    if e['event']!=old['event']+1:
     omitted['nonconsecutive_event_gap']+=1;continue
    assert e['start_ns']>=old['end_ns'], 'overlapping queues: idle estimate invalid'
    cycles[key]['gpu'][rank]['queue_gap']+=(e['start_ns']-old['end_ns'])/1e6
 # Host command-idle spans (not assumed GPU-idle) show when each process
 # waited for the next command. Rank1 half readiness is visible here.
 for req,n in native.items():
  for rank in (0,1):
   trace=sorted((t for t in n['rank_trace'] if t['rank']==rank),key=lambda t:t['rank_received'])
   previous=None
   for t in trace:
    if previous is not None and t['fixture']>0:
     key=(req,t['position']+1 if rank==1 else t['position'])
     if key in cycles:
      gap=max(0,(t['rank_received']-previous)*1000)
      cycles[key]['wait'][rank]['host.outside_command']+=gap
    previous=t['rank_completed']
 # Host draft wait and explicit head waits retain their own clock domain.
 for req,n in native.items():
  for d in n['draft_rows']:
   key=req,d['position']
   if key in cycles:cycles[key]['wait'][0]['wait.draft_publication']+=d['rank0_idle_waiting_for_guess_ms']
 tables=[];levers=[]
 for hit in (True,False):
  subset=[c for c in cycles.values() if c['hit']==hit];assert subset, 'missing hit/miss population'
  for rank in (0,1):
   for field in ('gpu','wait'):
    classes=sorted(set().union(*(c[field][rank] for c in subset)))
    for cls in classes:
     vals=[c[field][rank].get(cls,0) for c in subset]
     tables.append(dict(rank=rank,outcome='hit' if hit else 'miss',kind=field,category=cls,cycles=len(subset),mean_ms=statistics.mean(vals),median_ms=statistics.median(vals)))
 # Semantic work assignments do not partition wall time: draft crosses cycle
 # boundaries. Bounds are ideal removable work, never a measured speed gain.
 total=len(cycles);wall=statistics.mean(c['cycle_ms'] for c in cycles.values())
 for rank in (0,1):
  cats=sorted(set().union(*(c['gpu'][rank] for c in cycles.values())))
  for cat in cats:
   unknown=any(x in cat for x in ('queue_gap','transfers','rollback','snapshot'))
   bounds=[];heuristic=[]
   for c in cycles.values():
    cost=c['gpu'][rank].get(cat,0)
    other=sum(v for k,v in c['gpu'][1-rank].items() if k!='queue_gap')
    own=sum(v for k,v in c['gpu'][rank].items() if k!='queue_gap')
    cap=cost
    if rank==0 and cat=='target_head_suffix':cap=min(cost,c['wait'][1].get('wait.head.suffix',0))
    bounds.append(cap)
    heuristic.append(max(0,.2*cost-max(0,other-own)))
   bound=statistics.mean(bounds);saved=None if unknown else .2*bound
   gain=100*(wall/(wall-saved)-1) if saved is not None and saved<wall else None
   levers.append(dict(rank=rank,category=cat,critical_path_ms_ideal_bound=bound,
    projected_saved_ms_upper=saved,projected_gain_percent_upper=gain,
    clears_half_percent_upper=gain is not None and gain>=.5,
    branch_overlap_heuristic_ms=None if unknown else statistics.mean(heuristic),
    exposure='unknown; measure recoverability' if unknown else 'ideal bound; overlap and causal exposure unproven'))
 levers.sort(key=lambda x:x['critical_path_ms_ideal_bound'],reverse=True)
 return dict(summary=summary,tables=tables,levers=levers,cycles=total,mean_cycle_ms=wall,coverage=[sorted(v) for v in coverage],receipt_sha256=pins,
  omitted=dict(omitted),ranking_usable=summary['overhead_bounded'],
  caveats=['Prediction-cycle accounting includes correction after verification; it is not the 99-interval headline metric.',
   'Queue gaps use only observed consecutive events on each rank; prefill, reset, no-guess and boundary work excluded.',
   'Host waits overlap device execution and are not added to GPU class sums.',
   'Rank1 waits for rank0 target/correction readiness before commands and for suffix best during merge; rank0 waits for draft publication and rank1 final hidden.',
   'Semantic prediction-cycle assignment is not an exact wall-time partition: draft launches cross controller cycle boundaries.',
   'Ranking uses ideal removable class work as a critical-path upper limit. The separate branch-total overlap heuristic is not a bound or a causal scheduler replay.',
   'The >=0.5% bar applies to an optimistic 20% compute-class reduction scenario; passing it does not prove that savings are exposed in-engine.',
   'Suffix opportunity is capped by measured rank1 suffix-wait duration; this wait also includes transfer, publication and scheduling.',
   'No measured gain or promotion. If throughput ratio is below 0.90, ranking is withheld because instrumentation is intrusive.'])

def markdown(r):
 s=r['summary'];lines=['# Packet128 fresh in-engine budget','',f"Diagnostic only. {s['class_balanced_tps']:.3f} tok/s; ratio to 58.0–58.3: {s['ratio_to_baseline'][0]:.3f}–{s['ratio_to_baseline'][1]:.3f}. Overhead gate: {'PASS' if s['overhead_bounded'] else 'FAIL; lever ranking withheld'}.",'',f"Both ranks cover all 48 layers. {r['cycles']} prediction cycles; mean {r['mean_cycle_ms']:.4f} ms.",'','| Rank | Outcome | Clock/type | Class | Mean ms/cycle | Median ms/cycle | N |','|---|---|---|---|---:|---:|---:|']
 for t in r['tables']:lines.append(f"| {t['rank']} | {t['outcome']} | {t['kind']} | {t['category']} | {t['mean_ms']:.5f} | {t['median_ms']:.5f} | {t['cycles']} |")
 lines+=['','Rank 0 waits for the draft and rank 1 final hidden. Rank 1 waits for rank 0 target/correction readiness and the suffix winner. Host waits overlap the GPU rows above. Queue gaps include host submission, reporting and dependencies; they are not all recoverable.','', 'Levers are ranked by ideal critical-path work limits. The 20% class-time reduction scenario is optimistic: overlap is unproven. A >=0.5% upper projection only identifies work worth testing. Transfers, rollback and queue gaps retain unknown recoverability.','']
 if r['ranking_usable']:
  lines+=['| Rank/class | Ideal critical-path limit (ms) | Optimistic saved ms | Gain upper projection | >=0.5% upper |','|---|---:|---:|---:|---|']
  for x in r['levers']:
   saved='unknown' if x['projected_saved_ms_upper'] is None else f"{x['projected_saved_ms_upper']:.5f}"
   gain='unknown' if x['projected_gain_percent_upper'] is None else f"{x['projected_gain_percent_upper']:.3f}%"
   lines.append(f"| {x['rank']}/{x['category']} | {x['critical_path_ms_ideal_bound']:.5f} | {saved} | {gain} | {x['clears_half_percent_upper']} |")
 lines+=['']+['- '+x for x in r['caveats']]
 return '\n'.join(lines)+'\n'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=P/'evidence/device-B');a=ap.parse_args();r=generate(a.output)
 (P/'evidence/budget.json').write_text(json.dumps(r,indent=2)+'\n');(P/'BUDGET.md').write_text(markdown(r))
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()

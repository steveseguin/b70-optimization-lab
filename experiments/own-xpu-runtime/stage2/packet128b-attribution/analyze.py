"""Sampled in-engine attribution; queue clocks never cross ranks or routes."""
import argparse,collections,hashlib,json,math,re,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
SAMPLE_FIRST,SAMPLE_LAST=9,16

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def summarize(rows,incident,profile):
 assert len(rows)==12 and len({r['prompt_id'] for r in rows})==12
 assert incident['passed']
 classes=collections.defaultdict(list)
 for r in rows:
  assert r['passed'] and r['exact_oracle'] and len(r['tokens'])==64
  assert r['decode_intervals']==63 and r['decode_wall_ms']>0
  rate=63000/r['decode_wall_ms'];assert math.isfinite(rate) and rate>0
  classes[r['prompt_class']].append(rate)
 rate=statistics.median(statistics.median(v) for v in classes.values())
 return dict(passed=True,diagnostic=True,qualifying=False,submission_eligible=False,speed_evidence_eligible=False,
  realistic_final_gate=dict(passed=False,reason='12x64 sampled attribution diagnostic'),arithmetic='iq3-p49-split32-v1',
  requested_max_new=64,request_count=12,requests=rows,incident64=incident,profile=profile,
  class_balanced_tps=rate,baseline_tps=[58.0,58.3],ratio_to_baseline=[rate/58.3,rate/58.0],
  overhead_bounded=rate/58.0>=0.90,overhead_gate='At least 90% of historical 58.0 tok/s; response-length mismatch, not paired causal overhead',
  sample_generated_tokens=[9,16],kv_dtype='BF16',prompt_kv_response_reuse=False)

def events(path):
 with path.open() as f:
  for line in f:
   r=json.loads(line)
   if r.get('schema') in ('packet128b.event.v1','packet128b.host.v1'):yield r

def union_ns(intervals):
 """Busy time within one queue/clock; handles nested and overlapping events."""
 total=0;end=None
 for a,b in sorted(intervals):
  assert b>=a>0
  total+=max(0,b-max(a,end if end is not None else a));end=max(b,end or b)
 return total

def cycle_key(e):
 head=e['label'].startswith(('head.','transfer.head.','wait.head.'))
 return e['request'],e['position']+(1 if e['rank']==1 or head else 0)

def queue_accounting(es):
 """Separate submission routes; physical auto-copy engine is not exposed by SYCL.

 Never mix copy profiling with compute: retained copies can have placeholder
 zero-duration timestamps in a different clock domain. Compute idle is only
 the gaps in a compute-interval union, within an uninterrupted sampled fixture.
 Missing event IDs break the gap proof; they are never called idle.
 """
 grouped=collections.defaultdict(list);unknown=collections.Counter()
 for e in es:
  assert e['queue'] and e['queue_kind'] in ('compute','copy','other')
  assert e['end_ns']>=e['start_ns']>0
  if e['end_ns']==e['start_ns']:
   assert e['queue_kind']!='compute',('zero compute duration',e['label'])
   unknown[e['queue']]+=1;continue
  grouped[e['queue']].append(e)
 costs=[];gaps=[];omitted=0
 known={e['event'] for e in es}
 assert len(known)==len(es),'duplicate event ID'
 for queue,rows in sorted(grouped.items()):
  kinds={e['queue_kind'] for e in rows};assert len(kinds)==1
  costs.append(dict(queue=queue,kind=next(iter(kinds)),events=len(rows),
   busy_ms_union=union_ns((e['start_ns'],e['end_ns']) for e in rows)/1e6,
   summed_event_ms=sum(e['end_ns']-e['start_ns'] for e in rows)/1e6))
  if kinds!={'compute'}:continue
  previous=None;frontier=0
  for e in sorted(rows,key=lambda e:e['event']):
   if previous:
    uninterrupted=(e['fixture']==previous['fixture'] and e['event']>previous['event'] and
       e['event']-previous['event']<=len(known) and
       all(i in known for i in range(previous['event']+1,e['event'])))
    if uninterrupted:
     gaps.append((cycle_key(e),max(0,e['start_ns']-frontier)/1e6,queue))
    else:omitted+=1;frontier=0
   frontier=max(frontier,e['end_ns']);previous=e
 return costs,gaps,dict(unknown),omitted

def generate(output):
 output=Path(output);w=read(output/'window.json');assert w['passed'] and w['lease_released']
 identity=read(output/'identity.json');assert identity['timing']=='attribution' and identity['lane']=='B'
 assert identity['binary_sha256']==sha(P/'build/device/own-rt-iq3')
 assert identity['selection_sha256']==sha(P/'selection.json')
 proof=read(output/'run/report-inputs.json');assert proof['passed']
 rows=proof['requests'];summary=summarize(rows,proof['incident64'],'tp2')
 cycles={};pins={};native={};by_request={};all_cycles=0
 for r in rows:
  req=r['attribution_request'];assert req not in by_request;by_request[req]=r
  file=output/'run'/r['prompt_id']/'native-result.json';n=read(file);pins[str(file)]=sha(file);native[req]=n
  assert n['tokens']==r['tokens']
  origins={t['position']-t['fixture'] for t in n['rank_trace'] if t['op']==1 and t['fixture']>0}
  assert len(origins)==1,('generation origin',origins)
  origin=origins.pop();all_cycles+=len(n['guess_rows'])
  # r0 speculation/correction uses fixture k; rank1 verification/head/draft
  # uses fixture k-1. Both must lie in 9..16: complete cycles are 10..16.
  for g in n['guess_rows']:
   if not SAMPLE_FIRST<g['position']-origin<=SAMPLE_LAST:continue
   key=req,g['position'];assert key not in cycles
   cycles[key]=dict(hit=g['hit'],cycle_ms=g['cycle_ms'],gpu=[collections.defaultdict(float),collections.defaultdict(float)],
    wait=[collections.defaultdict(float),collections.defaultdict(float)],layers=[set(),set()])
  assert sum(k[0]==req for k in cycles)==SAMPLE_LAST-SAMPLE_FIRST,'missing sampled cycles'
 coverage=[set(),set()];omitted=collections.Counter();queues=[];seen=[set(),set()]
 for rank in (0,1):
  for r in rows:
   file=output/'run'/r['prompt_id']/f'rank{rank}/sites.jsonl';pins[str(file)]=sha(file);device=[]
   for e in events(file):
    req=e['request'];assert req==r['attribution_request'] and e['rank']==rank
    assert SAMPLE_FIRST<=e['fixture']<=SAMPLE_LAST,'unsampled event recorded'
    seen[rank].add(req);key=cycle_key(e)
    start,end=e['start_ns'],e['end_ns'];assert end>=start>0
    if e['schema']=='packet128b.event.v1':device.append(e)
    if key not in cycles:omitted['sample_boundary_event']+=1;continue
    c=cycles[key];label=e['label'];ms=(end-start)/1e6
    if e['schema']=='packet128b.host.v1':c['wait'][rank][label]+=ms;continue
    cat=e['class']
    if label.startswith('blk.'):
     layer=int(label.split('.')[1]);assert layer in range(rank*24,(rank+1)*24)
     coverage[rank].add(layer);c['layers'][rank].add(layer);cat+='/'+re.sub(r'^blk\.\d+\.','',label)
    if label.startswith('draft.'):cat='draft/'+cat+'/'+label.removeprefix('draft.')
    # Zero-duration copies are unknown, not free work and not lever candidates.
    if end==start:omitted['unresolved_copy_duration']+=1;continue
    c['gpu'][rank][(e['queue'],cat)]+=ms
   costs,gaps,unknown,missing=queue_accounting(device)
   queues.append(dict(rank=rank,request=r['attribution_request'],routes=costs,unknown_duration_events=unknown))
   omitted['unobserved_gap']+=missing
   for key,ms,queue in gaps:
    if key in cycles:cycles[key]['gpu'][rank][(queue,'compute_idle_observed')]+=ms
 assert seen==[set(by_request),set(by_request)],'missing rank/request events'
 assert coverage==[set(range(24)),set(range(24,48))],('missing layer coverage',coverage)
 for key,c in cycles.items():
  for rank in (0,1):assert c['layers'][rank]==set(range(rank*24,(rank+1)*24)),('missing layer in sampled cycle',key,rank)
 for hit in (True,False):assert any(c['hit']==hit for c in cycles.values()),'missing hit/miss population'
 for req,n in native.items():
  for d in n['draft_rows']:
   key=req,d['position']
   if key in cycles:cycles[key]['wait'][0]['wait.draft_publication']+=d['rank0_idle_waiting_for_guess_ms']
 tables=[]
 for hit in (True,False):
  subset=[c for c in cycles.values() if c['hit']==hit]
  for rank in (0,1):
   for field in ('gpu','wait'):
    for cls in sorted(set().union(*(c[field][rank] for c in subset))):
     vals=[c[field][rank].get(cls,0) for c in subset]
     queue,category=cls if field=='gpu' else ('host',cls)
     tables.append(dict(rank=rank,outcome='hit' if hit else 'miss',kind=field,queue=queue,category=category,
      cycles=len(subset),mean_ms=statistics.mean(vals),median_ms=statistics.median(vals)))
 wall=statistics.mean(c['cycle_ms'] for c in cycles.values());levers=[]
 # Gate before constructing any ranking, including the machine-readable output.
 if summary['overhead_bounded']:
  for rank in (0,1):
   for queue,cat in sorted(set().union(*(c['gpu'][rank] for c in cycles.values()))):
    unknown=queue!='compute' or any(x in cat for x in ('idle','transfers','rollback','snapshot'))
    vals=[]
    for c in cycles.values():
     cost=c['gpu'][rank].get((queue,cat),0)
     if rank==0 and cat=='target_head_suffix':cost=min(cost,c['wait'][1].get('wait.head.suffix',0))
     vals.append(cost)
    bound=statistics.mean(vals);saved=None if unknown else .2*bound
    gain=100*(wall/(wall-saved)-1) if saved is not None and saved<wall else None
    levers.append(dict(rank=rank,queue=queue,category=cat,critical_path_ms_ideal_bound=bound,
     projected_saved_ms_upper=saved,projected_gain_percent_upper=gain,clears_half_percent_upper=gain is not None and gain>=.5))
  levers.sort(key=lambda x:x['critical_path_ms_ideal_bound'],reverse=True)
 return dict(summary=summary,tables=tables,levers=levers,cycles=len(cycles),all_prediction_cycles=all_cycles,
  mean_cycle_ms=wall,coverage=[sorted(x) for x in coverage],queues=queues,receipt_sha256=pins,omitted=dict(omitted),
  ranking_usable=summary['overhead_bounded'],caveats=[
   'Only complete sampled prediction cycles (fixtures 10..16) enter means; unobserved cycles are not zero cost.',
   'Compute, automatic-copy and explicit BCS-copy routes have separate clock domains. Automatic-copy physical engine identity is unavailable; no BCS hardware identity is inferred.',
   'Queue busy time uses interval unions. Compute idle uses only observed uninterrupted compute intervals; gaps with missing IDs or at sample boundaries are excluded.',
   'Zero-duration copy timestamps are unresolved, never measured zero cost. Copy clocks never enter compute idle.',
   'Host waits overlap device execution. Semantic prediction-cycle assignments are not a wall-time partition.',
   'Critical-path limits and 20% scenarios are optimistic projections within the sample, not measured gains or whole-suite rankings.',
   'The 63-interval throughput is a diagnostic historical comparison; >=0.90 against 58.0 is required before any ranking.'])

def markdown(r):
 s=r['summary'];lines=['# Packet128b sampled in-engine budget','',f"Diagnostic only. {s['class_balanced_tps']:.3f} tok/s; ratios to 58.0 / 58.3: {s['ratio_to_baseline'][1]:.3f} / {s['ratio_to_baseline'][0]:.3f}. Overhead gate: {'PASS' if s['overhead_bounded'] else 'FAIL; ranking withheld'}.",'',f"All 48 layers, both ranks; {r['cycles']} complete sampled cycles of {r['all_prediction_cycles']} total. Sample mean cycle: {r['mean_cycle_ms']:.4f} ms.",'','| Rank | Outcome | Queue/clock | Class | Mean ms/cycle | Median | N |','|---|---|---|---|---:|---:|---:|']
 for t in r['tables']:lines.append(f"| {t['rank']} | {t['outcome']} | {t['queue']} | {t['category']} | {t['mean_ms']:.5f} | {t['median_ms']:.5f} | {t['cycles']} |")
 if r['ranking_usable']:
  lines+=['','| Rank/queue/class | Ideal limit ms | Optimistic gain % |','|---|---:|---:|']
  for x in r['levers']:
   gain='unknown' if x['projected_gain_percent_upper'] is None else f"{x['projected_gain_percent_upper']:.3f}"
   lines.append(f"| {x['rank']}/{x['queue']}/{x['category']} | {x['critical_path_ms_ideal_bound']:.5f} | {gain} |")
 return '\n'.join(lines+['']+['- '+x for x in r['caveats']])+'\n'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=P/'evidence/device-B');a=ap.parse_args();r=generate(a.output)
 (P/'evidence/budget.json').write_text(json.dumps(r,indent=2)+'\n');(P/'BUDGET.md').write_text(markdown(r))
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()

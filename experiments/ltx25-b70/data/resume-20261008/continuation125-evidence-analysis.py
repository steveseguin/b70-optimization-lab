#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU-only frozen file timeline. No runtime imports, endpoints or device access."""
import ast,hashlib,json,os
from pathlib import Path
from statistics import median,mean
from datetime import datetime,timezone
os.environ['OMP_NUM_THREADS']='2'
ROOT=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
HERE=Path(__file__).parent
SOURCES={}
def read(p,lines=False):
 b=p.read_bytes();SOURCES[str(p)]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
 return [json.loads(x) for x in b.splitlines() if x.strip()] if lines else json.loads(b)
def stats(xs):
 xs=sorted(x for x in xs if x is not None)
 return {'n':len(xs),'median':median(xs),'mean':mean(xs),'min':min(xs),'max':max(xs)} if xs else None
def delta(t,a,b):return (t[b]-t[a])/1e9 if t.get(a) is not None and t.get(b) is not None else None
def collect(session):
 client=Path('/home/steve/ltx-stream')/session
 manifest=read(client/'manifest.jsonl',True)
 first=manifest[0];ident=first['server_identity_sha256'];packet=first['run_name'].split('-')[0][6:]
 candidates=list(ROOT.glob('encoder-server-continuation-stream-'+packet+'*'))
 matched=[]
 for p in candidates:
  q=p/'receipts'/('receipt-'+first['run_name']+'.json')
  if q.is_file() and json.loads(q.read_bytes()).get('server_identity_sha256')==ident:matched.append(p)
 assert len(matched)==1,(session,matched)
 root=matched[0];rs={};ds={};ps={}
 # Fixed complete prefix from client manifest snapshot. Later running appends excluded.
 for line in manifest:
  i=line['stream_seq'];name=line['run_name']
  for table,kind in ((rs,'receipt'),(ds,'decode'),(ps,'preview')):
   p=root/'receipts'/(kind+'-'+name+'.json')
   if p.is_file():table[i]=read(p)
 rows=[]
 for i in sorted(rs):
  if i<10 or i-1 not in rs or i+1 not in rs or any(i not in x or i-1 not in x for x in (ds,ps)):continue
  r=rs[i];d=ds[i];v=ps[i];prev=ds[i-1];pv=ps[i-1];n=rs[i+1];base=r['timing_ns']['submit']
  rel=lambda x:None if x is None else round((x-base)/1e9,9)
  t=r['timing_ns'];dt=d['timing_ns'];pt=prev['timing_ns'];marks=n['turnaround']['marks_ns']
  snaps={s['label']:s for s in r['snapshots']}
  sources=r.get('conditioning_sources') or {};a=sources.get('A',{});b=sources.get('B',{})
  prev_a=(a.get('precompute') or {}).get('timing_ns',{})
  row={'seq':i,'origin_ns':base,'prompt_changed':r['prompt_changed'],'reuse_text':r['reuse_text'],
   'period_to_next':delta({'a':base,'b':n['timing_ns']['submit']},'a','b'),
   'period_from_previous':(base-rs[i-1]['timing_ns']['submit'])/1e9,
   'submit_to_sampler_a':delta(t,'submit','sampler_a_start'),
   'request_snapshot_wrapper':delta(t,'request_snapshot_start','request_snapshot_done'),
   'request_snapshot_inner':delta(snaps['request-before'],'start_ns','end_ns'),
   'first_node_to_condition_a':r['timing_s']['submit_split'].get('first_node_to_condition_a'),
   'condition_a_lookup':delta(t,'condition_a_start','condition_a_lookup_done'),
   'condition_a_tail':delta(t,'condition_a_lookup_done','condition_a_done'),
   'stage_a_consume':r['timing_s']['submit_split'].get('stage_a_consume'),
   'a_source':a.get('source'),'b_source':b.get('source'),'a_wait':a.get('waited_s'),
   'a_ready_before_lookup':(t['condition_a_start']-prev_a['done'])/1e9 if prev_a.get('done') else None,
   'own_a_precompute':delta(dt,'precompute_a_start','precompute_a_done'),
   'own_a_native_encode':(d.get('precompute',{}).get('A',{}).get('record') or {}).get('encode_s'),
   'own_b_precompute':delta(dt,'precompute_b_start','precompute_b_done'),
   'own_go_wait':d['schedule'].get('go_wait_s'),
   'own_fifo':delta(dt,'decode_queued','decode_start'),
   'sampler_a':delta(t,'sampler_a_start','stage_a_done'),'sampler_b':delta(t,'sampler_b_start','stage_b_done'),
   'upsample_bprep':delta(t,'stage_a_done','sampler_b_start'),
   'receipt_tail':delta(t,'anchor_ready','receipt_staged'),
   'next_commit_to_first_served':delta(marks,'commit_written','first_served'),
   'next_staged_to_submit':delta(marks,'receipt_staged','submit'),
   'prev_preview_before_receipt':(t['receipt_staged']-pv['timing_ns']['preview_written'])/1e9,
   'prev_display_before_request':(t['request_snapshot_start']-pt['display_done'])/1e9,
   'status_calls':r['authority_checks']['status_route_calls'],'status_seconds':r['authority_checks']['status_route_s'],
   'timeline':{'prompt':{k:rel(x) for k,x in t.items()},'snapshots':{k:[rel(x['start_ns']),rel(x['end_ns'])] for k,x in snaps.items()},
    'previous_decode':{k:rel(x) for k,x in pt.items()},'previous_preview':{k:rel(x) for k,x in pv['timing_ns'].items()},
    'own_decode':{k:rel(x) for k,x in dt.items()},'own_preview':{k:rel(x) for k,x in v['timing_ns'].items()},
    'receipt_to_next':{k:rel(x) for k,x in marks.items()}}}
  rows.append(row)
 last=None; comparisons=[]
 for row in rows:
  when=row['origin_ns']/1e9+row['timeline']['receipt_to_next']['executor_exit']
  observed=row['next_commit_to_first_served']>.15
  if last is None:
   if observed:last=when
   continue
  predicted=when-last>10.0
  if predicted:last=when
  comparisons.append({'seq':row['seq'],'predicted_post_prompt_housekeeping':predicted,'observed_handoff_over_150ms':observed,'match':predicted==observed})
 metrics=[k for k,v in rows[0].items() if isinstance(v,(float,int)) and not isinstance(v,bool) and k not in ('seq','origin_ns')]
 summary=lambda xs:{k:stats([r[k] for r in xs]) for k in metrics}
 return {'root':str(root),'identity':ident,'frames':first['frames'],'manifest_rows':len(manifest),'receipt_rows':len(rs),
  'analysis_range':[rows[0]['seq'],rows[-1]['seq']],'analysis_rows':len(rows),'summary':summary(rows),
  'parity':{str(k):summary([r for r in rows if r['seq']%2==k]) for k in range(2)},
  'modulo4':{str(k):summary([r for r in rows if r['seq']%4==k]) for k in range(4)},
  'conditioning_sources':{s:sum(r['a_source']==s for r in rows) for s in {r['a_source'] for r in rows}},
  'all_cone_equal':all(d['anchor_decode']['equal'] is True for d in ds.values()),
  'ten_second_model':{'method':'Seed first observed handoff over150ms, then apply strict elapsed>10s to executor_exit proxy; not GC instrumentation.','matches':sum(v['match'] for v in comparisons),'n':len(comparisons),'mismatches':[v['seq'] for v in comparisons if not v['match']]},
  'rows':[{k:v for k,v in row.items() if k!='timeline' or row['seq'] in (10,11,12,13)} for row in rows]}
if __name__=='__main__':
 sessions=['s121-live01','s121-live02','s123b-live01','s123b-live02','s123b-legacy-live01','s118b-live01','s118b-live02','s118b-live03','s120-live01']
 runs={s:collect(s) for s in sessions if (Path('/home/steve/ltx-stream')/s/'manifest.jsonl').is_file()}
 for packet in ['118b','120','121','123b','124']:
  for relative in ['source/main.py','source/comfy/model_management.py']:
   p=ROOT/('prepared-continuation-stream-'+packet)/relative;b=p.read_bytes();SOURCES[str(p)]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
 missing=[s for s in sessions if s not in runs]
 result={'observed_utc':datetime.now(timezone.utc).isoformat(),'missing_client_manifests':missing,'schema':'ltx.continuation125.cpu-timeline.v1','definition':'Period_to_next belongs to source seq; period_from_previous belongs to destination seq. No medians are subtracted to claim durations.','runs':runs,'sources':SOURCES}
 ast.parse(Path(__file__).read_text())
 checks=[('analysis_script_ast',True),
         ('captured_sessions_accounted_for',len(runs)+len(missing)==len(sessions)),
         ('interior_row_counts_match',all(r['analysis_rows']==len(r['rows']) for r in runs.values())),
         ('all_A_sources_precomputed',all(r['conditioning_sources']=={'precomputed':r['analysis_rows']} for r in runs.values())),
         ('all_saved_cone_equal',all(r['all_cone_equal'] for r in runs.values())),
         ('four_detailed_timelines_per_session',all(sum('timeline' in row for row in r['rows'])==4 for r in runs.values()))]
 assert all(passed for name,passed in checks),checks
 result['structural_verification']={'passed':6,'failed':0,'scope':'CPU analysis artifact checks; not native correctness or packet suite tests.',
                                    'checks':[{'name':name,'passed':passed} for name,passed in checks]}
 (HERE/'continuation125-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
 for s,r in runs.items():
  print(s,'rows',r['analysis_rows'],'range',r['analysis_range'],'A_sources',r['conditioning_sources'])
  for parity,t in r['parity'].items():
   print(' parity',parity,{k:round(t[k]['median'],4) if t[k] else None for k in ['period_to_next','period_from_previous','submit_to_sampler_a','request_snapshot_wrapper','request_snapshot_inner','own_a_precompute','own_a_native_encode','own_fifo','next_commit_to_first_served','prev_preview_before_receipt','status_seconds']})

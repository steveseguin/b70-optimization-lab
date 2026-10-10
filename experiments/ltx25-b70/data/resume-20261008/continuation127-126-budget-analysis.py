#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Read-only CPU receipt budget; output only beside this new analysis script."""
import importlib.util,json,hashlib
from pathlib import Path
from statistics import median,mean
from datetime import datetime,timezone
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('previous',HERE/'continuation125-evidence-analysis.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
S=['s126-live01']
runs={};missing=[]
for session in S:
 if not (Path('/home/steve/ltx-stream')/session/'manifest.jsonl').exists():missing.append(session);continue
 manifest=old.read(Path('/home/steve/ltx-stream')/session/'manifest.jsonl',True)
 if len(manifest)<12:
  missing.append(session+' (fewer than12 complete client rows)');continue
 c=old.collect(session);root=Path(c['root']);rows=[];events={}
 for row in c['rows']:
  i=row['seq'];packet=session.split('-')[0][1:];packet='123b' if packet=='123b' else packet
  name=f'stream{packet}-s{i:08d}'
  r=old.read(root/'receipts'/('receipt-'+name+'.json'));d=old.read(root/'receipts'/('decode-'+name+'.json'));v=old.read(root/'receipts'/('preview-'+name+'.json'))
  n=old.read(root/'receipts'/('receipt-'+f'stream{packet}-s{i+1:08d}'+'.json'))
  t=r['timing_ns'];dt=d['timing_ns'];m=n['turnaround']['marks_ns'];D=old.delta
  row.update({'cone_on_chain':D(t,'stage_b_done','video_done'),'anchor_handoff':D(t,'video_done','anchor_ready'),
   'display':D(dt,'display_start','display_done'),'decode_tail':D(dt,'display_done','record_staged'),'audio_after_display':D(dt,'display_done','audio_done'),
   'preview_encode':D(v['timing_ns'],'write_start','preview_written'),
   'staged_to_commit':D(m,'receipt_staged','commit'),'commit_write':D(m,'commit','commit_written'),
   'commit_to_executor_exit':D(m,'commit_written','executor_exit'),
   'executor_exit_to_served':D(m,'executor_exit','first_served'),'served_to_submit':D(m,'first_served','submit'),
   'snapshot_sum':sum(s['seconds'] for s in r['snapshots']),
   'snapshot_parts':{part:sum(s['parts_s'].get(part,0) for s in r['snapshots']) for part in ['state','facts','residence','memory']},
   'snapshot_labels':{s['label']:{'seconds':s['seconds'],'parts_s':s['parts_s']} for s in r['snapshots']},
   'options':r['server_options'],'maintenance_overlap':[]})
  for e in n.get('maintenance',{}).get('events',[]):events[e['sequence']]=e
  for e in n.get('maintenance',{}).get('events',[]):
   z=e['timing_ns'];start=z['gc_start'];end=z['cache_done']
   if start<m['submit'] and end>m['commit_written']:row['maintenance_overlap'].append(e)
  chain=['submit_to_sampler_a','sampler_a','upsample_bprep','sampler_b','cone_on_chain','anchor_handoff','receipt_tail','staged_to_commit','commit_write','next_commit_to_first_served','served_to_submit']
  row['chain_sum']=sum(row[k] for k in chain)
  assert abs(row['chain_sum']-row['period_to_next'])<1e-6
  if 'timeline' in row:row['maintenance_record']=n.get('maintenance')
  rows.append(row)
 numeric=[k for k,v in rows[0].items() if isinstance(v,(int,float)) and not isinstance(v,bool) and k not in ['seq','origin_ns']]
 def summary(rs):return {k:{'median':median([r[k] for r in rs]),'mean':mean([r[k] for r in rs])} for k in numeric if all(r.get(k) is not None for r in rs)}
 fixed=[r for r in rows if 10<=r['seq']<50]
 c.update({'rows':rows,'chain_partition':chain,'all_summary':summary(rows),'fixed40':summary(fixed) if len(fixed)==40 else None,
  'fixed40_parity':{str(p):summary([r for r in fixed if r['seq']%2==p]) for p in [0,1]} if len(fixed)==40 else None,
  'all_parity':{str(p):summary([r for r in rows if r['seq']%2==p]) for p in [0,1]},'maintenance_events':list(events.values())})
 runs[session]=c
for name in ['ltx_graph_capture.py','candidate_safety.py','snapshot_fingerprint.py','stream_contract.py','stream_decoder_graph.py','integration.py']:
 p=old.ROOT/'prepared-continuation-stream-126'/'source'/'scripts'/name
 if p.is_file():
  b=p.read_bytes();old.SOURCES[str(p)]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
out={'schema':'ltx.continuation127.cpu-budget-126-addendum.v1','observed_utc':datetime.now(timezone.utc).isoformat(),'runs':runs,'missing':missing,'sources':old.SOURCES,'checks':{'exclusive_chain_partitions_close':True,'sessions':len(runs),'rows':sum(len(x['rows']) for x in runs.values())}}
with (HERE/'continuation127-126-budget.json').open('x') as evidence_file:
 evidence_file.write(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
for s,c in runs.items():
 print(s,len(c['rows']),'period',round(c['all_summary']['period_to_next']['median'],4),'maint events',len(c['maintenance_events']))
 for p,x in c['all_parity'].items():print(p,{k:round(x[k]['median'],4) for k in c['chain_partition']+['display','decode_tail','preview_encode','snapshot_sum'] if k in x})
 if c['maintenance_events']:
  slow=[r for r in c['rows'] if r['next_commit_to_first_served']>.15]
  print('slow gaps',len(slow),'with manual maintenance',sum(bool(r['maintenance_overlap']) for r in slow))

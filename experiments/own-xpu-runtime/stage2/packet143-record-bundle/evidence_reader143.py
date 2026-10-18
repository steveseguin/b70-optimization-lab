"""Read-only, independently checked component brackets and exact composed smoke.

Derived from p142 compare and p137b packet137_report plus review26 raw-boundary
checks. Does not import a foreign packet, trust candidate_qualified, or rewrite
any evidence. All rates are rederived from the 99 timestamp intervals.
"""
import argparse,hashlib,json,math,statistics,sys
from pathlib import Path
from compositions import P,ROOT,read,sha
ARITHMETIC='iq3-p49-split32-v1'
CLASSES={'incident-retrospective':'operations','code-review':'code','customer-email':'prose','sql-debugging':'code','release-plan':'operations','benchmark-analysis':'analysis','architecture-tradeoff':'analysis','bug-report-synthesis':'operations','technical-guide':'documentation','risk-register':'structured-writing','performance-hypotheses':'analysis','decision-memo':'prose'}
def require(value,message):
 if not value:raise ValueError(message)
def oracle():
 from shared_oracle import completed_binding
 import contextlib,io
 with contextlib.redirect_stdout(io.StringIO()):completed_binding()
 import importlib.util
 f=P/'oracle/suite_check.py';spec=importlib.util.spec_from_file_location('packet143_original_oracle',f);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 require(tuple(m.PROMPT_IDS)==tuple(CLASSES),'oracle suite order differs')
 return lambda prompt:m.token_record(P/'oracle/results'/prompt)
def proposals(dest):
 f=dest/'rank1/draft-rows.jsonl';rows=[json.loads(s) for s in f.read_text().splitlines() if s.strip()]
 values=[[r[k] for k in ('draft_position','confirmed_token','guess','head')] for r in rows]
 require(values and any(r[3] for r in values),'missing draft proposals')
 return dict(rows=len(values),sha256=hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest())
def window(output):
 output=Path(output);w=read(output/'window.json')
 require(all(w.get(k) is True for k in ('passed','device_executed','device_complete','lease_released')) and not w.get('child_still_running') and not w.get('stop_reasons') and not w.get('child_retained'),'incomplete device window')
 require(w.get('end_utc') or w.get('finished_utc_ns') or w.get('ended_utc_ns'),'missing completed-window timestamp')
 for leaf,digest in w['files'].items():
  target=(output/leaf).resolve();require(target.is_relative_to(output.resolve()) and sha(target)==digest,'changed/escaping artifact '+leaf)
 def bound(leaf):
  require(w['files'].get(leaf)==sha(output/leaf),'unbound artifact '+leaf);return read(output/leaf)
 identity=bound('identity.json');require(w['identity']==identity,'window identity changed')
 require(bound('run/teardown.json').get('drained') is True,'incomplete drain')
 require(bound('run/device-isolation.json').get('passed') is True,'device isolation failed')
 require(w['oracle_completion_sha256']==sha(P/'oracle/results/completion.json'),'oracle changed')
 snapshot=bound('suite-manifest.snapshot.json');authority=read(P/'oracle/results/suite-manifest.json')
 def normalized(manifest):
  manifest=json.loads(json.dumps(manifest))
  for entry in manifest['prompts']:entry.pop('input_bundle',None)
  return manifest
 require(normalized(snapshot)==normalized(authority),'suite snapshot differs from original oracle')
 coordination=read(output/'lane-coordination.json')
 require(coordination['passed'] is True and coordination['released_before_report'] is True and coordination['reservation']['scope']=='lane-'+identity['lane'],'lane release unproven')
 return w,identity,bound

def checked_requests(summary,token_oracle,cap=128):
 rows=summary['requests'];require([r['prompt_id'] for r in rows]==list(CLASSES),'complete ordered prompt suite required')
 require(summary['passed'] is True and summary['cached_tokens']==0 and summary['request_count']==12 and summary['requested_max_new']==cap and summary['kv_dtype']=='BF16','cold full-precision scope differs')
 grouped={};counts=[]
 for r in rows:
  prompt=r['prompt_id'];require(r['prompt_class']==CLASSES[prompt],'prompt class changed')
  require(r['passed'] is True and r['exact_oracle'] is True and r['cached_tokens']==0 and r.get('repeat',1)==1,'request exact/cold gate failed')
  require(len(r['tokens'])==cap and r['tokens']==token_oracle(prompt)[:cap],'target output differs')
  if cap==64:continue
  ts=r['token_timestamps'];require(len(ts)==cap and all(type(t) in (int,float) and math.isfinite(t) for t in ts) and all(b>a for a,b in zip(ts,ts[1:])),'invalid timestamps')
  rate=99/(ts[99]-ts[0]);require(math.isclose(rate,r['tok_s_1_100_intervals_after_ttft'],rel_tol=1e-10),'stored rate differs')
  grouped.setdefault(CLASSES[prompt],[]).append(rate)
  hits,guesses=r['hits'],r['guesses'];require(type(hits) is int and type(guesses) is int and 0<=hits<=guesses and guesses>0,'invalid acceptance counts')
  require(math.isclose(r['acceptance'],hits/guesses,rel_tol=1e-10),'acceptance differs')
  counts.append(dict(prompt_id=prompt,hits=hits,guesses=guesses))
 return dict(rate=statistics.median(statistics.median(v) for v in grouped.values()) if grouped else None,acceptance_counts=counts)

def bracket(output,dimension,token_oracle=None):
 registration=read(P/'lineage-inputs/component-registration.json')[dimension]
 w,identity,bound=window(output);output=Path(output)
 require(w['wrapper_seal_sha256']==registration['wrapper_seal_sha256'],'component wrapper identity changed')
 require(identity['lane']=='B' and identity['binary_sha256']==registration['binary_sha256'],'registered component binary/lane differs')
 require(identity['dispatch_sha256']==sha(P/'dispatch-speed6.json'),'component dispatch differs')
 result=bound('bracket-summary.json');proof=bound('run/bracket-inputs.json')
 require(result['passed'] is True and result['kind']=='bracket' and proof['passed'] is True and proof['kind']=='bracket','bracket failed')
 require(all(result[k]==1 for k in ('model_lifetimes','target_loads','draft_loads','teardown_count')),'one-load bracket required')
 require(len(result['views'])==len(proof['views'])==len(identity['bracket']['views'])==5,'five complete views required')
 token_oracle=token_oracle or oracle();rows=[];descriptors=None
 for i,(r,raw,selection) in enumerate(zip(result['views'],proof['views'],identity['bracket']['views'])):
  choice='candidate' if i%2 else 'control';digest=registration[choice+'_selection_sha256'];prefix=f'run/views/{i:02d}-{choice}'
  require(r['index']==raw['index']==i and r['choice']==raw['choice']==selection['choice']==choice and r['lane']=='B','wrong bracket order/lane')
  require(raw['selection_sha256']==selection['selection_sha256']==digest,'component selection differs')
  require(raw['passed'] is True and raw['started_utc_ns']<raw['finished_utc_ns'] and (not i or proof['views'][i-1]['finished_utc_ns']<raw['started_utc_ns']),'overlapping/failed view')
  require(raw['output']==str(output/prefix),'view output escape')
  summary=bound(prefix+'/summary.json');require(len(summary['requests'])==len(raw['requests'])==12 and all(all(a[k]==b[k] for k in ('tokens','token_timestamps','prompt_id','prompt_class','cached_tokens','hits','guesses','passed','exact_oracle')) for a,b in zip(summary['requests'],raw['requests'])),'raw request proof differs')
  metrics=checked_requests(summary,token_oracle)
  require(math.isclose(metrics['rate'],r['rate'],rel_tol=1e-12) and metrics['acceptance_counts']==r['acceptance_counts'],'stored bracket metrics differ')
  incident=bound(prefix+'/incident64/receipt.json')
  require(raw['incident64']['receipt_sha256']==sha(output/prefix/'incident64/receipt.json') and incident['passed'] is True and incident['exact_oracle'] is True and incident['cached_tokens']==0 and incident['tokens']==token_oracle(next(iter(CLASSES)))[:64],'incident64 differs')
  current=[]
  for rank in (0,1):
   b=bound(prefix+f'/boundary/boundary-rank{rank}.json');require(b==raw['boundary'][rank] and b['passed'] is True and b['total_reset'] is True and b['allocation_ids_preserved'] is True and b['cached_tokens']==0 and b['weight_uploads_after_load']==0 and b['selection_sha256']==digest,'reset/allocation boundary differs')
   current.append((b['arena_descriptors_sha256'],b['weight_descriptors_sha256']))
  if descriptors is None:descriptors=current
  require(current==descriptors,'loaded descriptors changed')
  proposal={name:proposals(output/prefix/name) for name in ('incident64',*CLASSES)}
  require(proposal==r['draft_proposals'],'draft proposal trace differs')
  rows.append(dict(index=i,choice=choice,lane='B',all_13_exact=True,exact_count=13,draft_proposals=proposal,**metrics))
 if dimension=='token_input':
  sample=bound('run/ranks/rank1/token-table-samples.json');require(sample['passed'] is True and sample['samples']==32 and sample['before_ready'] is True,'table sample gate missing')
 else:
  for rank in (0,1):
   c=bound(f'run/ranks/rank{rank}/class-layout.json');require(c['class_layout_bank']==registration['variant'] and 0<c['bytes']<=600*1024**2 and c['budget']==600*1024**2 and c['weights'],'class-copy proof differs')
 return dict(result=dict(passed=True,kind='bracket',model_lifetimes=1,views=rows),window_sha256=sha(output/'window.json'),summary_sha256=sha(output/'bracket-summary.json'),selection_sha256=registration['candidate_selection_sha256'],evidence_path=str(output),coordination_sha256=sha(output/'lane-coordination.json'))

def smoke(output,selection,token_oracle=None):
 from compositions import path,native
 output=Path(output);w,identity,bound=window(output);lineage=path(selection)
 require(w['wrapper_seal_sha256']==sha(P/'placement-validation/wrapper-seal.json'),'composed smoke wrapper differs')
 require(identity['lane']=='A' and identity['binary_sha256']==sha(P/'v5/build/device/own-rt-iq3'),'composed smoke binary/lane differs')
 require(identity['selection_sha256']==sha(lineage/'selection.json') and read(lineage/'selection.json')==native(selection),'smoke selection differs')
 require(identity['dispatch_sha256']==sha(P/'dispatch-speed6.json'),'smoke dispatch differs')
 require(identity['seal_sha256']==sha(lineage/'screen-seal.json') and identity['memory_plan_sha256']==sha(lineage/'memory-plan.json'),'smoke seal/memory differs')
 require(identity['profile']=='tp2' and identity['timing']=='token' and identity['placement']['context']==4096 and identity['placement']['draft_rank']==1 and identity['placement']['target_split']==0,'smoke topology differs')
 summary=bound('summary.json');proof=bound('run/report-inputs.json')
 require(proof['passed'] is True and len(proof['requests'])==12 and proof['lane']=='A' and proof['placement']==identity['placement'] and proof['device_isolation']==summary['device_isolation']==bound('run/device-isolation.json'),'smoke raw proof/isolation missing')
 for a,b in zip(proof['requests'],summary['requests']):require(all(a[k]==b[k] for k in ('prompt_id','tokens','cached_tokens','repeat','passed','exact_oracle')),'smoke raw proof differs')
 require(summary['passed'] is True and summary['smoke'] is True and summary['tokens']==64 and summary['cached_tokens']==0 and summary['request_count']==12,'smoke scope differs')
 token_oracle=token_oracle or oracle()
 require([r['prompt_id'] for r in summary['requests']]==list(CLASSES),'smoke suite order differs')
 for r in summary['requests']:
  raw=bound('run/'+r['prompt_id']+'64/receipt.json')
  require(all(raw[k]==r[k] for k in ('tokens','prompt_id','cached_tokens','repeat','exact_oracle','passed')),'smoke request receipt differs')
  require(r['passed'] is True and r['exact_oracle'] is True and r['cached_tokens']==0 and r.get('repeat',1)==1 and len(r['tokens'])==64 and r['tokens']==token_oracle(r['prompt_id'])[:64],'smoke exact/cold gate failed')
 return dict(passed=True,request_count=12,max_new=64,lane='A',selection=selection,selection_sha256=identity['selection_sha256'],window_sha256=sha(output/'window.json'),summary_sha256=sha(output/'summary.json'),evidence_path=str(output),coordination_sha256=sha(output/'lane-coordination.json'))

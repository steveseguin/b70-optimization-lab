#!/usr/bin/env python3
"""Closed six-request readback only after root confirms drain. No operational imports."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,resource,stat,time
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2];D=P/'launch-b/evidence/device-b'
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-coverage-b.control');EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-coverage-b')
PLAN_SHA='9d80a1d2fc29cef4444a555ca2f033952adf8250f8a052bb2d1eadc08b7429ac'
BINARY='97348925367e1ad67313cf9863d0c4cba47abea871c386972983965e036ea4b2'
MANIFEST_SHA='90f8bf9f86ba5b4c8e082393509db0fde4111411ef9062417054ee60fa22dcd5'
BASE=L/'baseline/audit.py';BASE_SHA='43154e5b8101fb879eb08bbbebc29714443dd083cb90df6fbbb7e269d522d0ab'
BUNDLE=L/'state-bundle/evidence/device-a/audit.py';BUNDLE_SHA='4013acb3216fe908edda3761089a11377e9513f025c99d0442d9792386b5c594'
PRIOR=L/'baseline/evidence/independent-a/review.json';PRIOR_SHA='f662fcecf93c92f90006c09c05d4a4c02e71e84ae9d8c82dbff3fdfc39ebb5bb'
OLD_INDEX=PRIOR.parent/'artifact-index.jsonl.gz';OLD_INDEX_SHA='e8137dddb0929d5476d27a8a774539a77d595aeb296e9d0ec778ceec066a6982'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,name,h=None):
 if h is not None and sha(p)!=h:raise ValueError('frozen helper changed')
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
B=load(BASE,'coverage_baseline_readback',BASE_SHA);U=load(BUNDLE,'coverage_bundle_readback',BUNDLE_SHA)
read,require=B.read,B.require

def startup_request_distinction(plan):
 for layer in (plan,plan['suite'],plan['adapter']):
  require(layer['startup_max_new']==128 and layer['request_max_new_by_case']==[512,512,128],'explicit startup/request distinction')
 require(plan['max_new']==plan['adapter']['max_new']==512,'request ceiling unchanged')
 require(plan['unit']=='gsq-coverage-b.service' and plan['adapter']['output']==str(CONTROL/'ranks') and plan['adapter']['evidence_output']==str(EVIDENCE),'fresh coverage-b identity')
 for argv in plan['adapter']['rank_argv']:
  require(argv.count('--max-new')==1 and argv[argv.index('--max-new')+1]=='128','native startup cap')

def join_raw(full,raw,decoded):
 fields={'decoded_text','quality','prefix_baseline_exact'}
 require(set(full)==set(raw)|fields and not set(raw)&fields,'raw/enriched row schema')
 require({k:v for k,v in full.items() if k not in fields}==raw,'raw request joined before decode enrichment')
 require(decoded['tokens']==raw['result']['tokens'] and decoded['text']==full['decoded_text'] and decoded['quality']==full['quality'] and decoded['skip_special_tokens'] is False,'separate decoded output join')

def rubric_check(case,text,tokens,decode):
 visible=text
 if tokens and tokens[-1] in (248044,248046):
  end=decode([tokens[-1]])
  if visible.endswith(end):visible=visible[:-len(end)]
 rubric=case['rubric']
 if rubric['kind']!='exact_json_facts':return dict(automated_passed=None,manual_review_required=True,rubric=rubric,word_count=len(visible.split()),scope='Complete output needs human readback; word count is not quality proof')
 try:
  def unique(rows):
   out={}
   for k,v in rows:require(k not in out,'duplicate JSON key');out[k]=v
   return out
  value=json.loads(visible,object_pairs_hook=unique)
  return dict(automated_passed=type(value)is dict and value==rubric['expected'] and type(value.get('sensor_count'))is int,parsed=value,expected=rubric['expected'],manual_review_required=True)
 except (ValueError,TypeError) as e:return dict(automated_passed=False,error=str(e),expected=rubric['expected'],manual_review_required=True)

def reference_inventories():
 require(sha(OLD_INDEX)==OLD_INDEX_SHA,'original audited extent authority');out={0:{},1:{}}
 with gzip.open(OLD_INDEX,'rt') as f:
  for line in f:
   x=json.loads(line)
   if x['root']!='evidence':continue
   path=Path(x['path'])
   for rank in (0,1):
    if str(path.parent)==f'prompt-00-none/rank{rank}/state-2147483647':
     require(path.name not in out[rank],'duplicate original extent');out[rank][path.name]=x
 require(all(out.values()),'both rank extent inventories');return out

def run(plan_sha):
 require(plan_sha==PLAN_SHA,'fixed admitted coverage-b plan')
 require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper limits');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 D.mkdir(parents=True,exist_ok=True);require(not (D/'review.json').exists() and not (D/'artifact-index.jsonl.gz').exists(),'exclusive audit outputs')
 receipt=dict(schema='gsq.coverage.launch-b.independent-readback.v1',passed=False,quality_qualified=False,no_speed_claim=True,device_executed_by_reviewer=False);start=time.monotonic()
 try:
  manifest=read(P/'manifest.json');require(sha(P/'manifest.json')==MANIFEST_SHA,'fixed preregistered prompts/rubrics')
  require(sha(PRIOR)==PRIOR_SHA,'baseline review');prior=read(PRIOR);reference=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a/resident-suite.json')
  require(prior['passed'] and sha(reference)==prior['full_result_sha256'],'baseline full result');old=read(reference);prefix=old['prompts'][0]['arms'][0]['result']['tokens'];require(len(prefix)==128 and prefix[-1] not in (248044,248046),'existing128 prefix')
  plan=read(CONTROL/'plan.json');ad=read(CONTROL/'admission.json');terminal=read(CONTROL/'terminal.json')
  require(sha(CONTROL/'plan.json')==plan_sha==ad['plan_sha256']==terminal['plan_sha256'] and ad['plan']==plan,'exact plan join')
  require(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()==ad['canonical_plan_sha256'],'canonical plan')
  startup_request_distinction(plan)
  for k,v in plan['unit_properties'].items():require(ad['unit'][k]==v,'admitted safe properties')
  B.validate_passive(ad['before'],terminal['after'],terminal)
  require(plan['requests']==plan['suite']['requests']==6 and plan['suite']['pairs']==3 and plan['suite']['captures']==7 and plan['suite']['cases']==manifest['cases'],'fixed6request schedule')
  require(plan['adapter']['request_cap']==6 and plan['adapter']['storage']['raw_state_bytes']==1620097500 and plan['suite']['storage']['evidence_forecast_bytes']==1754315228,'seven capture forecast')
  for mapping in (plan['source_sha256'],plan['suite']['source_sha256'],plan['adapter']['source_sha256'],manifest['source_sha256']):
   for f,h in mapping.items():require(sha(R/f)==h,'admitted source '+f)
  for name,h in manifest['prompt_sha256'].items():require(sha(P/'prompts'/name)==h,'prompt text identity')
  native=read(plan['adapter']['build_receipt']);require(native['passed'] and sha(plan['adapter']['build_receipt'])==plan['adapter']['build_receipt_sha256'],'native receipt')
  require(sha(plan['adapter']['binary'])==native['binary_sha256']==plan['adapter']['binary_sha256']==BINARY,'qualified native binary')
  for mapping in (native['source_sha256'],native['object_sha256']):
   for f,h in mapping.items():require(sha(R/f)==h,'native source/object')
  T=load(P/'tokenizer.py','coverage_readback_tokenizer');tok,render,tokenizer_identity=T.load();require(tokenizer_identity==manifest['tokenizer'],'same exact tokenizer/template implementation identity')
  for case in (manifest['cases'][0],manifest['cases'][2]):require(tok.encode((P/'prompts'/(case['id']+'.txt')).read_text(),add_special_tokens=False).ids==case['tokens'],'exact retained chat input IDs')
  historical=R/'experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/inputs/prefill512/source.txt'
  require(tok.encode(historical.read_text(),add_special_tokens=False).ids[:512]==manifest['cases'][1]['tokens'],'exact historical raw512 IDs')
  fullpath=Path(terminal['result']['full_result_path']);require(fullpath==EVIDENCE/'coverage-result.json' and sha(fullpath)==terminal['result']['full_result_sha256'],'full result')
  full=read(fullpath);require(full['passed'] and full['requests']==6 and len(full['pairs'])==3 and full['all_target_mtp_exact'] and not full['quality_qualified'],'full exactness scope')
  require(full['explicit_final_DUMP'] and full['closed_stamps_verified'] and full['manifest_sha256']==MANIFEST_SHA and full['order_balance']==manifest['order_balance'],'repeat closure/order')
  require(full['rank_pids']==[x[0] for x in terminal['rank_identities']],'same pair identities')
  names=[case['id']+'-'+mode for case in manifest['cases'] for mode in case['order']];bases=[EVIDENCE]+[EVIDENCE/name for name in names]
  require(set(full['capture_stamps'])==set(names),'all six measured capture stamps')
  inventories=reference_inventories();raw=[];total=0
  for label,root in [('control',CONTROL),('evidence',EVIDENCE)]:
   for path in sorted(root.rglob('*')):
    st=path.lstat();require(not stat.S_ISLNK(st.st_mode),'artifact symlink')
    if stat.S_ISDIR(st.st_mode):continue
    require(stat.S_ISREG(st.st_mode),'regular artifacts');raw.append((label,root,path,st));total+=st.st_size
    require(len(raw)<=3000 and total<=2*1024**3,'bounded2GiB/3000file audit')
  expected={str(base/f'rank{rank}/state-2147483647') for base in bases for rank in (0,1)}
  require({str(path.parent) for _,_,path,_ in raw if path.name=='state.bundle'}==expected,'exact14 bundle paths')
  reconstructed={};physical={};captures=[]
  for base in bases:
   for rank in (0,1):
    path=base/f'rank{rank}/state-2147483647';got=U.stream_bundle(path,inventories[rank],semantic_oracle=False)
    reconstructed[(base.name if base!=EVIDENCE else '',rank)]=got
    physical.update({str(path/name):h for name,h in got['physical_sha256'].items()})
    captures.append(dict(path=str(path.relative_to(EVIDENCE)),payload_bytes=got['payload_bytes'],ranges=got['ranges'],physical_sha256=got['physical_sha256'],semantic_old_state_oracle=False))
  with (D/'artifact-index.jsonl.gz').open('xb') as f,gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as z:
   for label,root,path,st in raw:
    h=physical[str(path)] if str(path) in physical else sha(path);require(U.stamp(path.stat())==U.stamp(st),'artifact changed')
    z.write((json.dumps(dict(root=label,path=str(path.relative_to(root)),bytes=st.st_size,sha256=h),separators=(',',':'))+'\n').encode())
  number=0;checked=[]
  for case,pair in zip(manifest['cases'],full['pairs']):
   require(pair['case']==case['id'] and pair['order']==case['order'] and pair['exact_tokens'] and pair['exact_target_state'] and len(pair['arms'])==2,'case/order/pair')
   require(read(EVIDENCE/(case['id']+'-pair.json'))==pair,'raw pair')
   arms=[]
   for mode,row in zip(case['order'],pair['arms']):
    number+=1;name=case['id']+'-'+mode;dest=EVIDENCE/name
    require(row['request']==number and row['name']==name and row['case']==case['id'] and row['mode']==mode and row['prompt_tokens']==case['tokens'] and row['requested_max_new']==case['max_new'],'fixed arm identity')
    rawrow=read(dest/'request-result.json');decoded=read(dest/'decoded-output.json');join_raw(row,rawrow,decoded)
    tokens=row['result']['tokens'];metric=B.timing(row['result'],case['max_new']);consumed=B.confirmed_inputs(row['result'],case['tokens'])
    require(consumed==row['consumed_positions']==len(case['tokens'])+len(tokens)-1 and row['context_capacity']==4096 and consumed<4096,'actual consumed context/pending token')
    for k in ('output_tokens','decode_intervals','termination'):require(metric[k]==row['metric'][k],'retained metric')
    B.near(metric['decode_wall_ms'],row['metric']['decode_wall_ms'],'decode timing');B.near(metric['prompt_wall_ms'],row['metric']['prompt_wall_ms'],'prompt timing')
    if mode=='mtp':B.guess_outcomes(row['result'],case['tokens'],case['max_new'])
    else:require(all(row['result']['stats'][k]==0 for k in ('guesses','hits','misses')),'target only stats')
    if case['prefix_oracle_tokens']:require(len(tokens)>=128 and tokens[:128]==prefix and row['prefix_baseline_exact'] is True,'qualified128 prefix')
    else:require(row['prefix_baseline_exact'] is None,'no invented old output oracle')
    text=T.decode(tokens);require(text==row['decoded_text'] and decoded['tokenizer_sha256']==T.TOKENIZER_SHA,'honest full decode')
    assessed=rubric_check(case,text,tokens,T.decode);require(assessed==row['quality'],'independent exact rubric result')
    extent=0
    for rank in (0,1):
     got=reconstructed[(name,rank)];require(got['logical_map']==row['state_sha256'][str(rank)] and got['snapshots']==full['capture_stamps'][name][str(rank)],'closed full state/map stamps')
     reset=read(dest/f'rank{rank}/reset.json');require(reset['passed'] and reset['allocation_ids_preserved'],'positive full RESET');extent+=got['payload_bytes']
    require(extent==221743168,'full target byte extent')
    arms.append(dict(name=name,mode=mode,input_tokens=len(case['tokens']),output_tokens=len(tokens),tokens=tokens,consumed_positions=consumed,last_consumed_position=consumed-1,final_output_pending=True,timing=metric,stats=row['result']['stats'],decoded_text=text,quality=assessed,prefix_baseline_exact=row['prefix_baseline_exact']))
   require(pair['arms'][0]['result']['tokens']==pair['arms'][1]['result']['tokens'] and pair['arms'][0]['state_sha256']==pair['arms'][1]['state_sha256'],'same-target pair exact')
   checked.append(dict(case=case['id'],order=case['order'],arms=arms,exact_tokens_and_state=True))
  require(number==6,'all six requests');owners=[];memory=[]
  for rank,amount in enumerate((30947490698,29824495508)):
   launch=read(CONTROL/f'ranks/rank{rank}-launch.json');argv=launch['argv'];expected_argv=plan['adapter']['rank_argv'][rank]
   require(len(argv)==len(expected_argv),'actual launch argv length')
   for i,value in enumerate(expected_argv):
    if value in ('<channel-fd>','<stop-fd>'):require(str(argv[i]).isdigit(),'actual inherited descriptor')
    else:require(argv[i]==value,'actual launch argv')
   require(launch['pid']==terminal['rank_identities'][rank][0] and launch['environment']==plan['adapter']['environment'][rank],'actual launch identity/environment')
   owner=read(EVIDENCE/f'rank{rank}/receipt.json');require(owner['passed'] and owner['rank']==rank and not owner['error'] and len(owner['teardown'])==1,'clean owner');t=owner['teardown'][0]
   require(t['safe_to_exit'] and t['in_flight']==t['live_bytes']==t['exit_code']==0,'safe teardown');owners.append(t)
   census=read(EVIDENCE/f'rank{rank}/census.json');actual=sum(x['bytes'] for x in census['allocations'] if x['live'] and x['memory']=='device');require(actual==census['totals']['device']==amount,'same exact allocation ledger');memory.append(actual)
  ownership=read(EVIDENCE/'ownership.json');require(ownership['returncodes']==[0,0] and not ownership['retained_pids'] and ownership['signals_sent']==0 and not ownership['stop_requested'],'normal process closure')
  require(len([p for _,_,p,_ in raw if p.name=='state.json' and p.parent.name.startswith('state-')])==14,'exact14 state metadata captures')
  receipt.update(passed=True,startup_max_new=128,request_max_new_by_case=[512,512,128],prior_coverage_a_passed=False,requests=6,pairs=3,bundles=14,captures=captures,all_target_mtp_exact=True,prefix128_exact=True,case_results=checked,document_rubric_passed=all(a['quality']['automated_passed'] for a in checked[2]['arms']),manual_output_review_required=True,quality_qualified=False,order_balance=manifest['order_balance'],rank_identities=terminal['rank_identities'],owners=owners,ownership=ownership,actual_device_bytes=memory,physical_drain=True,positive_rank_contacts=terminal['observed_target_contact'],kernel_fault_baseline_unchanged=True,artifact_count=len(raw),indexed_bytes=total,index_sha256=sha(D/'artifact-index.jsonl.gz'),full_result_sha256=sha(fullpath),plan_sha256=plan_sha,manifest_sha256=MANIFEST_SHA,binary_sha256=BINARY,limitations=['Same-target/MTP equivalence on three fixed cases; no independent same-weight full-model reference','Only prompt00 first128 has old baseline output authority; no new long-output state oracle asserted','Raw historical512 is continuation, not chat question-answer accuracy; no output filtering or prompt tuning','Quality rubric outcomes and complete text retained separately from equivalence; manual readback still required','No speed aggregate or balanced-order claim; first requests may encounter JIT and all runtime caches remain uncontrolled','No live queries, devices, services or model tensor reads by auditor'])
 except BaseException as e:receipt['error']=type(e).__name__+': '+str(e);raise
 finally:
  receipt.update(auditor_sha256=sha(__file__),baseline_helper_sha256=BASE_SHA,bundle_parser_sha256=BUNDLE_SHA,elapsed_seconds=time.monotonic()-start)
  with (D/'review.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 print(json.dumps({'passed':True,'review_sha256':sha(D/'review.json'),'quality_qualified':False}))
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',action='store_true',required=True);ap.add_argument('--plan-sha256',required=True);a=ap.parse_args();require(len(a.plan_sha256)==64 and all(c in '0123456789abcdef' for c in a.plan_sha256),'plan SHA');run(a.plan_sha256)

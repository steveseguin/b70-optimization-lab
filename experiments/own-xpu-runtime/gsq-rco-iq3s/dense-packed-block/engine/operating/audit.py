#!/usr/bin/env python3
"""Closed full combined-candidate audit; --run ONLY after root authorizes drained readback.
No operational imports or device/service/model access. One resident qualification.
"""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,resource,stat,time
P=Path(__file__).resolve().parent;CAND=P.parent;D=P/'evidence/device-a';L=CAND.parents[1];R=L.parents[2]
BASE=L/'baseline/audit.py';BASE_SHA='43154e5b8101fb879eb08bbbebc29714443dd083cb90df6fbbb7e269d522d0ab'
assert hashlib.sha256(BASE.read_bytes()).hexdigest()==BASE_SHA
s=importlib.util.spec_from_file_location('completion_baseline_audit_helpers',BASE);B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
read,sha,require=B.read,B.sha,B.require
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-dense-packed-block-engine-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-dense-packed-block-engine-a')
PRIOR=L/'baseline/evidence/independent-a/review.json';PRIOR_SHA='f662fcecf93c92f90006c09c05d4a4c02e71e84ae9d8c82dbff3fdfc39ebb5bb'
BINARY=None
REFERENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a/resident-suite.json')
PARENT_AUDITOR_SHA='92b47efce21929a4f6f3bf752967cc67f657e9071b2a874001ebef592718598c'
BUNDLE_AUDITOR=L/'state-bundle/evidence/device-a/audit.py'
BUNDLE_AUDITOR_SHA='4013acb3216fe908edda3761089a11377e9513f025c99d0442d9792386b5c594'
require(sha(BUNDLE_AUDITOR)==BUNDLE_AUDITOR_SHA,'frozen independent bundle parser')
s=importlib.util.spec_from_file_location('iq3_closed_bundle_stream',BUNDLE_AUDITOR);U=importlib.util.module_from_spec(s);s.loader.exec_module(U)
OLD_INDEX=PRIOR.parent/'artifact-index.jsonl.gz'
OLD_INDEX_SHA='e8137dddb0929d5476d27a8a774539a77d595aeb296e9d0ec778ceec066a6982'
IMMEDIATE_PARENT=L/'dense-q6-p33/operating/audit.py'
IMMEDIATE_PARENT_SHA='966290e28bd4bcbfdfa5288a1c038f6d5be1a0e724a8a7420fee1772b65feb08'
PLAN_SHA=None
BUILD_SHA=None
require(sha(IMMEDIATE_PARENT)==IMMEDIATE_PARENT_SHA,'frozen qualified fullsuite auditor')

def expected_members(bases):
 expected={str((base/f'rank{rank}/state-2147483647').relative_to(EVIDENCE)):{} for base in bases for rank in (0,1)}
 require(sha(OLD_INDEX)==OLD_INDEX_SHA,'original fully audited byte index')
 with gzip.open(OLD_INDEX,'rt') as f:
  for line in f:
   x=json.loads(line)
   if x['root']!='evidence':continue
   rel=Path(x['path']);key=str(rel.parent)
   if key in expected:
    require(rel.name not in expected[key],'duplicate original member');expected[key][rel.name]=x
 require(len(expected)==54 and all(expected.values()),'all54 original inventories')
 return expected

def run(plan_sha):
 require(all(isinstance(h,str) and len(h)==64 and all(c in '0123456789abcdef' for c in h) for h in (PLAN_SHA,BUILD_SHA,BINARY)) and plan_sha==PLAN_SHA,'fixed admitted plan/build/binary pending or mismatched')
 require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19');require(os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper cores');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 D.mkdir(parents=True,exist_ok=True)
 require(not (D/'review.json').exists() and not (D/'artifact-index.jsonl.gz').exists(),'exclusive audit outputs')
 start=time.monotonic();receipt=dict(schema='ownrt.gsq.dense-packed-block-engine-independent-device.v1',passed=False,scope='All24 baseline-exact measured arms in one persistent rank pair; descriptive same-run target/MTP timings',combined_timing_claim=False,device_executed_by_reviewer=False)
 try:
  require(sha(PRIOR)==PRIOR_SHA,'immutable independent baseline authority');prior=read(PRIOR)
  require(prior['passed'] and prior['all12_exact'] and sha(REFERENCE)==prior['full_result_sha256'],'baseline authority');baseline=read(REFERENCE);refs={a['name']:a for p in baseline['prompts'] for a in p['arms']}
  plan=read(CONTROL/'plan.json');ad=read(CONTROL/'admission.json');term=read(CONTROL/'terminal.json')
  require(term['plan_sha256']==ad['plan_sha256']==sha(CONTROL/'plan.json')==plan_sha and ad['plan']==plan,'plan identity')
  require(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()==ad['canonical_plan_sha256'],'canonical plan')
  for k,v in plan['unit_properties'].items():require(ad['unit'][k]==v,'safe coordinator property')
  B.validate_passive(ad['before'],term['after'],term)
  require(plan['requests']==plan['suite']['total_requests']==26 and plan['suite']['measured_requests']==24,'fixed full suite')
  require(plan['suite']['storage']['retained_state_dumps']==27 and plan['suite']['storage']['evidence_forecast_bytes']==6383165228,'27-dump plus128MiB admission')
  require(plan['adapter']['request_cap']==26 and plan['adapter']['storage']['raw_state_bytes']==6248947500 and plan['adapter']['storage']['evidence_forecast_bytes']==6383165228,'adapter fullbundle forecast')
  require(plan['suite']['baseline_review_sha256']==PRIOR_SHA and plan['suite']['baseline_result_sha256']==prior['full_result_sha256'],'baseline admission')
  for mapping in (plan['source_sha256'],plan['suite']['source_sha256'],plan['adapter']['source_sha256']):
   for p,h in mapping.items():require(sha(R/p)==h,'admitted source '+p)
  native=read(plan['adapter']['build_receipt']);require(native['passed'] and native['mode']=='native' and sha(plan['adapter']['build_receipt'])==plan['adapter']['build_receipt_sha256']==BUILD_SHA,'native receipt')
  require(sha(plan['adapter']['binary'])==native['binary_sha256']==plan['adapter']['binary_sha256']==BINARY,'same candidate binary')
  for mapping in (native['source_sha256'],native['object_sha256']):
   for p,h in mapping.items():require(sha(R/p)==h,'native source/object '+p)
  fullpath=Path(term['result']['full_result_path']);require(fullpath==EVIDENCE/'resident-suite.json' and sha(fullpath)==term['result']['full_result_sha256'],'full result binding');full=read(fullpath)
  manifest=read(L/'baseline/manifest.json');require(full['manifest_sha256']==sha(L/'baseline/manifest.json')==plan['suite']['manifest_sha256'],'original corpus')
  require(full['passed'] and full['requests']==26 and full['measured_requests']==24 and len(full['prompts'])==12 and len(full['warmup'])==2,'complete full suite')
  require(full['rank_pids']==[x[0] for x in term['rank_identities']],'same persistent ranks')
  require(full['final_explicit_DUMP_verified'] and full['closed_capture_stamps_verified'],'explicit final repeat and owner closure')
  allnames=[a['name'] for pair in full['prompts'] for a in pair['arms']]
  bases=[EVIDENCE]+[EVIDENCE/w['name'] for w in full['warmup']]+[EVIDENCE/name for name in allnames]
  expected=expected_members(bases);rawpaths=[];total=0
  for label,root in [('control',CONTROL),('evidence',EVIDENCE)]:
   for path in sorted(root.rglob('*')):
    before=path.lstat();require(not stat.S_ISLNK(before.st_mode),'artifact symlink')
    if stat.S_ISDIR(before.st_mode):continue
    require(stat.S_ISREG(before.st_mode),'regular artifact');total+=before.st_size;rawpaths.append((label,root,path,before))
    require(total<=7*1024**3 and len(rawpaths)<=10000,'bounded7GiB/10000 artifacts')
  require({str(path.relative_to(EVIDENCE)) for _,root,path,_ in rawpaths if root==EVIDENCE and path.name=='state.bundle'}=={key+'/state.bundle' for key in expected},'exact54 bundle paths')
  reconstructed={};physical={};captures=[]
  for relative,original in expected.items():
   path=EVIDENCE/relative;got=U.stream_bundle(path,original,semantic_oracle=relative.startswith('prompt-'));reconstructed[relative]=got
   physical.update({str(path/name):h for name,h in got['physical_sha256'].items()})
   captures.append(dict(path=relative,payload_bytes=got['payload_bytes'],ranges=got['ranges'],semantic_baseline_required=got['semantic_baseline_required'],baseline_hash_differences=got['baseline_hash_differences'],inventory_and_lengths_exact=True,physical_sha256=got['physical_sha256']))
  digests={};sizes={}
  with (D/'artifact-index.jsonl.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as z:
   for label,root,path,before in rawpaths:
    h=physical[str(path)] if str(path) in physical else sha(path)
    require(U.stamp(path.stat())==U.stamp(before),'artifact changed after inventory');digests[str(path)]=h;sizes[str(path)]=before.st_size
    z.write((json.dumps(dict(root=label,path=str(path.relative_to(root)),bytes=before.st_size,sha256=h),separators=(',',':'))+'\n').encode())
  def states(base,expected_map):
   extent=0
   for rank in (0,1):
    key=str((base/f'rank{rank}/state-2147483647').relative_to(EVIDENCE));got=reconstructed[key]
    require(got['logical_map']==expected_map[str(rank)] and got['snapshots']==full['capture_stamps'][base.name][str(rank)],'exact closed target map/stamp')
    extent+=got['payload_bytes']
   require(extent==221743168,'full target state extent')
  checked=[];names=[];number=0
  for row,definition in zip(full['warmup'],manifest['warmup']):
   number+=1;require(row['request']==number and row['mode']==definition['mode'] and row['prompt_tokens']==definition['tokens'] and not row['measured'],'excluded warmup')
   require(read(EVIDENCE/row['name']/'suite-request.json')==row,'raw warmup');B.timing(row['result'],8,False);B.confirmed_inputs(row['result'],row['prompt_tokens'])
   for rank in (0,1):require(read(EVIDENCE/row['name']/f'rank{rank}/reset.json')['allocation_ids_preserved'],'warmup reset')
  for i,pair in enumerate(full['prompts']):
   definition=manifest['prompts'][i];require(pair['prompt_id']==definition['prompt_id'] and pair['order']==definition['order'] and pair['exact_tokens'] and pair['exact_final_target_state'],'original prompt/order/pair')
   require(read(EVIDENCE/f'pair-{i:02d}.json')==pair,'raw pair');arms=[]
   for row,mode in zip(pair['arms'],definition['order']):
    number+=1;name=f'prompt-{i:02d}-{mode}';names.append(name);ref=refs[name]
    require(row['request']==number and row['name']==name and row['mode']==mode and row['measured'] and row['requested_max_new']==128,'arm schedule')
    require(row['prompt_tokens']==ref['prompt_tokens']==definition['tokens'] and row['result']['tokens']==ref['result']['tokens'] and row['state_sha256']==ref['state_sha256'],'exact baseline tokens/state map')
    base=EVIDENCE/name;require(read(base/'suite-request.json')==row,'raw arm');marker=read(base/'baseline-exact.json');require(marker['passed'] and marker['reference_sha256']==prior['full_result_sha256'],'live exact gate')
    for rank in (0,1):
     reset=read(base/f'rank{rank}/reset.json');require(reset['passed'] and reset['allocation_ids_preserved'],'full RESET')
    states(base,row['state_sha256']);metric=B.timing(row['result'],128);consumed=B.confirmed_inputs(row['result'],row['prompt_tokens'])
    if mode=='mtp':B.guess_outcomes(row['result'],row['prompt_tokens'],128)
    else:require(all(row['result']['stats'][k]==0 for k in ('guesses','hits','misses')),'target stats')
    for k in ('output_tokens','decode_intervals','termination'):require(metric[k]==row['metric'][k],'metric identity')
    B.near(metric['decode_wall_ms'],row['metric']['decode_wall_ms'],'raw duration')
    arms.append(dict(name=name,mode=mode,tokens=row['result']['tokens'],timing=metric,stats=row['result']['stats'],consumed_positions=consumed,baseline_tokens_exact=True,baseline_state_exact=True))
   require(arms[0]['tokens']==arms[1]['tokens'] and pair['arms'][0]['state_sha256']==pair['arms'][1]['state_sha256'],'pair exact')
   checked.append(dict(prompt_id=pair['prompt_id'],order=pair['order'],arms=arms))
  require(number==26 and len(names)==24,'all26 requests')
  require({p.parent.name for p in EVIDENCE.glob('prompt-*/baseline-exact.json')}==set(names),'exactly24 live arm gates')
  derived=B.aggregate(checked);B.compare_summary(derived,full['summary']['order_groups']);B.compare_summary(derived,term['result']['summary']['order_groups'])
  ledger=read(CAND/'operating/candidate-ledger.json')['scenarios']['split24-24_mtp-rank0']['ranks'];owners=[];memory=[]
  for rank in (0,1):
   owner=read(EVIDENCE/f'rank{rank}/receipt.json');require(owner['passed'] and owner['rank']==rank and not owner['error'] and len(owner['teardown'])==1,'clean owner receipt');t=owner['teardown'][0]
   require(t['safe_to_exit'] and t['in_flight']==t['live_bytes']==t['exit_code']==0,'safe teardown');owners.append(t)
   census=read(EVIDENCE/f'rank{rank}/census.json');amount=sum(a['bytes'] for a in census['allocations'] if a['live'] and a['memory']=='device');require(amount==census['totals']['device']==ledger[rank]['device_logical_bytes'],'memory forecast');memory.append(amount)
  require(memory==[30994676618,29966053268],'unchanged exact device allocation totals')
  ownership=read(EVIDENCE/'ownership.json');require(ownership['returncodes']==[0,0] and not ownership['retained_pids'] and ownership['signals_sent']==0 and not ownership['stop_requested'],'clean process closure')
  require(set(names)==set(refs),'all original24 baseline arms')
  dump_roots=[p.parent for p in EVIDENCE.rglob('state.json') if p.parent.name.startswith('state-')]
  expected_bases=[EVIDENCE]+[EVIDENCE/w['name'] for w in full['warmup']]+[EVIDENCE/name for name in names]
  require(len(dump_roots)==54 and {p.parent for p in dump_roots}=={base/f'rank{rank}' for base in expected_bases for rank in (0,1)},'exact27 paired dump groups')
  receipt.update(passed=True,bundles=54,bundle_captures=captures,original_index_sha256=OLD_INDEX_SHA,initial_and_warmup_semantic_baseline_required=False,explicit_final_repeat_and_closed_stamps_verified=True,requests=26,measured_arms=24,exact_pairs=12,all12_exact=True,reset_requests=26,paired_state_dump_groups=27,same_persistent_rank_pair=True,baseline_review_sha256=PRIOR_SHA,baseline_result_sha256=prior['full_result_sha256'],plan_sha256=sha(CONTROL/'plan.json'),full_result_sha256=sha(fullpath),native_binary_sha256=BINARY,rank_pids=full['rank_pids'],prompts=checked,descriptive_timing=derived,owners=owners,ownership=ownership,actual_device_bytes=memory,physical_drain=True,kernel_fault_baseline_unchanged=True,artifact_count=len(digests),indexed_bytes=total,index_sha256=sha(D/'artifact-index.jsonl.gz'),limitations=['Exact same-model original-baseline tokens and target-state qualification; not an external-engine or general model-quality evaluation','All timing samples and early EOS retained; no cross-binary causal speed claim from separate sessions','Original baseline rawfiles may be archived; immutable index lengths/hashes, full-result maps and independent full-readback authority remain bound','Initial/warmup captures have sealed payload/inventory/length verification; their baseline hash differences are reported without claiming deterministic initialization','This116-site dense block implementation must independently pass original full-state and both physical-contact gates; its isolated micro timings do not establish a full-engine speedup','Physical ownership/fault findings use retained evidence; reviewer performs no live host/device queries'])
 except BaseException as e:receipt['error']=type(e).__name__+': '+str(e);raise
 finally:
  receipt.update(auditor_sha256=sha(__file__),immediate_parent_auditor_sha256=IMMEDIATE_PARENT_SHA,parent_auditor_sha256=BASE_SHA,fullsuite_parent_sha256=PARENT_AUDITOR_SHA,bundle_parser_sha256=BUNDLE_AUDITOR_SHA,elapsed_seconds=time.monotonic()-start)
  with (D/'review.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 print(json.dumps({'passed':True,'exact_arms':24,'requests':26,'review_sha256':sha(D/'review.json')}))
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True,action='store_true');ap.add_argument('--plan-sha256',required=True);args=ap.parse_args();require(len(args.plan_sha256)==64 and all(c in '0123456789abcdef' for c in args.plan_sha256),'fixed plan SHA');run(args.plan_sha256)

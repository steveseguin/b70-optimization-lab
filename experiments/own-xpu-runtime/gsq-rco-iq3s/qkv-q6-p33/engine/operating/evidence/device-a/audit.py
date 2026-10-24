#!/usr/bin/env python3
"""Closed full combined-candidate audit; --run ONLY after root authorizes drained readback.
No operational imports or device/service/model access. One resident qualification.
"""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json,os,resource,time
D=Path(__file__).resolve().parent;P=D.parents[1];CAND=P.parent;L=CAND.parents[1];R=L.parents[2]
BASE=L/'baseline/audit.py';BASE_SHA='43154e5b8101fb879eb08bbbebc29714443dd083cb90df6fbbb7e269d522d0ab'
assert hashlib.sha256(BASE.read_bytes()).hexdigest()==BASE_SHA
s=importlib.util.spec_from_file_location('completion_baseline_audit_helpers',BASE);B=importlib.util.module_from_spec(s);s.loader.exec_module(B)
read,sha,require=B.read,B.sha,B.require
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-attention-qkv-p33-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-attention-qkv-p33-a')
PRIOR=L/'baseline/evidence/independent-a/review.json';PRIOR_SHA='f662fcecf93c92f90006c09c05d4a4c02e71e84ae9d8c82dbff3fdfc39ebb5bb'
BINARY='401918bb0fb21db3cd0006dd2ddb7f5047b42e7b8959953050fa60a9ea83f0b4'
REFERENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a/resident-suite.json')
STORAGE_SHA='a7136c09bce458a9a2ffdceeed3a078441f6751eeff5083c8a017364a877b1ed'
STORAGE_COMPLETE_SHA='ab7a26e4c7993693e0b6d18bf8c714c80ad40922180a5ae6830b04bf5488cff0'
def storage_join(plan_sha):
 path=P/'evidence/storage-admission.json';require(sha(path)==STORAGE_SHA,'fixed storage admission');storage=read(path)
 require(storage['passed'] and storage['schema']=='gsq.combined.storage-admission.v1' and storage['plan_sha256']==plan_sha,'storage launch binding')
 require(storage['completed_archives']==27 and storage['removed_files']==56981 and storage['removed_bytes']==6113156852 and storage['hard_file_record_quota'] is False,'storage scope/counts')
 complete_path=L/'storage/attention-closed/evidence/complete.json'
 require(Path(storage['storage_complete_path'])==complete_path and sha(complete_path)==storage['storage_complete_sha256']==STORAGE_COMPLETE_SHA,'completed storage authority')
 for path,h in storage['source_sha256'].items():require(sha(path)==h,'storage prerequisite')
 complete=read(complete_path);require(complete['passed'] and len(complete['batches'])==27,'completed27 batches')
 expected={(profile,i) for profile,n in [('prefix',14),('completion',13)] for i in range(n)}
 require({(x['profile'],x['batch']) for x in complete['batches']}==expected,'exact archive batch identities')
 counts=raw=archives=0
 for batch in complete['batches']:
  phases={}
  for name,h in batch['phase_sha256'].items():
   path=R/name;require(sha(path)==h,'archive phase source');row=read(path);mode=path.stem.rsplit('-',1)[1];phases[mode]=row
   require(row['passed'] and row['archive_sha256']==batch['sha256'],'archive phase outcome/hash')
   require(all(row['authority'][k]==batch[k] for k in ('profile','batch','name')),'archive phase group')
  require(set(phases)=={'archive','prune','offload','release'},'four completed archive phases')
  a,q,o,r=(phases[k] for k in ('archive','prune','offload','release'))
  require(a['phase']=='all-members-readback-verified' and q['phase']=='audited-bin-files-pruned' and o['phase']=='USB-archive-readback-verified' and r['phase']=='local-archive-released-after-verified-USB-copy','exact phase states')
  require(a['entries']==q['removed']==batch['removed_files'] and a['source_bytes']==q['removed_bytes']==batch['removed_bytes']==batch['raw_bytes'],'archive/prune totals')
  require(a['archive_bytes']==o['archive_bytes']==batch['archive_bytes'] and o['usb']==r['usb']==batch['usb'],'offload/release identity')
  require(o['usb_identity'][0]==a['source_root_identity'][0]!=a['archive_identity'][0],'cross-device verified offload')
  require(q['source_json_and_directories_untouched'] and r['metadata_and_restore_map_retained'],'metadata preservation')
  counts+=q['removed'];raw+=q['removed_bytes'];archives+=o['archive_bytes']
 require(counts==complete['removed_files']==56981 and raw==complete['removed_bytes']==6113156852 and archives==complete['archive_bytes']==2326406928,'complete totals')
 require(storage['known_record_capacity_estimate']==86156 and storage['new_file_forecast']==61147 and storage['estimated_file_margin']==25009,'record estimate unchanged')
 return dict(admission_sha256=STORAGE_SHA,complete_sha256=STORAGE_COMPLETE_SHA,completed_archives=27,phase_receipts=108,removed_files=counts,removed_bytes=raw,archive_bytes=archives,hard_file_record_quota=False,scope='Retained phase receipt/hash joins only; no archive reread, physical free-record reservation or active filesystem query')
def run():
 require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19');require(os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper cores');resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 require(not (D/'review.json').exists() and not (D/'artifact-index.jsonl.gz').exists(),'exclusive audit outputs')
 start=time.monotonic();receipt=dict(schema='ownrt.gsq.attention-qkv-independent-device.v1',passed=False,scope='All24 baseline-exact measured arms in one persistent rank pair; descriptive same-run target/MTP timings',combined_timing_claim=False,device_executed_by_reviewer=False)
 try:
  require(sha(PRIOR)==PRIOR_SHA,'immutable independent baseline authority');prior=read(PRIOR)
  require(prior['passed'] and prior['all12_exact'] and sha(REFERENCE)==prior['full_result_sha256'],'baseline authority');baseline=read(REFERENCE);refs={a['name']:a for p in baseline['prompts'] for a in p['arms']}
  plan=read(CONTROL/'plan.json');ad=read(CONTROL/'admission.json');term=read(CONTROL/'terminal.json')
  require(term['plan_sha256']==ad['plan_sha256']==sha(CONTROL/'plan.json') and ad['plan']==plan,'plan identity')
  require(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()==ad['canonical_plan_sha256'],'canonical plan')
  for k,v in plan['unit_properties'].items():require(ad['unit'][k]==v,'safe coordinator property')
  B.validate_passive(ad['before'],term['after'],term)
  require(sha(CONTROL/'storage-admission.json')==STORAGE_SHA,'retained control storage admission')
  storage=storage_join(sha(CONTROL/'plan.json'))
  require(plan['requests']==plan['suite']['total_requests']==26 and plan['suite']['measured_requests']==24,'fixed full suite')
  require(plan['suite']['storage']['retained_state_dumps']==27 and plan['suite']['storage']['evidence_forecast_bytes']==6316056364,'27-dump admission')
  require(plan['suite']['baseline_review_sha256']==PRIOR_SHA and plan['suite']['baseline_result_sha256']==prior['full_result_sha256'],'baseline admission')
  for mapping in (plan['source_sha256'],plan['suite']['source_sha256'],plan['adapter']['source_sha256']):
   for p,h in mapping.items():require(sha(R/p)==h,'admitted source '+p)
  native=read(plan['adapter']['build_receipt']);require(native['passed'] and native['mode']=='native' and sha(plan['adapter']['build_receipt'])==plan['adapter']['build_receipt_sha256'],'native receipt')
  require(sha(plan['adapter']['binary'])==native['binary_sha256']==plan['adapter']['binary_sha256']==BINARY,'same candidate binary')
  for mapping in (native['source_sha256'],native['object_sha256']):
   for p,h in mapping.items():require(sha(R/p)==h,'native source/object '+p)
  fullpath=Path(term['result']['full_result_path']);require(fullpath==EVIDENCE/'resident-suite.json' and sha(fullpath)==term['result']['full_result_sha256'],'full result binding');full=read(fullpath)
  manifest=read(L/'baseline/manifest.json');require(full['manifest_sha256']==sha(L/'baseline/manifest.json')==plan['suite']['manifest_sha256'],'original corpus')
  require(full['passed'] and full['requests']==26 and full['measured_requests']==24 and len(full['prompts'])==12 and len(full['warmup'])==2,'complete full suite')
  require(full['rank_pids']==[x[0] for x in term['rank_identities']],'same persistent ranks')
  digests={};sizes={};total=0
  with (D/'artifact-index.jsonl.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as z:
   for label,root in [('control',CONTROL),('evidence',EVIDENCE)]:
    for p in sorted(root.rglob('*')):
     require(not p.is_symlink(),'artifact symlink')
     if not p.is_file():continue
     n=p.stat().st_size
     require(total+n<=7*1024**3 and len(digests)<65000,'bounded readback before file hash')
     h=sha(p);require(p.stat().st_size==n,'stable indexed extent');digests[str(p)]=h;sizes[str(p)]=n;total+=n
     z.write((json.dumps(dict(root=label,path=str(p.relative_to(root)),bytes=n,sha256=h),separators=(',',':'))+'\n').encode())
  def states(base,expected):
   extent=0
   for rank in (0,1):
    root=base/f'rank{rank}/state-2147483647';actual={str(p.relative_to(root)):digests[str(p)] for p in root.rglob('*') if p.is_file()}
    require(actual==expected[str(rank)] and actual,'exact raw target state')
    for key,h in read(root/'state.json')['buffers'].items():
     f=('alternate-'+key.split(':',1)[1] if key.startswith('alternate:') else key)+'.bin';require(actual[f]==h,'native state manifest')
    extent+=sum(sizes[str(p)] for p in root.glob('*.bin'))
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
  ownership=read(EVIDENCE/'ownership.json');require(ownership['returncodes']==[0,0] and not ownership['retained_pids'] and ownership['signals_sent']==0 and not ownership['stop_requested'],'clean process closure')
  require(set(names)==set(refs),'all original24 baseline arms')
  dump_roots=[p.parent for p in EVIDENCE.rglob('state.json') if p.parent.name.startswith('state-')]
  expected_bases=[EVIDENCE]+[EVIDENCE/w['name'] for w in full['warmup']]+[EVIDENCE/name for name in names]
  require(len(dump_roots)==54 and {p.parent for p in dump_roots}=={base/f'rank{rank}' for base in expected_bases for rank in (0,1)},'exact27 paired dump groups')
  for root in dump_roots:
   for key,h in read(root/'state.json')['buffers'].items():
    file=('alternate-'+key.split(':',1)[1] if key.startswith('alternate:') else key)+'.bin'
    require(digests[str(root/file)]==h,'every retained dump buffer hash')
  receipt.update(passed=True,storage_admission=storage,requests=26,measured_arms=24,exact_pairs=12,all12_exact=True,reset_requests=26,paired_state_dump_groups=27,same_persistent_rank_pair=True,baseline_review_sha256=PRIOR_SHA,baseline_result_sha256=prior['full_result_sha256'],plan_sha256=sha(CONTROL/'plan.json'),full_result_sha256=sha(fullpath),native_binary_sha256=BINARY,rank_pids=full['rank_pids'],prompts=checked,descriptive_timing=derived,owners=owners,ownership=ownership,actual_device_bytes=memory,physical_drain=True,kernel_fault_baseline_unchanged=True,artifact_count=len(digests),indexed_bytes=total,index_sha256=sha(D/'artifact-index.jsonl.gz'),limitations=['Exact same-model original-baseline tokens and target-state qualification; not an external-engine or general model-quality evaluation','All timing samples and early EOS retained; no cross-binary causal speed claim from separate sessions','Original baseline rawfiles may be archived; immutable full-result maps and independent full-readback authority remain bound','Physical ownership/fault findings use retained evidence; reviewer performs no live host/device queries'])
 except BaseException as e:receipt['error']=type(e).__name__+': '+str(e);raise
 finally:
  receipt.update(auditor_sha256=sha(__file__),parent_auditor_sha256=BASE_SHA,elapsed_seconds=time.monotonic()-start)
  with (D/'review.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 print(json.dumps({'passed':True,'exact_arms':24,'requests':26,'review_sha256':sha(D/'review.json')}))
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',required=True,action='store_true');ap.parse_args();run()

#!/usr/bin/env python3
"""Post-completion CPU-only exact comparison. Streams archives/bundles: run ONLY
once parent releases completed runs. Does not extract archived baseline payloads.
Baseline payload authority is its verified full-tar-compare archive receipt plus
native sealed per-entry/bundle SHA; archive path/size and completed independent control payload proof are checked;
archive SHA is NOT reread in this proof. Candidate
payload is streamed in full against every index entry and native bundle seal.
"""
import argparse,hashlib,json,os,pathlib,stat,struct

def need(ok,msg):
 if not ok:raise ValueError(msg)
def raw(p):
 p=pathlib.Path(p);need(not p.is_symlink() and p.is_file(),'regular source '+str(p));return p.read_bytes()
def read(p):return json.loads(raw(p))
def sha(b):return hashlib.sha256(b).hexdigest()
def identity(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def filehash(p):
 p=pathlib.Path(p);h=hashlib.sha256()
 with p.open('rb') as f:
  before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode) and not p.is_symlink(),'regular payload')
  while b:=f.read(4*1024**2):h.update(b)
  need(identity(before)==identity(os.fstat(f.fileno()))==identity(p.stat()),'payload changed')
 return h.hexdigest()
def sealed(dump,actual):
 index=raw(dump/'state-index.tsv');state=raw(dump/'state.json');seal=raw(dump/'state-seal.txt').decode().splitlines()
 need(len(seal)==5 and seal[0]=='GSQ_STATE_SEAL_V1' and sha(index)==seal[3] and sha(state)==seal[4],'native metadata seal')
 lines=index.decode().splitlines();need(lines[0]=='GSQ_STATE_BUNDLE_V1','bundle version');entries={};end=0
 for line in lines[1:]:
  name,off,size,digest=line.split('\t');off,size=int(off),int(size)
  need(name not in entries and off==end and size>0 and len(digest)==64,'contiguous native index')
  entries[name]={'offset':off,'bytes':size,'sha256':digest};end+=size
 need(end==int(seal[1]),'native bundle extent')
 if actual:
  bundle=dump/'state.bundle';need(not bundle.is_symlink() and bundle.stat().st_size==end,'actual bundle extent')
  whole=hashlib.sha256()
  with bundle.open('rb') as f:
   before=os.fstat(f.fileno())
   for name,e in entries.items():
    h=hashlib.sha256();left=e['bytes']
    while left:
     b=f.read(min(left,4*1024**2));need(b,'bundle truncated');left-=len(b);h.update(b);whole.update(b)
    need(h.hexdigest()==e['sha256'],'actual entry hash '+name)
   need(not f.read(1) and identity(before)==identity(os.fstat(f.fileno()))==identity(bundle.stat()),'bundle changed')
  need(whole.hexdigest()==seal[2],'actual full bundle SHA')
 return {'entries':entries,'state':json.loads(state),'bundle_sha256':seal[2],'bytes':end,'seal_sha256':sha(raw(dump/'state-seal.txt'))}
def roles(root):
 out=root/'output';r={s:out/s/'native/state-2147483647' for s in ['stage0','stage1']}
 for kind in ['dump','finish']:
  found=list((out/'stageprovider/native').glob('provider-'+kind+'-*'));need(len(found)==1,'unique provider '+kind);r['provider-'+kind]=found[0]
 return r
def terminal(root):
 t=read(root/'output/terminal.json');need(t['passed'] is True and t['error'] is None and not t['live_pids'] and len(t['returncodes'])==3 and all(v==0 for v in t['returncodes'].values()),'clean three-owner FINISH')
 events=[json.loads(s) for s in raw(root/'output/tokens.jsonl').decode().splitlines()];need(len(events)==512 and [e['index'] for e in events]==list(range(512)),'512 ordered output events')
 ids=[e['token'] for e in events];d=read(root/'output/driver-result.json');need(d['output_ids']==ids and d['passed'] is True,'actual result/token identity')
 times=[e['committed_monotonic_s'] for e in events];need(all(b>a for a,b in zip(times,times[1:])),'strict emission clock')
 timing={'event1_s':events[0]['emitted_elapsed_s'],'event100_s':events[99]['emitted_elapsed_s'],'event512_s':events[511]['emitted_elapsed_s'],'request_wall_s':d['scheduler_wall_seconds'],'lifecycle_wall_s':d['wall_seconds'],'first99_tps':99/(times[99]-times[0]),'all511_tps':511/(times[511]-times[0])}
 census={s:read(root/'output'/s/'native/census.json')['totals'] for s in ['stage0','stage1','stageprovider']}
 return {'terminal':t,'timing':timing,'output_ids':ids,'output_ids_i32_sha256':sha(struct.pack('<512i',*ids)),'censuses':census}
def request_identity(root,plan):
 config=read(root/'config.json')
 need(plan['config']==str(root/'config.json') and plan['output']==config['output']==str(root/'output'),'actual fresh config/output paths')
 need(config['dedicated_prefill_prompt']==plan['dedicated_prefill_prompt']==str(root/'prompt.i32'),'actual fresh prompt path')
 prompt=raw(root/'prompt.i32');need(sha(prompt)==config['dedicated_prefill_prompt_sha256']==plan['dedicated_prefill_prompt_sha256'],'same-content actual immutable prompt')
 need(prompt==struct.pack('<%di'%len(plan['prompt_tokens']),*plan['prompt_tokens']),'actual prompt LEi32 bytes')
 identity=dict(model=plan['model_identity_sha256'],draft_manifest=config['trusted_draft_manifest_sha256'],
  prompt=plan['prompt_tokens'],context=plan['context'],max_new=plan['max_new'],vocab=plan['vocab'],
  eos=config['eos_token_ids'],depth=config.get('speculative_depth',3),boundaries=config['boundaries'],
  target_bdfs=[o['bdf'] for o in plan['stages']],provider_bdf=config['provider_bdf'],
  check_policy=config.get('check_policy','qualification'),config_sha256=sha(raw(root/'config.json')),mode='dedicated-mtp')
 if config.get('dedicated_bulk_prefill',False):identity.update(dedicated_bulk_prefill=True,prefill_rows=plan['prefill_rows'],prompt_i32_sha256=sha(prompt))
 if config.get('dedicated_prefill_pipeline',False):identity['dedicated_prefill_pipeline']=True
 if config.get('dedicated_prefill_slots',2)==4:identity['dedicated_prefill_slots']=4
 digest=sha(json.dumps(identity,sort_keys=True,separators=(',',':')).encode())
 need(digest==plan['request_sha256'],'reconstructed actual request identity')
 return config,identity

def run(reference,candidate,result,baseline_payload_proof):
 result.update({'schema':'ownrt.bounded-controller-comparison.v1','reference':str(reference),'candidate':str(candidate),'passed':False})
 result['source_receipts']={'comparator':{'path':str(pathlib.Path(__file__).resolve()),'sha256':sha(raw(__file__))}}
 for name in ['source-pins.json','cpu-result-r1.json','candidate.patch']:
  f=pathlib.Path(__file__).resolve().parent/name
  result['source_receipts'][name]={'path':str(f),'sha256':sha(raw(f))}
 for label,root in [('reference',reference),('candidate',candidate)]:
  for f in root.glob('*registration*.json'):
   result['source_receipts'][label+':'+f.name]={'path':str(f),'sha256':sha(raw(f))}
  for owner in ['stage0','stage1','stageprovider']:
   f=root/'output'/owner/'native/receipt.json'
   result['source_receipts'][label+':'+owner+':native-receipt']={'path':str(f),'sha256':sha(raw(f))}
 # Refuse unfinished requests BEFORE any multi-GB reads.
 a,b=terminal(reference),terminal(candidate);result['runs']={'reference':a,'candidate':b}
 need(a['output_ids']==b['output_ids'],'exact512 actual output IDs')
 result['census_comparison']={}
 for owner in ['stage0','stage1','stageprovider']:
  x,y=raw(reference/'output'/owner/'native/census.json'),raw(candidate/'output'/owner/'native/census.json')
  result['census_comparison'][owner]={'totals_equal':a['censuses'][owner]==b['censuses'][owner],
   'full_bytes_equal':x==y,'reference_sha256':sha(x),'candidate_sha256':sha(y)}
 need(a['censuses']==b['censuses'],'three allocation census totals identical')
 pa,pb=read(reference/'output/plan.json'),read(candidate/'output/plan.json')
 keys=['prompt_tokens','max_new','context','vocab','boundaries','model_identity_sha256',
       'draft_model_sha256','speculative_depth','dedicated_prefill_prompt_sha256',
       'dedicated_prefill_slots','dedicated_prefill_pipeline','dedicated_capture_ready']
 need(all(k in pa and k in pb and pa[k]==pb[k] for k in keys),'matched exact actual plan identity')
 ca,ia=request_identity(reference,pa);cb,ib=request_identity(candidate,pb)
 differences={k:[ca.get(k),cb.get(k)] for k in ca.keys()|cb.keys() if ca.get(k)!=cb.get(k)}
 need(set(differences)=={'output','dedicated_prefill_prompt'},'config differs only fresh output and same-content prompt paths')
 semantic_a={k:v for k,v in ia.items() if k!='config_sha256'};semantic_b={k:v for k,v in ib.items() if k!='config_sha256'}
 need(semantic_a==semantic_b,'exact semantic request identity except config file digest')
 need(raw(ca['build_receipt'])==raw(cb['build_receipt']),'same native compiler/kernel build receipt')
 def normalized(value,root,request):
  return json.dumps(value,sort_keys=True).replace(str(root),'<RUN_ROOT>').replace(request,'<REQUEST_SHA>')
 need(normalized(pa['stages'],reference,pa['request_sha256'])==normalized(pb['stages'],candidate,pb['request_sha256']) and
      normalized(pa['provider'],reference,pa['request_sha256'])==normalized(pb['provider'],candidate,pb['request_sha256']),
      'identical actual native argv/environment/role except run paths and request digest')
 result['request_identity']={'reference':pa['request_sha256'],'candidate':pb['request_sha256'],
  'reconstructed_both':True,'semantic_identity_equal':True,'config_differences':differences,
  'cause':'request identity includes config_sha256; config bytes differ ONLY fresh output/prompt path strings, not scheduler source pins',
  'native_build_receipt_sha256':sha(raw(ca['build_receipt']))}
 result['plan_identity_keys']=keys
 result['plan_sha256']={'reference':sha(raw(reference/'output/plan.json')),'candidate':sha(raw(candidate/'output/plan.json'))}
 archive=read(reference/'archive.json');need(archive['full_tar_compare_passed'] is True and archive['deleted_only_compared_completed_files'] is True,'verified baseline archive receipt')
 ap=pathlib.Path(archive['archive']);need(ap.is_file() and not ap.is_symlink() and ap.stat().st_size==archive['archive_bytes'],'unchanged retained archive path/size')
 authority=read(baseline_payload_proof)
 need(authority['schema']=='ownrt.matched-state-payload-deduplication.v1' and authority['candidate_archive']==archive
      and authority['metadata_byte_identical'] is True and authority['deleted_only_fully_compared_completed_payloads'] is True,
      'previous full archive vs independent actual control payload authority')
 result['baseline_archive']=archive
 result['baseline_payload_authority']={'path':str(baseline_payload_proof),'sha256':sha(raw(baseline_payload_proof)),
  'archive_sha_reread_this_proof':False,'archive_path_size_unchanged':True,
  'scope':'Reuses previously hash-verified/full-tar-compared archive and subsequent full archived-vs-control byte comparison; candidate payload fully streamed NOW'}
 ra,rb=roles(reference),roles(candidate);comparisons={};result['states']=comparisons;canonical={}
 for role in ra:
  need(str((ra[role]/'state.bundle').relative_to(reference)) in archive['exact_paths'],'reference dump was verified archived member')
  comparisons[role]={'reference_dump':str(ra[role]),'candidate_dump':str(rb[role]),'validation':'started'}
  old,new=sealed(ra[role],False),sealed(rb[role],True)
  prior=authority['matched_full_payloads'][str((ra[role]/'state.bundle').relative_to(reference))]
  need(prior['full_archived_candidate_vs_actual_control_byte_comparison'] is True and
       prior['bytes']==old['bytes'] and prior['sha256']==old['bundle_sha256'],'prior verified full payload matches native reference seal')
  comparisons[role].update(validation='own-seals-and-full-candidate-stream-passed',
   whole_bundle_equal_before_exclusions=old['bundle_sha256']==new['bundle_sha256'],
   reference_bundle_sha256=old['bundle_sha256'],candidate_bundle_sha256=new['bundle_sha256'])
  need(set(old['entries'])==set(new['entries']),'same full native state inventory '+role)
  excluded=[]
  if role.startswith('stage'):
   meta=read(ra[role].parent/'pipeline-stage.json');other=read(rb[role].parent/'pipeline-stage.json')
   need(meta['inactive_alternate_banks']==other['inactive_alternate_banks'],'same native bank ownership')
   excluded=['alternate-'+n+'.bin' for n in meta['inactive_alternate_banks']]
   if role=='stage0':excluded+=['streams.bin','next_token.bin']
   # Only documented spare banks and nonfinal head scratch are noncanonical.
   # Every excluded payload is STILL fully hashed against its OWN native seal.
  else:
   need(len(new['entries'])==73,'complete actual draft73 inventory')
   comparisons[role]['state_metadata_equal']=old['state']==new['state']
   need(old['state']==new['state'],'complete provider host/layout/buffer metadata '+role)
  diffs=[];comparisons[role].update(excluded=excluded,mismatches=diffs)
  for name,e in old['entries'].items():
   f=new['entries'][name];need(e['bytes']==f['bytes'],'native typed extent '+role+name)
   if name not in excluded:
    if e['sha256']!=f['sha256']:diffs.append(name)
    if role.startswith('stage'):
     if name in canonical:need(canonical[name]==f['sha256'],'same replicated global state '+name)
     canonical[name]=f['sha256']
  if role.startswith('stage'):
   same={k:v for k,v in old['state'].items() if k!='buffers'}=={k:v for k,v in new['state'].items() if k!='buffers'}
   comparisons[role]['state_metadata_equal_except_buffers']=same
   need(same,'target sealed host metadata '+role)
  comparisons[role].update({'reference_dump':str(ra[role]),'candidate_dump':str(rb[role]),'entries':len(old['entries']),'compared_entries':len(old['entries'])-len(excluded),'excluded':excluded,'mismatches':diffs,'reference_bundle_sha256':old['bundle_sha256'],'candidate_bundle_sha256':new['bundle_sha256'],'candidate_bytes_fully_streamed':new['bytes'],'reference_seal_sha256':old['seal_sha256'],'candidate_seal_sha256':new['seal_sha256']})
 result['states']=comparisons;result['canonical_target_entries']=len(canonical)
 result['exclusion_rationale']='Only native-declared inactive temporal alternate banks and nonfinal target streams/next_token head scratch lack canonical ownership; every excluded byte still validated against its own native seal.'
 need(len(canonical)==2065,'complete target2065 canonical inventory')
 need(len(comparisons['provider-dump']['mismatches'])==0 and len(comparisons['provider-finish']['mismatches'])==0,'all73 draft entries exact')
 need(all(not v['mismatches'] for v in comparisons.values()),'canonical state parity')
 result['passed']=True;return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('reference',type=pathlib.Path);p.add_argument('candidate',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);p.add_argument('--baseline-payload-proof',type=pathlib.Path,required=True);a=p.parse_args()
 need(not a.output.exists(),'fresh exclusive proof output')
 result={}
 try:
  run(a.reference,a.candidate,result,a.baseline_payload_proof)
 except Exception as error:
  result['passed']=False;result['error']={'type':type(error).__name__,'message':str(error)}
 with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({'passed':result['passed'],'proof':str(a.output),'sha256':sha(raw(a.output))}))
 if not result['passed']:raise SystemExit(1)

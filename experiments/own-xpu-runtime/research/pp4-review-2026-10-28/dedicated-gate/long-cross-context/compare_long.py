#!/usr/bin/env python3
"""Registered121854/512 128K two-target to262K three-target comparison.
Source-only until coordinator release. No device work or archive extraction.
"""
import argparse, contextlib, hashlib, importlib.util, json, os, pathlib, stat, struct, sys, tempfile
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import compare as P
import compare_context as X
from measured_target import measured_target_candidate
spec=importlib.util.spec_from_file_location('long_completed',HERE.parent/'bounded-live-count-candidate/compare_completed.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
need,read,raw,sha=C.need,C.read,C.raw,C.sha

def roles(root,plan):
 out={f'stage{s["id"]}':pathlib.Path(s['native_output'])/'state-2147483647' for s in plan['stages']}
 provider=pathlib.Path(plan['provider']['native_output'])
 for kind in ('dump','finish'):
  found=list(provider.glob('provider-'+kind+'-*'));need(len(found)==1,'unique provider '+kind);out['provider-'+kind]=found[0]
 need(all(p.is_relative_to(root/'output') for p in out.values()),'actual native output ownership')
 return out

def terminal(root,plan):
 owners={str(s['id']) for s in plan['stages']}|{'provider'}
 t=read(root/'output/terminal.json');d,_=P.driver_result(root/'output/driver-result.json')
 need(t['passed'] is True and not t['error'] and not t['live_pids'] and set(t['returncodes'])==owners
      and all(type(v)is int and v==0 for v in t['returncodes'].values()),'all actual owners clean')
 need(d['passed'] is True and d['input_position']==122365 and len(d['output_ids'])==512,'actual long frontier/output count')
 events=[json.loads(x)for x in raw(root/'output/tokens.jsonl').splitlines()]
 need([e['index']for e in events]==list(range(512)) and [e['token']for e in events]==d['output_ids'],'actual ordered512 token events')
 censuses={}
 for native in [pathlib.Path(s['native_output']) for s in plan['stages']]+[pathlib.Path(plan['provider']['native_output'])]:
  receipt=read(native/'receipt.json');need(receipt['passed'] is True and not receipt.get('error') and receipt.get('teardown'),'native receipt')
  need(all(x['status']=='complete' and x['safe_to_exit'] is True and x['idle_marker_complete'] is True and x['in_flight']==x['live_bytes']==0 and not x['error'] for x in receipt['teardown']),'native teardown')
  census=read(native/'census.json');need(census['totals']['device']<=30*1024**3,'actual census respects existing30GiB cap')
  totals={k:sum(a['bytes'] for a in census['allocations'] if a['live'] and a['memory']==k)for k in census['totals']}
  need(totals==census['totals'],'complete actual live allocation census totals')
  censuses[str(native)]={'totals':census['totals'],'sha256':sha(raw(native/'census.json'))}
 return d,dict(terminal=t,censuses=censuses,output_ids_i32_sha256=sha(struct.pack('<512i',*d['output_ids'])))

def archive_authority(root,role_paths,reuse_path):
 reuse=read(reuse_path);need(reuse['schema']=='ownrt.exact-state-archive-reuse.v1' and reuse['baseline_archive_previously_fully_verified'] is True and reuse['deleted_only_proven_files'] is True,'explicit previously verified archive reuse')
 proof=pathlib.Path(reuse['quality_proof']);need(sha(raw(proof))==reuse['quality_proof_sha256'] and read(proof)['passed'] is True,'archive reuse exact completed payload proof')
 need(read(proof)['candidate']==str(root),'archive proof actual reference root')
 prior=read(proof)['baseline_archive'];receipt=pathlib.Path(prior['receipt']);need(sha(raw(receipt))==prior['receipt_sha256'],'prior full archive receipt hash')
 ar=read(receipt);need(ar['full_tar_compare_passed'] is True and ar['deleted_only_compared_completed_files'] is True and ar['sha256']==reuse['baseline_archive_sha256'] and ar['archive']==reuse['baseline_archive'],'fully verified prior archive authority')
 archive=pathlib.Path(reuse['baseline_archive']);need(archive.is_file() and not archive.is_symlink() and archive.stat().st_size==ar['archive_bytes'],'retained baseline archive exact size')
 # Its prior full hash/byte comparison is authority; deliberately do not reread7GB archive.
 members={r['candidate']:r for r in reuse['fully_streamed_candidate_payloads']}
 for dump in role_paths.values():
  key=str((dump/'state.bundle').relative_to(root));need(key in members,'reference payload archive mapping')
  old=C.sealed(dump,False);record=members[key]
  need((record['bytes'],record['sha256'])==(old['bytes'],old['bundle_sha256']) and record['baseline_archive_member'],'reference seal matches prior fully streamed payload')
 return dict(receipt=str(reuse_path),receipt_sha256=sha(raw(reuse_path)),archive=str(archive),prior_archive_sha256=reuse['baseline_archive_sha256'],archive_sha_reread=False,archive_stat=C.identity(archive.stat()),proof_sha256=reuse['quality_proof_sha256'])

@contextlib.contextmanager
def cached_sealed_metadata(cache):
 """Reuse only original authenticated metadata; candidate bytes verified later once.
 Reference payload authority is separately required by archive_authority.
 """
 original=P.T.BUNDLE.read_state
 def cached(path):
  key=str(pathlib.Path(path).resolve());need(key in cache,'unregistered sealed source')
  d=cache[key];return dict({n:e['sha256']for n,e in d['entries'].items()},**{'state.json':sha(raw(pathlib.Path(path)/'state.json'))})
 P.T.BUNDLE.read_state=cached
 try:yield
 finally:P.T.BUNDLE.read_state=original

def candidate_spec(plan,bulk):
 stages=[]
 for s in plan['stages']:
  n=pathlib.Path(s['native_output']);dump=n/'state-2147483647'
  stages.append(dict(id=s['id'],begin=s['begin'],end=s['end'],dump=str(dump),plan=str(n/'launch-plan.json'),metadata=str(n/'pipeline-stage.json'),quiescence=str(dump)+'.ring-state.json'))
 return dict(stages=stages,request_sha256=plan['request_sha256'],authenticated_bulk=bulk,registered_verification_policy='measured')

def stream_candidate(dump,sealed,prefixes):
 """One full candidate read: own entry/full seals plus old-prefix SHA/zero tail."""
 need(set(prefixes)<=set(sealed['entries']),'all registered capacity sources present in candidate payload')
 bundle=dump/'state.bundle';need(not bundle.is_symlink(),'regular candidate bundle');whole=hashlib.sha256();proofs=[]
 with bundle.open('rb') as f:
  before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==sealed['bytes'],'candidate bounds')
  for name,e in sealed['entries'].items():
   need(f.tell()==e['offset'],'contiguous actual entry');h=hashlib.sha256();prefix=hashlib.sha256();left=e['bytes'];consumed=0;old=prefixes.get(name)
   while left:
    b=f.read(min(65536,left));need(b,'truncated candidate entry');h.update(b);whole.update(b)
    if old:
     split=max(0,min(len(b),old['bytes']-consumed));prefix.update(b[:split]);need(not any(b[split:]),'nonzero262K extra-capacity tail '+name)
    consumed+=len(b);left-=len(b)
   need(h.hexdigest()==e['sha256'],'candidate original entry seal '+name)
   if old:
    need(e['bytes']==2*old['bytes'] and prefix.hexdigest()==old['sha256'],'exact128K prefix hash '+name)
    proofs.append(dict(source=name,prefix_bytes=old['bytes'],zero_tail_bytes=e['bytes']-old['bytes'],prefix_sha256=old['sha256'],full_sha256=e['sha256']))
  need(not f.read(1) and whole.hexdigest()==sealed['bundle_sha256'],'candidate full native seal')
  need(C.identity(before)==C.identity(os.fstat(f.fileno()))==C.identity(bundle.stat()),'candidate replaced/changed')
 return dict(bytes=sealed['bytes'],full_sha256=whole.hexdigest(),capacity_proofs=proofs)

def run(registration,result):
 reg=read(registration);need(reg['schema']=='ownrt.long-cross-context-registration.v1','explicit registered treatment')
 for name,digest in dict(reg['pins'],**reg['helper_pins']).items():need(sha(raw(name))==digest,'registered config/plan identity '+name)
 roots=[pathlib.Path(reg[k])for k in ('reference','candidate')];plans=[read(r/'output/plan.json')for r in roots]
 need([p['context']for p in plans]==[131072,262144] and [p['boundaries']for p in plans]==[[0,25,48],[0,17,33,48]],'registered contexts/partitions')
 need(all(p['max_new']==512 and len(p['prompt_tokens'])==121854 and p['activation_dtype']=='F32' and p['dedicated_prefill_slots']==4 for p in plans),'actual long precision/scheduler geometry')
 configs,identities=zip(*(C.request_identity(r,p)for r,p in zip(roots,plans)))
 need(reg['verification_policy']=='measured' and all(c['check_policy']=='measured' for c in configs),'registered actual measured-long policy')
 diffs={k:[configs[0].get(k),configs[1].get(k)]for k in configs[0].keys()|configs[1].keys()if configs[0].get(k)!=configs[1].get(k)}
 need(set(diffs)==set(reg['allowed_config_differences']),'only registered config treatments')
 ignore={'context','boundaries','target_bdfs','config_sha256'}
 need({k:v for k,v in identities[0].items()if k not in ignore}=={k:v for k,v in identities[1].items()if k not in ignore},'actual reconstructed semantic requests')
 builds=[read(c['build_receipt'])for c in configs];need(raw(configs[0]['build_receipt'])==raw(configs[1]['build_receipt']) and builds[0]['binary_sha256']==reg['binary_sha256'],'same registered native build/source identity')
 common=set(plans[0]['pins'])&set(plans[1]['pins']);need(all(plans[0]['pins'][k]==plans[1]['pins'][k]for k in common),'same shared scheduler/source pins')
 for role,plan in zip(('reference','candidate'),plans):
  need(sha(raw(roots[0 if role=='reference'else 1]/'plan.json'))==sha(raw(roots[0 if role=='reference'else 1]/'output/plan.json')),'actual executed plan equals registered plan')
  private=set(plan['pins'])-common;need(all(pathlib.Path(k).is_relative_to(roots[0 if role=='reference'else 1])for k in private),'nonshared pins only fresh run files')
 runs=[terminal(r,p)for r,p in zip(roots,plans)];need(runs[0][0]['output_ids']==runs[1][0]['output_ids'],'all512 actual IDs equal')
 result['runs']=[r[1]for r in runs];role_maps=[roles(r,p)for r,p in zip(roots,plans)];authority=archive_authority(roots[0],role_maps[0],pathlib.Path(reg['archive_reuse']))
 cache={str(d.resolve()):C.sealed(d,False)for rolemap in role_maps for d in rolemap.values()}
 stamps={str(d/f):C.identity((d/f).stat())for rolemap in role_maps for d in rolemap.values()for f in ('state.json','state-index.tsv','state-seal.txt')}
 pairs=[];prefixes=[]
 for root,plan in zip(roots,plans):
  commands=[json.loads(x,object_pairs_hook=P.T.BUNDLE.pairs)for x in P.trace_source(root/'output/commands.jsonl')[0].splitlines()]
  pair,bulk=P.plan_pairs(plan,commands,122365);need(len(pair)==122364,'actual122364 pairs');pairs.append(pair);prefixes.append(bulk)
 need(pairs[0]==pairs[1],'actual canonical token/parent-hidden pairs equal')
 need(all(v is not None for v in prefixes),'both actual native bulk witnesses required')
 chunk_payloads=[[(c['start'],c['count'],c['serial'],c['prompt_sha256'],c['raw_sha256'])for c in v['actual_native_chunks']]for v in prefixes]
 need(chunk_payloads[0]==chunk_payloads[1],'actual native chunk hidden-payload hashes equal; header hashes deliberately excluded')
 pairhash=sha(json.dumps(pairs[0],sort_keys=True,separators=(',',':')).encode())
 ids=runs[0][0]['output_ids'];identity=dict(position=122365,model_sha256=plans[0]['model_identity_sha256'],prompt_token_sha256=sha(struct.pack('<121854i',*plans[0]['prompt_tokens'])),output_token_sha256=sha(struct.pack('<512i',*ids)),arithmetic=plans[0]['activation_dtype'])
 seed=read(reg['draft_identity_seed'])['input_identity'];targets=[];drafts=[]
 with cached_sealed_metadata(cache),tempfile.TemporaryDirectory(prefix='ownrt-long-context-metadata-')as tmp:
  for i,(root,plan)in enumerate(zip(roots,plans)):
   bulk=prefixes[i];target=measured_target_candidate(candidate_spec(plan,0 if bulk is None else bulk['positions']),identity);targets.append(target)
   di=dict(seed,pair_sequence_sha256=pairhash,position=122364,context=plan['context'])
   need(di['model_sha256']==plan['model_identity_sha256'] and di['draft_model_sha256']==plan['draft_model_sha256'],'actual draft model identities')
   manifest=pathlib.Path(tmp)/f'draft{i}.json';manifest.write_text(json.dumps(dict(schema='ownrt.draft-state-set.v1',dump=str(role_maps[i]['provider-dump']),input_identity=di)))
   drafts.append(P.D.load_set(manifest))
 need(targets[0]['first_stage_host_history']==targets[1]['first_stage_host_history'],'actual target host token history')
 need(drafts[0]['host']==drafts[1]['host'],'actual draft host state')
 expected_prefix={str(d.resolve()):{}for d in role_maps[1].values()};counts=[]
 for draft,sets,registry in ((False,targets,X.TARGET),(True,drafts,X.DRAFT)):
  a,b=[s['canonical']for s in sets];need(set(a)==set(b) and len(a)==(73 if draft else 2065),'complete canonical inventory');exact=0
  for name in sorted(a):
   layout=lambda e:e['layout']if draft else {k:e[k]for k in ('bytes','dtype','shape','role')}
   if name in registry:
    X.capacity_layout(name,layout(b[name]),layout(a[name]),draft=draft,candidate_context=131072)
    key=P.T.BUNDLE.logical_name(name)if draft else name
    if draft:dumps=[role_maps[1][k]for k in ('provider-dump','provider-finish')]
    else:dumps=[X.target_dump(candidate_spec(plans[1],0),name)]
    for dump in dumps:expected_prefix[str(dump.resolve())][key]=dict(bytes=layout(a[name])['bytes'],sha256=a[name]['sha256'])
   else:need(a[name]==b[name],'exact noncapacity canonical source '+name);exact+=1
  need(exact==(69 if draft else 2017),'complete exact canonical inventory');counts.append(dict(total=len(a),exact=exact,capacity=len(registry)))
 # Provider FINISH is a separately sealed actual source and must preserve all73 DUMP entries.
 for rolemap in role_maps:
  dump,finish=[cache[str(rolemap[k].resolve())]for k in ('provider-dump','provider-finish')]
  need(dump['entries']==finish['entries'] and dump['state']==finish['state'],'provider DUMP/FINISH exact')
 streamed={name:stream_candidate(d,cache[str(d.resolve())],expected_prefix[str(d.resolve())])for name,d in role_maps[1].items()}
 need(sum(len(v['capacity_proofs'])for k,v in streamed.items()if k!='provider-finish')==52,'all52 actual capacity proofs')
 for name,before in stamps.items():need(C.identity(pathlib.Path(name).stat())==before,'sealed metadata changed')
 result.update(passed=True,scope='Registered121854/512 two-target128K tothree-target262K; exact2065/73 canonical state with52 capacity arrays matched by128K prefix SHA and zero extra tail. Candidate payload fully streamed; prior verified archive authority reused without archive extraction or rehash. Not independent model correctness.',request_identity_reconstructed=identities,config_treatments=diffs,archive_authority=authority,canonical_counts=counts,pair_sequence_sha256=pairhash,canonical_pairs=122364,outputs=512,bulk_hidden_payload_chunks=len(chunk_payloads[0]),bulk_hidden_payload_scope='Native raw_sha256 hashes count*40960 actual owned hidden bytes; request/topology-specific record hashes not compared',candidate_payloads=streamed)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('registration',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path,required=True);args=ap.parse_args();need(not args.out.exists(),'fresh proof output');result={'passed':False,'schema':'ownrt.long-cross-context-proof.v1','helper_sha256':sha(raw(__file__))}
 try:run(args.registration,result)
 except Exception as e:result.update(passed=False,error={'type':type(e).__name__,'message':str(e)})
 with args.out.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
 raise SystemExit(0 if result['passed']else 1)

"""Same-context3+1 long comparisons; actual complete payloads/pairs, no archived payload reread."""
import argparse,importlib.util,json,struct,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
lp=HERE.parent/'dedicated-gate/long-cross-context/compare_long.py';sys.path.insert(0,str(lp.parent))
spec=importlib.util.spec_from_file_location('long_context',lp);L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
C,P=L.C,L.P;need,read,raw,sha=C.need,C.read,C.raw,C.sha

def timing(root,d):
 events=[json.loads(x)for x in raw(root/'output/tokens.jsonl').splitlines()];ts=[x['committed_monotonic_s']for x in events];need(all(b>a for a,b in zip(ts,ts[1:])),'ordered actual token clocks')
 t=dict(ttft_s=events[0]['emitted_elapsed_s'],request_s=d['scheduler_wall_seconds'],first99_tps=99/(ts[99]-ts[0]),all511_tps=511/(ts[-1]-ts[0]),lifecycle_s=d['wall_seconds'])
 phases=d.get('lifecycle_phases')
 if phases:t.update(coordinator_to_all_ready_s=phases['all_owners_ready']-phases['coordinator_start'],ready_to_request_s=phases['request_start']-phases['all_owners_ready'])
 return t

def run(ref,candidate,proof,historical):
 roots=[ref,candidate];plans=[read(r/'output/plan.json')for r in roots];reg=read(HERE/'long-pair-registration.json')
 need(str(candidate)in reg['roots'] and (str(ref)==reg['prior_qualified_3plus1']if historical else [str(ref),str(candidate)]==reg['roots']),'registered run roots/order')
 gate=Path(reg['full_gate']);need(sha(raw(gate))==reg['full_gate_sha256'] and read(gate)['passed'],'prior full32 gate')
 for r,p in zip(roots,plans):need(p==read(r/'plan.json') and p['context']==262144 and p['boundaries']==[0,17,33,48] and p['max_new']==512 and len(p['prompt_tokens'])==121854 and p['activation_dtype']=='F32' and p['dedicated_prefill_slots']==4 and p['check_policy']=='measured','actual registered geometry/policy')
 configs,identities=zip(*(C.request_identity(r,p)for r,p in zip(roots,plans)))
 diffs={k:[configs[0].get(k),configs[1].get(k)]for k in configs[0].keys()|configs[1].keys()if configs[0].get(k)!=configs[1].get(k)}
 allowed={'output','dedicated_prefill_prompt','lookup_storage'}|({'build_receipt'}if historical else set())
 need(set(diffs)==allowed,'only registered config treatments')
 need({k:v for k,v in identities[0].items()if k!='config_sha256'}=={k:v for k,v in identities[1].items()if k!='config_sha256'},'same reconstructed semantic request')
 builds=[read(c['build_receipt'])for c in configs]
 need(sha(raw(configs[1]['build_receipt']))==reg['build_receipt_sha256'],'registered current build')
 if historical:
  expected=read(Path(reg['full_gate']).parent/'registration.json')['native_source_changes'];delta={k:[builds[0]['sources'].get(k),builds[1]['sources'].get(k)]for k in builds[0]['sources'].keys()|builds[1]['sources'].keys()if builds[0]['sources'].get(k)!=builds[1]['sources'].get(k)}
  need(delta==expected,'only preregistered observer/storage native source differences');proof['historical_build_changes']=delta
  need(configs[1]['lookup_storage']=='copy' and 'lookup_storage'not in configs[0],'historical baseline versus current copy')
 else:
  need(raw(configs[0]['build_receipt'])==raw(configs[1]['build_receipt']),'identical binary and full build receipt')
  common=set(plans[0]['pins'])&set(plans[1]['pins']);need(all(plans[0]['pins'][k]==plans[1]['pins'][k]for k in common),'identical common runtime/controller pins')
  need([c['lookup_storage']for c in configs]==['copy','view'],'registered copy to view treatment')
 def normrole(v,root,plan,build):return json.dumps(v,sort_keys=True).replace(str(root),'<RUN>').replace(plan['request_sha256'],'<REQUEST>').replace(build['binary'],'<BINARY>')
 normalized=json.loads(json.dumps(plans))
 if not historical:need(normalized[1]['stages'][0]['environment'].pop('OWNRT_LOOKUP_VIEW')=='1','first target view enabled')
 for p in normalized:
  for owner in p['stages']+[p['provider']]:need(not any(k in owner['environment']for k in ('OWNRT_LOOKUP_VIEW','OWNRT_L4_RAW_HISTORY','OWNRT_L4_PREP_HISTORY')),'no other storage/diagnostic treatment')
 for key in ['stages','provider']:need(normrole(normalized[0][key],ref,plans[0],builds[0])==normrole(normalized[1][key],candidate,plans[1],builds[1]),'role argv/env only declared changes')
 runs=[L.terminal(r,p)for r,p in zip(roots,plans)];need(runs[0][0]['output_ids']==runs[1][0]['output_ids'],'all512 actual output IDs')
 proof['runs']=[dict(root=str(r),timing=timing(r,d[0]),**d[1])for r,d in zip(roots,runs)]
 rolemaps=[L.roles(r,p)for r,p in zip(roots,plans)]
 if historical:
  arpath=ref/'archive.json';ar=read(arpath);ap=Path(ar['archive']);need(ar['root']==str(ref) and ar['full_tar_compare_passed'] and ar['deleted_only_compared_completed_files'] and ap.is_file() and not ap.is_symlink() and ap.stat().st_size==ar['archive_bytes'],'prior full archive authority')
  for dump in rolemaps[0].values():need(str((dump/'state.bundle').relative_to(ref))in ar['exact_paths'],'reference archived member')
  proof['baseline_archive']=dict(receipt=str(arpath),receipt_sha256=sha(raw(arpath)),archive=ar['archive'],archive_sha256=ar['sha256'],archive_sha_reread=False)
 else:proof['baseline_archive_reuse']=L.archive_authority(ref,rolemaps[0],ref/'archive-reuse.json')
 cache={};states={}
 for role in rolemaps[0]:
  x,y=C.sealed(rolemaps[0][role],False),C.sealed(rolemaps[1][role],True);cache[str(rolemaps[0][role].resolve())]=x;cache[str(rolemaps[1][role].resolve())]=y
  states[role]=dict(exact_complete_payload_and_metadata=x['bundle_sha256']==y['bundle_sha256'] and x['entries']==y['entries'] and x['state']==y['state'],candidate_streamed_bytes=y['bytes'],reference_bundle_sha256=x['bundle_sha256'],candidate_bundle_sha256=y['bundle_sha256'])
 proof['states']=states;need(all(v['exact_complete_payload_and_metadata']for v in states.values()),'all5 complete state sources exact')
 for role in ['stage0','stage1','stage2','stageprovider']:need(raw(ref/'output'/role/'native/census.json')==raw(candidate/'output'/role/'native/census.json'),'complete actual census equality '+role)
 pairs=[];bulks=[]
 for r,p in zip(roots,plans):
  commands=[json.loads(x,object_pairs_hook=P.T.BUNDLE.pairs)for x in P.trace_source(r/'output/commands.jsonl')[0].splitlines()];pair,bulk=P.plan_pairs(p,commands,122365);need(len(pair)==122364 and bulk is not None,'actual canonical pair/bulk witness');pairs.append(pair);bulks.append(bulk)
 need(pairs[0]==pairs[1],'all122364 actual token/parent-hidden pairs exact')
 chunks=[[(c['start'],c['count'],c['serial'],c['prompt_sha256'],c['raw_sha256'])for c in b['actual_native_chunks']]for b in bulks];need(chunks[0]==chunks[1],'actual native hidden payload chunks exact')
 pairhash=sha(json.dumps(pairs[0],sort_keys=True,separators=(',',':')).encode());ids=runs[0][0]['output_ids'];identity=dict(position=122365,model_sha256=plans[0]['model_identity_sha256'],prompt_token_sha256=sha(struct.pack('<121854i',*plans[0]['prompt_tokens'])),output_token_sha256=sha(struct.pack('<512i',*ids)),arithmetic='F32')
 seed=read(read(lp.parent/'registration.json')['draft_identity_seed'])['input_identity'];targets=[];drafts=[]
 with L.cached_sealed_metadata(cache),tempfile.TemporaryDirectory(prefix='lookup-long-metadata-')as temp:
  for i,(r,p)in enumerate(zip(roots,plans)):
   targets.append(L.measured_target_candidate(L.candidate_spec(p,bulks[i]['positions']),identity));di=dict(seed,pair_sequence_sha256=pairhash,position=122364,context=262144);need(di['model_sha256']==p['model_identity_sha256'] and di['draft_model_sha256']==p['draft_model_sha256'],'draft identity')
   m=Path(temp)/f'draft{i}.json';m.write_text(json.dumps(dict(schema='ownrt.draft-state-set.v1',dump=str(rolemaps[i]['provider-dump']),input_identity=di)));drafts.append(P.D.load_set(m))
 need(targets[0]['first_stage_host_history']==targets[1]['first_stage_host_history'] and drafts[0]['host']==drafts[1]['host'],'actual target/draft host histories')
 for sets,n in [(targets,2065),(drafts,73)]:need(sets[0]['canonical']==sets[1]['canonical'] and len(sets[0]['canonical'])==n,'all canonical sources exact')
 proof.update(passed=True,config_differences=diffs,canonical_targets=2065,canonical_draft=73,canonical_pairs=122364,pair_sequence_sha256=pairhash,bulk_hidden_payload_chunks=len(chunks[0]),scope='Same262K context/3+1 complete-state/output/pair equality. Historical comparison qualifies new binary copy control; same-binary copy/view comparison isolates storage treatment. CPU-reference fidelity unresolved.')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('reference',type=Path);ap.add_argument('candidate',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--historical',action='store_true');a=ap.parse_args();need(not a.output.exists(),'exclusive proof')
 result=dict(schema='ownrt.lookup-long-proof.v1',passed=False,reference=str(a.reference),candidate=str(a.candidate),helper_sha256=sha(raw(__file__)))
 try:run(a.reference,a.candidate,result,a.historical)
 except Exception as e:result['error']=dict(type=type(e).__name__,message=str(e))
 with a.output.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
 raise SystemExit(0 if result['passed']else 1)

#!/usr/bin/env python3
"""Registered cuts-only 262K comparison; run after both owners finish, CPU only.
Reuses canonical state/pair readers. Candidate payloads are streamed once; the
control uses its previously byte-verified archive receipt, never HDD extraction.
"""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile

HERE=Path(__file__).resolve().parent
LONG=HERE.parent/'dedicated-gate/long-cross-context'
sys.path.insert(0,str(LONG))
spec=importlib.util.spec_from_file_location('equal16_long_helpers',LONG/'compare_long.py')
L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
C,P=L.C,L.P
need,read,raw,sha=C.need,C.read,C.raw,C.sha


def request_identity(plan):
 config_path=Path(plan['config']);config=read(config_path)
 need(config['output']==plan['output'],'actual config output')
 prompt_path=Path(plan['dedicated_prefill_prompt']);prompt=raw(prompt_path)
 need(str(prompt_path)==config['dedicated_prefill_prompt'] and
      sha(prompt)==config['dedicated_prefill_prompt_sha256']==plan['dedicated_prefill_prompt_sha256'] and
      prompt==struct.pack('<%di'%len(plan['prompt_tokens']),*plan['prompt_tokens']), 'actual immutable prompt bytes')
 need(plan['pins'][str(config_path)]==sha(raw(config_path)) and plan['pins'][str(prompt_path)]==sha(prompt),'actual config/prompt pins')
 identity=dict(model=plan['model_identity_sha256'],draft_manifest=config['trusted_draft_manifest_sha256'],
  prompt=plan['prompt_tokens'],context=plan['context'],max_new=plan['max_new'],vocab=plan['vocab'],eos=config['eos_token_ids'],
  depth=config.get('speculative_depth',3),boundaries=config['boundaries'],target_bdfs=[s['bdf']for s in plan['stages']],
  provider_bdf=config['provider_bdf'],check_policy=config.get('check_policy','qualification'),
  config_sha256=sha(raw(config_path)),mode='dedicated-mtp',reference_route_tie_sort=plan['reference_route_tie_sort'],
  reference_route_scope=plan['reference_route_scope'],draft_route_policy=plan['draft_route_policy'],
  dedicated_bulk_prefill=True,prefill_rows=plan['prefill_rows'],prompt_i32_sha256=sha(prompt),
  dedicated_prefill_pipeline=True,dedicated_prefill_slots=4)
 need(sha(json.dumps(identity,sort_keys=True,separators=(',',':')).encode())==plan['request_sha256'],'reconstructed actual policy-bound request identity')
 return config,identity


def normalized_owner(owner,plan,target=False):
 value=deepcopy(owner)
 if target:
  i=value['id'];need((value['begin'],value['end'])==tuple(plan['boundaries'][i:i+2]),'actual owner cut extent')
  need(type(value['packed_weight_bytes'])is int and value['packed_weight_bytes']>0,'positive recorded packed census estimate')
  for key in ('begin','end','packed_weight_bytes'):value.pop(key)
 argv=value['argv']
 if target:
  need(argv.count('--pipeline-boundaries')==1,'one target cut argv')
  pos=argv.index('--pipeline-boundaries')+1
  need(argv[pos]==','.join(map(str,plan['boundaries'])),'actual target argv cuts')
  argv[pos]='<CUTS>'
 need(value['environment'].get('OWNRT_REFERENCE_ROUTE_TIE_SORT')=='1','every owner explicit reference policy')
 def normalize(v):
  if isinstance(v,str):
   if v==plan['request_sha256']:return '<REQUEST>'
   if v==plan['output'] or v.startswith(plan['output']+'/'):return '<OUTPUT>'+v[len(plan['output']):]
   return v
  if isinstance(v,list):return [normalize(x)for x in v]
  if isinstance(v,dict):return {k:normalize(x)for k,x in v.items()}
  return v
 return normalize(value)


def identity_guards(reg,plans,configs,identities):
 need(reg['schema']=='ownrt.equal16-matched-registration.v1' and [c['name']for c in reg['cases']]==['control','equal16'],'registered ordered cases')
 need([p['boundaries']for p in plans]==[[0,17,33,48],[0,16,32,48]],'registered cuts-only treatment')
 for case,p,c in zip(reg['cases'],plans,configs):
  need(p['config']==case['config'] and p['boundaries']==case['boundaries'] and p['context']==262144 and
   p['max_new']==512 and len(p['prompt_tokens'])==121854 and p['model_identity_sha256']==case['model_identity_sha256'] and
   p['activation_dtype']=='F32' and p['check_policy']=='measured' and p['speculative_depth']==3 and
   p['prefill_rows']==256 and p['dedicated_prefill_slots']==4 and p['dedicated_prefill_pipeline']is True and
   p['reference_route_tie_sort']is True and p['reference_route_scope']=='f32-target-only' and p['draft_route_policy']=='unchanged-bf16',
   'actual registered geometry/precision/policy')
  need(c['reference_route_tie_sort']is True,'actual config policy on')
  need([s['bdf']for s in p['stages']]==['0000:23:00.0','0000:27:00.0','0000:47:00.0'] and p['provider']['bdf']=='0000:43:00.0','same registered physical owner roles')
 diffs={k:[configs[0].get(k),configs[1].get(k)]for k in configs[0].keys()|configs[1].keys()if configs[0].get(k)!=configs[1].get(k)}
 need(set(diffs)=={'boundaries','output'},'only cuts/output config differences')
 semantic=lambda d:{k:v for k,v in d.items()if k not in ('boundaries','config_sha256')}
 need(semantic(identities[0])==semantic(identities[1]),'same semantic request except cuts/config digest')
 common=set(plans[0]['pins'])&set(plans[1]['pins'])
 need(all(plans[0]['pins'][k]==plans[1]['pins'][k]for k in common),'same common runtime/controller pins')
 for p in plans:need(set(p['pins'])-common=={p['config']},'only private config source pin')
 for key in ('stages','provider'):
  a,b=([normalized_owner(s,p,True)for s in p[key]]if key=='stages'else normalized_owner(p[key],p)for p in plans)
  need(a==b,'role argv/env only cuts and fresh output/cache paths')
 omit={'boundaries','config','output','request_sha256','pins','stages','provider'}
 need({k:v for k,v in plans[0].items()if k not in omit}=={k:v for k,v in plans[1].items()if k not in omit},'no other plan treatment')
 return diffs


def terminal(output,plan):
 owners={str(s['id'])for s in plan['stages']}|{'provider'}
 t=read(output/'terminal.json');d,_=P.driver_result(output/'driver-result.json')
 need(t['passed']is True and not t['error'] and not t['live_pids'] and set(t['returncodes'])==owners and
      all(type(v)is int and v==0 for v in t['returncodes'].values()),'all actual owners clean FINISH')
 need(d['passed']is True and d['input_position']==122365 and len(d['output_ids'])==512,'actual long frontier/output count')
 events=[json.loads(x)for x in raw(output/'tokens.jsonl').splitlines()]
 need([e['index']for e in events]==list(range(512)) and [e['token']for e in events]==d['output_ids'],'actual ordered512 token events')
 clocks=[e['committed_monotonic_s']for e in events];need(all(b>a for a,b in zip(clocks,clocks[1:])),'ordered actual token clocks')
 census={}
 for s in plan['stages']+[plan['provider']]:
  native=Path(s['native_output']);receipt=read(native/'receipt.json')
  need(receipt['passed']is True and not receipt.get('error') and receipt.get('teardown'),'native receipt')
  need(all(x['status']=='complete' and x['safe_to_exit']is True and x['idle_marker_complete']is True and
    x['in_flight']==x['live_bytes']==0 and not x['error']for x in receipt['teardown']),'native quiescent teardown')
  c=read(native/'census.json');need(c['totals']['device']<=30*1024**3,'actual30GiB device cap')
  need({k:sum(a['bytes']for a in c['allocations']if a['live']and a['memory']==k)for k in c['totals']}==c['totals'],'actual complete allocation census')
  census[str(s['id'])]=dict(totals=c['totals'],sha256=sha(raw(native/'census.json')))
 timing=dict(ttft_s=events[0]['emitted_elapsed_s'],request_s=d['scheduler_wall_seconds'],first99_tps=99/(clocks[99]-clocks[0]),all511_tps=511/(clocks[-1]-clocks[0]),lifecycle_s=d['wall_seconds'])
 return d,dict(output=str(output),terminal=t,censuses=census,timing=timing,output_ids_i32_sha256=sha(struct.pack('<512i',*d['output_ids'])))


def roles(output,plan):
 result={f'stage{s["id"]}':Path(s['native_output'])/'state-2147483647'for s in plan['stages']}
 provider=Path(plan['provider']['native_output'])
 for kind in ('dump','finish'):
  paths=list(provider.glob('provider-'+kind+'-*'));need(len(paths)==1,'unique actual provider '+kind);result['provider-'+kind]=paths[0]
 need(all(p.is_relative_to(output)for p in result.values()),'actual native output ownership')
 return result


def archive_authority(path,output,rolemap,seals):
 ar=read(path)
 need(ar['schema']=='ownrt.reference-route-dedicated-state-archive.v1' and ar['full_tar_bytes_compared']is True and
      ar['actual_payload_sha256_matches_all_seals']is True and ar['removal_completed']is True,'verified completed control archive authority')
 archive=Path(ar['archive']);need(archive.is_file()and not archive.is_symlink()and archive.stat().st_size==ar['archive_bytes'],'retained verified archive path/size')
 members={m['path']:m for m in ar['members']}
 for dump in rolemap.values():
  bundle=str(dump/'state.bundle');need(bundle in members,'actual control archived member')
  row=members[bundle];s=seals[str(dump.resolve())]
  need(row['bytes']==s['bytes']and row['sha256']==s['bundle_sha256'],'archive member bound to retained seal')
  need(Path(row['member'])==Path(bundle).relative_to(output.parent),'actual archive relative member')
 return dict(receipt=str(path),receipt_sha256=sha(raw(path)),archive=str(archive),archive_sha256=ar['archive_sha256'],archive_sha_reread=False,archive_stat=C.identity(archive.stat()))


def run(registration,archive_receipt,result):
 reg=read(registration);plans=[]
 result['helper_sources']={str(Path(f).resolve()):sha(raw(f)) for f in
  (__file__,L.__file__,C.__file__,P.__file__,P.T.__file__,P.D.__file__,P.T.BUNDLE.__file__,LONG/'measured_target.py')}
 for case in reg['cases']:
  plan_path=Path(case['plan']);need(sha(raw(plan_path))==case['plan_sha256'],'registered plan SHA')
  plan=read(plan_path);need(raw(Path(plan['output'])/'plan.json')==raw(plan_path),'actual executed plan equals registered plan');plans.append(plan)
 outputs=[Path(p['output'])for p in plans]
 configs,identities=zip(*(request_identity(p)for p in plans));diffs=identity_guards(reg,plans,configs,identities)
 builds=[read(c['build_receipt'])for c in configs]
 need(raw(configs[0]['build_receipt'])==raw(configs[1]['build_receipt'])and builds[0]['binary_sha256']==reg['binary_sha256'],'same registered compiled binary/source receipt')
 for p,c in zip(plans,configs):need(p['pins'][str(Path(c['build_receipt']).resolve())]==sha(raw(c['build_receipt'])),'actual build receipt pin')
 runs=[terminal(o,p)for o,p in zip(outputs,plans)];need(runs[0][0]['output_ids']==runs[1][0]['output_ids'],'all512 actual output IDs exact')
 result['runs']=[r[1]for r in runs]
 rolemaps=[roles(o,p)for o,p in zip(outputs,plans)]
 cache={str(d.resolve()):C.sealed(d,False)for rm in rolemaps for d in rm.values()}
 stamps={str(d/f):C.identity((d/f).stat())for rm in rolemaps for d in rm.values()for f in ('state.json','state-index.tsv','state-seal.txt')}
 result['baseline_archive']=archive_authority(archive_receipt,outputs[0],rolemaps[0],cache)
 pairs=[];bulks=[]
 for out,p in zip(outputs,plans):
  commands=[json.loads(x,object_pairs_hook=P.T.BUNDLE.pairs)for x in P.trace_source(out/'commands.jsonl')[0].splitlines()]
  pair,bulk=P.plan_pairs(p,commands,122365);need(len(pair)==122364 and bulk is not None,'actual122364 pairs and bulk witness');pairs.append(pair);bulks.append(bulk)
 need(pairs[0]==pairs[1],'all122364 canonical token/parent-hidden pairs exact')
 chunks=[[(c['start'],c['count'],c['serial'],c['prompt_sha256'],c['raw_sha256'])for c in b['actual_native_chunks']]for b in bulks]
 need(chunks[0]==chunks[1],'actual native bulk hidden payload chunks exact')
 pairhash=sha(json.dumps(pairs[0],sort_keys=True,separators=(',',':')).encode());ids=runs[0][0]['output_ids']
 identity=dict(position=122365,model_sha256=plans[0]['model_identity_sha256'],prompt_token_sha256=sha(struct.pack('<121854i',*plans[0]['prompt_tokens'])),output_token_sha256=sha(struct.pack('<512i',*ids)),arithmetic='F32')
 seed=read(read(LONG/'registration.json')['draft_identity_seed'])['input_identity'];targets=[];drafts=[]
 with L.cached_sealed_metadata(cache),tempfile.TemporaryDirectory(prefix='equal16-long-metadata-')as temp:
  for i,p in enumerate(plans):
   targets.append(L.measured_target_candidate(L.candidate_spec(p,bulks[i]['positions']),identity))
   di=dict(seed,pair_sequence_sha256=pairhash,position=122364,context=262144)
   need(di['model_sha256']==p['model_identity_sha256']and di['draft_model_sha256']==p['draft_model_sha256'],'actual draft model identity')
   m=Path(temp)/f'draft{i}.json';m.write_text(json.dumps(dict(schema='ownrt.draft-state-set.v1',dump=str(rolemaps[i]['provider-dump']),input_identity=di)));drafts.append(P.D.load_set(m))
 need(targets[0]['first_stage_host_history']==targets[1]['first_stage_host_history']and drafts[0]['host']==drafts[1]['host'],'actual target/draft host history')
 for sets,count in ((targets,2065),(drafts,73)):need(sets[0]['canonical']==sets[1]['canonical']and len(sets[0]['canonical'])==count,'complete canonical source equality')
 for rm in rolemaps:
  a,b=[cache[str(rm[k].resolve())]for k in ('provider-dump','provider-finish')]
  need(a['entries']==b['entries']and a['state']==b['state'],'actual provider DUMP/FINISH exact')
 # Only now stream all candidate bytes against every entry and whole bundle seal.
 streamed={name:L.stream_candidate(d,cache[str(d.resolve())],{})for name,d in rolemaps[1].items()}
 for name,before in stamps.items():need(C.identity(Path(name).stat())==before,'retained metadata changed during comparison')
 result.update(passed=True,config_differences=diffs,canonical_targets=2065,canonical_draft=73,canonical_pairs=122364,outputs=512,pair_sequence_sha256=pairhash,bulk_hidden_payload_chunks=len(chunks[0]),candidate_payloads=streamed,
  exclusion_scope='Existing measured_target policy: inactive alternate banks and nonfinal head scratch excluded from cross-topology canonical comparison; EVERY candidate byte still read against its own entry/full seals.',
  scope='Same262K reference-route policy and binary, contiguous cuts17/16/15 to16/16/16 only. Complete canonical target/draft state and actual outputs/pairs/chunks. First-inference screen, not independent CPU model validation or suite promotion.')

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('registration',type=Path);ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();need(not a.out.exists(),'exclusive proof output')
 result=dict(schema='ownrt.equal16-reference-route-long-proof.v1',passed=False,helper_sha256=sha(raw(__file__)),registration_sha256=sha(raw(a.registration)))
 try:run(a.registration,a.archive,result)
 except Exception as e:result['error']=dict(type=type(e).__name__,message=str(e))
 with a.out.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
 raise SystemExit(0 if result['passed']else 1)

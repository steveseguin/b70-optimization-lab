#!/usr/bin/env python3
"""CPU-only completed32-token AOT gate. Run only after coordinator release.
Reference authority is retained sealed metadata + previously verified archive receipt;
no baseline HDD archive hash reread. Every candidate payload byte is streamed.
"""
import argparse, importlib.util, json, pathlib, struct
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('completed',HERE.parent/'dedicated-gate/bounded-live-count-candidate/compare_completed.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
need,read,raw,sha=C.need,C.read,C.raw,C.sha
FLAG='-fsycl-targets=intel_gpu_bmg_g31'
OWNERS=['stage0','stage1','stageprovider']
def terminal(root):
 t=read(root/'output/terminal.json')
 need(t['passed'] is True and not t['error'] and not t['live_pids'] and set(t['returncodes'])=={'0','1','provider'} and set(t['returncodes'].values())=={0},'clean3owner terminal')
 d=read(root/'output/driver-result.json');events=[json.loads(x)for x in raw(root/'output/tokens.jsonl').splitlines()]
 need(d['passed'] is True and d['input_position']==1708 and len(d['output_ids'])==32,'complete1677/32 result')
 need([x['index']for x in events]==list(range(32)) and [x['token']for x in events]==d['output_ids'],'actual ordered32 token events')
 for owner in OWNERS:
  r=read(root/'output'/owner/'native/receipt.json');need(r['passed'] is True and not r.get('error') and r.get('teardown'),'native teardown receipt')
  need(all(x['status']=='complete' and x['safe_to_exit'] is True and x['idle_marker_complete'] is True and x['in_flight']==x['live_bytes']==0 and not x['error']for x in r['teardown']),'native teardown complete')
 return d['output_ids']
def builds(a,b,result):
 need(a['sources']==b['sources'] and len(a['sources'])==256,'exact256 native source hashes')
 need(a['runtime_assets']==b['runtime_assets'] and a['generated_dependencies']==b['generated_dependencies'] and a['generated_authority']==b['generated_authority'],'exact runtime/generated assets')
 need(set(a['commands'])==set(b['commands']),'same compile/link command inventory')
 ar=str(pathlib.Path(a['binary']).parent);br=str(pathlib.Path(b['binary']).parent)
 for name in a['commands']:
  x,y=a['commands'][name],b['commands'][name];need(x['rc']==y['rc']==0,'successful compile/link '+name)
  av=x['cmd'];bv=y['cmd'];need(FLAG not in av and bv.count(FLAG)==1,'one explicit AOT addition '+name)
  aa=[v.replace(ar,'<BUILD>') for v in av];bb=[v.replace(br,'<BUILD>')for v in bv if v!=FLAG]
  need(aa==bb,'only AOT target flag/build directory differs '+name)
 result['build_identity']={'sources256_equal':True,'runtime_assets_equal':True,'compiler_commands_only_added_flag':FLAG,'reference_binary':a['binary_sha256'],'candidate_binary':b['binary_sha256']}
def run(reference,candidate,archive_receipt,result):
 result.update(schema='ownrt.full-AOT-gate-comparison.v1',passed=False,reference=str(reference),candidate=str(candidate),comparator_sha256=sha(raw(__file__)))
 need(terminal(reference)==terminal(candidate),'exact32 output IDs')
 pa,pb=read(reference/'output/plan.json'),read(candidate/'output/plan.json')
 ca,ia=C.request_identity(reference,pa);cb,ib=C.request_identity(candidate,pb)
 diffs={k:[ca.get(k),cb.get(k)]for k in ca.keys()|cb.keys()if ca.get(k)!=cb.get(k)}
 need(set(diffs)=={'output','dedicated_prefill_prompt','build_receipt'},'declared config path/build treatment only')
 need({k:v for k,v in ia.items()if k!='config_sha256'}=={k:v for k,v in ib.items()if k!='config_sha256'},'reconstructed semantic request identity')
 need(pa['context']==pb['context']==131072 and pa['max_new']==pb['max_new']==32 and pa['boundaries']==pb['boundaries']==[0,25,48] and pa['dedicated_prefill_slots']==pb['dedicated_prefill_slots']==4,'actual gate geometry')
 ba,bb=read(ca['build_receipt']),read(cb['build_receipt']);builds(ba,bb,result)
 def norm(v,root,plan,receipt):
  return json.dumps(v,sort_keys=True).replace(str(root),'<RUN>').replace(plan['request_sha256'],'<REQUEST>').replace(receipt['binary'],'<BINARY>')
 for key in ['stages','provider']:
  need(norm(pa[key],reference,pa,ba)==norm(pb[key],candidate,pb,bb),'actual role argv/env only declared path/binary/request differences '+key)
 result['request_identity']={'reconstructed_both':True,'config_differences':diffs,'semantic_equal_except_config_digest':True}
 result['censuses']={}
 for owner in OWNERS:
  a=raw(reference/'output'/owner/'native/census.json');b=raw(candidate/'output'/owner/'native/census.json');result['censuses'][owner]={'byte_equal':a==b,'reference_sha256':sha(a),'candidate_sha256':sha(b)}
 need(all(x['byte_equal']for x in result['censuses'].values()),'all3 censusbytes exact')
 ar=read(archive_receipt);need(ar['root']==str(reference) and ar['full_tar_compare_passed'] is True and ar['deleted_only_compared_completed_files'] is True,'baseline verified archive authority')
 ap=pathlib.Path(ar['archive']);need(not ap.is_symlink() and ap.is_file() and ap.stat().st_size==ar['archive_bytes'],'retained archive path/size unchanged')
 result['baseline_archive']={'receipt':str(archive_receipt),'receipt_sha256':sha(raw(archive_receipt)),'archive_sha256':ar['sha256'],'archive_sha_reread':False,'authority':'Prior full archive hash/tar compare and retained native metadata; actual candidate fully streamed now'}
 ra,rb=C.roles(reference),C.roles(candidate);states={};result['states']=states
 for role in ra:
  need(str((ra[role]/'state.bundle').relative_to(reference))in ar['exact_paths'],'verified reference archive member')
  states[role]={'validation':'started'}
  old,new=C.sealed(ra[role],False),C.sealed(rb[role],True)
  mismatches=[k for k in old['entries'].keys()|new['entries'].keys()if old['entries'].get(k)!=new['entries'].get(k)]
  states[role]={'candidate_streamed_bytes':new['bytes'],'reference_bundle_sha256':old['bundle_sha256'],'candidate_bundle_sha256':new['bundle_sha256'],'entry_mismatches':mismatches,'whole_bundle_equal':old['bundle_sha256']==new['bundle_sha256'],'state_json_equal':old['state']==new['state'],'reference_seal_sha256':old['seal_sha256'],'candidate_seal_sha256':new['seal_sha256']}
 # Retain all four mismatches rather than silently filtering/excluding buffers.
 need(all(x['whole_bundle_equal'] and not x['entry_mismatches'] and x['state_json_equal']for x in states.values()),'all4 complete sealed payload/layouts exact; no exclusions')
 result.update(passed=True,outputs=32,scope='Exact complete4bundle AOT/JIT equality and actual source/build identity; no independentCPUquality or performance proof.')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('reference',type=pathlib.Path);p.add_argument('candidate',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);p.add_argument('--archive-receipt',type=pathlib.Path,required=True);a=p.parse_args();need(not a.output.exists(),'exclusive proof output');result={}
 try:run(a.reference,a.candidate,a.archive_receipt,result)
 except Exception as e:result.update(passed=False,error={'type':type(e).__name__,'message':str(e)})
 with a.output.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
 raise SystemExit(0 if result['passed'] else 1)

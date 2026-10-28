"""Completed full-state lookup-view gate; retained baseline archive authority, actual candidate bytes."""
import argparse,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('full_gate',HERE.parent/'aot-cold-gate/compare_full_gate.py');G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)
C=G.C;need,read,raw,sha=C.need,C.read,C.raw,C.sha

def run(root,proof):
 reg=read(root/'registration.json');ref=Path(reg['reference']);need(reg['candidate']==str(root),'registered candidate root')
 pa,pb=read(ref/'output/plan.json'),read(root/'output/plan.json')
 need(sha(raw(ref/'output/plan.json'))==reg['reference_plan_sha256'] and sha(raw(root/'plan.json'))==reg['candidate_plan_sha256'] and pb==read(root/'plan.json'),'registered actual plans')
 a,b=G.terminal(ref,1677,32),G.terminal(root,1677,32);need(a['output_ids']==b['output_ids'],'all32 actual output IDs')
 ca,ia=C.request_identity(ref,pa);cb,ib=C.request_identity(root,pb)
 diffs={k:[ca.get(k),cb.get(k)]for k in ca.keys()|cb.keys()if ca.get(k)!=cb.get(k)}
 need(set(diffs)=={'output','dedicated_prefill_prompt','build_receipt','lookup_storage'} and cb['lookup_storage']=='view' and 'lookup_storage'not in ca,'only declared storage/build/path config changes')
 need({k:v for k,v in ia.items()if k!='config_sha256'}=={k:v for k,v in ib.items()if k!='config_sha256'},'same semantic request excluding declared config hash')
 need(pa['context']==pb['context']==131072 and pa['boundaries']==pb['boundaries']==[0,25,48] and pa['dedicated_prefill_slots']==pb['dedicated_prefill_slots']==4,'registered geometry')
 ba,bb=read(ca['build_receipt']),read(cb['build_receipt'])
 need(sha(raw(ca['build_receipt']))==reg['reference_build_receipt_sha256'] and sha(raw(cb['build_receipt']))==reg['candidate_build_receipt_sha256'],'registered build receipts')
 delta={k:[ba['sources'].get(k),bb['sources'].get(k)]for k in ba['sources'].keys()|bb['sources'].keys()if ba['sources'].get(k)!=bb['sources'].get(k)}
 need(delta==reg['native_source_changes'] and len(delta)==6,'exact preregistered observer/storage source changes')
 need(ba['runtime_assets']==bb['runtime_assets'] and ba['generated_dependencies']==bb['generated_dependencies'] and ba['generated_authority']==bb['generated_authority'],'unchanged runtime assets')
 need(set(ba['commands'])==set(bb['commands']),'same command inventory')
 for k in ba['commands']:
  x,y=ba['commands'][k],bb['commands'][k];need(x['rc']==y['rc']==0 and G.FLAG not in x['cmd'] and y['cmd'].count(G.FLAG)==1,'qualified JIT versus AOT compiler flags')
  norm=lambda cmd,receipt:[v.replace(str(Path(receipt['binary']).parent),'<BUILD>')for v in cmd if v!=G.FLAG]
  need(norm(x['cmd'],ba)==norm(y['cmd'],bb),'only registered AOT flag/path compile change')
 def normrole(v,root,plan,receipt):return json.dumps(v,sort_keys=True).replace(str(root),'<RUN>').replace(plan['request_sha256'],'<REQUEST>').replace(receipt['binary'],'<BINARY>')
 candidate=json.loads(json.dumps(pb));need(candidate['stages'][0]['environment'].pop('OWNRT_LOOKUP_VIEW')=='1','first target mapping opt-in')
 for owner in candidate['stages']+[candidate['provider']]:need(not any(k in owner['environment']for k in ('OWNRT_LOOKUP_VIEW','OWNRT_L4_RAW_HISTORY','OWNRT_L4_PREP_HISTORY')),'only one storage owner and no observer')
 for key in ['stages','provider']:need(normrole(pa[key],ref,pa,ba)==normrole(candidate[key],root,pb,bb),'actual role argv/env only registered differences')
 proof.update(runs={'reference':a,'candidate':b},config_differences=diffs,native_source_changes=delta,censuses={})
 for owner in G.OWNERS:
  x,y=raw(ref/'output'/owner/'native/census.json'),raw(root/'output'/owner/'native/census.json');proof['censuses'][owner]=dict(byte_equal=x==y,reference_sha256=sha(x),candidate_sha256=sha(y));need(x==y,'complete native census '+owner)
 arpath=HERE.parent/'dedicated-gate/four-slots-2plus1-128k-gate-r2-archive.json';ar=read(arpath);ap=Path(ar['archive'])
 need(ar['root']==str(ref) and ar['full_tar_compare_passed'] and ar['deleted_only_compared_completed_files'] and ap.is_file() and not ap.is_symlink() and ap.stat().st_size==ar['archive_bytes'],'verified baseline archive authority')
 proof['baseline_archive']=dict(receipt=str(arpath),receipt_sha256=sha(raw(arpath)),archive=ar['archive'],archive_sha256=ar['sha256'],archive_sha_reread=False)
 ra,rb=C.roles(ref),C.roles(root);proof['states']={}
 for role in ra:
  need(str((ra[role]/'state.bundle').relative_to(ref))in ar['exact_paths'],'verified reference member')
  x,y=C.sealed(ra[role],False),C.sealed(rb[role],True)
  equal=x['bundle_sha256']==y['bundle_sha256'] and x['entries']==y['entries'] and x['state']==y['state']
  proof['states'][role]=dict(exact_complete_payload_and_metadata=equal,candidate_streamed_bytes=y['bytes'],reference_bundle_sha256=x['bundle_sha256'],candidate_bundle_sha256=y['bundle_sha256'])
 need(all(x['exact_complete_payload_and_metadata']for x in proof['states'].values()),'all4 complete payload/layout/state JSON exact; no exclusions')
 residency=read(root/'output/stage0/native/lookup-residency.json');need(residency['file_backed']is True and residency['anonymous_table_bytes']==0 and residency['tables']==2,'actual retained table views')
 proof.update(passed=True,residency=residency,outputs=32,scope='Complete output/state/census equality for opt-in host mapping. Independent CPU quality unresolved; qualification workload is not a speed benchmark.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args();need(not a.output.exists(),'exclusive proof')
 result=dict(schema='ownrt.lookup-view-full-gate.v1',passed=False,comparator_sha256=sha(raw(__file__)))
 try:run(a.root,result)
 except Exception as e:result['error']=dict(type=type(e).__name__,message=str(e))
 with a.output.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
 raise SystemExit(0 if result['passed']else 1)

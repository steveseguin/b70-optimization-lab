#!/usr/bin/env python3
"""Reuse only identical complete historical inputs; compute changed cases once."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,struct,subprocess,time
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('twelve_prepared',HERE.parent/'fresh-twelve-cpu/run.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
sha,save,need=P.sha,P.save,P.need
HIST=P.ROOT/'gsq-rco-iq3s/service-speed/e-reference'
HIST_BINARY_SHA='71a28e2ca040f9c27c32dfa961257599f373539ea1662a5d52b360238b67f9c9'
def reuse_proof(case,old_input,old_rows):
 actual=json.loads(Path(case['input']).read_text());old=json.loads(Path(old_input).read_text())
 # Exact complete LEi32 bytes and scoring boundary; never just matching output
 # lengths, prompt prefixes, historical names or an earlier common prefix.
 pack=lambda t:struct.pack('<'+str(len(t))+'i',*t)
 if pack(actual['tokens'])!=pack(old['tokens'])or actual['score_from']!=old['score_from']:return None
 need(actual['full_rows']==old['full_rows']==[],'historical scoring treatment')
 proof=P.validate_rows(Path(old_rows),case)
 need(proof['matches']==case['generated_tokens']and not proof['mismatches'],'historical rows argmax/next equality for identical actual continuation')
 return dict(input_path=str(old_input),input_sha256=sha(old_input),rows_path=str(old_rows),rows_sha256=sha(old_rows),packed_input_sha256=P.packed(old['tokens']),score_from=old['score_from'],full_input_bytes_equal=True,comparison=proof)
def committed_file(path,commit):
 rel=Path(path).resolve().relative_to(P.REPO);blob=subprocess.check_output(['git','rev-parse',f'{commit}:{rel}'],cwd=P.REPO,text=True).strip();data=subprocess.check_output(['git','cat-file','blob',blob],cwd=P.REPO)
 need(data==Path(path).read_bytes(),'historical reference file differs from registered committed blob')
 return dict(path=str(path),sha256=sha(path),git_blob=blob,git_commit=commit)
def prepare(gpu,dest):
 dest=dest.resolve();need(not dest.exists(),'fresh mixed authority output');dest.mkdir()
 original=P.prepare(gpu,dest/'all-inputs');allcases=json.loads(original.read_text())
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=P.REPO,text=True).strip()
 buildhash=HIST/'build-hashes.txt';need(buildhash.read_text().splitlines()[0]==HIST_BINARY_SHA+'  build/exact-logits','original historical binary build hash')
 capture=json.loads((HERE.parent/'capture-source-identity.json').read_text());need(capture['source_hashes']['/dev/shm/llref/build/exact-logits']==HIST_BINARY_SHA and sha('/dev/shm/llref/build/exact-logits')==HIST_BINARY_SHA,'preserved original historical executable identity')
 historical_metadata=[committed_file(x,commit)for x in [buildhash,HIST/'RESULT-F32.md',HIST/'runs/f32suite/run_all.sh',HERE.parent/'capture-source-identity.json']]
 cases=[];fresh=[];reused=[];histpins={}
 for c in allcases['cases']:
  old_input=HIST/f'runs/f32suite/inputs/in-{c["id"]}.json';old_rows=HIST/f'runs/f32suite/{c["id"]}.rows.jsonl'
  for path in [old_input,old_rows]:histpins[str(path)]=committed_file(path,commit)
  proof=reuse_proof(c,old_input,old_rows);r=dict(c,historical_input=histpins[str(old_input)],historical_rows=histpins[str(old_rows)])
  if proof is None:r.update(reference_kind='fresh-changed-input',cpu_context_index=len(fresh));fresh.append(r)
  else:r.update(reference_kind='reused-identical-historical',cpu_context_index=None,historical_reuse=proof);reused.append(r)
  cases.append(r)
 need(len(fresh)==2 and len(reused)==10,'current completed GPU suite must have exactly2 changed and10 identical full inputs')
 need([(c['index'],c['id'])for c in fresh]==[(2,'bug-report-synthesis'),(11,'technical-guide')],'explicit suite/local CPU context mapping')
 listing=dest/'changed-inputs.txt';listing.write_text(''.join(c['input']+'\n'for c in fresh))
 save(dest/'inputs.json',dict(schema='ownrt.fresh-changed.cpu-inputs.v1',original_full_input_authority=str(original),original_full_input_authority_sha256=sha(original),cases=cases,fresh_contexts=2,reused_reference_cases=10,fresh_input_list=str(listing),fresh_input_list_sha256=sha(listing),historical_binary_sha256=HIST_BINARY_SHA,historical_metadata=historical_metadata,historical_files=histpins,scope='10 historical CPU row sets reused only for complete identical actual input bytes/scoring;2 changed actual inputs require fresh CPU contexts. No CPU model run yet. Historical source commit not retrospectively inferred.'))
 return dest/'inputs.json'
def preflight(authority):
 mixed=json.loads(authority.read_text());need(sha(mixed['original_full_input_authority'])==mixed['original_full_input_authority_sha256'],'original actual GPU input authority')
 _,_,modelstat,mem=P.preflight(Path(mixed['original_full_input_authority']))
 build=json.loads((HERE/'compiled-identity.json').read_text())
 for p,h in build['pins'].items():need(sha(p)==h,'new reference build/source pin:'+p)
 need(sha(build['binary'])==build['binary_sha256'],'changed wrapper binary')
 for v in mixed['historical_metadata']+list(mixed['historical_files'].values()):need(sha(v['path'])==v['sha256'],'historical authority changed')
 need(sha(mixed['fresh_input_list'])==mixed['fresh_input_list_sha256'],'exact changed context list')
 fresh=[c for c in mixed['cases']if c['reference_kind']=='fresh-changed-input'];need([(c['index'],c['cpu_context_index'])for c in fresh]==[(2,0),(11,1)],'explicit original/context indices')
 for c in mixed['cases']:
  proof=reuse_proof(c,c['historical_input']['path'],c['historical_rows']['path'])
  need((proof is not None)==(c['reference_kind']=='reused-identical-historical'),'no changed token/score boundary may reuse historical rows')
 return mixed,build,modelstat,mem
def run(authority,output,only):
 need(not output.exists(),'fresh exclusive model output; no retry');mixed,build,modelstat,mem=preflight(authority)
 if only:print(json.dumps(dict(passed=True,model_loaded=False,fresh_contexts=2,reused_cases=10,MemAvailable=mem)));return
 output.mkdir();env=os.environ.copy()
 for k in list(env):
  if k.startswith(('GGML_CPU_EXACT','EXACT_')):env.pop(k)
 env.update(GGML_CPU_EXACT_F64='1',EXACT_KV='f32',OMP_NUM_THREADS='8')
 cmd=['nice','-n','19','taskset','-c','8-15',build['binary'],str(P.MODEL),mixed['fresh_input_list'],str(output),'8']
 record=dict(argv=cmd,environment={k:v for k,v in env.items()if k.startswith(('GGML_CPU_EXACT','EXACT_','OMP_'))},started=time.time(),MemAvailable=mem,model_files=modelstat,build=build,input_authority=str(authority),input_authority_sha256=sha(authority),runner_sha256=sha(__file__),reused_cases=10,fresh_contexts=2)
 save(output/'run.json',record)
 with(output/'log.txt').open('w')as log:rc=subprocess.call(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
 record.update(returncode=rc,finished=time.time());save(output/'run.json',record);need(rc==0,'model failure retained; no retry')
 lifecycle=json.loads((output/'lifecycle.json').read_text());need(lifecycle==dict(loaded_models=1,completed_fresh_contexts=2,returncode=0),'exact1 model/2 completed fresh contexts')
 cases=[]
 for c in mixed['cases']:
  r=dict(c)
  if c['reference_kind']=='fresh-changed-input':
   path=output/f'case-{c["cpu_context_index"]:02d}/rows.jsonl';r.update(actual_cpu_rows=str(path),comparison=P.validate_rows(path,c))
  else:r['comparison']=c['historical_reuse']['comparison']
  cases.append(r)
 reused=[c for c in cases if c['reference_kind']=='reused-identical-historical'];fresh=[c for c in cases if c['reference_kind']=='fresh-changed-input']
 save(output/'receipt.json',dict(schema='ownrt.fresh-mixed.cpu-teacherforce.v1',passed=True,lifecycle=lifecycle,process_exit_code=rc,input_authority_sha256=sha(authority),run_sha256=sha(output/'run.json'),cases=cases,reused_reference_cases=10,reused_generated_tokens=sum(c['generated_tokens']for c in reused),fresh_contexts=2,fresh_generated_tokens=sum(c['generated_tokens']for c in fresh),total_generated_tokens=sum(c['generated_tokens']for c in cases),matched_generated_tokens=sum(c['comparison']['matches']for c in cases),fidelity_all_match=all(not c['comparison']['mismatches']for c in cases),scope='10 authenticated historical row sets for complete identical actual inputs +2 newly computed changed-input contexts in1 model load. Not12 new CPU evaluations. Each final unconsumed-next row retained but excluded from generated-token denominator.'))
def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='action',required=True);p=sub.add_parser('prepare');p.add_argument('--gpu-output',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p=sub.add_parser('run');p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight-only',action='store_true');a=ap.parse_args()
 if a.action=='prepare':print(prepare(a.gpu_output,a.output))
 else:run(a.inputs.resolve(),a.output.resolve(),a.preflight_only)
if __name__=='__main__':main()

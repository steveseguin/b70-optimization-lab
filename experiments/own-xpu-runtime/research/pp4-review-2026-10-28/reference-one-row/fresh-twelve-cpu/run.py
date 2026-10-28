#!/usr/bin/env python3
"""Prepare actual candidate continuations; one CPU model load, no retries."""
from pathlib import Path
import argparse,hashlib,json,math,os,struct,subprocess,time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
REPO=ROOT.parents[1]
MODEL=Path('/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf')
MATRIX=HERE.parents[1]/'realistic-matrix-registration.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
def packed(tokens):return hashlib.sha256(struct.pack('<'+str(len(tokens))+'i',*tokens)).hexdigest()
def need(ok,message):
 if not ok:raise ValueError(message)
def ids(tokens):return type(tokens)is list and bool(tokens)and all(type(x)is int and 0<=x<248320 for x in tokens)
def prepare(gpu,dest):
 gpu=gpu.resolve();dest=dest.resolve();need(not dest.exists(),'fresh prepared output')
 terminal=json.loads((gpu/'terminal.json').read_text());result=json.loads((gpu/'result.json').read_text())
 for x in [terminal,result]:need(x['passed']is True and not x['live_pids']and x['returncodes']=={'0':0,'1':0},'completed clean native lifetime')
 need(result['phase_A_full_diagnostic_parity']['passed']is True and len(result['phase_B_records'])==12,'complete GPU seven-plus-twelve authority')
 matrix=json.loads(MATRIX.read_text());registered=next(x['inputs']for x in matrix['matrix']if x['case']=='short-realistic-decode');need(len(registered)==12,'fixed12 matrix')
 cases=[];files={str(gpu/f):sha(gpu/f)for f in ['terminal.json','result.json']};files[str(MATRIX)]=sha(MATRIX)
 # Validate every actual record before creating preparation output.
 for i,reg in enumerate(registered):
  path=gpu/f'phase-b-{i:02d}.json';row=json.loads(path.read_text());need(row==result['phase_B_records'][i],'individual actual record equals completed result')
  promptfile=REPO/reg['path'];prompt=json.loads(promptfile.read_text());out=row['actual_output_ids']
  need(sha(promptfile)==reg['sha256']and row['prompt_source_sha256']==reg['sha256']and Path(row['prompt_source'])==promptfile,'registered prompt source')
  need(row['id']==reg['id']and row['prompt_tokens']==prompt and ids(prompt)and len(prompt)==reg['tokens'],'exact fixed prompt')
  need(ids(out)and 1<=len(out)<=512 and out==row['result']['tokens']and row['max_new']==512 and row['cached_tokens']==0 and row['prompt_state_reused']is False,'actual cold output continuation')
  eos=row['eos_token_ids'];need(eos==[248044,248046]and(len(out)==512 or out[-1]in eos)and not any(x in eos for x in out[:-1]),'actual naturalEOS extent')
  tokens=prompt+out;need(len(tokens)<=4096,'reference context capacity')
  cases.append(dict(index=i,id=row['id'],gpu_record=str(path),gpu_record_sha256=sha(path),prompt_source=str(promptfile),prompt_source_sha256=sha(promptfile),prompt_tokens=len(prompt),generated_tokens=len(out),input_tokens=tokens,packed_input_sha256=packed(tokens),packed_generated_sha256=packed(out),score_from=len(prompt)))
  files[str(path)]=sha(path);files[str(promptfile)]=sha(promptfile)
 dest.mkdir();paths=[]
 for c in cases:
  path=dest/f'input-{c["index"]:02d}.json';save(path,dict(tokens=c.pop('input_tokens'),score_from=c['score_from'],full_rows=[]));c.update(input=str(path),input_sha256=sha(path));paths.append(str(path))
 listing=dest/'inputs.txt';listing.write_text(''.join(x+'\n'for x in paths))
 save(dest/'inputs.json',dict(schema='ownrt.fresh-twelve.cpu-inputs.v1',gpu_output=str(gpu),cases=cases,source_files=files,input_list=str(listing),input_list_sha256=sha(listing),expected_case_count=12,runtime_oracle=False))
 return dest/'inputs.json'
def validate_rows(path,c):
 data=json.loads(Path(c['input']).read_text());tokens=data['tokens'];rows=[json.loads(x)for x in path.read_text().splitlines()]
 need([r['position']for r in rows]==list(range(c['score_from']-1,len(tokens))),'complete contiguous predicted-position coverage')
 findings=[];margins=[]
 for r in rows:
  p=r['position'];top=r['top'];need(len(top)==20 and len({v[0]for v in top})==20 and r['argmax']==top[0][0]and all(type(v[0])is int and 0<=v[0]<248320 and all(math.isfinite(x)for x in v[1:])for v in top),'finite complete argmax/top20')
  need(all(top[i][1]>=top[i+1][1]for i in range(19)),'top20 order')
  margins.append(dict(position=p,margin=top[0][1]-top[1][1],argmax=r['argmax']))
  if p+1<len(tokens):
   need(r['next']==tokens[p+1]and math.isfinite(r['next_logit'])and math.isfinite(r['next_logprob']),'exact actual predicted input token provenance')
   if r['argmax']!=tokens[p+1]:findings.append(dict(position=p,output_index=p+1-c['score_from'],actual_generated=tokens[p+1],cpu_argmax=r['argmax'],margin=margins[-1]['margin']))
  else:need('next'not in r,'last row has no invented next token')
 return dict(rows=len(rows),scored_generated_tokens=c['generated_tokens'],matches=c['generated_tokens']-len(findings),mismatches=findings,margins=margins,rows_sha256=sha(path),rows_bytes=path.stat().st_size)
def preflight(authority):
 authority=authority.resolve();suite=json.loads(authority.read_text());build=json.loads((HERE/'compiled-identity.json').read_text())
 for p,h in build['pins'].items():need(sha(p)==h,'reference build/source pin:'+p)
 need(sha(build['binary'])==build['binary_sha256'],'reference binary identity')
 need(sha(suite['input_list'])==suite['input_list_sha256']and len(suite['cases'])==12,'exact12 input list')
 for p,h in suite['source_files'].items():need(sha(p)==h,'actual GPU/input authority:'+p)
 for c in suite['cases']:
  need(sha(c['input'])==c['input_sha256'],'prepared input identity');d=json.loads(Path(c['input']).read_text());need(packed(d['tokens'])==c['packed_input_sha256']and d['score_from']==c['score_from']and d['full_rows']==[],'prepared scoring identity')
 old=json.loads(Path('/dev/shm/sc117-reference-prefix178-cpu-20261028-r1/model/run.json').read_text())
 modelstat={str(p):dict(size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,inode=p.stat().st_ino)for p in sorted(MODEL.parent.glob('*.gguf'))}
 need(modelstat==old['model_files'],'same model files as validated prefix178 CPU run')
 mem={k:int(v.split()[0])*1024 for k,v in(x.split(':',1)for x in Path('/proc/meminfo').read_text().splitlines())}
 need(mem['MemAvailable']>=80*1024**3,'80GiB CPU model startup floor')
 return suite,build,modelstat,mem['MemAvailable']
def run(authority,output,only):
 need(not output.exists(),'fresh exclusive model output; no retry');suite,build,modelstat,mem=preflight(authority)
 if only:print(json.dumps(dict(passed=True,model_loaded=False,MemAvailable=mem)));return
 output.mkdir();env=os.environ.copy()
 for k in list(env):
  if k.startswith(('GGML_CPU_EXACT','EXACT_')):env.pop(k)
 env.update(GGML_CPU_EXACT_F64='1',EXACT_KV='f32',OMP_NUM_THREADS='8')
 cmd=['nice','-n','19','taskset','-c','8-15',build['binary'],str(MODEL),suite['input_list'],str(output),'8']
 rec=dict(argv=cmd,environment={k:v for k,v in env.items()if k.startswith(('GGML_CPU_EXACT','EXACT_','OMP_'))},started=time.time(),MemAvailable=mem,model_files=modelstat,build=build,input_authority=str(authority),input_authority_sha256=sha(authority),runner_sha256=sha(__file__))
 save(output/'run.json',rec)
 with(output/'log.txt').open('w')as log:rc=subprocess.call(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
 rec.update(returncode=rc,finished=time.time());save(output/'run.json',rec);need(rc==0,'model failure retained; no retry')
 lifecycle=json.loads((output/'lifecycle.json').read_text());need(lifecycle==dict(loaded_models=1,completed_fresh_contexts=12,returncode=0),'one model12 completed fresh contexts')
 cases=[]
 for c in suite['cases']:cases.append(dict(c,comparison=validate_rows(output/f'case-{c["index"]:02d}/rows.jsonl',c)))
 save(output/'receipt.json',dict(schema='ownrt.fresh-twelve.cpu-teacherforce.v1',passed=True,lifecycle=lifecycle,process_exit_code=rc,input_authority_sha256=sha(authority),run_sha256=sha(output/'run.json'),cases=cases,generated_tokens=sum(c['generated_tokens']for c in cases),matched_generated_tokens=sum(c['comparison']['matches']for c in cases),fidelity_all_match=all(not c['comparison']['mismatches']for c in cases),scope='Actual GPU continuations teacher-forced by independent CPU; mismatch is a numerical finding, not lifecycle failure. Final unconsumed-next row retained separately. No renewed historical5959/5965 claim.'))
def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='action',required=True);p=sub.add_parser('prepare');p.add_argument('--gpu-output',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p=sub.add_parser('run');p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight-only',action='store_true');a=ap.parse_args()
 if a.action=='prepare':print(prepare(a.gpu_output,a.output))
 else:run(a.inputs,a.output.resolve(),a.preflight_only)
if __name__=='__main__':main()

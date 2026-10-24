#!/usr/bin/env python3
"""Closed CPU reference readback; preserve failed orchestration result."""
import argparse,hashlib,json,math,pathlib,re
P=pathlib.Path(__file__).resolve().parent
RAW=pathlib.Path('/mnt/usb-models/own-xpu-runtime-reference/sc117-cpu-23b0202a-b/runtime-b')
ROOT=pathlib.Path('/home/steve/llm-optimizations');SRC=pathlib.Path('/home/steve/build/flash-next-iq3-baseline-20261010/llama.cpp')
PLAN_SHA='c2027efd2dd9a330a590d26f19b7bde6fd63109d8b423d92dd49a7aad584d3b0'
CUSTOM=P.parents[1]/'quality-expanded/evidence/device-a/review.json'
def need(v,s):
 if not v:raise RuntimeError(s)
def read(p):return json.loads(p.read_text())
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def run():
 need(not (P/'evidence/closed-readback-review.json').exists(),'exclusive review')
 files=sorted(x for x in RAW.rglob('*') if x.is_file());need(len(files)<100 and sum(x.stat().st_size for x in files)<=128<<20,'readback bound')
 index={}
 for f in files:
  need(not f.is_symlink(),'raw symlink');a=f.stat();h=digest(f);b=f.stat();need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns),'unstable raw')
  index[str(f.relative_to(RAW))]={'sha256':h,'bytes':b.st_size,'identity':[b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns]}
 need(index['plan.json']['sha256']==PLAN_SHA==digest(P/'plan.json'),'plan identity')
 plan=read(RAW/'plan.json');terminal=read(RAW/'terminal.json');request=read(RAW/'request.json');owner=read(RAW/'owner.json');monitor=read(RAW/'monitor.json');answer=read(RAW/'response.json');response=answer['response']
 for name,h in plan['source_sha256'].items():need(digest(pathlib.Path(name))==h,'source drift '+name)
 need(terminal['passed'] is False and terminal['first_error']=="RuntimeError('effective sampler settings')",'preserve exact validator failure')
 need(terminal['owner_exited'] and terminal['returncode']==0 and terminal['signal_sent_once'],'safe close')
 proc=pathlib.Path('/proc',str(owner['pid']),'stat')
 if proc.exists():
  v=proc.read_text().rsplit(')',1)[1].split();need(v[19]!=str(owner['start_ticks']) or v[0] in ['Z','X'],'owner still live')
 need(request==plan['request'] and len(request['prompt'])==87 and request['temperature']==-1,'request')
 need(answer['status']==200 and response['tokens_evaluated']==87 and response['tokens_predicted']==32 and not response['truncated'] and response['stop_type']=='limit' and response['stop'],'complete bounded response')
 g=response['generation_settings'];expected={'temperature':0,'samplers':['temperature'],'seed':0,'n_predict':32,'ignore_eos':False,'n_probs':32,'post_sampling_probs':False,'repeat_penalty':1,'presence_penalty':0,'frequency_penalty':0,'dynatemp_range':0,'mirostat':0,'dry_multiplier':0,'backend_sampling':False,'speculative.types':'none','logit_bias':[],'grammar':''}
 for k,v in expected.items():need(g[k]==v,'effective setting '+k)
 # Verify the actual source normalization, rather than changing a live validator.
 schema=(SRC/'tools/server/server-schema.cpp').read_text();sampler=(SRC/'src/llama-sampler.cpp').read_text()
 need('field_num("temperature", params.sampling.temp))\n        ->set_limits(0.0f, std::numeric_limits<float>::infinity())' in schema,'temperature schema')
 need('val = std::max(min, std::min(max, data.at(n).template get<T>()));' in schema,'clamp source')
 need('if (temp <= 0.0f)' in sampler and 'cur_p->data[max_i].logit = -INFINITY;' in sampler,'greedy source')
 tokens=response['tokens'];probs=response['completion_probabilities'];need(len(tokens)==len(probs)==32,'32 token/probability rows')
 margins=[]
 for token,row in zip(tokens,probs):
  top=row['top_logprobs'];need(token==row['id'] and len(top)==32 and len({x['id'] for x in top})==32,'top32 IDs')
  logs=[x['logprob'] for x in top];need(all(isinstance(x,(int,float)) and math.isfinite(x) for x in logs),'finite logprobs')
  need(logs==sorted(logs,reverse=True) and top[0]['id']==token and row['logprob']==logs[0],'chosen argmax')
  margins.append(logs[0]-logs[1])
 custom=read(CUSTOM);need(digest(CUSTOM)=='c70ee06dc9f51e8f3e5506b73fba7b442217421d3e986096d23e3230ccd70ead','custom authority')
 old=custom['prompts'][0]['arms'][0]['tokens'];first=next((i for i,(a,b) in enumerate(zip(tokens,old)) if a!=b),None);need(tokens==old[:32],'report observed fixed32 prefix')
 log=(RAW/'server.log').read_text();kv=re.findall(r'^.*K \(bf16\).*V \(bf16\).*$',log,re.M);rs=re.findall(r'^.*R \(f32\).*S \(f32\).*P \(f32\).*$',log,re.M);need(kv and rs,'actual allocation dtypes')
 need(monitor and all(x['mem_available']>=8*(1<<30) for x in monitor),'memory samples')
 need(all(re.search(r'^Pid:\s+'+str(owner['pid'])+r'$',x['status'],re.M) for x in monitor),'monitored owner')
 source_files=[SRC/'tools/server/server-schema.cpp',SRC/'src/llama-sampler.cpp',SRC/'common/sampling.cpp',SRC/'src/llama-kv-cache.cpp',SRC/'src/llama-memory-recurrent.cpp',P/'once.py',P/'audit.py']
 out={'schema':'gsq.reference.cpu.closed-readback.v1','evidence_review_passed':True,'original_runtime_terminal_passed':False,'original_runtime_terminal_preserved':True,'postresponse_validator_bug':'Frozen validator expected temperature=-1 echo. Actual schema clamps to0; temp<=0 is greedy. One complete response survives; no rerun.','independent_effective_request_validation_passed':True,'prompt_tokens':87,'output_tokens':tokens,'stop_type':response['stop_type'],'all32_original_custom_prefix_equal':True,'first_differing_index':first,'chosen_argmax_rows':32,'top_candidates_per_row':32,'logprob_margin_min':min(margins),'response_content':response['content'],'reference_binary_sha256':plan['binary_sha256'],'custom_binary_sha256':custom['native_binary_sha256'],'actual_dtype_logs':kv+rs,'owner':owner,'safe_exit':True,'single_sigterm':True,'monitor_samples':len(monitor),'minimum_mem_available':min(x['mem_available'] for x in monitor),'accelerator_observation_scope':'Frozen no_device checks ran before each retained monitor sample; raw FD/map lists were not retained. Static library/backend/environment evidence and successful sampled checks are established, not exhaustive transient-FD exclusion.','source_sha256':{str(x):digest(x) for x in source_files},'artifact_index':index,'limitations':['One prompt87/32 continuation only; no broad quality or throughput qualification.','This tests unchanged CPU reference against historical custom BF16-state binary5aef; it does not qualify the not-yet-run F32 correction.','No custom logits were retained, so token agreement is not distribution equality.','Raw terminal remains failed; independent evidence validation is separately reported.']}
 for f in files:
  st=f.stat();need([st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]==index[str(f.relative_to(RAW))]['identity'],'raw changed during audit')
 with (P/'evidence/closed-readback-review.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
 print(json.dumps({'evidence_review_passed':True,'original_terminal_passed':False,'matched_tokens':32,'review_sha256':digest(P/'evidence/closed-readback-review.json')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');a=p.parse_args();need(a.run,'explicit closed readback required');run()

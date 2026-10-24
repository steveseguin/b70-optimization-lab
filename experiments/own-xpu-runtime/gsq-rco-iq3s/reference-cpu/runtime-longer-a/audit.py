#!/usr/bin/env python3
"""Independent closed three-request CPU reference readback. Root alone invokes --run."""
import argparse,hashlib,json,math,os,pathlib,re,stat
P=pathlib.Path(__file__).resolve().parent
RAW=pathlib.Path('/mnt/usb-models/own-xpu-runtime-reference/sc117-cpu-23b0202a-b/runtime-longer-a')
PLAN_SHA='c32288583d1cc40369c81e6722e3f955d9d9828ba7250a743389224a13538079'
BINARY='256d4043888e16c387ae0ed51061c9a3839f9d8112ea985e8b4c99f65d23b8ee'
PARENT=P.parent/'runtime-b/audit.py'
PARENT_SHA='f5ecadd37e369b4b5d8e8c015a692b4554cfcf13201a26a6bfc31803dca96f27'
SOURCE=pathlib.Path('/home/steve/build/flash-next-iq3-baseline-20261010/llama.cpp')
def need(v,msg):
 if not v:raise ValueError(msg)
def stamp(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def unique(pairs):
 out={}
 for k,v in pairs:need(k not in out,'duplicate JSON key');out[k]=v
 return out
def parse(b):return json.loads(b,object_pairs_hook=unique)
def held_bytes(p,cap=128<<20):
 need(p.resolve()==p,'canonical artifact path')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<=s.st_size<=cap,'bounded regular artifact')
  data=bytearray()
  while len(data)<s.st_size:
   b=os.read(fd,min(1<<20,s.st_size-len(data)));need(b,'artifact truncated');data.extend(b)
  need(stamp(s)==stamp(os.fstat(fd))==stamp(os.stat(p,follow_symlinks=False)),'artifact changed')
  return bytes(data),{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'identity':stamp(s)}
 finally:os.close(fd)
def digest(p):return held_bytes(p)[1]['sha256']
def load(p):return parse(held_bytes(p)[0])
def check_response(response,request):
 tokens=response['tokens'];need(type(tokens)is list and 0<len(tokens)<=512 and all(type(t)is int and 0<=t<248320 for t in tokens),'all generated IDs/count')
 need(response['tokens_evaluated']==len(request['prompt']) and response['tokens_predicted']==len(tokens),'prompt/output counts')
 need(response['timings']['prompt_n']==len(request['prompt']) and response['timings']['cache_n']==0 and response['truncated'] is False,'cold full raw prompt')
 need(response['stop'] is True and response['stop_type'] in ('eos','limit'),'bounded stop reason')
 need(response['stop_type']!='limit' or len(tokens)==512,'full requested cap')
 expected={'temperature':0,'samplers':['temperature'],'seed':0,'n_predict':512,'ignore_eos':False,'n_probs':32,'post_sampling_probs':False,'repeat_penalty':1,'presence_penalty':0,'frequency_penalty':0,'dynatemp_range':0,'mirostat':0,'dry_multiplier':0,'backend_sampling':False,'speculative.types':'none','logit_bias':[],'grammar':'','lora':[]}
 g=response['generation_settings']
 for k,v in expected.items():need(g[k]==v,'effective generation '+k)
 rows=response['completion_probabilities'];need(type(rows)is list and 0<len(rows)<=len(tokens),'reported probability extent')
 cursor=0;margins=[]
 for row in rows:
  token=row['id'];need(type(token)is int,'probability token type')
  while cursor<len(tokens) and tokens[cursor]!=token:cursor+=1
  need(cursor<len(tokens),'probability rows ordered subsequence');cursor+=1
  top=row['top_logprobs'];need(len(top)==32 and len({r['id'] for r in top})==32 and all(type(r['id'])is int and 0<=r['id']<248320 for r in top),'32 valid unique candidate IDs')
  logs=[r['logprob'] for r in top];need(all(type(x)in (int,float) and math.isfinite(x) for x in logs) and type(row['logprob'])in (int,float) and math.isfinite(row['logprob']),'finite probability logs')
  need(logs==sorted(logs,reverse=True),'descending retained candidates')
  selected=[r for r in top if r['id']==token];need(len(selected)==1 and selected[0]['logprob']==row['logprob']==logs[0],'chosen greedy argmax, ties allowed')
  margins.append(logs[0]-logs[1])
 need(type(response['content'])is str,'full returned text retained')
 return {'generated_tokens':len(tokens),'reported_probability_rows':len(rows),'omitted_probability_rows':len(tokens)-len(rows),'all_reported_rows_greedy_argmax':True,'probability_alignment':'Ordered subsequence only; source suppresses rows while accumulated UTF8 is incomplete. Repeated IDs prevent unique per-position inference; all output IDs remain the token oracle.'},min(margins)
def closure(terminal,owner):
 need(terminal['passed'] is True and terminal['first_error'] is None and terminal['response_valid'] is True and terminal['completed_requests']==3,'successful three-request terminal')
 need(terminal['owner_exited'] and terminal['returncode']==0 and terminal['signal_sent_once'],'one graceful safe owner close')
 need(terminal['plan_sha256']==PLAN_SHA,'terminal plan')
 need(type(owner['pid'])is int and owner['pid']>0,'owner PID')
 proc=pathlib.Path('/proc',str(owner['pid']),'stat')
 if proc.exists():
  fields=proc.read_text().rsplit(')',1)[1].split();need(fields[19]!=str(owner['start_ticks']) or fields[0]in ('Z','X'),'matching owner still live')
def run():
 need(digest(PARENT)==PARENT_SHA,'qualified parent auditor source')
 need(digest(P/'plan.json')==PLAN_SHA,'admitted local plan')
 plan=load(P/'plan.json');need(plan['binary_sha256']==BINARY and plan['output']==str(RAW),'exact reference binary/run')
 for name,h in plan['source_sha256'].items():need(digest(pathlib.Path(name))==h,'admitted source drift '+name)
 need(digest(RAW/'plan.json')==PLAN_SHA,'actual launched plan')
 terminal=load(RAW/'terminal.json');owner=load(RAW/'owner.json');closure(terminal,owner)
 # Closed artifacts only: no model/header reads or endpoint requests.
 files=sorted(x for x in RAW.rglob('*') if x.is_file());need(len(files)<100 and sum(x.stat().st_size for x in files)<=128<<20,'bounded closed inventory')
 index={};data={}
 for f in files:
  b,m=held_bytes(f);index[str(f.relative_to(RAW))]=m
  if f.suffix=='.json':data[str(f.relative_to(RAW))]=parse(b)
  elif f.name=='server.log':data['server.log']=b.decode('utf-8',errors='replace')
 need(data['terminal.json']==terminal and data['owner.json']==owner and index['plan.json']['sha256']==PLAN_SHA,'stable initial closure')
 requests=data['requests.json'];need(requests==plan['requests'] and len(requests)==3,'fixed serial request list')
 request_manifest=load(P/'requests.json');need(requests==request_manifest['cases'],'fixed prompt authority')
 manifest_path=pathlib.Path(request_manifest['manifest_path']);need(digest(manifest_path)==request_manifest['manifest_sha256'],'original numeric prompt manifest');manifest=load(manifest_path)
 template=load(P.parent/'request-proposal.json');cases=[];completed=[]
 for i,case in enumerate(requests):
  need(case==dict(index=i,id=manifest['prompts'][i]['prompt_id'],request=dict(template,prompt=manifest['prompts'][i]['tokens'],n_predict=512,temperature=0)),'exact original prompt/order/settings')
  prefix=f'request-{i:02d}';need(data[prefix+'.json']==case,'actual request file');answer=data[prefix+'-response.json'];need(answer['status']==200,'successful HTTP response')
  response=answer['response'];prob,min_margin=check_response(response,case['request'])
  item=dict(index=i,id=case['id'],response_sha256=index[prefix+'-response.json']['sha256'],tokens=response['tokens'],stop_type=response['stop_type'],probability_evidence=prob)
  need(data[prefix+'-validation.json']==dict(passed=True,request_sha256=index[prefix+'.json']['sha256'],**item),'independently reconstructed live validation')
  completed.append(item);cases.append(dict(**item,prompt_tokens=case['request']['prompt'],prompt_token_count=len(case['request']['prompt']),response_path=str(RAW/(prefix+'-response.json')),output_tokens=len(response['tokens']),full_text=response['content'],minimum_reported_top2_logprob_margin=min_margin,termination='natural_eos' if response['stop_type']=='eos' else 'cap512',probability_scope='Missing probability rows are not synthesized; repeated-token subsequence positions may be ambiguous.'))
 full=data['reference-results.json'];need(full['passed'] and full['cases']==completed,'all completed serial responses')
 log=data['server.log'];kv=re.findall(r'^.*K \(bf16\).*V \(bf16\).*$',log,re.M);rs=re.findall(r'^.*R \(f32\).*S \(f32\).*P \(f32\).*$',log,re.M);need(kv and rs,'actual BF16 KV/F32 recurrent dtype logs')
 samples=data['monitor.json'];need(samples and all(x['mem_available']>=8*(1<<30) for x in samples),'memory floor samples')
 need(all(re.search(r'^Pid:\s+'+str(owner['pid'])+r'$',x['status'],re.M) for x in samples),'monitored same owner')
 need(all(0<=x['elapsed']<3600 for x in samples) and all(a['elapsed']<=b['elapsed'] for a,b in zip(samples,samples[1:])),'ordered bounded monitor times')
 for f in files:need(stamp(os.stat(f,follow_symlinks=False))==index[str(f.relative_to(RAW))]['identity'],'closed artifact changed during audit')
 need(files==sorted(x for x in RAW.rglob('*') if x.is_file()),'inventory changed')
 return dict(schema='gsq.reference.cpu.three.closed-readback.v1',passed=True,evidence_review_passed=True,original_runtime_terminal_passed=True,plan_sha256=PLAN_SHA,reference_binary_sha256=BINARY,binary_sha256=BINARY,owner_exited=True,returncode=0,source_sha256={str(P/'audit.py'):digest(P/'audit.py'),str(P/'once.py'):digest(P/'once.py'),str(PARENT):PARENT_SHA},cases=cases,request_count=3,actual_dtype_logs=kv+rs,owner=owner,safe_exit=True,single_sigterm=True,monitor_samples=len(samples),minimum_mem_available=min(x['mem_available'] for x in samples),artifact_index=index,source_and_header_scope='Plan/source pins independently checked. Frozen successful runner authenticated fixed model-header prefixes before load and rechecked model stat identities on exit; no header/payload reread by this auditor.',accelerator_observation_scope='Frozen runner checked accelerator FDs and exact mapped-library allowlist before every retained monitor sample; raw FD/maps not retained, so no exhaustive transient-FD exclusion claim.',native_comparison_performed=False,quality_qualified=False,limitations=['Three original short input prompts87/90/77 at output cap512, not general quality or long-input coverage.','Every generated token ID including EOS retained; probability rows can be missing for incomplete UTF8 steps.','After native/reference output divergence, later free-running logits use different prefixes and are not aligned error measurements.','Reference uses F32 tensor activations with quantized CPU matmul intermediates; native precision comparison remains a separate task.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');a=p.parse_args();need(a.run,'explicit root closed readback required');out=P/'evidence/closed-readback-review.json'
 with out.open('x') as f:
  try:r=run()
  except BaseException as e:r={'passed':False,'error':repr(e),'auditor_sha256':digest(P/'audit.py')};json.dump(r,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());raise
  json.dump(r,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 print(json.dumps({'passed':True,'review_sha256':digest(out),'cases':3}))

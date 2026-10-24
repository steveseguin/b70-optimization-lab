#!/usr/bin/env python3
"""Root-operated actual Host Engine pair: initial RESET, none, RESET, MTP, repeat DUMP, close."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,resource,shutil,struct,time
P=Path(__file__).resolve().parent;F=P.parent;L=F.parent;R=F.parents[3]
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-recurrent-f32-host-a.control')
ADAPTER=L/'serving/adapter.py';READER=L/'state-bundle/reader.py'
ADAPTER_SHA='68538b214b7bda9c2fa5cd87534bad2243745b8a1af0dc82b43f01da48b06a01'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,s):
 if not x:raise RuntimeError(s)
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def save(p,r):
 with p.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
def limits():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'placement');need(all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')),'threads')
 resource.setrlimit(resource.RLIMIT_AS,(4<<30,4<<30));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 need(shutil.disk_usage(R).free>=27000000000+(64<<20),'root reserve unchanged')
 if CONTROL.exists():need(sum(f.stat().st_size for f in CONTROL.rglob('*') if f.is_file())<=32<<20,'Host evidence32MiB bound')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true',required=True);ap.parse_args();limits()
 need(sha(ADAPTER)==ADAPTER_SHA,'frozen adapter');bpath=P/'evidence/build.json';build=json.loads(bpath.read_text());need(build['passed'] and build['mode']=='host' and not build['binary_invoked'],'Host build')
 need(sha(build['binary'])==build['binary_sha256'],'Host binary')
 for f,h in build['source_sha256'].items():need(sha(f)==h,'Host source '+f)
 for f,h in build['object_sha256'].items():need(sha(f)==h,'Host object')
 need(not CONTROL.exists(),'fresh control, no retry');CONTROL.mkdir(mode=0o700)
 A=load(ADAPTER,'rf32_host_adapter');B=load(READER,'rf32_bundle_reader');original_build=A.build_plan;original_command=A.command
 def command(plan,rank,channel,stop):return original_command(plan,rank,channel,stop)+['--recurrent-f32']
 A.command=command
 def plan_builder(output,**kw):
  need(kw.get('mini') is True,'CPU miniature only');p=original_build(output,**kw);p.update(binary=build['binary'],binary_sha256=build['binary_sha256'],build_receipt=str(bpath),build_receipt_sha256=sha(bpath),build_ready=True)
  p['rank_argv']=[command(p,r,'<channel-fd>','<stop-fd>') for r in range(2)];p['command_sha256']=hashlib.sha256(json.dumps({'argv':p['rank_argv'],'environment':p['environment']},sort_keys=True).encode()).hexdigest();return p
 A.build_plan=plan_builder
 def validate(p):
  need(p==plan_builder(p['output'],mini=True,max_new=p['max_new'],seconds=p['seconds'],evidence_output=p['evidence_output']),'exact Host plan');need(sha(p['binary'])==p['binary_sha256'],'binary changed');return build
 A.validate_plan=validate
 def state(t):
  result={}
  for rank in (0,1):
   t.call(rank,A.BASE.DUMP,position=2147483647);result[str(rank)]=B.read_state(t.request_output/f'rank{rank}/state-2147483647')
  return result
 A.state_hashes=state
 plan=A.build_plan(CONTROL/'run',mini=True,max_new=4,seconds=120);A.validate_plan(plan);save(CONTROL/'plan.json',plan)
 receipt={'passed':False,'scope':'Actual tiny Host Engine F32 recurrence, snapshot/rollback/RESET and target-MTP lifecycle; no real model or GPU','source_sha256':{str(p):sha(p) for p in [Path(__file__),ADAPTER,READER,bpath]},'binary_sha256':build['binary_sha256'],'rows':[],'device_executed':False,'real_model_loaded':False}
 t=A.Transport.__new__(A.Transport);counts={'recurrent_ranges':0,'non_bf16_f32_words':0,'kv_ranges':0}
 def inspect(directory,zero=False):
  rows=(directory/'state-index.tsv').read_text().splitlines()[1:]
  with (directory/'state.bundle').open('rb') as stream:
   for line in rows:
    name,off,length,h=line.split('\t');n=int(length)
    recurrent=name.endswith(('.gdn.state.bin','.gdn.history.bin','ple.history.bin'))
    if recurrent:
     expected=192 if name.endswith('.gdn.state.bin') else 240 if name.endswith('.gdn.history.bin') else 2304
     need(n==expected,'actual F32 tiny extent '+name);counts['recurrent_ranges']+=1;stream.seek(int(off));data=stream.read(n);need(hashlib.sha256(data).hexdigest()==h,'actual recurrent bytes')
     if zero:need(not any(data),'initial recurrence nonzero')
     else:counts['non_bf16_f32_words']+=sum((v&65535)!=0 for (v,) in struct.iter_unpack('<I',data))
    if name.endswith(('.qsa.keys.bin','.qsa.values.bin','.qsa.raw.bin','.qsa.pooled.bin')):
     need(n==(128 if name.endswith('.qsa.pooled.bin') else 512),'BF16 tiny attention extent');counts['kv_ranges']+=1
 try:
  def admit(p):need(p==plan and p['mini'] and '--authorized-device-window' not in p['rank_argv'][0],'Host only')
  t.__init__(plan,admit=admit,check=limits,launch_hook=lambda pid:None);t.request_output=t.out
  initial=state(t)
  for rank in (0,1):inspect(t.out/f'rank{rank}/state-2147483647',True)
  A.reset(t,t.out/'none-request');reset_trace=[{'phase':'initial','acknowledged':True}]
  for mode in ('none','mtp'):
   if mode=='mtp':A.reset(t,t.out/'mtp-request');reset_trace.append({'phase':'previous-none','acknowledged':True})
   result=A.BASE.NativeController(t,A.BASE.Draft(mode),True,False).run([2,5,3],4,())
   logical=state(t);save(CONTROL/(mode+'-result.json'),result)
   for rank in (0,1):inspect(t.request_output/f'rank{rank}/state-2147483647')
   receipt['rows'].append({'mode':mode,'tokens':result['tokens'],'state':logical,'guess_rows':result['guess_rows'],'output':str(t.request_output)})
  x,y=receipt['rows'];need(x['tokens']==y['tokens'] and len(x['tokens'])==4,'confirmed token equivalence');need(x['state']==y['state'],'corrected final target state equivalence')
  need(any(not r['hit'] for r in y['guess_rows']) and any(r['hit'] for r in y['guess_rows']),'actual rejection and acceptance required')
  need(state(t)==y['state'],'explicit repeated final DUMP');t.close(True)
  rank_receipts=[json.loads((t.out/f'rank{r}/receipt.json').read_text()) for r in (0,1)];need(all(r['passed'] and not r['device_executed'] and len(r['teardown'])==1 for r in rank_receipts),'Host rank receipts');owners=[r['teardown'][0] for r in rank_receipts]
  need(all(o.get('safe_to_exit') and o.get('in_flight')==0 and o.get('live_bytes')==0 for o in owners),'safe Host owner closure');need(all(p.poll()==0 for p in t.children),'clean Host children')
  for row in receipt['rows']:
   closed={str(rank):B.read_state(Path(row['output'])/f'rank{rank}/state-2147483647') for rank in (0,1)};need(closed==row['state'],'closed target map changed')
  snapshot=json.loads((t.request_output/'rank0/speculative-snapshot.json').read_text());need(snapshot['captures']>0 and snapshot['restores']>0 and not snapshot['snapshot_valid'],'actual rollback lifecycle')
  need(counts['recurrent_ranges'] and counts['kv_ranges'] and counts['non_bf16_f32_words'],'nonvacuous F32 retention and BF16 KV')
  receipt.update(passed=True,counts=counts,owners=owners,reset_trace=reset_trace,snapshot=snapshot,initial_state=initial,repeat_dump_acknowledged=True)
 except BaseException as e:
  receipt['error']=repr(e)
  try:A.cleanup_failure(t,e)
  except A.RetainedOwner as retained:
   receipt['retained']=True;save(CONTROL/'retained.json',receipt)
   while getattr(t,'spawn_uncertain',False) or any(c.poll() is None for c in getattr(t,'children',[])):time.sleep(1)
  raise
 finally:save(CONTROL/'receipt.json',receipt)
 save(P/'evidence/lifecycle.json',receipt);print(json.dumps({'passed':True,'receipt_sha256':sha(P/'evidence/lifecycle.json'),'counts':counts}))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Explicit CPU-only native tests, AFTER authorized compilation. Never chooses a device binary."""
import argparse,hashlib,importlib.util,json,os,resource,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];sys.path.insert(0,str(P))
from build_engine import limits
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run-host-only',action='store_true');a=ap.parse_args()
 if not a.run_host_only:ap.error('explicit --run-host-only required; compile and coordinator authorization come first')
 limits();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 build=load(P/'evidence/build-compile-only.json');assert build['passed'] and build['device_executed'] is False
 assert build['source_overlay_sha256']==sha(P/'evidence/source-overlay.json')
 plans={x['target']:x for x in build['plans']}
 for target in ('protocol','host'):assert sha(plans[target]['binary'])==plans[target]['binary_sha256']
 host=Path(plans['host']['binary']);assert host==P/'build/host/own-rt-iq3'
 assert '-DOWN_RT_HOST_ONLY' in plans['host']['commands'][0] and '/usr/bin/g++'==plans['host']['commands'][0][0]
 protocol=subprocess.run([plans['protocol']['binary']],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15);assert protocol.returncode==0,(protocol.stdout,protocol.stderr)
 spec=importlib.util.spec_from_file_location('parent_native_env',P.parent/'packet181-session-swap-v3/one-card/native_env.py');envmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(envmod);env=envmod.environment('A')
 spec=importlib.util.spec_from_file_location('request_front_client',ROOT/'experiments/own-xpu-runtime/integration/request_front/client.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
 run=P/'build'/('host-probe-'+time.strftime('%Y%m%dT%H%M%S',time.gmtime()));run.mkdir();tid=run/'tokenizer.tsv'
 tid.write_text('format\townrt.tokenizer-identity.v1\ngguf_header_sha256\t'+'1'*64+'\ntokenizer_source_sha256\t'+'2'*64+'\nvocab_bin_sha256\t'+'3'*64+'\n')
 base=[str(host),'--mini','--pipeline-mini','--context','64','--retain-steps','none','--native-nice','19','--seconds','120']
 fixed=['--request-front','--request-front-max-requests','16','--request-front-idle-seconds','10','--request-front-checkpoints',str(run/'checkpoints'),'--request-front-tokenizer-identity',str(tid)]
 # Real parser refusals precede model initialization, not Python replicas of it.
 for name,argv in [('missing-bounds',base+['--request-front','--output',str(run/'bad-missing')]),('zero-bound',base+fixed+['--request-front-max-requests','0','--output',str(run/'bad-zero')]),('mixed-input',base+fixed+['--input',str(tid),'--output',str(run/'bad-mixed')])]:
  cp=subprocess.run(argv,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15);assert cp.returncode!=0,name
  assert not (Path(argv[argv.index('--output')+1])/'device-contact.json').exists()
 output=run/'owner';argv=base+fixed+['--output',str(output)]
 with (run/'stderr.log').open('wb') as log:
  proc=subprocess.Popen(argv,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
  try:
   front=client.NativeFront(proc,context=64,vocab=16,max_requests=16,startup_timeout=30,request_timeout=30)
   assert front.ready['model_loads']==1 and front.ready['experimental'] is True and front.ready['context']==64 and front.ready['vocab']==16
   events=[]
   def request(name,tokens,cap,**kwargs):
    response=front.request(name,tokens,cap,**kwargs);row=load(output/'requests'/name/'result.json')
    assert row['passed'] and row['tokens']==response['tokens'];assert response['completion']['request_quiesced'] is True
    assert row['request_front_scope']=='experimental-warm-owner-v1' and row['session_reuse'] is bool(kwargs.get('restore'))
    assert row['cached_tokens']==(row['checkpoint']['restore']['saved_prefix_length'] if kwargs.get('restore') else 0)
    assert load(output/'requests'/name/'reset.json')['cached_tokens']==0
    events.append(dict(id=name,tokens=row['tokens'],checkpoint=row['checkpoint']));return row['tokens']
   A=[2,5,3,7,1];B=[4,6,2,8];saved=request('fresh-a',A,8,save='s1')
   b=request('fresh-b',B,4)
   resumed=request('resume-a',A,4,restore='s1',save='s2')
   appended=A+saved+[4,6,9,2,8,3]
   x=request('append-a',appended,4,restore='s1',save='s3')
   y=request('append-repeat',appended,4,restore='s1',save='s4')
   z=request('append-fresh',appended,4,save='s5')
   reference=request('fresh-a-reference',A,12)
   repeat_b=request('fresh-b-repeat',B,4)
   assert len(saved)==8 and len(resumed)==4 and saved+resumed==reference
   assert x==y==z and b==repeat_b
   def state(name):
    directory=run/'checkpoints'/name;m=load(directory/'manifest.json')
    assert m['label']=='experimental-warm-front' and m['contract']=='v1.2+p197' and m['qualified_by']['device_gates']==[]
    return {n:sha(directory/n) for n in ('tokens.bin',*[v['name']+'.bin' for v in m['blobs']])}
   assert state('s3')==state('s4')==state('s5'),'append/repeat/fresh checkpoint state mismatch'
   stopped=front.close();assert stopped['safe_to_exit'] is True and proc.returncode==0
   receipt=load(output/'receipt.json');assert receipt['safe_to_exit'] is True and receipt['device_executed'] is False
  except BaseException:
   # A single cooperative incident stop. Never kill or restart; retain a stuck owner for the coordinator.
   if proc.poll() is None:proc.terminate()
   try:proc.wait(timeout=65)
   except subprocess.TimeoutExpired:print('HOST OWNER RETAINED PID '+str(proc.pid),file=sys.stderr)
   raise
 row=dict(passed=True,device_executed=False,host_native_executed=True,model_loads=1,requests=len(events),protocol_probe_passed=True,actual_argv_refusals=3,save_resume_exact=True,append_repeat_fresh_state_exact=True,events=events,run_directory=str(run),binary_sha256=sha(host),scope='Synthetic tiny geometry, real host-only entry/reset/checkpoint logic; no device or production arithmetic/performance qualification.')
 (P/'evidence/host-probe.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(dict(passed=True,requests=len(events),device_executed=False)))
if __name__=='__main__':main()

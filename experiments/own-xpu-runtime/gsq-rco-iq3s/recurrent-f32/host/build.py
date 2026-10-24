#!/usr/bin/env python3
"""Root-operated GNU Host build; never invokes resulting binary."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,sys
P=Path(__file__).resolve().parent;F=P.parent;R=F.parents[3];OUT=Path('/mnt/usb-models/own-xpu-runtime-builds/gsq-recurrent-f32-host-a')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,s):
 if not v:raise RuntimeError(s)
def limits():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement');need(all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')),'threads')
 resource.setrlimit(resource.RLIMIT_AS,(4<<30,4<<30));resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_FSIZE,(128<<20,128<<20))
 need(shutil.disk_usage(R).free>=27000000000+(64<<20),'root floor');need(Path('/mnt/usb-models').stat().st_dev==2050,'USB identity');need(shutil.disk_usage('/mnt/usb-models').free>=(2<<30)+(384<<20),'USB output128+temporary256MiB reservations')
def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--build',action='store_true');a=ap.parse_args();prep=json.loads((P/'preparation.json').read_text());m=F/'evidence/materialization.json';need(sha(m)==prep['materialization_sha256'],'materialization');material=json.loads(m.read_text())
 pins={str(R/f):h for f,h in material['generated_sha256'].items()};pins.update(prep['additional_sources']);pins[str(F/'recurrent_policy.hpp')]=material['policy_sha256'];pins.update({str(f):sha(f) for f in [P/'build.py',P/'preparation.json',m,F/'evidence/cpu-proof.json',R/'experiments/own-xpu-runtime/ops/compile_turn.py']})
 need(json.loads((F/'evidence/cpu-proof.json').read_text())['passed'],'CPU proof')
 for f,h in pins.items():need(sha(f)==h,'source drift '+f)
 commands=[];objects=[]
 for i,source in enumerate(prep['sources'].values()):
  obj=str(OUT/(str(i)+'.o'));objects.append(obj);commands.append(prep['flags']+['-MMD','-MF',str(OUT/(str(i)+'.d')),'-c',source,'-o',obj])
 binary=OUT/'gsq-host';commands.append(['/usr/bin/g++','-fopenmp','-Wl,--gc-sections',*objects,'-lcrypto','-o',str(binary)])
 receipt={'mode':'host','passed':False,'commands':commands,'source_sha256':pins,'binary':str(binary),'objects_reused':0,'real_model_loaded':False,'device_executed':False,'binary_invoked':False,'output':str(OUT),'TMPDIR':str(OUT/'tmp')}
 if a.plan:print(json.dumps(receipt,indent=2));return
 limits();need(not OUT.exists(),'fresh output, no automatic retry');need(not (P/'evidence/build.json').exists(),'no overwrite');OUT.mkdir(parents=True);(OUT/'tmp').mkdir();env=dict(os.environ,TMPDIR=str(OUT/'tmp'),TMP=str(OUT/'tmp'),TEMP=str(OUT/'tmp'))
 compiler=commands[0][0];receipt['compiler_sha256']=sha(compiler);turnpath=R/'experiments/own-xpu-runtime/ops/compile_turn.py';sys.modules['build_engine']=sys.modules[__name__];s=importlib.util.spec_from_file_location('rf32_hostturn',turnpath);turn=importlib.util.module_from_spec(s);s.loader.exec_module(turn)
 try:
  with turn.turn():
   for i,cmd in enumerate(commands):
    limits()
    with (OUT/f'command-{i}.log').open('x') as log:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,cwd=R,timeout=300)
    need(r.returncode==0,'command '+str(i))
   deps={}
   for f in OUT.glob('*.d'):
    for name in shlex.split(f.read_text().replace('\\\n',' ').split(':',1)[1]):
     path=str(Path(name).resolve());need(pins.get(path)==sha(path),'unbound dep '+path);deps[path]=pins[path]
   for f,h in pins.items():need(sha(f)==h,'post source drift')
   need(sha(compiler)==receipt['compiler_sha256'],'compiler drift');need(sum(f.stat().st_size for f in OUT.rglob('*') if f.is_file())<384<<20,'retained build total')
   receipt.update(passed=True,dependencies=deps,binary_sha256=sha(binary),object_sha256={o:sha(o) for o in objects})
 except BaseException as e:receipt['error']=repr(e);raise
 finally:(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 with (P/'evidence/build.json').open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({'passed':True,'receipt_sha256':sha(P/'evidence/build.json')}))
if __name__=='__main__':main()

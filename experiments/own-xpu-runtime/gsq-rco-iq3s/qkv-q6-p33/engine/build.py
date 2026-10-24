#!/usr/bin/env python3
"""Compile the generated policy CPU fixture or one full native entry; never run native."""
import argparse,hashlib,importlib.util,json,os,resource,shutil,subprocess,sys,time
from pathlib import Path
import prepare as M
P=M.P;L=M.L;R=M.R
def sha(p):return M.sha(p)
def require(v,m):return M.require(v,m)
def limits():
 require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement')
 require(all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')),'two threads')
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 require(shutil.disk_usage(R).free>=27000000000+250*1024**2,'root floor+250MiB')
def admission():
 old,parent=M.parent();prep=json.loads((P/'preparation.json').read_text())
 for f,h in prep['source_sha256'].items():require(sha(f)==h,'prepared source drift')
 require(prep['objects']==parent['objects'] and prep['sites']==M.selected(),'fixed source/dependency selection')
 return old,prep
def recipe(mode,d,old,prep):
 source=Path(prep['materialized_directory'])
 if mode=='cpu':return [['/usr/bin/g++','-std=gnu++20','-O2','-g0','-fno-fast-math','-ffp-contract=off','-I'+str(source),'-MMD','-MF',str(d/'policy.d'),str(P/'policy_fixture.cpp'),'-o',str(d/'policy')],[str(d/'policy')]],d/'policy'
 cmd=list(old['commands'][0]);cmd[cmd.index('-c')+1]=str(source/'entry.cpp');cmd[cmd.index('-o')+1]=str(d/'entry.o');cmd[cmd.index('-MF')+1]=str(d/'entry.d')
 link=list(old['commands'][-1]);link[link.index(old['commands'][0][-1])]=str(d/'entry.o');link[link.index('-o')+1]=str(d/'gsq-engine')
 return [cmd,link],d/'gsq-engine'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('cpu','native'),required=True);group=ap.add_mutually_exclusive_group(required=True);group.add_argument('--plan',action='store_true');group.add_argument('--build',action='store_true');args=ap.parse_args()
 old,prep=admission();d=P/'build'/('preview-'+args.mode if args.plan else args.mode+'-'+str(time.time_ns()));commands,binary=recipe(args.mode,d,old,prep)
 if args.plan:print(json.dumps(dict(commands=commands,mode=args.mode,objects_reused=39 if args.mode=='native' else 0,compiler_invoked=False),indent=2));return
 limits()
 if args.mode=='native':
  cpu=json.loads((P/'evidence/cpu-proof.json').read_text());require(cpu['passed'] and cpu['preparation_sha256']==sha(P/'preparation.json'),'actual policy CPU proof')
  require(json.loads((P.parent/'evidence/cpu-proof.json').read_text())['passed'],'Q6 arithmetic proof')
  require(json.loads((P.parent/'micro/evidence/device-a/review.json').read_text())['passed'],'Q6 actual native micro proof')
  require(sha(commands[0][0])==old['compiler_sha256'],'same native compiler')
 d.mkdir(parents=True);pins=dict(old['source_sha256'])
 for f,h in {**json.loads((P/'parent-pins.json').read_text()),**prep['source_sha256']}.items():pins[str(Path(f).relative_to(R))]=h
 for f in [P/'build.py',P/'policy_fixture.cpp',P/'preparation.json']:
  pins[str(f.relative_to(R))]=sha(f);shutil.copy2(f,d/f.name)
 turnpath=R/'experiments/own-xpu-runtime/ops/compile_turn.py';pins[str(turnpath.relative_to(R))]=sha(turnpath)
 sys.modules['build_engine']=sys.modules[__name__];spec=importlib.util.spec_from_file_location('combined_compile_turn',turnpath);turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
 receipt=dict(passed=False,mode=args.mode,commands=commands,binary=str(binary),source_sha256=pins,compiler_sha256=sha(commands[0][0]),preparation_sha256=sha(P/'preparation.json'),native_binary_invoked=False,objects_reused=39 if args.mode=='native' else 0)
 try:
  for i,cmd in enumerate(commands):
   with turn.turn(),(d/f'command-{i}.log').open('x') as log:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd=R,timeout=1200 if args.mode=='native' else 60)
   require(r.returncode==0,'command failed '+str(i))
  deps={}
  for dep in d.glob('*.d'):
   for n in dep.read_text().replace('\\\n',' ').split(':',1)[1].split():
    path=Path(n).resolve();key=str(path.relative_to(R));require(pins.get(key)==sha(path),'unbound compiler dependency '+key);deps[key]=sha(path)
  receipt['dependencies']=deps;receipt['binary_sha256']=sha(binary)
  if args.mode=='cpu':receipt['proof']=json.loads((d/'command-1.log').read_text());require(receipt['proof']['passed'],'policy proof')
  else:
   receipt['object_sha256']={x['object']:x['object_sha256'] for x in prep['objects'] if x['reuse']};receipt['object_sha256'][str(d/'entry.o')]=sha(d/'entry.o');receipt['reused_object_provenance']=prep['objects'];receipt['control_compilation_receipt_sha256']=sha(L/'integration/evidence/full-native-build.json')
   symbols=subprocess.check_output(['/usr/bin/nm','-C','--defined-only',str(binary)],text=True,timeout=60);(d/'symbols.log').write_text(symbols)
   require(all(x in symbols for x in ('packet26_model_entry','p33::submit','mtp36::DraftRuntime')),'integrated symbols')
   compiler=Path('/opt/intel/oneapi/compiler/2026.0/bin/compiler');bundler=str(compiler/'clang-offload-bundler');obj=d/'entry.o'
   targets=subprocess.check_output([bundler,'-type=o','-list','-input='+str(obj)],text=True,timeout=60).splitlines();targets=[x for x in targets if x.startswith('sycl-spir64')];require(len(targets)==1,'one entry image')
   bc=d/'entry-device.bc';subprocess.run([bundler,'-type=o','-unbundle','-targets='+targets[0],'-input='+str(obj),'-output='+str(bc)],check=True,timeout=120);subprocess.run([str(compiler/'sycl-post-link'),'-symbols','-split=source','-o',str(d/'kernel.table'),str(bc)],check=True,timeout=120)
   entries='\n'.join(f.read_text() for f in d.glob('kernel*.sym'));(d/'kernel-entries.log').write_text(entries)
   for t in (12,13,18,23,42):require('PackedKernelILj'+str(t)+'E' in entries,'generic format entry')
   receipt['offline']={'entry_device_sha256':sha(bc),'kernel_entries_sha256':sha(d/'kernel-entries.log'),'symbols_sha256':sha(d/'symbols.log'),'p33_object_reused_unchanged':True}
   receipt['prerequisite_sha256']={str(f):sha(f) for f in [P/'evidence/cpu-proof.json',P.parent/'evidence/cpu-proof.json',P.parent/'micro/evidence/device-a/review.json']}
  admission()
  for f,h in pins.items():require(sha(R/f)==h,'final source drift '+f)
  require(sha(commands[0][0])==receipt['compiler_sha256'],'compiler drift');receipt['passed']=True
  dest=P/'evidence'/('native-build.json' if args.mode=='native' else 'cpu-proof.json')
  with dest.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 except BaseException as e:receipt['error']=repr(e);raise
 finally:(d/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({'passed':True,'mode':args.mode,'receipt_sha256':sha(dest)}))
if __name__=='__main__':main()

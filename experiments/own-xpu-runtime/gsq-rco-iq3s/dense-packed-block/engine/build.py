#!/usr/bin/env python3
"""One CPU selector proof or one native entry compile/link; native is never run."""
import argparse,hashlib,importlib.util,json,os,resource,shutil,subprocess,sys,time
from pathlib import Path
import prepare as M
P=M.P;L=M.L;R=L.parents[2];S=M.A
sha=M.sha;need=M.need
MODE='cpu'
def limits():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement')
 need(all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')),'two threads')
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 need(shutil.disk_usage(R).free>=27000000000+(16 if MODE=='cpu' else 250)*1024**2,'root floor plus bounded build')
def admission():
 prep=json.loads((P/'preparation.json').read_text());old=json.loads((S/'evidence/native-build.json').read_text())
 for f,h in {**json.loads((P/'parent-pins.json').read_text()),**prep['source_sha256']}.items():need(sha(f)==h,'source drift '+f)
 need(prep['reused_objects']==39 and old['passed'],'source prerequisites')
 return prep,old
def commands(mode,d,prep,old):
 if mode=='cpu':return [['/usr/bin/g++','-std=gnu++20','-O2','-g0','-fno-fast-math','-ffp-contract=off','-MMD','-MF',str(d/'selector.d'),str(P/'policy_fixture.cpp'),'-o',str(d/'selector')],[str(d/'selector')]],d/'selector'
 cmd=list(old['commands'][0]);oldobj=cmd[cmd.index('-o')+1]
 cmd[cmd.index('-c')+1]=str(Path(prep['materialized_directory'])/'entry.cpp');cmd[cmd.index('-o')+1]=str(d/'entry.o');cmd[cmd.index('-MF')+1]=str(d/'entry.d')
 link=list(old['commands'][-1]);need(link.count(oldobj)==1,'exact parent entry object');link[link.index(oldobj)]=str(d/'entry.o');link[link.index('-o')+1]=str(d/'gsq-engine')
 return [cmd,link],d/'gsq-engine'
def main():
 global MODE
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('cpu','native'),required=True);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--build',action='store_true');a=ap.parse_args();MODE=a.mode
 prep,old=admission();d=P/'build'/('preview-'+a.mode if a.plan else a.mode+'-'+str(time.time_ns()));cmds,binary=commands(a.mode,d,prep,old)
 if a.plan:print(json.dumps(dict(mode=a.mode,commands=cmds,compiler_invoked=False,native_invoked=False),indent=2));return
 limits();dest=P/'evidence'/('cpu-proof.json' if a.mode=='cpu' else 'native-build.json');need(not dest.exists(),'no promoted receipt overwrite')
 pins={}
 if a.mode=='native':
  cpu=json.loads((P/'evidence/cpu-proof.json').read_text());need(cpu['passed'] and cpu['proof']['passed'],'selector CPU proof')
  for f,h in cpu['source_sha256'].items():need(sha(R/f)==h,'CPU drift '+f)
  review=json.loads((S/'operating/evidence/device-a/review.json').read_text());need(review['passed'],'qualified parent Engine')
  micro=json.loads((P.parent/'micro/operating/evidence/device-a/review.json').read_text());need(micro['passed'] and micro['qualification_complete'] and micro['exact_pairs']==84 and micro['backend_ACK'] and micro['physical_drain'],'qualified exact physical dense micro')
  need(sha(cmds[0][0])==old['compiler_sha256'],'same compiler')
  pins.update(old['source_sha256'])
  for o in prep['objects']:
   if o['reuse']:
    need(sha(o['object'])==o['object_sha256'],'reused object drift')
    for f,h in o['dependencies'].items():need(sha(f)==h,'reused dependency drift')
  need(sha(old['binary'])==old['binary_sha256'],'parent binary drift')
 files=[P/'build.py',P/'prepare.py',P/'preparation.json',P/'parent-pins.json',P/'policy_fixture.cpp',R/'experiments/own-xpu-runtime/ops/compile_turn.py']
 if a.mode=='native':files += [P/'evidence/cpu-proof.json',S/'operating/evidence/device-a/review.json',P.parent/'micro/operating/evidence/device-a/review.json']
 for f,h in {**json.loads((P/'parent-pins.json').read_text()),**prep['source_sha256']}.items():pins[str(Path(f).relative_to(R))]=h
 for f in files:pins[str(f.relative_to(R))]=sha(f)
 d.mkdir(parents=True);(P/'evidence').mkdir(exist_ok=True)
 for f in [P/'build.py',P/'policy_fixture.cpp',P/'preparation.json'] :shutil.copy2(f,d/f.name)
 (d/'commands.json').write_text(json.dumps(cmds,indent=2)+'\n')
 turnpath=R/'experiments/own-xpu-runtime/ops/compile_turn.py';sys.modules['build_engine']=sys.modules[__name__];spec=importlib.util.spec_from_file_location('iq3_engine_turn',turnpath);turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
 receipt=dict(schema='gsq.dense-packed-block.engine.build.v1',passed=False,mode=a.mode,commands=cmds,binary=str(binary),compiler_sha256=sha(cmds[0][0]),source_sha256=pins,native_binary_invoked=False)
 try:
  for i,cmd in enumerate(cmds):
   with turn.turn(),(d/f'command-{i}.log').open('x') as log:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,cwd=R,timeout=1200 if a.mode=='native' else 60)
   need(r.returncode==0,'command failure '+str(i))
  deps={}
  for f in d.glob('*.d'):
   for name in f.read_text().replace('\\\n',' ').split(':',1)[1].split():
    path=Path(name).resolve();key=str(path.relative_to(R));need(pins.get(key)==sha(path),'unbound dependency '+key);deps[key]=sha(path)
  receipt.update(dependencies=deps,binary_sha256=sha(binary))
  if a.mode=='cpu':
   receipt['proof']=json.loads((d/'command-1.log').read_text());need(receipt['proof']['passed'],'CPU policy failure');need(len(deps)==3,'fixture/generated policy/frozen selector dependencies')
  else:
   receipt['object_sha256']={o['object']:o['object_sha256'] for o in prep['objects'] if o['reuse']};receipt['object_sha256'][str(d/'entry.o')]=sha(d/'entry.o');receipt['reused_object_provenance']=prep['objects'];receipt['objects_reused']=39
   symbols=subprocess.check_output(['/usr/bin/nm','-C','--defined-only',str(binary)],text=True,timeout=60);(d/'symbols.log').write_text(symbols);need('packet26_model_entry' in symbols and 'mtp36::DraftRuntime' in symbols,'Engine symbols')
   compiler=Path('/opt/intel/oneapi/compiler/2026.0/bin/compiler');bundler=str(compiler/'clang-offload-bundler');obj=d/'entry.o'
   targets=subprocess.check_output([bundler,'-type=o','-list','-input='+str(obj)],text=True,timeout=60).splitlines();targets=[x for x in targets if x.startswith('sycl-spir64')];need(len(targets)==1,'one device image')
   bc=d/'entry-device.bc';subprocess.run([bundler,'-type=o','-unbundle','-targets='+targets[0],'-input='+str(obj),'-output='+str(bc)],check=True,timeout=120);subprocess.run([str(compiler/'sycl-post-link'),'-symbols','-split=source','-o',str(d/'kernel.table'),str(bc)],check=True,timeout=120)
   entries='\n'.join(f.read_text() for f in d.glob('kernel*.sym'));(d/'kernel-entries.log').write_text(entries)
   need('BlockKernel' in entries,'preserved IQ3 candidate device entry')
   for t in (12,13,23):need('DenseBlockKernelILj'+str(t)+'E' in entries,'new dense block device entry')
   for t in (12,13,18,23,42):need('PackedKernelILj'+str(t)+'E' in entries,'preserved generic format entry')
   receipt['offline']={'entry_device_sha256':sha(bc),'kernel_entries_sha256':sha(d/'kernel-entries.log'),'symbols_sha256':sha(d/'symbols.log')}
   receipt['native_qualification_complete']=False
   receipt['arithmetic_kernel_reused_unchanged']=True
  admission()
  for f,h in pins.items():need(sha(R/f)==h,'post source drift '+f)
  if a.mode=='native':
   for f,h in receipt['object_sha256'].items():need(sha(f)==h,'post object drift')
  need(sha(cmds[0][0])==receipt['compiler_sha256'],'compiler changed');need(sum(f.stat().st_size for f in d.rglob('*') if f.is_file())<(16 if a.mode=='cpu' else 250)*1024**2,'retained build budget')
  receipt['passed']=True
  with dest.open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n')
 except BaseException as e:receipt['error']=repr(e);raise
 finally:(d/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(dict(passed=True,mode=a.mode,receipt_sha256=sha(dest))))
if __name__=='__main__':main()

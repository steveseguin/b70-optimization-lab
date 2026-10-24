#!/usr/bin/env python3
"""Root-operated 21-TU compile/link, USB output and scratch; never invoke binary."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,sys,time
P=Path(__file__).resolve().parent; R=P.parents[3]
USB=Path('/mnt/usb-models'); OUT=USB/'own-xpu-runtime-builds/gsq-recurrent-f32-native-a'
ROOT_FLOOR=27_000_000_000+(64<<20); USB_FLOOR=2<<30
OUTPUT_CAP=256<<20; TEMP_CAP=512<<20
MATERIALIZATION_SHA='36d06637ebfafc307f05f90937d12085c438ef7953d2704dd77a7aea6797e653'
CPU_SHA='c4b684dd0c39af0fae991adc7f028c1d459cd7b1f1522c4544c2b3e5dc6a044c'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(b,s):
 if not b:raise RuntimeError(s)
def total(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file()) if p.exists() else 0
def limits():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement')
 need(all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')),'thread limit')
 resource.setrlimit(resource.RLIMIT_AS,(4<<30,4<<30));resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_FSIZE,(OUTPUT_CAP,OUTPUT_CAP))
 need(shutil.disk_usage(R).free>=ROOT_FLOOR,'unchanged root floor plus metadata reserve')
 need(USB.stat().st_dev==2050 and not USB.is_symlink(),'fixed admitted USB filesystem')
 need(shutil.disk_usage(USB).free>=USB_FLOOR+OUTPUT_CAP+TEMP_CAP,'USB floor plus output/temp reservations')
 if OUT.exists():
  need(total(OUT/'tmp')<=TEMP_CAP,'temporary quota');need(total(OUT)-total(OUT/'tmp')<=OUTPUT_CAP,'output quota')
def admission():
 m=P/'evidence/materialization.json';need(sha(m)==MATERIALIZATION_SHA,'materialization changed');r=json.loads(m.read_text())
 need(r['rebuild_count']==21 and r['reuse_count']==19 and not r['physical_include_escapes'],'closure geometry')
 c=P/'evidence/cpu-proof.json';need(sha(c)==CPU_SHA and json.loads(c.read_text())['passed'],'actual CPU proof')
 pins={**r['parent_sources'],**{str(R/f):h for f,h in r['generated_sha256'].items()},str(P/'recurrent_policy.hpp'):r['policy_sha256']}
 for f,h in pins.items():need(sha(f)==h,'source drift '+f)
 for o in r['objects_reused']:
  need(sha(o['object'])==o['object_sha256'],'reused object drift')
  for f,h in o['dependencies'].items():need(pins.get(f)==h and sha(f)==h,'reused source drift '+f)
 for f in (Path(__file__),m,c,P/'evidence/cpu-bootstrap-provenance.json',P/'memory-ledger.json',R/'experiments/own-xpu-runtime/ops/compile_turn.py'):pins[str(f)]=sha(f)
 return r,pins
def commands(r):
 old=str(P/'build/native-preview');return [[x.replace(old,str(OUT)) for x in cmd] for cmd in r['commands']]
def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--build',action='store_true');a=ap.parse_args()
 r,pins=admission();cmds=commands(r);binary=OUT/'gsq-recurrent-f32';compiler=cmds[0][0]
 plan={'commands':cmds,'cwd':str(R),'output':str(OUT),'TMPDIR':str(OUT/'tmp'),'root_floor_bytes':ROOT_FLOOR,'usb_floor_bytes':USB_FLOOR,'output_cap_bytes':OUTPUT_CAP,'temporary_cap_bytes':TEMP_CAP,'rebuild':21,'reuse':19,'native_invoked':False,'resource_note':'New USB reservations; no old 250MiB root reservation is waived','source_sha256':pins}
 if a.plan:print(json.dumps(plan,indent=2));return
 limits();need(not OUT.exists(),'fresh attempt required; no automatic retry');need(not (P/'evidence/native-build.json').exists(),'no receipt overwrite')
 OUT.mkdir(parents=True);(OUT/'tmp').mkdir();env=dict(os.environ,TMPDIR=str(OUT/'tmp'),TMP=str(OUT/'tmp'),TEMP=str(OUT/'tmp'))
 (OUT/'commands.json').write_text(json.dumps(plan,indent=2)+'\n')
 turnpath=R/'experiments/own-xpu-runtime/ops/compile_turn.py';sys.modules['build_engine']=sys.modules[__name__];spec=importlib.util.spec_from_file_location('rf32_compile_turn',turnpath);turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
 receipt={**plan,'passed':False,'compiler_sha256':sha(compiler),'binary':str(binary),'materialization_sha256':MATERIALIZATION_SHA,'cpu_proof_sha256':CPU_SHA,'native_qualification_complete':False,'parent_binary_sha256':r['parent_binary_sha256']}
 def command(cmd,label,timeout):
  with (OUT/(label+'.log')).open('x') as log:
   result=subprocess.run(cmd,cwd=R,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
  need(result.returncode==0,'command failed '+label)
 try:
  with turn.turn():
   for i,cmd in enumerate(cmds):
    limits();command(cmd,'command-'+str(i),1200)
   deps={}
   for f in OUT.glob('*.d'):
    for name in shlex.split(f.read_text().replace('\\\n',' ').split(':',1)[1]):
     n=str(Path(name).resolve());need(pins.get(n)==sha(n),'unbound new dependency '+n);deps[n]=pins[n]
   command(['/usr/bin/nm','-C','--defined-only',str(binary)],'symbols',120)
   symbols=(OUT/'symbols.log').read_text();need('packet26_model_entry' in symbols and 'mtp36::DraftRuntime' in symbols,'Engine/MTP linkage')
   command(['/usr/bin/objdump','-d','--disassemble=main',str(binary)],'public-main',60)
   toolkit=Path('/opt/intel/oneapi/compiler/2026.0/bin/compiler');bundler=str(toolkit/'clang-offload-bundler')
   for name in ('entry','11'):
    command([bundler,'-type=o','-list','-input='+str(OUT/(name+'.o'))],name+'-targets',60)
    targets=[s for s in (OUT/(name+'-targets.log')).read_text().splitlines() if s.startswith('sycl-spir64')];need(len(targets)==1,'one device target')
    bc=OUT/(name+'-device.bc');command([bundler,'-type=o','-unbundle','-targets='+targets[0],'-input='+str(OUT/(name+'.o')),'-output='+str(bc)],name+'-unbundle',120)
    command([str(toolkit/'sycl-post-link'),'-symbols','-split=source','-o',str(OUT/(name+'-kernels.table')),str(bc)],name+'-post-link',120)
   entries='\n'.join(f.read_text() for f in OUT.glob('*-kernels*.sym'));need('DenseBlockKernel' in entries and 'PackedKernel' in entries,'packed arithmetic entries')
   need('Kernel' in '\n'.join(f.read_text() for f in OUT.glob('11-kernels*.sym')),'rebuilt recurrent device image')
   for f,h in pins.items():need(sha(f)==h,'postbuild source drift '+f)
   need(sha(compiler)==receipt['compiler_sha256'],'compiler drift')
   objects={str(OUT/(str(t['index'])+'.o')):sha(OUT/(str(t['index'])+'.o')) for t in r['translation_units_rebuild']}
   for o in r['objects_reused']:need(sha(o['object'])==o['object_sha256'],'postbuild reuse drift');objects[o['object']]=o['object_sha256']
   limits();receipt.update(passed=True,dependencies=deps,objects=objects,binary_sha256=sha(binary),objects_rebuilt=21,objects_reused=19,artifacts={str(f):sha(f) for f in OUT.iterdir() if f.is_file()},retained_output_bytes=total(OUT)-total(OUT/'tmp'),temporary_bytes=total(OUT/'tmp'))
 except BaseException as e:receipt['error']=repr(e);raise
 finally:(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 with (P/'evidence/native-build.json').open('x') as f:f.write(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({'passed':True,'receipt_sha256':sha(P/'evidence/native-build.json'),'binary_sha256':receipt['binary_sha256']}))
if __name__=='__main__':main()

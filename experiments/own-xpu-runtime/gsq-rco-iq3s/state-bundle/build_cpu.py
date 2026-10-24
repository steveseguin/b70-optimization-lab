#!/usr/bin/env python3
"""Small GNU writer/reader tests; optional root-authorized few-KiB NTFS pilot."""
import argparse,hashlib,importlib.util,json,os,resource,shutil,subprocess,sys,time
from pathlib import Path
import prepare as M
P=M.P;R=M.R
def sha(p):return M.sha(p)
def require(v,m):return M.require(v,m)
def limits():
 require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement')
 require(all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')),'two threads')
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0));require(shutil.disk_usage(R).free>=27000000000+20*1024**2,'root floor+20MiB')
def sources():
 M.authority();prep=json.loads((P/'preparation.json').read_text())
 for f,h in prep['source_sha256'].items():require(sha(f)==h,'materialized source drift')
 return {str(f):sha(f) for f in [P/n for n in ('bundle.hpp','fixture.cpp','reader.py','test_bundle.py','build_cpu.py','preparation.json','parent-pins.json','generated/adapter.py')]}
def fs_pilot():
 import reader
 proof=json.loads((P/'evidence/cpu-proof.json').read_text());require(proof['passed'] and proof['source_sha256']==sources(),'current CPU proof');require(sha(proof['binary'])==proof['binary_sha256'],'CPU binary')
 path=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-state-bundle-fs-pilot-c');parent=path.parent;require(parent.resolve()==parent and parent.stat().st_dev==2050 and not os.path.lexists(path),'fixed fresh USB pilot')
 path.mkdir(mode=0o700);out={'passed':False,'scope':'Tiny actual NTFS CPU writer/reader only; no model or Device','path':str(path),'filesystem_device':2050,'cpu_proof_sha256':sha(P/'evidence/cpu-proof.json'),'source_sha256':sources()}
 try:
  for mode in ('tiny-create','tiny-repeat'):
   r=subprocess.run([proof['binary'],mode,str(path/'state')],capture_output=True,text=True,timeout=10);(path/(mode+'.log')).write_text(r.stdout+r.stderr);require(r.returncode==0,'USB writer '+mode)
   current=reader.read_state(path/'state');snapshot={f.name:[f.stat().st_ino,f.stat().st_size,f.stat().st_mtime_ns,sha(f)] for f in (path/'state').iterdir()}
   if mode=='tiny-create':before=snapshot;logical=current
   else:require(before==snapshot and logical==current,'repeated USB dump changed')
  require((path/'state/state.bundle').stat().st_size==261,'tiny payload bound');out.update(passed=True,payload_bytes=261,logical_map=logical,files=snapshot,exclusive_link_publication_and_directory_fsync=True)
 except BaseException as e:out['error']=repr(e);raise
 finally:
  (path/'result.json').write_text(json.dumps(out,indent=2)+'\n');(P/'evidence/fs-pilot.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({'passed':True,'receipt_sha256':sha(P/'evidence/fs-pilot.json')}))
def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--build',action='store_true');g.add_argument('--fs-pilot',action='store_true');a=ap.parse_args();limits()
 if a.fs_pilot:fs_pilot();return
 pins=sources();d=P/'build'/('cpu-'+str(time.time_ns()));d.mkdir(parents=True);binary=d/'fixture';cmd=['/usr/bin/g++','-std=gnu++20','-O2','-g0','-fno-fast-math','-ffp-contract=off','-MMD','-MF',str(d/'fixture.d'),str(P/'fixture.cpp'),'-lcrypto','-o',str(binary)]
 for f in pins:shutil.copy2(f,d/Path(f).name)
 turnpath=R/'experiments/own-xpu-runtime/ops/compile_turn.py';sys.modules['build_engine']=sys.modules[__name__];spec=importlib.util.spec_from_file_location('bundle_compile_turn',turnpath);turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
 out={'passed':False,'source_sha256':pins,'commands':[cmd,[sys.executable,'-B','-m','unittest','test_bundle','-v']],'compiler_sha256':sha(cmd[0]),'binary':str(binary),'compile_turn_sha256':sha(turnpath),'scope':'Actual native-writer header in GNU CPU fixture plus independent reader and adapter/synthetic RPC tests; no Engine/Device/model'}
 try:
  with turn.turn(),(d/'compile.log').open('x') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=90)
  require(r.returncode==0,'CPU compile')
  deps={}
  for n in (d/'fixture.d').read_text().replace('\\\n',' ').split(':',1)[1].split():require(str(Path(n).resolve()) in pins,'unbound CPU dependency');deps[str(Path(n).resolve())]=sha(n)
  out['dependencies']=deps;out['binary_sha256']=sha(binary);env=dict(os.environ,BUNDLE_TEST_BINARY=str(binary))
  with (d/'tests.log').open('x') as log:r=subprocess.run(out['commands'][1],cwd=P,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60)
  require(r.returncode==0,'CPU tests');require(sources()==pins and sha(cmd[0])==out['compiler_sha256'],'source/compiler drift');out.update(passed=True,tests=9,test_log=str(d/'tests.log'),test_log_sha256=sha(d/'tests.log'))
  (P/'evidence').mkdir(exist_ok=True)
  with (P/'evidence/cpu-proof.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
 except BaseException as e:out['error']=repr(e);raise
 finally:(d/'receipt.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({'passed':True,'receipt_sha256':sha(P/'evidence/cpu-proof.json'),'attempt':str(d)}))
if __name__=='__main__':main()

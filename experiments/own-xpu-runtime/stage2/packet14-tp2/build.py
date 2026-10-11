#!/usr/bin/env python3
"""CPU only: compile native target without executing it; test host targets."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BUILD=HERE/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--keep-build',action='store_true');a=p.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 assert not BUILD.is_symlink()
 if any(BUILD.rglob('window.json')) or (BUILD/'FAULT.json').exists():raise SystemExit('preserve coordinator evidence; no cleanup')
 r=dict(schema='own-runtime.iq3.packet14.build.v1',passed=False,device_executed=False,nice=19,OMP_NUM_THREADS='2',max_build_jobs=2,commands=[])
 def run(cmd):
  proc=subprocess.run(list(map(str,cmd)),text=True,capture_output=True,cwd=ROOT)
  r['commands'].append(dict(argv=list(map(str,cmd)),returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
  if proc.returncode:raise RuntimeError(proc.stdout+proc.stderr)
  print(proc.stdout,flush=True)
 try:
  owner=BUILD/'owner';owner.mkdir(parents=True,exist_ok=True)
  for f in (HERE.parents[1]/'stage1/packet3-prep/src').glob('*'):
   if f.suffix in ('.hpp','.cpp') and f.name!='owner.hpp':
    dst=owner/f.name
    if not dst.exists() or dst.read_bytes()!=f.read_bytes():shutil.copyfile(f,dst)
  f=owner/'owner.hpp';s=(HERE.parents[1]/'stage1/packet3-prep/src/owner.hpp').read_text();anchor='  EventTiming timing(Event);'
  assert s.count(anchor)==1
  s=s.replace(anchor,'  void peer_from(Device&, Allocation, std::size_t, Allocation, std::size_t, std::size_t);\n'+anchor)
  if not f.exists() or f.read_text()!=s:f.write_text(s)
  control=(HERE.parent/'packet13-integrate/main.cpp').read_text()
  control=control.replace('a.mini ? Geometry::tiny() : flash::geometry_from_directory(w.directory)', 'a.mini ? []{auto g=Geometry::tiny();g.kvh=2;g.kh=2;g.vh=4;return g;}() : flash::geometry_from_directory(w.directory)')
  control=control.replace('#include "performance.hpp"','#include "../../packet13-integrate/performance.hpp"').replace('#include "../packet2/', '#include "../../packet2/').replace('#include "../packet3/', '#include "../../packet3/')
  control=control.replace('s.packed_heads = !a.mini;', 's.packed_heads = true;')
  target=BUILD/'kv2_control.cpp'
  if not target.exists() or target.read_text()!=control:target.write_text(control)
  for mode,compiler in [('host','/usr/bin/g++'),('device','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
   run(['cmake','-S',HERE,'-B',BUILD/mode,f'-DCMAKE_CXX_COMPILER={compiler}',f'-DOWN_RT_HOST_ONLY={"ON" if mode=="host" else "OFF"}'])
   run(['cmake','--build',BUILD/mode,'-j2'])
  run([BUILD/'host/tp-tests']);run([BUILD/'host/authority-tests']);run([BUILD/'host/owner-retirement-tests'])
  if (BUILD/'tests').exists():shutil.rmtree(BUILD/'tests')
  run([sys.executable,'-B',HERE/'test.py','--binary',BUILD/'host/own-rt-iq3','--control',BUILD/'host/p13-control'])
  census=json.loads((ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json').read_text())['tensors']
  directory=BUILD/'directory.tsv'
  directory.write_text('\n'.join(f"{t['name']} {t['type']} {','.join(map(str,t['dimensions']))} {t['bytes']} {t['component']}" for t in census)+'\n')
  plan=subprocess.check_output([str(BUILD/'host/placement-tests'),str(directory)],text=True)
  (HERE/'placement.json').write_text(json.dumps(json.loads(plan),indent=2)+'\n')
  out=BUILD/'tests/real-metadata'
  run([BUILD/'host/own-rt-iq3','--record','--census',directory,'--cards','2','--card','2','--memory','tp2-streaming','--output',out])
  actual=json.loads((out/'plan.json').read_text())['tensor_owners']
  assert len(actual)==len(census)==1224
  assert {t['name']:t['source_bytes'] for t in actual}=={t['name']:t['bytes'] for t in census}
  for t in actual:
   if t['placement'] in ('expert-id','output-rows'):
    left,right=t['ranges'];assert left['begin']==0 and left['end']==right['begin'] and right['end']>right['begin']
   elif t['placement']=='replicated':assert t['ranges'][0]['stored_bytes']==t['ranges'][1]['stored_bytes']
   else:assert t['placement']=='host-lookup' and not t['ranges']
  r['actual_cli_tensor_coverage']=len(actual)
  run([sys.executable,'-B',HERE/'test_window.py'])
  r['artifacts_sha256']={f'{mode}/own-rt-iq3':sha(BUILD/mode/'own-rt-iq3') for mode in ['host','device']}
  r['passed']=True
 finally:
  folders=[HERE,*[HERE.parent/n for n in ['packet2','packet3','packet4','packet6-kopt','packet7-kopt2','packet8-kopt3','packet9-kopt4','packet10-kopt5','packet13-integrate']],HERE.parents[1]/'stage1/packet3-prep/src']
  files=set()
  for folder in folders:
   files.update(f for f in folder.rglob('*') if f.is_file() and 'build' not in f.relative_to(folder).parts and f.suffix in ('.cpp','.hpp','.inc','.py'))
  files.add(HERE/'CMakeLists.txt')
  r['sources']={str(f.relative_to(ROOT)):sha(f) for f in sorted(files)}
  if not a.keep_build and BUILD.exists():shutil.rmtree(BUILD)
  r['build_directory_removed']=not BUILD.exists()
  (HERE/'build-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Explicit compile-only helper. Default prints a plan; never executes a model or a device probe."""
import argparse,hashlib,importlib.util,json,os,resource,shlex,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];A=P.parent/'packet181-session-swap-v3';ONE=A/'one-card'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=27_000_000_000
 assert os.environ.get('OMP_NUM_THREADS')=='2'
def load(p):return json.loads(p.read_text())
def dependency_paths(path):
 text=Path(path).read_text().replace('\\\n',' ')
 assert ':' in text,'invalid compiler dependency file'
 result=set()
 for name in shlex.split(text.split(':',1)[1]):
  p=Path(name);p=p if p.is_absolute() else ROOT/p
  if p.is_relative_to(ROOT):result.add(p.resolve(strict=True))
 return result
def expected_dependencies(target,pins):
 if target=='protocol':return {(P/'tests/protocol_probe.cpp').resolve(),(P/'native/request_front.hpp').resolve()}
 parent_native=ONE/'native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'
 paths={(ROOT/p).resolve(strict=True) for p in pins['compiler_parent_dependencies'][target]}
 for leaf in ('main.cpp','entry-main.cpp','checkpoint.hpp'):
  paths.remove((parent_native/leaf).resolve(strict=True));paths.add((P/'build/native'/leaf).resolve(strict=True))
 paths.add((P/'build/native/request_front.hpp').resolve(strict=True))
 return paths
def verify_dependencies(target,path,pins):
 actual=dependency_paths(path);expected=expected_dependencies(target,pins)
 assert actual==expected,dict(target=target,missing=sorted(map(str,expected-actual)),unexpected=sorted(map(str,actual-expected)))
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(actual)}
def plan(target):
 if target=='protocol':return dict(target=target,commands=[['/usr/bin/g++','-std=c++20','-O2','-Wall','-Wextra','-Werror=return-type','-MMD','-MF',str(P/'build/protocol/protocol-probe.d'),str(P/'tests/protocol_probe.cpp'),'-o',str(P/'build/protocol/protocol-probe')]],objects={},binary=str(P/'build/protocol/protocol-probe'),depfile=str(P/'build/protocol/protocol-probe.d'))
 if target=='device':
  recipe=load(ONE/'lineage/packet181-build.json');pins=load(ONE/'lineage/build-inputs.json')['objects']
  objects={x:pins[str(Path(x).relative_to(ONE))]['sha256'] for x in recipe['link'] if x.endswith('.o') and not x.endswith('/entry-main.o')}
  assert len(objects)==41
 else:
  assert target=='host';recipe=load(ONE/'build/checkpoint-probe/compiled-inputs.json');objects=recipe['ancestor_objects_sha256'];assert len(objects)==33
 compile=list(recipe['compile']);link=list(recipe['link']);out=P/'build'/target;entry=out/'entry-main.o'
 compile[compile.index('-c')+1]=str(P/'build/native/entry-main.cpp');compile[compile.index('-o')+1]=str(entry)
 if '-MF' in compile:compile[compile.index('-MF')+1]=str(out/'entry-main.d')
 replaced=0
 for index,arg in enumerate(link):
  if arg.endswith('/entry-main.o'):link[index]=str(entry);replaced+=1
 assert replaced==1
 binary=out/'own-rt-iq3';link[link.index('-o')+1]=str(binary)
 return dict(target=target,commands=[compile,link],objects=objects,binary=str(binary),depfile=str(out/'entry-main.d'))
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--target',choices=('protocol','host','device','all'),default='all');ap.add_argument('--compile-only',action='store_true');a=ap.parse_args();limits()
 targets=('protocol','host','device') if a.target=='all' else (a.target,)
 pins=load(P/'parent-pins.json')
 for path,digest in pins['sources'].items():assert sha(ROOT/path)==digest,path
 plans=[plan(t) for t in targets]
 if not a.compile_only:print(json.dumps(dict(executed=False,plans=plans),indent=2));return
 # A separate, explicit coordinator authorization is required before invoking this option.
 overlay=load(P/'evidence/source-overlay.json')
 assert overlay['parent_pins_sha256']==sha(P/'parent-pins.json')
 for path,digest in overlay['outputs'].items():assert sha(P/path)==digest,path
 assert sha(P/'native/request_front.hpp')==overlay['outputs']['build/native/request_front.hpp']
 spec=importlib.util.spec_from_file_location('p197_compile_turn',ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py');turn=importlib.util.module_from_spec(spec);spec.loader.exec_module(turn)
 sys.modules['build_engine']=sys.modules[__name__]
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));records=[]
 for item in plans:
  for path,digest in item['objects'].items():assert sha(path)==digest,path
  out=P/'build'/item['target'];out.mkdir(parents=True,exist_ok=True)
  for i,command in enumerate(item['commands']):
   limits()
   with turn.turn(),(out/f'compile-{i}.log').open('w') as log:
    start=time.monotonic();cp=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
   assert cp.returncode==0,(item['target'],i,cp.returncode)
   if i==0:
    item['repository_dependencies']=verify_dependencies(item['target'],item['depfile'],pins)
    for path,digest in pins['sources'].items():assert sha(ROOT/path)==digest,path
    for path,digest in overlay['outputs'].items():assert sha(P/path)==digest,path
   records.append(dict(target=item['target'],command=command,seconds=time.monotonic()-start))
  for path,digest in item['objects'].items():assert sha(path)==digest,path
  item['binary_sha256']=sha(item['binary'])
  assert verify_dependencies(item['target'],item['depfile'],pins)==item['repository_dependencies']
 row=dict(passed=True,device_executed=False,native_executed=False,compile_only=True,source_overlay_sha256=sha(P/'evidence/source-overlay.json'),parent_pins_sha256=sha(P/'parent-pins.json'),plans=plans,commands=records)
 (P/'evidence/build-compile-only.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(dict(passed=True,targets=list(targets),device_executed=False)))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Sequential CPU preparation. NEVER runs a device executable."""
import argparse,hashlib,json,os,subprocess,resource,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def run(cmd,log):
 with (B/log).open('w') as f:r=subprocess.run(['nice','-n','19','ionice','-c','3',*map(str,cmd)],stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(str(B/log))
 print(log,'PASS',flush=True)
def build(mode):
 receipt_path=P/'build-receipt.json'
 invalid=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
 invalid['passed']=False
 receipt_path.write_text(json.dumps(invalid,indent=2)+'\n')
 def inputs():
  sys.path.insert(0,str(P.parent/'packet29-merged'))
  from math_gate import closure
  files=set(closure())|{x for x in P.iterdir() if x.suffix in ('.cpp','.hpp') or x.name=='CMakeLists.txt'}
  return {str(x):sha(x) for x in files}
 initial=inputs()
 if mode=='device':
  from mirror import make
  make()
 host=mode!='device';compiler='/usr/bin/g++' if mode in ('host','asan') else IC
 run(['cmake','-S',P,'-B',B/mode,'-DCMAKE_CXX_COMPILER='+compiler,'-DHOST_ONLY='+('ON' if host else 'OFF'),'-DSANITIZE='+('ON' if mode=='asan' else 'OFF')],f'configure-{mode}.log')
 run(['cmake','--build',B/mode,'--parallel','1'],f'build-{mode}.log')
 assert inputs()==initial,'source changed during build; discard affected objects and rebuild'
 receipt=json.loads((P/'build-receipt.json').read_text()) if (P/'build-receipt.json').exists() else {}
 receipt.update(schema='packet34.build.v1',device_executed=False,qualified=False,max_compile_jobs=1,numeric_threads=2)
 receipt.setdefault('binaries',{})
 for name in ('replay-bench','jit-smoke'):
  path=B/mode/name
  if path.exists():receipt['binaries'][f'{mode}/{name}']=sha(path)
 flags=['-fno-fast-math','-ffp-contract=off']
 if not host:flags+=['-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl']
 cc=json.loads((B/mode/'compile_commands.json').read_text()); links=list((B/mode).rglob('link.txt'))
 assert cc and all(all(f in c['command'].split() for f in flags) for c in cc)
 assert links and all(all(f in path.read_text().split() for f in flags) for path in links)
 receipt.setdefault('precision',{})[mode]={'flags':flags,'compile_commands':len(cc),'link_commands':len(links),'asserted_compile_and_link':True}
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['host','icpx-host','asan','device']);a=p.parse_args()
 B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 # Compilers bounded in address space (ASan runtime is run separately).
 resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3))
 build(a.mode)
if __name__=='__main__':main()

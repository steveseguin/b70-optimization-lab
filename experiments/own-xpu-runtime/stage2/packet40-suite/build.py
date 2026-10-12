#!/usr/bin/env python3
"""CPU gates and native compilation only. No device entry is ever executed."""
import argparse,hashlib,json,os,resource,struct,subprocess,time,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
PY='/home/steve/.venvs/vllm-xpu/bin/python';IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,log,bounded=True):
 with (B/log).open('w') as out:
  def limit():
   old=resource.getrlimit(resource.RLIMIT_AS)[1];cap=min(8*1024**3,old) if old!=resource.RLIM_INFINITY else 8*1024**3
   resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
  r=subprocess.run(list(map(str,args)),stdout=out,stderr=subprocess.STDOUT,preexec_fn=limit if bounded else None)
 if r.returncode:raise RuntimeError(str(B/log))
 print(log,'PASS',flush=True)
def configure(mode,jobs=1):
 from storage import admit
 admit(350_000_000)
 host=mode!='device';compiler=IC if mode in ('device','icpx-host') else '/usr/bin/g++'
 cmd=['cmake','-S',P,'-B',B/mode,'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+('ON' if host else 'OFF'),'-DOWN_RT_SANITIZE='+('ON' if mode=='asan' else 'OFF')]
 run(cmd,'configure-'+mode+'.log');run(['cmake','--build',B/mode,'-j'+str(jobs)],'build-'+mode+'.log')
def sources():
 from math_gate import closure
 paths=set(closure())|set((P/'prototype').rglob('*.py'))|{x for x in P.iterdir() if x.suffix in ('.cpp','.hpp','.py') or x.name in ('CMakeLists.txt','rope.bf16','dispatch-default.json','dispatch-all-new.json','dispatch-p33.json','dispatch-p38.json','dispatch-incumbent.json','k2-class-registry.json','kernel-registry.json','dispatch-merged-example.json')}
 return {str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)}
def prepare():
 if not (P/"mtp-manifest.tsv").exists():run([PY,"-B",P/"prepare_mtp.py"],"prepare-mtp.log")
 if not (B/'input').exists():run([PY,'-B',P/'prepare.py','--output',B/'input'],'prepare.log')
 if not (B/'fusion-fixtures').exists():run([PY,'-B',P/'prototype/fixtures.py','--output',B/'fusion-fixtures'],'prepare-fixtures.log')
 values=struct.unpack('<262144H',(P/'rope.bf16').read_bytes())
 (B/'fusion-rope.hpp').write_text('#pragma once\nnamespace rope_constants { inline constexpr int positions=4096; inline constexpr uint16_t table[]={'+','.join(map(str,values))+'};}\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','gnu-host','icpx-host','asan','device','seal']);p.add_argument('--jobs',type=int,choices=(1,2),default=1);a=p.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 if a.stage=='prepare':prepare()
 elif a.stage=='seal':
  from seal import main as seal_main
  seal_main()
 else:configure(a.stage,a.jobs)
if __name__=='__main__':main()

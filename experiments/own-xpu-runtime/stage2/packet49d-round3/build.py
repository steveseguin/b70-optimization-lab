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
 from storage import cpu_build_admit
 cpu_build_admit(350_000_000)
 host=mode!='device';compiler=IC if mode in ('device','icpx-host') else '/usr/bin/g++'
 cmd=['cmake','-S',P,'-B',B/mode,'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+('ON' if host else 'OFF'),'-DOWN_RT_SANITIZE='+('ON' if mode=='asan' else 'OFF')]
 run(cmd,'configure-'+mode+'.log')
 targets=['--target','own-rt-iq3','p49-qsa-fixtures','p49b-expert-fixtures','p49c-fixtures','p49d-fixtures'] if mode=='asan' else []
 run(['cmake','--build',B/mode,'-j'+str(jobs),*targets],'build-'+mode+'.log')
 record_mode_build(mode)
def compiled_sources():
 from math_gate import closure
 paths=set(closure())|{P/n for n in ('CMakeLists.txt','kernel_gate.py','kernel_overlay.py','submission_overlay.py','validation_mirror.py','math_gate.py','kernel_guard.hpp','rope.bf16')}
 return {str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)}
def record_mode_build(mode):
 directory=B/mode
 targets=('p49d-fixtures','p49c-fixtures','p49b-expert-fixtures','p49-qsa-fixtures','p39-merged-fixtures','own-rt-iq3','nongemv-fixtures','k2-fixtures','p33-linked-fixtures','jit-smoke','authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests','prepared-invalidation-tests','libmath_bridge.so')
 artifacts={str(f.relative_to(B)):sha(f) for f in directory.iterdir() if f.is_file() and f.name in targets}
 commands=directory/'compile_commands.json';links={str(f.relative_to(B)):sha(f) for f in sorted(directory.rglob('link.txt'))}
 if not artifacts or not links or not commands.is_file():raise RuntimeError('incomplete build cannot record provenance: '+mode)
 receipt=dict(schema='packet44.mode-build.v1',passed=True,device_executed=False,mode=mode,
  actual_artifact_targets=sorted(Path(name).name for name in artifacts),
  requested_targets=['own-rt-iq3','p49-qsa-fixtures','p49b-expert-fixtures','p49c-fixtures','p49d-fixtures'] if mode=='asan' else ['all'],
  compiled_sources_sha256=compiled_sources(),artifacts_sha256=artifacts,
  checked_mirror_sha256={str(f.relative_to(B)):sha(f) for f in sorted((B/'checked').rglob('*')) if f.is_file()},
  compile_commands_sha256=sha(commands),link_files_sha256=links)
 (P/('build-'+mode+'-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
def sources():
 from math_gate import closure
 paths=set(closure())|set((P/'prototype').rglob('*.py'))|{x for x in P.iterdir() if x.suffix in ('.cpp','.hpp','.py') or x.name in ('CMakeLists.txt','rope.bf16','dispatch-default.json','dispatch-all-new.json','dispatch-p33.json','dispatch-p38.json','dispatch-incumbent.json','k2-class-registry.json','kernel-registry.json','dispatch-merged-example.json','dispatch-p45.json')}
 return {str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)}
def prepare():
 # Packet49 deliberately reuses admitted metadata/fixtures read-only.  Never
 # run the historical weight-scanning preparer or write through these links.
 for path in (P/'mtp-manifest.tsv',B/'input/input.json',B/'input/plan.tsv',B/'fusion-fixtures',B/'fusion-rope.hpp',P/'rope.bf16'):
  if not path.exists():raise RuntimeError('restore admitted packet45 input before building: '+str(path))
 print('admitted metadata and fixture inputs present; no weight payload read',flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','gnu-host','icpx-host','asan','device']);p.add_argument('--jobs',type=int,choices=(1,),default=1);a=p.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 if a.stage=='prepare':prepare()
 else:configure(a.stage,a.jobs)
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Packet59b CPU-only serial compiler. Never executes a device binary."""
import argparse,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def guard():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
 assert shutil.disk_usage(P).free>=1_000_000_000
 assert sum(x.stat().st_size for x in B.rglob('*') if x.is_file() and not x.is_symlink())<600_000_000

def run(cmd,name):
 guard();start=time.monotonic()
 logfile=B/(name+'.log')
 if logfile.exists():
  history=B/'log-history';history.mkdir(exist_ok=True);logfile.rename(history/(str(time.time_ns())+'-'+name+'.log'))
 with logfile.open('w') as f:
  subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,check=True)
 print(name,'passed',round(time.monotonic()-start,2),flush=True)
 return list(map(str,cmd))
def sources():
 from math_gate import closure
 paths=set(closure())|{x for x in P.iterdir() if x.suffix in ('.py','.hpp','.cpp','.inc','.bf16') or x.name in ('CMakeLists.txt','selection.json','memory-plan.json','dispatch-speed6.json','parent-binding.json','mtp-manifest.tsv')}
 return {str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['gnu-host','device']);a=ap.parse_args();guard()
 compiler='/usr/bin/g++' if a.mode=='gnu-host' else '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
 commands=[]
 commands.append(run(['cmake','-S',P,'-B',B/a.mode,'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+('ON' if a.mode=='gnu-host' else 'OFF')],'configure-'+a.mode))
 targets=['own-rt-iq3','p59b-fixtures'] if a.mode=='gnu-host' else ['own-rt-iq3']
 commands.append(run(['cmake','--build',B/a.mode,'-j1','--target',*targets],'compile-'+a.mode))
 artifacts={str((B/a.mode/n).relative_to(P)):sha(B/a.mode/n) for n in targets}
 files=[B/a.mode/'compile_commands.json',*sorted((B/a.mode).rglob('link.txt'))]
 receipt=dict(schema='packet59b.compile.v1',passed=True,device_executed=False,mode=a.mode,commands=commands,sources=sources(),artifacts=artifacts,compiler=compiler,compiler_sha256=sha(Path(compiler)),command_files={str(x.relative_to(P)):sha(x) for x in files},checked_mirror_sha256={str(x.relative_to(P)):sha(x) for x in sorted((B/'checked').rglob('*')) if x.is_file()})
 (P/('build-'+a.mode+'-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n');guard()
if __name__=='__main__':main()

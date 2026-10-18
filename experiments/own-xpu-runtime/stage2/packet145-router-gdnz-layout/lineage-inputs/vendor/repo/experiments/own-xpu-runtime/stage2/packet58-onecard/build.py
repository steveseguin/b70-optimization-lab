#!/usr/bin/env python3
"""Serial low priority CPU builds only; never executes a device binary."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent; B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source_identity():
 from math_gate import closure
 paths=set(closure())|{P/n for n in ('CMakeLists.txt','build.py','kernel_gate.py','kernel_overlay.py','submission_overlay.py','math_gate.py','validation_mirror.py')}
 return {str(p.relative_to(P.parents[3])):sha(p) for p in sorted(paths)}
def main():
 a=argparse.ArgumentParser();a.add_argument('stage',choices=['prepare','gnu-host','device']);args=a.parse_args()
 if os.getpriority(os.PRIO_PROCESS,0)!=19:raise SystemExit('nice19 required')
 if not set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32)):raise SystemExit('CPU affinity outside admission')
 if (sum(x.stat().st_size for x in B.rglob('*') if x.is_file()) if B.exists() else 0) > 1500000000:raise SystemExit('build cap')
 B.mkdir(exist_ok=True)
 parent=P.parent/'packet56-draft-prefix/build'
 for name in ('input','fusion-fixtures','fusion-rope.hpp'):
  dest=B/name
  if not dest.exists():dest.symlink_to((parent/name).resolve())
 if args.stage=='prepare':return
 before=source_identity()
 mode=args.stage;dest=B/mode;env=os.environ.copy();env['OMP_NUM_THREADS']='2';env['PYTHONDONTWRITEBYTECODE']='1'
 compiler='/usr/bin/g++' if mode=='gnu-host' else '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
 cmds=[['cmake','-S',str(P),'-B',str(dest),'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+('ON' if mode=='gnu-host' else 'OFF')],['cmake','--build',str(dest),'--target','own-rt-iq3','-j1']]
 if (P/'p58_native_fixture.cpp').exists():cmds[-1].insert(-1,'p58-cache-fixtures')
 for i,cmd in enumerate(cmds):
  with (B/(mode+'-'+str(i)+'.log')).open('w') as f:
   subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 after=source_identity()
 if before!=after:raise SystemExit('source changed while compiler ran; rebuild required')
 actual_bytes=sum(x.stat().st_size for x in B.rglob('*') if x.is_file())
 if actual_bytes>1500000000:raise SystemExit('build exceeded1.5GB')
 binaries=[dest/n for n in ('own-rt-iq3','p58-cache-fixtures') if (dest/n).is_file()]
 (P/('build-'+mode+'-receipt.json')).write_text(json.dumps({'schema':'packet58.build.v1','device_executed':False,'passed':True,'sources_sha256':after,'build_bytes':actual_bytes,'commands':cmds,'binaries':{str(x.relative_to(P)):sha(x) for x in binaries},'built_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},indent=2)+'\n')
if __name__=='__main__':main()

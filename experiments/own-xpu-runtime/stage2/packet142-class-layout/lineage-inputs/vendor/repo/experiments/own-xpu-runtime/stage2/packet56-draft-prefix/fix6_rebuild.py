"""Rebuild only binaries linking the changed model entry; never execute them."""
import json,os,subprocess,time
from pathlib import Path
import build
from storage import admit,digest
P=Path(__file__).resolve().parent;E=P/'evidence/fix6'
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
 for mode in ('gnu-host','device'):
  admit(600_000_000);start=time.monotonic()
  compiler='/usr/bin/g++' if mode=='gnu-host' else build.IC
  targets=['own-rt-iq3','nongemv-fixtures','k2-fixtures','p33-linked-fixtures','p39-merged-fixtures' if mode=='gnu-host' else 'jit-smoke']
  commands=[['cmake','-S',str(P),'-B',str(P/'build'/mode),'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+('ON' if mode=='gnu-host' else 'OFF'),'-DOWN_RT_SANITIZE=OFF'],['cmake','--build',str(P/'build'/mode),'--target',*targets,'-j2']]
  with (E/('build-'+mode+'.log')).open('w') as log:
   for command in commands:
    r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    if r.returncode:raise RuntimeError('build failed '+mode)
  build.record_mode_build(mode)
  row=dict(passed=True,mode=mode,targets=targets,commands=commands,seconds=time.monotonic()-start,device_executed=False,receipt_sha256=digest(P/('build-'+mode+'-receipt.json')))
  (E/('build-'+mode+'.json')).write_text(json.dumps(row,indent=2)+'\n')
  print(json.dumps(row),flush=True)
if __name__=='__main__':main()

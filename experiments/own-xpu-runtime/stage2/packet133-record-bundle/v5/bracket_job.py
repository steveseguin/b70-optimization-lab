"""Packet133 lane A adapter for the byte-identical frozen packet130 v5 engine."""
import argparse,json,sys,os,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE.parent;ROOT=P.parents[3]
FROZEN=P.with_name('packet130-suffix-interleave')/'v5'
def main(argv=None):
 os.environ.clear();os.environ.update({'PATH': '/usr/bin:/bin', 'OMP_NUM_THREADS': '2', 'LD_LIBRARY_PATH': '/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'})
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--kind',choices=('smoke','bracket'),required=True)
 ap.add_argument('--lane',choices=('A',),required=True)
 ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--fault-review',type=Path)
 ap.add_argument('--authorized-device-window',action='store_true')
 ap.add_argument('--plan',action='store_true');a=ap.parse_args(argv)
 sys.path.insert(0,str(P))
 from reuse_build import verify_native
 verify_native()
 sys.path.insert(0,str(FROZEN))
 from readiness import verify_ready
 verify_ready()
 if not a.plan:
  subprocess.run([sys.executable,'-B',str(ROOT/'experiments/own-xpu-runtime/ops/packet133-orchestration/verify_cpu.py')],stdin=subprocess.DEVNULL,check=True,timeout=240)
 if a.kind=='bracket' and not a.plan:
  from bracket_job import smoke_gate
  smoke_gate() # exact p130 B smoke, same native composition; local composed smoke still required for chain
 import screen133 as screen
 args=['--lane','A','--placement','1','--lineage',str(FROZEN/'lineage'),'--bracket',str(FROZEN/'configs'/(a.kind+'.json')),'--output',str(a.output)]
 if a.plan:args+=['--plan']
 else:
  assert a.authorized_device_window and a.fault_review,'coordinator authorization and review required'
  assert a.output==HERE/'evidence'/('device-smoke-A' if a.kind=='smoke' else 'device-v5-A'),'fresh registered output required'
  args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
 return screen.main(args)
if __name__=='__main__':raise SystemExit(main())

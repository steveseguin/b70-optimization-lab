"""Coordinator-only v4 C/X/C/X/C, with a separate composed 12x64 smoke."""
import argparse,hashlib,json,os,sys,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];O=P.parents[1]/'ops/packet139-orchestration'
ORDER=('control','candidate','control','candidate','control')
LIBRARIES='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
def view(label):
 from bundle_selection import aliases,name
 return P/'selections'/(name(*aliases()['base' if label=='control' else 'both'])+'--placement-1')
def output(index):
 assert index==-1,'bundle9 has no second-lane grid'
 return P/'evidence/device-smoke-A'
def admission():
 # Run the same CPU admission for --plan and launch, in an isolated import namespace.
 result=subprocess.run(['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(O/'verify_cpu.py')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
 if result.returncode:raise ValueError('CPU admission refused: '+result.stderr[-3000:])
 from source_gate136 import oracle
 oracle()
def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--index',type=int,choices=(-1,),required=True);ap.add_argument('--output',required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 assert Path(a.output).resolve()==output(a.index)
 admission()
 if a.plan:
  cp=subprocess.run([sys.executable,'-B',str(O/'entry_gate.py'),'--probe','-1'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=LIBRARIES))
  if cp.returncode:raise ValueError('real smoke startup probe refused: '+cp.stderr[-4000:])
 if not a.plan:
  assert a.authorized_device_window and a.fault_review
  if a.index>=0:
   from smoke_validation import require_smoke
   require_smoke(lineage=view('candidate'),root=output(-1),lane='A')
   from compare136 import load
   for i in range(a.index):load(dict(lane='A',index=i,choice=ORDER[i]))
 # Closed launch environment, including the library path; no caller setup needed.
 os.environ.clear();os.environ.update(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=LIBRARIES)
 from bootstrap import install
 install()
 lineage=view('candidate' if a.index==-1 else ORDER[a.index])
 args=['--profile','tp2','--lane','A','--placement','1','--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(output(a.index))]
 args+=['--plan'] if a.plan else ['--authorized-device-window','--fault-review',a.fault_review]
 if a.index==-1:
  import smoke_screen as screen
  screen.command=lambda args,identity,manifest:['/usr/bin/python3','-B',str(P/'smoke_worker.py'),'--identity',str(args.output/'identity.json'),'--output',str(args.output/'run'),'--seconds','1800']
  screen.WATCHDOG={'tp2':1800};return screen.main(args)
 from run_screen import main as screen
 return screen(args)
if __name__=='__main__':raise SystemExit(main())

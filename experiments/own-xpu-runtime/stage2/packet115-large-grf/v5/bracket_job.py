"""Coordinator-only one-load B bracket, blocked until micro and CPU evidence pass."""
import argparse, importlib.util, json, sys
from pathlib import Path
from common import HERE,require,read,sha

def micro_winner():
 path=HERE.parent/'micro_gate.py'
 spec=importlib.util.spec_from_file_location('p115_micro_gate',path)
 gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
 # Bind the one root-local dependency explicitly; do not change import search
 # precedence for this wrapper's common/build_engine modules.
 route_spec=importlib.util.spec_from_file_location('p115_route_inputs',HERE.parent/'route_inputs.py')
 route=importlib.util.module_from_spec(route_spec);route_spec.loader.exec_module(route)
 previous=sys.modules.get('route_inputs')
 sys.modules['route_inputs']=route
 try:winners=gate.require_qualified()
 finally:
  if previous is None:sys.modules.pop('route_inputs',None)
  else:sys.modules['route_inputs']=previous
 from bracket_config import VALUES
 require(isinstance(winners,(list,tuple)) and winners,'two fresh micro processes have no qualifying design')
 return next(v for v in VALUES if v in winners)

def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--lane',choices=('B',),required=True)
 ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--fault-review',type=Path)
 ap.add_argument('--authorized-device-window',action='store_true')
 ap.add_argument('--plan',action='store_true')
 a=ap.parse_args(argv)
 from cpu_seal import verify
 verify()
 pending_plan=a.plan and not (HERE.parent/'evidence/micro-qualification.json').is_file()
 if pending_plan:
  print(json.dumps(dict(device_executed=False,micro_qualified=False,conditional_plan=True,launch_eligible=False,reason='two-process micro qualification pending')))
 else:
  winner=micro_winner()
  require(read(HERE/'lineage/candidate.json')['choices']['expert_kernels']==winner,'CPU-sealed candidate differs from earliest qualifying micro design')
 import screen
 args=['--lane','B','--placement','1','--lineage',str(HERE/'lineage'),'--bracket',str(HERE/'configs/bracket.json'),'--output',str(a.output)]
 if a.plan:args+=['--plan']
 else:
  require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
  args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
 return screen.main(args)

if __name__=='__main__':raise SystemExit(main())

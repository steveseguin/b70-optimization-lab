"""Coordinator-only one-load B bracket; micro pass precedes any admission."""
import argparse, importlib.util, sys, subprocess, json
from pathlib import Path
from common import HERE,require
def micro_gate():
 directory=HERE.parent/'micro';sys.path.insert(0,str(directory))
 try:
  spec=importlib.util.spec_from_file_location('p116_micro_gate',directory/'qualification.py')
  gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
  row=gate.evaluate(write=False)
  require(row['passed'] and row['integration_allowed'] and row['kill_gate_passed'],'two fresh exact QSA micros must pass <=0.6 at context128')
  # The micro owns a different sealed common/cpu_seal module namespace.
  # Verify in an isolated read-only process, preserving every inherited limit.
  checked=subprocess.run([sys.executable,'-B',str(HERE/'micro_identity.py')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120,check=True)
  identity=json.loads(checked.stdout)
  require(all(owner['identity']==identity for owner in row['owners']),'micro executable/seal changed after measurements')
  return row
 finally:sys.path.remove(str(directory))
def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--lane',choices=('B',),required=True);ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--fault-review',type=Path);ap.add_argument('--authorized-device-window',action='store_true');ap.add_argument('--plan',action='store_true')
 a=ap.parse_args(argv)
 from cpu_seal import verify
 verify()
 if not a.plan:micro_gate()
 import screen
 args=['--lane','B','--placement','1','--lineage',str(HERE/'lineage'),'--bracket',str(HERE/'configs/bracket.json'),'--output',str(a.output)]
 if a.plan:args+=['--plan']
 else:
  require(a.authorized_device_window and a.fault_review,'coordinator authorization and review required')
  require(not a.output.exists(),'fresh bracket output required')
  args+=['--authorized-device-window','--fault-review',str(a.fault_review)]
 return screen.main(args)
if __name__=='__main__':raise SystemExit(main())

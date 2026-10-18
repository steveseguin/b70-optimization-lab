"""Pre-plan requires the CPU composition; launch additionally requires entry/queue proofs."""
import json
from p145_v5_build_engine import P,ROOT,sha
from cpu_seal import verify,check_sources
GATES=('entry-gate','launch-limits','worker-gate','report-gate','queue-plan','pin-guard')
def verify_ready(preplan=False,variant=None,kind=None,lane=None):
 row=verify()
 if preplan:return row
 for name in GATES:
  path=P/'evidence'/(name+'.json');proof=json.loads(path.read_text())
  assert proof.get('passed') is True and proof.get('device_executed') is False,'missing CPU admission: '+name
  if proof.get('sources'):check_sources(proof['sources'])
 marker_path=P.parent/'READY-FOR-DEVICE.json'
 if not marker_path.exists():
  assert (variant,kind,lane)==('router-order600','smoke','A'),'milestone readiness is router smoke lane A only'
  marker_path=P.parent/'READY-FOR-DEVICE-router-A.json'
 marker=json.loads(marker_path.read_text())
 assert marker.get('passed') is True and marker.get('queued') is False,'final device-readiness marker required'
 assert marker['cpu_seal_sha256']==sha(P/'cpu-seal.json'),'final composition differs'
 for name,digest in marker['cpu_gate_sha256'].items():assert sha(P/'evidence'/(name+'.json'))==digest,'final gate changed: '+name
 return row

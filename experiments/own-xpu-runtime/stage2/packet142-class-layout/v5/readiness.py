"""Pre-plan requires the CPU composition; launch additionally requires entry/queue proofs."""
import json
from p142_v5_build_engine import P,ROOT,sha
from cpu_seal import verify,check_sources
GATES=('entry-gate','launch-limits','worker-gate','queue-plan','pin-guard')
def verify_ready(preplan=False):
 row=verify()
 if preplan:return row
 for name in GATES:
  path=P/'evidence'/(name+'.json');proof=json.loads(path.read_text())
  assert proof.get('passed') is True and proof.get('device_executed') is False,'missing CPU admission: '+name
  if proof.get('sources'):check_sources(proof['sources'])
 marker=json.loads((P.parent/'READY-FOR-DEVICE.json').read_text())
 assert marker.get('passed') is True and marker.get('queued') is False,'final device-readiness marker required'
 assert marker['cpu_seal_sha256']==sha(P/'cpu-seal.json'),'final composition differs'
 for name,digest in marker['cpu_gate_sha256'].items():assert sha(P/'evidence'/(name+'.json'))==digest,'final gate changed: '+name
 return row

"""Final marker is written only after all CPU gates and the proposal plan."""
import json
from p191_v5_build_engine import P,ROOT,sha
from cpu_seal import verify,check_sources
GATES=('entry-gate','launch-limits','worker-gate','report-gate','queue-plan','pin-guard')
def verify_ready(preplan=False,variant=None,kind=None,lane=None,index=None):
 row=verify()
 if preplan:return row
 from bracket_config import ROWS
 assert lane=='B' and index in range(len(ROWS)) and kind==ROWS[index]['kind'] and variant==ROWS[index]['variant'],'registered lane-B packet189 rows only'
 marker=json.loads((P.parent/'READY-FOR-DEVICE.json').read_text())
 assert marker['passed'] and marker['ready_for_device'] and marker['queued'] is False
 for path,digest in marker['proposal_sha256s'].items():assert sha(ROOT/path)==digest,'proposal changed'
 assert marker['cpu_seal_sha256']==sha(P/'cpu-seal.json'),'final composition changed'
 for name in GATES:
  path=P/'evidence'/(name+'.json');proof=json.loads(path.read_text())
  assert proof['passed'] and proof['device_executed'] is False,name
  assert marker['cpu_gate_sha256'][name]==sha(path),'final gate changed: '+name
  if proof.get('sources'):check_sources(proof['sources'])
 return row

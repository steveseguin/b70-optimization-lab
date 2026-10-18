"""Bind the extended CPU gates after planning; hardware admission stays separate."""
import json,resource
from pathlib import Path
from common import HERE,ROOT,read,require,sha,save,verify_map
GATES=('argument-gate','legacy-windows','all-windows','worker-gate','launch-limits','queue-plan','queue-gate','report137b-gate')
def verify_ready():
 from preplan import verify as verify_preplan
 verify_preplan()
 from cpu_seal import verify
 seal=verify();row=read(HERE/'evidence/qualification.json')
 require(row['passed'] is True and row['device_executed'] is False and row['device_quality_and_speed_pending'] is True,'CPU qualification incomplete')
 require(row['screen_seal_sha256']==sha(HERE/'lineage/screen-seal.json'),'CPU seal changed after extended gates')
 verify_map(ROOT,row['sources'])
 for name in GATES:
  gate=read(HERE/'evidence'/(name+'.json'))
  require(gate['passed'] is True and gate['device_executed'] is False,'extended gate failed: '+name)
  if gate.get('sources'):verify_map(ROOT,gate['sources'])
 require(read(HERE/'evidence/argument-gate.json')['registered_windows']==['smoke','bracket'],'missing registered window gate')
 require(read(HERE/'evidence/legacy-windows.json')['total_windows']==44,'missing legacy window shapes')
 require(len(read(HERE/'evidence/queue-gate.json')['cases'])==4,'missing queue success/failure cases')
 return row

def seal_ready():
 from cpu_seal import verify
 verify()
 paths=[HERE/'evidence'/(name+'.json') for name in GATES]
 for p in paths:
  row=read(p);require(row['passed'] is True and row['device_executed'] is False,'missing extended CPU gate')
 sources={str(p.relative_to(ROOT)):sha(p) for p in paths}
 for p in paths:
  row=read(p)
  if row.get('sources'):sources.update(row['sources'])
 sources[str((HERE/'readiness.py').relative_to(ROOT))]=sha(HERE/'readiness.py')
 row=dict(passed=True,device_executed=False,device_quality_and_speed_pending=True,cpu_preparation_ready=True,screen_seal_sha256=sha(HERE/'lineage/screen-seal.json'),sources=sources)
 save(HERE/'evidence/qualification.json',row);return verify_ready()
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 import sys
 row=seal_ready() if '--seal' in sys.argv else verify_ready()
 print(json.dumps(dict(passed=row['passed'],cpu_preparation_ready=True,device_quality_and_speed_pending=True)))

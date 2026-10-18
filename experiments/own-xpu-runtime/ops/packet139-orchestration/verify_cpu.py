"""Read-only, noncircular CPU prerequisites shared by plan and device entry."""
from source_decision import O,P,ROOT,sha

def verify():
 from composite_jobs import current,validate
 _,config=current();validate(config)
 from chain_adapter import install
 install()
 from chain_seal import verify as chain
 chain()
 from drain_check import check
 check()
 return dict(passed=True,device_executed=False,device_quality_and_speed_pending=True)
if __name__=='__main__':
 import json
 print(json.dumps(verify()))

"""Read-only CPU preparation admission for the future lane-A screen."""
from source_decision import O,P,ROOT,sha

def verify():
 from composite_jobs import current,validate
 _,config=current();validate(config)
 from policy_seal import verify as policy
 policy()
 from chain_adapter import install
 install()
 from chain_seal import verify as chain
 chain()
 from argument_gate import verify as arguments
 arguments()
 from orchestrate import verify_tests
 verify_tests()
 from drain_check import check
 check()
 import json
 limits=json.loads((O/'evidence/launch-limits.json').read_text())
 assert limits['passed'] and len(limits['cases'])==4 and all(r['passed'] for r in limits['cases'])
 assert all(sha(ROOT/n)==h for n,h in limits['sources'].items())
 return dict(passed=True,device_executed=False,device_quality_and_speed_pending=True)
if __name__=='__main__':
 import json
 print(json.dumps(verify()))

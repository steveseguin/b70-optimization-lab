"""Recheck identical-selection evidence and all frozen chain bindings."""
import json
from orchestrate import O

def verify():
 row=json.loads((O/'ready.json').read_text())
 assert row['schema']=='packet103.ready.v1'
 assert row.get('evidence_rule')=='identical-selection-v1','Full decision readiness has not run'
 from decision_readiness import verify as verify_decision
 return verify_decision(row)
if __name__=='__main__':verify();print('packet103 readiness verified')

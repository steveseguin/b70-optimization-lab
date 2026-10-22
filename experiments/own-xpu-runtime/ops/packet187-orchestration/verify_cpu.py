"""Admission requires current CPU receipts and their exact source identity."""
import json
from chain_adapter import O,P,ROOT,sha,install

def verify():
 install()
 from chain_seal import verify as seal
 seal()
 row=json.loads((O/'cpu-receipts.json').read_text())
 assert row['passed'] is True and row['device_executed'] is False
 assert row['proposal_sha256']==sha(O/'proposal.jsonl'),'proposal changed'
 for name,digest in row['sources'].items():assert sha(ROOT/name)==digest,'CPU-tested source changed: '+name
 for name,digest in row['receipts'].items():assert sha(ROOT/name)==digest,'CPU receipt changed: '+name
 for name in ('composition-bytes.json','real-shape.json','argument-gate.json','entry187.json','preparation.json','launch-limits.json','submission-rehearsal.json','entry-report.json','real-report.json','transport-gate.json','bracket-gate.json'):
  value=json.loads((O/'evidence'/name).read_text());assert value['passed'] is True,name+' failed'
 return dict(passed=True,device_executed=False,receipt_sha256=sha(O/'cpu-receipts.json'),seal_sha256=sha(P/'build-receipt.json'))
if __name__=='__main__':print(json.dumps(verify(),indent=2))

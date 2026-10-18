"""Hash-bound orchestration policy. Only its explicit CPU CLI writes the seal."""
import json
from pathlib import Path
from source_decision import O,ROOT,sha,save
NAMES=('chain_adapter.py','chain_entry.py','submission.py','submission_evidence.py','prepare_submission.py','device-entry.sh','source_decision.py','composite_jobs.py','composite_screen.py','verify_ready.py','policy_seal.py','orchestrate.py','drain_gate.py','drain_check.py','argument_gate.py','inputs/packet124-native-identity.json')
def verify():
 row=json.loads((O/'policy-seal.json').read_text());assert row['passed']
 for name,digest in row['sources'].items():assert sha(ROOT/name)==digest,'orchestration policy changed: '+name
 assert set(row['sources'])=={str((O/n).relative_to(ROOT)) for n in NAMES}
 return row
if __name__=='__main__':
 save(O/'policy-seal.json',dict(passed=True,device_executed=False,sources={str((O/n).relative_to(ROOT)):sha(O/n) for n in NAMES}));verify()

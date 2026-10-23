"""Seal CPU evidence; READY markers are written by write_ready.py afterwards."""
import json,resource,shutil
from pathlib import Path
from chain_adapter import O,P,ROOT,sha,install

def main():
 assert shutil.disk_usage('/').free>=27_000_000_000
 install()
 from chain_seal import verify
 seal=verify()
 from argument_gate import verify as args
 args()
 names=('composition-bytes.json','real-shape.json','argument-gate.json','entry195.json','preparation.json','preparation-build.json','launch-limits.json','submission-rehearsal.json','entry-report.json','real-report.json','drain-fix.json','input-check.json','transport-gate.json','compile-poll.json','bracket-gate.json')
 receipts={}
 for name in names:
  f=O/'evidence'/name;r=json.loads(f.read_text());assert r['passed'] is True,name
  for path,digest in r.get('sources',{}).items():assert sha(ROOT/path)==digest,'stale gate source '+path
  receipts[str(f.relative_to(ROOT))]=sha(f)
 entry=json.loads((O/'evidence/entry195.json').read_text());assert len(entry['windows'])==11 and entry['negative_unit_and_environment']
 report=json.loads((O/'evidence/entry-report.json').read_text());assert report['proposal_sha256']==sha(O/'proposal.jsonl')
 tests={}
 for name in ('policy-tests.log','readiness-tests.log','submission-tests.log'):
  f=O/'evidence'/name;assert '\nOK\n' in f.read_text(),name;receipts[str(f.relative_to(ROOT))]=sha(f)
 row=dict(passed=True,device_executed=False,model_payload_read=False,sources=seal['sources'],receipts=receipts,scope='CPU preparation/admission only; no packet195 device result or submission',proposal_sha256=sha(O/'proposal.jsonl'))
 (O/'cpu-receipts.json').write_text(json.dumps(row,indent=2)+'\n')
 from verify_cpu import verify as cpu
 cpu();print('all CPU receipts and exact source closure PASS; READY remains a separate last write')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()

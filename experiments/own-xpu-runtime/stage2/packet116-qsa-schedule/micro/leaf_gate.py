"""Verify root GNU/Intel exceptional-value operator gates without importing cap code."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent.parent

def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def verify():
 receipt=P/'evidence/cpu-leaf.json';r=json.loads(receipt.read_text())
 assert r['passed'] is True and r['device_executed'] is False
 assert r['arithmetic']=='iq3-p49-split32-v1' and r['within_compiler_production_candidate_bytes'] is True
 for name,digest in r['source_sha256'].items():assert sha(P/name)==digest,name
 assert {row['compiler'] for row in r['compilers']}=={'GNU','Intel'}
 for compiler in r['compilers']:
  runs=compiler['runs'];assert len(runs)==2 and {x['owner'] for x in runs}=={'1','2'}
  assert len({x['output_sha256'] for x in runs})==1
  for row in runs:
   assert row['passed'] is True and row['device_executed'] is False and row['checks']>=8764
   binary,output=map(Path,row['command']);assert sha(binary)==row['binary_sha256'] and sha(output)==row['output_sha256']
 return {'passed':True,'receipt_sha256':sha(receipt),'source_sha256':r['source_sha256']}

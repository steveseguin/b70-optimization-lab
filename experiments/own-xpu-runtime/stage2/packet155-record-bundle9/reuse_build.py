"""Verify vendored packet153 native bytes without consulting mutable parents."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]
O=ROOT/'experiments/own-xpu-runtime/ops/packet155-orchestration'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify_native():
 row=json.loads((O/'inputs/packet153-native.json').read_text())
 for name,digest in row['sources'].items():
  assert sha(P/name)==digest,'native source changed: '+name
 for name,item in row['binaries'].items():
  assert sha(P/name)==item['sha256'],'native binary changed: '+name
 return row
if __name__=='__main__':verify_native();print('vendored packet153 native identity PASS')

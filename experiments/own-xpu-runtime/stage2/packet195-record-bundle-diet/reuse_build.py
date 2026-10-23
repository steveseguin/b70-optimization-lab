"""Verify the copied packet194 exp-diet engines and diet native snapshot without consulting mutable parents."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]
O=ROOT/'experiments/own-xpu-runtime/ops/packet195-orchestration'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify_native():
 row=json.loads((O/'inputs/packet194-native.json').read_text())
 assert row['reused_byte_for_byte'] is True and row['binaries']['build/device/own-rt-iq3']['sha256']=='b8482321769039274daf42b70f783517177cbc8c1d0b2d81b8ebab25f1442bdc'
 for name,digest in row['sources'].items():
  assert sha(P/name)==digest,'native source changed: '+name
 for name,item in row['binaries'].items():
  assert sha(P/name)==item['sha256'],'native binary changed: '+name
 return row
if __name__=='__main__':verify_native();print('packet194 exp-diet native identity PASS')

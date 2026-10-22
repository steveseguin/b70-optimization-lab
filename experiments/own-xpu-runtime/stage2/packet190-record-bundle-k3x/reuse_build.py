"""Verify the copied packet189 k3x engines and k3x native snapshot without consulting mutable parents."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]
O=ROOT/'experiments/own-xpu-runtime/ops/packet190-orchestration'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify_native():
 row=json.loads((O/'inputs/packet189-native.json').read_text())
 assert row['reused_byte_for_byte'] is True and row['binaries']['build/device/own-rt-iq3']['sha256']=='87eec6453a2a9a9bfe30ed19466c6a70644d9cd168f734be87d2f0a17b776af4'
 for name,digest in row['sources'].items():
  assert sha(P/name)==digest,'native source changed: '+name
 for name,item in row['binaries'].items():
  assert sha(P/name)==item['sha256'],'native binary changed: '+name
 return row
if __name__=='__main__':verify_native();print('packet189 k3x native identity PASS')

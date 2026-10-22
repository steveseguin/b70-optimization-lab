"""Verify the copied packet186 V3 engines and V3 native snapshot without consulting mutable parents."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]
O=ROOT/'experiments/own-xpu-runtime/ops/packet187-orchestration'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify_native():
 row=json.loads((O/'inputs/packet186-native.json').read_text())
 assert row['reused_byte_for_byte'] is True and row['binaries']['build/device/own-rt-iq3']['sha256']=='693cc194bb577cd20f95e63f06bf6e463074944e2d1193f8c3ed1a8a4528d739'
 for name,digest in row['sources'].items():
  assert sha(P/name)==digest,'native source changed: '+name
 for name,item in row['binaries'].items():
  assert sha(P/name)==item['sha256'],'native binary changed: '+name
 return row
if __name__=='__main__':verify_native();print('packet186 V3 native identity PASS')

"""Verify the current all-window interception and actual native CPU proofs."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
O=ROOT/'experiments/own-xpu-runtime/ops/packet155-orchestration'
def verify():
 from reuse_build import verify_native
 verify_native()
 from chain_seal import check_map
 row=json.loads((P/'startup103.json').read_text())
 assert row['passed'] and row['device_executed'] is False
 check_map(ROOT,row['sources'])
 for name in ('composition-bytes.json','real-shape.json'):
  proof=json.loads((O/'evidence'/name).read_text());assert proof['passed'] and proof['device_executed'] is False
 return row

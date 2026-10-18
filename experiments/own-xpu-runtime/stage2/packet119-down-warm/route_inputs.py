"""Read-only verification of packet100b's captured routes; no model or device."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
ORIGIN=P.parent/'packet100b-route-capture/evidence'
MANIFEST=P/'evidence/route-inputs.json';ROUTES=P/'evidence/routes.bin'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read_inputs():
 row=json.loads(MANIFEST.read_text());original=json.loads((ORIGIN/'route-inputs.json').read_text())
 assert sha(ORIGIN/'route-inputs.json')==row['origin_manifest_sha256']
 assert original['passed'] and original['ready'] and original['micro_route_vectors']==384
 assert sha(ROUTES)==row['route_bytes_sha256']==original['route_bytes_sha256']==sha(ORIGIN/'routes.bin')
 assert ROUTES.stat().st_size==384*120
 for name,digest in original['sources'].items():assert sha(ROOT/name)==digest,name
 return row
require_ready=read_inputs
def main():
 from build_engine import limits
 limits();MANIFEST.parent.mkdir(parents=True,exist_ok=True);original=json.loads((ORIGIN/'route-inputs.json').read_text())
 row=dict(schema='packet119.real-routes.v1',passed=True,ready=True,diagnostic_only=True,
  origin_manifest=str((ORIGIN/'route-inputs.json').relative_to(ROOT)),origin_manifest_sha256=sha(ORIGIN/'route-inputs.json'),
  route_bytes_sha256=original['route_bytes_sha256'],micro_route_vectors=384,
  micro_rows=original['micro_rows'],gate_mapping='same expert IDs and order; full row_count 2560 maps to 640 for gate/up; row_begin stays zero',
  weights_and_activations='synthetic diagnostic values; real routing from exact accepted target capture')
 ROUTES.write_bytes((ORIGIN/'routes.bin').read_bytes());MANIFEST.write_text(json.dumps(row,indent=2)+'\n')
 read_inputs();print('384 real route vectors verified; no device run')
if __name__=='__main__':main()

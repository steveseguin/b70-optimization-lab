"""Frozen packet100b target-route evidence, never parent orchestration outputs."""
import gzip,json,struct,hashlib
from build_engine import P,ROOT,sha
MANIFEST=P/'evidence/route-inputs.json.gz'
ROUTES=P/'evidence/routes.bin'
def require_ready():
 row=json.loads(gzip.decompress(MANIFEST.read_bytes()))
 assert row['schema']=='packet100b.real-routes.v1' and row['passed'] and row['ready']
 assert row['micro_route_vectors']==384 and row['all_route_vectors']==6144
 assert row['exact_requests']==2 and row['tokens_per_request']==64
 assert row['micro_checkpoint_fixtures']==[1,16,32,64]
 raw=ROUTES.read_bytes();assert len(raw)==384*120 and sha(ROUTES)==row['route_bytes_sha256']
 for name,digest in row['sources'].items():assert sha(ROOT/name)==digest,name
 assert len(row['micro_rows'])==384
 for i,entry in enumerate(row['micro_rows']):
  chunk=raw[i*120:(i+1)*120]
  assert entry['micro_offset']==i*120 and hashlib.sha256(chunk).hexdigest()==entry['sha256']
  routes=list(struct.iter_unpack('<III',chunk))
  assert all(e<512 and begin==0 and count==2560 for e,begin,count in routes)
  assert len({e for e,_,_ in routes})==10
 return row

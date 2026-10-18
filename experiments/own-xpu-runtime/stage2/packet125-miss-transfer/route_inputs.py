"""Immutable route/mask inputs; no device imports or resource changes."""
import json,struct
from build_engine import P,ROOT,sha
ROUTES=P/'evidence/cases.bin'
def read_inputs():
 row=json.loads((P/'evidence/route-inputs.json').read_text())
 for path,digest in row['origin_sources'].items():assert sha(ROOT/path)==digest,path
 assert sha(ROUTES)==row['cases_sha256']
 assert sha(P/'evidence/all-routes.bin')==row['all_routes_sha256']
 raw=ROUTES.read_bytes();assert len(raw)==384*132
 for i in range(384):
  v=struct.unpack_from('<33I',raw,i*132);assert v[0]<128 and v[0]%64 in (0,15,31,63) and v[1]==i%48 and v[2]<1024
  assert len(set(v[3::3]))==10 and all(e<512 for e in v[3::3]) and set(v[4::3])=={0} and set(v[5::3])=={2560}
 return row

#!/usr/bin/env python3
"""Source-only exact26-request operating adaptation, no runtime admission."""
from pathlib import Path
import json,hashlib,difflib
P=Path(__file__).resolve().parent;L=P.parents[2];R=L.parents[2];OLD=L/'dense-q6-p33/operating'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rep(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
def main():
 pins=json.loads((P/'parent-pins.json').read_text())
 for f,h in pins.items():assert sha(f)==h,f
 out=P/'generated';assert not out.exists();out.mkdir();patch=[];generated={}
 for name in ['generated/adapter.py','generated/suite.py','checks.py','once.py','test_operating.py']:
  before=(OLD/name).read_text();s=before
  if name=='generated/adapter.py':s=rep(s,"'--dense-q6-p33'])","'--dense-q6-p33','--dense-packed-block'])")
  elif name=='generated/suite.py':s=s.replace('gsq_dense_q6_checks','gsq_dense_packed_checks').replace('GSQ additional dense Q6 candidate','GSQ dense packed block candidate')
  elif name=='checks.py':
   s=rep(s,'L=P.parents[1]','L=P.parents[2]')
   s=rep(s,"parent=read(L/'expert-iq3xxs-block/engine/operating/evidence/device-a/review.json')","parent=read(L/'dense-q6-p33/operating/evidence/device-a/review.json')")
   s=rep(s,"require(parent['passed'] is True,'qualified current combined Engine')","require(parent['passed'] is True and parent['all12_exact'] and parent['physical_drain'],'qualified current combined Engine')\n micro=read(L/'dense-packed-block/micro/operating/evidence/device-a/review.json');require(micro['passed'] and micro['qualification_complete'] and micro['exact_pairs']==84 and micro['backend_ACK'] and micro['physical_drain'],'qualified three-format physical micro')")
   s=rep(s,"for name,h in read(P/'authority.json').items():","newdelta=read(CANDIDATE/'memory-ledger.json');require(newdelta['delta_bytes']==[0,0] and newdelta['initial_host_forecast_increment_bytes']==0 and newdelta['device_forecast_bytes']==[r['device_logical_bytes'] for r in new],'zero allocation delta')\n for name,h in read(P/'authority.json').items():")
  elif name=='once.py':
   s=rep(s,'L=P.parents[1]','L=P.parents[2]');s=s.replace('gsq-dense-q6-p33-engine-a','gsq-dense-packed-block-engine-a').replace('gsq_dense_q6','gsq_dense_packed').replace('gsq.dense-q6-once','gsq.dense-packed-once')
   s=rep(s,"L/'expert-iq3xxs-block/engine/operating/evidence/device-a/review.json'","L/'dense-q6-p33/operating/evidence/device-a/review.json',L/'dense-packed-block/micro/operating/evidence/device-a/review.json'")
  elif name=='test_operating.py':s=rep(s,"'--dense-q6-p33']","'--dense-q6-p33','--dense-packed-block']")
  dest=P/name;dest.write_text(s);generated[str(dest.relative_to(R))]=sha(dest);patch.extend(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile=str((OLD/name).relative_to(R)),tofile=str(dest.relative_to(R))))
 (P/'overlay.patch').write_text(''.join(patch));(P/'candidate-ledger.json').write_bytes((OLD/'candidate-ledger.json').read_bytes())
 auth=json.loads((OLD/'authority.json').read_text())
 for f in [OLD/'evidence/device-a/review.json',L/'dense-packed-block/micro/operating/evidence/device-a/review.json',P.parent/'memory-ledger.json',P.parent/'selection.json',P.parent/'preparation.json']:
  auth[str(f)]=sha(f)
 (P/'authority.json').write_text(json.dumps(auth,indent=2)+'\n')
 result=dict(schema='gsq.dense-packed-block.operating.source.v1',source_sha256={str(Path(f).relative_to(R)):h for f,h in pins.items()},generated_sha256=generated,recipe_sha256=sha(__file__),patch_sha256=sha(P/'overlay.patch'),device_executed=False,requests=26,retained_capture_groups=27,target_bundles=54,metadata_forecast_bytes=128*1024**2)
 (P/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()

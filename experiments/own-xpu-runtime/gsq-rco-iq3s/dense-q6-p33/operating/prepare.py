#!/usr/bin/env python3
"""Private source-only adaptation of qualified combined bundle suite."""
import difflib,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2];OLD=L/'expert-iq3xxs-block/engine/operating'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
def main():
 pins=json.loads((P/'parent-pins.json').read_text())
 for f,h in pins.items():assert sha(f)==h,f
 out=P/'generated';assert not out.exists();out.mkdir();patch=[];generated={}
 names=['generated/adapter.py','generated/suite.py','checks.py','once.py','test_operating.py']
 for name in names:
  src=OLD/name;before=src.read_text();s=before
  if name=='generated/adapter.py':
   s=replace(s,"LEDGER=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/qkv-q6-p33/engine/operating/candidate-ledger.json')","LEDGER=P.parent/'candidate-ledger.json'")
   s=replace(s,"'--expert-iq3xxs-block'])","'--expert-iq3xxs-block','--dense-q6-p33'])")
  elif name=='generated/suite.py':s=s.replace('gsq_iq3_block_checks','gsq_dense_q6_checks').replace('GSQ IQ3_XXS block candidate','GSQ additional dense Q6 candidate')
  elif name=='checks.py':
   s=replace(s,'L=P.parents[2]','L=P.parents[1]')
   s=replace(s,"ledger['initial_mem_available_delta_bytes']==382730240","ledger['initial_mem_available_delta_bytes']==571473920")
   s=replace(s,'for a,b,q6 in zip(old,new,(183500800,104857600)):', 'for a,b,q6,dense in zip(old,new,(183500800,104857600),(47185920,141557760)):')
   s=replace(s,"b['device_logical_bytes']==a['device_logical_bytes']+47185920+q6 and b['expanded_q8_delta_bytes']==47185920 and b['expanded_q6_delta_bytes']==q6","b['device_logical_bytes']==a['device_logical_bytes']+47185920+q6+dense and b['expanded_q8_delta_bytes']==47185920 and b['expanded_q6_delta_bytes']==q6 and b['expanded_dense_q6_delta_bytes']==dense")
   s=replace(s,'scale_authority();qkv_authority()','scale_authority();qkv_authority();parent_engine_authority()')
   start=s.index('def bundle_and_micro_authority():');end=s.index('\ndef capture_stamp(',start)
   s=s[:start]+'''def parent_engine_authority():
 parent=read(L/'expert-iq3xxs-block/engine/operating/evidence/device-a/review.json')
 require(parent['passed'] is True,'qualified current combined Engine')
 bundle=read(L/'state-bundle/evidence/device-a/review.json');require(bundle['passed'] is True,'qualified bundle writer')
 return parent
'''+s[end:]
  elif name=='once.py':
   s=replace(s,'L=P.parents[2]','L=P.parents[1]');s=s.replace('gsq-iq3xxs-block-engine-a','gsq-dense-q6-p33-engine-a').replace('gsq_iq3_block','gsq_dense_q6').replace('gsq.iq3xxs-block-once','gsq.dense-q6-once').replace('initial_ram_delta_bytes=382730240','initial_ram_delta_bytes=571473920')
   s=replace(s,"P.parent.parent/'micro/evidence/device-a/review.json'","L/'expert-iq3xxs-block/engine/operating/evidence/device-a/review.json'")
   s=replace(s,"P/'adaptation.patch'","P/'overlay.patch'")
  elif name=='test_operating.py':
   s=s.replace("'--expert-iq3xxs-block']","'--expert-iq3xxs-block','--dense-q6-p33']").replace('[30947490698,29824495508]','[30994676618,29966053268]')
  dest=P/name;dest.write_text(s);generated[str(dest.relative_to(R))]=sha(dest)
  patch.extend(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile=str(src.relative_to(R)),tofile=str(dest.relative_to(R))))
 (P/'overlay.patch').write_text(''.join(patch))
 ledger=json.loads((OLD/'candidate-ledger.json').read_text());ledger['schema']='ownrt.gsq.dense-q6-memory.v1';ledger['initial_mem_available_delta_bytes']=571473920;ledger['scope']='Existing qualified combined allocations plus19 dense Q6 expansions; no new workspace. Actual census required.'
 for r,delta in zip(ledger['scenarios']['split24-24_mtp-rank0']['ranks'],(47185920,141557760)):
  r['device_logical_bytes']+=delta;r['expanded_dense_q6_delta_bytes']=delta
 (P/'candidate-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 auth=json.loads((OLD/'authority.json').read_text());f=OLD/'evidence/device-a/review.json';auth[str(f)]=sha(f)
 for f in (P.parent/'memory-ledger.json',P.parent/'selection.json',P.parent/'preparation.json'):auth[str(f)]=sha(f)
 (P/'authority.json').write_text(json.dumps(auth,indent=2)+'\n')
 result=dict(schema='gsq.dense-q6.operating.source.v1',source_sha256={str(Path(f).relative_to(R)):h for f,h in pins.items()},generated_sha256=generated,recipe_sha256=sha(__file__),patch_sha256=sha(P/'overlay.patch'),device_executed=False,requests=26,retained_state_dumps=27,metadata_forecast_bytes=128*1024**2)
 (P/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()

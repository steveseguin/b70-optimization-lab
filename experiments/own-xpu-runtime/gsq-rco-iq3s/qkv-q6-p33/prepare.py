#!/usr/bin/env python3
"""Fixed Q6 QKV source selection and fixture plan. No model/fixture payload reads."""
from pathlib import Path
import hashlib,json,gzip,difflib
P=Path(__file__).resolve().parent;L=P.parent;ROOT=L.parents[2]
STAGE=L/'integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2'
EXPECTED=[0,2,4,5,6,8,9,14,16,17,18,20,21,22,24,25,28,30,32,36,37,40]
CASES=[0,24,40]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 cpath=L/'metadata/new-census.json';gpath=L/'graph/new-plan.json'
 assert sha(cpath)=='b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1'
 assert sha(gpath)=='4d37ea499b0994a69664309d8f3c88aefc908e5034ac441b63f02e02151cf78b'
 c=json.loads(cpath.read_text());g=json.loads(gpath.read_text());sites=[];counts={}
 for x in g['launches']:
  if not x['label'].endswith('.gdn.qkv'):continue
  t=c['tensors'][x['weights'][0]];counts[t['type']]=counts.get(t['type'],0)+1
  if t['type']!='Q6_K':continue
  layer=int(x['label'].split('.')[1]);assert x['op']=='gemv' and x['shape']==[1,10240,2560] and t['shape']==[10240,2560] and t['bytes']==21504000
  sites.append(dict(layer=layer,label=x['label'],weight=x['weights'][0],rows=10240,columns=2560,packed_bytes=t['bytes'],expanded_bytes=34611200,rank=0 if layer<24 else 1,shard=t['shard'],offset=t['file_offset']))
 assert [s['layer'] for s in sites]==EXPECTED
 profile_review=L/'profiling/evidence/independent-a/review.json';r=json.loads(profile_review.read_text());assert r['passed'] and r['exact_baseline_tokens'] and r['exact_baseline_target_state']
 pindex=L/'profiling/evidence/independent-a/artifact-index.jsonl.gz';bindex=L/'baseline/evidence/independent-a/artifact-index.jsonl.gz';assert sha(pindex)==r['index_sha256'];assert sha(bindex)=='e8137dddb0929d5476d27a8a774539a77d595aeb296e9d0ec778ceec066a6982'
 indexes=[]
 for path in (pindex,bindex):
  with gzip.open(path,'rt') as f:indexes.append({(x['root'],x['path']):x for x in map(json.loads,f)})
 cases=[]
 for layer in CASES:
  site=next(x for x in sites if x['layer']==layer);rank=site['rank'];entry=dict(site=site,fixtures={})
  for kind,name,size in [('input',f'blk.{layer}.hc.a.mix',5120),('expected',f'blk.{layer}.gdn.qkv',20480)]:
   writers=[{'index':i,'label':x['label'],'op':x['op']} for i,x in enumerate(g['launches']) if name in x['outputs']];readers=[{'index':i,'label':x['label'],'op':x['op']} for i,x in enumerate(g['launches']) if name in x['inputs']]
   assert len(writers)==1 and writers[0]['op']==('hc_mix' if kind=='input' else 'gemv')
   suffix=f'rank{rank}/state-2147483647/{name}.bin';pp='profile-none/'+suffix;bp='prompt-00-none/'+suffix
   # The independently audited profile has identical complete target state.
   ps=next(v for (root,path),v in indexes[0].items() if path==pp);bs=indexes[1][('evidence',bp)]
   assert ps['bytes']==bs['bytes']==size and ps['sha256']==bs['sha256']
   entry['fixtures'][kind]=dict(source='/mnt/usb-models/own-xpu-runtime-results/gsq-profile-a/'+pp,baseline_original='/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a/'+bp,bytes=size,sha256=ps['sha256'],writers=writers,readers=readers)
  cases.append(entry)
 text=(STAGE/'packet194-expert-diet-engine/p33_candidates.hpp').read_text();a=text.index('template<iq3::Type T,unsigned K>\ninline float dense_lane(');z=text.index('// Integer rank scheduling',a);body=text[a:z]
 (P/'fixture_math.hpp').write_text('#pragma once\n#include "'+str(STAGE/'packet6-kopt/reference.hpp')+'"\n#include "'+str(STAGE/'packet194-expert-diet-engine/p28/dense.hpp')+'"\nnamespace p33 {\n'+body+'\n}\n')
 old=L/'attention-q8-p33/micro/runner.cpp';src=old.read_text();assert sha(old)=='8c4b534f3df7a58d0b3887cc45b5d1d06b60d2aeee5c67b927c71ce81cd7de5d'
 # Same reviewed lifecycle/schedule. Geometry-only transformation; no kernel body.
 replacements={'iq3::Type::Q8_0':'iq3::Type::Q6_K','16711680':'21504000','18677760':'34611200','12288':'5120','81920':'327680','106481664':'169466880','134217728':'201326592','gsq.attention-q8.native-micro.v1':'gsq.qkv-q6.native-micro.v1'}
 # Output replacements precede input replacements to avoid replacing new input size.
 src=src.replace('5120','20480')
 for before,after in replacements.items():src=src.replace(before,after)
 src=src.replace('m.rows=2560;m.columns=6144','m.rows=10240;m.columns=2560').replace('m.span=2560','m.span=10240').replace(',2560,6144,iq3::Type::BF16',',10240,2560,iq3::Type::BF16').replace('data[i].w.size(),6144','data[i].w.size(),2560')
 (P/'micro/runner.cpp').write_text(src)
 (P/'micro/runner.patch').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),src.splitlines(True),fromfile=str(old),tofile=str(P/'micro/runner.cpp'))))
 selected=L/'attention-q8-p33/micro/selected.hpp';(P/'micro/selected.hpp').write_bytes(selected.read_bytes())
 files=[cpath,gpath,profile_review,pindex,bindex,L/'baseline/evidence/independent-a/review.json',old,selected,L/'integration/evidence/full-native-build.json',L/'attention-q8-p33/evidence/native-build.json',STAGE/'packet6-kopt/reference.hpp',STAGE/'packet6-kopt/kernels.cpp',STAGE/'packet10-kopt5/expanded.hpp',STAGE/'packet194-expert-diet-engine/p33_candidates.hpp',STAGE/'packet194-expert-diet-engine/p33_submit.cpp',STAGE/'packet194-expert-diet-engine/owner.cpp',L/'integration/build/private/source/diet-native/native-src/main.cpp']
 plan={'schema':'gsq.qkv-q6.source-selection.v1','qkv_format_counts':counts,'selected_layers':EXPECTED,'sites':sites,'micro_cases':cases,'fixture_payload_bytes':76800,'fixture_payload_read':False,'weight_payload_read':False,'native_compiled':False,'source_sha256':{str(f):sha(f) for f in files},'selected_p33_body_sha256':hashlib.sha256(body.encode()).hexdigest(),'variant':6,'split':1,'micro_device_bytes':169466880,'micro_transfer_cap':201326592,'allocation_delta_bytes':288358400,'per_rank_delta_bytes':[183500800,104857600],'combined_with_attention_device_bytes':[30947490698,29824495508],'timing_scope':'Old aggregate QKV1811.757ms mixes four formats; no Q6-only timing attribution.'}
 (P/'selection.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps({'selected_sites':len(sites),'planned_fixture_bytes':76800,'payload_reads':False}))
if __name__=='__main__':main()

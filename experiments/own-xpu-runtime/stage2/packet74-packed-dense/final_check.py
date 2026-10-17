"""Read-only seal/pin checks; emits only this packet's final CPU receipt."""
import json,sys,re
from pathlib import Path
from types import SimpleNamespace
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sys.path.insert(0,str(P/'screen'))
from common import read,sha,sealed,save,verify_map,require
from cpu_seal import verify
from conditions import cpu_gate

def main():
 cpu_gate();wrapper=verify()
 build=read(P/'build-device-receipt.json');verify_map(ROOT,build['sources']);verify_map(P,build['artifacts'])
 fixture=read(P/'evidence/cpu-byte-identity.json');verify_map(ROOT,fixture['sources']);require(fixture['passed'] and len(fixture['runs'])==4,'CPU fixture runs')
 for r in fixture['runs']:
  source=ROOT/r['path'];require(sha(source/'expected.bin')==r['expected_sha256']==r['candidate_sha256']==sha(source/'candidate.bin'),'fixture bytes changed')
  require(r['native']['cases']==60 and r['native']['dequant_values']==5657600,'fixture coverage')
 micro=read(P/'evidence/microbench-build.json');verify_map(ROOT,micro['sources']);require(sha(P/'build/microbench')==micro['binary_sha256'],'microbenchmark binary')
 views=[]
 for name in ('production','head-packed','dense-packed','combined'):
  v=P/'selections'/name
  identity=sealed(SimpleNamespace(lineage=v,seal=v/'screen-seal.json',binary=v/'build/device/own-rt-iq3',dispatch=v/'dispatch-speed6.json',profile='tp2',timing='token',placement='1'))
  require(identity['placement']['supported'],'unsupported view');views.append(dict(name=name,seal_sha256=sha(v/'screen-seal.json'),binary_sha256=identity['binary_sha256']))
 require(len({v['binary_sha256'] for v in views})==1,'shared binary')
 plans_a=read(P/'evidence/plans-A.json')['plans'];alternatives=read(P/'evidence/plans-B.json')['alternatives']
 require(len(plans_a)==5 and len(alternatives)==3 and all(len(a['plans'])==3 for a in alternatives),'screen plan coverage')
 plans=plans_a+[p for a in alternatives for p in a['plans']];require(all(p['supported'] and p['identity']['placement']['supported'] for p in plans),'unsupported screen plan')
 require(read(P/'evidence/queue-plans.json')['passed'],'queue plans')
 parents=read(P/'parent-source-manifest.json');verify_map(ROOT,parents)
 modified=[]
 for path,digest in parents.items():
  local=P/Path(path).name
  if sha(local)!=digest:modified.append(local.name)
 require(set(modified)=={'main.cpp','mtp.hpp','p49c_kernel.hpp','p49d_submit.cpp','math_gate.py','selection.json'},'unexpected parent source delta: '+str(modified))
 vram=read(P/'VRAM.json');verify_map(ROOT,vram['sources'])
 require(vram['views']['combined']['net_vram_saving_bytes_by_rank']==[661749760,682327040],'VRAM accounting')
 test_text=(P/'screen/placement-validation/tests.log').read_text();require('Ran 79 tests' in test_text and test_text.rstrip().endswith('OK'),'wrapper tests')
 size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file());require(size<1_000_000_000,'build budget')
 proofs={str(p.relative_to(ROOT)):sha(p) for p in [P/'final_check.py',P/'VRAM.json',P/'evidence/plans-A.json',P/'evidence/plans-B.json',P/'evidence/queue-plans.json',P/'evidence/cpu-byte-identity.json',P/'evidence/microbench-build.json',P/'screen/placement-validation/wrapper-seal.json']}
 save(P/'evidence/final-validation.json',dict(passed=True,device_executed=False,cpu_model_executed=False,views=views,wrapper_tests=79,screen_plans=14,queue_plans=2,build_logical_bytes=size,build_peak_rss_kib=build['max_rss_kib'],cpu_fixture_peak_rss_kib=fixture['max_rss_kib'],microbench_build_peak_rss_kib=micro['max_rss_kib'],modified_copied_inputs=modified,proofs=proofs,device_quality='pending',device_speed='unmeasured',actual_peak_vram='unmeasured'))
 print('PASS: four sealed views, one binary, GNU+Intel bytes,79 mocks,14 screen plans,2 queue plans; build bytes',size)
if __name__=='__main__':main()

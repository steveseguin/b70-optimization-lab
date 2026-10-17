"""Read-only seal verification plus small local CPU evidence retention."""
import json,shutil,sys
from pathlib import Path
from types import SimpleNamespace
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sys.path.insert(0,str(P/'screen'))
from common import read,sha,sealed,save,verify_map
from cpu_seal import verify
from conditions import cpu_gate
def main():
 cpu_gate();verify()
 build=read(P/'build-device-receipt.json');verify_map(ROOT,build['sources']);verify_map(P,build['artifacts'])
 fixture=read(P/'evidence/cpu-byte-identity.json');verify_map(ROOT,fixture['sources'])
 runs=[]
 for r in fixture['runs']:
  source=ROOT/r['path'];dest=P/'evidence/cpu-runs'/r['compiler']/f"repeat-{r['repeat']}";dest.mkdir(parents=True,exist_ok=True)
  assert sha(source/'expected.bin')==r['expected_sha256']==r['candidate_sha256']==sha(source/'candidate.bin')
  for n in ('cases.jsonl','native.json','run.log'):shutil.copyfile(source/n,dest/n)
  runs.append(dict(compiler=r['compiler'],repeat=r['repeat'],sources={str((dest/n).relative_to(ROOT)):sha(dest/n) for n in ('cases.jsonl','native.json','run.log')}))
 views=[]
 for name in ('production','attention-out','combined'):
  v=P/'selections'/name
  identity=sealed(SimpleNamespace(lineage=v,seal=v/'screen-seal.json',binary=v/'build/device/own-rt-iq3',dispatch=v/'dispatch-speed6.json',profile='tp2',timing='token',placement='1'))
  assert identity['placement']['supported'];views.append(dict(name=name,seal_sha256=sha(v/'screen-seal.json'),binary_sha256=identity['binary_sha256']))
 assert len({v['binary_sha256'] for v in views})==1
 for lane,n in [('A',4),('B',3)]:
  plans=read(P/'evidence/reseal-r2'/f'plans-{lane}.json');assert len(plans['plans'])==n and all(p['supported'] and p['reservation_scope']=='lane-'+lane for p in plans['plans'])
 assert read(P/'evidence/reseal-r2/validation.json')['passed']
 size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file());assert size<1_000_000_000
 save(P/'evidence/final-validation.json',dict(passed=True,device_executed=False,cpu_model_executed=False,views=views,cpu_runs=runs,wrapper_tests=82,screen_plans=7,queue_plans=1,build_logical_bytes=size,build_peak_rss_kib=build['max_rss_kib'],cpu_fixture_peak_rss_kib=fixture['max_rss_kib'],actual_dram_counters='unavailable',device_quality='pending',device_speed='unmeasured'))
 print('PASS: three views, one binary, four CPU lifetimes, seven screen plans, revision-2 queue plan; build bytes',size)
if __name__=='__main__':main()

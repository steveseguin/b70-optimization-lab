"""Seal packet91 compositions using pinned binaries and exact CPU evidence."""
from functools import lru_cache
import gzip,hashlib,importlib.util,json,os
from build_engine import P,ROOT,B,PARENTS,sha,save,limits,provenance
from bundle_selection import views,choices,selection,placements,PLACEMENTS,prefix_rows,name as view_name
from chain_seal import check_map
GATES=('cpu-byte-identity.json','full-shape.json')
@lru_cache(maxsize=1)
def proof():
 build=provenance();reports={n:json.loads((P/'evidence'/n).read_text()) for n in GATES};sources=dict(build['sources'])
 for r in reports.values():
  assert r['passed'] and r['device_executed'] is False;check_map(ROOT,r['sources']);sources.update(r['sources'])
 memory_source=str((P/'lineage-inputs/packet91-memory-plan.json').relative_to(ROOT));sources[memory_source]=sha(ROOT/memory_source)
 from startup_receipt103 import verify as verify_startup
 startup=verify_startup();sources.update(startup['sources']);sources[startup['archive']['path']]=startup['archive']['sha256'];sources[str((P/'startup103.json').relative_to(ROOT))]=sha(P/'startup103.json')
 sources[str((P/'copy-lineage.json').relative_to(ROOT))]=sha(P/'copy-lineage.json')
 shape=reports['full-shape.json'];assert {(r['view'],r['rank']) for r in shape['runs']}=={(n,rank) for n in views() for rank in (0,1)}
 for row in shape['runs']:
  assert row['passed'] and row['selection_key_consumers_verified']
  for art in row['artifacts'].values():assert sha(ROOT/art['path'])==art['sha256'];sources[art['path']]=art['sha256']
 assert set(reports['cpu-byte-identity.json']['views'])==set(views())
 sources.update(json.loads((P/'dependency-pins.json').read_text()));check_map(ROOT,sources)
 extras=[*P.glob('*.py'),* (P/'prefix-calibration').glob('*.json'),P/'build-device-receipt.json',P/'baseline-pins.json',P/'extension-slots.json',P/'placement-policy.json',P/'dependency-pins.json',P/'selection-template.json',P/'shared-wrapper-pin.json',*[P/'evidence'/n for n in GATES]]
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in extras})
 return build,reports,sources

def seal_view(v,placement):
 from stopped_archive import require_fresh_chain
 require_fresh_chain(B);assert placement in placements(v)
 from bootstrap import install
 install();build,reports,sources=proof();name=view_name(*v)
 selected=reports['cpu-byte-identity.json']['views'][name];assert selected['choices']==choices(*v)
 assert {(r['compiler'],r['repeat']) for r in selected['runs']}=={(c,n) for c in ('GNU','Intel') for n in (1,2)}
 for r in selected['runs']:
  f=ROOT/r['fixture'];assert sha(f)==r['fixture_sha256'];assert hashlib.sha256(gzip.decompress(f.read_bytes())).hexdigest()==r['expected_sha256']==r['candidate_sha256'];sources[str(f.relative_to(ROOT))]=sha(f)
 view=P/'selections'/(name+'--placement-'+placement);view.mkdir(parents=True,exist_ok=True)
 if (view/'screen-seal.json').exists():
  seal=json.loads((view/'screen-seal.json').read_text());check_map(ROOT,seal['sources'])
  for key in ('artifacts','gates','fixture_files'):check_map(view,seal[key])
  return view
 save(view/'selection.json',selection(v))
 from memory_plans import plan
 save(view/'memory-plan.json',plan(v))
 (view/'dispatch-speed6.json').write_bytes((P/'dispatch-speed6.json').read_bytes())
 binaries=build['variants'][v[6]]['binaries'];artifacts={}
 for mode,item in binaries.items():
  dest=view/'build'/mode/'own-rt-iq3';dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists():os.link(ROOT/item['path'],dest)
  assert sha(dest)==item['sha256'];artifacts[str(dest.relative_to(view))]=item['sha256']
 fixture=ROOT/selected['runs'][0]['fixture']
 for n in ('expected','actual'):
  dest=view/('fixture-'+n+'.bin.gz');dest.write_bytes(fixture.read_bytes())
 parent=PARENTS[v[6]]
 audit=dict(placement=placement,draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],draft_prefix_rows=int(v[14]),rank0_private_prefix_bytes=0,target_head=choices(*v)["head"],rank1_separate_expanded_prefix_bytes=0,dispatch_sha256=sha(view/'dispatch-speed6.json'),binary_sha256=binaries['device']['sha256'],engine_sources={str((parent/n).relative_to(ROOT)):sha(parent/n) for n in ('main.cpp','rank.hpp','mtp.hpp','native_controller.hpp','p56_config.hpp','p56_prefix.hpp')},memory_sources=reports['full-shape.json']['sources'])
 save(view/'placement-audit.json',audit);sources[str((view/'placement-audit.json').relative_to(ROOT))]=sha(view/'placement-audit.json')
 bp=view/'build-receipt.json';fp=view/'byte-fixture.json';save(bp,dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts))
 save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,build_receipt_sha256=sha(bp),sources=reports['cpu-byte-identity.json']['sources'],changed_class='Packet97 compiled runtime. All selected GNU/Intel raw operator bytes, joint expert grid/cache arithmetic, host report-state bytes, and complete joint startup/admission.',command=['python3','-B',str(P/'cpu_gate.py')],**{k:dict(path='fixture-'+k+'.bin.gz',sha256=sha(view/('fixture-'+k+'.bin.gz'))) for k in ('expected','actual')}))
 spec=importlib.util.spec_from_file_location('packet91_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 generic.create(view,'tp2',bp,fp,view/'build/device/own-rt-iq3',view/'dispatch-speed6.json',view/'screen-seal.json')
 save(P/'cpu-validation.json',dict(passed=True,device_executed=False,cpu_model_executed=False,files={str((P/'evidence'/n).relative_to(ROOT)):sha(P/'evidence'/n) for n in GATES}))
 return view

def main():
 limits()
 for name,v in views().items():seal_view(v,'1');print(name,'sealed',flush=True)
if __name__=='__main__':main()

"""Seal isolated DOWN views; composition corners are startup proofs only."""
import gzip,hashlib,importlib.util,json,os
from build_engine import P,ROOT,B,sha,save,limits,provenance
from bundle_selection import views,choices,selection
from memory_plans import plan
from chain_seal import check_map

def main():
 limits()
 from bootstrap import install
 install()
 from cpu_seal import verify as verify_wrapper
 wrapper=verify_wrapper();build=provenance()
 reports={n:json.loads((P/'evidence'/n).read_text()) for n in ('cpu-byte-identity.json','full-shape.json','python-tests.json')}
 sources=dict(build['sources'])
 for row in reports.values():
  assert row['passed'] and not row['device_executed'];check_map(ROOT,row['sources']);sources.update(row['sources'])
 shape=reports['full-shape.json'];cpu=reports['cpu-byte-identity.json']
 assert {(r['view'],r['rank']) for r in shape['runs']}=={(v,r) for v in views() for r in (0,1)}
 assert shape['negative_extent_rejected'] and len(shape['negative_allocations'])==68 and shape['selection_negatives_rejected']==5 and shape['unsupported_modes_rejected']==14
 assert all(r['passed'] and r['selection_key_consumers_verified'] for r in shape['runs'])
 for r in shape['runs']:
  for a in r['artifacts'].values():assert sha(ROOT/a['path'])==a['sha256'];sources[a['path']]=a['sha256']
 offline=json.loads((P/'register-report-offline.json').read_text());assert offline['passed'] and not offline['device_executed'];check_map(ROOT,offline['sources']);sources.update(offline['sources'])
 for r in offline['kernels']:assert sha(ROOT/r['assembly'])==r['sha256'];sources[r['assembly']]=r['sha256']
 extras=[*P.glob('*.py'),P/'placement-policy.json',P/'shared-wrapper-pin.json',P/'dependency-pins.json',P/'selection-template.json',P/'build-device-receipt.json',P/'register-report-offline.json',*[P/'evidence'/n for n in reports]]
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in extras});sources.update(wrapper['sources']);check_map(ROOT,sources)
 spec=importlib.util.spec_from_file_location('p100_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 for name in ('production','down-interleave','down-tile16'):
  v=P/'selections'/name;v.mkdir(parents=True,exist_ok=True);assert not (v/'screen-seal.json').exists()
  selected=cpu['views'][name];assert selected['passed'] and selected['choices']==choices(name)
  assert {(r['compiler'],r['repeat']) for r in selected['runs']}=={(c,r) for c in ('GNU','Intel') for r in (1,2)}
  raw=set()
  for r in selected['runs']:
   assert r['cases']==36 and r['raw_fp32_chain_checks']==62208 and r['raw_fp32_tree_checks']==1944 and r['half_patterns']==65536
   f=ROOT/r['raw_evidence'];assert sha(f)==r['raw_evidence_sha256'];assert hashlib.sha256(gzip.decompress(f.read_bytes())).hexdigest()==r['candidate_sha256']==r['expected_sha256'];raw.add(r['candidate_sha256']);sources[r['raw_evidence']]=sha(f)
   f=ROOT/r['cases_path'];assert sha(f)==r['cases_sha256'];sources[r['cases_path']]=sha(f)
  assert len(raw)==1
  save(v/'selection.json',selection(name));save(v/'memory-plan.json',plan((name,)));(v/'dispatch-speed6.json').write_bytes((P/'dispatch-speed6.json').read_bytes())
  artifacts={}
  for mode,item in build['variants']['rec-parallel']['binaries'].items():
   dest=v/'build'/mode/'own-rt-iq3';dest.parent.mkdir(parents=True,exist_ok=True)
   if not dest.exists():os.link(ROOT/item['path'],dest)
   assert sha(dest)==item['sha256'];artifacts[str(dest.relative_to(v))]=sha(dest)
  fixture=ROOT/selected['runs'][0]['raw_evidence']
  for n in ('expected','actual'):(v/('fixture-'+n+'.bin.gz')).write_bytes(fixture.read_bytes())
  audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],draft_prefix_rows=91392,rank0_private_prefix_bytes=0,target_head='production',rank1_separate_expanded_prefix_bytes=0,dispatch_sha256=sha(v/'dispatch-speed6.json'),binary_sha256=artifacts['build/device/own-rt-iq3'],engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','native_controller.hpp','p100_down.hpp','p49d_expert_submit.cpp')},memory_sources=shape['sources'])
  save(v/'placement-audit.json',audit);bound=dict(sources);bound[str((v/'placement-audit.json').relative_to(ROOT))]=sha(v/'placement-audit.json')
  bp=v/'build-receipt.json';fp=v/'byte-fixture.json';save(bp,dict(passed=True,device_executed=False,sources=bound,artifacts=artifacts))
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='DOWN raw packed-byte permutation and/or workgroup order; full GNU/Intel FP32 chains/tree and BF16/status bytes; 34 startup corners with actual arenas',command=['python3','-B',str(P/'cpu_gate.py')],build_receipt_sha256=sha(bp),sources=cpu['sources'],raw_runs=selected['runs'],**{k:dict(path='fixture-'+k+'.bin.gz',sha256=sha(v/('fixture-'+k+'.bin.gz'))) for k in ('expected','actual')}))
  generic.create(v,'tp2',bp,fp,v/'build/device/own-rt-iq3',v/'dispatch-speed6.json',v/'screen-seal.json');print(name,'sealed',flush=True)
 job_sources={str(f.relative_to(ROOT)):sha(f) for f in extras}
 for v in (P/'selections').iterdir():job_sources[str((v/'screen-seal.json').relative_to(ROOT))]=sha(v/'screen-seal.json')
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,sources=job_sources,wrapper_seal_sha256=sha(P.parent/'screen/v4-lanes/wrapper-seal.json')))
if __name__=='__main__':main()

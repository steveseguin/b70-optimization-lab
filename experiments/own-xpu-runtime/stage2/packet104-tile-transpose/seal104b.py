"""Seal three CPU-qualified views; pin immutable parent code/object inputs only."""
import gzip,hashlib,importlib.util,json,os
from build_engine import P,ROOT,B,sha,save,limits
from build104b import provenance
from bundle_selection import views,choices,selection
from memory_plans import plan
from chain_seal import check_map

def main():
 limits()
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert size<=200_000_000,size
 from down_proof104b import verify as verify_down
 down=verify_down()
 from bootstrap import install
 install()
 from cpu_seal import verify as verify_wrapper
 wrapper=verify_wrapper();build=provenance()
 from screening_override import verify
 verify()
 cpu=json.loads((P/'evidence/cpu-byte-identity.json').read_text())
 shape=json.loads((P/'evidence/full-shape.json').read_text())
 startup=json.loads((P/'startup97e.json').read_text())
 reports=[cpu,shape,startup,down];sources=dict(build['sources'])
 for row in reports:
  assert row['passed'] and row['device_executed'] is False;check_map(ROOT,row['sources']);sources.update(row['sources'])
 assert {(r['view'],r['rank']) for r in shape['runs']}=={(v,r) for v in views() for r in (0,1)}
 assert shape['unsupported_modes_rejected']==21 and len(shape['negative_allocations'])==24 and shape['selection_negatives_rejected']==5
 a=startup['archive'];assert sha(ROOT/a['path'])==a['sha256'];raw=gzip.decompress((ROOT/a['path']).read_bytes());assert hashlib.sha256(raw).hexdigest()==a['uncompressed_sha256']
 runs=json.loads(raw)['runs']
 from startup97e import WINDOWS
 assert {(r['view'],r['window']) for r in runs}=={(v,w) for v in views() for w in WINDOWS}
 assert startup['total_windows']==33
 for r in runs:
  assert r['selected']==selection(r['view']) and r['target_selection_sha256']==sha(P/'selections'/r['view']/'selection.json')
 sources[a['path']]=a['sha256']
 for r in shape['runs']:
  assert r['passed'] and r['selection_key_consumers_verified'] and r['memory']['passed']
  for a in r['artifacts'].values():assert sha(ROOT/a['path'])==a['sha256'];sources[a['path']]=a['sha256']
 extras=[*P.glob('*.py'),P/'placement-policy.json',P/'evidence/micro-retention104b.json',P/'evidence/micro-B/samples.jsonl.gz',P/'evidence/micro-B/kernel-boot-before-review.jsonl.gz',P/'base-memory-plan.json',P/'memory-plan.json',P/'shared-wrapper-pin.json',P/'dependency-pins.json',P/'p104b-parent-selection.json',P/'screening-override.json',P/'build-device-receipt.json',P/'startup97e.json',P/'evidence/cpu-byte-identity.json',P/'evidence/full-shape.json',P/'evidence/python-tests104b.json']
 tests=json.loads((P/'evidence/python-tests104b.json').read_text());assert tests['passed']
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in extras});sources.update(wrapper['sources'])
 assert not any('/ops/' in n or ('packet97-record-bundle' in n and n.endswith(('.json','.log'))) for n in sources), 'mutable parent input'
 check_map(ROOT,sources)
 spec=importlib.util.spec_from_file_location('p104_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 for name in views():
  v=P/'selections'/name;selected=cpu['views'][name]
  assert selected['passed'] and selected['choices']==choices(name)
  assert {(r['compiler'],r['repeat']) for r in selected['runs']}=={(c,r) for c in ('GNU','Intel') for r in (1,2)}
  digests=set()
  for r in selected['runs']:
   assert r['cases']==36 and r['half_patterns']==65536 and r['raw_fp32_chain_checks']>0 and r['raw_fp32_tree_checks']>0
   f=ROOT/r['raw_evidence'];assert sha(f)==r['raw_evidence_sha256'];assert hashlib.sha256(gzip.decompress(f.read_bytes())).hexdigest()==r['candidate_sha256']==r['expected_sha256'];digests.add(r['candidate_sha256']);sources[r['raw_evidence']]=sha(f)
   f=ROOT/r['cases_path'];assert sha(f)==r['cases_sha256'];sources[r['cases_path']]=sha(f)
  assert len(digests)==1
  save(v/'memory-plan.json',plan((name,)));(v/'dispatch-speed6.json').write_bytes((P/'dispatch-speed6.json').read_bytes())
  artifacts={}
  for mode in ('device','gnu-host'):
   src=B/mode/'own-rt-iq3';dest=v/'build'/mode/'own-rt-iq3';dest.parent.mkdir(parents=True,exist_ok=True)
   if not dest.exists():os.link(src,dest)
   assert sha(src)==sha(dest);artifacts[str(dest.relative_to(v))]=sha(dest)
  fixture=ROOT/selected['runs'][0]['raw_evidence']
  for n in ('expected','actual'):(v/('fixture-'+n+'.bin.gz')).write_bytes(fixture.read_bytes())
  audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],draft_prefix_rows=91392,rank0_private_prefix_bytes=0,target_head='production',rank1_separate_expanded_prefix_bytes=0,dispatch_sha256=sha(v/'dispatch-speed6.json'),binary_sha256=artifacts['build/device/own-rt-iq3'],engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','native_controller.hpp','p100_down.hpp','p104iq2.hpp','p104iq2hc.hpp','p49d_expert_submit.cpp')},memory_sources=shape['sources'])
  save(v/'placement-audit.json',audit);bound=dict(sources);bound[str((v/'placement-audit.json').relative_to(ROOT))]=sha(v/'placement-audit.json')
  bp=v/'build-receipt.json';fp=v/'byte-fixture.json';save(bp,dict(passed=True,device_executed=False,sources=bound,artifacts=artifacts))
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='TARGET gate/up tile16 with optional exact FP32 weight half-scale cache; raw GNU/Intel FP32/BF16/status identity; down tile16 composition and all 11 startup windows',command=['python3','-B',str(P/'cpu_gate.py')],build_receipt_sha256=sha(bp),sources=cpu['sources'],raw_runs=selected['runs'],**{k:dict(path='fixture-'+k+'.bin.gz',sha256=sha(v/('fixture-'+k+'.bin.gz'))) for k in ('expected','actual')}))
  generic.create(v,'tp2',bp,fp,v/'build/device/own-rt-iq3',v/'dispatch-speed6.json',v/'screen-seal.json');print(name,'sealed',flush=True)
 job_sources={str(f.relative_to(ROOT)):sha(f) for f in extras}
 for name in views():
  f=P/'selections'/name/'screen-seal.json';job_sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,sources=job_sources,wrapper_seal_sha256=sha(P.parent/'screen/v4-lanes/wrapper-seal.json')))
if __name__=='__main__':main()

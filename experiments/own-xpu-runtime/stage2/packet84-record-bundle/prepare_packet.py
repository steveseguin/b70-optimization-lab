"""Seal a CPU-proven composition on demand without compilation or all-view copies."""
import argparse,gzip,importlib.util,json,os
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices,selection,placements,PLACEMENTS,prefix_rows,name as view_name
from chain_seal import check_map
GATES=('cpu-byte-identity.json','retirement-byte-identity.json','protocol.json','full-shape.json','memory-admission.json','cpu-gates.json')
def proof():
 build=json.loads((P/'build-device-receipt.json').read_text());reports={n:json.loads((P/'evidence'/n).read_text()) for n in GATES}
 for r in (build,*reports.values()):
  assert r['passed'] and r['device_executed'] is False;check_map(ROOT,r['sources'])
 check_map(P,build['artifacts'])
 from bundle_selection import configurations
 assert len(reports['full-shape.json']['runs'])==len(configurations())*2
 assert set(reports['cpu-byte-identity.json']['views'])==set(views())
 sources=dict(build['sources'])
 for r in reports.values():sources.update(r['sources'])
 sources.update(json.loads((P/'dependency-pins.json').read_text()))
 extras=[*P.glob('*.py'),P/'baseline-pins.json',P/'placement-policy.json',P/'dependency-pins.json',P/'selection-template.json',P/'shared-wrapper-pin.json',*[P/'evidence'/n for n in GATES]]
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in extras})
 return build,reports,sources
def seal_view(v,placement):
 from stopped_archive import require_fresh_chain
 require_fresh_chain(B);assert placement in placements(v),'unqualified draft placement'
 from bootstrap import install
 install();build,reports,sources=proof();name=view_name(*v)
 selected=reports['cpu-byte-identity.json']['views'][name];assert selected['choices']==choices(*v)
 assert {(r['compiler'],r['repeat']) for r in selected['runs']}=={(c,n) for c in ('GNU','Intel') for n in (1,2)}
 for r in selected['runs']:
  f=ROOT/r['fixture'];assert sha(f)==r['fixture_sha256'];assert __import__('hashlib').sha256(gzip.decompress(f.read_bytes())).hexdigest()==r['expected_sha256']==r['candidate_sha256']
 view=P/'selections'/(name+'--placement-'+placement);view.mkdir(parents=True,exist_ok=True)
 # Identical selected source proof is reusable; changed cached proof refuses.
 if (view/'screen-seal.json').exists():
  seal=json.loads((view/'screen-seal.json').read_text());check_map(ROOT,seal['sources']);check_map(view,seal['artifacts']);check_map(view,seal['gates']);check_map(view,seal['fixture_files']);return view
 save(view/'selection.json',selection(v))
 from memory_matrix import ledger
 save(view/'memory-plan.json',ledger(v[-1]));(view/'dispatch-speed6.json').write_bytes((P/'dispatch-speed6.json').read_bytes())
 for n in ('device','gnu-host'):
  dest=view/'build'/n/'own-rt-iq3';dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists():os.link(B/n/'own-rt-iq3',dest)
 fixture=ROOT/selected['runs'][0]['fixture']
 for n in ('expected','actual'):
  dest=view/('fixture-'+n+'.bin.gz')
  if not dest.exists():os.link(fixture,dest)
 rank,split,boundary=PLACEMENTS[placement]
 audit=dict(placement=placement,draft_rank=rank,target_split=split,layer_boundary=boundary,target_layers=[boundary,48-boundary],draft_prefix_rows=prefix_rows(v[-1]),rank0_private_prefix_bytes=308904960 if rank==0 else 0,dispatch_sha256=sha(view/'dispatch-speed6.json'),binary_sha256=sha(view/'build/device/own-rt-iq3'),engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','native_controller.hpp','p56_config.hpp','p56_prefix.hpp')},memory_sources=reports['memory-admission.json']['sources'])
 save(view/'placement-audit.json',audit);sources[str((view/'placement-audit.json').relative_to(ROOT))]=sha(view/'placement-audit.json')
 bp=view/'build-receipt.json';fp=view/'byte-fixture.json';save(bp,dict(passed=True,device_executed=False,sources=sources,artifacts=build['artifacts']))
 save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,build_receipt_sha256=sha(bp),sources=reports['cpu-byte-identity.json']['sources'],changed_class='Independent selected operator byte transcripts under GNU/Intel twice; full composition operation capture and allocation census; draft Q4 scalar-reference arithmetic only, target unchanged.',command=['python3','-B',str(P/'operator_matrix.py')],**{k:dict(path='fixture-'+k+'.bin.gz',sha256=sha(view/('fixture-'+k+'.bin.gz'))) for k in ('expected','actual')}))
 spec=importlib.util.spec_from_file_location('packet84_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 generic.create(view,'tp2',bp,fp,view/'build/device/own-rt-iq3',view/'dispatch-speed6.json',view/'screen-seal.json')
 save(P/'cpu-validation.json',dict(passed=True,device_executed=False,cpu_model_executed=False,files={str((P/'evidence'/n).relative_to(ROOT)):sha(P/'evidence'/n) for n in GATES}))
 return view
def main():
 limits();base=json.loads((P/'baseline-pins.json').read_text())['selection']
 from bundle_selection import KEYS
 seal_view(tuple(base[k] for k in KEYS),base['placement']);print('Baseline sealed; other admitted compositions seal on demand')
if __name__=='__main__':main()

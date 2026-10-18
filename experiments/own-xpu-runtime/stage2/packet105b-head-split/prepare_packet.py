"""Seal three views only after byte, mock, every-window and allocation gates."""
import importlib.util,json,os
from build_engine import P,ROOT,sha,save,limits,provenance,check_map
from bundle_selection import aliases,name,selection
from memory_plans import plan
def main():
 limits();build=provenance();sources=dict(build['sources'])
 reports={leaf:json.loads((P/leaf).read_text()) for leaf in ('evidence/reset-regression.json','evidence/cpu-byte-identity.json','evidence/full-shape.json','evidence/runtime-mock.json','evidence/controller.json','startup97e.json')}
 for leaf,r in reports.items():
  assert r['passed'] and r['device_executed'] is False,leaf
  check_map(ROOT,r['sources']);sources.update(r['sources']);sources[str((P/leaf).relative_to(ROOT))]=sha(P/leaf)
 from startup_receipt97e import verify as verify_startup
 verify_startup()
 startup=reports['startup97e.json'];assert startup['compositions']==2 and startup['windows_per_composition']==11 and startup['total_windows']==22
 archive=startup['archive'];assert sha(ROOT/archive['path'])==archive['sha256'];sources[archive['path']]=archive['sha256']
 shape=reports['evidence/full-shape.json'];assert len(shape['runs'])==4
 for r in shape['runs']:
  assert r['passed'] and r['memory']['passed']
  for artifact in r['artifacts'].values():sources[artifact['path']]=artifact['sha256']
 gates=reports['evidence/cpu-byte-identity.json']['runs'];assert {(r['compiler'],r['repeat']) for r in gates}=={(c,r) for c in ('GNU','Intel') for r in (1,2)};assert len({r['candidate_sha256'] for r in gates})==1
 sources.update(json.loads((P/'dependency-pins.json').read_text()))
 for f in [*[P/n for n in ('prepare_packet.py','startup_receipt97e.py','placement.py','bootstrap.py','screen_seal_support.py')],P/'copy-lineage.json',P/'placement-policy.json',P/'shared-wrapper-pin.json',P/'selection-template.json',P/'build-device-receipt.json']:sources[str(f.relative_to(ROOT))]=sha(f)
 # Parent composition outputs change while chains run. No seal binds them.
 forbidden=('bundle-selection.json','selection-dry-run.json','composition-selection.json','/ops/')
 assert not any('packet105b-head-split' not in n and any(k in n for k in forbidden) for n in sources)
 for f in [*(P/'build/input').glob('*'),P.parent/'suite-inputs-20261012/code-review/plan.tsv',*[P/n for n in ('kernel-registry.json','k2-class-registry.json','extension-slots.json','runtime-revision.json','chain-registration.json','base-memory-plan.json')]]:
  if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 check_map(ROOT,sources)
 from bootstrap import install
 install();spec=importlib.util.spec_from_file_location('p105_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 fixture=gates[0]
 for label,v in aliases().items():
  view=P/'selections'/label;view.mkdir(parents=True,exist_ok=True);assert not (view/'screen-seal.json').exists(),'sealed views immutable'
  save(view/'selection.json',selection(v));save(view/'memory-plan.json',plan(v));(view/'dispatch-speed6.json').write_bytes((P/'dispatch-speed6.json').read_bytes())
  artifacts={}
  for mode in ('device','gnu-host'):
   dest=view/'build'/mode/'own-rt-iq3';dest.parent.mkdir(parents=True,exist_ok=True)
   if not dest.exists():os.link(P/'build'/mode/'own-rt-iq3',dest)
   artifacts[str(dest.relative_to(view))]=sha(dest)
  split=label!='production'
  audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],draft_prefix_rows=91392,rank0_private_prefix_bytes=0,target_head=label,
    rank0_target_suffix_rows=46080 if split else 0,rank1_target_rows=202240 if split else 248320,rank0_suffix_weight_bytes=155750400 if split else 0,
    target_hidden_source='verified normalized final.mix only',transfer_placement='bcs' if label.endswith('bcs') else 'compute',
    dispatch_sha256=sha(view/'dispatch-speed6.json'),binary_sha256=artifacts['build/device/own-rt-iq3'],
    engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','native_controller.hpp','p105_runtime.hpp','p105_common.hpp','single_device.cpp','strict_snapshot.hpp')},memory_sources=shape['sources'],startup_view=name(*v))
  save(view/'placement-audit.json',audit);bound=dict(sources);bound[str((view/'placement-audit.json').relative_to(ROOT))]=sha(view/'placement-audit.json')
  for leaf in ('expected','actual'):(view/('fixture-'+leaf+'.bin.gz')).write_bytes((ROOT/fixture['fixture']).read_bytes())
  bp=view/'build-receipt.json';fp=view/'byte-fixture.json';save(bp,dict(passed=True,device_executed=False,sources=bound,artifacts=artifacts))
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,build_receipt_sha256=sha(bp),sources=reports['evidence/cpu-byte-identity.json']['sources'],changed_class='Exact p33 target rows and BF16 logits; round2 argmax with global ties, nonfinite refusal. GNU/Intel repeated full vocabulary. Actual Runtime and native-controller mock gates separately bound.',command=['python3','-B',str(P/'cpu_gate.py')],**{k:dict(path='fixture-'+k+'.bin.gz',sha256=sha(view/('fixture-'+k+'.bin.gz'))) for k in ('expected','actual')}))
  generic.create(view,'tp2',bp,fp,view/'build/device/own-rt-iq3',view/'dispatch-speed6.json',view/'screen-seal.json');print(label,'sealed',flush=True)
if __name__=='__main__':main()

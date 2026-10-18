"""Seal bundle9 from exact frozen packet137 CPU proofs, no build or device."""
import json,os,shutil,subprocess,sys,importlib.util
from pathlib import Path
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
def main():
 from build_engine import limits
 limits()
 from source_decision import main as decision,selections
 decision()
 upstream=P.with_name('packet137-token-input')
 cp=subprocess.run([sys.executable,'-B',str(upstream/'v5/cpu_seal.py')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
 assert cp.returncode==0,cp.stderr
 save(O/'evidence/upstream-cpu-verification.json',dict(passed=True,device_executed=False,command=cp.args,seal_sha256=sha(upstream/'v5/lineage/screen-seal.json'),reused_unchanged=True))
 from reuse_build import verify_native
 native=verify_native()
 from bundle_selection import aliases,selection,KEYS,name
 values=aliases()['both'];assert selection(values)==json.loads((P/'selection.json').read_text())
 view=P/'selections/bundle9-token-both--placement-1';view.mkdir(parents=True,exist_ok=True)
 for leaf in ('selection.json','memory-plan.json','dispatch-speed6.json'):shutil.copyfile(P/leaf,view/leaf)
 sources=dict(native['sources']);sources.update(json.loads((P/'startup103.json').read_text())['sources'])
 # Only safe logical paths enter source maps. External legacy links remain independently verified.
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in P.glob('*.py')})
 for f in (P/'copy139.json',P/'token-input-selection.json',P/'native-reuse.json',P/'startup103.json',P/'placement-policy.json',P/'PREREGISTRATION.md',O/'inputs/external-source-bindings.json',O/'inputs/symlink-audit.json'):
  sources[str(f.relative_to(ROOT))]=sha(f)
 sources={n:h for n,h in sources.items() if '/oracle/' not in n and (ROOT/n).resolve().is_relative_to(ROOT)}
 artifacts={}
 for mode in ('device','gnu-host'):
  dest=view/'build'/mode/'own-rt-iq3';dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists():os.link(P/'build'/mode/'own-rt-iq3',dest)
  artifacts[str(dest.relative_to(view))]=sha(dest)
 state=json.loads((upstream/'v5/evidence/state-regression.json').read_text());assert len({r['canonical_sha256'] for r in state['runs']})==1
 transcript=ROOT/state['runs'][0]['archive'];assert sha(transcript)==state['runs'][0]['archive_sha256']
 for label in ('expected','actual'):shutil.copyfile(transcript,view/('fixture-'+label+'.bin.gz'))
 audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],draft_prefix_rows=80128,rank0_private_prefix_bytes=0,target_head='head-split-compute',rank1_separate_expanded_prefix_bytes=0,dispatch_sha256=sha(view/'dispatch-speed6.json'),binary_sha256=artifacts['build/device/own-rt-iq3'],engine_sources={str(f.relative_to(ROOT)):sha(f) for f in [*(upstream/'v5/native-src').glob('*'),*(upstream/'v5/native').glob('*'),*(upstream/n for n in ('native_controller.hpp','p56_config.hpp','p56_prefix.hpp'))] if f.is_file()},memory_sources=json.loads((P/'startup103.json').read_text())['sources'])
 save(view/'placement-audit.json',audit);sources[str((view/'placement-audit.json').relative_to(ROOT))]=sha(view/'placement-audit.json')
 save(view/'build-receipt.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts))
 save(view/'byte-fixture.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,reused_unchanged=True,build_receipt_sha256=sha(view/'build-receipt.json'),sources={str((upstream/'v5/evidence/state-regression.json').relative_to(ROOT)):sha(upstream/'v5/evidence/state-regression.json')},changed_class='Byte-identical packet137 both engine: GNU/Intel original/both 491-case cancellation/redo canonical transcripts; frozen full table, target and production-shape proofs bound by source closure.',command=['python3','-B',str(upstream/'v5/cpu_seal.py')],**{k:dict(path='fixture-'+k+'.bin.gz',sha256=sha(view/('fixture-'+k+'.bin.gz'))) for k in ('expected','actual')}))
 from bootstrap import install
 install()
 spec=importlib.util.spec_from_file_location('p139_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 # Only this new, unlaunched packet is resealed during CPU preparation.
 (view/'screen-seal.json').unlink(missing_ok=True)
 generic.create(view,'tp2',view/'build-receipt.json',view/'byte-fixture.json',view/'build/device/own-rt-iq3',view/'dispatch-speed6.json',view/'screen-seal.json')
 save(P/'bundle-selection.json',dict(selections()[1],name=name(*values),placement='1',draft='draft-hc',miss='banks-batch',draft_rank=1,target_split=0,layer_boundary=24,selection_sha256=sha(P/'selection.json'),screen_seal_sha256=sha(view/'screen-seal.json')))
 shutil.copyfile(view/'screen-seal.json',P/'screen-seal.json')
 save(P/'cpu-validation.json',dict(passed=True,device_executed=False,cpu_model_executed=False,reused_unchanged=True,files={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('native-reuse.json','startup103.json')}))
 from chain_adapter import install as chain_install
 chain_install()
 from chain_seal import checked,verify
 save(P/'build-receipt.json',checked())
 from packet56_submission import pin_resealed_packet56
 pin_resealed_packet56();verify()
 print('bundle9 selection, native identity and chain sealed; no device evidence inherited')
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()

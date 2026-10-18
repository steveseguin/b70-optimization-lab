"""Seal just the diagnostic view after actual CPU build, bytes and shape checks."""
import importlib.util,json,os,shutil,sys
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
V=P/'selections/acceptance'
def main():
 limits();build=json.loads((P/'build-device-receipt.json').read_text());cpu=json.loads((P/'evidence/cpu-gates.json').read_text());shape=json.loads((P/'evidence/full-shape.json').read_text())
 assert build['passed'] and cpu['passed'] and shape['passed']
 assert len(shape['runs'])==2 and {r['rank'] for r in shape['runs']}=={0,1}
 sources=dict(build['sources']);sources.update(cpu['sources']);sources.update(shape['sources'])
 for name in ('format-gate.json','reset-gate.json'):
  gate=json.loads((P/'evidence'/name).read_text());assert gate['passed'] and not gate['device_executed'];sources.update(gate['sources'])
 for n in ('cpu-gates.json','full-shape.json','reset-gate.json','format-gate.json'):sources[str((P/'evidence'/n).relative_to(ROOT))]=sha(P/'evidence'/n)
 for f in P.glob('*.py'):sources[str(f.relative_to(ROOT))]=sha(f)
 for n in ('placement-policy.json','parent-manifest.json','dependency-pins.json','preregistration.json'):sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 sources[str((P/'calibration/inputs.json').relative_to(ROOT))]=sha(P/'calibration/inputs.json')
 sources.update(json.loads((P/'dependency-pins.json').read_text()))
 V.mkdir(parents=True,exist_ok=True)
 for n in ('selection.json','memory-plan.json','dispatch-speed6.json'):shutil.copyfile(P/n,V/n)
 artifacts={}
 for mode in ('gnu-host','device'):
  f=V/f'build/{mode}/own-rt-iq3';f.parent.mkdir(parents=True,exist_ok=True)
  if f.exists() and sha(f)!=build['artifacts'][f'build/{mode}/own-rt-iq3']:
   assert '--reseal' in sys.argv
   f.unlink()
  if not f.exists():os.link(B/mode/'own-rt-iq3',f)
  assert sha(f)==build['artifacts'][f'build/{mode}/own-rt-iq3'];artifacts[str(f.relative_to(V))]=sha(f)
 for mode in ('expected','actual'):shutil.copyfile(P/f'evidence/fixture-{mode}.bin',V/f'fixture-{mode}.bin')
 audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],draft_prefix_rows=80128,rank0_private_prefix_bytes=0,
  dispatch_sha256=sha(V/'dispatch-speed6.json'),binary_sha256=sha(V/'build/device/own-rt-iq3'),engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','p105_runtime.hpp','strict_snapshot.hpp','p129_fp8.hpp')},memory_sources=shape['sources'])
 save(V/'placement-audit.json',audit);sources[str((V/'placement-audit.json').relative_to(ROOT))]=sha(V/'placement-audit.json')
 save(V/'build-receipt.json',dict(passed=True,device_executed=False,sources=sources,artifacts=artifacts))
 save(V/'byte-fixture.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,build_receipt_sha256=sha(V/'build-receipt.json'),sources=cpu['sources'],changed_class='Production-driven FP8 expert shadow acceptance diagnostic. Miniature CPU target/draft/repeat bytes; unchanged arithmetic object hashes and full production startup census. Device exactness pending.',command=['python3','-B',str(P/'cpu_gate.py')],**{k:dict(path=f'fixture-{k}.bin',sha256=sha(V/f'fixture-{k}.bin')) for k in ('actual','expected')}))
 from bootstrap import install
 install()
 spec=importlib.util.spec_from_file_location('generic_seal',P.parent/'screen/seal.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 if (V/'screen-seal.json').exists():
  assert '--reseal' in sys.argv,'explicit local reseal required'
  (V/'screen-seal.json').unlink()
 module.create(V,'tp2',V/'build-receipt.json',V/'byte-fixture.json',V/'build/device/own-rt-iq3',V/'dispatch-speed6.json',V/'screen-seal.json')
 seal=json.loads((V/'screen-seal.json').read_text());seal['timing_modes']=['token'];save(V/'screen-seal.json',seal)
 print('diagnostic view sealed',flush=True)
if __name__=='__main__':main()

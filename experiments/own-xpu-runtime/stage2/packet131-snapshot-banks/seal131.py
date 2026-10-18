"""New screen seals; inherited historical receipts are never admission evidence."""
import gzip,importlib.util,json,os,shutil
from build131 import P,ROOT,B,sha,save,cpu_main,limits
def main():
 build=json.loads((P/'build-device-receipt.json').read_text())
 state=json.loads((P/'evidence/state131.json').read_text());shape=json.loads((P/'evidence/census131.json').read_text())
 reset=json.loads((P/'evidence/reset-regression.json').read_text())
 assert build['passed'] and state['passed'] and shape['passed'] and reset['passed']
 assert len(state['runs'])==8 and len({r['canonical_sha256'] for r in state['runs']})==1
 sources=dict(build['sources'])
 for report in (state,shape,reset):sources.update(report['sources'])
 for name in ('state131.json','census131.json','reset-regression.json'):sources[str((P/'evidence'/name).relative_to(ROOT))]=sha(P/'evidence'/name)
 for f in [*P.glob('*.py'),P/'placement-policy.json',P/'copy131.json',P/'dependency-pins.json',P/'shared-wrapper-pin.json']:
  sources[str(f.relative_to(ROOT))]=sha(f)
 sources.update(json.loads((P/'dependency-pins.json').read_text()))
 from bootstrap import install
 install()
 spec=importlib.util.spec_from_file_location('p131_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 for label in ('control','candidate'):
  v=P/'selections'/label
  for n in ('memory-plan.json','dispatch-speed6.json'):shutil.copyfile(P/n,v/n)
  artifacts={}
  for mode in ('gnu-host','device'):
   f=v/f'build/{mode}/own-rt-iq3';f.parent.mkdir(parents=True,exist_ok=True)
   if not f.exists():os.link(B/mode/'own-rt-iq3',f)
   assert sha(f)==build['artifacts'][f'build/{mode}/own-rt-iq3'];artifacts[str(f.relative_to(v))]=sha(f)
  for key,choice in (('expected','control'),('actual',label)):
   row=next(r for r in state['runs'] if r['compiler']=='GNU' and r['repeat']==1 and r['view']==choice)
   shutil.copyfile(ROOT/row['artifact'],v/f'fixture-{key}.txt.gz')
  audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],draft_prefix_rows=80128,rank0_private_prefix_bytes=0,
   dispatch_sha256=sha(v/'dispatch-speed6.json'),binary_sha256=sha(v/'build/device/own-rt-iq3'),engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','p105_runtime.hpp','strict_snapshot.hpp','p49d_submit.cpp')},memory_sources=shape['sources'])
  save(v/'placement-audit.json',audit);local_sources=dict(sources);local_sources[str((v/'placement-audit.json').relative_to(ROOT))]=sha(v/'placement-audit.json')
  save(v/'build-receipt.json',dict(passed=True,device_executed=False,sources=local_sources,artifacts=artifacts))
  save(v/'byte-fixture.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,build_receipt_sha256=sha(v/'build-receipt.json'),sources=state['sources'],changed_class='Speculative GDN/conv destination bank rotation: all logical committed/spare bytes and full nonbank bytes at every forced hit/miss/cancel/fallback; GNU/Intel CPU. Full model device equality pending.',command=['python3','-B',str(P/'state131.py')],**{k:dict(path=f'fixture-{k}.txt.gz',sha256=sha(v/f'fixture-{k}.txt.gz')) for k in ('expected','actual')}))
  generic.create(v,'tp2',v/'build-receipt.json',v/'byte-fixture.json',v/'build/device/own-rt-iq3',v/'dispatch-speed6.json',v/'screen-seal.json')
  print(label,'sealed',flush=True)
if __name__=='__main__':cpu_main();main()

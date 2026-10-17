"""Seal outputs-unchanged observation after small CPU gates; no model runs."""
import json,os,subprocess,sys,shutil
from pathlib import Path
from build_engine import P,ROOT,BASE,limits,sha,save

def main():
 limits();V=P/'screen/attr';dest=P/'selections/1-production-control'
 assert not dest.exists(),'immutable selection'
 build=json.loads((P/'build-device-receipt.json').read_text());gate=json.loads((P/'evidence/observer-gate.json').read_text());assert gate['passed']
 for name,digest in build['sources'].items():assert sha(ROOT/name)==digest,name
 sources=dict(build['sources'])
 for f in [*P.glob('*.py'),P/'evidence/observer-gate.json',P/'build-device-receipt.json',P/'evidence/existing-analysis.json']:
  sources[str(f.relative_to(ROOT))]=sha(f)
 dest.mkdir(parents=True)
 for name in ('selection.json','selection-decision.json','memory-plan.json','dispatch-speed6.json'):
  shutil.copyfile(P/name,dest/name)
 # Explicit control view from packet64-attribution, never current packet64 default.
 assert json.loads((dest/'selection.json').read_text())['choices']['miss']=='control'
 binary=dest/'build/device/own-rt-iq3';binary.parent.mkdir(parents=True);os.link(P/'build/device/own-rt-iq3',binary)
 audit=dict(placement='1',draft_rank=1,target_split=0,binary_sha256=sha(binary),dispatch_sha256=sha(dest/'dispatch-speed6.json'),
   engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','attribution.hpp')},rationale='packet64 production control, extra observation sites only')
 save(dest/'placement-audit.json',audit)
 plan=json.loads((P.parent/'packet64-attribution/selections/1-production-control/attribution-plan.json').read_text())
 plan.update(schema='packet69.attribution.plan.v1',outside_sites=['logits','final.*','argmax','transfer.*'],expected_work_seconds=420)
 save(dest/'attribution-plan.json',plan)
 for f in dest.glob('*.json'):sources[str(f.relative_to(ROOT))]=sha(f)
 for key in ('expected','actual'):shutil.copyfile(P/'evidence'/('fixture-'+key+'.bin'),dest/('fixture-'+key+'.bin'))
 save(dest/'build-receipt.json',dict(passed=True,device_executed=False,sources=sources,artifacts={'build/device/own-rt-iq3':sha(binary)}))
 save(dest/'fixture.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
   build_receipt_sha256=sha(dest/'build-receipt.json'),sources={str((P/'observation_gate.py').relative_to(ROOT)):sha(P/'observation_gate.py')},
   changed_class=gate['scope'],command=[sys.executable,'-B',str(P/'observation_gate.py')],
   **{k:dict(path='fixture-'+k+'.bin',sha256=sha(dest/('fixture-'+k+'.bin'))) for k in ('expected','actual')}))
 subprocess.run([sys.executable,'-B',str(P.parent/'screen/seal.py'),'--profile','tp2','--lineage',str(dest),'--build-receipt',str(dest/'build-receipt.json'),'--fixture',str(dest/'fixture.json'),'--binary',str(binary),'--dispatch',str(dest/'dispatch-speed6.json'),'--output',str(dest/'screen-seal.json')],check=True,stdin=subprocess.DEVNULL)
 seal=json.loads((dest/'screen-seal.json').read_text());seal.update(timing_modes=['attribution'],attribution_plan=plan);save(dest/'screen-seal.json',seal)
 # Gate actual relocated wrapper and plan, before its first seal is issued.
 with (P/'evidence/measurement-tests.log').open('w') as log:
  subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(V),'-p','test_*.py','-v'],check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 prior=json.loads((P.parent/'screen/v3-attr/placement-validation/wrapper-seal.json').read_text())
 closure={n:sha(ROOT/n) for n in prior['sources']}
 for f in [*V.glob('*.py'),*V.glob('*.json'),P/'outside.py',P/'summarize.py',P/'timeline.py']:
  if f.name=='wrapper-seal.json':continue
  closure[str(f.relative_to(ROOT))]=sha(f)
 save(V/'wrapper-seal.json',dict(passed=True,device_executed=False,sources=closure,tests_sha256=sha(P/'evidence/measurement-tests.log'),release_before_reporting=True))
 cmd=[sys.executable,'-B',str(V/'screen.py'),'--profile','tp2','--lane','B','--placement','1','--timing','attribution','--lineage',str(dest),'--seal',str(dest/'screen-seal.json'),'--output',str(V/'evidence/p69-attribution-B-a'),'--plan']
 with (P/'evidence/measurement-plan-B.json').open('w') as log:subprocess.run(cmd,check=True,stdin=subprocess.DEVNULL,stdout=log)
 print('measurement sealed; no device execution',sha(dest/'screen-seal.json'))
if __name__=='__main__':main()

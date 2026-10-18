"""Issue immutable per-site views after operator-byte and parser gates."""
import json,subprocess,sys,shutil,os
from build_engine import P,ROOT,BASE,limits,sha,save
from selections import CHOICES

def main():
 limits();build=json.loads((P/'build-device-receipt.json').read_text())
 gates=[json.loads((P/'evidence'/n).read_text()) for n in ('cpu-gates.json','selection-gate.json')]
 assert all(g['passed'] and not g['cpu_model_executed'] and not g['device_executed'] for g in gates)
 sources=dict(build['sources'])
 for gate in gates:sources.update(gate['sources'])
 for n,h in sources.items():assert sha(ROOT/n)==h,n
 for f in [P/'build-device-receipt.json',P/'seal_candidates.py',P/'selections.py',P/'evidence/cpu-gates.json',P/'evidence/selection-gate.json']:
  sources[str(f.relative_to(ROOT))]=sha(f)
 for choice in CHOICES:
  dest=P/'selections'/choice;assert not (dest/'screen-seal.json').exists()
  for n in ('memory-plan.json','dispatch-speed6.json'):shutil.copyfile(P/n,dest/n)
  binary=dest/'build/device/own-rt-iq3';binary.parent.mkdir(parents=True,exist_ok=True);os.link(P/'build/device/own-rt-iq3',binary)
  for key,name in [('expected','p69_fixture-gnu-1.bin'),('actual','p69_fixture-gnu-1.actual.bin')]:shutil.copyfile(P/'evidence'/name,dest/('fixture-'+key+'.bin'))
  audit=dict(placement='1',draft_rank=1,target_split=0,binary_sha256=sha(binary),dispatch_sha256=sha(dest/'dispatch-speed6.json'),
    engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','p49d_submit.hpp','p49d_submit.cpp','p69_head.hpp','p69_head.cpp')},
    rationale='packet64 production 24/24 with explicit independent site choices; unchanged target arithmetic, full BF16 KV and original prefix')
  save(dest/'placement-audit.json',audit)
  bound=dict(sources)
  for f in dest.glob('*.json'):bound[str(f.relative_to(ROOT))]=sha(f)
  save(dest/'build-receipt.json',dict(passed=True,device_executed=False,sources=bound,artifacts={'build/device/own-rt-iq3':sha(binary)}))
  save(dest/'fixture.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
    build_receipt_sha256=sha(dest/'build-receipt.json'),sources=gates[0]['sources'],
    changed_class='head wider loads and independent rows: production FP32/BF16 exact; draft split32/HC deterministic (operator checks only)',
    command=[sys.executable,'-B',str(P/'cpu_gate.py')],
    **{k:dict(path='fixture-'+k+'.bin',sha256=sha(dest/('fixture-'+k+'.bin'))) for k in ('expected','actual')}))
  subprocess.run([sys.executable,'-B',str(P.parents[1]/'screen/seal.py'),'--profile','tp2','--lineage',str(dest),'--build-receipt',str(dest/'build-receipt.json'),'--fixture',str(dest/'fixture.json'),'--binary',str(binary),'--dispatch',str(dest/'dispatch-speed6.json'),'--output',str(dest/'screen-seal.json')],check=True,stdin=subprocess.DEVNULL)
 print('PASS seven candidate seals; default production; GPU unmeasured')
if __name__=='__main__':main()

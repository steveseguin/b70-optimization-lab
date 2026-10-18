"""Seal only the micro executable inputs; analysis can be refreshed independently."""
import json
from build_engine import P,ROOT,sha,save,limits
def main():
 limits()
 for mode in ('gnu-host','intel-host','device'):
  r=json.loads((P/'evidence'/('build-'+mode+'.json')).read_text());assert r['passed'] and not r['device_executed']
  for group,base in [('sources',ROOT),('objects',ROOT),('artifacts',P)]:
   for n,h in r[group].items():assert sha(base/n)==h,n
 assert json.loads((P/'evidence/cpu-layers.json').read_text())['passed']
 assert json.loads((P/'evidence/cpu-leaf.json').read_text())['passed']
 names=['qualification.py','test_gate.py','recurrence_cases.hpp','p113_recurrence.hpp','cpu_leaf.py','evidence/cpu-leaf.json','run_micro.py','cpu_layers.py','build_engine.py','compile_turn.py','layer_bench.cpp','dispatch-speed6.json','selection.json','rope.bf16','shared-wrapper-pin.json','evidence/cpu-layers.json']
 names += [str(x.relative_to(P)) for pattern in ('leaf-v2-*/*','full-*/*') for x in (P/'evidence').glob(pattern) if x.is_file()]
 save(P/'seal.json',dict(schema='packet113.row-gdn.v1',passed=True,device_executed=False,admitted_modes=['current','specialized'],admitted_layers=[4],files={n:sha(P/n) for n in names},runtime_inputs={str((P.parent/'packet34-replay-bench/directory.tsv').relative_to(ROOT)):sha(P.parent/'packet34-replay-bench/directory.tsv')}))
 print('sealed packet113 micro only; runtime integration gated')
if __name__=='__main__':main()

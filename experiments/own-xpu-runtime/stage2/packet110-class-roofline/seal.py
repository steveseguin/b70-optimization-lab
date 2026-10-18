"""Seal only the micro executable inputs; analysis can be refreshed independently."""
import json
from build_engine import P,ROOT,sha,save,limits
def main():
 limits()
 for mode in ('gnu-host','device'):
  r=json.loads((P/'evidence'/('build-'+mode+'.json')).read_text());assert r['passed'] and not r['device_executed']
  for group,base in [('sources',ROOT),('objects',ROOT),('artifacts',P)]:
   for n,h in r[group].items():assert sha(base/n)==h,n
 assert json.loads((P/'evidence/cpu-layers.json').read_text())['passed']
 names=['run_micro.py','cpu_layers.py','build_engine.py','compile_turn.py','layer_bench.cpp','dispatch-speed6.json','selection.json','rope.bf16','shared-wrapper-pin.json','evidence/cpu-layers.json']
 save(P/'seal.json',dict(schema='packet110.current-gdn.v1',passed=True,device_executed=False,admitted_modes=['current'],admitted_layers=[4],files={n:sha(P/n) for n in names},runtime_inputs={str((P.parent/'packet34-replay-bench/directory.tsv').relative_to(ROOT)):sha(P.parent/'packet34-replay-bench/directory.tsv')}))
 print('sealed current GDN only')
if __name__=='__main__':main()

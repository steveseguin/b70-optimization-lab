"""Bind micro code, CPU evidence, runtime fixture bytes and packet94 compile policy."""
import json
from build_engine import P,ROOT,sha,save,limits
def main():
 limits()
 for mode in ('gnu-host','intel-host','device'):
  r=json.loads((P/'evidence'/('build-'+mode+'.json')).read_text());assert r['passed'] and not r['device_executed']
  for group,base in [('sources',ROOT),('objects',ROOT),('artifacts',P)]:
   for n,h in r[group].items():assert sha(base/n)==h,n
 from leaf_gate import verify
 verify()
 assert json.loads((P/'evidence/cpu-layers.json').read_text())['passed']
 names=['run_micro.py','leaf_gate.py','qualification.py','cpu_layers.py','build_engine.py','layer_bench.cpp','fixture_bytes.hpp','dispatch-speed6.json','selection.json','shared-wrapper-pin.json','evidence/cpu-layers.json']
 runtime=[P.parents[1]/'packet34-replay-bench/directory.tsv',P.parents[1]/'packet94-hc-norm-fusion/compile_turn.py',P.parent/'evidence/cpu-leaf.json',P.parents[1]/'packet110-class-roofline/rope.bf16']
 assert (P/'rope.bf16').is_symlink() and str((P/'rope.bf16').readlink())=='../../packet110-class-roofline/rope.bf16'
 save(P/'seal.json',dict(schema='packet116.qsa-micro.v1',passed=True,device_executed=False,admitted_modes=['production','p116'],admitted_layers=[3],files={n:sha(P/n) for n in names},runtime_inputs={str(f.relative_to(ROOT)):sha(f) for f in runtime}))
 print('sealed QSA production/p116 micro')
if __name__=='__main__':main()

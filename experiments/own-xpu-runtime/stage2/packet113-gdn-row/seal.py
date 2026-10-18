"""Seal only the micro executable inputs; analysis can be refreshed independently."""
import json
from build_engine import P,ROOT,sha,save,limits
def main():
 limits()
 for mode in ('gnu-host','intel-host','device'):
  r=json.loads((P/'evidence'/('build-'+mode+'.json')).read_text());assert r['passed'] and not r['device_executed']
  for group,base in [('sources',ROOT),('objects',ROOT),('artifacts',P)]:
   for n,h in r[group].items():assert sha(base/n)==h,n
 cpu=json.loads((P/'evidence/cpu-layers.json').read_text());assert cpu['passed'] and not cpu['device_executed']
 assert [(r['compiler'],r['repeat']) for r in cpu['records']]==[(c,i) for c in ('gnu-host','intel-host') for i in (1,2)]
 for r in cpu['records']:
  assert sha(P/r['receipt'])==r['receipt_sha256'] and sha(P/r['invocation'])==r['invocation_sha256']
  invocation=json.loads((P/r['invocation']).read_text());build=P/'evidence'/('build-'+r['compiler']+'.json')
  assert invocation['binary_sha256']==r['binary_sha256']==sha(P/'build'/r['compiler']/'layer-bench')
  assert invocation['build_receipt_sha256']==sha(build) and invocation['device_executed'] is False
  directory=(P/r['receipt']).parent
  assert sha(directory/'recurrence-cases.jsonl')==r['recurrence_transcript_sha256']
  assert sha(directory/'comparisons.jsonl')==r['exact_output_identity']
 assert json.loads((P/'evidence/cpu-leaf.json').read_text())['passed']
 names=['seal.py','evidence/build-gnu-host.json','evidence/build-intel-host.json','qualification.py','test_gate.py','recurrence_cases.hpp','p113_recurrence.hpp','cpu_leaf.py','evidence/cpu-leaf.json','run_micro.py','cpu_layers.py','build_engine.py','compile_turn.py','layer_bench.cpp','dispatch-speed6.json','selection.json','rope.bf16','shared-wrapper-pin.json','evidence/cpu-layers.json']
 names += [str(x.relative_to(P)) for pattern in ('leaf-v2-*/*','full-*/*') for x in (P/'evidence').glob(pattern) if x.is_file()]
 save(P/'seal.json',dict(schema='packet113.row-gdn.v1',passed=True,device_executed=False,admitted_modes=['current','specialized'],admitted_layers=[4],files={n:sha(P/n) for n in names},runtime_inputs={str((P.parent/'packet34-replay-bench/directory.tsv').relative_to(ROOT)):sha(P.parent/'packet34-replay-bench/directory.tsv')}))
 print('sealed packet113 micro only; runtime integration gated')
if __name__=='__main__':main()

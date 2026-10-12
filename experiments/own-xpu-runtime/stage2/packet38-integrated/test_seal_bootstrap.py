#!/usr/bin/env python3
"""No-rank seal output/warmup validation mocks; final admission remains separate."""
import argparse,copy,hashlib,json,os,tempfile
from pathlib import Path
from unittest.mock import patch
import seal,suite
P=Path(__file__).resolve().parent

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 prompts=[[2,5,3,7,1],[9,8,7,6,5,4]];tokens=suite.select_warmup(prompts,256,248320)
 warm=dict(passed=True,device_executed=False,excluded_from_timing=True,controller='native',draft='mtp',tokens=[17,18],warmup_selection=dict(schema='packet38.distinct-kernel-warmup.v1',token_ids=tokens,token_sha256=seal.canonical(tokens),prompt_tokens=5,requested_output_tokens=2,completed_output_tokens=2,eos_termination_disabled_only_for_excluded_warmup=True,distinct_from_every_suite_prompt=True,absent_from_every_contiguous_suite_input_span=True,suite_prompt_count=2,complete_reset_before_measured_requests=True))
 def table(row):
  text=json.dumps(row);return {'warmup/receipt.json':dict(text=text,sha256=hashlib.sha256(text.encode()).hexdigest())}
 assert seal.bind_suite_warmup(table(warm),prompts)==table(warm)['warmup/receipt.json']['sha256']
 checks=['current distinct two-output warmup accepted']
 for name,mutation in [
  ('measured warmup refused',lambda r:r.update(excluded_from_timing=False)),
  ('early EOS completion refused',lambda r:r.update(tokens=[248044])),
  ('old suite prompt warmup refused',lambda r:r['warmup_selection'].update(token_ids=prompts[0],token_sha256=seal.canonical(prompts[0]))),
  ('missing EOS warmup rule refused',lambda r:r['warmup_selection'].update(eos_termination_disabled_only_for_excluded_warmup=False)),
  ('missing reset assertion refused',lambda r:r['warmup_selection'].update(complete_reset_before_measured_requests=False))]:
  row=copy.deepcopy(warm);mutation(row)
  try:seal.bind_suite_warmup(table(row),prompts)
  except AssertionError:pass
  else:raise AssertionError(name)
  checks.append(name)
 with tempfile.TemporaryDirectory(prefix='seal-bootstrap-',dir=P/'build') as tmp:
  root=Path(tmp)
  for name in ('build-receipt.json','cpu-tests.json','BINARY-HASHES.md'):(root/name).write_text('prior evidence')
  receipt=dict(passed=True,gate_receipts={'a.json':'a'*64})
  with patch.object(seal,'P',root):seal.write_seal_outputs(receipt,['a.json'],{'host/example':'b'*64},bootstrap=True)
  assert json.loads((root/'build-admission-candidate.json').read_text())==receipt
  assert all((root/name).read_text()=='prior evidence' for name in ('build-receipt.json','cpu-tests.json','BINARY-HASHES.md'))
  checks.append('bootstrap writes candidate only and preserves prior final artifacts')
 record=dict(passed=True,device_executed=False,native_ranks_executed=False,mocked_only=True,checks=checks,dynamic_final_admission_pending=True,source_sha256={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in ['seal.py','suite.py','test_window_seal_admission.py','test_seal_bootstrap.py']})
 (P/'seal-bootstrap-gates.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(passed=True,checks=len(checks))))
if __name__=='__main__':main()

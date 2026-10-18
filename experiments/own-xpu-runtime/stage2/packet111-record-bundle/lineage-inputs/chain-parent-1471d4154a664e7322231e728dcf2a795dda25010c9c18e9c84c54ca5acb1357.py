"""Owner-authorized metadata reseal: no model run, rebuild or device execution.

Existing execution receipts remain archived. Reuse of the three prior host
chains is explicit; new diagnostic coverage is a separate nine-window run.
"""
import json,os
from pathlib import Path
from unittest.mock import patch
import storage,seal45
import hc_fix_campaign as campaign
P=Path(__file__).resolve().parent
E=P/'evidence/minimal-reseal'
ALLOWED={'window.py','draft_window.py','coordinator_cpu_gate.py','coordinator_windows.sh'}
def reuse_chain(chain):
 import coordinator_cpu_gate as c
 assert chain['passed'] and chain['device_executed'] is False
 assert chain['host_binary_sha256']==storage.digest(P/'build/gnu-host/own-rt-iq3')
 seal45.archive_bound(chain['archive'])
 old=chain['source_sha256'];current={n:storage.digest(P/n) for n in old}
 assert {n for n in old if old[n]!=current[n]}<=ALLOWED
 assert json.loads((P/'diagnostic-coordinator-gates.json').read_text())['passed']
 chain=dict(chain,execution_source_sha256=old,source_sha256=current,
  evidence_rebound=True,reuse_reason='Owner 2026-10-15 01:10 UTC: retain existing three host chains; binary unchanged since those executions. Optional diagnostic provenance branch tested separately on one nine-window chain. No new production-decode execution claimed.',
  audit6_gate_sha256=storage.digest(P/'audit6-gates.json'))
 return chain
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
 E.mkdir(parents=True,exist_ok=True);campaign.E=E
 names=['audit6-gates.json','audit6-tests.json','fixture-delta-tests.json','seal45-binding-tests.json','wrapper-merge-tests.json','context-window-gates.json','real-cross-placement-tests.json','real-cross-placement-gates.json','build-receipt.json','cpu-tests.json','window-seal-admission-gates.json','window-seal-binding.json','evidence/storage-admission-fix/admission-audit.json']
 retained=storage.archive_files([P/n for n in names],E/'before-reseal.jsonl.gz')
 (E/'retained.json').write_text(json.dumps(retained,indent=2)+'\n')
 chain=json.loads((P/'wrapper-merge-tests.json').read_text())['coordinator_chains']
 import audit6
 audit6.report() # Revalidate retained sparse census; do not execute its binary.
 campaign.units('audit6-tests',['test_audit6'],['audit6.py','test_audit6.py'])
 campaign.units('fixture-delta-tests',['test_fixture_delta'],['fixture_delta.py','test_fixture_delta.py'])
 import admission_audit
 admission_audit.main()
 for name in ('wrapper-merge-tests.json','context-window-gates.json'):
  row=json.loads((P/name).read_text());old=row['sources']
  current={n:storage.digest(P/n) for n in old}
  assert {n for n in old if old[n]!=current[n]}<=ALLOWED
  row.update(execution_sources=old,sources=current,evidence_rebound=True,
   reuse_reason='Existing wrapper mock tests and three chains retained by owner direction; new diagnostic provenance path has separate 14-test and nine-window receipts. No rerun claimed.',
   admission_audit_sha256=storage.digest(P/'evidence/storage-admission-fix/admission-audit.json'),
   coordinator_chains=reuse_chain(chain))
  (P/name).write_text(json.dumps(row,indent=2)+'\n')
 # These test retained-state comparisons and seal tamper rejection only.
 for script in ('test_real_cross_placement_gate.py','real_cross_placement_gate.py','test_seal45_bindings.py'):
  campaign.py(script[:-3],script)
 seal45.main()
 campaign.py('window-admission','test_window_seal_admission.py')
 seal45.verify_window_admission()
 print('PASS metadata reseal; zero new real-model cases, zero compiler/sanitizer rebuilds')
if __name__=='__main__':main()

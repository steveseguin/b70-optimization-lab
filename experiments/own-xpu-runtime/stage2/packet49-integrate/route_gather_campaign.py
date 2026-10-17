#!/usr/bin/env python3
"""Serial CPU-only repair qualification, including compile-only device builds."""
import os,sys
from pathlib import Path
import hc_fix_campaign as campaign
P=Path(__file__).resolve().parent
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 campaign.E=P/'evidence/route-gather-fix';campaign.E.mkdir(exist_ok=True,parents=True)
 phase=sys.argv[1]
 if phase=='all':
  for step in ('matrix','builds','gates','models','final'):campaign.py('phase-'+step,Path(__file__),step)
 elif phase=='matrix':campaign.py('fusion-matrix','fusion_matrix.py','--label','after')
 elif phase=='gates-tail':
  # Resume a recorded wrapper refusal after the unchanged arithmetic/owner
  # receipts passed. The final seal revalidates their sources and binaries.
  py=campaign.py
  def resume(name,*args):
   if name in ('capacity_selection_gate','capacity_fixture_gate','asan_fixture_gate','p39_merged_fixture_gate','cpu_gates'):
    print('REUSE completed unchanged gate',name,flush=True);return
   py(name,*args)
  campaign.py=resume;sys.argv=[sys.argv[0],'gates'];campaign.main()
 elif phase=='gates':
  campaign.py('hc-activation','hc_activation_gate.py','--label','after')
  campaign.py('legacy-entry-validation','validation_gate.py')
  campaign.py('capacity-fixtures-fresh','capacity_fixture_gate.py','--fresh')
  campaign.py('fusion-seal-tests','test_fusion_bindings.py')
  sys.argv=[sys.argv[0],phase];campaign.main()
 elif phase in ('builds','models','final'):
  sys.argv=[sys.argv[0],phase];campaign.main()
 else:raise ValueError(phase)
if __name__=='__main__':main()

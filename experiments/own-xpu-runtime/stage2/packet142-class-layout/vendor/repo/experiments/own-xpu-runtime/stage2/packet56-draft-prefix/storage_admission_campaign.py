#!/usr/bin/env python3
"""Complete serial CPU requalification after a host gate change; no device build/run."""
import json,os,sys
from pathlib import Path
import hc_fix_campaign as campaign
from storage import digest,admit
P=Path(__file__).resolve().parent
E=P/'evidence/storage-admission-fix'
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 E.mkdir(parents=True,exist_ok=True);campaign.E=E
 # Preserve the previous gate identity before rerunning even unchanged model gates.
 for name in ('build-receipt.json','cpu-tests.json','cpu-real-gates.json','cpu-merged-gates.json'):
  dest=E/('before-'+name)
  if not dest.exists():dest.write_bytes((P/name).read_bytes())
 phase=sys.argv[1]
 if phase=='all':
  for next_phase in ('gates','models','final'):campaign.py('phase-'+next_phase,Path(__file__),next_phase)
 elif phase=='gates':
  campaign.py('storage-regression','test_window_storage.py','--output',E/'window-storage.json')
  campaign.py('storage-race','test_storage_race.py')
  campaign.py('hc-activation','hc_activation_gate.py','--label','after')
  campaign.py('legacy-entry-validation','validation_gate.py')
  campaign.py('capacity-fixtures-fresh','capacity_fixture_gate.py','--fresh')
  # Remaining existing suite includes cross-compiler, ASAN, owners, wrappers,
  # kernel selection, memory, and all three controller/mailbox build modes.
  sys.argv=[sys.argv[0],'gates'];campaign.main()
 elif phase in ('models','final'):
  sys.argv=[sys.argv[0],phase];campaign.main()
 else:raise ValueError(phase)
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Serial CPU-only fix-4 campaign; device mode compiles/links only."""
import os,sys
from pathlib import Path
import hc_fix_campaign as campaign
P=Path(__file__).resolve().parent
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 campaign.E=P/'evidence/copy-extent-fix';campaign.E.mkdir(exist_ok=True,parents=True)
 phase=sys.argv[1]
 if phase=='all':
  for step in ('copy','matrix','builds','gates','models','final'):campaign.py('phase-'+step,Path(__file__),step)
 elif phase=='copy':campaign.py('copy-adoption','copy_adoption_gate.py')
 elif phase=='matrix':
  campaign.py('fusion-matrix','-c',"import sys;from pathlib import Path;import fusion_matrix as m;m.E=m.P/'evidence/copy-extent-fix/fusion';m.E.mkdir(exist_ok=True);sys.argv=['fusion_matrix.py','--label','after'];m.main()")
 elif phase=='gates':
  campaign.py('hc-activation','hc_activation_gate.py','--label','after')
  campaign.py('legacy-entry-validation','validation_gate.py')
  campaign.py('capacity-fixtures-fresh','capacity_fixture_gate.py','--fresh')
  campaign.py('fusion-seal-tests','test_fusion_bindings.py')
  campaign.py('copy-seal-tests','test_copy_adoption.py')
  sys.argv=[sys.argv[0],phase];campaign.main()
 elif phase in ('builds','models','final'):
  sys.argv=[sys.argv[0],phase];campaign.main()
 else:raise ValueError(phase)
if __name__=='__main__':main()

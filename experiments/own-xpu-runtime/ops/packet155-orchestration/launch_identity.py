"""Exact packet155 chain unit and closed interpreter environment, lane A."""
import os
from pathlib import Path
UNIT='packet155-chain-a.service'
def verify(cgroup=None,environment=None):
 from chain_adapter import P
 import sys
 sys.path.insert(0,str(P))
 from confirm136 import LIBRARIES
 group=Path('/proc/self/cgroup').read_text() if cgroup is None else cgroup
 env=dict(os.environ) if environment is None else environment
 assert any('/user@' in line and line.rstrip().endswith('/'+UNIT) for line in group.splitlines()),'wrong packet155 chain unit'
 expected=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=LIBRARIES)
 assert env==expected or env==dict(expected,LC_CTYPE='C.UTF-8'),'closed chain environment required'
 return dict(passed=True,unit=UNIT,lane='A',cards=[0,1],environment=expected)

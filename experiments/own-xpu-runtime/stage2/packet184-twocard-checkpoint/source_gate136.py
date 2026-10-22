"""Repository-only source maps; oracle authority always has its own validator."""
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def verify_sources(sources):
 import bootstrap
 from common import verify_map
 verify_map(ROOT,sources)
 for name in sources:
  if (ROOT/name).is_relative_to(P/'oracle'):
   raise ValueError('oracle authority must use static binding, not source map')
 return sources

def oracle():
 import subprocess
 from shared_oracle import static_binding
 binding=static_binding()
 command=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(P/'shared_oracle.py'),'--require-complete']
 result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
 if result.returncode:raise ValueError('complete shared oracle refused: '+result.stderr[-2000:])
 return dict(binding=binding,returncode=0)

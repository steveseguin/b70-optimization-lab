"""Install only local chain modules, original oracle authority and exec guard."""
import sys,runpy
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations');P=ROOT/'experiments/own-xpu-runtime/stage2/packet143-record-bundle';O=ROOT/'experiments/own-xpu-runtime/ops/packet143-orchestration'
sys.path.insert(0,str(P))
def install():
 from cpu_prepare143 import verify
 verify()
 from shared_oracle import static_binding
 static_binding()
 from exec_limits import install as guard
 guard()
 import shared_oracle
 return shared_oracle
if __name__=='__main__':
 role=sys.argv.pop(1);assert role in ('check_inputs.py','chain103.py','fast_reseal.py');install();sys.argv[0]=str(P/role);runpy.run_path(str(P/role),run_name='__main__')

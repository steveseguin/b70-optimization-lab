"""Load the local vendored wrappers, with no foreign packet imports or reseal."""
import importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];WRAPPER=P/'v5'
def install():
 sys.path.insert(0,str(WRAPPER))
 import common
 common.HERE=P
 for name,filename in [('cpu_seal','cpu_prepare143.py'),('placement','placement.py'),('drain_gate','drain_gate.py')]:
  path=P/filename;spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
 return sys.modules['placement']

# Explicit factory used by both screen and worker: a symlink-preserving view
# refers to one local binary, never an unbound path from caller arguments.
def composition_sealed(args):
 from compositions import path,read,sha
 from cpu_prepare143 import verify
 verify();root=args.lineage.resolve();selection=read(root/'composition.json')
 assert root==path(selection) and args.profile=='tp2' and args.placement=='1' and args.timing=='token'
 binary=P/'v5/build/device/own-rt-iq3';dispatch=root/'dispatch-speed6.json';seal=root/'screen-seal.json'
 for value,expected in ((args.binary,binary),(args.dispatch,dispatch),(args.seal,seal)):assert value is None or value.resolve()==expected.resolve(),'unsealed smoke input'
 import placement
 config=placement.admit(root,read(seal),seal,dispatch,'1')
 return dict(placement=config,timing='token',timing_modes=['token'],lineage=str(root),seal=str(seal),seal_sha256=sha(seal),binary=str(binary),binary_sha256=sha(binary),dispatch=str(dispatch),dispatch_sha256=sha(dispatch),profile='tp2',selection_sha256=sha(root/'selection.json'),memory_plan_sha256=sha(root/'memory-plan.json'))
_original_install=install
def install():
 result=_original_install()
 import common
 common.sealed=composition_sealed
 return result

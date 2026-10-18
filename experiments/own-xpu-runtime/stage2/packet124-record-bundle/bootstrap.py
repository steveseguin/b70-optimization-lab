"""Load the pinned shared wrapper with a packet-local placement policy only."""
import importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];WRAPPER=P.parent/'screen/v4-lanes'
sys.path.insert(0,str(WRAPPER))
from common import read,require,sha,verify_map
from cpu_seal import verify as verify_wrapper

def install():
 pin=read(P/'dependency-pins.json');verify_map(ROOT,pin)
 verify_wrapper()
 path=P/'placement.py'
 spec=importlib.util.spec_from_file_location('placement',path);module=importlib.util.module_from_spec(spec)
 sys.modules['placement']=module;spec.loader.exec_module(module)
 return module

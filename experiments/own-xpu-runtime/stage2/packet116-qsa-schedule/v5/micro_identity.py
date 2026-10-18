"""Read-only micro seal check in its own module namespace; never runs a device."""
import json,sys
from pathlib import Path
if __name__=='__main__':
 directory=Path(__file__).resolve().parent.parent/'micro'
 sys.path.insert(0,str(directory))
 from run_micro import build_gate
 print(json.dumps(build_gate()))

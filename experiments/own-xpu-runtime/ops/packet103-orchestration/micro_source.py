"""Read the real-route qualification in its isolated source namespace."""
import sys,json
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'stage2/packet100b-route-capture'
sys.path.insert(0,str(P))
from qualification import require_qualified,measured
if __name__=='__main__':
 require_qualified(P)
 result=measured(P)
 result['validation_sources']={**json.loads((P/'packet-seal.json').read_text())['sources'],**json.loads((P/'evidence/microbench-build.json').read_text())['sources']}
 print(json.dumps(result))

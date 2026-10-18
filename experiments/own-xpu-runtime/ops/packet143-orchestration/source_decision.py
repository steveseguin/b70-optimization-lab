from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent
ROOT=O.parents[3]
P=ROOT/'experiments/own-xpu-runtime/stage2/packet143-record-bundle'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')

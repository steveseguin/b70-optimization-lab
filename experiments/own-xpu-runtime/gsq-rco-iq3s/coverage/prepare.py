#!/usr/bin/env python3
"""Small private adaptation of the qualified bundle transport; no execution."""
from pathlib import Path
import hashlib,json,difflib
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2]
SOURCE=L/'expert-iq3xxs-block/engine/operating/generated/adapter.py'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 pins=json.loads((P/'parent-pins.json').read_text())
 for f,h in pins.items():assert sha(f)==h,f
 old=SOURCE.read_text();s=old
 replacements=[('CANDIDATE=P.parent.parent',"CANDIDATE=Path("+repr(str(L/'expert-iq3xxs-block/engine'))+")"),('request_cap=26,','request_cap=6,'),('27*(221743168+9699332) # initial blank RESET plus all26 requests','7*(221743168+9699332) # initial blank RESET plus six requests'),("'request_count':26,","'request_count':6,")]
 for a,b in replacements:assert s.count(a)==1;s=s.replace(a,b)
 out=P/'generated';out.mkdir(exist_ok=False);(out/'adapter.py').write_text(s)
 (P/'adapter.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile=str(SOURCE.relative_to(R)),tofile=str((out/'adapter.py').relative_to(R)))))
 d=dict(source_sha256=pins,generated_sha256={str(out/'adapter.py'):sha(out/'adapter.py')},recipe_sha256=sha(__file__),patch_sha256=sha(P/'adapter.patch'),device_executed=False,requests=6,captures=7)
 (P/'preparation.json').write_text(json.dumps(d,indent=2)+'\n')
if __name__=='__main__':main()

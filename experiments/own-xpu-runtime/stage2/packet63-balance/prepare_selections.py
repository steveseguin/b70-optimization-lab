#!/usr/bin/env python3
"""Create only control and the exact packet59c screen2 HC group."""
import json,os
from pathlib import Path
from build_engine import sha,save
P=Path(__file__).resolve().parent;DRAFT=P.parent/'packet59c-draft-select'
CHOICES=('control','draft-hc')
def configs():
 candidate=json.loads((DRAFT/'selections/screen2-hc.json').read_text())
 assert candidate['decision']['sha256']==sha(P/'selection-decision.json')
 active={k for k,v in candidate['draft'].items() if v=='packet59'}
 assert len(active)==14 and all(k.startswith(('hc_','fuse_hc_')) for k in active)
 control=json.loads(json.dumps(candidate));control['draft']={k:'production' for k in candidate['draft']}
 return {'control':control,'draft-hc':candidate}
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 for name,config in configs().items():
  dest=P/'selections'/name;dest.mkdir(parents=True,exist_ok=False)
  save(dest/'selection.json',config)
  for leaf in ('selection-decision.json','memory-plan.json','dispatch-speed6.json'):(dest/leaf).write_bytes((P/leaf).read_bytes())
 print('Two selections prepared; target and 23/25 split unchanged')
if __name__=='__main__':main()

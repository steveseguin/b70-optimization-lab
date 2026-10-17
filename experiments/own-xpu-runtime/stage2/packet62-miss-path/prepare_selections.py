#!/usr/bin/env python3
import json,os
from pathlib import Path
P=Path(__file__).resolve().parent
CHOICES=('control','batch','banks','banks-batch','banks-batch-overlap')
def main():
 for choice in CHOICES:
  d=P/'selections'/choice;d.mkdir(exist_ok=True)
  assert not (d/'screen-seal.json').exists()
  selection=json.loads((P/'selection.json').read_text());selection['choices']['miss']=choice
  (d/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
  for name in ('dispatch-speed6.json','memory-plan.json','selection-decision.json'):
   (d/name).write_bytes((P/name).read_bytes())
if __name__=='__main__':main()

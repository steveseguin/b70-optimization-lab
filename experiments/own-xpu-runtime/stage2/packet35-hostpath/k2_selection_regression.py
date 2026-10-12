#!/usr/bin/env python3
"""CPU-only replay of historical K2 selections; never runs a device program."""
import hashlib
import json
from pathlib import Path
from k2_summary import resolve_fusions
HERE=Path(__file__).resolve().parent

def main():
 source=HERE.parent/'packet29-merged/build/k2-r29/run/summary.json'
 summary=json.loads(source.read_text())
 classes=json.loads((HERE/'k2-class-registry.json').read_text())['classes']
 dispatch=json.loads((HERE/'dispatch-default.json').read_text())
 for name,entry in classes.items():
  row=summary['classes'][name];row['selected_comparison']=None
  for candidate in row['comparisons']:
   if row['selected']!=row['incumbent'] and (candidate==row['selected'] or entry.get('candidate_implementation')==row['selected']):
    row['selected_comparison']=candidate;break
  if entry.get('dispatch_section'):
   for key in entry.get('dispatch_keys',[entry['dispatch_key']]):
    dispatch[entry['dispatch_section']][key]=row['selected']
 result=resolve_fusions(dispatch,summary['classes'],classes)
 assert {row['fusion'] for row in result if row['selected']=='fusion'}=={'small.hc','small.gdn.ab','small.ffn'}
 receipt=dict(schema='packet35.k2.selection-regression.v1',passed=True,device_executed=False,
  input_source=str(source.relative_to(HERE.parents[3])),input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
  note='CPU reaggregation of packet29 historical measurements; not packet35 device measurements',
  resolutions=result,dispatch=dispatch)
 (HERE/'k2-selection-regression.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print('historical K2 selection regression: 3/3 fusions restored; device_executed=false')

if __name__=='__main__':main()

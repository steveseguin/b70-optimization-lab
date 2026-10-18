#!/usr/bin/env python3
"""Unsealed view configuration and fixed coordinator job manifests."""
from pathlib import Path
import json
P=Path(__file__).resolve().parent
CHOICES={'production':{},'hc-a':{'hc_a_gate':'stream4'},'hc-f':{'hc_f_gate':'stream4'},
         'rec-head':{'recurrence_head':'head-once'},'combined':{'hc_a_gate':'stream4','hc_f_gate':'stream4','recurrence_head':'head-once'}}
ORDERS={'A':('production','hc-a','hc-f','rec-head','combined','production'),
        'B':('production','combined','rec-head','hc-f','hc-a','production')}
def main():
 base=json.loads((P/'selection.json').read_text())
 for name,changes in CHOICES.items():
  dest=P/'selections'/name;dest.mkdir(parents=True,exist_ok=True)
  assert not (dest/'screen-seal.json').exists(),'never edit sealed views'
  sel=json.loads(json.dumps(base));sel['choices'].update(changes)
  (dest/'selection.json').write_text(json.dumps(sel,indent=2)+'\n')
 for lane,order in ORDERS.items():
  lines=['# out|lineage|seal|binary|dispatch|placement']
  for i,name in enumerate(order):
   d=P/'selections'/name
   lines.append('|'.join(map(str,(f'p67-quick-{lane}-{i+1}-{name}-a',d,d/'screen-seal.json',d/'build/device/own-rt-iq3',d/'dispatch-speed6.json','1'))))
  (P/'screen/quick'/f'jobs-{lane}.txt').write_text('\n'.join(lines)+'\n')
 p=P/'screen/quick/jobs.py';s=p.read_text().replace('packet65','packet67').replace('p65-quick','p67-quick')
 start=s.index('ORDERS =');end=s.index('\n\n',start);s=s[:start]+'ORDERS = '+repr(ORDERS)+s[end:];p.write_text(s)
 for name in ('screen/quick/quick_seal.py','screen/quick/screen.py'):
  p=P/name;p.write_text(p.read_text().replace('packet65','packet67'))
 p=P/'screen/placement.py';p.write_text(p.read_text().replace("'packet65-expert-occupancy')","'packet65-expert-occupancy', 'packet67-roofline')"))
 print('five unsealed views and two six-screen job orders')
if __name__=='__main__':main()

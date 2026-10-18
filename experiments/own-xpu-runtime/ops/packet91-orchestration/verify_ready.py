"""Reject stale, changed or incomplete readiness before a coordinator launch."""
from orchestrate import O,P,ROOT,sha,command,select,apply_pins,DEFAULTS
import json
from pathlib import Path

def verify():
 row=json.loads((O/'ready.json').read_text())
 assert row.get('schema')=='packet91.ready.v1'
 assert row.get('ready') is True and row.get('device_executed') is False and row.get('preparation_passed') is True
 assert row['chain_command']==command()
 assert row['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 assert set(row['checks'])=={'cpu-dry-run','seal','inputs','storage','queue-plan'}
 assert row['pins'] and set(row['screens'])=={'91','90'}
 for name,h in row['pins'].items():assert sha(ROOT/name)==h,name
 for name,h in row['checks'].items():assert sha(O/(name+'.log'))==h,name
 for packet in row['screens'].values():
  assert packet['status'] in ('winner','no-winner')
  for category in ('receipts','sources'):
   for name,h in packet[category].items():assert sha(ROOT/name)==h,name
 choice,pins=apply_pins(select(row['screens']),[k+'='+v for k,v in row.get('coordinator_pins',{}).items()])
 assert choice==row['selection']
 assert not (P/'build/device-cards01-a').exists(),'chain already started'
 return row
if __name__=='__main__':verify();print('real readiness verified')

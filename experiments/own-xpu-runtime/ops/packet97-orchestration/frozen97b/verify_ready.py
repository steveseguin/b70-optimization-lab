"""Recheck every source, receipt, selection, composition and readiness binding."""
import json
from pathlib import Path
from orchestrate import O,P,ROOT,sha,command,select,apply_pins,composition,matched_composition

def verify():
 row=json.loads((O/'ready.json').read_text());assert row['schema']=='packet97.ready.v1'
 assert row['ready'] is True and row['preparation_passed'] is True and row['device_executed'] is False
 assert row['chain_command']==command() and row['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 assert set(row['checks'])=={'cpu-dry-run','seal','inputs','storage','queue-plan'}
 assert row['pins'] and set(row['screens'])=={'90','91','92','93','94','95'}
 for n,h in row['pins'].items():assert sha(ROOT/n)==h,n
 for n,h in row['checks'].items():assert sha(O/(n+'.log'))==h,n
 for number,r in row['screens'].items():
  assert r['status'] in ('winner','no-winner','pending')
  if number not in row['qualified_sources']:continue
  for cat in ('receipts','sources'):
   for n,h in r[cat].items():assert sha(ROOT/n)==h,n
 control,choice,confirmed=select(row['screens']);choice,pins=apply_pins(choice,[k+'='+v for k,v in row['coordinator_pins'].items()])
 config=json.loads((P/'composition-selection.json').read_text())
 expected=composition(row['screens'],control,choice,confirmed,pins,row['coordinator_closures'])
 assert config==expected and config['candidate']==row['selection']
 result=matched_composition(config)
 assert result==row['composition'] and result['passed'] and result['chain_policy_passed'] and not result['leave_one_out']['required']
 assert not (P/'build/device-cards01-a').exists(),'chain already started'
 return row
if __name__=='__main__':verify();print('packet97 real readiness verified')

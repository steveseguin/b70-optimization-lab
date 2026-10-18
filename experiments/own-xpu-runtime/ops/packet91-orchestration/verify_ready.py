"""Reject stale, changed or incomplete readiness before coordinator launch."""
from orchestrate import O,P,ROOT,sha,command
import json
from pathlib import Path
def verify():
    row=json.loads((O/'ready.json').read_text())
    assert row.get('ready') is True and row.get('device_executed') is False
    assert row['chain_command']==command()
    assert row['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    for name,h in row['pins'].items():assert sha(ROOT/name)==h,name
    for name,h in row['checks'].items():assert sha(O/(name+'.log'))==h,name
    for packet in row['screens'].values():
        for category in ('receipts','sources'):
            for name,h in packet[category].items():assert sha(ROOT/name)==h,name
    assert not (P/'build/device-cards01-a').exists(),'chain already started'
    return row
if __name__=='__main__':verify();print('real readiness verified')

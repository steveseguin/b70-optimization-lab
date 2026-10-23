#!/usr/bin/env python3
"""Live-launch-only privileged passive inventory. CPU rehearsals never call this."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations');HERE=Path(__file__).resolve().parent

def main():
    helper=HERE/'passive_device_holders.py'
    ready=json.loads((HERE/'READY-FOR-DEVICE.json').read_text())
    assert hashlib.sha256(helper.read_bytes()).hexdigest()=={item['relative_path']:item['digest'] for item in ready['orchestration_source_pins']}[str(helper.relative_to(ROOT))]
    with Path('/home/steve/SUDOPASSWORD.txt').open('rb') as credential:
        cp=subprocess.run(['/usr/bin/sudo','-S','-p','','--','/usr/bin/python3','-B',str(helper)],stdin=credential,capture_output=True,text=True,timeout=30,cwd=ROOT)
    assert cp.returncode in (0,1) and not cp.stderr.strip(),'privileged inventory failed'
    row=json.loads(cp.stdout)
    assert row.get('metadata_only') is True and row.get('device_opens')==0
    assert cp.returncode==0 and row.get('passed') is True and not row.get('holders') and not row.get('errors'),'holders or unreadable inventory remain'
    print(json.dumps(row))
if __name__=='__main__':main()

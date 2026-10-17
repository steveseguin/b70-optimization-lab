#!/usr/bin/env python3
"""CPU-only fail-closed protocol tests; record source-bound receipts."""
from datetime import datetime,timezone
import json
import subprocess
from build import HERE,ROOT,sha,limits

def main():
    limits();out=HERE/'evidence'/('python-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir(parents=True,exist_ok=False)
    sources={str(p.relative_to(ROOT)):sha(p) for p in HERE.glob('*.py')}
    parent=HERE.parent/'packet34-replay-bench/window.py';sources[str(parent.relative_to(ROOT))]=sha(parent)
    with (out/'stdout').open('w') as stdout,(out/'stderr').open('w') as stderr:
        subprocess.run(['/usr/bin/python3','-B','-m','unittest','discover','-s',str(HERE),'-p','test_*.py','-v'],check=True,stdout=stdout,stderr=stderr)
    for p,h in sources.items():assert sha(ROOT/p)==h,'source changed during tests'
    row=dict(schema='ownrt.packet48.python-gates.v1',passed=True,device_executed=False,
             source_hashes=sources,files={str(p.relative_to(HERE)):sha(p) for p in out.iterdir()})
    (HERE/'python-gates.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(dict(passed=True,device_executed=False)))

if __name__=='__main__':main()

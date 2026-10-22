"""Run only AFTER the queue stops and the design patch is applied."""
import hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
from speed5_qualification import BEFORE,PINS
raw=subprocess.check_output(['git','show','eabc1324206442b9ecb6bffd375cd5b4b8c52f3c:'+str((P/'build-receipt.json').relative_to(ROOT))],cwd=ROOT)
assert hashlib.sha256(raw).hexdigest()==BEFORE
assert hashlib.sha256((P/'build-receipt.json').read_bytes()).hexdigest()==BEFORE,'a newer seal requires rebasing this proposal'
assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in PINS.items()),'proposal source changed'
p=P/'evidence/speed5/before-build-receipt.json';p.parent.mkdir(exist_ok=True)
if p.exists():assert p.read_bytes()==raw
else:p.write_bytes(raw)
print('SPEED5 baseline pinned; build and gates are still required')

"""Run and retain the bounded host fault evidence, then remove scratch."""
import json,shutil,subprocess,sys,time
from pathlib import Path
from pipeline import P,sha,save
root=P/'build'/f'fault-gates-{time.time_ns()}'
subprocess.run([sys.executable,'-B',str(P/'fault_gates.py'),'--binary',str(P/'build/gnu-host/own-rt-iq3'),'--output',str(root)],check=True)
result=json.loads((root/'receipt.json').read_text())
result['test_source_sha256']=sha(P/'fault_gates.py')
result['evidence']={str(f.relative_to(root)):json.loads(f.read_text()) for f in root.rglob('*.json') if f.name in ('receipt.json','ownership.json','failure-before-teardown.json') and f!=root/'receipt.json'}
save(P/'review-native-faults.json',result)
shutil.rmtree(root)

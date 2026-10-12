"""Finish small CPU checks once the two campaigns and capture runner have retired."""
import json,os,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';PY='/home/steve/.venvs/vllm-xpu/bin/python'
assert os.getpriority(os.PRIO_PROCESS,0)==19
needed=('real-campaign-gnu-host.json','real-campaign-icpx-host.json','remaining-cpu-receipt.json')
while True:
 ready=True
 for name in needed:
  path=P/name
  if not path.exists():ready=False;continue
  try:result=json.loads(path.read_text())
  except json.JSONDecodeError:ready=False;continue
  assert result['passed'],name
 if ready:break
 time.sleep(5)
for script in ('draft_auth_gate.py','resident_host_gate.py','pipeline_draft_agreement.py','seal.py'):
 with (B/('final-'+script+'.log')).open('w') as log:
  result=subprocess.run([PY,'-B',str(P/script)],stdout=log,stderr=subprocess.STDOUT)
 print(script,result.returncode,flush=True)
 assert result.returncode==0,script
print('CPU checks sealed; device not run',flush=True)

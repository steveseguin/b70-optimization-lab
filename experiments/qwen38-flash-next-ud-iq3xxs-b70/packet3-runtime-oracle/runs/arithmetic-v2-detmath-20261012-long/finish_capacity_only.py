"""Stop this preparation supervisor after its verified capacity gate; no retry."""
import json,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
while True:
 p=HERE/'capacity-incident/equality-proof.json'
 if p.exists():
  assert json.loads(p.read_text())['passed']
  result=subprocess.run(['nice','-n','19','ionice','-c','3','systemctl','--user','stop','iq3-long-campaign-final-20261012'],check=True)
  (HERE/'capacity-supervisor-boundary.json').write_text(json.dumps(dict(reason='End preparation at the complete verified capacity gate before finalizing long-run receipt compression. Any just-started diagnostic is stopped cooperatively.',capacity_gate_passed=True,stop_returncode=result.returncode),indent=2)+'\n')
  break
 time.sleep(1)

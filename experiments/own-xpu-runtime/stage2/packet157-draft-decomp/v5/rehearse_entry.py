"""Packet-specific CPU rehearsal: actual entry exec interception and report path."""
import argparse,json,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('proposal',type=Path);ap.add_argument('--report',action='store_true',required=True);a=ap.parse_args()
job=json.loads(a.proposal.read_text());argv=job['argv'];value=lambda n:argv[argv.index(n)+1]
kind,lane,variant=map(value,('--kind','--lane','--variant'))
rows=[]
for name,args in [('entry_gate.py',['--probe',variant,kind,'positive',lane]),('report_gate.py',['--probe',kind,variant,lane])]:
 cp=subprocess.run([sys.executable,'-B',str(P/name),*args],stdin=subprocess.DEVNULL,capture_output=True,text=True)
 if cp.returncode:raise RuntimeError(cp.stdout+cp.stderr)
 rows.append(dict(script=name,passed=True))
print(json.dumps(dict(passed=True,device_executed=False,packet_specific_synthetic_streams=True,proposal=str(a.proposal),rows=rows)))

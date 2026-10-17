"""Coordinator invocation only; no services, retries or implicit GPU admission."""
import argparse,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('job',choices=('smoke-B','control-B','candidate-B','control-repeat-B'));ap.add_argument('--fault-review',type=Path);ap.add_argument('--plan',action='store_true');a=ap.parse_args()
 row=next(r for r in json.loads((P/'screen/jobs.json').read_text()) if r['name']==a.job)
 cmd=row['command']+(['--plan'] if a.plan else ['--fault-review',str(a.fault_review.resolve()),'--authorized-device-window'] if a.fault_review else [])
 if not a.plan and not a.fault_review:ap.error('coordinator fault review required')
 return subprocess.call(cmd,stdin=subprocess.DEVNULL,env=os.environ)
if __name__=='__main__':raise SystemExit(main())

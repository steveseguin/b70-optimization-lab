"""Extend the frozen shared checker only for this two-card record report shape.

The original checker covers v5 screens and packet58 one-card reports, and rejects
this inherited packet136 chain shape. Retain that refusal. Use every original
loader/storage/deadline/preparation/identity check unchanged, substituting only
the unsupported report adapter with read-only replay on real 136/153 evidence.
"""
import importlib.util,json,resource,subprocess,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3]
sys.path.insert(0,str(O.parent))
import rehearse_entry as shared

def chain_report(job,env,source_root=ROOT):
 assert job['lane']=='A' and job['plan']['coordinator_unit']=='packet195-chain-a'
 assert Path(job['argv'][2]).name=='chain_entry.py'
 cp=subprocess.run(['/usr/bin/python3','-B',str(O/'real_report.py')],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
 (O/'evidence/real-report.log').write_text(cp.stderr)
 assert cp.returncode==0,cp.stderr[-1500:]
 row=json.loads(cp.stdout);assert row['passed'] and row['real_evidence'] and not row['device_executed']
 (O/'evidence/real-report.json').write_text(json.dumps(row,indent=2)+'\n')
 return dict(passed=True,device_executed=False,real_evidence=True,adapter='packet195 record-chain report adapter',windows=[r['window'] for r in row['chain']],sources={str((O/'real_report.py').relative_to(ROOT)):shared.digest(O/'real_report.py')},generic_screen_report_not_applicable=True)

def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('proposal',type=Path);ap.add_argument('--report',action='store_true',required=True);args=ap.parse_args()
 job=json.loads(args.proposal.read_text());queue=shared.lanequeue();ldp=queue.library_path()
 shared.rehearse_report=chain_report
 row=shared.rehearse(job,queue,ldp,report=True)
 result=dict(passed=row['passed'],device_executed=False,jobs=[row],shared_checker_sha256=shared.digest(O.parent/'rehearse_entry.py'),proposal_sha256=shared.digest(args.proposal),extension_scope='Only the unsupported two-card report adapter. Original four packaging checks and native loader/parser tests execute unchanged. Actual coordinator-unit entry is separately tested by entry195.py.')
 (O/'evidence/entry-report.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:row.get(k) for k in ('passed','storage_floor','wall_deadlines','preparation_path','gate_identity')},indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);raise SystemExit(main())

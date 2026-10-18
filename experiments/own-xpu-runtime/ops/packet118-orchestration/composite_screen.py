"""Coordinator entry. CPU --plan does not bypass execution prerequisites."""
import argparse,json
from pathlib import Path
from composite_jobs import P,WRAPPER,sha,jobs,view,validate

def main(argv=None):
 ap=argparse.ArgumentParser();ap.add_argument('--decision',type=Path,required=True);ap.add_argument('--decision-sha256',required=True);ap.add_argument('--lane',choices=('A','B'),required=True);ap.add_argument('--index',type=int,choices=range(3),required=True);ap.add_argument('--plan',action='store_true');ap.add_argument('--fault-review');ap.add_argument('--authorized-device-window',action='store_true');a=ap.parse_args(argv)
 assert sha(a.decision)==a.decision_sha256;config=json.loads(a.decision.read_text());validate(config)
 job=jobs(config,a.lane)[a.index];lineage=view(job['selection'])
 cmd=['--profile','tp2','--lane',a.lane,'--placement','1','--timing','token','--lineage',str(lineage),'--seal',str(lineage/'screen-seal.json'),'--output',str(WRAPPER/'evidence'/job['out'])]
 if a.plan:cmd+=['--plan']
 else:
  from policy_seal import verify as verify_policy
  verify_policy()
  assert config['extra_dimension_selected'],'no new dimension qualifies; identical-selection jobs stay plan-only'
  assert a.authorized_device_window and a.fault_review
  from smoke_validation import require_smoke
  require_smoke()
  # Reread current source evidence before each launch; a later A loss vetoes it.
  from source_decision import read_sources,decide
  selected=decide(read_sources())
  assert all(config['candidate'][k]==v for k,v in selected.items()),'source decision changed; prepare a fresh decision'
  cmd+=['--fault-review',a.fault_review,'--authorized-device-window']
 from run_screen import main as run
 return run(cmd)
if __name__=='__main__':raise SystemExit(main())

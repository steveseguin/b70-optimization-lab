"""Review26: exact lane-B v5 >=0.5%, drift <=1%, plus exact lane-A 12x64."""
import json,math,subprocess,sys
from pathlib import Path
from composite_jobs import O,ROOT,P,sha,current,validate,view,jobs

def read_device(path,lane,kind):
 cp=subprocess.run([sys.executable,'-B',str(O/'evidence_reader.py'),str(path),lane,kind],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
 if cp.returncode:raise ValueError(str(path)+': '+cp.stderr[-1600:])
 return json.loads(cp.stdout)
def smoke():
 from confirm136 import output
 row=read_device(output(-1),'A','smoke');r=row['result']
 assert r['passed'] is True and r['kind']=='smoke' and r['request_count']==12 and r['max_new']==64
 return row
def qualify_bracket(row,lane='B'):
 assert lane=='B','review26 has one bracket, on B'
 r=row['result'];views=r['views']
 assert r['passed'] is True and r['kind']=='bracket' and r['model_lifetimes']==1,'one-load v5 required'
 assert len(views)==5 and [v['choice'] for v in views]==['control','candidate','control','candidate','control']
 assert all(v['index']==i and v['lane']=='B' and v['all_13_exact'] is True and v['exact_count']==13 for i,v in enumerate(views)),'every prompt and incident exact required'
 assert all(type(v['rate']) in (int,float) and math.isfinite(v['rate']) and v['rate']>0 for v in views),'invalid rates'
 assert all(v['acceptance_counts']==views[0]['acceptance_counts'] for v in views),'acceptance changed'
 assert views[0]['draft_proposals'] and all(v['draft_proposals']==views[0]['draft_proposals'] for v in views),'draft proposals changed'
 controls=[v['rate'] for v in views if v['choice']=='control'];candidates=[v['rate'] for v in views if v['choice']=='candidate']
 drift=100*(max(controls)/min(controls)-1);ratio=min(candidates)/max(controls)
 assert drift<=1.0+1e-12,'control drift exceeds 1%'
 assert ratio>=1.005-1e-12,'each candidate must beat every control by >=0.5%'
 return dict(passed=True,ratio=ratio,control_drift_percent=drift,controls=controls,candidates=candidates,selection_sha256=row['selection_sha256'],window_sha256=row['window_sha256'],summary_sha256=row['summary_sha256'],evidence_path=row['evidence_path'],model_lifetimes=1)
def matched(config):
 return dict(passed=True,lanes={'B':qualify_bracket(read_device(jobs(config,'B')['path'],'B','bracket'))},threshold_ratio=1.005,max_control_drift_percent=1.0,second_lane_grid_required=False)
def evaluate():
 path,config=current();row=dict(schema='packet139.ready.v1',ready=False,device_executed=False,cpu_preparation_ready=False,evidence_rule=config['evidence_rule'],decision=str(path.relative_to(ROOT)),decision_sha256=sha(path),selection=config['candidate'],chain_output='device-cards01-a',other_lane_pause_required=False)
 row['chain_command']=f"systemd-run --user --unit=packet139-chain-a --property=Restart=no --property=Nice=0 '--property=CPUAffinity=0-3 16-19' --property=KillMode=process --property=SendSIGKILL=no --property=ExitType=cgroup --property=TimeoutStopSec=infinity --working-directory={ROOT} /usr/bin/taskset -c 0-3,16-19 /usr/bin/bash {O/'device-entry.sh'} chain {P/'build/device-cards01-a'} </dev/null"
 try:
  from verify_cpu import verify as cpu
  cpu()
  from policy_seal import verify as policy
  policy()
  from argument_gate import verify as arguments
  arguments();row['argument_gate_sha256']=sha(O/'evidence/argument-gate.json')
  from native_startup139 import verify as native_startup
  native_startup();row['native_startup_sha256']=sha(O/'evidence/native-startup.json')
  from entry_gate import verify as entries
  entries();row['confirm_entries_sha256']=sha(O/'evidence/confirm-entries.json')
  from proposal_plan import verify as plan
  plan();row['proposal_plan_sha256']=sha(O/'evidence/queue-plan.json')
  from orchestrate import verify_tests
  verify_tests();row['cpu_tests_sha256']=sha(O/'cpu-tests.json')
  limits=json.loads((O/'evidence/launch-limits.json').read_text());assert limits['passed'] and len(limits['cases'])==4 and all(r['passed'] for r in limits['cases'])
  assert all(sha(ROOT/n)==h for n,h in limits['sources'].items());row['launch_limits_sha256']=sha(O/'evidence/launch-limits.json')
  assert not (P/'build/device-cards01-a').exists(),'chain folder must be fresh'
  row['cpu_preparation_ready']=True
  missing=[]
  try:row['smoke']=smoke()
  except (AssertionError,ValueError,OSError,KeyError) as e:missing.append('A composed smoke: '+str(e))
  try:row['composition']=matched(config)
  except (AssertionError,ValueError,OSError,KeyError) as e:missing.append('B v5 bracket: '+str(e))
  if missing:raise ValueError('; '.join(missing))
  assert row['smoke']['selection_sha256']==row['composition']['lanes']['B']['selection_sha256']==sha(P/'selection.json')
  from storage import precheck
  row['storage']=precheck();assert row['storage']['passed'],'storage admission refused'
  row['pins']={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('build-receipt.json','submission-pins.json','startup103.json')}
  row['ready']=True
 except (AssertionError,ValueError,OSError,KeyError,TypeError) as error:row['reason']=str(error) or type(error).__name__
 return row
def verify():
 stored=json.loads((O/'ready.json').read_text());actual=evaluate()
 assert stored['ready'] is True and actual['ready'] is True,actual.get('reason','stored readiness false')
 for key in ('decision_sha256','selection','chain_output','pins','smoke','composition','argument_gate_sha256','native_startup_sha256','launch_limits_sha256','cpu_tests_sha256','proposal_plan_sha256','confirm_entries_sha256'):assert stored[key]==actual[key],key+' changed'
 return actual
if __name__=='__main__':
 try:print(json.dumps(verify(),indent=2))
 except (AssertionError,ValueError,OSError,KeyError) as error:raise SystemExit('REFUSED: '+str(error))

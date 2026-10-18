"""Fail closed until both exact v5 lanes and a composed 12x64 smoke qualify."""
import json,math,subprocess,sys
from pathlib import Path
from composite_jobs import O,ROOT,P,sha,current,validate,view,jobs

def read_device(path,lane,kind):
 if not (Path(path)/'window.json').is_file():raise ValueError('pending '+lane+' '+kind+': '+str(path))
 cp=subprocess.run([sys.executable,'-B',str(O/'evidence_reader.py'),str(path),lane,kind],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
 if cp.returncode:raise ValueError(str(path)+': '+cp.stderr[-1600:])
 return json.loads(cp.stdout)

def smoke():
 row=read_device(P/'v5/evidence/device-smoke-A','A','smoke');r=row['result']
 assert r['passed'] is True and r['kind']=='smoke' and r['request_count']==12 and r['max_new']==64,'composed twelve-prompt exact 64-token smoke required'
 return row

def qualify_bracket(row,lane):
 r=row['result'];views=r['views']
 assert r['passed'] is True and r['kind']=='bracket' and r['model_lifetimes']==1,'complete one-load bracket required'
 assert len(views)==5 and [v['choice'] for v in views]==['control','candidate','control','candidate','control'],'A/B/A/B/A required'
 assert all(v['lane']==lane and v['all_13_exact'] is True and v['exact_count']==13 for v in views),'every prompt and incident must be exact on '+lane
 assert all(type(v['rate']) in (int,float) and math.isfinite(v['rate']) and v['rate']>0 for v in views),'invalid rates'
 assert all(v['acceptance_counts']==views[0]['acceptance_counts'] for v in views),'per-prompt acceptance changed on '+lane
 controls=[v['rate'] for v in views if v['choice']=='control'];candidate=[v['rate'] for v in views if v['choice']=='candidate']
 drift=100*(max(controls)/min(controls)-1)
 assert drift<=3.0,'control drift exceeds 3% on '+lane
 ratio=min(candidate)/max(controls)
 assert ratio>=1.005,'both candidates need >=0.5% over every '+lane+' control'
 return dict(passed=True,ratio=ratio,control_drift_percent=drift,acceptance_counts=views[0]['acceptance_counts'],selection_sha256=row['selection_sha256'],evidence_path=row.get('evidence_path'),window_sha256=row.get('window_sha256'),summary_sha256=row.get('summary_sha256'))

def matched(config):
 assert config['control']!=config['candidate'],'identical selections cannot establish gain'
 rows={};errors=[]
 for lane in ('A','B'):
  try:rows[lane]=qualify_bracket(read_device(jobs(config,lane)['path'],lane,'bracket'),lane)
  except (AssertionError,ValueError,OSError,KeyError) as error:errors.append(error)
 if errors:
  kind=ValueError if any(not isinstance(e,AssertionError) for e in errors) else AssertionError
  raise kind('; '.join(str(e) for e in errors))
 assert rows['A']['selection_sha256']==rows['B']['selection_sha256'],'identical-selection rule across lanes'
 assert rows['A']['acceptance_counts']==rows['B']['acceptance_counts'],'candidate acceptance differs across fresh lanes'
 return dict(passed=True,lanes=rows,threshold_ratio=1.005)

def evaluate():
 path,config=current();row=dict(schema='packet133.ready.v1',ready=False,device_executed=False,evidence_rule=config['evidence_rule'],decision=str(path.relative_to(ROOT)),decision_sha256=sha(path),selection=config['candidate'],chain_output='device-cards01-a',other_lane_pause_required=False,timing_exclusivity='Existing whole-host timing windows retain ordinary exclusive admission')
 row['chain_command']=f"systemd-run --user --unit=packet133-chain-a --property=Restart=no --property=Nice=0 '--property=CPUAffinity=0-3 16-19' --property=KillMode=process --property=SendSIGKILL=no --property=ExitType=cgroup --property=TimeoutStopSec=infinity --working-directory={ROOT} /usr/bin/taskset -c 0-3,16-19 /usr/bin/bash {O/'device-entry.sh'} chain {P/'build/device-cards01-a'} </dev/null"
 try:
  from drain_check import check
  row['drain_fix']=check()
  from argument_gate import verify as arguments
  arguments();row['argument_gate_sha256']=sha(O/'evidence/argument-gate.json')
  validate(config)
  from policy_seal import verify as policy
  policy()
  from chain_adapter import install
  install()
  limits=json.loads((O/'evidence/launch-limits.json').read_text())
  assert limits['passed'] and len(limits['cases'])==4 and all(x['passed'] for x in limits['cases']),'launch-limit gate incomplete'
  assert all(sha(ROOT/k)==v for k,v in limits['sources'].items()),'launch-limit sources changed'
  row['launch_limits_sha256']=sha(O/'evidence/launch-limits.json')
  from orchestrate import verify_tests
  verify_tests();row['cpu_tests_sha256']=sha(O/'cpu-tests.json')
  from chain_seal import verify
  seal=verify()
  assert seal['bundle_selection']['selection_sha256']==sha(view(config['candidate'])/'selection.json'),'chain selection differs'
  assert not (P/'build/device-cards01-a').exists(),'chain folder is not fresh'
  from proposal_plan import verify as queue_plan
  queue_plan();row['proposal_plan_sha256']=sha(O/'evidence/queue-plan.json')
  row['cpu_preparation_ready']=True
  # Missing device evidence remains an explicit refusal, never an inherited pass.
  missing=[]
  try:row['smoke']=smoke()
  except (AssertionError,ValueError,OSError,KeyError) as error:missing.append(str(error))
  try:row['composition']=matched(config)
  except (AssertionError,ValueError,OSError,KeyError) as error:missing.append(str(error))
  if missing:raise ValueError('; '.join(missing))
  assert row['smoke']['selection_sha256']==row['composition']['lanes']['A']['selection_sha256'],'smoke selection differs'
  from storage import precheck
  row['storage']=precheck();assert row['storage']['passed'],'storage admission refused'
  row['pins']={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('build-receipt.json','submission-pins.json','startup103.json')}
  row['ready']=True
 except (AssertionError,ValueError,OSError,KeyError,TypeError) as error:row['reason']=str(error) or type(error).__name__
 return row

def verify():
 stored=json.loads((O/'ready.json').read_text());actual=evaluate()
 assert stored['ready'] is True and actual['ready'] is True,actual.get('reason','stored readiness false')
 for key in ('decision_sha256','selection','chain_output','pins','smoke','composition','argument_gate_sha256','launch_limits_sha256','cpu_tests_sha256','proposal_plan_sha256'):assert stored[key]==actual[key],key+' changed'
 return actual
if __name__=='__main__':
 try:print(json.dumps(verify(),indent=2))
 except (AssertionError,ValueError,OSError,KeyError) as e:raise SystemExit('REFUSED: '+str(e))

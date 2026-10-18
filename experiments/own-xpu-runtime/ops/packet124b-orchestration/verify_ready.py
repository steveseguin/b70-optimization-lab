"""Read-only fail-closed readiness, never launches or synthesizes device evidence."""
import json,sys
from pathlib import Path
from composite_jobs import O,ROOT,P,sha,current,validate,view,evidence_view,jobs,WRAPPER

def inherited_smoke():
 from source_decision import parent_candidate_view
 from smoke_validation import require_smoke
 lineage=parent_candidate_view()
 root=WRAPPER/'evidence'/('p118-'+sha(lineage/'screen-seal.json')[:12]+'-B-smoke12')
 return require_smoke(lineage=lineage,root=root)

def matched(config):
 assert config['candidate']!=config['control'],'identical selections cannot establish a gain'
 import compare
 original_view,original_output=compare.view,compare.output
 try:
  from policy_seal import verify as verify_policy
  verify_policy()
  from chain_adapter import install
  install()
  compare.view=lambda label:evidence_view(config[label]);compare.output=lambda job:WRAPPER/'evidence'/job['out']
  brackets={}
  for lane in ('A','B'):
   brackets[lane]=[]
   for job in jobs(config,lane):
    try:brackets[lane].append(compare.load(job))
    except (AssertionError,ValueError,OSError,KeyError) as error:
     raise ValueError(job['out']+': '+(str(error) or type(error).__name__)) from error
  ratios={}
  for lane,rows in brackets.items():
   compare.compare(rows,('control','candidate','control'))
   ratios[lane]=rows[1]['rate']/max(rows[0]['rate'],rows[-1]['rate'])
   assert ratios[lane]>=1.01,'composition needs >=1.0% over both '+lane+' controls'
  assert brackets['A'][1]['acceptance_counts']==brackets['B'][1]['acceptance_counts'],'candidate acceptance differs across fresh lanes'
  return dict(passed=True,ratios=ratios,brackets=brackets,evidence_rule='bundle7-identical-selection-v1',new_performance_claim=False)
 finally:compare.view,compare.output=original_view,original_output

def evaluate():
 path,config=current();row=dict(schema='packet124.ready.v1',ready=False,device_executed=False,evidence_rule='bundle7-identical-selection-v1',decision=str(path.relative_to(ROOT)),decision_sha256=sha(path),selection=config['candidate'],chain_output='device-cards01-a',other_lane_pause_required=False,timing_exclusivity='Existing whole-host timing windows still acquire their normal exclusive reservation')
 row['chain_command']=f"systemd-run --user --unit=packet124b-chain-a --property=Restart=no --property=Nice=0 '--property=CPUAffinity=0-3 16-19' --property=KillMode=process --property=SendSIGKILL=no --property=ExitType=cgroup --property=TimeoutStopSec=infinity --working-directory={ROOT} /usr/bin/taskset -c 0-3,16-19 /usr/bin/bash {O/'device-entry.sh'} chain {P/'build/device-cards01-a'} </dev/null"
 try:
  from drain_check import check as check_drain
  row['drain_fix']=check_drain()
  from argument_gate import verify as verify_arguments
  verify_arguments();row['argument_gate_sha256']=sha(O/'evidence/argument-gate.json')
  validate(config)
  from policy_seal import verify as verify_policy
  verify_policy()
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
  assert config['composition_kind']=='bundle7-identical'
  try:row['smoke']=inherited_smoke()
  except (AssertionError,ValueError,OSError,KeyError) as error:
   raise ValueError('packet118-smoke12-B has not passed complete exact smoke validation: '+(str(error) or type(error).__name__)) from error
  row['composition']=matched(config)
  from source_decision import read_sources,decide
  current_sources=decide(read_sources());assert all(config['candidate'][k]==v for k,v in current_sources.items()),'source evidence changed'
  from storage import precheck
  row['storage']=precheck();assert row['storage']['passed'],'storage admission refused'
  row['ready']=True;row['pins']={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('build-receipt.json','submission-pins.json','startup103.json')}
 except (AssertionError,ValueError,OSError,KeyError) as error:row['reason']=str(error) or type(error).__name__
 return row

def verify():
 stored=json.loads((O/'ready.json').read_text());actual=evaluate()
 assert stored['ready'] is True and actual['ready'] is True,actual.get('reason','stored readiness is false')
 for key in ('decision_sha256','selection','chain_output','pins'):assert stored[key]==actual[key],key+' changed'
 return actual
if __name__=='__main__':
 try:print(json.dumps(verify(),indent=2))
 except (AssertionError,ValueError,OSError,KeyError) as e:raise SystemExit('REFUSED: '+str(e))

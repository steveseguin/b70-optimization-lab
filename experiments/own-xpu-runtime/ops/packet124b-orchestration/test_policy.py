"""Real policy boundaries with synthetic receipt rows; no device execution."""
import copy,json,subprocess,sys
from unittest.mock import patch
import pytest
import source_decision as s
import composite_jobs as c
import verify_ready as ready

def rows(lane,rate):
 return [dict(choice=label,rate=rate if label=='candidate' else 100.,all_13_exact=True,exact=True,exact_count=13,lane=lane,acceptance_counts=[dict(prompt_id='fixture',hits=7 if label=='candidate' else 8,guesses=10)],acceptance=.7 if label=='candidate' else .8,boot_id='fixture',started_utc_ns=2*i+1,finished_utc_ns=2*i+2) for i,label in enumerate(('control','candidate','control'))]

def matched(a=101.,b=101.,change=lambda x:None):
 import compare
 fixture={lane:rows(lane,rate) for lane,rate in [('A',a),('B',b)]};change(fixture)
 _,config=c.current()
 with patch('policy_seal.verify'),patch('chain_adapter.install'),patch.object(compare,'load',side_effect=lambda j:fixture[j['lane']][j['index']]):return ready.matched(config)

def test_one_selection_only():
 from bundle_selection import views
 assert len(views())==1 and {v[-1] for v in views().values()}=={'80128'}

def test_actual_decision_and_control():
 _,config=c.current();c.validate(config)
 assert c.view(config['control']).parent.parent.name=='packet103-record-bundle'
 assert c.view(config['candidate']).parent.parent.name=='packet124b-record-bundle'

@pytest.mark.parametrize('field,value',[('draft_prefix','79872'),('other_fusion','production'),('target_head','production')])
def test_no_retune_or_dimension_omission(field,value):
 _,config=c.current();config=copy.deepcopy(config);config['candidate'][field]=value
 with pytest.raises(AssertionError):c.validate(config)

def test_preregistration_binding():
 sources=s.read_sources();prefix=json.loads((s.O/'inputs/prefix-selection.json').read_text())
 assert prefix['draft_vocab_rows']==80128
 assert prefix['preregistration_sha256']==sources['prefix-preregistration.json']['sha256']

def test_source_snapshot_tampering():
 _,config=c.current();config=copy.deepcopy(config);config['sources']['prefix-selection.json']['sha256']='0'*64
 with pytest.raises(AssertionError):c.validate(config)

def test_identical_selection_refusal():
 _,config=c.current();config=copy.deepcopy(config);config['candidate']=config['control']
 with pytest.raises(AssertionError,match='identical'):ready.matched(config)

@pytest.mark.parametrize('lane',['A','B'])
def test_below_one_percent_refused(lane):
 rates={'a':101.1,'b':101.1};rates[lane.lower()]=100.999
 with pytest.raises(AssertionError,match='>=1.0%.*'+lane):matched(**rates)

def test_exact_one_percent_both_lanes():assert matched()['passed']

def test_stronger_control_not_mean():
 def change(r):r['B'][2]['rate']=100.2
 with pytest.raises(AssertionError,match='>=1.0%.*B'):matched(101.1,101.1,change)

def test_different_prefix_acceptance_allowed():assert matched()['passed']

def test_control_acceptance_repeat_required():
 def change(r):r['B'][2]['acceptance_counts']=[]
 with pytest.raises(ValueError,match='control acceptance'):matched(change=change)

def test_candidate_deterministic_across_lanes():
 def change(r):r['B'][1]['acceptance_counts']=[]
 with pytest.raises(AssertionError,match='candidate acceptance'):matched(change=change)

def test_every_prompt_exact():
 def change(r):r['A'][1]['all_13_exact']=False
 with pytest.raises(ValueError):matched(change=change)

def test_six_original_bundle7_outputs():
 _,config=c.current();jobs=c.jobs(config,'A')+c.jobs(config,'B')
 assert len({j['out'] for j in jobs})==6
 assert all(j['out'].startswith('p118-89f2d60778eb2d6e-composite-') for j in jobs)
 assert len({j['out'] for j in jobs if j['lane']=='A'})==3
 assert c.evidence_view(config['candidate']).parent.parent.name=='packet118-record-bundle'

def test_chain_fresh():assert not (s.P/'build/device-cards01-a').exists()

def test_device_imports_preserve_every_limit():
 code='import resource; kinds={getattr(resource,k) for k in dir(resource) if k.startswith("RLIMIT_")}; before={k:resource.getrlimit(k) for k in kinds}; import composite_screen,verify_ready,source_decision,chain_entry; assert before=={k:resource.getrlimit(k) for k in kinds}; assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)'
 subprocess.run([sys.executable,'-B','-c',code],cwd=s.O,stdin=subprocess.DEVNULL,check=True)

def test_smoke_pending_cannot_unlock():
 lineage=s.parent_candidate_view()
 root=c.WRAPPER/'evidence'/('p118-'+s.sha(lineage/'screen-seal.json')[:12]+'-B-smoke12')
 if not (root/'window.json').exists():
  with pytest.raises((ValueError,AssertionError,OSError)):ready.inherited_smoke()
 else:assert ready.inherited_smoke()['passed']

def test_drain_scan_is_a_hard_gate():
 with patch('drain_check.check',side_effect=AssertionError('drain-fix hard gate failed')):
  result=ready.evaluate()
 assert result['ready'] is False and 'drain-fix' in result['reason']

def test_changed_candidate_cannot_borrow_parent_results():
 _,config=c.current();config=copy.deepcopy(config);config['candidate']['draft_prefix']='91392'
 with pytest.raises(AssertionError,match='identical selections'):c.jobs(config,'A')

def test_native_memory_and_selection_are_identical():
 _,config=c.current();candidate=c.view(config['candidate']);parent=s.parent_candidate_view()
 for name in ('selection.json','memory-plan.json','dispatch-speed6.json','build/device/own-rt-iq3','build/gnu-host/own-rt-iq3'):
  assert s.sha(candidate/name)==s.sha(parent/name)

def test_parent_chain_state_is_not_a_runtime_pin():
 receipt=json.loads((s.P/'build-receipt.json').read_text())
 forbidden=('packet118-record-bundle/build-receipt.json','packet118-record-bundle/bundle-selection.json',
            'packet118-record-bundle/selection.json','packet118-orchestration/ready.json',
            'packet118-record-bundle/build/device-cards01-')
 assert not any(any(item in name for item in forbidden) for name in receipt['sources'])

def test_real_chain_import_uses_fixed_drain():
 code='from pathlib import Path; from chain_adapter import install,P; install(); import chain103; q,w=chain103.install(); import window_adapter,drain_gate; assert Path(drain_gate.__file__).resolve()==P/"drain_gate.py"; assert window_adapter.DrainPermit is drain_gate.DrainPermit'
 subprocess.run([sys.executable,'-B','-c',code],cwd=s.O,stdin=subprocess.DEVNULL,check=True)

def test_slot_configuration_does_not_enable_unqualified_levers():
 slots=json.loads((s.P/'extension-slots.json').read_text())
 assert slots['sealed_now']==['bundle7-identical-base'] and slots['maximum_followup_compositions']==1
 assert set(slots['slots'])=={'116','117','119','120','122','123'}

def test_complete_readiness_path_with_synthetic_device_evidence():
 # Actual source, selection, startup, drain, limit, storage and chain gates.
 # Only unavailable device receipts and this in-flight test receipt are mocked.
 original=ready.sha
 def digest(path):return 'synthetic-test-receipt' if path==s.O/'cpu-tests.json' else original(path)
 with patch.object(ready,'matched',return_value=dict(passed=True,synthetic=True)),patch.object(ready,'inherited_smoke',return_value=dict(passed=True,synthetic=True)),patch('orchestrate.verify_tests',return_value=dict(passed=True,synthetic=True)),patch.object(ready,'sha',side_effect=digest):
  result=ready.evaluate()
 assert result['ready'] is True,result.get('reason')
 assert result['other_lane_pause_required'] is False and result['drain_fix']['passed']

def test_missing_composite_identifies_exact_output():
 import compare
 _,config=c.current()
 with patch('policy_seal.verify'),patch('chain_adapter.install'),patch.object(compare,'load',side_effect=FileNotFoundError('no receipt')):
  with pytest.raises(ValueError,match='p118-.*-composite-A-0-control: no receipt'):ready.matched(config)

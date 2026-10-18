"""CPU-only policy and full readiness rehearsal; synthetic evidence never leaves tests."""
import copy,json,subprocess,sys
from unittest.mock import patch
import pytest
import source_decision as s
import composite_jobs as c
import verify_ready as ready

def fixture(lane='A',rate=100.5):
 return dict(selection_sha256='synthetic-same-selection',result=dict(passed=True,kind='bracket',model_lifetimes=1,views=[dict(choice=choice,rate=rate if choice=='candidate' else 100.,all_13_exact=True,exact_count=13,lane=lane,acceptance_counts=[dict(prompt_id='fixture',hits=7,guesses=10)]) for choice in ('control','candidate','control','candidate','control')]))
def matched(a=100.5,b=100.5,change=lambda x:None):
 rows={lane:fixture(lane,rate) for lane,rate in [('A',a),('B',b)]};change(rows)
 _,config=c.current()
 with patch.object(ready,'read_device',side_effect=lambda path,lane,kind:rows[lane]):return ready.matched(config)

def test_exactly_two_selections():
 from bundle_selection import views
 assert len(views())==2 and {v[-1] for v in views().values()}=={'production','interleave'}
 _,cfg=c.current();c.validate(cfg)
 assert set(k for k in cfg['candidate'] if cfg['candidate'][k]!=cfg['control'][k])=={'suffix_schedule'}

@pytest.mark.parametrize('field,value',[('draft_prefix','91392'),('other_fusion','production'),('target_head','production'),('suffix_schedule','unknown')])
def test_no_retune_or_extra_arm(field,value):
 _,cfg=c.current();cfg=copy.deepcopy(cfg);cfg['candidate'][field]=value
 with pytest.raises(AssertionError):c.validate(cfg)

def test_preregistered_prefix():
 rows=s.read_sources();prefix=json.loads((s.O/'inputs/prefix-selection.json').read_text())
 assert prefix['draft_vocab_rows']==80128 and prefix['preregistration_sha256']==rows['prefix-preregistration.json']['sha256']

def test_source_tampering():
 _,cfg=c.current();cfg=copy.deepcopy(cfg);cfg['sources']['suffix-native.json']['sha256']='0'*64
 with pytest.raises(AssertionError):c.validate(cfg)

def test_identical_control_candidate_refused():
 _,cfg=c.current();cfg=copy.deepcopy(cfg);cfg['candidate']=cfg['control']
 with pytest.raises(AssertionError,match='identical'):ready.matched(cfg)

@pytest.mark.parametrize('lane',['A','B'])
def test_both_lanes_required(lane):
 rates={'a':100.6,'b':100.6};rates[lane.lower()]=100.499
 with pytest.raises(AssertionError,match='0.5%'):matched(**rates)

def test_exact_half_percent_passes():assert matched()['passed']

def test_slower_candidate_against_fastest_control():
 def change(rows):rows['B']['result']['views'][4]['rate']=100.2
 with pytest.raises(AssertionError,match='0.5%'):matched(100.6,100.6,change)

def test_one_good_repeat_insufficient():
 def change(rows):rows['B']['result']['views'][3]['rate']=100.49
 with pytest.raises(AssertionError,match='0.5%'):matched(102,102,change)

@pytest.mark.parametrize('index',range(5))
def test_every_view_exact(index):
 row=fixture();row['result']['views'][index]['all_13_exact']=False
 with pytest.raises(AssertionError,match='exact'):ready.qualify_bracket(row,'A')

@pytest.mark.parametrize('value',[float('nan'),float('inf'),0,-1,True])
def test_invalid_rates(value):
 row=fixture();row['result']['views'][1]['rate']=value
 with pytest.raises(AssertionError,match='rates'):ready.qualify_bracket(row,'A')

def test_drift_refusal():
 row=fixture(rate=110);row['result']['views'][0]['rate']=96
 with pytest.raises(AssertionError,match='drift'):ready.qualify_bracket(row,'A')

def test_acceptance_repeat_refusal():
 row=fixture();row['result']['views'][3]['acceptance_counts']=[]
 with pytest.raises(AssertionError,match='acceptance'):ready.qualify_bracket(row,'A')

def test_cross_lane_identity():
 def change(rows):rows['B']['selection_sha256']='different'
 with pytest.raises(AssertionError,match='identical-selection'):matched(change=change)

def test_cross_lane_acceptance():
 def change(rows):
  for view in rows['B']['result']['views']:view['acceptance_counts']=[]
 with pytest.raises(AssertionError,match='acceptance'):matched(change=change)

def test_missing_or_failed_bracket_not_pass():
 _,cfg=c.current()
 with patch.object(ready,'read_device',side_effect=ValueError('missing B receipt')):
  with pytest.raises(ValueError,match='missing B'):ready.matched(cfg)

def test_chain_fresh():assert not (s.P/'build/device-cards01-a').exists()

def test_native_selection_and_binary_identical():
 from reuse_build import verify_native
 verify_native()

def test_limits_unchanged_on_import():
 code='import resource; kinds={getattr(resource,k) for k in dir(resource) if k.startswith("RLIMIT_")}; before={k:resource.getrlimit(k) for k in kinds}; import verify_ready,source_decision,chain_entry; assert before=={k:resource.getrlimit(k) for k in kinds}; assert resource.getrlimit(resource.RLIMIT_AS)==(-1,-1)'
 subprocess.run([sys.executable,'-B','-c',code],cwd=s.O,stdin=subprocess.DEVNULL,check=True)

def test_drain_hard_gate():
 with patch('drain_check.check',side_effect=AssertionError('drain-fix sentinel')):row=ready.evaluate()
 assert row['ready'] is False and 'drain-fix sentinel' in row['reason']

def test_pending_smoke_refused():
 with patch.object(ready,'read_device',side_effect=ValueError('no smoke')):
  with pytest.raises(ValueError,match='no smoke'):ready.smoke()

@pytest.mark.parametrize('key,value',[('request_count',11),('max_new',128),('passed',False)])
def test_incomplete_composed_smoke(key,value):
 row=dict(result=dict(passed=True,kind='smoke',request_count=12,max_new=64));row['result'][key]=value
 with patch.object(ready,'read_device',return_value=row),pytest.raises(AssertionError):ready.smoke()

def test_full_readiness_with_only_device_evidence_synthetic():
 original=ready.sha
 def digest(path):return 'synthetic-tests' if path==s.O/'cpu-tests.json' else original(path)
 composition=dict(passed=True,lanes={'A':dict(selection_sha256='synthetic'),'B':dict(selection_sha256='synthetic')})
 with patch.object(ready,'matched',return_value=composition),patch.object(ready,'smoke',return_value=dict(passed=True,selection_sha256='synthetic')),patch('orchestrate.verify_tests',return_value=dict(passed=True)),patch.object(ready,'sha',side_effect=digest):row=ready.evaluate()
 assert row['ready'] is True,row.get('reason')
 assert row['cpu_preparation_ready'] and row['drain_fix']['passed']

def test_slot131_disabled():
 slots=json.loads((s.P/'extension-slots.json').read_text())
 assert len(slots['sealed_now'])==2 and slots['maximum_followup_compositions']==0
 assert set(slots['slots'])=={'131'} and 'disabled' in slots['slots']['131']['status']

def test_proposal_not_queue():
 from proposal_plan import verify,PROPOSAL
 row=verify();assert PROPOSAL.name=='proposed-p133-v5-A.txt'
 assert row['watchdog_seconds']>=4*max(row['expected_seconds']) and row['live_queue_modified'] is False

def test_submission_cli_complete():
 from submission import load_submitter
 assert callable(load_submitter().main)

def test_screen_copy_changes_only_output_and_worker_location():
 frozen=s.P.with_name('packet130-suffix-interleave')/'v5/screen.py'
 expected=frozen.read_text().replace("args.output.is_relative_to(HERE / 'evidence')", "args.output.is_relative_to(Path(__file__).resolve().parent / 'evidence')").replace("str(Path(__file__).with_name('tp2_worker.py'))", "str(HERE/'tp2_worker.py')")
 assert (s.P/'v5/screen133.py').read_text()==expected

def test_launch_environment_is_embedded():
 driver=(s.P/'v5/bracket_job.py').read_text();entry=(s.O/'device-entry.sh').read_text()
 assert 'os.environ.clear();os.environ.update(' in driver and 'LD_LIBRARY_PATH' in driver
 assert 'P49_LDP' not in entry and 'source /tmp/' not in entry and 'env -i' in entry
 assert 'verify_cpu.py' in driver

def test_cpu_only_readiness_entry():
 from verify_cpu import verify
 with patch('orchestrate.verify_tests',return_value=dict(passed=True)):
  assert verify()['device_executed'] is False

def test_only_memory_view_label_may_differ():
 from evidence_reader import same_memory_layout
 assert same_memory_layout(dict(view='bundle8',allocation=42),dict(view='bundle7',allocation=42))
 with pytest.raises(ValueError,match='allocation'):
  same_memory_layout(dict(view='bundle8',allocation=43),dict(view='bundle7',allocation=42))
 with pytest.raises(ValueError):same_memory_layout(dict(allocation=42),dict(view='bundle7',allocation=42))

def test_both_lanes_are_read_even_if_one_is_pending():
 _,cfg=c.current();seen=[]
 def pending(path,lane,kind):
  seen.append(lane)
  if lane=='A':raise ValueError('pending A')
  return fixture('B',100)
 with patch.object(ready,'read_device',side_effect=pending),pytest.raises(ValueError,match='pending A.*0.5%'):
  ready.matched(cfg)
 assert seen==['A','B']

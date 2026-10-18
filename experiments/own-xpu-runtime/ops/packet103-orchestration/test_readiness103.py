"""Synthetic policy cases; these never count as device evidence."""
import json,copy
from pathlib import Path
import pytest
import decision_readiness as d
BOOT=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def bracket(lane,rates=(100.,101.,100.)):
 return dict(lane=lane,rows=[dict(choice=c,rate=r,lane=lane,exact=True,exact_count=13,all_13_exact=True,acceptance=.7,acceptance_counts=[[7,10]],boot_id=BOOT,started_utc_ns=3*i+1,finished_utc_ns=3*i+2) for i,(c,r) in enumerate(zip(('control','candidate','control'),rates))])
def evidence():return [bracket('A'),bracket('A'),bracket('B'),bracket('B',(100.,100.8,101.))]
def test_all_brackets_count():
 r=d.evaluate(evidence(),['91','90','101']);assert r['passed'] and len(r['brackets'])==4 and r['chain_policy_passed']
def test_a_loss_not_hidden():
 r=d.evaluate(evidence()+[bracket('A',(100.,99.,100.))],['91','90']);assert not r['passed']
def test_b_loss_not_hidden():
 r=d.evaluate(evidence()+[bracket('B',(100.,99.,100.))],['91','90']);assert not r['passed']
@pytest.mark.parametrize('change',[dict(exact=False),dict(exact_count=12),dict(acceptance_counts=[]),dict(boot_id='old')])
def test_invalid_evidence_refuses(change):
 r=evidence();r[0]['rows'][1].update(change);assert not d.evaluate(r,['91','90'])['passed']
def test_missing_lane_refuses():assert not d.evaluate([bracket('A')],['91','90'])['passed']
@pytest.mark.parametrize('field',d.IDENTITY_FIELDS)
def test_identity_must_match(field):
 expected={k:k for k in d.IDENTITY_FIELDS};assert d.identical(expected,expected)
 changed=dict(expected);changed[field]='different';assert not d.identical(changed,expected)
def test_single_lever_needs_one_point_five_percent():assert not d.evaluate(evidence(),['101'])['chain_policy_passed']
def test_fresh_folder(tmp_path,monkeypatch):
 from fresh_chain import output
 monkeypatch.setattr(d.o,'P',tmp_path);(tmp_path/'build/device-cards01-a').mkdir(parents=True)
 with pytest.raises(AssertionError):output('device-cards01-a')
 assert output('device-cards01-b')==tmp_path/'build/device-cards01-b'
 with pytest.raises(AssertionError):output('../bad')

@pytest.mark.parametrize('row,reason',[
 (dict(status='no-winner',record_lane_veto=dict(reason='A loss')), 'later record-lane A veto'),
 (dict(status='failed',reason='broken receipt'), 'current source evidence invalid')])
def test_later_source_veto_blocks_frozen_decision(monkeypatch,row,reason):
 import read_screens as reader
 from types import SimpleNamespace
 monkeypatch.setattr(reader.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout=json.dumps(row),stderr=''))
 with pytest.raises(ValueError,match=reason):reader.reject_later_record_lane_losses(dict(confirmed_levers=['100']))

def test_window_arrival_during_read_refuses(tmp_path):
 import read_screens as reader
 path=tmp_path/'window.json';screens={'100':dict(observed_windows={str(path):None})}
 reader.require_current(screens)
 path.write_text('{}')
 with pytest.raises(ValueError,match='results changed during decision'):reader.require_current(screens)

def test_fresh_chain_readiness_replays_matching_entry_tag(tmp_path,monkeypatch):
 import fresh_chain
 config=dict(candidate={'down':'tile16'},confirmed_levers=['100'])
 result=dict(passed=True,chain_policy_passed=True)
 for attr in ('P','O','ROOT'):monkeypatch.setattr(d.o,attr,tmp_path)
 monkeypatch.setattr(d.o,'command',lambda:'legacy-command')
 monkeypatch.setattr(fresh_chain,'command',lambda name:'fresh-command-'+name)
 calls=[];monkeypatch.setattr(fresh_chain,'startup',lambda:calls.append('startup'))
 monkeypatch.setattr(d,'validate',lambda config:None)
 monkeypatch.setattr(d,'matched',lambda config:result)
 monkeypatch.setattr(d,'preparation_config',lambda config,path:config)
 (tmp_path/'chain-registration.json').write_text(json.dumps({'output':'device-cards01-c'}))
 (tmp_path/'composition-selection.json').write_text(json.dumps(config))
 decision=tmp_path/'decision.json';decision.write_text(json.dumps(config))
 checks={}
 for label in ('cpu-dry-run','seal','inputs','storage','queue-plan'):
  path=tmp_path/(label+'.log');path.write_text('synthetic test only');checks[label]=d.o.sha(path)
 row=dict(schema='packet103.ready.v1',ready=True,preparation_passed=True,device_executed=False,
  evidence_rule=d.RULE,chain_entry='packet103',chain_output='device-cards01-c',
  chain_command='fresh-command-device-cards01-c',boot_id=BOOT,checks=checks,pins={},
  decision='decision.json',decision_sha256=d.o.sha(decision),selection=config['candidate'],
  qualified_sources=config['confirmed_levers'],composition=result)
 assert d.verify(row)==row and calls==['startup']
 with pytest.raises(AssertionError):d.verify(dict(row,chain_entry='packet103e'))

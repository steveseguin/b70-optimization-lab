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

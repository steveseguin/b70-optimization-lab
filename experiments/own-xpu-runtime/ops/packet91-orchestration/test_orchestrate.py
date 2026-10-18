"""Matched composition, default-only pins, isolated readiness and no-launch tests."""
import copy,json,sys,types
from pathlib import Path
import pytest
import orchestrate as o
from screen_jobs import ORDER

def rows(lane,order,choice='route-fast'):
 return [dict(choice=c,lane=lane,rate=12. if c==choice else 10.,acceptance=.78,all_13_exact=True,exact=True,exact_count=13,boot_id='boot',started_utc_ns=i*3+1,finished_utc_ns=i*3+2) for i,c in enumerate(order)]
def winner(choice='route-fast'):
 return dict(status='winner',best=dict(choice=choice,ratio=1.2),confirmation=dict(choice=choice,ratio=1.2),lanes={'A':rows('A',ORDER,choice),'B':rows('B',('control',choice,'control'),choice)})
def test_baseline_and_composed_winners():
 base=o.select({});assert base['recurrence']=='rec-parallel' and base['route']=='production'
 for c in tuple(o.VIEWS)[1:]:assert o.select({'91':winner(c)})==dict(o.VIEWS[c],expert_hc='none')
 with pytest.raises(ValueError):o.select({'90':dict(status='winner')})
@pytest.mark.parametrize('bad',[.9,1.,float('nan'),float('inf'),True])
def test_both_lane_rate_gate(bad):
 w=winner();w['confirmation']['ratio']=bad
 with pytest.raises(ValueError):o.select({'91':w})
@pytest.mark.parametrize('mutate',[
 lambda w:w['lanes'].pop('B'),lambda w:w['lanes']['B'][0].update(exact_count=12),
 lambda w:w['confirmation'].update(choice='rec-both-plus'),
 lambda w:w['lanes']['B'][-1].update(rate=13),lambda w:w['lanes']['B'][0].update(all_13_exact=False),
 lambda w:w['lanes']['B'][1].update(boot_id='other'),lambda w:w['lanes']['B'][1].update(started_utc_ns=1),
 lambda w:w['lanes']['B'][1].update(rate=float('nan'))])
def test_invalid_matched_evidence(mutate):
 w=winner();mutate(w)
 with pytest.raises(ValueError):o.select({'91':w})
def test_default_only_pins():
 chosen=o.select({'91':winner('route-fast-rec-both-plus')})
 assert o.apply_pins(chosen,['route=production','recurrence=rec-parallel'])[0]==o.DEFAULTS
 for pins in (['route=fast'],['recurrence=rec-both-plus'],['placement=0'],['unknown=x'],['route=production','route=production']):
  with pytest.raises(ValueError):o.apply_pins(chosen,pins)
def test_pending_closure_requires_all_default_pins():
 screens={'91':dict(status='pending')};choice,pins=o.apply_pins(o.DEFAULTS,['route=production','recurrence=rec-parallel'])
 closed=o.close_packets(screens,choice,pins,['91=coordinator closed these levers']);assert closed and screens['91']['status']=='no-winner'
 for state,pins,value in [('winner',pins,'91=x'),('pending',{},'91=x'),('pending',pins,'91='),('pending',pins,'999=x')]:
  with pytest.raises(ValueError):o.close_packets({'91':dict(status=state)},choice,pins,[value])
@pytest.mark.parametrize('status,expected',[('no-winner',True),('pending',False)])
def test_ready_with_temp_ops_directory(tmp_path,monkeypatch,status,expected):
 # Regressions for both p84 failures: pinning temp O must not relative_to(ROOT).
 calls=[];monkeypatch.setattr(o,'O',tmp_path);monkeypatch.setattr(o,'sha',lambda p:'a'*64)
 monkeypatch.setattr(o,'run',lambda name,args:calls.append(name));monkeypatch.setattr(o,'limits',lambda:None)
 monkeypatch.setattr(o.subprocess,'run',lambda *a,**k:types.SimpleNamespace(stdout=json.dumps(dict(status=status,lanes={},receipts={},sources={}))))
 monkeypatch.setattr(sys,'argv',['orchestrate.py']);assert o.main()==(0 if expected else 2)
 result=json.loads((tmp_path/'ready.json').read_text());assert result['ready'] is expected and result['preparation_passed'] is True
 assert str(tmp_path/'device-entry.sh') in result['pins']
 assert calls==['reseal','cpu-dry-run','seal','inputs','storage','queue-plan']
def test_no_launch():
 text=(o.O/'orchestrate.py').read_text();assert '--authorized-device-window' not in text
 assert 'systemd-run' in o.command() and 'packet91-chain' in o.command()
 assert 'orchestrate.py' not in (o.P/'dry_run.py').read_text()

"""CPU-only source decisions, stale/invalid refusals, revert pins and temp O."""
import copy,json,sys
from pathlib import Path
import pytest
import orchestrate as o

def screens():return {n:dict(status='no-winner',receipts={},sources={}) for n in o.DIMENSIONS}
def winner(choice,rate=10.2):
 rows={lane:[dict(choice=c,lane=lane,rate=rate if i==1 else 10.,acceptance_counts=[[64,100]],exact=True,exact_count=13,boot_id='boot',started_utc_ns=i*3+1,finished_utc_ns=i*3+2) for i,c in enumerate(('production',choice,'production'))] for lane in ('A','B')}
 return dict(status='winner',winner=choice,ratios={'A':rate/10,'B':rate/10},lanes=rows,receipts={},sources={})
def all_winners():
 s=screens()
 for n,c in [('91','route-fast-rec-both-plus'),('93','head-transpose'),('92','reply-first'),('94','hc-normfuse'),('95','exp-grid-prefetch'),('90','exp-halfcache')]:s[n]=winner(c)
 return s

def test_all_dimensions_and_composition():
 control,candidate,confirmed=o.select(all_winners());assert control['route']=='fast' and control['recurrence']=='rec-both-plus'
 assert candidate['experts']=='wide64+grid-prefetch+halfcache' and candidate['head']=='head-transpose' and candidate['host']=='ordered+reply-first' and candidate['hc_norm']=='normfuse'
 assert len(confirmed)==5
 assert o.select(screens())[:2]==(o.DEFAULTS,o.DEFAULTS)
@pytest.mark.parametrize('mutate',[
 lambda r:r['lanes'].pop('B'),lambda r:r['lanes']['B'][0].update(exact_count=12),lambda r:r['lanes']['B'][1].update(exact=False),lambda r:r['lanes']['B'][-1].update(rate=11),lambda r:r['lanes']['B'][1].update(rate=float('nan')),lambda r:r['lanes']['B'][0].update(boot_id='other'),lambda r:r['lanes']['B'][1].update(started_utc_ns=1),lambda r:r['lanes']['B'][0].update(acceptance_counts=[[63,100]]),lambda r:r['ratios'].update(A=2.)])
def test_invalid_or_unbracketed_winner(mutate):
 s=all_winners();mutate(s['93'])
 with pytest.raises((AssertionError,ValueError)):o.select(s)
@pytest.mark.parametrize('number,choice',[('90','hc-weightcache'),('93','head-plane'),('94','hc-normfuse+weightcache')])
def test_closed_choices_refused(number,choice):
 s=screens();s[number]=winner(choice)
 with pytest.raises(ValueError):o.select(s)
def test_revert_only_pins():
 _,candidate,_=o.select(all_winners());reverted,pins=o.apply_pins(candidate,['experts=wide64','head=production']);assert reverted['experts']=='wide64' and reverted['head']=='production'
 for values in (['head=head-transpose'],['experts=wide64+halfcache'],['unknown=x'],['head=production','head=production']):
  with pytest.raises(ValueError):o.apply_pins(candidate,values)
def test_pending_closure_explicit_baseline():
 s=screens();s['91']['status']='pending';choice,pins=o.apply_pins(o.DEFAULTS,['route=production','recurrence=rec-parallel']);assert o.close_packets(s,choice,pins,['91=source tests closed'])
 for status,pins,value in [('failed',pins,'91=x'),('winner',pins,'91=x'),('pending',{},'91=x'),('pending',pins,'91=')]:
  s=screens();s['91']['status']=status
  with pytest.raises(ValueError):o.close_packets(s,choice,pins,[value])
def test_only_retained_confirmed_levers_count():
 s=all_winners();control,candidate,confirmed=o.select(s);candidate,pins=o.apply_pins(candidate,['experts=wide64']);c=o.composition(s,control,candidate,confirmed,pins,{})
 assert set(c['confirmed_levers'])=={'92','93','94'}
 s['90']['status']='pending'
 with pytest.raises(AssertionError):o.composition(s,control,candidate,confirmed,pins,{})
def test_ready_with_temp_ops_directory(tmp_path,monkeypatch):
 # Packet84 regression: an external temporary O must remain an absolute pin.
 import read_screens
 packet=tmp_path/'packet';packet.mkdir();(packet/'composition-selection.json').write_text('{}')
 monkeypatch.setattr(o,'O',tmp_path);monkeypatch.setattr(o,'P',packet);monkeypatch.setattr(o,'limits',lambda:None);monkeypatch.setattr(o,'sha',lambda p:'a'*64)
 monkeypatch.setattr(read_screens,'collect',all_winners);calls=[]
 monkeypatch.setattr(o,'run',lambda label,args:calls.append(label));monkeypatch.setattr(o,'matched_composition',lambda config:dict(passed=True));monkeypatch.setattr(sys,'argv',['orchestrate.py'])
 assert o.main()==0
 result=json.loads((tmp_path/'ready.json').read_text());assert result['ready'] and result['preparation_passed']
 assert o.pin_path(tmp_path/'device-entry.sh') in result['pins'];assert o.pin_path(tmp_path/'device-entry.sh')==str(tmp_path/'device-entry.sh')
 assert calls==['composition-queue-plan','reseal','cpu-dry-run','seal','inputs','storage','queue-plan']
def test_pending_never_ready(tmp_path,monkeypatch):
 import read_screens
 s=screens();s['93']['status']='pending';monkeypatch.setattr(read_screens,'collect',lambda:s);monkeypatch.setattr(o,'O',tmp_path);monkeypatch.setattr(o,'limits',lambda:None);monkeypatch.setattr(sys,'argv',['orchestrate.py'])
 monkeypatch.setattr(o,'run',lambda *a:pytest.fail('must not prepare unresolved selection'))
 assert o.main()==2 and not json.loads((tmp_path/'ready.json').read_text())['ready']
def test_no_device_launch_and_pending_verifier(tmp_path,monkeypatch):
 import verify_ready as v
 assert '--authorized-device-window' not in (o.O/'orchestrate.py').read_text()
 assert 'packet97-chain' in o.command()
 monkeypatch.setattr(v,'O',tmp_path);(tmp_path/'ready.json').write_text(json.dumps(dict(schema='packet97.ready.v1',ready=False)))
 with pytest.raises(AssertionError):v.verify()

"""CPU-only confirmation, pin, direction and no-launch regressions."""
import copy,json,sys,types
from pathlib import Path
from unittest.mock import patch
import pytest
import orchestrate as o
import read_screens as r
def winner(choice):
 return dict(status='winner',best=dict(choice=choice,ratio=1.03),confirmation=dict(choice=choice,ratio=1.01),lanes={lane:[dict(exact=True,exact_count=13)]*3 for lane in ('A','B')})
def test_baseline_and_all_independent_winners():
 base=o.select({});assert base['host']=='ordered' and base['hc']=='hc-wide' and base['route']==base['norm']=='production'
 s=o.select({'81':winner('input-packed'),'82':winner('rec-parallel'),'83':winner('prefix985')})
 assert (s['experts'],s['recurrence'],s['draft_head'])==('input-packed','rec-parallel','prefix985')
 assert s['host']==base['host'] and s['placement']=='1'
@pytest.mark.parametrize('bad',[0.9,1.0,float('nan'),float('inf'),True])
def test_both_lane_rate_gate(bad):
 w=winner('input-packed');w['confirmation']['ratio']=bad
 with pytest.raises(ValueError):o.select({'81':w})
def test_exact_missing_and_different_confirmation():
 for mutate in (lambda w:w['lanes'].pop('B'),lambda w:w['lanes']['B'][0].update(exact_count=12),lambda w:w['confirmation'].update(choice='other')):
  w=winner('input-packed');mutate(w)
  with pytest.raises(ValueError):o.select({'81':w})
 assert o.select({'81':dict(status='pending')})['experts']=='wide64'
def test_pins_only_revert_defaults():
 selected=o.select({'81':winner('input-packed'),'83':winner('q4-g32')})
 assert o.apply_pins(selected,['experts=wide64','draft_head=production','host=production'])[0]['experts']=='wide64'
 for pins in (['experts=production'],['route=fast'],['placement=0'],['unknown=x'],['host=ordered','host=production']):
  with pytest.raises(ValueError):o.apply_pins(selected,pins)
def test_packet83_reverse_confirmation_not_hidden_by_missing_a_grid(tmp_path):
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 def require(ok,reason):
  if not ok:raise ValueError(reason)
 def jobs(lane,choice=None,mode='grid'):
  return [dict(out=lane+'-'+mode+'-'+str(i),choice=c) for i,c in enumerate(['production','q4-g32','prefix990','prefix985','production'] if mode=='grid' else ['production',choice,'production'])]
 def load(job,lane):
  if lane=='A' and '-grid-' in job['out']:raise FileNotFoundError('A grid absent')
  return dict(choice=job['choice'],rate=12 if job['choice']=='q4-g32' else 10,exact=True,acceptance=.9)
 c=types.SimpleNamespace(HERE=tmp_path,cpu_gate=lambda:None,require=require,read=lambda path:{'boot_id':boot},load=load)
 j=types.SimpleNamespace(verify=lambda:None,jobs=jobs,choose=lambda rows:max(rows[1:-1],key=lambda x:x['rate']))
 with patch.dict(sys.modules,compare=c,screen_jobs=j):result=r.collect(83)
 assert result['status']=='winner' and result['source_lane']=='B' and set(result['lanes'])=={'A','B'}
def test_no_launch_code_and_cache_independent_of_coordinator():
 assert '--authorized-device-window' not in (o.O/'orchestrate.py').read_text()
 assert 'systemd-run' in o.command()
 text=(o.P/'dry_run.py').read_text();assert 'ops.glob' not in text and 'orchestrate.py' not in text

@pytest.mark.parametrize('status,expected',[('no-winner',True),('pending',False)])
def test_ready_requires_resolved_screens_and_only_runs_cpu_checks(tmp_path,monkeypatch,status,expected):
 calls=[]
 monkeypatch.setattr(o,'O',tmp_path)
 monkeypatch.setattr(o,'sha',lambda p:'a'*64)
 monkeypatch.setattr(o,'run',lambda name,args:calls.append(name))
 def read(args,**kwargs):
  assert str(args[-2]).endswith('/read_screens.py')
  return types.SimpleNamespace(stdout=json.dumps(dict(status=status,lanes={},receipts={},sources={})))
 monkeypatch.setattr(o.subprocess,'run',read)
 monkeypatch.setattr(sys,'argv',['orchestrate.py'])
 assert o.main()==(0 if expected else 2)
 result=json.loads((tmp_path/'ready.json').read_text())
 assert result['ready'] is expected and result['preparation_passed'] is True
 assert result['selection']==o.select({})
 assert calls==['reseal','cpu-dry-run','seal','inputs','storage','queue-plan']

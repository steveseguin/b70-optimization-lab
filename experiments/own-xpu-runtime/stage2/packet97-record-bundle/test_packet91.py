"""CPU-only composition, dispatch and submission regressions."""
import json,copy,types
from pathlib import Path
import pytest
import bundle_selection as b
import packet56_submission as s
P=Path(__file__).resolve().parent

def bundle(v):
 return dict(zip(b.KEYS,v),name=b.name(*v),placement='1',draft='draft-hc',miss='batch',draft_rank=1,target_split=0,layer_boundary=24)
def test_every_composition_consumed_and_disclosed():
 from merge_dispatch import validate,merge
 dispatch=json.loads((P/'dispatch-speed6.json').read_text());merged,_=merge([dispatch,dispatch]);validate(merged);assert merged==dispatch
 for name,v,p in b.configurations():
  row=bundle(v);s.validate_bundle(row,b.selection(v))
  for resumed in (False,True):
   notes=s.submission_notes(row,resumed=resumed);assert len(notes)<=2000
   assert 'Recurrence='+row['recurrence'] in notes and 'route='+row['route'] in notes
   if row['head']=='production':assert 'prefix rows [0,91,392)' in notes and 'shared 248,320-row head on rank1' in notes
   else:assert 'separate unchanged expanded 91,392-row prefix' in notes and 'packed transposed head' in notes
   assert 'private' not in notes and 'verifies every accepted token' in notes
   assert 'Q4/g32 changes' not in notes
   rank0=dict(row,draft_rank=0);text=s.submission_notes(rank0,resumed=resumed)
   assert 'private 91,392-row prefix copy on rank0; full head on rank1' in text and len(text)<=2000

def test_collect_supplies_frozen_admission_bytes(tmp_path,monkeypatch):
 import receipt_replay
 sidecar=tmp_path/'KD-lane-admission.json';raw=b'{"frozen":"admission bytes"}\n';sidecar.write_bytes(raw)
 window=dict(lane_admission=dict(path=str(sidecar)),receipts=[])
 class StubEvidence:
  def add(self,key,path):return json.dumps(window).encode() if key.endswith('/window.json') else b'{}'
  def read(self,key):return dict(prompts=[]) if key=='oracle/suite-manifest.json' else {}
 calls=[]
 def verify(row,*,data):
  calls.append((row,data));assert data==raw
 monkeypatch.setattr(s,'Evidence',StubEvidence);monkeypatch.setattr(s,'validate_threshold',lambda row:None)
 monkeypatch.setattr(s,'WINDOWS',('KD',));monkeypatch.setattr(receipt_replay,'verify_receipt',verify)
 s.collect(s.P56_PACKET,tmp_path,tmp_path/'oracle',repo=tmp_path)
 assert calls==[(window,raw)]

def test_recurrence_dispatch_normalization(tmp_path,monkeypatch):
 import p49_dispatch as d
 from test_selection_postprocessing import ARCHIVE,P70
 from storage import digest
 import shutil
 pins=json.loads((P70/'evidence/k2fix-archive.json').read_text())['files']
 for n in ('K2/run0/summary.json','K2/run0/dispatch-measured.json','K2/round3-timing/receipt.json','K2/round3-timing/timings.jsonl'):assert digest(ARCHIVE/n)==pins[n]
 for n in ('dispatch-speed6.json','dispatch-speed6-provenance.json','k2-class-registry.json'):shutil.copyfile(P/n,tmp_path/n)
 for name,v in b.views().items():
  run=tmp_path/name;run.mkdir()
  for n in ('summary.json','dispatch-measured.json'):shutil.copyfile(ARCHIVE/'K2/run0'/n,run/n)
  (tmp_path/'selection.json').write_text(json.dumps(b.selection(v)))
  monkeypatch.setattr(d,'P',tmp_path);monkeypatch.setattr(b,'selected',lambda:bundle(v))
  result,policy=d.pin_production_dispatch(run,json.loads((ARCHIVE/'K2/run0/summary.json').read_text()),round3_root=ARCHIVE/'K2/round3-timing')
  assert result['passed'] and policy['packet49d_measured_selection']['passed']
  assert (run/'dispatch-measured.json').read_bytes()==(P/'dispatch-speed6.json').read_bytes()

def test_future_slot_and_unsupported_compositions_refuse():
 for values in (('production','hc-wide','input-packed','ordered','fast','production','rec-parallel','production'),('production','hc-wide','wide64','ordered','fast','production','rec-both','production')):
  with pytest.raises(ValueError):b.name(*values)
 assert 'hc-weightcache' in json.loads((P/'extension-slots.json').read_text())['closed']
 assert len(b.views())==128

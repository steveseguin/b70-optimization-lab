"""Fast selected consumers and safety boundaries; no native device execution."""
import json,copy
from pathlib import Path
import pytest
import bundle_selection as b
from packet56_submission import validate_bundle,submission_notes
from draft_identity import identity,validate_prefix
P=Path(__file__).resolve().parent
def bundle(v,p='1'):
 dr,split,boundary=b.PLACEMENTS[p]
 return dict(zip(b.KEYS,v),name=b.name(*v),placement=p,draft='draft-hc',miss='batch',draft_rank=dr,target_split=split,layer_boundary=boundary)
def test_every_composition_consumed_and_disclosed():
 from merge_dispatch import validate,merge
 dispatch=json.loads((P/'dispatch-speed6.json').read_text());merged,_=merge([dispatch,dispatch]);validate(merged);assert merged==dispatch
 for name,v,p in b.configurations():
  row=bundle(v,p);validate_bundle(row,b.selection(v));notes=submission_notes(row,resumed=True)
  assert len(notes)<=2000
  for key in ('experts','draft_head'):assert key+'='+row[key] in notes
  assert 'Recurrence='+row['recurrence'] in notes
  assert str(b.prefix_rows(v[-1])) in notes and 'verifies every accepted token' in notes
def test_draft_prefix_kd_selection_and_tamper():
 for head in b.DRAFT_HEAD:
  v=('production','hc-wide','wide64','ordered','production','production','production',head)
  expected=identity(bundle(v));prefix=dict(rows=b.prefix_rows(head),full_rows=248320,calibration_sha256=expected['selection_sha256'],target_head_unchanged=True)
  validate_prefix(prefix,expected)
  for key,value in (('rows',1),('calibration_sha256','0'*64),('target_head_unchanged',False)):
   with pytest.raises(ValueError):validate_prefix(dict(prefix,**{key:value}),expected)
def test_unqualified_composition_rejected():
 v=('production','hc-wide','wide64','ordered','production','production','production','q4-g32')
 for p in ('0','0-split23','1-split23'):
  with pytest.raises(ValueError):validate_bundle(bundle(v,p),b.selection(v))
 bad=b.selection(v);bad['draft']['head_prefix']='coverage990'
 with pytest.raises(ValueError):validate_bundle(bundle(v),bad)
def test_real_k2_selected_consumer(tmp_path,monkeypatch):
 import p49_dispatch as d
 from test_selection_postprocessing import ARCHIVE,P70
 from storage import digest
 import shutil
 pins=json.loads((P70/'evidence/k2fix-archive.json').read_text())['files']
 for n in ('K2/run0/summary.json','K2/run0/dispatch-measured.json','K2/round3-timing/receipt.json','K2/round3-timing/timings.jsonl'):assert digest(ARCHIVE/n)==pins[n]
 for n in ('dispatch-speed6.json','dispatch-speed6-provenance.json','k2-class-registry.json'):shutil.copyfile(P/n,tmp_path/n)
 # Exercise the complete new recurrence/expert product through actual K2 logic.
 for expert in b.EXPERTS:
  for rec in b.RECURRENCE:
   run=tmp_path/(expert+'-'+rec);run.mkdir()
   for n in ('summary.json','dispatch-measured.json'):shutil.copyfile(ARCHIVE/'K2/run0'/n,run/n)
   v=('production','hc-wide',expert,'ordered','fast','fused',rec,'q4-g32')
   (tmp_path/'selection.json').write_text(json.dumps(b.selection(v)))
   monkeypatch.setattr(d,'P',tmp_path);monkeypatch.setattr(b,'selected',lambda:bundle(v))
   result,policy=d.pin_production_dispatch(run,json.loads((ARCHIVE/'K2/run0/summary.json').read_text()),round3_root=ARCHIVE/'K2/round3-timing')
   assert result['passed'] and policy['packet49d_measured_selection']['passed']
   assert (run/'dispatch-measured.json').read_bytes()==(P/'dispatch-speed6.json').read_bytes()

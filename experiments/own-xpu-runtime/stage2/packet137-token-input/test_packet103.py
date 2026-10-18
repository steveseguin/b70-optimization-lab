import json,pytest
from pathlib import Path
import bundle_selection as b
from kd_reference import project
P=Path(__file__).resolve().parent

def test_cartesian_selections():
 assert len(b.views())==512
 for label,v in b.views().items():
  assert len(label+'--placement-1')<256
  s=b.selection(v)
  assert s['choices']['experts'].endswith('+down-tile16')==(v[10]=='tile16')
  assert (s['draft']['qsa_attention']=='packet59')==(v[11]=='split32')
  ref=project(s)
  assert ref['draft']==s['draft'] and ref['choices']['experts']=='wide64'

def test_memory_extents():
 from memory_plans import plan
 for v in b.views().values():
  row=plan(v)
  assert row['down_transpose_extra_device_bytes']==0 and row['down_row_bytes']==360
  for rank in row['placements']['1']['capacities']['4096']['ranks']:
   assert rank['arena_margin_passed'] and rank['allocation_margin_passed']

def test_submissions_disclose_new_dimensions():
 import packet56_submission as s
 for v in b.views().values():
  row=dict(zip(b.KEYS,v),name=b.name(*v),placement='1',draft='draft-hc',miss='batch',draft_rank=1,target_split=0,layer_boundary=24)
  s.validate_bundle(row,b.selection(v))
  note=s.submission_notes(row)
  assert 'down='+v[10] in note and 'draft attention='+v[11] in note
  assert len(note)<=2000

def test_startup_complete():
 from startup_receipt103 import verify
 assert verify()['total_windows']==512*11

def test_receipt_fix_presealed():
 text=(P/'packet56_submission.py').read_text()
 assert 'verify_receipt(window, data=' in text
 assert 'validate_kd_projection' in text

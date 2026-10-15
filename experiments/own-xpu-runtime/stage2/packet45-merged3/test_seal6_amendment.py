"""Narrow reuse and device-publication authority regression tests; no execution."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import seal6_amendment as a
sys.path.insert(0,str(a.ROOT/'scripts'))
from promotion_evidence import validate_packet45_device_evidence
class Amendment(unittest.TestCase):
 def test_speed6_scope(self):
  from speed6_qualification import PINS,before
  for n in PINS:
   self.assertTrue(a.source_matches(a.P/n,before()['sources'][str((a.P/n).relative_to(a.ROOT))]))
   self.assertFalse(a.source_matches(a.P/n,'0'*64))
  self.assertEqual(a.verify()['speed6_extension']['sparse_production_rows'],120)
 def test_speed6_short_workspace(self):
  import speed6_qualification as s
  original=s.json.loads
  def mutate(raw,*args,**kwargs):
   row=original(raw,*args,**kwargs)
   if isinstance(row,dict) and row.get('plan_dispatch_rows')==120 and row.get('rows') and 'sparse_workspace' in row['rows'][0]:
    row['rows'][0]['sparse_workspace']['workspace_peak_bytes']=8*1024**2+1
   return row
  with patch.object(s.json,'loads',side_effect=mutate),self.assertRaises(AssertionError):s.verify()
 def test_current(self):self.assertEqual(a.verify()['plan_dispatch_rows'],48)
 def test_speed1_scope(self):
  from speed1_qualification import PINS,before
  for n,h in PINS.items():
   self.assertTrue(a.source_matches(a.P/n,before()['sources'][str((a.P/n).relative_to(a.ROOT))]))
   self.assertFalse(a.source_matches(a.P/n,'0'*64))
  self.assertEqual(a.verify()['speed1_extension']['mini_checks'],36)
 def test_speed2_scope(self):
  from speed2_qualification import PINS,before
  for n,h in PINS.items():
   self.assertTrue(a.source_matches(a.P/n,before()['sources'][str((a.P/n).relative_to(a.ROOT))]))
   self.assertFalse(a.source_matches(a.P/n,'0'*64))
  self.assertEqual(a.verify()['speed2_extension']['mini_checks'],36)
 def test_speed4_scope(self):
  from speed4_qualification import PINS,before
  for n in PINS:
   self.assertTrue(a.source_matches(a.P/n,before()['sources'][str((a.P/n).relative_to(a.ROOT))]))
   self.assertFalse(a.source_matches(a.P/n,'0'*64))
  self.assertEqual(a.verify()['speed4_extension']['mini_checks'],78)
 def test_speed4_wrong_writer(self):
  import speed4_qualification as s
  original=s.json.loads
  def mutated(raw,*args,**kwargs):
   row=original(raw,*args,**kwargs)
   if isinstance(row,list) and len(row)==18 and isinstance(row[0],dict) and 'extents' in row[0]:
    next(x for x in row[0]['extents'] if x['redo_overwritten'])['redo_first_writer']='unproved.writer'
   return row
  with patch.object(s.json,'loads',side_effect=mutated),self.assertRaises(AssertionError):s.verify()
 def test_speed4_partial_coverage(self):
  import speed4_qualification as s
  original=s.json.loads
  def mutated(raw,*args,**kwargs):
   row=original(raw,*args,**kwargs)
   if isinstance(row,list) and len(row)==18 and isinstance(row[0],dict) and 'extents' in row[0]:
    next(x for x in row[0]['extents'] if x['redo_overwritten'])['redo_covered_bytes']-=1
   return row
  with patch.object(s.json,'loads',side_effect=mutated),self.assertRaises(AssertionError):s.verify()
 def test_unproved_snapshot_exclusion(self):
  import speed2_qualification as s
  original=s.json.loads
  def mutated(raw,*args,**kwargs):
   row=original(raw,*args,**kwargs)
   if isinstance(row,list) and len(row)==12 and isinstance(row[0],dict) and 'extents' in row[0]:
    extent=next(x for x in row[0]['extents'] if x['name']=='streams');extent['captured_bytes']-=1
   return row
  with patch.object(s.json,'loads',side_effect=mutated),self.assertRaises(AssertionError):s.verify()
 def test_main_tamper(self):
  from build import compiled_sources
  now=compiled_sources();now[str((a.P/'main.cpp').relative_to(a.ROOT))]='0'*64
  with patch('build.compiled_sources',return_value=now),self.assertRaises(AssertionError):a.verify()
 def test_other_production_tamper(self):
  from build import compiled_sources
  now=compiled_sources();now[str((a.P/'owner.cpp').relative_to(a.ROOT))]='0'*64
  with patch('build.compiled_sources',return_value=now),self.assertRaises(AssertionError):a.verify()
 def test_old_main_only(self):
  self.assertTrue(a.source_matches(a.P/'main.cpp',a.OLD_MAIN))
  self.assertFalse(a.source_matches(a.P/'main.cpp','0'*64))
 def publication(self,change=None):
  with tempfile.TemporaryDirectory(dir=a.P/'evidence') as tmp:
   root=Path(tmp);rows=[];artifacts={'device/own-rt-iq3':'a'*64}
   for name in ('W2m','WS','WSs','WS128x'):
    row=dict(schema='packet45.window.v1',window=name,passed=True,device_executed=True,artifacts_sha256=artifacts)
    if change and name=='WS128x':row.update(change)
    p=root/(name+'.json');p.write_text(json.dumps(row));rows.append(dict(path=str(p),sha256=a.sha(p)))
   validate_packet45_device_evidence(dict(artifacts_sha256=artifacts),rows,root/'attestation.json')
 def test_device_publication(self):self.publication()
 def test_cpu_not_publication(self):
  with self.assertRaises(ValueError):self.publication({'device_executed':False})
 def test_diagnostic_not_publication(self):
  with self.assertRaises(ValueError):self.publication({'diagnostic_unsealed':True})
 def test_failed_not_publication(self):
  with self.assertRaises(ValueError):self.publication({'passed':False})
 def test_other_artifact_not_publication(self):
  with self.assertRaises(ValueError):self.publication({'artifacts_sha256':{'device/own-rt-iq3':'b'*64}})
 def test_missing_device_windows(self):
  with self.assertRaises(ValueError):validate_packet45_device_evidence({'artifacts_sha256':{'x':'a'}},[],a.P/'x.json')
if __name__=='__main__':unittest.main()

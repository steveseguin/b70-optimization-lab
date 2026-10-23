"""Audit admission cannot accept missing rows, stale evidence or larger extents."""
import json,unittest
from audit6 import P,verify
class Audit(unittest.TestCase):
 def setUp(self):self.row=json.loads((P/'audit6-gates.json').read_text())
 def test_current(self):verify(self.row)
 def test_missing_window(self):
  self.row['rows'].pop()
  with self.assertRaises(AssertionError):verify(self.row)
 def test_oversize_copy(self):
  self.row['rows'][0]['maximum_copy']=134217729
  with self.assertRaises(AssertionError):verify(self.row)
 def test_capacity(self):
  self.row['rows'][0]['peak_device_bytes'][0]=2**36
  with self.assertRaises(AssertionError):verify(self.row)
 def test_projection(self):
  self.row['rows'][0]['projected_write_bytes']=1
  with self.assertRaises(AssertionError):verify(self.row)
 def test_inventory(self):
  self.row['copy_sites'].pop()
  with self.assertRaisesRegex(AssertionError,'inventory'):verify(self.row)
 def test_source(self):
  self.row['sources']['owner.cpp']='0'*64
  with self.assertRaisesRegex(AssertionError,'sources'):verify(self.row)
 def test_log(self):
  self.row['evidence_sha256'][next(iter(self.row['evidence_sha256']))]='0'*64
  with self.assertRaisesRegex(AssertionError,'evidence'):verify(self.row)
if __name__=='__main__':unittest.main()

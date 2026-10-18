"""Reject stale or incomplete full-extent/adoption evidence before sealing."""
import copy,json,unittest
from copy_adoption_gate import P,verify
class Binding(unittest.TestCase):
 def setUp(self):self.gate=json.loads((P/'copy-adoption-gates.json').read_text())
 def test_valid(self):verify(self.gate)
 def reject(self,mutate):
  mutate(self.gate)
  with self.assertRaises(AssertionError):verify(self.gate)
 def test_missing_choice(self):self.reject(lambda g:g['selection_rows'].pop())
 def test_wrong_choice(self):self.reject(lambda g:g['selection_rows'][0].update(candidate='missing'))
 def test_missing_full_bank(self):self.reject(lambda g:g['extent_rows'][0].update(bank_bytes=4))
 def test_excess_copy(self):self.reject(lambda g:g['extent_rows'][0].update(maximum_copy=134217729))
 def test_stale_source(self):self.reject(lambda g:g['compiled_sources_sha256'].clear())
 def test_stale_log(self):self.reject(lambda g:g['programs']['selection'].update(log_sha256='0'*64))
 def test_guard_coverage(self):self.reject(lambda g:g['extent_result'].update(guard_rejections=0))
if __name__=='__main__':unittest.main()

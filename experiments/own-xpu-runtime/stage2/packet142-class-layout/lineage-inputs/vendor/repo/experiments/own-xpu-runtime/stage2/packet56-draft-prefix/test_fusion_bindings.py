"""Seal must reject omitted fused versions, validation shims and stale receipts."""
import copy,json,unittest
import seal45 as seal
class FusionBindings(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.gate=seal.read('fusion-matrix-gates.json')
 def test_current(self):seal.fusion_bindings(self.gate)
 def test_missing_compiler(self):
  row=copy.deepcopy(self.gate);row['rows'].pop()
  with self.assertRaises(AssertionError):seal.fusion_bindings(row)
 def test_missing_folded_reference(self):
  row=copy.deepcopy(self.gate);row['rows'][0]['result']['adapter_rows']=[r for r in row['rows'][0]['result']['adapter_rows'] if (r['case'],r['version'])!=(8,0)]
  with self.assertRaises(AssertionError):seal.fusion_bindings(row)
 def test_rank32_fallback(self):
  row=copy.deepcopy(self.gate)
  for r in row['rows'][0]['result']['adapter_rows']:
   if r['version']==6:r['passes']=1
  with self.assertRaises(AssertionError):seal.fusion_bindings(row)
 def test_missing_p39(self):
  row=copy.deepcopy(self.gate);row['rows'][0]['result']['p39_checks']=0
  with self.assertRaises(AssertionError):seal.fusion_bindings(row)
 def test_missing_small(self):
  row=copy.deepcopy(self.gate);row['rows'][0]['result']['small_checks']=0
  with self.assertRaises(AssertionError):seal.fusion_bindings(row)
 def test_stale_source(self):
  row=copy.deepcopy(self.gate);row['compiled_sources_sha256'][next(iter(row['compiled_sources_sha256']))]='0'*64
  with self.assertRaises(AssertionError):seal.fusion_bindings(row)
 def test_stale_binary(self):
  row=copy.deepcopy(self.gate);row['rows'][0]['binary_sha256']='0'*64
  with self.assertRaises(AssertionError):seal.fusion_bindings(row)
if __name__=='__main__':unittest.main()

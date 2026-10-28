import unittest,struct
import compare_cpu as C
class Validation(unittest.TestCase):
 def test_metrics(self):
  m=C.metrics(struct.pack('<2f',1.,3.),struct.pack('<2f',1.,2.));self.assertEqual(m['unequal_words'],1);self.assertEqual(m['max_abs'],1.)
 def test_nonfinite(self):
  with self.assertRaises(ValueError):C.metrics(struct.pack('<f',float('nan')),struct.pack('<f',0.))
 def test_wrong_prefix_receipt(self):
  with self.assertRaises(ValueError):C.cpu_arrays(dict(schema='ownrt.prefix178.cpu-capture-receipt.v1',passed=True,input_json_sha256='244-not-178',packed_prompt_sha256=C.PACKED_SHA,position=243,tokens=244))
if __name__=='__main__':unittest.main()

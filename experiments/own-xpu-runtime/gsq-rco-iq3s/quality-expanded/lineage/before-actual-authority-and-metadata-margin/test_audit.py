"""Metadata-only expanded-auditor delta tests; no actual result/decode operation."""
import copy,importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('expanded_readback_test',P/'audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Tests(unittest.TestCase):
 def test_prefix_continuation_and_terminal_eos(self):
  A.prefix_exact([2]*512,[2]*128)
  with self.assertRaises(ValueError):A.prefix_exact([3]+[2]*511,[2]*128)
  with self.assertRaises(ValueError):A.prefix_exact([2]*127,[2]*128)
  A.prefix_exact([2,248046],[2,248046])
  with self.assertRaises(ValueError):A.prefix_exact([2,248046,2],[2,248046])
 def test_decode_identity_rubric_and_failed_quality_not_repaired(self):
  row=dict(result={'tokens':[2,248046]},metric={'termination':'eos'});rubric={'id':'case','requested_elements':['fact']}
  record=dict(tokens=[2,248046],requested_max_new=512,termination='eos',tokenizer_sha256=A.T.TOKENIZER_SHA,skip_special_tokens=False,text='bad answer<eos>',rubric=rubric,automated_quality_passed=None,manual_full_output_review_required=True)
  with patch.object(A.T,'decode',return_value='bad answer<eos>') as decode:
   got=A.validate_decoded(row,record,rubric);self.assertTrue(got['manual_full_output_review_required']);decode.assert_called_once_with([2,248046])
   for key,value in [('text','repaired answer'),('automated_quality_passed',True),('requested_max_new',128),('termination','cap')]:
    bad=copy.deepcopy(record);bad[key]=value
    with self.assertRaises(ValueError):A.validate_decoded(row,bad,rubric)
 def test_plan_pending_and_all_bundle_scope_explicit(self):
  self.assertIsNone(A.PLAN_SHA);self.assertEqual(A.CAND.name,'engine');self.assertEqual(A.P.name,'quality-expanded')
  with self.assertRaisesRegex(ValueError,'fixed admitted plan'):A.run('0'*64)
  text=(P/'audit.py').read_text();self.assertIn('U.stream_bundle(path,original,semantic_oracle=False)',text);self.assertNotIn('semantic_oracle=relative.startswith',text)
  self.assertIn("states(base,row['state_sha256'])",text);self.assertIn("pair['arms'][0]['state_sha256']==pair['arms'][1]['state_sha256']",text)
if __name__=='__main__':unittest.main(verbosity=2)

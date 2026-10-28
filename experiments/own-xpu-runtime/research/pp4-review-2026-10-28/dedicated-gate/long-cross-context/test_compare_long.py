"""Tiny authenticated range negatives; no model/long-run proof execution."""
import hashlib, pathlib, tempfile, unittest
from compare_long import C,stream_candidate
sha=lambda b:hashlib.sha256(b).hexdigest()
class StreamTests(unittest.TestCase):
 def fixture(self,root,payload):
  d=pathlib.Path(root);state=b'{}';index=('GSQ_STATE_BUNDLE_V1\narray\t0\t%d\t%s\n'%(len(payload),sha(payload))).encode()
  (d/'state.bundle').write_bytes(payload);(d/'state.json').write_bytes(state);(d/'state-index.tsv').write_bytes(index)
  (d/'state-seal.txt').write_text('GSQ_STATE_SEAL_V1\n%d\n%s\n%s\n%s\n'%(len(payload),sha(payload),sha(index),sha(state)))
  return d,C.sealed(d,False)
 def test_original_prefix_sha_and_zero_tail(self):
  with tempfile.TemporaryDirectory()as t:
   d,s=self.fixture(t,b'ABC\0\0\0');r=stream_candidate(d,s,{'array':dict(bytes=3,sha256=sha(b'ABC'))})
   self.assertEqual(r['capacity_proofs'][0]['zero_tail_bytes'],3)
 def test_authenticated_nonzero_tail_refused(self):
  with tempfile.TemporaryDirectory()as t:
   d,s=self.fixture(t,b'ABC\0\0X')
   with self.assertRaisesRegex(ValueError,'nonzero'):stream_candidate(d,s,{'array':dict(bytes=3,sha256=sha(b'ABC'))})
 def test_authentic_candidate_different_prefix_refused(self):
  with tempfile.TemporaryDirectory()as t:
   d,s=self.fixture(t,b'ABD\0\0\0')
   with self.assertRaisesRegex(ValueError,'prefix hash'):stream_candidate(d,s,{'array':dict(bytes=3,sha256=sha(b'ABC'))})
 def test_payload_corruption_refused_by_original_seal(self):
  with tempfile.TemporaryDirectory()as t:
   d,s=self.fixture(t,b'ABC\0\0\0');(d/'state.bundle').write_bytes(b'ABD\0\0\0')
   with self.assertRaisesRegex(ValueError,'entry seal'):stream_candidate(d,s,{})
 def test_missing_capacity_source_refused(self):
  with tempfile.TemporaryDirectory()as t:
   d,s=self.fixture(t,b'ABC\0\0\0')
   with self.assertRaisesRegex(ValueError,'capacity sources'):stream_candidate(d,s,{'missing':dict(bytes=3,sha256=sha(b'ABC'))})
if __name__=='__main__':unittest.main()

"""Tiny synthetic authority tests; never open current-run payloads."""
import copy,importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('quality_pair_test',P/'reuse.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
def rows():return [dict(root='evidence',path=name,bytes=size,sha256=('%064x'%i)) for i,(a,b,size) in enumerate(M.PAIRS) for name in (a,b)]
class Tests(unittest.TestCase):
 def test_exact_allowlist_extent(self):
  result=M.mapping(rows());self.assertEqual(len(result),24);self.assertEqual(sum(x['bytes'] for x in result),2660918016)
  self.assertTrue(all('-mtp/' in x['original'] and '-none/' in x['canonical'] for x in result))
  self.assertFalse({x['original'] for x in result}&{x['canonical'] for x in result})
  self.assertEqual(len({x['original'] for x in result}),24)
 def test_missing_duplicate_wrong_extent_and_different_bytes_refuse(self):
  base=rows()
  for altered in (base[:-1],base+[base[0]], [dict(x,bytes=x['bytes']+1) if i==0 else x for i,x in enumerate(base)], [dict(x,sha256='f'*64) if i==0 else x for i,x in enumerate(base)]):
   with self.assertRaises(ValueError):M.mapping(altered)
 def test_pending_binding_and_fixed_batch(self):
  self.assertIsNone(M.BINDING_SHA)
  for batch in (-1,24,True):
   with self.assertRaisesRegex(ValueError,'fixed batch'):M.authority(batch)
  with self.assertRaisesRegex(ValueError,'binding pending'):M.authority(0)
 def test_primitives_and_non_target_files_excluded(self):
  self.assertEqual(M.sha(M.PARENT),M.PARENT_SHA)
  base=rows();base.append(dict(root='evidence',path='warmup-mtp/rank0/state-2147483647/state.bundle',bytes=1,sha256='f'*64))
  self.assertEqual(M.mapping(base),M.mapping(rows()))
  self.assertIn('os.unlink(RAW/row[\'original\'])',(P/'reuse.py').read_text())
if __name__=='__main__':unittest.main(verbosity=2)

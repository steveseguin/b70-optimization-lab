import unittest
import closed_bundles as C
class FixedAuthority(unittest.TestCase):
 def test_fixed_metadata_plan(self):
  p=C.plan();self.assertEqual(p['files'],12);self.assertEqual(p['bytes'],1330459008);self.assertTrue(p['attribution_excluded']);self.assertFalse(p['operations_performed'])
  self.assertEqual(len({(b['source'],b['name']) for b in p['batches']}),12)
  self.assertEqual(p['archive_quota_per_batch'],134217728);self.assertEqual(p['reserve_floor'],27067108864)
  self.assertLess(p['max_conservative_container_bytes'],p['archive_quota_per_batch'])
 def test_paths_reject_traversal_alias_and_other_files(self):
  good='rank0/state-2147483647/state.bundle';self.assertEqual(C.relative(good),('rank0','state-2147483647','state.bundle'))
  for bad in ('/'+good,'../'+good,'rank0/../'+good,'./'+good,good.replace('/','//'),good+'/',good+'.bin',good.replace('state.bundle','state.json'),good.replace('rank0','rank2'),'prompt-01-none/'+good,'random.bundle'):
   with self.subTest(path=bad),self.assertRaises(Exception):C.relative(bad)
 def test_only12_fixed_batches(self):
  for n in (-1,12,True,'0'):
   with self.subTest(batch=n),self.assertRaises(Exception):C.selected(n)
  self.assertEqual(C.selected(0)[0]['name'],'bundle');self.assertEqual(C.selected(11)[0]['name'],'class')
if __name__=='__main__':unittest.main(verbosity=2)

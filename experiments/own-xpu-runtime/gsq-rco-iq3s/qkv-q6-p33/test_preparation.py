import hashlib,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
class SourcePreparation(unittest.TestCase):
 def test_exact_selected_sites_and_formats(self):
  p=json.loads((P/'selection.json').read_text());self.assertEqual({'Q6_K':22,'Q5_K':10,'Q4_K':2,'IQ4_XS':2},p['qkv_format_counts']);self.assertEqual(22,len(p['sites']));self.assertTrue(all(x['rows']==10240 and x['columns']==2560 for x in p['sites']));self.assertEqual([0,24,40],[x['site']['layer'] for x in p['micro_cases']])
 def test_memory(self):
  p=json.loads((P/'selection.json').read_text());self.assertEqual(22*(3380-2100)*10240,p['allocation_delta_bytes']);self.assertEqual([14*13107200,8*13107200],p['per_rank_delta_bytes']);self.assertEqual(3*(21504000+34611200+5120+20480*2+327680),p['micro_device_bytes']);self.assertLess(3*(21504000+34611200+5120)+84*2*20480,p['micro_transfer_cap'])
 def test_copied_profile_baseline_identity(self):
  c=json.loads((P/'evidence/fixture-copy.json').read_text());self.assertTrue(c['passed']);self.assertEqual(76800,c['bytes'])
  for f in c['files']:
   data=Path(f['path']).read_bytes();self.assertEqual(f['bytes'],len(data));self.assertEqual(f['sha256'],hashlib.sha256(data).hexdigest())
  p=json.loads((P/'selection.json').read_text())
  for c in p['micro_cases']:
   for f in c['fixtures'].values():self.assertEqual(1,len(f['writers']))
 def test_original_p33_body(self):
  p=json.loads((P/'selection.json').read_text());path=next(Path(x) for x in p['source_sha256'] if x.endswith('/p33_candidates.hpp'));s=path.read_text();a=s.index('template<iq3::Type T,unsigned K>\ninline float dense_lane(');z=s.index('// Integer rank scheduling',a);body=s[a:z];self.assertEqual(p['selected_p33_body_sha256'],hashlib.sha256(body.encode()).hexdigest());self.assertIn(body,(P/'fixture_math.hpp').read_text())
if __name__=='__main__':unittest.main(verbosity=2)

import hashlib, json, unittest
from pathlib import Path
import prepare
D=Path(__file__).resolve().parent
class Source(unittest.TestCase):
 def test_exact_derivation(self):
  old,new=prepare.derive();self.assertEqual(new,(D/'direct.hpp').read_text())
 def test_arithmetic_and_guards(self):
  s=(D/'direct.hpp').read_text();old=prepare.P.read_text()
  for start,end in [('template<Type T,unsigned SG> inline float dot(', 'template<unsigned SG> float dispatch_dot'),('          for(unsigned width=1;', '        }));'),('Descriptor bind_matrix(', '\n}\n')]:
   self.assertEqual(s[s.index(start):s.index(end,s.index(start))],old[old.index(start):old.index(end,old.index(start))])
  for text in ['rows_per_group=4','sycl::range<1>(SG*rows_per_group)','local_stride*rows_per_group>local','kopt aliased bindings','kopt routing handles required','return d.compute(op,ids,{})']:
   self.assertIn(text,s)
  self.assertNotIn('sycl::local_accessor',s);self.assertNotIn('it.barrier(',s)
  self.assertEqual(s.count('stage_row<SG>('),0)
 def test_parent_pins(self):
  for p,h in json.loads((D/'source-pins.json').read_text()).items():self.assertEqual(hashlib.sha256(Path(p).read_bytes()).hexdigest(),h,p)
if __name__=='__main__':unittest.main()

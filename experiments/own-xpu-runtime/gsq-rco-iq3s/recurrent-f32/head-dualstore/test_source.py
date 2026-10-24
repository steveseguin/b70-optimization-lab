"""Small source/rounding checks, not C++ arithmetic or native qualification."""
import hashlib,json,struct,unittest
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[5]
def f32(bits):return struct.unpack('<f',struct.pack('<I',bits))[0]
def bf16(bits):
 if bits&0x7fffffff>0x7f800000:return (bits>>16)|0x40
 return ((bits+0x7fff+((bits>>16)&1))>>16)&65535
class Tests(unittest.TestCase):
 def test_selected_frozen_sources(self):
  pins=json.loads((P/'parent-pins.json').read_text())
  for p,h in pins.items():self.assertEqual(hashlib.sha256((R/p).read_bytes()).hexdigest(),h,p)
  math=next(R/p for p in pins if p.endswith('/kernels/math.hpp'))
  self.assertIn('(b+0x7fff+((b>>16)&1))>>16',math.read_text())
 def test_finite_rounding_order_and_ties(self):
  # Adjacent cells, midpoint ties-to-even, negative cells, signed zeros,
  # subnormal/normal transition. Distinct BF16 cells never reverse order.
  starts=[0,0x00008000,0x007f8000,0x00800000,0x3f7f8000,0x3f800000,0x3f808000,0x40008000,0x80000000,0x807f8000,0xbf7f8000,0xbf800000,0xbf808000]
  vals=sorted({v for start in starts for off in [-2,-1,0,1,2] if 0<=(b:=start+off)<=0xffffffff and (b&0x7f800000)!=0x7f800000 for v in [(f32(b),f32(bf16(b)<<16))]})
  for (x,a),(y,b) in zip(vals,vals[1:]):self.assertLessEqual(x,y);self.assertLessEqual(a,b)
  a,b=0x3f800001,0x3f800002
  self.assertLess(f32(a),f32(b));self.assertEqual(bf16(a),bf16(b))
  self.assertEqual(bf16(0x3f808000),0x3f80);self.assertEqual(bf16(0x3f818000),0x3f82)
 def test_exact_selected_arithmetic_and_two_stores(self):
  s=(P/'operation.hpp').read_text()
  self.assertEqual(s.count('p33::dense_lane<iq3::Type::Q6_K,columns>'),2)
  self.assertEqual(s.count('d.observation[row]=v;'),2)
  self.assertEqual(s.count('d.y[row]=iq3::bf16_bits(v);'),2)
  self.assertIn('if(lane%(2*width)==0)sum=sum+rhs;',s)
  self.assertIn('p28::validate(d,{m},"p28.dense.wg32",false,6);',s)
  self.assertIn('{m.workspace,true},{observation,true}',s)
  self.assertNotIn('fma(',s)
  self.assertEqual(248320*3380,839321600);self.assertEqual(248320*4,993280)
if __name__=='__main__':unittest.main()

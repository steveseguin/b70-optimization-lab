import sys,types,unittest,copy,struct
from pathlib import Path
root=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime')
sys.path.insert(0,str(root/'research/pp4-review-2026-10-28/dedicated-gate'))
import test_compare as F
src=Path('/dev/shm/dedicated-bulk-compare-overlay-20261028/compare.py').read_text().replace("ENGINE=Path(__file__).resolve().parents[3]/'engine'",f"ENGINE=Path({str(root/'engine')!r})")
C=types.ModuleType('bulk_compare');C.__file__='/dev/shm/dedicated-bulk-compare-overlay-20261028/compare.py';exec(compile(src,C.__file__,'exec'),C.__dict__)
class Bulk(unittest.TestCase):
 def rows(self):
  r=F.commands();issued,complete=r;issued['sequence']=complete['sequence']=2
  row=issued['row'];row['position']=2
  issued['request_hex']=struct.pack('<8i',27,row['token'],2,row['fixture'],3,2,0x50525631,1).hex()
  p=complete['provider'];p.update(provider_serial=2,seed_position=2,restored_position=2)
  raw=bytearray.fromhex(p['proposal_hex']);struct.pack_into('<Q',raw,24,2)
  struct.pack_into('<Q',raw,56,2);struct.pack_into('<2i',raw,64,2,2)
  p.update(proposal_hex=raw.hex(),proposal_sha256=C.sha256(raw).hexdigest(),reply_hex=struct.pack('<8i4d',0,21,0,224,2,-1,0x50525631,1,0.,0.,0.,0.).hex())
  return r
 def prefix(self):return dict(positions=1,actual_native_chunks=[{}],actual_native_pairs=[dict(position=1,token=7,hidden_bytes=40960,hidden_sha256='12'*32)])
 def test_actual_suffix_offset(self):self.assertEqual([p['position'] for p in C.canonical_pairs(self.rows(),3,prefix=self.prefix())],[1,2])
 def test_missing_duplicate_suffix(self):
  for r in ([],self.rows()+self.rows()):
   with self.assertRaises(ValueError):C.canonical_pairs(r,3,prefix=self.prefix())
 def test_wrong_sequence_offset(self):
  with self.assertRaises(ValueError):C.canonical_pairs(F.commands(),3,prefix=self.prefix())
 def test_wrong_seam_serial(self):
  r=self.rows();r[1]['provider']['provider_serial']=1
  with self.assertRaises(ValueError):C.canonical_pairs(r,3,prefix=self.prefix())
 def test_default_unchanged(self):self.assertEqual(len(C.canonical_pairs(F.commands(),2)),1)
if __name__=='__main__':unittest.main()

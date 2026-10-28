"""Prepared model-free sealed-fixture checks; not run during measured request."""
import json,hashlib,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
import capture_dump4 as c
sha=lambda b:hashlib.sha256(b).hexdigest()
def fixture(directory,layer):
 directory.mkdir();data=b'';rows=['GSQ_STATE_BUNDLE_V1'];buffers={}
 for layer in ([layer] if isinstance(layer,int) else layer):
  for suffix,n in c.FIELDS.items():
   key=f'blk.{layer}.{suffix}';name=key+'.bin';v=bytes((i*17)%251 for i in range(n));rows.append(f'{name}\t{len(data)}\t{n}\t{sha(v)}');data+=v;buffers[key]=sha(v)
 index=('\n'.join(rows)+'\n').encode();state=json.dumps({'history0':0,'history1':0,'buffers':buffers}).encode()
 for name,v in {'state.bundle':data,'state-index.tsv':index,'state.json':state,'state-seal.txt':f'GSQ_STATE_SEAL_V1\n{len(data)}\n{sha(data)}\n{sha(index)}\n{sha(state)}\n'.encode()}.items():(directory/name).write_bytes(v)
class Capture(unittest.TestCase):
 def test_full_reader_and_selected_extents(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);source=root/'state';fixture(source,4);r=c.extract(source,root/'selected',4,lambda:None)
   self.assertTrue(r['full_seal_verified']);self.assertEqual(r['bytes'],12608)
   for key,n in c.FIELDS.items():self.assertEqual((root/'selected'/f'blk.4.{key}.bin').stat().st_size,n)
 def test_bad_seal_keeps_full_evidence(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);source=root/'state';fixture(source,25);(source/'state.bundle').write_bytes(b'bad')
   with self.assertRaises(ValueError):c.extract(source,root/'selected',25,lambda:None)
   self.assertTrue((source/'state.bundle').exists());self.assertFalse((root/'selected').exists())
 def test_all_layers_verify_each_owner_once(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);out=root/'out';out.mkdir();records=[];real=c.reader.read_state
   with patch.object(c.reader,'read_state',wraps=real) as read:
    for rank,layers in enumerate((list(range(23)),list(range(23,48)))):
     source=root/f'owner{rank}';fixture(source,layers)
     records.extend(c.extract_layers(source,out,layers,lambda:None))
    self.assertEqual(read.call_count,2)
   self.assertEqual([r['layer'] for r in records],list(range(48)))
   self.assertEqual(sum(r['bytes'] for r in records),605184)
 def test_source_mutation_after_full_verification_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);source=root/'state';fixture(source,[4,25]);out=root/'out';out.mkdir();real=c.reader.read_state
   def mutate(directory):
    verified=real(directory)
    with (directory/'state.bundle').open('ab') as f:f.write(b'x')
    return verified
   with patch.object(c.reader,'read_state',side_effect=mutate):
    with self.assertRaises(AssertionError):c.extract_layers(source,out,[4,25],lambda:None)
   self.assertTrue((source/'state.bundle').exists());self.assertEqual(list(out.iterdir()),[])
if __name__=='__main__':unittest.main()

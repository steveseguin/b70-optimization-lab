import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import capture_l4_dump4 as c
sha=lambda b:hashlib.sha256(b).hexdigest()
def fixture(d):
 d.mkdir();rows=['GSQ_STATE_BUNDLE_V1'];buffers={};data=bytearray()
 for k,n in c.FIELDS.items():
  key=f'alternate:blk.4.{k.split(":",1)[1]}' if k.startswith('alternate:') else f'blk.4.{k}'
  name=c.reader.logical_name(key);v=bytes([len(rows)%251])*n
  rows.append(f'{name}\t{len(data)}\t{n}\t{sha(v)}');buffers[key]=sha(v);data.extend(v)
 index=('\n'.join(rows)+'\n').encode();state=json.dumps(dict(buffers=buffers)).encode()
 for name,v in {'state.bundle':data,'state-index.tsv':index,'state.json':state,'state-seal.txt':f'GSQ_STATE_SEAL_V1\n{len(data)}\n{sha(data)}\n{sha(index)}\n{sha(state)}\n'.encode()}.items():(d/name).write_bytes(v)
class Tests(unittest.TestCase):
 def test_l4_full_extents_and_spare_identity(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);s=r/'state';fixture(s);out=r/'out';out.mkdir();real=c.reader.read_state
   with patch.object(c.reader,'read_state',wraps=real) as read:records=c.extract_layers(s,out,[4],lambda:None)
   self.assertEqual(read.call_count,1);self.assertEqual(records[0]['bytes'],sum(c.FIELDS.values()))
   self.assertEqual(len(records[0]['selected']),24)
   self.assertEqual((out/'layer4/alternate-blk.4.gdn.state.bin').stat().st_size,3145728)
   self.assertTrue((s/'state.bundle').exists())
 def test_no_selected_layers_still_verifies_owner(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);s=r/'state';fixture(s);real=c.reader.read_state
   with patch.object(c.reader,'read_state',wraps=real) as read:self.assertEqual(c.extract_layers(s,r,[],lambda:None),[])
   self.assertEqual(read.call_count,1)
if __name__=='__main__':unittest.main()

import unittest,tempfile,shutil,json,importlib.util,sys
from pathlib import Path
from unittest.mock import patch
import validate
import capture_history as c
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
spec=importlib.util.spec_from_file_location('l4_old_fixture',HERE.parent/'test_dump.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
SOURCE=Path('/dev/shm/sc117-l4-history-recorder-cpu-20261028-r1/output/complete')
class Tests(unittest.TestCase):
 def test_actual_cpp_recorder_seal(self):
  r=validate.verify(SOURCE,[42]*244);self.assertEqual(r['payload_bytes'],16084480)
 def test_authenticated_bad_row_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)/'copy';shutil.copytree(SOURCE,d);p=d/'rows.jsonl';rows=p.read_text().splitlines();row=json.loads(rows[1]);row['position']=0;rows[1]=json.dumps(row);p.write_text('\n'.join(rows)+'\n');seal=json.loads((d/'seal.json').read_text());seal['index_sha256']=validate.sha(p.read_bytes());(d/'seal.json').write_text(json.dumps(seal))
   with self.assertRaises(AssertionError):validate.verify(d)
 def test_metadata_retained_for_owner_without_selected_layer(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);source=r/'state';old.fixture(source);out=r/'out';out.mkdir();metadata=r/'rank1';real=c.reader.read_state
   with patch.object(c.reader,'read_state',wraps=real) as read:self.assertEqual(c.extract_layers(source,out,[],lambda:None,metadata),[])
   self.assertEqual(read.call_count,1)
   for name in ['state-index.tsv','state.json','state-seal.txt']:self.assertEqual((metadata/name).read_bytes(),(source/name).read_bytes())
   self.assertTrue(json.loads((metadata/'verification.json').read_text())['full_seal_verified'])
if __name__=='__main__':unittest.main()

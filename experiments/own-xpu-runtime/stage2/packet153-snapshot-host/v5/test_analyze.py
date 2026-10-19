"""Actual retained p150 stream schema; missing streams/scopes must fail closed."""
import gzip,json,tempfile,unittest,shutil
from pathlib import Path
import analyze
P=Path(__file__).resolve().parent
class Proof(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.dest=self.root/'incident64'
  for name in ('receipt.json','rank0/timings.jsonl','rank1/timings.jsonl'):
   path=self.dest/name;path.parent.mkdir(parents=True,exist_ok=True)
   path.write_bytes(gzip.decompress((P.parent/'lineage-inputs/timing-fixture'/(name.replace('/','-')+'.gz')).read_bytes()))
  self.row=json.loads((self.dest/'receipt.json').read_text());self.row['prompt_id']='incident64'
 def tearDown(self):self.tmp.cleanup()
 def test_actual_embedded_trace(self):self.assertTrue(analyze.data_proof(self.root,self.row)['passed'])
 def test_missing_rank(self):
  for rank in (0,1):
   path=self.dest/f'rank{rank}/timings.jsonl';raw=path.read_bytes();path.unlink()
   with self.assertRaises((ValueError,FileNotFoundError)):analyze.data_proof(self.root,self.row)
   path.write_bytes(raw)
 def test_missing_every_scope(self):
  path=self.dest/'rank0/timings.jsonl';raw=path.read_text();rows=[json.loads(x) for x in raw.splitlines()]
  for name in {r['p150_segment'] for r in rows if 'p150_segment' in r} - set(analyze.REPLAYS.values()):
   path.write_text('\n'.join(json.dumps(r) for r in rows if r.get('p150_segment')!=name)+'\n')
   with self.subTest(scope=name),self.assertRaises(ValueError):analyze.data_proof(self.root,self.row)
  path.write_text(raw)
 def test_empty_native_trace(self):
  for key in ('rank_trace','guess_rows'):
   row=dict(self.row);row[key]=[]
   with self.assertRaises(ValueError):analyze.data_proof(self.root,row)
 def test_missing_native_trace(self):
  row=dict(self.row);row.pop('rank_trace')
  with self.assertRaises(ValueError):analyze.data_proof(self.root,row)
if __name__=='__main__':unittest.main()

"""Actual retained p150 stream schema; missing streams/scopes must fail closed."""
import gzip,hashlib,json,tempfile,time,unittest,shutil
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
 def test_unsplit_refuses_real_head_service(self):
  # packet185: the real split-head stream records the rank-0 suffix service; an unsplit view must not.
  with self.assertRaisesRegex(ValueError,'unsplit view recorded a rank-0 head service'):analyze.data_proof(self.root,self.row,False)
 def test_unsplit_without_head_scopes(self):
  path=self.dest/'rank0/timings.jsonl';raw=path.read_text();rows=[json.loads(x) for x in raw.splitlines()]
  path.write_text('\n'.join(json.dumps(r) for r in rows if r.get('p150_segment') not in analyze.HEAD_ONLY)+'\n')
  self.assertTrue(analyze.data_proof(self.root,self.row,False)['passed'])
  with self.assertRaises(ValueError):analyze.data_proof(self.root,self.row,True)
  for name in ('remote_reply_wait','token_prep','snapshot','draft_wait'):
   path.write_text('\n'.join(json.dumps(r) for r in rows if r.get('p150_segment') not in analyze.HEAD_ONLY|{name})+'\n')
   with self.subTest(scope=name),self.assertRaises(ValueError):analyze.data_proof(self.root,self.row,False)
  path.write_text(raw)
 def test_missing_native_trace(self):
  row=dict(self.row);row.pop('rank_trace')
  with self.assertRaises(ValueError):analyze.data_proof(self.root,row)
class ColdFirstRequest(unittest.TestCase):
 """Real packet153 failed smoke, with no data-proof or clock mocks."""
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);fixture=P.parent/'lineage-inputs/timing-fixture-p153b'
  manifest=json.loads((fixture/'manifest.json').read_text())
  source=P/'evidence/device-static-smoke-B/run/views/00-candidate/incident64'
  for name,entry in manifest['files'].items():
   raw=gzip.decompress((fixture/entry['fixture']).read_bytes())
   self.assertEqual(hashlib.sha256(raw).hexdigest(),entry['sha256'])
   if source.is_dir():
    self.assertEqual(raw,(source/name).read_bytes())
   dest=self.root/'incident64'/name;dest.parent.mkdir(parents=True,exist_ok=True)
   dest.write_bytes(raw)
  self.row=json.loads((self.root/'incident64/receipt.json').read_text())
  self.started=time.time_ns()-120_000_000_000
 def test_real_first_request_after_sixty_seconds(self):
  proof=analyze.first_minute_proof(self.root,self.row,self.started)
  self.assertTrue(proof['passed'])
  self.assertGreater(proof['seconds_after_view_start'],60)
  self.assertEqual(json.loads((self.root/'first-minute-data-proof.json').read_text()),proof)
  result=analyze.analyze([dict(index=0,choice='control',output=str(self.root),
                             requests=[dict(self.row,prompt_id='incident64')])])
  self.assertTrue(result['passed'])
 def test_empty_rank_stream_after_sixty_seconds(self):
  for rank in (0,1):
   path=self.root/f'incident64/rank{rank}/timings.jsonl';raw=path.read_bytes()
   path.write_bytes(b'')
   with self.subTest(rank=rank),self.assertRaisesRegex(ValueError,'missing rank timing stream'):
    analyze.first_minute_proof(self.root,self.row,self.started)
   self.assertFalse((self.root/'first-minute-data-proof.json').exists())
   path.write_bytes(raw)
 def test_missing_rank_stream_after_sixty_seconds(self):
  (self.root/'incident64/rank1/timings.jsonl').unlink()
  with self.assertRaisesRegex(ValueError,'missing rank timing stream'):
   analyze.first_minute_proof(self.root,self.row,self.started)
  self.assertFalse((self.root/'first-minute-data-proof.json').exists())
if __name__=='__main__':unittest.main()

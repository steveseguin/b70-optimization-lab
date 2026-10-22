"""Actual retained p150 V3 streams (packet186, read where retained); missing streams/scopes must fail closed.

Fixtures are packet186's real V3 incident64 requests (bracket view 01-candidate; smoke row view 00-candidate): every
packet188 variant runs a boundary every cycle; `k3trims` (rank0_prepare=async) must NOT record the synchronous
token_history readback, the others must.
"""
import json,shutil,tempfile,time,unittest
from pathlib import Path
import analyze
P=Path(__file__).resolve().parent
EV=P.parents[1]/'packet186-twocard-v3/v5/evidence'
BRACKET_V3=EV/'device-row2-bracket-u-v3-B-p186/run/views/01-candidate/incident64'
SMOKE_V3=EV/'device-row0-smoke-v3-B-p186/run/views/00-candidate/incident64'
FILES=('receipt.json','rank0/timings.jsonl','rank1/timings.jsonl','native-result.json')


def stage(source,root):
 dest=root/'incident64'
 for name in FILES:
  src=source/name
  if src.is_file():
   path=dest/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,path)
 row=json.loads((dest/'receipt.json').read_text());row['prompt_id']='incident64';return dest,row


class Proof(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.dest,self.row=stage(BRACKET_V3,self.root)
  self.path=self.dest/'rank0/timings.jsonl';self.raw=self.path.read_text();self.rows=[json.loads(x) for x in self.raw.splitlines() if x.strip()]
 def tearDown(self):self.tmp.cleanup()
 def write(self,rows):self.path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
 def test_real_v3_stream_passes_v3_and_v3k(self):
  for variant in ('v3','v3k'):
   with self.subTest(variant=variant):
    scopes=analyze.data_proof(self.root,self.row,variant)['host_scopes']
    self.assertGreater(scopes['boundary_ms_per_cycle'],0.9)
 def test_k3trims_refuses_a_synchronous_token_history(self):
  with self.assertRaisesRegex(ValueError,'staged view recorded a synchronous token_history readback'):analyze.data_proof(self.root,self.row,'k3trims')
  self.write([r for r in self.rows if r.get('p150_segment')!='token_history'])
  self.assertTrue(analyze.data_proof(self.root,self.row,'k3trims')['passed'])
  with self.assertRaisesRegex(ValueError,'missing measured comparison scope'):analyze.data_proof(self.root,self.row,'v3')
 def test_missing_rank(self):
  for rank in (0,1):
   path=self.dest/f'rank{rank}/timings.jsonl';raw=path.read_bytes();path.unlink()
   with self.assertRaises((ValueError,FileNotFoundError)):analyze.data_proof(self.root,self.row,'v3')
   path.write_bytes(raw)
 def test_missing_every_scope(self):
  for name in {r['p150_segment'] for r in self.rows if 'p150_segment' in r} - set(analyze.REPLAYS.values())-{'accept','rollback','draft_zero_wait'}:
   self.write([r for r in self.rows if r.get('p150_segment')!=name])
   with self.subTest(scope=name),self.assertRaises(ValueError):analyze.data_proof(self.root,self.row,'v3')
  self.path.write_text(self.raw)
 def test_boundary_every_cycle_and_no_head_service(self):
  self.write([r for r in self.rows if r.get('p150_segment') not in analyze.BOUNDARY])
  with self.assertRaises(ValueError):analyze.data_proof(self.root,self.row,'v3k')
  first=[r for r in self.rows if r.get('p150_segment')=='boundary_total'][:10]
  self.write([r for r in self.rows if r.get('p150_segment') not in analyze.BOUNDARY]+first+[r for r in self.rows if r.get('p150_segment')=='boundary_body'])
  with self.assertRaisesRegex(ValueError,'every packet188 view must run the boundary every cycle'):analyze.data_proof(self.root,self.row,'v3k')
  head=dict(next(r for r in self.rows if 'p150_segment' in r),p150_segment='suffix_head');self.write(self.rows+[head])
  with self.assertRaisesRegex(ValueError,'un-split view recorded a rank-0 head service'):analyze.data_proof(self.root,self.row,'v3')
  with self.assertRaisesRegex(ValueError,'packet188 variant required'):analyze.data_proof(self.root,self.row,'u')
 def test_empty_or_missing_native_trace(self):
  for key in ('rank_trace','guess_rows'):
   row=dict(self.row);row[key]=[]
   with self.assertRaises(ValueError):analyze.data_proof(self.root,row,'v3')
  native=self.dest/'native-result.json'
  if native.exists():native.unlink()
  row=dict(self.row);row.pop('rank_trace')
  with self.assertRaises(ValueError):analyze.data_proof(self.root,row,'v3')


class ColdFirstRequest(unittest.TestCase):
 """Real packet186 V3 smoke first request (64 tokens), no data-proof or clock mocks."""
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.dest,self.row=stage(SMOKE_V3,self.root);self.started=time.time_ns()-120_000_000_000
 def test_real_first_request_after_sixty_seconds(self):
  proof=analyze.first_minute_proof(self.root,self.row,self.started,'v3')
  self.assertTrue(proof['passed']);self.assertGreater(proof['seconds_after_view_start'],60)
  self.assertEqual(json.loads((self.root/'first-minute-data-proof.json').read_text()),proof)
  result=analyze.analyze([dict(index=0,choice='control',output=str(self.root),requests=[dict(self.row,prompt_id='incident64')])],variants=['v3'])
  self.assertTrue(result['passed'])
 def test_empty_or_missing_rank_stream(self):
  for rank in (0,1):
   path=self.root/f'incident64/rank{rank}/timings.jsonl';raw=path.read_bytes();path.write_bytes(b'')
   with self.subTest(rank=rank),self.assertRaisesRegex(ValueError,'missing rank timing stream'):analyze.first_minute_proof(self.root,self.row,self.started,'v3')
   self.assertFalse((self.root/'first-minute-data-proof.json').exists());path.write_bytes(raw)
  (self.root/'incident64/rank1/timings.jsonl').unlink()
  with self.assertRaisesRegex(ValueError,'missing rank timing stream'):analyze.first_minute_proof(self.root,self.row,self.started,'v3')


if __name__=='__main__':unittest.main()

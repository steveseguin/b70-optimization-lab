"""CPU-only synthetic accounting tests; fixture times are never lab evidence."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import analyze
class Accounting(unittest.TestCase):
 def fixture(self,root):
  def save(path,r):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(r))
  save(root/'window.json',dict(passed=True,lease_released=True))
  save(root/'identity.json',dict(lane='B',timing='attribution',binary_sha256='mock',selection_sha256='mock'))
  rows=[]
  for req in range(1,13):
   name=f'p{req}';row=dict(prompt_id=name,prompt_class=['prose','code','analysis','operations'][req%4],attribution_request=req,passed=True,exact_oracle=True,tokens=list(range(64)),decode_intervals=63,decode_wall_ms=1050)
   rows.append(row);save(root/'run'/name/'native-result.json',dict(tokens=row['tokens'],guess_rows=[dict(position=pos,hit=pos==11,cycle_ms=17) for pos in (11,12)],draft_rows=[dict(position=pos,rank0_idle_waiting_for_guess_ms=2) for pos in (11,12)],rank_trace=[]))
   for rank in (0,1):
    events=[];i=0
    for pos in (11,12):
     for layer in range(rank*24,(rank+1)*24):
      i+=1;events.append(dict(schema='packet128.event.v1',request=req,rank=rank,fixture=pos-10,position=pos-rank,label=f'blk.{layer}.gdn',**{'class':'attention'},event=i,start_ns=i*10000,end_ns=i*10000+5000))
    f=root/'run'/name/f'rank{rank}/sites.jsonl';f.parent.mkdir();f.write_text(''.join(json.dumps(e)+'\n' for e in events))
  save(root/'run/report-inputs.json',dict(passed=True,requests=rows,incident64=dict(passed=True)))
  return rows
 def run_fixture(self,mutate=None):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rows=self.fixture(root)
   if mutate:mutate(root,rows)
   with patch.object(analyze,'sha',return_value='mock'):return analyze.generate(root)
 def test_full_both_ranks_and_outcomes(self):
  r=self.run_fixture();self.assertEqual(r['cycles'],24);self.assertEqual(r['coverage'],[list(range(24)),list(range(24,48))]);self.assertTrue(r['ranking_usable'])
  costs=[x for x in r['tables'] if x['category']=='attention/gdn'];self.assertEqual(len(costs),4)
  for t in costs:self.assertAlmostEqual(t['mean_ms'],.12)
 def test_missing_layer_refused(self):
  def change(root,rows):
   for f in root.glob('run/*/rank0/sites.jsonl'):f.write_text('\n'.join(s for s in f.read_text().splitlines() if json.loads(s)['label']!='blk.0.gdn')+'\n')
  with self.assertRaisesRegex(AssertionError,'missing layer'):self.run_fixture(change)
 def test_zero_compute_refused(self):
  def change(root,rows):
   f=root/'run/p1/rank0/sites.jsonl';events=[json.loads(s) for s in f.read_text().splitlines()];events[0]['end_ns']=events[0]['start_ns'];f.write_text(''.join(json.dumps(e)+'\n' for e in events))
  with self.assertRaisesRegex(AssertionError,'zero compute'):self.run_fixture(change)
 def test_intrusive_profile_withholds_ranking(self):
  def change(root,rows):
   for r in rows:r['decode_wall_ms']=3000
   (root/'run/report-inputs.json').write_text(json.dumps(dict(passed=True,requests=rows,incident64=dict(passed=True))))
  r=self.run_fixture(change);self.assertFalse(r['ranking_usable']);self.assertIn('ranking withheld',analyze.markdown(r))
 def test_missing_tokens_refused(self):
  with tempfile.TemporaryDirectory() as d:
   rows=self.fixture(Path(d));rows[0]['tokens'].pop()
   with self.assertRaises(AssertionError):analyze.summarize(rows,dict(passed=True),'tp2')
 def test_failed_exactness_refused(self):
  with tempfile.TemporaryDirectory() as d:
   rows=self.fixture(Path(d));rows[0]['exact_oracle']=False
   with self.assertRaises(AssertionError):analyze.summarize(rows,dict(passed=True),'tp2')
if __name__=='__main__':unittest.main()

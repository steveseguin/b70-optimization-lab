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
   rows.append(row);save(root/'run'/name/'native-result.json',dict(tokens=row['tokens'],guess_rows=[dict(position=pos,hit=pos%2==0,cycle_ms=17) for pos in range(10,17)],draft_rows=[dict(position=pos,rank0_idle_waiting_for_guess_ms=2) for pos in (11,12)],rank_trace=[dict(op=1,position=9,fixture=9,rank=0)]))
   for rank in (0,1):
    events=[];i=0
    for pos in range(10,17):
     for layer in range(rank*24,(rank+1)*24):
      i+=1;events.append(dict(schema='packet128b.event.v1',request=req,rank=rank,fixture=pos-rank,position=pos-rank,label=f'blk.{layer}.gdn',**{'class':'attention'},queue='compute',queue_kind='compute',event=i,start_ns=i*10000,end_ns=i*10000+5000))
    f=root/'run'/name/f'rank{rank}/sites.jsonl';f.parent.mkdir();f.write_text(''.join(json.dumps(e)+'\n' for e in events))
  save(root/'run/report-inputs.json',dict(passed=True,requests=rows,incident64=dict(passed=True)))
  return rows
 def run_fixture(self,mutate=None):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);rows=self.fixture(root)
   if mutate:mutate(root,rows)
   with patch.object(analyze,'sha',return_value='mock'):return analyze.generate(root)
 def test_full_both_ranks_and_outcomes(self):
  r=self.run_fixture();self.assertEqual(r['cycles'],84);self.assertEqual(r['coverage'],[list(range(24)),list(range(24,48))]);self.assertTrue(r['ranking_usable'])
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
  r=self.run_fixture(change);self.assertFalse(r['ranking_usable']);self.assertEqual(r['levers'],[]);self.assertIn('ranking withheld',analyze.markdown(r))
 def test_missing_tokens_refused(self):
  with tempfile.TemporaryDirectory() as d:
   rows=self.fixture(Path(d));rows[0]['tokens'].pop()
   with self.assertRaises(AssertionError):analyze.summarize(rows,dict(passed=True),'tp2')
 def test_failed_exactness_refused(self):
  with tempfile.TemporaryDirectory() as d:
   rows=self.fixture(Path(d));rows[0]['exact_oracle']=False
   with self.assertRaises(AssertionError):analyze.summarize(rows,dict(passed=True),'tp2')

class MultiQueue(unittest.TestCase):
 def event(self,i,a,b,queue='compute',kind='compute',fixture=10):
  return dict(event=i,start_ns=a,end_ns=b,queue=queue,queue_kind=kind,fixture=fixture,
   request=1,rank=0,position=10,label='blk.0.gdn')
 def test_union_nested_and_overlap(self):
  self.assertEqual(analyze.union_ns([(10,30),(15,20),(25,40),(50,60)]),40)
 def test_copy_overlap_not_compute_idle(self):
  es=[self.event(1,100,200),self.event(2,150,500,'copy-bcs','copy'),self.event(3,250,350)]
  costs,gaps,unknown,omitted=analyze.queue_accounting(es)
  self.assertEqual({x['queue'] for x in costs},{'compute','copy-bcs'})
  self.assertEqual(sum(x[1] for x in gaps),50/1e6)
 def test_other_queue_and_clock_never_subtracted(self):
  es=[self.event(1,100,200),self.event(2,10**12,10**12+700,'draft-aux','other'),self.event(3,220,300)]
  self.assertAlmostEqual(sum(x[1] for x in analyze.queue_accounting(es)[1]),20/1e6)
 def test_overlap_on_compute_uses_union(self):
  es=[self.event(1,100,300),self.event(2,150,200),self.event(3,250,400),self.event(4,450,500)]
  costs,gaps,_,_=analyze.queue_accounting(es)
  self.assertAlmostEqual(costs[0]['busy_ms_union'],350/1e6)
  self.assertAlmostEqual(sum(x[1] for x in gaps),50/1e6)
 def test_zero_copy_is_unknown(self):
  es=[self.event(1,100,200),self.event(2,10,10,'copy-auto','copy'),self.event(3,250,300)]
  _,gaps,unknown,_=analyze.queue_accounting(es)
  self.assertEqual(unknown,{'copy-auto':1});self.assertAlmostEqual(sum(x[1] for x in gaps),50/1e6)
 def test_missing_events_and_sampling_boundaries_break_gap(self):
  es=[self.event(1,100,200),self.event(3,250,300),self.event(4,800,900,fixture=11)]
  _,gaps,_,omitted=analyze.queue_accounting(es)
  self.assertEqual(gaps,[]);self.assertEqual(omitted,2)
 def test_ratio_threshold_uses_58(self):
  with tempfile.TemporaryDirectory() as d:
   rows=Accounting().fixture(Path(d))
   for r in rows:r['decode_wall_ms']=63000/(58*.90)
   self.assertTrue(analyze.summarize(rows,{'passed':True},'tp2')['overhead_bounded'])
   for r in rows:r['decode_wall_ms']=63000/(58*.8999)
   self.assertFalse(analyze.summarize(rows,{'passed':True},'tp2')['overhead_bounded'])
 def test_unsampled_event_fails_closed(self):
  def change(root,rows):
   f=root/'run/p1/rank0/sites.jsonl';es=[json.loads(s) for s in f.read_text().splitlines()];es[0]['fixture']=8
   f.write_text(''.join(json.dumps(e)+'\n' for e in es))
  with self.assertRaisesRegex(AssertionError,'unsampled'):Accounting().run_fixture(change)
 def test_one_cycle_missing_layer_fails(self):
  def change(root,rows):
   f=root/'run/p1/rank0/sites.jsonl';es=[json.loads(s) for s in f.read_text().splitlines()]
   f.write_text(''.join(json.dumps(e)+'\n' for e in es if not(e['fixture']==10 and e['label']=='blk.0.gdn')))
  with self.assertRaisesRegex(AssertionError,'missing layer in sampled cycle'):Accounting().run_fixture(change)

if __name__=='__main__':unittest.main()

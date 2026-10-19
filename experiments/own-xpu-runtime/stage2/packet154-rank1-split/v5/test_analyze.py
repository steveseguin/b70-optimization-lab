import json,tempfile,unittest
from pathlib import Path
from analyze import analyze,request_split,overlap,REQUIRED

class Analyze(unittest.TestCase):
 def fixture(self,root,index=0,choice='candidate',dominant='b_issue'):
  dest=root/str(index);requests=[]
  for prompt in range(12):
   name='p'+str(prompt);folder=dest/name
   for rank in (0,1):(folder/f'rank{rank}').mkdir(parents=True)
   a=[];b=[]
   def row(name,rank,start,end,seq):
    return dict(p154_segment=name,rank=rank,start=start,end=end,ms=(end-start)*1000,position=seq,sequence=seq,op=1,replay='duplicate' in name)
   for seq in range(1,64):
    start=100+seq-1+.1;end=start+.00154
    a.append(row('remote_reply_wait',0,start,end,seq))
    b.append(row('command',1,start-.01,end,seq))
    b.append(row(dominant,1,start,end,seq))
    for n,name2 in enumerate(REQUIRED-{dominant}):
     t=start-.009+n*.00001;b.append(row(name2,1,t,t+.000001,seq))
   for rank,rows in ((0,a),(1,b)):(folder/f'rank{rank}/timings.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
   requests.append(dict(prompt_id=name,token_timestamps=list(range(100,164))))
  return dict(index=index,choice=choice,output=str(dest),requests=requests)
 def test_smoke_and_conservation(self):
  with tempfile.TemporaryDirectory() as d:
   v=self.fixture(Path(d));r=analyze([v],smoke=True)
   self.assertAlmostEqual(r['views'][0]['remote_reply_wait_ms_per_cycle'],1.54)
   self.assertAlmostEqual(r['views'][0]['overlap_ms_per_cycle']['b_half'],1.54)
   self.assertFalse(r['speed_evidence_eligible'])
 def test_bracket_decision(self):
  with tempfile.TemporaryDirectory() as d:
   views=[self.fixture(Path(d),i,c,'draft_issue') for i,c in enumerate(['control','candidate','control','candidate','control'])]
   self.assertIn('draft brief',analyze(views)['decision'])
 def test_missing_empty_unmatched_and_incomplete(self):
  for failure in ('missing','empty','unmatched','incomplete'):
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as d:
    v=self.fixture(Path(d));p=Path(v['output'])/'p0/rank1/timings.jsonl'
    if failure=='missing':p.unlink()
    elif failure=='empty':p.write_text('')
    else:
     rows=[json.loads(x) for x in p.read_text().splitlines()]
     rows=[x for x in rows if x['p154_segment']!=('command' if failure=='unmatched' else 'draft_issue')]
     p.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    with self.assertRaises(ValueError):analyze([v],smoke=True)
 def test_pending_not_compute_and_nested_no_double_count(self):
  w=dict(start=1.,end=2.)
  r=overlap(w,[dict(start=1.,end=2.,p154_segment='draft_completion_pending'),dict(start=1.2,end=1.8,p154_segment='b_issue'),dict(start=1.3,end=1.4,p154_segment='prefix_export')])
  self.assertAlmostEqual(sum(r.values()),1000)
  self.assertAlmostEqual(r['draft_pending'],400)
  self.assertAlmostEqual(r['b_half'],500)
  self.assertAlmostEqual(r['transport'],100)
 def test_bad_timestamp(self):
  with tempfile.TemporaryDirectory() as d:
   v=self.fixture(Path(d));v['requests'][0]['token_timestamps'][1]=0
   with self.assertRaises(ValueError):analyze([v],smoke=True)
if __name__=='__main__':unittest.main()

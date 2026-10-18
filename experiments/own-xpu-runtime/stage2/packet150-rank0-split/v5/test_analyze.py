import json,tempfile,unittest
from pathlib import Path
from analyze import analyze,request_split

class Analyze(unittest.TestCase):
 def fixture(self,root,index,choice):
  dest=root/str(index);folder=dest/'p/rank0';folder.mkdir(parents=True)
  rows=[]
  for cycle in range(63):
   start=100+cycle+.1
   for offset,(name,ms) in enumerate([('token_prep',.6),('snapshot',1.),('suffix_head',.8),('draft_wait',.2),('remote_reply_wait',.1),('token_prep_duplicate',.61 if choice=='candidate' else .01)]):
    t=start+offset*.01
    rows.append(dict(p150_segment=name,position=cycle,rank=0,replay=name.endswith('duplicate'),ms=ms,start=t,end=t+ms/1000))
   t=start+.0101
   rows.append(dict(p150_segment='snapshot_duplicate',position=cycle,rank=0,replay=True,ms=.2,start=t,end=t+.0002))
  (folder/'timings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
  request=dict(prompt_id='p',token_timestamps=list(range(100,164)),hits=40,misses=23)
  return dict(index=index,choice=choice,output=str(dest),requests=[request])
 def test_pairing_threshold_and_no_false_removal(self):
  with tempfile.TemporaryDirectory() as d:
   views=[self.fixture(Path(d),i,v) for i,v in enumerate(['control','candidate','control','candidate','control'])]
   result=analyze(views);decisions={x['segment']:x for x in result['decisions']}
   self.assertAlmostEqual(decisions['token_prep']['control_median_ms_per_cycle'],.6)
   self.assertAlmostEqual(decisions['capture_snapshot']['control_median_ms_per_cycle'],.8)
   self.assertAlmostEqual(decisions['token_prep']['replay_minus_skip_ms_per_cycle'][0],.6)
   self.assertTrue(decisions['token_prep']['at_least_0_4_ms_in_every_control'])
   self.assertFalse(decisions['draft_wait']['at_least_0_4_ms_in_every_control'])
   self.assertEqual(result['removable_segments'],[])
   self.assertFalse(result['speed_evidence_eligible'])
 def test_missing_receipt_not_zero(self):
  with tempfile.TemporaryDirectory() as d:
   view=self.fixture(Path(d),0,'control');p=Path(view['output'])/'p/rank0/timings.jsonl';p.write_text('')
   with self.assertRaisesRegex(ValueError,'missing packet150'):request_split(Path(view['output']),view['requests'][0])
 def test_bad_clock_refuses(self):
  with tempfile.TemporaryDirectory() as d:
   v=self.fixture(Path(d),0,'control');v['requests'][0]['token_timestamps'][5]=0
   with self.assertRaisesRegex(ValueError,'monotone'):request_split(Path(v['output']),v['requests'][0])
 def test_synthetic_never_measurement(self):
  self.assertFalse(analyze([],synthetic=True)['device_evidence'])
if __name__=='__main__':unittest.main()

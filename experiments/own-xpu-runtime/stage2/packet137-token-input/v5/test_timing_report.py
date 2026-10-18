import json,tempfile,unittest
from pathlib import Path
from timing_report import summarize
class TimingTests(unittest.TestCase):
 def test_same_request_position_binding(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);view=dict(index=1,choice='candidate',output=str(root),requests=[dict(prompt_id='p',guess_rows=[dict(position=9,hit=True),dict(position=10,hit=False)])])
   for rank in (0,1):(root/f'p/rank{rank}').mkdir(parents=True)
   service=[dict(leg='suffix-service',position=p,wait_ready_us=1,import_us=2,suffix_compute_and_scalars_us=3,service_us=6) for p in (8,9)]
   wait=[dict(leg='wait.head.suffix',position=p,host_us=7) for p in (8,9)]
   halves=[dict(position=p,speculative=True,half_completion_ms=12) for p in (9,10)]
   for path,rows in [('p/rank0/p105-transfers.jsonl',service),('p/rank1/p105-transfers.jsonl',wait),('p/rank0/timings.jsonl',halves)]:
    (root/path).write_text(''.join(json.dumps(r)+'\n' for r in rows))
   result=summarize(root,[view])['views'][0]['costs'];self.assertEqual(len(result),12)
   self.assertEqual({r['outcome'] for r in result},{'hit','miss'})
   self.assertTrue(all(r['mean_us']==12000 for r in result if r['stage']=='speculative-half'))
   (root/'p/rank1/p105-transfers.jsonl').unlink()
   with self.assertRaisesRegex(ValueError,'missing suffix timing'):summarize(root,[view])
if __name__=='__main__':unittest.main()

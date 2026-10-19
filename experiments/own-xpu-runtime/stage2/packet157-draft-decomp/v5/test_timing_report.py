import tempfile,unittest
from pathlib import Path
from timing_report import summarize
class TimingTests(unittest.TestCase):
 def view(self,root):
  traces=[dict(rank=0,op=1,position=p,speculative=s,rank_received=1.,rank_completed=1.+ms/1000,busy_ms=ms) for p,s,ms in ((9,True,8),(10,True,7),(10,False,12),(11,False,11))]
  return dict(index=1,choice='candidate',output=str(root),requests=[dict(prompt_id='p',guess_rows=[dict(position=9,hit=True),dict(position=10,hit=False)],rank_trace=traces)])
 def test_view_native_trace_no_head_receipts(self):
  with tempfile.TemporaryDirectory() as d:
   v=self.view(Path(d));r=summarize(d,[v])['views'][0]
   self.assertEqual(r['miss_count'],1);self.assertAlmostEqual(r['corrected_half']['mean_ms'],12)
 def test_missing_or_duplicate_correction_refused(self):
  with tempfile.TemporaryDirectory() as d:
   v=self.view(Path(d));v['requests'][0]['rank_trace'].pop(2)
   with self.assertRaisesRegex(ValueError,'corrected HALF'):summarize(d,[v])
   v=self.view(Path(d));v['requests'][0]['rank_trace'].append(v['requests'][0]['rank_trace'][2])
   with self.assertRaisesRegex(ValueError,'corrected HALF'):summarize(d,[v])
 def test_absent_trace_is_unknown_not_zero(self):
  with tempfile.TemporaryDirectory() as d:
   v=self.view(Path(d));v['requests'][0].pop('rank_trace');r=summarize(d,[v])['views'][0]
   self.assertIsNone(r['miss_count']);self.assertIsNone(r['corrected_half']['mean_ms']);self.assertEqual(r['status'],'unavailable')
if __name__=='__main__':unittest.main()

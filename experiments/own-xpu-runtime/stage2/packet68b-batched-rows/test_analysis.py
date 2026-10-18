import json,tempfile,unittest
from pathlib import Path
from analyze_probe import analyze,project
P=Path(__file__).resolve().parent
class Analysis(unittest.TestCase):
 def test_pipeline_rewards_and_bar(self):
  good=project([14.23,14.69],[14.23*1.3,14.69*1.3])
  bad=project([14.23,14.69],[14.23*1.9,14.69*1.9])
  self.assertEqual(good['reward_tokens'],2)
  self.assertAlmostEqual(sum(good['probabilities'].values()),1)
  self.assertTrue(good['cases']['no_overlap_credit']['go_at_eight_percent'])
  self.assertFalse(bad['cases']['no_overlap_credit']['go_at_eight_percent'])
  self.assertFalse(good['depth1_batched_redo']['go_at_eight_percent'])
  self.assertLess(project([14.23,14.69],[18.5,19.1],3)['cases']['no_overlap_credit']['projected_tok_s'],project([14.23,14.69],[18.5,19.1],0)['cases']['no_overlap_credit']['projected_tok_s'])
 def test_requires_exact_complete_device_evidence(self):
  with tempfile.TemporaryDirectory(dir=P/'build') as tmp:
   root=Path(tmp);run=root/'run';run.mkdir()
   (root/'window.json').write_text(json.dumps(dict(passed=True,device_executed=True)))
   summary=dict(passed=True,request_count=12,arithmetic='iq3-p49-split32-v1',incident64=dict(passed=True,tokens_compared=64))
   (run/'summary.json').write_text(json.dumps(summary))
   rows=[]
   for i in range(13):
    request=run/str(i);request.mkdir();(request/'receipt.json').write_text(json.dumps(dict(exact_oracle=True)))
    for rank in (0,1):
     for fixture in (8,16,32):
      rows.append(dict(schema='packet68b.sample.v1',byte_identity=True,rank=rank,fixture=fixture,request_directory=str(request/f'rank{rank}'),H1=dict(wall_ms=14.5,device_span_ms=14.,device_sum_ms=13.,classes_ms=dict(dense=4)),H2=dict(wall_ms=19.,device_span_ms=18.,device_sum_ms=17.,classes_ms=dict(dense=5)),batched_classes=['dense']))
   path=run/'batched-rows.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   result=analyze(root);self.assertEqual(result['measured_half_costs']['0']['samples'],39)
   self.assertTrue(result['decision'].startswith('NO-GO')) # restore missing
   path.write_text(''.join(json.dumps(r)+'\n' for r in rows[:-1]))
   with self.assertRaises(ValueError):analyze(root)
   rows[0]['byte_identity']=False;path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaises(ValueError):analyze(root)
   summary['incident64']['passed']=False;(run/'summary.json').write_text(json.dumps(summary))
   with self.assertRaises(ValueError):analyze(root)
if __name__=='__main__':unittest.main()

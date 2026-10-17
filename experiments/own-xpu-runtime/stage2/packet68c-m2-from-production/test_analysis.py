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
     for fixture in (8,16,32,9,17,33):
      mixed=fixture in (9,17,33)
      rows.append(dict(schema='packet68c.sample.v1',byte_identity=True,row_identity=[True,True],row_kind='consecutive-engine-inputs-independent-state' if mixed else 'duplicate-independent-state',position=fixture+64,previous_position=fixture+63 if mixed else fixture+64,route_sites=24,differing_route_sites=12 if mixed else 0,shared_experts=150 if mixed else 240,union_experts=330 if mixed else 240,rank=rank,fixture=fixture,request_directory=str(request/f'rank{rank}'),H1=dict(wall_ms=14.5,device_span_ms=14.,device_sum_ms=13.,classes_ms=dict(dense=4,serial=2)),H2=dict(wall_ms=19.,device_span_ms=18.,device_sum_ms=17.,classes_ms=dict(dense=5,serial=4)),batched_classes=['dense'],serial_classes=['serial']))
   path=run/'batched-rows.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   result=analyze(root);self.assertEqual(result['measured_half_costs']['0']['samples'],39)
   self.assertEqual(result['duplicate_half_costs']['0']['samples'],39)
   self.assertEqual(result['measured_half_costs']['0']['classes']['serial']['execution'],'serial-M1')
   self.assertTrue(result['decision'].startswith('NO-GO')) # restore missing
   restore=root/'restore.json';restore.write_text(json.dumps(dict(passed=True,device_executed=True,medians=dict(restore_ms=0.98))))
   self.assertEqual(analyze(root,restore)['projection']['restore_ms'],0.98)
   path.write_text(''.join(json.dumps(dict(r,differing_route_sites=0))+'\n' for r in rows))
   with self.assertRaisesRegex(ValueError,'differing real routes'):analyze(root)
   path.write_text(''.join(json.dumps(dict(r,previous_position=r['position']))+'\n' for r in rows))
   with self.assertRaisesRegex(ValueError,'nonconsecutive'):analyze(root)
   path.write_text(''.join(json.dumps(dict(r,serial_classes=['serial','dense']))+'\n' for r in rows))
   with self.assertRaisesRegex(ValueError,'ambiguous'):analyze(root)
   path.write_text(''.join(json.dumps(r)+'\n' for r in rows[:-1]))
   with self.assertRaises(ValueError):analyze(root)
   rows[0]['byte_identity']=False;path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaises(ValueError):analyze(root)
   summary['incident64']['passed']=False;(run/'summary.json').write_text(json.dumps(summary))
   with self.assertRaises(ValueError):analyze(root)
if __name__=='__main__':unittest.main()

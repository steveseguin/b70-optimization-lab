"""CPU timing failure must never hide missing classes, candidates, or stages."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import k2_summary as k
class Structure(unittest.TestCase):
 def check(self,mutate=None):
  classes={'norm':dict(candidates=['a','b'],workloads=['x'])}
  classes.update({'fusion:p39.'+str(i):{} for i in range(8)})
  rows=[dict(class_='norm',candidate=c,variant=v,workload='x',stage_count=1,repetition=0,start_ns=0,end_ns=0) for c in ('a','b') for v in ('packet18','specialised')]
  for r in rows:r['class']=r.pop('class_')
  if mutate:mutate(rows)
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'receipt.json').write_text(json.dumps(dict(schema='packet26.k2.v1',passed=True,device_executed=False,validation_only=True,context=4096,p39_checks=56)))
   (root/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with patch.object(k,'registry_for_context',return_value=classes):return k.cpu_structure(root)
 def test_valid_cpu_structure_is_not_timing(self):self.assertFalse(self.check()['timing_qualified'])
 def test_missing_class(self):
  with self.assertRaisesRegex(ValueError,'class coverage'):self.check(lambda rows:rows.clear())
 def test_missing_candidate(self):
  with self.assertRaisesRegex(ValueError,'candidate coverage'):self.check(lambda rows:rows.__delitem__(slice(2,None)))
 def test_missing_variant(self):
  with self.assertRaisesRegex(ValueError,'variant coverage'):self.check(lambda rows:rows.pop())
 def test_wrong_workload(self):
  with self.assertRaisesRegex(ValueError,'workload coverage'):self.check(lambda rows:rows[0].update(workload='wrong'))
 def test_missing_stage(self):
  with self.assertRaisesRegex(ValueError,'stage coverage'):self.check(lambda rows:rows[0].update(stage_count=2))
 def test_fabricated_timing(self):
  with self.assertRaisesRegex(ValueError,'timestamps'):self.check(lambda rows:rows[0].update(end_ns=1))
if __name__=='__main__':unittest.main()

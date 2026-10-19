"""Synthetic schema tests are not measurements; real parent replay is separate."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import micro_analyze as a

def fixture(path,ratio):
 # Stable complete buffer census from retained native CPU output.
 gate=json.loads((a.P/'evidence/cpu-real-parity.json').read_text());assert gate['passed'] and gate['real_weights']
 source=a.P.parents[3]/gate['records'][0]['stdout']
 rows=[json.loads(x) for x in source.read_text().splitlines()]
 checks=[r for r in rows if r['kind']=='bytes']
 assert len(checks)>300 and all(r['different_bytes']==0 for r in checks)
 with path.open('w') as f:
  for layer in a.LAYERS:
   for pos in a.POSITIONS:
    for r in checks:
     if r['layer']==layer and r['position']==pos:f.write(json.dumps(r)+'\n')
    for repeat in range(200):
     for j in range(2):
      arm=(repeat+j)%2;index=0;clock=1000000
      f.write(json.dumps(dict(kind='oracle',layer=layer,position=pos,repeat=repeat,arm=arm,passed=True,compared_buffers=60))+'\n')
      for _ in range(2 if arm==0 else 1):
       for cls,count in a.COUNTS[layer].items():
        for _ in range(count):
         duration=10000 if arm==0 else round(10000*ratio)
         f.write(json.dumps(dict(kind='sample',layer=layer,position=pos,repeat=repeat,arm=arm,event=index,**{'class':cls},start_ns=clock,end_ns=clock+duration))+'\n');index+=1;clock+=duration+10
  f.write(json.dumps(dict(kind='summary',passed=True,drained=True,identity='iq3-p49-split32-v1',layer_complete=True,intermediate_checks_complete=True,zero_errors=True,finite_outputs=True,cpu_oracle_match=True,backend='device'))+'\n')

class Reports(unittest.TestCase):
 def test_both_decisions(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'DO-NOT-REPEAT.md').write_text('Synthetic test only\n')
   sizes=[]
   for ratio in (1.5,1.5001):
    out=root/str(ratio);out.mkdir();fixture(out/'samples.jsonl',ratio)
    with patch.object(a,'P',root):result=a.evaluate(out)
    self.assertTrue(result['decision'].startswith('build brief:' if ratio==1.5 else 'close:'))
    self.assertAlmostEqual(result['projections'][0]['implied_prefill_tps'],180/ratio)
    self.assertAlmostEqual(result['layers'][0]['ops']['layer_device_sum']['m2_over_m1'],ratio)
    self.assertEqual(json.loads((out/'analysis.json').read_text()),result)
    sizes.append((out/'samples.jsonl').stat().st_size)
   self.assertIn('1.5001/analysis.json',(root/'DO-NOT-REPEAT.md').read_text())
   self.assertLessEqual(32*1024**2,3*max(sizes))
   (a.P/'evidence/report-fixture-write-size.json').write_text(json.dumps(dict(synthetic_schema_fixture=True,device_measurement=False,measured_serialized_stream_bytes=max(sizes),planned_write_bytes=32*1024**2,planned_over_measured=(32*1024**2)/max(sizes)),indent=2)+'\n')
 def test_missing_class(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'samples.jsonl';fixture(path,1.2)
   rows=[json.loads(s) for s in path.read_text().splitlines()];rows[0]['different_bytes']=1
   path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaisesRegex(ValueError,'byte mismatch'):a.analyze(path)
 def test_summary_cannot_replace_oracle(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'samples.jsonl';fixture(path,1.2)
   rows=[json.loads(s) for s in path.read_text().splitlines()];rows[-1]['cpu_oracle_match']=False
   path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   with self.assertRaisesRegex(ValueError,'oracle gate'):a.analyze(path)
if __name__=='__main__':unittest.main()

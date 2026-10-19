"""Real parent-event parser regression plus fail-closed layer coverage checks."""
import json,statistics,tempfile,unittest
from pathlib import Path
import micro_analyze as a
class Test(unittest.TestCase):
 def test_real_parent_events(self):
  path=a.P.parent/'packet162-iq2-lookup/evidence/enum11-diagnostic-B1/samples.jsonl'
  self.assertEqual(a.sha(path),'da1d41370fe90d1368bc3925816583e2ebee77c1e45df457fe91e69ad2811fce')
  rows=a.read_events(path);samples=[r for r in rows if r['kind']=='sample' and r['shape']=='layer0' and r['fixture']==0]
  values=[[a.event_duration(r) for r in samples if r['arm']==arm] for arm in (0,1)]
  self.assertEqual(list(map(len,values)),[200,200]);self.assertEqual(statistics.median(values[0]),48334);self.assertEqual(statistics.median(values[1]),232604)
  with self.assertRaisesRegex(ValueError,'identity-matched'):a.analyze(path)
 def test_bad_timestamps(self):
  for row in ({'start_ns':0,'end_ns':1},{'start_ns':2,'end_ns':1},{'start_ns':True,'end_ns':5},{'start_ns':1,'end_ns':1}):
   with self.assertRaises(ValueError):a.event_duration(row)
 def test_cpu_refused(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'samples';p.write_text(json.dumps(dict(kind='summary',passed=True,drained=True,identity='iq3-p49-split32-v1',layer_complete=True,backend='cpu'))+'\n')
   with self.assertRaisesRegex(ValueError,'CPU output'):a.analyze(p)
 def test_no_coverage(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'samples';p.write_text(json.dumps(dict(kind='summary',passed=True,drained=True,identity='iq3-p49-split32-v1',layer_complete=True,backend='device',intermediate_checks_complete=True,zero_errors=True,finite_outputs=True,cpu_oracle_match=True))+'\n')
   with self.assertRaisesRegex(ValueError,'200 complete'):a.analyze(p)
if __name__=='__main__':unittest.main()

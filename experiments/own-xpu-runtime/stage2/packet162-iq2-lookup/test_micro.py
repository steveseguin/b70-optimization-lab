import copy,json,unittest,tempfile
from unittest.mock import patch
from pathlib import Path
from micro_analyze import analyze,check_bytes,SHAPES
P=Path(__file__).resolve().parent

def fixture(ratio=.85):
 rows=[]
 for s in SHAPES:
  for f in range(3):
   for b in range(2):rows.append(dict(kind='bytes',shape=s,fixture=f,invalid=b,different_bytes=0,bytes_equal=True))
   if f==2:continue
   for rep in range(200):
    for arm in range(2):rows.append(dict(kind='sample',shape=s,fixture=f,repeat=rep,arm=arm,start_ns=1000000,end_ns=1000000+int(10000*(ratio if arm else 1))))
 rows.append(dict(kind='summary',passed=True,drained=True,rows=640,columns=2560,diagnostic_only=True));return rows

class Tests(unittest.TestCase):
 def test_threshold(self):
  self.assertEqual(analyze(fixture())['decision'],'reopen: NaN parity + full build')
  self.assertEqual(analyze(fixture(.8501))['decision'],'close: device speed > 0.85')
 def test_partial_duplicate_order(self):
  for mutate in (lambda x:x.pop(10),lambda x:x.insert(10,x[10]),lambda x:x[9].update(arm=9)):
   x=fixture();mutate(x)
   with self.assertRaises(AssertionError):analyze(x)
 def test_nonfinite_event(self):
  x=fixture();next(r for r in x if r['kind']=='sample')['end_ns']=float('nan')
  with self.assertRaises(AssertionError):analyze(x)
 def test_finite_vs_nan(self):
  x=fixture();x[0].update(different_bytes=1,bytes_equal=False)
  self.assertEqual(analyze(x)['decision'],'blocked: finite output bytes differ')
  x=fixture();next(r for r in x if r.get('fixture')==2).update(different_bytes=1,bytes_equal=False)
  self.assertEqual(analyze(x)['decision'],'reopen: NaN parity + full build')
 def test_every_shape(self):
  x=fixture(.8)
  for r in x:
   if r['kind']=='sample' and r['shape']=='layer24' and r['arm']==1:r['end_ns']=1010000
  self.assertEqual(analyze(x)['decision'],'close: device speed > 0.85')
 def test_real_report_path(self):
  import run_micro,micro_analyze
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);out=root/'evidence/device';out.mkdir(parents=True)
   (root/'DO-NOT-REPEAT.md').write_text('historical evidence\n')
   for ratio in (.85,.86):
    (out/'samples.jsonl').write_text('\n'.join(json.dumps(r) for r in fixture(ratio))+'\n')
    with patch.object(micro_analyze,'P',root):result=run_micro.report_completed(out)
    self.assertTrue((out/'analysis.json').is_file())
   self.assertIn('Final closure',(root/'DO-NOT-REPEAT.md').read_text())
 def test_cpu_outputs(self):
  for name,shapes in [('synthetic',('synthetic',)),('real',SHAPES)]:
   rows=[json.loads(s) for s in (P/f'evidence/micro-prep/{name}-cpu.jsonl').read_text().splitlines()]
   exact,nan=check_bytes(rows,shapes);self.assertTrue(exact);self.assertTrue(nan)
   with self.assertRaises(AssertionError):analyze(rows)
if __name__=='__main__':unittest.main()

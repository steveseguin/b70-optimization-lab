"""Analyzer tests on synthetic streams AND on the REAL parent evidence (packet192's analysis.json control datums and
its samples.jsonl, which must be refused; this packet's CPU host streams, refused), so packaging failures are caught
on CPU. No device, no model."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import s193_report as R
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def spec(ratio_gate=0.78,ratio_down=0.82,**kw):
 s=dict(routes=24,cold_repeats=2,warm_repeats=20,
  **{'exp-diet':{'cold':dict(production=73750,ratio=ratio_gate),'warm':dict(production=46354,ratio=ratio_gate),'warm-real-layer0':dict(production=46145,ratio=ratio_gate),'warm-real-layer24':dict(production=46250,ratio=ratio_gate)},
     'exp-act-epilogue':{'cold':dict(production=79170,ratio=ratio_gate),'warm':dict(production=51770,ratio=ratio_gate),'warm-real-layer0':dict(production=51560,ratio=ratio_gate),'warm-real-layer24':dict(production=51670,ratio=ratio_gate)},
     'down-diet':{'cold':dict(production=45938,ratio=ratio_down),'warm':dict(production=33750,ratio=ratio_down)}});s.update(kw);return s
def stream(s):
 with tempfile.TemporaryDirectory() as d:
  R.synthetic_fixture(d,s);return R.read_rows(Path(d)/'samples.jsonl')
class Tests(unittest.TestCase):
 def test_qualified(self):
  r=R.analyze(stream(spec()));self.assertTrue(r['passed']);self.assertEqual(r['verdict'],'measured')
  for c in R.CANDIDATES:self.assertIn('qualified',r['candidates'][c]['verdict'])
  self.assertEqual(r['candidates']['exp-diet']['strata']['cold']['orders']['AB']['production']['n'],24*2)
  self.assertEqual(r['combined']['qualified'],list(R.CANDIDATES));self.assertGreater(r['combined']['projected_two_card_pct'],0)
  self.assertAlmostEqual(r['candidates']['down-diet']['layer_equivalent']['projected_one_card_pct'],r['candidates']['down-diet']['layer_equivalent']['saved_us_cold']*2/11.4,places=6)
  self.assertFalse(r['identity']['identity_as_proposed'])
 def test_closed_ratio(self):
  r=R.analyze(stream(spec(ratio_gate=0.90)));self.assertTrue(r['passed']);self.assertIn('closed',r['candidates']['exp-diet']['verdict']);self.assertIn('qualified',r['candidates']['down-diet']['verdict'])
  self.assertEqual(r['combined']['qualified'],['down-diet']);self.assertIsNone(r['combined']['gateup_pick'])
 def test_byte_kill_is_per_candidate(self):
  r=R.analyze(stream(spec(byte_mismatch=[['down-diet','down','fixture-f2-invalid']])));self.assertTrue(r['passed']);self.assertIn('withheld: byte difference',r['candidates']['down-diet']['verdict']);self.assertIn('qualified',r['candidates']['exp-diet']['verdict'])
  r=R.analyze(stream(spec(byte_mismatch=[['exp-act-epilogue','gateup','cold']])));self.assertIn('withheld',r['candidates']['exp-act-epilogue']['verdict']);self.assertEqual(r['combined']['gateup_pick'],'exp-diet')
 def test_report_kills(self):
  r=R.analyze(stream(spec(control_scale=1.15)));self.assertFalse(r['passed']);self.assertIn('control disagreement',r['verdict'])
  r=R.analyze(stream(spec(disturb=['down-diet','warm'])));self.assertFalse(r['passed']);self.assertIn('p90/median',r['verdict'])
  self.assertTrue(R.analyze(stream(spec(control_scale=1.05)))['passed'])
 def test_cpu_and_parent_streams_refused(self):
  with self.assertRaises(ValueError):R.analyze(stream(spec(cpu_only=True)))
  for name in ('cpu-host-gnu.jsonl','cpu-host-intel.jsonl'):
   path=P/'evidence'/name
   if path.is_file():
    with self.assertRaises(ValueError):R.analyze(R.read_rows(path))
  parents=json.load((P/'lineage-inputs/parent-inputs.json').open())['parents']
  for p in parents:
   if p.get('parent_relpath','').endswith('samples.jsonl'):
    with self.assertRaises(ValueError):R.analyze(R.read_rows(ROOT/p['parent_relpath']))   # packet192's stream: different schema
 def test_packet192_controls_are_the_real_datums(self):
  a=json.load((ROOT/'experiments/own-xpu-runtime/stage2/packet192-expert-issue-floor/evidence/issue-floor-B1/analysis.json').open())
  self.assertTrue(a['passed'] and a['verdict']=='measured')
  for k in ('gateup','down'):
   for s in ('cold','warm'):self.assertAlmostEqual(a['kernels'][k]['strata'][s]['median_us'],R.PACKET192_US[k][s],places=3)
  self.assertAlmostEqual(a['kernels']['gateup']['follow_on_bars_us']['exp-diet']['cold_bar_us'],0.85*R.PACKET192_US['gateup']['cold'],places=3)
  self.assertEqual(a['gateup_verdict'],'instruction-issue bound: only an instruction diet can move the class')
 def test_malformed(self):
  rows=stream(spec())
  for mutate in (lambda x:x.pop(),lambda x:x.pop(5),lambda x:x.insert(10,x[10]),lambda x:[r for r in x if r.get('kind')=='sample'][0].update(end_ns=float('nan')),lambda x:[r for r in x if r.get('kind')=='bytes' and r['candidate']=='exp-act-epilogue' and r['stratum']=='exceptional'][0].update(exactness_claim=True)):
   x=json.loads(json.dumps(rows));mutate(x)
   with self.assertRaises((ValueError,TypeError,KeyError)):R.analyze(x)
 def test_evaluate_writes_report_and_rows(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);out=root/'out';R.synthetic_fixture(out,spec());(root/'DO-NOT-REPEAT.md').write_text('synthetic\n')
   with patch.object(R,'P',root):result=R.evaluate(out)
   self.assertEqual(json.loads((out/'analysis.json').read_text()),result);self.assertTrue((out/'s193_report.md').is_file())
   text=(root/'DO-NOT-REPEAT.md').read_text();self.assertEqual(text.count('packet193 '),3);self.assertEqual(result['samples_sha256'],R.sha(out/'samples.jsonl'))
if __name__=='__main__':unittest.main()

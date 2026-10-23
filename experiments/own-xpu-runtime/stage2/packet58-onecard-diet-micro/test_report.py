"""Analyzer tests on synthetic streams AND on the REAL parent evidence: packet193's real device samples.jsonl (two-card
stream, different schema: must be refused), this packet's CPU host streams (refused), plus packet193's real NaN
payload-order row class replayed into this schema (must NOT kill). No device, no model."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import s58dm_report as R
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
P193=ROOT/'experiments/own-xpu-runtime/stage2/packet193-expert-diet/evidence/diet-B1/samples.jsonl'
def spec(ratio=0.78,**kw):
 s=dict(routes=24,cold_repeats=2,warm_repeats=20,cold=dict(production=76000,ratio=ratio),warm=dict(production=48000,ratio=ratio),**{'warm-direct':dict(production=47500,ratio=ratio),'warm-real-layer0':dict(production=47800,ratio=ratio),'warm-real-layer24':dict(production=47900,ratio=ratio)});s.update(kw);return s
def stream(s):
 with tempfile.TemporaryDirectory() as d:
  R.synthetic_fixture(d,s);return R.read_rows(Path(d)/'samples.jsonl')
class Tests(unittest.TestCase):
 def test_qualified(self):
  r=R.analyze(stream(spec()));self.assertTrue(r['passed']);self.assertEqual(r['verdict'],'measured');v=r['candidates']['p58-diet']
  self.assertIn('qualified',v['verdict']);self.assertEqual(v['strata']['cold']['orders']['AB']['production']['n'],24*2)
  self.assertAlmostEqual(v['layer']['projected_one_card_pct_cold'],v['layer']['saved_us_cold']*2/11.4,places=6);self.assertGreater(v['layer']['saved_us_cold'],0)
  self.assertFalse(r['identity']['identity_as_proposed']);self.assertEqual(r['exactness']['p58-diet/production']['nan_rows'],3);self.assertEqual(r['nan_payload_order_rows'],[])
 def test_closed_ratio_and_ungated_strata(self):
  r=R.analyze(stream(spec(ratio=0.90)));self.assertTrue(r['passed']);self.assertIn('closed',r['candidates']['p58-diet']['verdict']);self.assertIn('cold',r['candidates']['p58-diet']['verdict'])
  s=spec();s['warm-direct']=dict(production=47500,ratio=0.95);r=R.analyze(stream(s));self.assertIn('qualified',r['candidates']['p58-diet']['verdict']);self.assertIn('above 0.85',r['candidates']['p58-diet']['ungated_strata']['warm-direct'])
 def test_byte_kill_withholds_candidate(self):
  r=R.analyze(stream(spec(byte_mismatch=[['fixture-f1-invalid','production']])));self.assertTrue(r['passed']);self.assertIn('withheld: byte difference',r['candidates']['p58-diet']['verdict'])
  r=R.analyze(stream(spec(byte_mismatch=[['slots-shuffled','fixture']])));self.assertIn('withheld',r['candidates']['p58-diet']['verdict'])
 def test_nan_payload_order_never_kills_but_value_does(self):
  r=R.analyze(stream(spec(nan_payload=['exceptional','fixture-f2-valid'])));self.assertTrue(r['passed']);self.assertIn('qualified',r['candidates']['p58-diet']['verdict'])
  self.assertEqual(len(r['nan_payload_order_rows']),2*3)   # production/fixture, candidate/production, candidate/fixture x 2 strata
  r=R.analyze(stream(spec(nan_value_mismatch=['exceptional'])));self.assertTrue(r['passed']);self.assertIn('withheld: value difference or status/error byte in a NaN-only stratum',r['candidates']['p58-diet']['verdict'])
  r=R.analyze(stream(spec(nan_value_mismatch=['fixture-f2-invalid'],nan_value_on_production=True)));self.assertFalse(r['passed']);self.assertIn('NaN-only stratum',r['verdict']);self.assertEqual(r['candidates']['p58-diet']['verdict'],'withheld')
 def test_report_kills(self):
  r=R.analyze(stream(spec(control_scale=1.15)));self.assertFalse(r['passed']);self.assertIn('fresh production-only pass',r['verdict']);self.assertEqual(r['candidates']['p58-diet']['verdict'],'withheld')
  r=R.analyze(stream(spec(disturb='warm')));self.assertFalse(r['passed']);self.assertIn('p90/median',r['verdict'])
  self.assertTrue(R.analyze(stream(spec(control_scale=1.05)))['passed'])
 def test_cpu_and_parent_streams_refused(self):
  with self.assertRaises(ValueError):R.analyze(stream(spec(cpu_only=True)))
  for name in ('cpu-host-gnu.jsonl','cpu-host-intel.jsonl'):
   path=P/'evidence'/name
   if path.is_file():
    with self.assertRaises(ValueError):R.analyze(R.read_rows(path))
  self.assertTrue(P193.is_file(),'packet193 real samples required')
  with self.assertRaises(ValueError):R.analyze(R.read_rows(P193))   # packet193's two-card stream: different schema
 def test_packet193_real_nan_payload_row_is_diagnostic_here(self):
  # The real row that stopped packet193's window (production vs GNU fixture on the NaN-only exceptional stratum: 2,353
  # NaN-vs-NaN words, 0 other bytes). Replayed into this packet's schema it must be nan_equal and must not kill.
  real=next(r for r in R.read_rows(P193) if r.get('kind')=='bytes' and r['candidate']=='production' and r['stratum']=='exceptional' and r['against']=='fixture')
  self.assertEqual((real['different_words'],real['nan_vs_nan_words'],real['other_bytes']),(2353,2353,0))
  rows=stream(spec())
  for r in rows:
   if r.get('kind')=='bytes' and r['stratum']=='exceptional' and r['candidate']=='production':
    r.update(different_bytes=real['different_bytes'],bytes_equal=False,different_words=real['different_words'],nan_vs_nan_words=real['nan_vs_nan_words'],other_bytes=0,payload_order_only=True,nan_equal=True)
  r=R.analyze(rows);self.assertTrue(r['passed']);self.assertIn('qualified',r['candidates']['p58-diet']['verdict']);self.assertEqual(len(r['nan_payload_order_rows']),1)
  import run_micro
  with tempfile.TemporaryDirectory() as d:
   Path(d,'samples.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
   with patch.object(run_micro,'CANDIDATES',R.CANDIDATES),patch.object(run_micro,'COLD_REPEATS',2),patch.object(run_micro,'WARM_REPEATS',20):
    with self.assertRaises(ValueError):run_micro.native_summary(Path(d,'samples.jsonl'))   # routes 24 != 384: identity refused, after the byte gate accepted the payload-order row
   for x in rows:
    if x.get('kind')=='summary':x['route_count']=384
   Path(d,'samples.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
   with patch.object(run_micro,'COLD_REPEATS',2),patch.object(run_micro,'WARM_REPEATS',20):
    s=run_micro.native_summary(Path(d,'samples.jsonl'));self.assertEqual(len(s['nan_payload_order_rows']),1)
   bad=[dict(x) for x in rows]
   for x in bad:
    if x.get('kind')=='bytes' and x['stratum']=='warm' and x['candidate']=='p58-diet' and x['against']=='production':x.update(different_bytes=2,bytes_equal=False,different_words=1,other_bytes=0)
   Path(d,'samples.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in bad))
   with patch.object(run_micro,'COLD_REPEATS',2),patch.object(run_micro,'WARM_REPEATS',20):
    with self.assertRaisesRegex(ValueError,'claimed stratum'):run_micro.native_summary(Path(d,'samples.jsonl'))
 def test_malformed(self):
  rows=stream(spec())
  for mutate in (lambda x:x.pop(),lambda x:x.pop(5),lambda x:x.insert(10,x[10]),lambda x:[r for r in x if r.get('kind')=='sample'][0].update(end_ns=float('nan')),lambda x:[r for r in x if r.get('kind')=='bytes' and r['stratum']=='exceptional'][0].update(exactness_claim=True),lambda x:[r for r in x if r.get('kind')=='sample' and r['candidate']=='control'][0].update(arm='candidate')):
   x=json.loads(json.dumps(rows));mutate(x)
   with self.assertRaises((ValueError,TypeError,KeyError)):R.analyze(x)
 def test_evaluate_writes_report_and_rows(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);out=root/'out';R.synthetic_fixture(out,spec());(root/'DO-NOT-REPEAT.md').write_text('synthetic\n')
   with patch.object(R,'P',root):result=R.evaluate(out)
   self.assertEqual(json.loads((out/'analysis.json').read_text()),result);self.assertTrue((out/'s58dm_report.md').is_file())
   text=(root/'DO-NOT-REPEAT.md').read_text();self.assertEqual(text.count('packet58-onecard-diet-micro p58-diet'),1);self.assertEqual(result['samples_sha256'],R.sha(out/'samples.jsonl'))
if __name__=='__main__':unittest.main()

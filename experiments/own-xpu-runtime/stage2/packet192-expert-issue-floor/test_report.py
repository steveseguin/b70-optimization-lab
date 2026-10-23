"""Analyzer tests on synthetic streams AND on the REAL parent summaries (packet100b micro-B, packet162b, this
packet's CPU host streams), so packaging failures are caught on CPU. No device, no model."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import s192_report as R
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
BASE=dict(gateup=dict(cold=60400,warm=48300,**{'warm-real-layer0':48300,'warm-real-layer24':47900},noload=47000),down=dict(cold=46000,warm=30000,noload=29000))
def stream(spec):
 with tempfile.TemporaryDirectory() as d:
  R.synthetic_fixture(d,spec);return R.read_rows(Path(d)/'samples.jsonl')
class Tests(unittest.TestCase):
 def test_verdicts(self):
  r=R.analyze(stream(BASE));self.assertTrue(r['passed']);self.assertEqual(r['gateup_verdict'],'instruction-issue bound: only an instruction diet can move the class')
  self.assertEqual(r['kernels']['gateup']['strata']['cold']['n'],384*20*2);self.assertEqual(r['kernels']['gateup']['strata']['warm']['n'],400)
  lat=json.loads(json.dumps(BASE));lat['gateup']['noload']=30000;lat['down']['noload']=20000
  self.assertEqual(R.analyze(stream(lat))['down_verdict'],'load-latency exposed: LSC prefetch is the candidate')
  mix=json.loads(json.dumps(BASE));mix['gateup']['noload']=40000
  self.assertEqual(R.analyze(stream(mix))['gateup_verdict'],'mixed')
 def test_kill_rules(self):
  r=R.analyze(stream(dict(BASE,byte_mismatch_routes=[['gateup','cold',3]])));self.assertFalse(r['passed']);self.assertIn('byte difference',r['verdict'])
  r=R.analyze(stream(dict(BASE,alias_ok=False)));self.assertFalse(r['passed']);self.assertIn('alias self-test',r['verdict'])
  r=R.analyze(stream(dict(BASE,pass_drift=0.12)));self.assertFalse(r['passed']);self.assertIn('disagreement',r['verdict'])
  r=R.analyze(stream(dict(BASE,disturb_stratum=['down','cold'])));self.assertFalse(r['passed']);self.assertIn('p90/median',r['verdict'])
  self.assertTrue(R.analyze(stream(dict(BASE,pass_drift=0.05)))['passed'])
 def test_cpu_streams_refused(self):
  with self.assertRaises(ValueError):R.analyze(stream(dict(BASE,cpu_only=True)))
  for name in ('cpu-host-gnu.jsonl','cpu-host-intel.jsonl'):
   path=P/'evidence'/name
   if path.is_file():
    with self.assertRaises(ValueError):R.analyze(R.read_rows(path))
 def test_malformed(self):
  rows=stream(BASE)
  for mutate in (lambda x:x.pop(),lambda x:x.pop(5),lambda x:x.insert(10,x[10]),lambda x:[r for r in x if r.get('kind')=='sample'][0].update(end_ns=float('nan'))):
   x=json.loads(json.dumps(rows));mutate(x)
   with self.assertRaises((ValueError,TypeError,KeyError)):R.analyze(x)
 def test_real_parent_streams_refused_and_datums(self):
  parents=json.load((P/'lineage-inputs/parent-inputs.json').open())['parents']
  for p in parents:
   if p.get('parent_relpath','').endswith('samples.jsonl'):
    rows=R.read_rows(ROOT/p['parent_relpath'])
    with self.assertRaises(ValueError):R.analyze(rows)   # packet100b/packet162b device streams are a different schema
  datums=R.reference_data(parents)
  self.assertAlmostEqual(datums['packet100b_down_tile16_cold_median_us'],R.PARENT_DATUM_US['down_cold_tile16'],places=3)
  self.assertAlmostEqual(datums['packet100b_p65_production_cold_median_us'],66.25,places=2)
  self.assertAlmostEqual(datums['packet162b_gateup_warm_median_us']['layer0/0'],48.334,places=3)
 def test_evaluate_writes_report_and_row(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);out=root/'out';R.synthetic_fixture(out,BASE);(root/'DO-NOT-REPEAT.md').write_text('synthetic\n')
   with patch.object(R,'P',root):result=R.evaluate(out)
   self.assertEqual(json.loads((out/'analysis.json').read_text()),result);self.assertTrue((out/'s192_report.md').is_file())
   self.assertIn('packet192 issue-floor measurement',(root/'DO-NOT-REPEAT.md').read_text());self.assertEqual(result['samples_sha256'],R.sha(out/'samples.jsonl'))
 def test_small_identity_flagged(self):
  r=R.analyze(stream(dict(BASE,cold_repeats=1,warm_repeats=20)));self.assertTrue(r['passed']);self.assertFalse(r['identity']['identity_as_proposed'])
  self.assertTrue(R.analyze(stream(BASE))['identity']['identity_as_proposed'])
  with self.assertRaises(ValueError):R.analyze(stream(dict(BASE,warm_repeats=5)))
 def test_follow_on_bars(self):
  r=R.analyze(stream(BASE));bars=r['kernels']['gateup']['follow_on_bars_us']
  self.assertAlmostEqual(bars['exp-diet']['cold_bar_us'],0.85*r['kernels']['gateup']['strata']['cold']['median_us'],places=6)
  self.assertGreater(bars['exp-act-epilogue']['cold_bar_us'],bars['exp-diet']['cold_bar_us']);self.assertIn('down-diet',r['kernels']['down']['follow_on_bars_us'])
if __name__=='__main__':unittest.main()

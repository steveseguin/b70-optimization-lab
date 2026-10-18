"""CPU-only receipt, model and admission refusal tests. No device imports."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import report
import run_micro as runner
P=Path(__file__).resolve().parent

def fixture():
    rows=[]
    for rep in range(200):
        for case,size in [('hidden',5120),('best8',8),('best16',16),('pipeline20480',20480),('mailbox20480',20480)]:
            for busy in ([False] if case=='mailbox20480' else [False,True]):
                rows.append(dict(kind='sample',case=case,bytes=size,rep=rep,concurrent=busy,
                                 source_card=3 if case=='hidden' else 2,destination_card=2 if case=='hidden' else 3,
                                 start_s=0.,export_done_s=.00001,usable_s=.00003,total_us=30.,export_us=10.,import_us=20.,host_boundary_us=2.,bytes_exact=True,token_upload_bytes=4 if case=='pipeline20480' else 0,export_compute_pending=busy,import_compute_pending=busy))
    rows.append(dict(kind='summary',passed=True,drained=True,samples=1800,repetitions=200))
    return rows

class ReceiptTests(unittest.TestCase):
    def test_complete(self):
        result=report.summarize(fixture());self.assertEqual(len(result),9)
        self.assertEqual(result['hidden/idle']['total_us']['median'],30.)
    def test_refuse_partial(self):
        with self.assertRaises(ValueError):report.summarize(fixture()[1:])
    def test_reject_mutations(self):
        mutations=[('bytes',4096),('source_card',2),('bytes_exact',False),('total_us',float('nan')),
                   ('total_us',-1.),('total_us',999.),('rep',1),('case','unknown'),('concurrent',1),('export_done_s',1.)]
        for key,value in mutations:
            with self.subTest(key=key,value=value):
                rows=fixture();rows[0][key]=value
                with self.assertRaises(ValueError):report.summarize(rows)
    def test_requires_drain(self):
        rows=fixture();rows[-1]['drained']=False
        with self.assertRaises(ValueError):report.summarize(rows)
    def test_nearest_rank_p90(self):self.assertEqual(report.stats(range(200))['p90'],179)
    def test_original_equations(self):
        ns,prior=report.equations(P)
        for option in ('target','draft'):
            self.assertEqual(ns['optimum'](option),prior['options'][option]['known_boundary_only_optimum'])
    def test_zero_and_large_cost(self):
        summary=report.summarize(fixture());r=report.predict(P,summary)
        self.assertTrue(all(row['design_threshold_passed'] for row in r['options'].values()))
        for row in summary.values():
            for stat in (v for k,v in row.items() if k!='compute_pending_counts'):stat.update(median=10000.,p90=10000.)
        r=report.predict(P,summary)
        self.assertFalse(any(row['design_threshold_passed'] for row in r['options'].values()))
    def test_cost_monotonicity(self):
        ns,_=report.equations(P)
        for option in ('target','draft'):
            rates=[ns['optimum'](option,(x,x,x))['predicted_tok_s'] for x in (0.,.01,.1,1.)]
            self.assertEqual(rates,sorted(rates,reverse=True))
    def test_idle_decision_does_not_double_count_compute(self):
        summary=report.summarize(fixture());a=report.predict(P,summary)
        for key,values in summary.items():
            if key.endswith('/compute'):
                for row in (v for k,v in values.items() if k!='compute_pending_counts'):row.update(median=10000.,p90=10000.)
        b=report.predict(P,summary);self.assertEqual(a['options'],b['options'])
    def test_unreceipted_samples_refused(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'evidence/micro-B').mkdir(parents=True);(p/'evidence/micro-B/window.json').write_text('{}');(p/'evidence/microbench-build.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'device receipt'):report.evaluate(p)

    def test_receipt_to_design_and_closeout(self):
        # Synthetic receipts live only in a disposable tree; never lab evidence.
        with tempfile.TemporaryDirectory(prefix='p87t-report-test-') as t:
            stage=Path(t)/'repo/experiments/lane/stage2';stage.mkdir(parents=True)
            packet=stage/'packet87t';out=packet/'evidence/micro-B';out.mkdir(parents=True)
            (packet/'build').mkdir();(packet/'build/microbench').write_bytes(b'test fixture, not executable')
            (packet/'report.py').write_bytes((P/'report.py').read_bytes())
            (packet/'runner-pins.json').write_text('{}')
            for parent in ('packet87-slack-model','packet85-critical-path'):
                (stage/parent).symlink_to(P.parent/parent,target_is_directory=True)
            identity=dict(artifacts={'build/microbench':report.sha(packet/'build/microbench')})
            (packet/'evidence/microbench-build.json').write_text(json.dumps(identity))
            rows=fixture()
            for latency in (30.,30000.):
                for row in rows[:-1]:
                    row.update(export_done_s=latency/3/1e6,usable_s=latency/1e6,total_us=latency,export_us=latency/3,import_us=latency*2/3)
                (out/'samples.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
                window=dict(passed=True,drained=True,device_executed=True,lane='B',physical_cards=[2,3],
                    samples_sha256=report.sha(out/'samples.jsonl'),binary_sha256=report.sha(packet/'build/microbench'),
                    build_receipt_sha256=report.sha(packet/'evidence/microbench-build.json'),
                    runner_pins_sha256=report.sha(packet/'runner-pins.json'),device_isolation={'passed':True})
                (out/'window.json').write_text(json.dumps(window))
                result=report.evaluate(packet)
                self.assertEqual(any(r['design_threshold_passed'] for r in result['prediction']['options'].values()),latency==30.)
                self.assertTrue((packet/('DESIGN.md' if latency==30. else 'DO-NOT-REPEAT.md')).is_file())
            (out/'samples.jsonl').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'sample receipt mismatch'):report.evaluate(packet)

class AdmissionTests(unittest.TestCase):
    def test_memory_floor(self):
        with patch.object(runner.M,'meminfo',return_value={'MemAvailable':10*runner.GIB-1}):
            with self.assertRaises(ValueError):runner.memory_admit()
    def test_memory_boundary(self):
        with patch.object(runner.M,'meminfo',return_value={'MemAvailable':10*runner.GIB}):
            self.assertEqual(runner.memory_admit()['host_reserve_bytes'],8*runner.GIB)
    def test_memory_before_lease_and_launch(self):
        tree=ast.parse((P/'run_micro.py').read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        calls=[n for n in ast.walk(main) if isinstance(n,ast.Call)]
        first=lambda name:min(n.lineno for n in calls if isinstance(n.func,ast.Name) and n.func.id==name)
        self.assertLess(first('memory_admit'),first('Reservation'))
        self.assertLess(first('storage_admit'),first('Reservation'))
        self.assertLess(first('Reservation'),min(n.lineno for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr=='Popen'))
    def test_plan_short_circuits_device_path(self):
        with patch.object(runner,'build_gate',return_value={}),patch.object(runner,'cpu_gate'),patch.object(runner,'lane_gate',side_effect=AssertionError('device path')),patch('builtins.print'):
            self.assertEqual(runner.main(['--run','--plan']),0)
    def test_no_mode_refused(self):
        with self.assertRaises(ValueError):runner.main([])
    def test_wrong_output_refused(self):
        with self.assertRaises(ValueError):runner.main(['--plan','--output','/tmp/foreign-output'])
    def test_native_summary_refuses_partial(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'sample';p.write_text('{"kind":"summary","passed":true,"drained":false}')
            with self.assertRaises(ValueError):runner.native_summary(p)
    def test_build_closure(self):self.assertIn('binary_sha256',runner.build_gate())

if __name__=='__main__':unittest.main(verbosity=2)

"""Packet169 regression gates; all new fixture trees live in /tmp."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import launch_env
import rehearse_entry as entry
import rehearse_report_adapters as adapters


CONTRACT = dict(schema='own-runtime.report-contract.v1', analyzer='analysis:evaluate',
    fixture_generator='fixture:generate',
    samples=dict(path='events.jsonl', format='jsonl', required={'duration': 'int'}),
    analysis=dict(path='report.json', format='json', required={'decision': 'str', 'diagnostic_only': 'bool'}),
    cases=[dict(name='accept', fixture={'duration': 8}, expected={'decision': 'accept', 'diagnostic_only': True}),
           dict(name='close', fixture={'duration': 12}, expected={'decision': 'close', 'diagnostic_only': True})])


class ReportContracts(unittest.TestCase):
    def test_packet162_deterministic_receipt_bytes(self):
        path=entry.ROOT/'experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/micro_analyze.py'
        namespace={'__file__':str(path),'__name__':'_legacy_analyzer'}
        exec(compile(path.read_text(),str(path),'exec'),namespace)
        expected={
            'DO-NOT-REPEAT.md':'fe6bf73478033c5e8e61cc93794565c44be9ede4bf43449cfc625dd7e19642c0',
            'close/analysis.json':'7ce6e57805c0c950bf0ea9cc876534a97e671b1c76ec311c48eff3b7a553c22e',
            'close/samples.jsonl':'3f548ce31c058a529155c45f0c51d1e5b2c3b6a13258a818e9c6f01985d319f8',
            'reopen/analysis.json':'13f59bd5451df761b00ab2e1d16307a39359196bda8d1065f89c9b3dcb044598',
            'reopen/samples.jsonl':'8a84a54c2e4fa60675dc08df553d29f322b33d9085ce4dd814c3c60ff85ec19a'}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);namespace['P']=root
            (root/'DO-NOT-REPEAT.md').write_text('Synthetic rehearsal only\n')
            for name,duration in [('reopen',8500),('close',8600)]:
                out=root/name;out.mkdir();entry.synthetic_micro(out,duration)
                namespace['evaluate'](out)
            self.assertEqual({str(p.relative_to(root)):entry.digest(p) for p in root.rglob('*') if p.is_file()},expected)

    def fixture(self, root):
        (root / 'run_micro.py').write_text('''import argparse
from analysis import evaluate
def parser():
    p=argparse.ArgumentParser();p.add_argument('--lane');return p
def report_completed(output):
    return evaluate(output)
''')
        (root / 'analysis.py').write_text('''import json
def evaluate(output):
    value=json.loads((output/'events.jsonl').read_text())
    result=dict(decision='accept' if value['duration']<10 else 'close',diagnostic_only=True)
    (output/'report.json').write_text(json.dumps(result))
    return result
''')
        (root / 'fixture.py').write_text('''import json
def generate(output, parameters):
    (output/'events.jsonl').write_text(json.dumps(parameters)+'\\n')
''')
        (root / 'report-contract.json').write_text(json.dumps(CONTRACT))
        return dict(name='contract-B', lane='B', argv=['/usr/bin/python3', '-B', str(root/'run_micro.py'), '--lane', 'B'])

    def run_report(self, job, root):
        return entry.rehearse_report(job, launch_env.environment(), root)

    def test_new_schema_real_analyzer_both_decisions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);job=self.fixture(root)
            result=self.run_report(job, root)
            self.assertTrue(result['passed'], result)
            self.assertEqual([c['name'] for c in result['kinds'][0]['cases']], ['accept','close'])

    def test_missing_and_malformed_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);job=self.fixture(root)
            path=root/'report-contract.json'
            path.unlink()
            result=self.run_report(job, root)
            self.assertFalse(result['passed'])
            self.assertEqual(result['kinds'][0]['error'], 'missing report contract for standalone micro schema')
            path.write_text('{"schema":"wrong"}')
            result=self.run_report(job, root)
            self.assertFalse(result['passed'])
            self.assertEqual(result['kinds'][0]['error'], 'malformed report contract')

    def test_contract_validation_rejects_unsafe_or_ambiguous_fields(self):
        mutations=[('samples', {'path':'../outside','format':'jsonl','required':{'x':'int'}}),
                   ('analyzer','os:system'), ('cases', []), ('cases', [CONTRACT['cases'][0]]*2),
                   ('samples', []), ('fixture_generator', 'fixture:generate; print(1)')]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'report-contract.json'
            for key,value in mutations:
                c=copy.deepcopy(CONTRACT);c[key]=value;path.write_text(json.dumps(c))
                if value=='os:system':
                    with self.assertRaises(adapters.ContractError):adapters.local_symbol(Path(d),value)
                else:
                    with self.assertRaises(adapters.ContractError):adapters.read_contract(path)

    def test_wrong_stream_wrong_decision_and_bypassed_analyzer_refuse(self):
        for mode in ('stream', 'decision', 'analyzer'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as d:
                root=Path(d);job=self.fixture(root)
                c=copy.deepcopy(CONTRACT)
                if mode=='stream':c['samples']['required']['duration']='str'
                if mode=='decision':c['cases'][0]['expected']['decision']='wrong'
                if mode=='analyzer':
                    (root/'analysis.py').write_text((root/'analysis.py').read_text()+'\ndef unused(output): return {}\n')
                    c['analyzer']='analysis:unused'
                (root/'report-contract.json').write_text(json.dumps(c))
                self.assertFalse(self.run_report(job,root)['passed'])

    def test_generator_cannot_read_host_data_even_if_caught(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);job=self.fixture(root)
            p=root/'fixture.py'
            p.write_text(p.read_text().replace("    (output/", "    try: open('/etc/passwd').read()\n    except PermissionError: pass\n    (output/"))
            result=self.run_report(job,root)
            self.assertFalse(result['passed'],result)

    def test_window_metadata_and_invalid_cap(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'READY-FOR-DEVICE.json').write_text(json.dumps(dict(arm_order=['a','b','a'],max_new=32)))
            self.assertEqual(adapters.window_shape({},root,'bracket'),dict(arm_order=['a','b','a'],max_new=32))
            self.assertEqual(adapters.window_shape({},root,'smoke'),{})
            for cap in (False,0,513):
                with self.assertRaises(adapters.ContractError):
                    adapters.window_shape({'plan':{'entry_rehearsal':{'window':{'max_new':cap}}}},root,'bracket')

    def test_packet166_missing_contract_is_explicit(self):
        path=entry.OPS/'lane-queue/proposed-p166-micro-B.txt'
        if not path.exists():
            path=next((entry.OPS/'lane-queue').glob('proposed-p166*'))
        job=json.loads(next(x for x in path.read_text().splitlines() if x.startswith('{')))
        result=self.run_report(job,entry.ROOT)
        self.assertFalse(result['passed'],result)
        self.assertEqual(result['kinds'][0]['error'],'missing report contract for standalone micro schema')

    def test_packet58aq_six_views(self):
        path=entry.OPS/'lane-queue/proposed-p58aq-split-A.txt'
        job=json.loads(next(x for x in path.read_text().splitlines() if x.startswith('{')))
        result=self.run_report(job,entry.ROOT)
        self.assertTrue(result['passed'],result)
        self.assertEqual([r['request_count'] for r in result['kinds']],[12,72])


if __name__=='__main__':
    unittest.main()

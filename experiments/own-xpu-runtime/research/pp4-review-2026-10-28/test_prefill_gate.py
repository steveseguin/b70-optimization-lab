"""CPU-only registration and actual-pair identity tests."""
import unittest
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import mock
import prefill_gate as gate


class GateTests(unittest.TestCase):
    def test_failed_lifecycle_never_enters_comparison(self):
        lifecycle = SimpleNamespace(execute=mock.Mock(side_effect=ValueError('native finish failed')))
        backend = SimpleNamespace(base=SimpleNamespace(), bridge=SimpleNamespace(Stage=object),
            rolling_driver=SimpleNamespace(live=SimpleNamespace(target=SimpleNamespace(lifecycle=lifecycle))))
        with mock.patch.object(gate, 'dependencies', return_value=(backend, None)), mock.patch.object(gate, 'compare_completed') as compare:
            with self.assertRaisesRegex(ValueError, 'native finish failed'):
                gate.execute({}, {}, 'mock.service')
            compare.assert_not_called()

    def test_comparison_requires_clean_final_lifecycle_before_attach(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            plan = dict(output=str(output), stages=[dict(id=0), dict(id=1)])
            def require(value, message):
                if not value: raise ValueError(message)
            base = SimpleNamespace(require=require, save=lambda p,v: Path(p).write_text(json.dumps(v)))
            manifests = [output/'serial.json', output/'pipeline.json']
            events = []
            attach = SimpleNamespace(attach=lambda p: events.append(('attach', p)) or p)
            comparator = SimpleNamespace(load_set=lambda p: events.append(('load', p)) or {}, compare=lambda *sets: dict(passed=True))
            with mock.patch.dict('sys.modules', attach_prefill_provenance=attach, compare_pipeline_state=comparator, compare_draft_state=comparator):
                good = dict(passed=True, error=None, live_pids=[], returncodes={'0':0,'1':0})
                for bad in [dict(good, passed=False), dict(good, error='failure'), dict(good, live_pids=[9]), dict(good, returncodes={'0':0}), dict(good, returncodes={'0':0,'1':1})]:
                    (output/'result.json').write_text(json.dumps(bad))
                    with self.assertRaises(ValueError): gate.compare_completed(plan, base, manifests)
                    self.assertEqual(events, [])
                (output/'result.json').write_text(json.dumps(good))
                gate.compare_completed(plan, base, manifests)
                self.assertEqual([x[0] for x in events[:2]], ['attach','attach'])
                self.assertTrue((output/'target-comparison.json').exists())
                self.assertTrue((output/'draft-comparison.json').exists())

    def test_modes_are_explicit_and_request_plan_is_retained(self):
        original = dict(epoch=1, other='retained')
        self.assertFalse(gate.selected_plan(original, 1)['prefill_pipeline'])
        self.assertTrue(gate.selected_plan(original, 2)['prefill_pipeline'])
        self.assertNotIn('prefill_pipeline', original)
        self.assertEqual(gate.selected_plan(original, 2)['other'], 'retained')
        with self.assertRaises(ValueError):
            gate.selected_plan(original, 3)

    def test_pair_hash_binds_actual_hidden_and_tokens(self):
        a = [gate.pair(1, 7, b'hidden-a'), gate.pair(2, 8, b'hidden-b')]
        digest = gate.validate_pairs(a, 3)
        b = [gate.pair(1, 7, b'hidden-c'), a[1]]
        self.assertNotEqual(digest, gate.validate_pairs(b, 3))
        c = [gate.pair(1, 9, b'hidden-a'), a[1]]
        self.assertNotEqual(digest, gate.validate_pairs(c, 3))
        self.assertEqual(digest, gate.validate_pairs(list(a), 3))

    def test_missing_duplicate_or_out_of_order_pairs_refused(self):
        a = gate.pair(1, 7, b'a')
        for rows in ([a], [a, a], [gate.pair(2, 8, b'b'), a]):
            with self.assertRaises(ValueError):
                gate.validate_pairs(rows, 3)


    def test_lifecycle_driver_manifest_schema_with_retained_receipts(self):
        retained = Path('/dev/shm/sc117-pp4-262k-qualification/run-10')
        if not (retained/'plan.json').exists():
            self.skipTest('retained run-10 fixture unavailable')
        plan = json.loads((retained/'plan.json').read_text())
        records = []
        for index, name in enumerate(('serial', 'pipeline')):
            record = json.loads((retained/'requests'/f'request-{index+1:06d}'/'result.json').read_text())
            record.update(id=name, index=index)
            records.append(record)
        def save(path, value):
            Path(path).write_text(json.dumps(value))
        base = SimpleNamespace(SLOT=65536, save=save,
            require=lambda condition, message: self.assertTrue(condition, message))
        class FakeStage:
            stream_bytes = 16
            shared = bytearray(200000)
            def command(self, *args, **kwargs):
                return ('reply',)
            def issue_provider(self, command):
                return None
        def native_drive(stages, chosen, guard, destination, *, epoch):
            index = epoch-1
            self.assertEqual(chosen['prefill_pipeline'], bool(index))
            position = records[index]['driver_result']['input_position']
            for p in range(1, position-1):
                stages[0].command(9, token=p, position=p)
            stages[0].issue_provider(SimpleNamespace(seed=SimpleNamespace(
                row=SimpleNamespace(position=position-1, token=7)),
                parent=SimpleNamespace(handoff=SimpleNamespace(hidden=b'canonical-hidden'))))
            return records[index]['driver_result']
        bridge = SimpleNamespace(Stage=FakeStage, drive=native_drive)
        loaded = []
        def load_set(path):
            spec = json.loads(Path(path).read_text())
            loaded.append(spec)
            if spec['schema'] == 'ownrt.pipeline-state-set.v7':
                index = 0 if 'request-00-' in str(path) else 1
                self.assertEqual(spec['ring_epoch'], records[index]['epoch'])
                self.assertEqual(spec['ring_request_sha256'], records[index]['request_sha256'])
                self.assertEqual(spec['input_identity']['position'], records[index]['driver_result']['input_position'])
                for item, receipt in zip(spec['stages'], records[index]['reset_receipts']):
                    native = Path(receipt['native_output'])
                    self.assertEqual(item['dump'], str(native/f'state-{2000000000+index}'))
                    self.assertEqual(item['metadata'], str(native/'pipeline-stage.json'))
                    self.assertEqual(item['quiescence'], item['dump']+'.ring-state.json')
                self.assertEqual(spec['draft_input_identity']['arithmetic'], 'F32-target/BF16-draft')
            return spec
        comparator = SimpleNamespace(load_set=load_set, compare=lambda a, b: dict(passed=True))
        def suite_run(stages, run_plan, guard, output, drive):
            for index, record in enumerate(records):
                destination = output/f"request-{index:02d}-{record['id']}"
                destination.mkdir()
                drive(stages, dict(run_plan, epoch=index+1), guard, destination, epoch=index+1)
                selected = json.loads((destination/'selected-request-plan.json').read_text())
                self.assertEqual(selected['prefill_pipeline'], bool(index))
                captured = json.loads((destination/'canonical-pairs.json').read_text())
                self.assertEqual(len(captured['pairs']), record['driver_result']['input_position']-1)
                self.assertEqual(captured['sha256'], gate.validate_pairs(captured['pairs'], record['driver_result']['input_position']))
            return dict(requests=records)
        def lifecycle(plan, admission, unit, **kwargs):
            self.assertFalse(kwargs['scripted_proposals'])
            self.assertTrue(issubclass(kwargs['stage_type'], bridge.Stage))
            result = kwargs['driver']([kwargs['stage_type']()], plan, None, output)
            save(output/'result.json', dict(result, passed=True, error=None, live_pids=[], returncodes={str(x['id']):0 for x in plan['stages']}))
            return None
        backend = SimpleNamespace(base=base, bridge=bridge,
            rolling=SimpleNamespace(run=suite_run),
            rolling_driver=SimpleNamespace(live=SimpleNamespace(target=SimpleNamespace(
                lifecycle=SimpleNamespace(execute=lifecycle)))))
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            plan['output'] = str(output)
            with mock.patch.object(gate, 'dependencies', return_value=(backend, None)), \
                 mock.patch.dict('sys.modules', compare_pipeline_state=comparator, compare_draft_state=comparator, attach_prefill_provenance=SimpleNamespace(attach=lambda p:p)):
                gate.execute(plan, {}, 'mock.service')
            self.assertTrue((output/'target-comparison.json').exists())
            self.assertTrue((output/'draft-comparison.json').exists())
        self.assertEqual(len(loaded), 4)


if __name__ == '__main__':
    unittest.main()

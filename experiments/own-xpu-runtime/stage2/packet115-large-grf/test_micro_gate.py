"""CPU-only refusal tests for missing evidence, repeated processes and speed attribution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import micro_gate as gate


def fixture(ratio=0.84):
    rows = []
    for route in range(gate.ROUTE_COUNT):
        for name in gate.CANDIDATES:
            height, width = gate.shape(name)
            for control in gate.CONTROLS:
                common = dict(route=route, control=control, rows=height, columns=width, count=10, experts=512)
                rows.append(dict(kind='correctness', view=name, all_bytes_exact=True, bf16_exact=True, status_exact=True, **common))
                for rep in (0, 1):
                    for pos in (0, 1):
                        view = name if pos ^ (rep & 1) else control
                        rows.append(dict(kind='sample', pair=name, view=view, repeat=rep, position=pos,
                            event_ns=100000 * ratio if view == name else 100000,
                            wg=64, sg=32, scrub_bytes=536870912, diagnostic_only=True, **common))
    rows.append(dict(kind='summary', passed=True, drained=True, diagnostic_only=True,
                     route_count=384, candidates=list(gate.CANDIDATES)))
    return rows


def windows():
    return [dict(repeat=n, passed=True, device_executed=True, drained=True, lease_released=True,
                 pid=100+n, process_start_ticks=200+n, boot_id='boot', started_utc_ns=n*100,
                 finished_utc_ns=n*100+50) for n in (1, 2)]


class MicroGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.good = fixture()

    def test_full_capture_and_inclusive_boundary(self):
        for ratio in (0.84, 0.85):
            self.assertEqual(gate.analyze(fixture(ratio))['qualified'], list(gate.CANDIDATES))

    def test_single_route_outlier_is_retained_without_extra_speed_gate(self):
        rows = copy.deepcopy(self.good)
        sample = next(r for r in rows if r['kind'] == 'sample' and r['route'] == 383
                      and r['pair'] == 'e5-shared' and r['control'] == 'production-large'
                      and r['view'] == 'e5-shared' and r['repeat'] == 1)
        sample['event_ns'] = 85001
        result = gate.analyze(rows)
        self.assertEqual(result['qualified'], list(gate.CANDIDATES))
        control = result['candidates']['e5-shared']['controls']['production-large']
        self.assertGreater(control['worst_route_ratio'], 0.85)
        self.assertFalse(result['threshold']['every_route'])
        self.assertTrue(result['threshold']['all_routes_measured'])
        self.assertEqual(len(control['routes']), 384)

    def test_opposite_order_median_over_bar_rejects_only_candidate(self):
        rows = copy.deepcopy(self.good)
        for sample in rows:
            if (sample['kind'] == 'sample' and sample['pair'] == 'e5-shared'
                and sample['control'] == 'production-large' and sample['view'] == 'e5-shared'
                and sample['repeat'] == 1):
                sample['event_ns'] = 85100
        result = gate.analyze(rows)
        self.assertEqual(result['qualified'], list(gate.CANDIDATES[:-1]))
        control = result['candidates']['e5-shared']['controls']['production-large']
        self.assertLess(control['time_ratio'], 0.85)
        self.assertGreater(control['order_time_ratios'][1], 0.85)
        self.assertFalse(result['candidates']['e5-shared']['qualified'])

    def test_large_control_cannot_be_replaced_by_normal_control(self):
        rows = copy.deepcopy(self.good)
        rows = [r for r in rows if r.get('control') != 'production-large']
        with self.assertRaisesRegex(ValueError, 'missing correctness'):
            gate.analyze(rows)

    def test_missing_route_order_and_duplicate_samples_refused(self):
        sample_index = next(i for i, r in enumerate(self.good) if r['kind'] == 'sample')
        missing = copy.deepcopy(self.good); del missing[sample_index]
        with self.assertRaisesRegex(ValueError, 'missing timing'):
            gate.analyze(missing)
        duplicate = copy.deepcopy(self.good); duplicate.insert(0, duplicate[sample_index])
        with self.assertRaisesRegex(ValueError, 'duplicate timing'):
            gate.analyze(duplicate)
        wrong = copy.deepcopy(self.good); wrong[sample_index]['view'] = 'e3-next'
        with self.assertRaisesRegex(ValueError, 'nonalternating'):
            gate.analyze(wrong)

    def test_all_output_and_status_bytes_required(self):
        for field in ('all_bytes_exact', 'bf16_exact', 'status_exact'):
            rows = copy.deepcopy(self.good); rows[0][field] = False
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'device bytes differ'):
                gate.analyze(rows)

    def test_nonfinite_zero_and_boolean_timings_refused(self):
        for value in (0, -1, float('nan'), float('inf'), True):
            rows = copy.deepcopy(self.good); rows[1]['event_ns'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'invalid event timing'):
                gate.analyze(rows)

    def test_fresh_process_identity_and_nonoverlap(self):
        gate.validate_processes(windows())
        rows = windows(); rows[1].update(pid=rows[0]['pid'], process_start_ticks=rows[0]['process_start_ticks'])
        with self.assertRaisesRegex(ValueError, 'same native process'):
            gate.validate_processes(rows)
        rows = windows(); rows[1]['started_utc_ns'] = 120
        with self.assertRaisesRegex(ValueError, 'overlap'):
            gate.validate_processes(rows)
        rows = windows(); del rows[1]['process_start_ticks']
        with self.assertRaisesRegex(ValueError, 'identity missing'):
            gate.validate_processes(rows)

    def test_native_evidence_mutation_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet = Path(temporary); directory = packet/'evidence/micro-B-1'; directory.mkdir(parents=True)
            binary = packet/'build/microbench'; binary.parent.mkdir(); binary.write_bytes(b'fixture-no-device')
            samples = directory/'samples.jsonl'
            samples.write_text(''.join(json.dumps(r)+'\n' for r in self.good))
            bindings = {'evidence/microbench-build.json': 'fixture-receipt'}
            window = windows()[0]
            window.update(binary_sha256=gate.sha(binary), build_receipt_sha256='fixture-receipt',
                          prerequisite_bindings=bindings, samples_sha256=gate.sha(samples))
            gate.save(directory/'window.json', window)
            result, _ = gate.one_process(packet, 1, bindings)
            self.assertEqual(result['qualified'], list(gate.CANDIDATES))
            samples.write_text(samples.read_text()+'\n')
            with self.assertRaisesRegex(ValueError, 'sample bytes changed'):
                gate.one_process(packet, 1, bindings)

    def test_first_process_writes_result_without_claiming_two_process_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet = Path(temporary); (packet/'evidence/micro-B-1').mkdir(parents=True)
            gate.save(packet/'evidence/micro-B-1/window.json', windows()[0])
            with patch.object(gate, 'prerequisites', return_value={}), patch.object(gate, 'one_process', return_value=(gate.analyze(self.good), windows()[0])):
                result = gate.evaluate(packet, 1)
            self.assertTrue(result['pending'])
            self.assertFalse(result['passed'])
            self.assertFalse((packet/gate.QUALIFICATION).exists())
            self.assertTrue((packet/'evidence/micro-B-1/qualification.json').is_file())

if __name__ == '__main__':
    from build_engine import limits
    limits()
    unittest.main()

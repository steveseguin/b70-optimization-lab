#!/usr/bin/env python3
"""CPU-only protocol regressions. All child launches and journals are mocked."""
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import build as packet_build
import device_window as w
import summarize_census as census_summary


class WindowTests(unittest.TestCase):
    def setUp(self):
        w.BUILD.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='window-test-', dir=w.BUILD)
        self.root = Path(self.temp.name)
        self.build = self.root / 'build'
        self.build.mkdir()
        self.latch = self.build / 'device-fault-latch.json'
        self.output = self.build / 'fresh'
        self.patches = [patch.object(w, 'ROOT', self.root), patch.object(w, 'BUILD', self.build),
                        patch.object(w, 'LATCH', self.latch), patch.object(w.os, 'getpriority', return_value=19),
                        patch.dict(w.os.environ, {'OMP_NUM_THREADS': '2'})]
        for p in self.patches:
            p.start()
        self.source = self.root / 'source.txt'
        self.source.write_text('original')
        self.manifest = dict(wa_host_references_complete=True, wa_reference_hashes={}, wa_reference_dir='wa-reference', precision_control_binary='plain-control', compiled=True, device_executed=False, chunk=262144, native_bits=32,
                             hashes={'source.txt': w.sha(self.source)}, host_hashes_complete=True,
                             cpu_three_way_passed=True, fixture_trace_complete=True,
                             census_binary='census-device', fixture_binary='fixture-device',
                             fixture_trace='trace.bin', host_hashes='hashes.txt', fixtures='fixtures',
                             cases=['case'], authority='iq3-p17-detmath-v2')
        w.save(self.build / 'window-prepared.json', self.manifest)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_wa_runs_same_probe_inputs_on_both_links_before_census(self):
        commands = []
        deadlines = []
        def watch(command, directory, seconds, on_started=None):
            directory.mkdir()
            commands.append(command)
            deadlines.append(seconds)
            if on_started:
                on_started(1234)
            return dict(returncode=0)
        plain = {name: dict(correctly_rounded_on_probes=False) for name in ('division', 'sqrtf', 'rsqrt-plain', 'rsqrt-barrier', 'rsqrt-corrected')}
        precise = {name: dict(correctly_rounded_on_probes=True) for name in plain}
        with patch.object(w, 'check', return_value=(self.manifest, self.output)), \
                patch.object(w, 'journal', return_value=('', 'cursor')), \
                patch.object(w, 'watch', side_effect=watch), \
                patch.object(w, 'final_jsonl', return_value={'complete': True}), \
                patch.object(w, 'sha', return_value='digest'), \
                patch.object(w, 'precision_verdicts', side_effect=[plain, precise]), \
                patch.object(w, 'summarize_census', return_value={'complete': True}):
            receipt = w.execute('W-A', self.output, 3, 30)
        self.assertTrue(receipt['passed'])
        self.assertTrue(receipt['precision_link_effect_observed'])
        self.assertEqual(len(commands), 3)
        self.assertEqual(deadlines, [60, 60, 30])
        self.assertEqual([cmd[1] for cmd in commands], ['precision-probe', 'precision-probe', 'native'])
        self.assertEqual([cmd[5] for cmd in commands], [str(self.root / 'wa-reference')] * 3)
        self.assertEqual(commands[0][2:4], commands[1][2:4])
        self.assertEqual(Path(commands[0][0]).name, 'plain-control')
        self.assertEqual(Path(commands[1][0]).name, 'census-device')

    def test_fixture_deadline_independent_of_census(self):
        for census_seconds, fixture_seconds in ((60, 1800), (7200, 1800), (1800, 2400)):
            with self.subTest(census=census_seconds, fixture=fixture_seconds), \
                    patch.object(w, 'check', return_value=(self.manifest, self.output)), \
                    patch.object(w, 'journal', return_value=('', 'cursor')), \
                    patch.object(w, 'watch', return_value={'returncode': 0}) as watch, \
                    patch.object(w, 'final_jsonl', return_value={'complete': True}), \
                    patch.object(w, 'sha', return_value='digest'), \
                    patch.object(w, 'fixture_gate', return_value={'case': 'same'}):
                receipt = w.execute('W-B', self.output, 3, census_seconds, fixture_seconds)
                self.assertTrue(receipt['passed'])
                self.assertEqual([call.args[2] for call in watch.call_args_list],
                                 [census_seconds, fixture_seconds] * 2)
            import shutil
            shutil.rmtree(self.output)

    def test_short_fixture_cli_deadline_rejected_before_check(self):
        import sys
        with patch.object(sys, 'argv', ['device_window.py', '--check', '--mode', 'W-B',
                                      '--fixture-seconds', '600', '--output', str(self.output)]), \
                patch.object(w, 'check') as check:
            with self.assertRaisesRegex(SystemExit, 'fixture deadline'):
                w.main()
            check.assert_not_called()

    def test_wa_preparation_has_no_short_timeout(self):
        with patch.object(packet_build, 'B', self.build), patch.object(packet_build, 'run') as run:
            packet_build.prepare_wa_references(2)
        self.assertIn('--precompute', run.call_args.args[0])
        self.assertIsNone(run.call_args.kwargs['timeout'])

    def test_wa_index_rejects_missing_coverage_and_path_escape(self):
        import prepare_wa
        root = self.root / 'references'
        root.mkdir()
        w.save(root / 'complete.json', dict(complete=True, device_executed=False, chunk=262144, fixture_calls=1))
        (root / 'coverage.jsonl').write_text(''.join(json.dumps(dict(function=name, selected_bits=32))+'\n' for name in census_summary.UNARY))
        (root / 'index.txt').write_text('')
        with self.assertRaisesRegex(ValueError, 'incomplete reference coverage'):
            prepare_wa.validate_index(root)
        (root / 'index.txt').write_text('../escape 0 32 native-exhaustive 4294967296 0\n')
        with self.assertRaisesRegex(ValueError, 'invalid reference path'):
            prepare_wa.validate_index(root)

    def test_wa_host_arithmetic_matches_precomputation_snapshot(self):
        import prepare_wa
        prefix = (w.HERE / 'evidence/wa-precompute-census.cpp.snapshot').read_text().split('int main(int argc', 1)[0]
        import hashlib
        self.assertEqual(prepare_wa.input_identity()['census_host_arithmetic_sha256'],
                         hashlib.sha256(prefix.encode()).hexdigest())

    def test_wa_requires_precomputed_references_before_any_launch(self):
        self.manifest['wa_host_references_complete'] = False
        w.save(self.build / 'window-prepared.json', self.manifest)
        with patch.object(w.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'sealed W-A host references'):
                w.check('W-A', self.output, 3)
            run.assert_not_called()

    def test_wa_changed_reference_rejected_before_loader(self):
        self.manifest['wa_reference_hashes'] = {'source.txt': 'wrong'}
        w.save(self.build / 'window-prepared.json', self.manifest)
        with patch.object(w.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'W-A reference changed'):
                w.check('W-A', self.output, 3)
            run.assert_not_called()

    def test_precision_verdict_requires_all_same_probes(self):
        file = self.root / 'probes.jsonl'
        rows = [dict(kind='precision-verdict', function=name, count=65536,
                     non_nan_differences=0, correctly_rounded_on_probes=True)
                for name in ('division', 'sqrtf', 'rsqrt-plain', 'rsqrt-barrier', 'rsqrt-corrected')]
        file.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        self.assertEqual(len(w.precision_verdicts(file)), 5)
        rows[0]['non_nan_differences'] = 1
        file.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'invalid precision'):
            w.precision_verdicts(file)
        file.write_text(''.join(json.dumps(row)+'\n' for row in rows[1:]))
        with self.assertRaisesRegex(ValueError, 'incomplete precision'):
            w.precision_verdicts(file)

    def test_device_link_options_required_on_every_device_target(self):
        native = self.root / 'native'
        paths = []
        flags = '-fsycl -foffload-fp32-prec-div -foffload-fp32-prec-sqrt'
        for target in ('device-test', 'census-device', 'future-device'):
            path = native / 'CMakeFiles' / (target + '.dir') / 'link.txt'
            path.parent.mkdir(parents=True)
            (path.parent / 'flags.make').write_text('CXX_FLAGS = -O2 -fsycl')
            path.write_text('icpx ' + flags + ' object.o -o ' + target)
            paths.append(path)
        self.assertEqual(len(packet_build.assert_device_link_options(native)), 3)
        for path in paths:
            original = path.read_text()
            for flag in ('-fsycl', '-foffload-fp32-prec-div', '-foffload-fp32-prec-sqrt'):
                path.write_text(original.replace(flag, ''))
                with self.assertRaisesRegex(ValueError, 'link command missing'):
                    packet_build.assert_device_link_options(native)
            path.write_text(original)
        paths[0].unlink()
        with self.assertRaisesRegex(ValueError, 'missing device target'):
            packet_build.assert_device_link_options(native)

    def test_missing_libraries_fail_before_latch_or_output(self):
        missing = subprocess.CompletedProcess([], 0, 'libsycl.so => not found\n', '')
        with patch.object(w.subprocess, 'run', return_value=missing) as run:
            with self.assertRaisesRegex(ValueError, 'loader preflight'):
                w.check('W-A', self.output, 3)
        self.assertIn('ldd', run.call_args.args[0])
        self.assertFalse(self.output.exists())
        self.assertFalse(self.latch.exists())

    def test_existing_output_rejected(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh output'):
            w.check('W-A', self.output, 3)

    def test_changed_source_rejected_before_loader(self):
        self.source.write_text('changed')
        with patch.object(w.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                w.check('W-A', self.output, 3)
            run.assert_not_called()

    def test_incomplete_host_hashes_rejected(self):
        self.manifest['host_hashes_complete'] = False
        w.save(self.build / 'window-prepared.json', self.manifest)
        with self.assertRaisesRegex(ValueError, r'all 2\^32'):
            w.check('W-B', self.output, 3)

    def test_core_device_vs_host_is_mandatory(self):
        path = self.build / 'fixture-owner'
        path.mkdir()
        receipt = dict(checks=2, packet4_device_checks=1, packet4_device_host_matches=0,
                       authority='iq3-p17-detmath-v2', error='',
                       teardown=dict(safe_to_exit=True, idle_marker_complete=True, live_bytes=0,
                                     in_flight=0, exit_code=0, status='complete', error='',
                                     sequence=['context-released']))
        w.save(path / 'device.json', receipt)
        (path / 'case.core').write_bytes(b'core')
        with self.assertRaisesRegex(ValueError, 'host-core'):
            w.fixture_gate(path, ['case'], 'iq3-p17-detmath-v2')
        receipt['packet4_device_host_matches'] = 1
        w.save(path / 'device.json', receipt)
        self.assertEqual(w.fixture_gate(path, ['case'], 'iq3-p17-detmath-v2'), {'case': w.sha(path / 'case.core')})

    def test_second_fresh_owner_must_match(self):
        with patch.object(w, 'check', return_value=(self.manifest, self.output)), \
                patch.object(w, 'journal', return_value=('', 'cursor')), \
                patch.object(w, 'watch', return_value={'returncode': 0}), \
                patch.object(w, 'final_jsonl', return_value={'complete': True}), \
                patch.object(w, 'sha', return_value='digest'), \
                patch.object(w, 'fixture_gate', side_effect=[{'case': 'one'}, {'case': 'two'}]):
            receipt = w.execute('W-B', self.output, 3, 60)
        self.assertFalse(receipt['passed'])
        self.assertIn('fresh owners differ', receipt['error'])
        self.assertTrue(self.latch.exists())

    def test_deadline_sends_one_sigterm_then_returns_live_owner(self):
        child = Mock(pid=777)
        child.poll.return_value = None
        tick = iter(range(0, 1000, 25))
        with patch.object(w, 'journal', return_value=('', 'cursor')), \
                patch.object(w.subprocess, 'Popen', return_value=child), \
                patch.object(w.time, 'monotonic', side_effect=lambda: next(tick)), \
                patch.object(w.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'no retry'):
                w.watch(['never-executed'], self.output, 1)
        child.send_signal.assert_called_once_with(signal.SIGTERM)
        child.kill.assert_not_called()
        child.terminate.assert_not_called()
        receipt = json.loads((self.output / 'watch.json').read_text())
        self.assertTrue(receipt['child_alive'])
        self.assertEqual(receipt['pid'], 777)
        self.assertTrue(self.latch.exists())

    def test_watcher_preflight_does_not_claim_execution(self):
        with patch.object(w, 'check', return_value=(self.manifest, self.output)), \
                patch.object(w, 'journal', return_value=('', 'cursor')), \
                patch.object(w, 'watch', side_effect=RuntimeError('watch journal preflight failed')):
            receipt = w.execute('W-A', self.output, 3, 60)
        self.assertFalse(receipt['device_executed'])

    def test_launch_callback_only_after_popen(self):
        child = Mock(pid=778)
        child.poll.return_value = 0
        callback = Mock()
        with patch.object(w, 'journal', return_value=('', 'cursor')), \
                patch.object(w.subprocess, 'Popen', return_value=child), \
                patch.object(w.time, 'sleep'):
            w.watch(['never-executed'], self.output, 60, on_started=callback)
        callback.assert_called_once_with(778)

    def census_rows(self, differences=None, both_nan=None, fixture_difference=None):
        differences, both_nan = differences or {}, both_nan or {}
        rows = []
        def add(kind, name, n, diff=0, both=0):
            rows.append(dict(kind=kind, function=name, start=0, count=n, different=diff,
                             both_nan_different=both, seconds=.001,
                             ulp_histogram=[n-diff, diff] + [0] * 32))
        for name in census_summary.UNARY:
            rows.append(dict(kind='coverage-selection', function=name, selected_bits=32))
            add('native-exhaustive', name, 1 << 32, differences.get(name, 0), both_nan.get(name, 0))
        for name in ('division', 'mul-add', 'fma', 'separate'):
            add('triples', name, 1 << 26)
        add('rope-arguments', 'pow-sin-cos-rope', 3 * 32 * 151)
        for name in ('sqrtf',) + census_summary.CANDIDATES:
            add('actual-fixture-inputs', name, 1, int(fixture_difference == name))
        rows.append(dict(complete=True, fixture_calls=4))
        path = self.build / 'mock-census.jsonl'
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return path

    def test_summary_both_nan_payloads_exempt(self):
        path = self.census_rows({'sqrtf': 1, 'rsqrt-barrier': 2}, {'sqrtf': 1, 'rsqrt-barrier': 2})
        result = census_summary.summarize(path)
        self.assertEqual(result['selected_spelling'], 'rsqrt-barrier')
        self.assertTrue(result['reciprocal_sqrt_candidates']['rsqrt-barrier']['exact_on_tested_inputs'])

    def test_summary_one_nan_mismatch_fails_candidate(self):
        path = self.census_rows({'rsqrt-barrier': 1})
        result = census_summary.summarize(path)
        self.assertFalse(result['reciprocal_sqrt_candidates']['rsqrt-barrier']['exact_on_tested_inputs'])
        self.assertEqual(result['selected_spelling'], 'rsqrt-plain')

    def test_summary_sqrt_mismatch_blocks_every_candidate(self):
        result = census_summary.summarize(self.census_rows({'sqrtf': 1}))
        self.assertIsNone(result['selected_spelling'])
        self.assertTrue(all(not c['exact_on_tested_inputs'] for c in result['reciprocal_sqrt_candidates'].values()))

    def test_summary_fixture_mismatch_also_blocks_candidate(self):
        result = census_summary.summarize(self.census_rows(fixture_difference='rsqrt-barrier'))
        self.assertFalse(result['reciprocal_sqrt_candidates']['rsqrt-barrier']['exact_on_tested_inputs'])

    def test_summary_incomplete_file_rejected(self):
        path = self.census_rows()
        path.write_text('\n'.join(path.read_text().splitlines()[:-1]) + '\n')
        with self.assertRaisesRegex(ValueError, 'did not finish'):
            census_summary.summarize(path)


if __name__ == '__main__':
    unittest.main()

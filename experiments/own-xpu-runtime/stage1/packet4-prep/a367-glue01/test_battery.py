"""CPU-only assertions against retained A367 record and A364 battery receipts."""
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import battery_client as b
import compare

DATA = b.REPO / 'experiments/qwen38-flash-next-fp8-b70/data'
PREFIX = '20260913-tp4-mtp1-a364-native-exact-gdn-'
TEST_DEPENDENCIES = {
    'quality-current': '63581810b20dd74bfef5dda30c8cb91c1e72737f09c2729dffda8ce49d6649f1',
    'exact-depth-2k-r1': 'ad186ac340a8ae3a49e6548bf36a2082797e3b84090f381d048e2754f6296882',
    'exact-depth-4k-r1': '8b9d2fa985e96a7b2ed2b9fcad376bb0a31136a1a40c3a57dc6a6e7decb96018',
    'bench-short-r1': '020a46cffd52d8362eb08a342a6e1e94f6a5bce35a55243d806c67afbc504364',
}


def old(name):
    path = DATA / (PREFIX + name + '.json')
    assert b.sha(path) == TEST_DEPENDENCIES[name], 'historical CPU fixture drift'
    return b.read(path)


def canary(_=None):
    return {'model': b.MODEL, 'choices': [{'finish_reason': 'stop', 'message': {'content': 'OK'}}],
        'usage': {'prompt_tokens': 17, 'completion_tokens': 2, 'total_tokens': 19,
        'prompt_tokens_details': {'cached_tokens': 0, 'created_cache_tokens': 0}}}


class BatteryTests(unittest.TestCase):
    def setUp(self):
        self.record = b.read(b.REPO / b.RECORD)

    def test_dependency_pins(self):
        b.verify_dependencies()

    def test_record_full_arrays_and_text_pass(self):
        self.assertTrue(b.validate_realistic(self.record, self.record))

    def test_token_array_changes_refuse_even_if_text_hash_stays(self):
        bad = copy.deepcopy(self.record); bad['rows'][0]['token_ids'][0] += 1
        with self.assertRaisesRegex(ValueError, 'token_ids'):
            b.validate_realistic(bad, self.record)

    def test_text_changes_refuse_even_if_hash_stays(self):
        bad = copy.deepcopy(self.record); bad['rows'][0]['text'] += 'x'
        with self.assertRaisesRegex(ValueError, 'text'):
            b.validate_realistic(bad, self.record)

    def test_finish_changes_refuse(self):
        bad = copy.deepcopy(self.record); bad['rows'][0]['finish_reasons'] = ['stop']
        with self.assertRaisesRegex(ValueError, 'finish_reasons'):
            b.validate_realistic(bad, self.record)

    def test_subset_refuses(self):
        bad = copy.deepcopy(self.record); bad['rows'].pop()
        with self.assertRaisesRegex(ValueError, 'complete'):
            b.validate_realistic(bad, self.record)

    def test_cache_refuses(self):
        bad = copy.deepcopy(self.record); bad['rows'][0]['cached_tokens'] = 1
        with self.assertRaisesRegex(ValueError, 'cache'):
            b.validate_realistic(bad, self.record)

    def test_request_cap_change_refuses(self):
        bad = copy.deepcopy(self.record); bad['run_identity']['max_tokens'] = 128
        with self.assertRaisesRegex(ValueError, 'max_tokens'):
            b.validate_realistic(bad, self.record)

    def test_historical_quality_passes_same_exception(self):
        q = old('quality-current')
        result = b.validate_quality(q, 1)
        self.assertTrue(result['known_code_execution_30_exception'])
        self.assertEqual(result['repeats'], 16)

    def test_quality_new_miss_refuses(self):
        q = old('quality-current'); q['exact_cases'][0]['pass'] = False
        with self.assertRaisesRegex(ValueError, 'quality failure'):
            b.validate_quality(q, 1)

    def test_fifteen_repeats_refuse(self):
        q = old('quality-current'); q['repeat_case']['runs'].pop()
        with self.assertRaisesRegex(ValueError, '16/16'):
            b.validate_quality(q, 1)

    def test_repeat_bytes_refuse(self):
        q = old('quality-current'); q['repeat_case']['runs'][0]['normalized'] += 'x'
        with self.assertRaisesRegex(ValueError, 'bytes'):
            b.validate_quality(q, 1)

    def test_needle_cache_refuses(self):
        q = old('quality-current'); q['long_context_case']['usage']['prompt_tokens_details']['cached_tokens'] = 1
        with self.assertRaisesRegex(ValueError, 'cache'):
            b.validate_quality(q, 1)

    def test_depth_both_historical_pins_pass(self):
        for depth in (2048, 4096):
            self.assertTrue(b.validate_depth(old(f'exact-depth-{depth//1024}k-r1'), depth))

    def test_depth_raw_array_changes_refuse_despite_recorded_hash(self):
        d = old('exact-depth-2k-r1'); d['response']['token_ids'][0] += 1
        with self.assertRaisesRegex(ValueError, 'token-array'):
            b.validate_depth(d, 2048)

    def test_older_lineage_4k_pin_refuses(self):
        d = old('exact-depth-4k-r1'); d['response']['output_token_ids_sha256'] = 'c6193cc6' + '0'*56
        with self.assertRaisesRegex(ValueError, 'token-array'):
            b.validate_depth(d, 4096)

    def test_depth_cache_refuses(self):
        d = old('exact-depth-2k-r1'); d['response']['usage']['prompt_tokens_details']['cached_tokens'] = 1
        with self.assertRaisesRegex(ValueError, 'cached'):
            b.validate_depth(d, 2048)

    def test_depth_finish_refuses(self):
        d = old('exact-depth-2k-r1'); d['response']['finish_reasons'] = ['stop']
        with self.assertRaisesRegex(ValueError, 'finish'):
            b.validate_depth(d, 2048)

    def test_depth_capacity_refuses(self):
        d = old('exact-depth-4k-r1'); d['run_identity']['configured_context_capacity'] = 4096
        with self.assertRaisesRegex(ValueError, 'capacity'):
            b.validate_depth(d, 4096)

    def test_original_short_diagnostic_pin(self):
        b.validate_short([old('bench-short-r1')] * 3)

    def test_canary_usage_pinned(self):
        b.validate_canary(canary())
        bad = canary(); bad['usage']['prompt_tokens'] += 1
        with self.assertRaises(ValueError):
            b.validate_canary(bad)

    def test_command_order_and_no_old_wrapper_or_timeout_kill(self):
        jobs = b.commands(Path('/tmp/unused'), 'http://127.0.0.1:19980')
        self.assertEqual([j['name'] for j in jobs[:3]], ['realistic-suite-v1-result', 'check-replay-result', 'quality-current'])
        self.assertEqual(len([j for j in jobs if j['name'].startswith('exact-depth')]), 4)
        serialized = json.dumps(jobs)
        for forbidden in ('timeout --signal', 'kill-after', 'a367-fullgraphdet-w13n32-client.sh'):
            self.assertNotIn(forbidden, serialized)
        for job in jobs:
            self.assertEqual(job['command'][:3], ['taskset', '-c', '4-15,20-31'])
            if '--tokenizer' in job['command']:
                self.assertEqual(job['command'][job['command'].index('--tokenizer') + 1],
                                 '/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8')

    def test_99_interval_metric_recomputed(self):
        report = b.report(self.record)
        self.assertAlmostEqual(report['class_balanced_99_interval_median_tok_s'], 46.85424994838007)
        self.assertAlmostEqual(report['all_prompt_99_interval_median_tok_s'], 46.322146702065716)
        self.assertEqual(report['metric_numerator'], 99)
        self.assertFalse(report['speed_is_pass_gate'])

    def test_acceptance_counter_delta(self):
        before = 'vllm:spec_decode_num_accepted_tokens_total{model_name="x"} 10\nvllm:spec_decode_num_draft_tokens_total{model_name="x"} 20\n'
        after = 'vllm:spec_decode_num_accepted_tokens_total{model_name="x"} 90\nvllm:spec_decode_num_draft_tokens_total{model_name="x"} 120\n'
        self.assertEqual(b.report(self.record, before, after)['acceptance']['ratio'], 0.8)

    def test_missing_counters_report_unavailable(self):
        r = b.report(self.record)
        self.assertIsNone(r['acceptance']['ratio'])
        self.assertIsNone(r['M2_steps'])

    def test_graph_dispatch_counts_keep_window_scope(self):
        log = '| 1 | 1 | 0 | FULL | 12 |\n| 2 | 2 | 0 | FULL | 40 |\n| 1 | 2 | 1 | FULL | 7 |\n| 2 | 2 | 0 | FULL | 5 |'
        r = compare.graph_dispatch_counts(log)
        self.assertEqual((r['M1_steps'], r['M2_steps']), (12, 45))
        self.assertIn('entire server window', r['scope'])
        self.assertIsNone(compare.graph_dispatch_counts('no table')['M2_steps'])

    def mock_run(self, root, fail_first=False):
        events = []
        def execute(command, **kwargs):
            name = Path(kwargs['stdout'].name).stem
            events.append(name)
            if fail_first and len(events) == 1:
                return types.SimpleNamespace(returncode=2)
            if name == 'realistic-suite-v1-result':
                b.write(root / b.RESULT, self.record)
            elif name == 'quality-current':
                b.write(root / (name + '.json'), old('quality-current'))
            elif name.startswith('bench-short'):
                b.write(root / (name + '.json'), old('bench-short-r1'))
            elif name.startswith('exact-depth'):
                b.write(root / (name + '.json'), old(name.replace('-r2', '-r1')))
            return types.SimpleNamespace(returncode=1 if name == 'quality-current' else 0)
        def do_canary(payload):
            events.append('canary')
            return canary()
        return execute, do_canary, events

    def test_mock_end_to_end_suite_before_every_battery_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); execute, do_canary, events = self.mock_run(root)
            b.run(root, 'http://127.0.0.1:19980', 'control', run_command=execute, snapshot=lambda _: '', canary=do_canary)
            self.assertEqual(events[:4], ['realistic-suite-v1-result', 'check-replay-result', 'canary', 'quality-current'])
            self.assertTrue(compare.validate_arm(root, 'control')['exact'])

    def test_failed_suite_blocks_all_battery_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); execute, do_canary, events = self.mock_run(root, True)
            with self.assertRaisesRegex(ValueError, 'failed'):
                b.run(root, 'http://127.0.0.1:19980', 'control', run_command=execute, snapshot=lambda _: '', canary=do_canary)
            self.assertEqual(events, ['realistic-suite-v1-result'])

    def test_comparison_revalidates_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); execute, do_canary, _ = self.mock_run(root)
            b.run(root, 'http://127.0.0.1:19980', 'control', run_command=execute, snapshot=lambda _: '', canary=do_canary)
            (root / 'exact-depth-2k-r1.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'artifact hash'):
                compare.validate_arm(root, 'control')

    def test_metrics_snapshot_changes_refuse_even_when_counters_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); execute, do_canary, _ = self.mock_run(root)
            b.run(root, 'http://127.0.0.1:19980', 'control', run_command=execute, snapshot=lambda _: '', canary=do_canary)
            (root / 'metrics-before-suite.prom').write_text('# modified evidence\n')
            with self.assertRaisesRegex(ValueError, 'artifact hash changed: metrics-before-suite.prom'):
                compare.validate_arm(root, 'control')

    def test_short_pin_failure_blocks_remaining_diagnostics_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); execute, do_canary, events = self.mock_run(root)
            def changed(command, **kwargs):
                result = execute(command, **kwargs)
                if Path(kwargs['stdout'].name).stem == 'bench-short-r1':
                    path = root / 'bench-short-r1.json'
                    row = b.read(path)
                    row['scenarios']['c1']['records'][0]['sha256'] = '0' * 64
                    path.write_text(json.dumps(row))
                return result
            with self.assertRaisesRegex(ValueError, 'short hash changed'):
                b.run(root, 'http://127.0.0.1:19980', 'control', run_command=changed, snapshot=lambda _: '', canary=do_canary)
            self.assertEqual(events, ['realistic-suite-v1-result', 'check-replay-result', 'canary', 'quality-current', 'bench-short-r1'])
            self.assertFalse((root / 'battery-result.json').exists())

    def test_comparison_speed_is_not_pass_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = [Path(tmp) / name for name in ('control', 'candidate')]
            for root in roots:
                execute, do_canary, _ = self.mock_run(root)
                b.run(root, 'http://127.0.0.1:19980', root.name, run_command=execute, snapshot=lambda _: '', canary=do_canary)
            def lifecycle(root, arm):
                identity = {k: 'same' for k in ('campaign_sha256', 'seal_sha256', 'preregistration_sha256', 'host', 'boot_id')}
                return {'identity': identity, 'launch': {'unix': 1000}, 'stop': {'completed_unix': 100, 'next_launch_not_before_unix': 405},
                        'owner': {'previous_teardown_completed_unix': 100}}
            with patch.object(compare, 'validate_lifecycle', side_effect=lifecycle), patch('operator_gate.validate_receipts', return_value=[]):
                report = compare.compare(*roots)
            self.assertTrue(report['exact'])
            self.assertEqual(report['change_percent'], 0)
            self.assertFalse(report['speed_is_pass_gate'])

    def test_candidate_requires_operator_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); execute, do_canary, _ = self.mock_run(root)
            b.run(root, 'http://127.0.0.1:19980', 'candidate', run_command=execute, snapshot=lambda _: '', canary=do_canary)
            with self.assertRaises(FileNotFoundError):
                compare.check_arm(root, 'candidate')

    def test_pair_comparison_requires_full_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); execute, do_canary, _ = self.mock_run(root)
            b.run(root, 'http://127.0.0.1:19980', 'control', run_command=execute, snapshot=lambda _: '', canary=do_canary)
            with self.assertRaises(FileNotFoundError):
                compare.validate_lifecycle(root, 'control')


if __name__ == '__main__':
    unittest.main()

"""No native subprocesses or model payloads: test screen refusal/metric parsing."""
import importlib.util
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('screen', HERE / 'run-screen.py')
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)


class ScreenTests(unittest.TestCase):
    def registered_commands(self, tmp):
        spec = importlib.util.spec_from_file_location('prepare', HERE / 'prepare-prompts.py')
        prep = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prep)
        out = Path(tmp) / 'inputs'
        prep.prepare(out)
        return json.loads((out / 'commands.json').read_text())

    def test_onecard_preserves_suite_sampling_and_allows_fitting(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = self.registered_commands(tmp)
            plan = screen.configure_plan(original, 'onecard', 'level_zero:2', 'SYCL0')
        self.assertEqual(len(plan), 24)
        self.assertEqual([(c['id'], c['repeat']) for c in original],
                         [(c['id'], c['repeat']) for c in plan])
        for c, old in zip(plan, original):
            argv = c['argv']
            for flag, value in (('--fit', 'on'), ('--load-mode', 'mmap'),
                                ('--predict', '64'), ('--seed', '20260609'),
                                ('--ctx-size', '4096'), ('--cache-type-k', 'f16'),
                                ('--cache-type-v', 'f16'), ('--device', 'SYCL0')):
                self.assertEqual(argv[argv.index(flag) + 1], value)
            for flag in ('--gpu-layers', '--tensor-split', '--override-tensor'):
                self.assertNotIn(flag, argv)
                self.assertIn(flag, old['argv'])
            self.assertIn('--verbose', argv)
            self.assertIn('--perf', argv)
            self.assertEqual(c['cards'], [2])
            self.assertEqual(argv[-2:], old['argv'][-2:])

    def test_twocard_retains_registered_argv_except_selected_devices(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = self.registered_commands(tmp)
        plan = screen.configure_plan(original, 'twocard', 'level_zero:2,3', 'SYCL0,SYCL1')
        self.assertEqual([c['argv'] for c in original], [c['argv'] for c in plan])
        self.assertTrue(all(c['cards'] == [2, 3] for c in plan))

    def test_selector_and_device_list_fail_closed(self):
        for selector in ('', '*', 'level_zero:*', 'level_zero:0.0', 'opencl:2',
                         'level_zero:0,0', 'level_zero:4', 'level_zero:0;level_zero:1'):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                screen.selector_cards(selector)
        for plan, selector, devices in [('onecard', 'level_zero:2,3', 'SYCL0'),
                                         ('twocard', 'level_zero:2', 'SYCL0'),
                                         ('onecard', 'level_zero:2', 'SYCL2'),
                                         ('twocard', 'level_zero:2,3', 'SYCL0,SYCL0')]:
            with self.subTest(devices=devices), self.assertRaises(ValueError):
                screen.configure_plan([], plan, selector, devices)

    def test_default_gaps_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'commands.json').write_text('[]')
            for plan, gap, extra in [('onecard', 60, []), ('twocard', 305, []),
                                     ('twocard', 60, ['--gap-seconds', '60'])]:
                with patch.object(screen, 'run_admitted') as run, patch('sys.argv',
                        ['screen', '--inputs', tmp, '--plan', plan,
                         '--execute-after-admission'] + extra):
                    screen.main()
                    self.assertEqual(run.call_args.args[0].gap_seconds, gap)

    def test_negative_gap_refused(self):
        with patch('sys.argv', ['screen', '--gap-seconds', '-1']), \
                patch('sys.stderr'), self.assertRaises(SystemExit):
            screen.main()

    def fake_proc(self, root, argv, selector):
        proc = Path(root) / '999999'
        proc.mkdir(exist_ok=True)
        (proc / 'cmdline').write_bytes('\0'.join(argv).encode())
        (proc / 'environ').write_bytes(('ONEAPI_DEVICE_SELECTOR=' + selector + '\0').encode())
        return proc

    def test_process_admission_allows_disjoint_refuses_overlap_and_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for argv in (['/build/llama-completion'], ['python3', '-m', 'vllm.entrypoints.openai.api_server']):
                self.fake_proc(root, argv, 'level_zero:0,1')
                self.assertEqual(screen.check_process_cards([2], root)[0]['cards'], [0, 1])
                with self.assertRaises(RuntimeError):
                    screen.check_process_cards([1, 2], root)
                self.fake_proc(root, argv, '')
                with self.assertRaises(RuntimeError):
                    screen.check_process_cards([2], root)

    def test_process_admission_ignores_search_and_shell_strings(self):
        for argv in (['rg', 'llama-completion'], ['bash', '-c', 'llama-completion'],
                     ['python3', 'run-screen.py']):
            self.assertFalse(screen.runtime_process(argv))

    def test_unreadable_runtime_environment_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_proc(tmp, ['llama-completion'], 'level_zero:0')
            original = Path.read_bytes
            def read(path):
                if path.name == 'environ':
                    raise PermissionError('test')
                return original(path)
            with patch.object(Path, 'read_bytes', read), self.assertRaises(RuntimeError):
                screen.check_process_cards([2], Path(tmp))

    def test_card_locks_exclude_overlap_allow_disjoint_release_after_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with ExitStack() as first:
                screen.lock_cards(first, [0, 1], root)
                with ExitStack() as other:
                    screen.lock_cards(other, [2, 3], root)
                with self.assertRaises(RuntimeError), ExitStack() as other:
                    screen.lock_cards(other, [1, 2], root)
            with ExitStack() as later:
                screen.lock_cards(later, [0, 1, 2, 3], root)

    def test_runtime_timings_have_distinct_numerators(self):
        text = ('llama_perf_context_print: prompt eval time = 120.00 ms / 50 tokens (2.40 ms per token, 416.67 tokens per second)\n'
                'llama_perf_context_print:        eval time = 6000.00 ms / 63 runs (95.24 ms per token, 10.50 tokens per second)\n')
        r = screen.timings(text)
        self.assertEqual(r['prefill']['count'], 50)
        self.assertEqual(r['decode']['count'], 63)
        self.assertEqual(r['decode']['reported_tokens_per_second'], 10.5)

    def test_missing_duplicate_and_zero_timings_refuse(self):
        row = 'eval time = 20.00 ms / 1 runs (20.00 ms per token, 50.00 tokens per second)\n'
        for text in ('', row, row + row,
                     'prompt eval time = 0.00 ms / 0 tokens (0.00 ms per token, 0.00 tokens per second)\n' + row):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                screen.timings(text)

    def test_immediate_end_of_text_records_zero_generation(self):
        text = ('I common_perf_print: prompt eval time =    1519.66 ms /    90 tokens (   16.89 ms per token,    59.22 tokens per second)\n'
                'I common_perf_print:        eval time =       0.00 ms /     1 runs   (    0.00 ms per token,      inf tokens per second)\n')
        r = screen.timings(text)
        self.assertEqual(r['prefill']['count'], 90)
        self.assertIsNone(r['decode'])
        self.assertEqual(r['generated_tokens'], 0)

    def test_signals_only_set_supervisor_stop(self):
        with patch.object(screen.subprocess, 'Popen', side_effect=AssertionError('native launch')):
            screen.stop(None, None)
            self.assertTrue(screen.STOP)
            screen.STOP = False

    def test_default_plan_never_launches(self):
        with tempfile.TemporaryDirectory(prefix='iq3-cpu-test-') as tmp, patch('builtins.print'), \
                patch.object(screen.subprocess, 'Popen', side_effect=AssertionError('native launch')):
            Path(tmp, 'commands.json').write_text('[]')
            with patch('sys.argv', ['run-screen.py', '--inputs', tmp]):
                screen.main()

    def test_execute_without_receipts_refuses_before_launch(self):
        with tempfile.TemporaryDirectory(prefix='iq3-cpu-test-') as tmp, \
                patch.object(screen.subprocess, 'Popen', side_effect=AssertionError('native launch')):
            Path(tmp, 'commands.json').write_text('[]')
            with patch('sys.argv', ['run-screen.py', '--inputs', tmp, '--execute-after-admission']), self.assertRaises(AssertionError):
                screen.main()


if __name__ == '__main__':
    unittest.main()

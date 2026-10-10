"""No native subprocesses or model payloads: test screen refusal/metric parsing."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('screen', HERE / 'run-screen.py')
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)


class ScreenTests(unittest.TestCase):
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

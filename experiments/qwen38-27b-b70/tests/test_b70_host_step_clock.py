"""CPU check of b70-host-step-clock 0.1.0 against a stand-in runner: one log line per run of decode steps, waits
attributed to the step they fall in, events still forward record(), outputs returned unchanged. No vLLM, no GPU."""
import importlib.util
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('clock', HERE / 'overlays/b70-host-step-clock/b70_host_step_clock.py')
clock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clock)


class Event:
    def __init__(self, wait=0.0):
        self.wait, self.records = wait, 0

    def record(self, *a):
        self.records += 1

    def synchronize(self):
        time.sleep(self.wait)


class Out:
    def __init__(self, n):
        self.total_num_scheduled_tokens = n


class Runner:
    def __init__(self):
        self.prepare_inputs_event = Event(0.002)
        self.valid_sampled_token_count_event = None
        self.draft_token_ids_event = Event(0.0)
        self.num_accepted_tokens_event = Event(0.0)

    def execute_model(self, scheduler_output, intermediate=None):
        self.prepare_inputs_event.synchronize()
        self.prepare_inputs_event.record()
        time.sleep(0.001)
        return None

    def sample_tokens(self, grammar_output):
        time.sleep(0.0005)
        return self.propose_draft_token_ids(grammar_output)

    def propose_draft_token_ids(self, x):
        time.sleep(0.001)
        return ('drafts', x)


class ClockTest(unittest.TestCase):
    def test_runs_and_waits(self):
        lines = []
        cls = type('GPUModelRunner', (Runner,), {})
        self.assertTrue(clock.install(cls, lines.append, every=400, max_tokens=8))
        self.assertFalse(clock.install(cls, lines.append))
        r = cls()
        self.assertIsInstance(r.prepare_inputs_event, clock.TimedEvent)
        self.assertIsNone(r.valid_sampled_token_count_event)
        r.execute_model(Out(800))                         # a prompt piece: not a decode step
        r.sample_tokens(None)
        for _ in range(30):
            r.execute_model(Out(6))
            self.assertEqual(r.sample_tokens(7), ('drafts', 7))
        r.execute_model(Out(0))                           # run ends
        self.assertEqual(len(lines), 1)
        self.assertIn('run: 29 decode steps', lines[0])
        self.assertEqual(r.prepare_inputs_event._event.records, 32)
        wait = float(lines[0].split('wait ')[1].split('/')[0])
        period = float(lines[0].split('period ')[1].split('/')[0])
        self.assertGreater(wait, 1.5)                      # the 2 ms prepare wait, in milliseconds
        self.assertGreater(period, wait + 2.0)            # plus execute 1 ms, sample 0.5 ms, draft 1 ms
        self.assertIn('prep %.2f' % wait, lines[0])

    def test_short_run_dropped(self):
        lines = []
        cls = type('GPUModelRunner', (Runner,), {})
        clock.install(cls, lines.append)
        r = cls()
        for _ in range(5):
            r.execute_model(Out(1))
        r.execute_model(Out(500))
        self.assertEqual(lines, [])


if __name__ == '__main__':
    unittest.main()

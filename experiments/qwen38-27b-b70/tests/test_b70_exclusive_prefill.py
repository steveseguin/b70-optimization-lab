"""CPU check of the pure-step policy and of the wrapper's bookkeeping, with a stub scheduler (no vLLM, no GPU)."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('excl', HERE / 'overlays/b70-exclusive-prefill/b70_exclusive_prefill.py')
excl = importlib.util.module_from_spec(spec); spec.loader.exec_module(excl)


class Req:
    def __init__(self, name, prefill):
        self.name, self.is_prefill_chunk, self.next_decode_eligible_step = name, prefill, 0


def make_scheduler(running, waiting, limit=16):
    seen = {}

    class Scheduler:
        def __init__(self):
            self.running, self.waiting, self.skipped_waiting = running, waiting, []
            self.max_num_running_reqs, self.current_step = limit, 10

        def schedule(self):
            self.current_step += 1
            seen['eligible'] = [r.name for r in self.running if not self.current_step < r.next_decode_eligible_step]
            seen['admit_room'] = self.max_num_running_reqs - len(self.running)
            return 'out'

    mods = {'vllm': types.ModuleType('vllm'), 'vllm.logger': types.ModuleType('vllm.logger'), 'vllm.v1': types.ModuleType('v1'),
            'vllm.v1.core': types.ModuleType('core'), 'vllm.v1.core.sched': types.ModuleType('sched'),
            'vllm.v1.core.sched.scheduler': types.ModuleType('scheduler')}
    mods['vllm.logger'].init_logger = lambda name: types.SimpleNamespace(warning=lambda *a, **k: None)
    mods['vllm.v1.core.sched.scheduler'].Scheduler = Scheduler
    mods['vllm.v1.core.sched'].scheduler = mods['vllm.v1.core.sched.scheduler']
    sys.modules.update(mods)
    os.environ['B70_EXCLUSIVE_PREFILL'] = '1'
    excl.register()
    return Scheduler(), seen


class PolicyTest(unittest.TestCase):
    def test_choose(self):
        c = excl._choose
        self.assertEqual(c(['p'], ['d'], False, True, 'D'), 'P')     # alternate: prompt after a decode step
        self.assertEqual(c(['p'], ['d'], False, True, 'P'), 'D')     # then decode
        self.assertEqual(c([], ['d'], True, True, 'D'), 'P')         # a waiting request gets a prompt step
        self.assertEqual(c([], ['d'], True, False, 'D'), 'D')        # no room to admit: decode
        self.assertEqual(c(['p'], [], False, True, 'P'), 'P')        # only prompt work: keep going
        self.assertIsNone(c([], [], False, True, 'D'))

    def test_prompt_step_runs_one_request_alone(self):
        a, b, d1, d2 = Req('a', True), Req('b', True), Req('d1', False), Req('d2', False)
        sched, seen = make_scheduler([d1, a, d2, b], waiting=['w'])
        sched.schedule()
        self.assertEqual(seen['eligible'], ['a'])                    # the first prefilling request, alone
        self.assertEqual(seen['admit_room'], 0)                      # nobody admitted beside it
        self.assertEqual(sched.max_num_running_reqs, 16)             # restored
        sched.schedule()                                             # next step: decode only
        self.assertEqual(seen['eligible'], ['d1', 'd2'])
        self.assertEqual(seen['admit_room'], 0)

    def test_admission_step_is_alone(self):
        d1, d2 = Req('d1', False), Req('d2', False)
        sched, seen = make_scheduler([d1, d2], waiting=['w'])
        sched.schedule()
        self.assertEqual(seen['eligible'], [])                       # running decodes are skipped
        self.assertEqual(seen['admit_room'], 1)                      # exactly one admission

    def test_decode_only_when_nothing_to_read(self):
        d1, d2 = Req('d1', False), Req('d2', False)
        sched, seen = make_scheduler([d1, d2], waiting=[])
        sched.schedule(); sched.schedule()
        self.assertEqual(seen['eligible'], ['d1', 'd2'])


class AdmitCountTest(unittest.TestCase):
    def test_admit_count(self):
        f = excl.admit_count
        self.assertEqual(f([31, 31, 31, 31], 4096, 1), 1)
        self.assertEqual(f([31, 31, 31, 31], 4096, 8), 4)
        self.assertEqual(f([31] * 20, 4096, 8), 8)
        self.assertEqual(f([3000, 2000, 31], 4096, 8), 1)        # the second would overflow the step
        self.assertEqual(f([5000, 31], 4096, 8), 1)              # a long first prompt goes alone, in its usual chunks
        self.assertEqual(f([31, None, 31], 4096, 8), 1)          # a request that is not a fresh prompt stops the run
        self.assertEqual(f([], 4096, 8), 1)


if __name__ == '__main__':
    unittest.main()

"""CPU check of b70_spec_resume_accepted with a stub model runner that mimics the stock async bookkeeping
(gpu_model_runner.py:2154-2189: num_accepted_tokens = 1, then valid_sampled_token_count for rows of requests that
were in the previous step). No vLLM, no GPU."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'resume', HERE / 'overlays/b70-spec-resume-accepted/b70_spec_resume_accepted.py')
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)

NS = types.SimpleNamespace


class StockRunner:
    """The parts of GPUModelRunner the overlay touches, with the stock async-spec semantics."""
    use_async_spec_decode = True

    def __init__(self):
        self.input_batch = NS(req_ids=[], num_reqs=0, prev_req_id_to_index=None)
        self.num_accepted_tokens = NS(gpu=torch.ones(16, dtype=torch.int32))
        self.input_ids = NS(gpu=torch.zeros(128, dtype=torch.int32), cpu=torch.zeros(128, dtype=torch.int32))
        self.valid_sampled_token_count_gpu = None

    def _prepare_inputs(self, so, num_scheduled_tokens=None):
        prev = self.input_batch.prev_req_id_to_index or {}
        acc = self.num_accepted_tokens.gpu
        acc.fill_(1)
        for row, rid in enumerate(self.input_batch.req_ids):
            if rid in prev and self.valid_sampled_token_count_gpu is not None:
                acc[row] = int(self.valid_sampled_token_count_gpu[prev[rid]])
        # input ids: one sampled token + the scheduled drafts per request (placeholders stay -1 for returning rows)
        pos = 0
        for rid in self.input_batch.req_ids:
            toks = [7] + list(so.scheduled_spec_decode_tokens.get(rid, ()))
            for t in toks:
                self.input_ids.cpu[pos] = t
                self.input_ids.gpu[pos] = t
                pos += 1
        return 'stock-result'


def sched_out(batch, spec=None, finished=(), resumed=()):
    spec = {} if spec is None else spec
    total = sum(1 + len(spec.get(r, ())) for r in batch)
    return NS(scheduled_spec_decode_tokens=spec, finished_req_ids=set(finished),
              scheduled_cached_reqs=NS(resumed_req_ids=set(resumed)), total_num_scheduled_tokens=total)


def run_step(runner, batch, valid_after, spec=None, finished=(), resumed=(), reuse_buffer=False):
    """One engine step: prepare inputs for `batch`, then 'sample' (valid counts per row) for the next step."""
    runner.input_batch.req_ids = list(batch)
    runner.input_batch.num_reqs = len(batch)
    out = runner._prepare_inputs(sched_out(batch, spec, finished, resumed), None)
    acc = {rid: int(runner.num_accepted_tokens.gpu[i]) for i, rid in enumerate(batch)}
    runner.input_batch.prev_req_id_to_index = {rid: i for i, rid in enumerate(batch)}
    if reuse_buffer and runner.valid_sampled_token_count_gpu is not None:
        runner.valid_sampled_token_count_gpu[:len(valid_after)] = torch.tensor(valid_after, dtype=torch.int32)
    else:
        runner.valid_sampled_token_count_gpu = torch.tensor(valid_after, dtype=torch.int32)
    return out, acc


def patched_runner():
    class Runner(StockRunner):
        pass
    Runner._prepare_inputs = resume.wrap_prepare_inputs(StockRunner._prepare_inputs, {})
    return Runner()


DRAFTS = [-1] * 5


class StockDefectTest(unittest.TestCase):
    def test_stock_loses_the_count_of_a_request_that_sat_out(self):
        r = StockRunner()
        run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})      # step N-1: a accepts 3, x accepts 4
        run_step(r, ['y'], [1])                                                 # step N: prompt-only, a and x hidden
        _, acc = run_step(r, ['a', 'x', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS, 'y': DRAFTS})
        self.assertEqual(acc, {'a': 1, 'x': 1, 'y': 1})                       # slot 0 instead of 2 and 3: the bug


class OverlayTest(unittest.TestCase):
    def test_returning_requests_get_their_count(self):
        r = patched_runner()
        run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        run_step(r, ['y'], [2])
        _, acc = run_step(r, ['a', 'x', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS, 'y': DRAFTS})
        self.assertEqual(acc, {'a': 3, 'x': 4, 'y': 2})                        # y ran last step: stock value
        self.assertEqual(r._b70_resume_stash, {})

    def test_order_change_on_return(self):
        r = patched_runner()
        run_step(r, ['a', 'b', 'x'], [2, 6, 1], spec={k: DRAFTS for k in 'abx'})
        run_step(r, ['y'], [1])
        _, acc = run_step(r, ['y', 'x', 'b', 'a'], [1, 1, 1, 1], spec={k: DRAFTS for k in 'abxy'})
        self.assertEqual(acc, {'y': 1, 'x': 1, 'b': 6, 'a': 2})

    def test_no_skip_is_identical_to_stock(self):
        # (batch, valid counts, requests on their first (prompt) step: no drafts)
        seq = [(['a'], [1], 'a'), (['a'], [6], ''), (['a'], [2], ''), (['a', 'b'], [1, 1], 'b'), (['a', 'b'], [4, 5], ''),
               (['b', 'a'], [1, 1], '')]
        stock, patched = StockRunner(), patched_runner()
        for batch, valid, new in seq:
            spec = {k: DRAFTS for k in batch if k not in new}
            s_out, s_acc = run_step(stock, batch, valid, spec=spec)
            p_out, p_acc = run_step(patched, batch, valid, spec=spec)
            self.assertEqual(s_out, p_out)
            self.assertEqual(s_acc, p_acc)
            self.assertTrue(torch.equal(stock.input_ids.gpu, patched.input_ids.gpu))   # no clamp without a return

    def test_two_steps_out(self):
        r = patched_runner()
        run_step(r, ['x'], [5], spec={'x': DRAFTS})
        run_step(r, ['y'], [0])            # first chunk of a long prompt: nothing sampled
        run_step(r, ['y'], [1])            # second chunk
        _, acc = run_step(r, ['x', 'y'], [1, 1], spec={'x': DRAFTS})
        self.assertEqual(acc['x'], 5)

    def test_stash_is_a_copy_of_the_counts(self):
        r = patched_runner()
        run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        run_step(r, ['y'], [1, 9], reuse_buffer=True)    # the next step overwrites the same buffer in place
        _, acc = run_step(r, ['a', 'x', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS})
        self.assertEqual((acc['a'], acc['x']), (3, 4))

    def test_zero_count_clamped_to_one(self):
        r = patched_runner()
        run_step(r, ['x'], [0])
        run_step(r, ['y'], [1])
        _, acc = run_step(r, ['x'], [1], spec={'x': DRAFTS})
        self.assertEqual(acc['x'], 1)

    def test_finished_and_preempted_drop_the_count(self):
        r = patched_runner()
        run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        run_step(r, ['y'], [1])
        _, acc = run_step(r, ['x', 'y'], [1, 1], finished=['a'], resumed=['x'])
        self.assertEqual(acc['x'], 1)                         # resumed from preemption: recomputed, stock value
        self.assertEqual(r._b70_resume_stash, {})

    def test_placeholder_drafts_of_a_returning_request_are_not_negative_ids(self):
        r = patched_runner()
        run_step(r, ['x'], [3], spec={'x': [11, 12]})
        run_step(r, ['y'], [1])
        run_step(r, ['x', 'y'], [1, 1], spec={'x': DRAFTS, 'y': [13]})
        self.assertGreaterEqual(int(r.input_ids.gpu.min()), 0)
        self.assertGreaterEqual(int(r.input_ids.cpu.min()), 0)
        self.assertEqual(r.input_ids.gpu[:9].tolist(), [7, 0, 0, 0, 0, 0, 7, 13, 0])

    def test_sync_runner_untouched(self):
        class Sync(StockRunner):
            use_async_spec_decode = False
        Sync._prepare_inputs = resume.wrap_prepare_inputs(StockRunner._prepare_inputs, {})
        r = Sync()
        run_step(r, ['x'], [4], spec={'x': DRAFTS})
        run_step(r, ['y'], [1])
        _, acc = run_step(r, ['x'], [1], spec={'x': DRAFTS})
        self.assertEqual(acc['x'], 1)


class RegisterTest(unittest.TestCase):
    def _fake_vllm(self):
        class GPUModelRunner(StockRunner):
            pass
        mods = {'vllm': types.ModuleType('vllm'), 'vllm.logger': types.ModuleType('vllm.logger'),
                'vllm.v1': types.ModuleType('vllm.v1'), 'vllm.v1.worker': types.ModuleType('vllm.v1.worker'),
                'vllm.v1.worker.gpu_model_runner': types.ModuleType('vllm.v1.worker.gpu_model_runner')}
        mods['vllm.logger'].init_logger = lambda name: NS(warning=lambda *a, **k: None)
        mods['vllm.v1.worker.gpu_model_runner'].GPUModelRunner = GPUModelRunner
        mods['vllm.v1.worker'].gpu_model_runner = mods['vllm.v1.worker.gpu_model_runner']
        return mods, GPUModelRunner

    def test_env_gate_and_idempotent(self):
        mods, cls = self._fake_vllm()
        saved = {k: sys.modules.get(k) for k in mods}
        sys.modules.update(mods)
        try:
            os.environ.pop('B70_SPEC_RESUME_ACCEPTED', None)
            resume.register()
            self.assertIs(cls._prepare_inputs, StockRunner._prepare_inputs)
            os.environ['B70_SPEC_RESUME_ACCEPTED'] = '1'
            resume.register()
            first = cls._prepare_inputs
            self.assertTrue(getattr(first, resume._GUARD, False))
            resume.register()
            self.assertIs(cls._prepare_inputs, first)
            r = cls()
            run_step(r, ['x'], [4], spec={'x': DRAFTS})
            run_step(r, ['y'], [1])
            _, acc = run_step(r, ['x'], [1], spec={'x': DRAFTS})
            self.assertEqual(acc['x'], 4)
        finally:
            os.environ.pop('B70_SPEC_RESUME_ACCEPTED', None)
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v


if __name__ == '__main__':
    unittest.main()

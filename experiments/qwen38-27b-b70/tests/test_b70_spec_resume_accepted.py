"""CPU check of b70_spec_resume_accepted with a stub model runner that mimics the stock async bookkeeping. No vLLM, no GPU.

Modelled from the R310/R314 source:
  _update_states   removes requests this step does not schedule from the persistent batch
                   (gpu_model_runner.py:1257-1263); remove_request also pops them from prev_req_id_to_index
                   (gpu_input_batch.py:573-574); returning and new requests are added (:1464-1477, :1514-1516).
  _prepare_inputs  num_accepted_tokens = 1, then valid_sampled_token_count[prev row] for rows of requests in the
                   previous step (:2154-2189, spec_decode/utils.py:566-596); input ids: sampled token + scheduled
                   drafts (placeholder -1 for a returning request).
  after sampling   prev_req_id_to_index = this step's rows (:3846), valid_sampled_token_count_gpu = new counts.
"""
import importlib.util
import os
import sys
import types
import unittest
import unittest.mock
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'resume', HERE / 'overlays/b70-spec-resume-accepted/b70_spec_resume_accepted.py')
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)

NS = types.SimpleNamespace
DRAFTS = [-1] * 5


class Batch:
    def __init__(self):
        self.req_ids, self.prev_req_id_to_index = [], None

    @property
    def num_reqs(self):
        return len(self.req_ids)

    def remove_request(self, rid):
        self.req_ids.remove(rid)
        if self.prev_req_id_to_index is not None:
            self.prev_req_id_to_index.pop(rid, None)       # gpu_input_batch.py:573-574


class StockRunner:
    use_async_spec_decode = True

    def __init__(self):
        self.input_batch = Batch()
        self.num_accepted_tokens = NS(gpu=torch.ones(16, dtype=torch.int32))
        self.input_ids = NS(gpu=torch.zeros(128, dtype=torch.int32), cpu=torch.zeros(128, dtype=torch.int32))
        self.valid_sampled_token_count_gpu = None

    def _update_states(self, so):
        for rid in list(so.finished_req_ids):
            if rid in self.input_batch.req_ids:
                self.input_batch.remove_request(rid)
        for rid in [r for r in self.input_batch.req_ids if r not in so.num_scheduled_tokens]:
            self.input_batch.remove_request(rid)
        for rid in so.num_scheduled_tokens:                  # returning / new requests appended
            if rid not in self.input_batch.req_ids:
                self.input_batch.req_ids.append(rid)
        return None

    def _prepare_inputs(self, so, num_scheduled_tokens=None):
        prev = self.input_batch.prev_req_id_to_index or {}
        acc = self.num_accepted_tokens.gpu
        acc.fill_(1)
        for row, rid in enumerate(self.input_batch.req_ids):
            if rid in prev and self.valid_sampled_token_count_gpu is not None:
                acc[row] = int(self.valid_sampled_token_count_gpu[prev[rid]])
        pos = 0
        for rid in self.input_batch.req_ids:
            for t in [7] + list(so.scheduled_spec_decode_tokens.get(rid, ())):
                self.input_ids.cpu[pos] = t
                self.input_ids.gpu[pos] = t
                pos += 1
        return 'stock-result'


def sched_out(batch, spec=None, finished=(), resumed=()):
    spec = {} if spec is None else spec
    return NS(num_scheduled_tokens={r: 1 + len(spec.get(r, ())) for r in batch},
              scheduled_spec_decode_tokens=spec, finished_req_ids=set(finished),
              scheduled_cached_reqs=NS(resumed_req_ids=set(resumed)),
              total_num_scheduled_tokens=sum(1 + len(spec.get(r, ())) for r in batch))


def run_step(runner, batch, valid_after, spec=None, finished=(), resumed=(), reuse_buffer=False):
    """One engine step for the scheduled `batch`; returns num_accepted per request as the kernels would see it."""
    so = sched_out(batch, spec, finished, resumed)
    runner._update_states(so)
    out = runner._prepare_inputs(so, None)
    rows = list(runner.input_batch.req_ids)
    acc = {rid: int(runner.num_accepted_tokens.gpu[i]) for i, rid in enumerate(rows)}
    runner.input_batch.prev_req_id_to_index = {rid: i for i, rid in enumerate(rows)}
    valid = torch.tensor([valid_after[batch.index(r)] for r in rows], dtype=torch.int32)
    if reuse_buffer and runner.valid_sampled_token_count_gpu is not None:
        runner.valid_sampled_token_count_gpu[:len(valid)] = valid
    else:
        runner.valid_sampled_token_count_gpu = valid
    return out, acc


def patched_runner(log=None, base=StockRunner):
    class Runner(base):
        pass
    resume.install(Runner, log)
    return Runner()


class StockDefectTest(unittest.TestCase):
    def test_stock_loses_the_count_of_a_request_that_sat_out(self):
        r = StockRunner()
        run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})      # step N-1: a accepts 3, x accepts 4
        run_step(r, ['y'], [1])                                                 # step N: prompt-only, a and x hidden
        _, acc = run_step(r, ['a', 'x', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS, 'y': DRAFTS})
        self.assertEqual(acc, {'a': 1, 'x': 1, 'y': 1})                       # slot 0 instead of 2 and 3: the bug

    def test_hidden_request_is_gone_from_prev_map_before_prepare_inputs(self):
        # why 0.1.0 never fired: by _prepare_inputs the hidden request is no longer in prev_req_id_to_index
        r = StockRunner()
        run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        r._update_states(sched_out(['y']))
        self.assertEqual(r.input_batch.prev_req_id_to_index, {})


class OverlayTest(unittest.TestCase):
    def test_returning_requests_get_their_count(self):
        r = patched_runner()
        run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        run_step(r, ['y'], [2])
        _, acc = run_step(r, ['a', 'x', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS, 'y': DRAFTS})
        self.assertEqual(acc, {'a': 3, 'x': 4, 'y': 2})                        # y ran last step: stock value
        self.assertEqual(r._b70_resume['stash'], {})

    def test_order_change_on_return(self):
        r = patched_runner()
        run_step(r, ['a', 'b', 'x'], [2, 6, 1], spec={k: DRAFTS for k in 'abx'})
        run_step(r, ['y'], [1])
        _, acc = run_step(r, ['y', 'x', 'b', 'a'], [1, 1, 1, 1], spec={k: DRAFTS for k in 'abxy'})
        self.assertEqual(acc, {'y': 1, 'x': 1, 'b': 6, 'a': 2})

    def test_partial_skip_keeps_others_on_stock_path(self):
        r = patched_runner()
        run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        run_step(r, ['a'], [5], spec={'a': DRAFTS})                           # only x sits out
        _, acc = run_step(r, ['a', 'x'], [1, 1], spec={'a': DRAFTS, 'x': DRAFTS})
        self.assertEqual(acc, {'a': 5, 'x': 4})

    def test_no_skip_is_identical_to_stock(self):
        seq = [(['a'], [1], 'a'), (['a'], [6], ''), (['a'], [2], ''), (['a', 'b'], [1, 1], 'b'), (['a', 'b'], [4, 5], ''),
               (['a', 'b'], [1, 3], '')]
        stock, patched = StockRunner(), patched_runner()
        for batch, valid, new in seq:
            spec = {k: DRAFTS for k in batch if k not in new}
            s_out, s_acc = run_step(stock, batch, valid, spec=spec)
            p_out, p_acc = run_step(patched, batch, valid, spec=spec)
            self.assertEqual(s_out, p_out)
            self.assertEqual(s_acc, p_acc)
            self.assertTrue(torch.equal(stock.input_ids.gpu, patched.input_ids.gpu))

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
        run_step(r, ['y'], [9], reuse_buffer=True)            # the next step overwrites the same buffer in place
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
        run_step(r, ['y'], [1], finished=['a'])               # a finishes while out: never stored
        self.assertNotIn('a', r._b70_resume['stash'])
        _, acc = run_step(r, ['x', 'y'], [1, 1], resumed=['x'])
        self.assertEqual(acc['x'], 1)                         # resumed from preemption: recomputed, stock value
        self.assertEqual(r._b70_resume['stash'], {})

    def test_placeholder_drafts_of_a_returning_request_are_not_negative_ids(self):
        r = patched_runner()
        run_step(r, ['x'], [3], spec={'x': [11, 12]})
        run_step(r, ['y'], [1])
        run_step(r, ['x', 'y'], [1, 1], spec={'x': DRAFTS, 'y': [13]})
        rows = r.input_batch.req_ids
        self.assertEqual(rows, ['y', 'x'])
        self.assertGreaterEqual(int(r.input_ids.gpu.min()), 0)
        self.assertGreaterEqual(int(r.input_ids.cpu.min()), 0)
        self.assertEqual(r.input_ids.gpu[:8].tolist(), [7, 13, 7, 0, 0, 0, 0, 0])

    def test_sync_runner_untouched(self):
        class Sync(StockRunner):
            use_async_spec_decode = False
        r = patched_runner(base=Sync)
        run_step(r, ['x'], [4], spec={'x': DRAFTS})
        run_step(r, ['y'], [1])
        _, acc = run_step(r, ['x'], [1], spec={'x': DRAFTS})
        self.assertEqual(acc['x'], 1)

    def test_first_restore_logged_once(self):
        lines = []
        r = patched_runner(log=lambda fmt, *a: lines.append(fmt % a))
        for _ in range(3):
            run_step(r, ['x'], [4], spec={'x': DRAFTS})
            run_step(r, ['y'], [1])
        restores = [l for l in lines if 'first restore' in l]
        self.assertEqual(len(restores), 1)


class Event:
    def __init__(self):
        self.waits = 0

    def synchronize(self):
        self.waits += 1


class AlignStockRunner(StockRunner):
    """Align-mode prefix caching (R314 source): the count the GDN kernels read is the CPU array
    input_batch.num_accepted_tokens_cpu. After a step the align postprocess writes its per-row result there (1 where it
    already moved the state to the block-aligned slot); _prepare_inputs keeps it for rows of the previous step and puts 1
    in the others (gpu_model_runner.py:2137-2144); after preprocess_mamba the GPU count is rewritten from the CPU array
    (:4437-4444). Rows move with their requests when the batch is condensed (gpu_input_batch.py:813)."""
    cache_config = NS(mamba_cache_mode='align')

    def __init__(self):
        super().__init__()
        self.input_batch.num_accepted_tokens_cpu = torch.ones(16, dtype=torch.int32).numpy()
        self.num_accepted_tokens.np = torch.ones(16, dtype=torch.int32).numpy()
        self.num_accepted_tokens_event = Event()

    def _update_states(self, so):
        before = list(self.input_batch.req_ids)
        old = self.input_batch.num_accepted_tokens_cpu.copy()
        super()._update_states(so)
        cpu = self.input_batch.num_accepted_tokens_cpu
        for row, rid in enumerate(self.input_batch.req_ids):
            cpu[row] = old[before.index(rid)] if rid in before else 1      # condense moves rows; add_request sets 1
        return None

    def _prepare_inputs(self, so, num_scheduled_tokens=None):
        out = super()._prepare_inputs(so, num_scheduled_tokens)
        prev = self.input_batch.prev_req_id_to_index or {}
        cpu, host = self.input_batch.num_accepted_tokens_cpu, self.num_accepted_tokens.np
        for row, rid in enumerate(self.input_batch.req_ids):
            host[row] = cpu[row] if rid in prev else 1
            cpu[row] = host[row]
        self.num_accepted_tokens.gpu[:len(host)] = torch.from_numpy(host.copy())
        return out


def run_align_step(runner, batch, post_after, spec=None, finished=()):
    """One align-mode step: returns the count the GDN kernels read per request (after the stock CPU-to-GPU rewrite).
    `post_after`: the postprocessed count per request that the step leaves in the CPU array."""
    so = sched_out(batch, spec, finished)
    runner._update_states(so)
    runner._prepare_inputs(so, None)
    rows = list(runner.input_batch.req_ids)
    n = len(rows)
    runner.num_accepted_tokens.gpu[:n] = torch.from_numpy(runner.input_batch.num_accepted_tokens_cpu[:n].copy())
    acc = {rid: int(runner.num_accepted_tokens.gpu[i]) for i, rid in enumerate(rows)}
    runner.input_batch.prev_req_id_to_index = {rid: i for i, rid in enumerate(rows)}
    for i, rid in enumerate(rows):
        runner.input_batch.num_accepted_tokens_cpu[i] = post_after[batch.index(rid)]
    runner.valid_sampled_token_count_gpu = torch.tensor([post_after[batch.index(r)] for r in rows], dtype=torch.int32)
    return acc


class AlignModeTest(unittest.TestCase):
    def test_stock_align_loses_the_count(self):
        r = AlignStockRunner()
        run_align_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        run_align_step(r, ['y'], [1])
        acc = run_align_step(r, ['a', 'x', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS, 'y': DRAFTS})
        self.assertEqual(acc, {'a': 1, 'x': 1, 'y': 1})

    def test_overlay_0_2_gpu_restore_alone_would_be_overwritten(self):
        # 0.2.0 wrote only the GPU count; the stock rewrite from the CPU array undoes that (campaign 24)
        r = AlignStockRunner()
        run_align_step(r, ['a'], [3], spec={'a': DRAFTS})
        run_align_step(r, ['y'], [1])
        so = sched_out(['a', 'y'], {'a': DRAFTS})
        r._update_states(so)
        r._prepare_inputs(so, None)
        r.num_accepted_tokens.gpu[r.input_batch.req_ids.index('a')] = 3          # a GPU-only restore
        n = len(r.input_batch.req_ids)
        r.num_accepted_tokens.gpu[:n] = torch.from_numpy(r.input_batch.num_accepted_tokens_cpu[:n].copy())
        self.assertEqual(int(r.num_accepted_tokens.gpu[r.input_batch.req_ids.index('a')]), 1)

    def test_overlay_restores_in_cpu_array(self):
        r = patched_runner(base=AlignStockRunner)
        run_align_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        run_align_step(r, ['y'], [2])
        self.assertEqual(r.num_accepted_tokens_event.waits, 1)                 # waited once, in the step they sat out
        acc = run_align_step(r, ['a', 'x', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS, 'y': DRAFTS})
        self.assertEqual(acc, {'a': 3, 'x': 4, 'y': 2})
        self.assertEqual(r._b70_resume['stash'], {})

    def test_postprocessed_one_is_kept(self):
        # the postprocess already moved a's state to the block-aligned slot and left 1: restore 1, not the raw count
        r = patched_runner(base=AlignStockRunner)
        run_align_step(r, ['a', 'x'], [1, 5], spec={'a': DRAFTS, 'x': DRAFTS})
        r.valid_sampled_token_count_gpu = torch.tensor([6, 5], dtype=torch.int32)   # raw counts differ for a
        run_align_step(r, ['y'], [1])
        acc = run_align_step(r, ['x', 'a', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS})
        self.assertEqual((acc['a'], acc['x']), (1, 5))

    def test_partial_skip_and_order(self):
        r = patched_runner(base=AlignStockRunner)
        run_align_step(r, ['a', 'b', 'x'], [2, 6, 3], spec={k: DRAFTS for k in 'abx'})
        run_align_step(r, ['a'], [4], spec={'a': DRAFTS})                    # b and x sit out
        acc = run_align_step(r, ['x', 'b', 'a'], [1, 1, 1], spec={k: DRAFTS for k in 'abx'})
        self.assertEqual(acc, {'x': 3, 'b': 6, 'a': 4})

    def test_no_skip_identical_to_stock(self):
        seq = [(['a'], [1], 'a'), (['a'], [6], ''), (['a', 'b'], [2, 1], 'b'), (['a', 'b'], [4, 5], ''),
               (['a', 'b'], [1, 3], '')]
        stock, patched = AlignStockRunner(), patched_runner(base=AlignStockRunner)
        for batch, post, new in seq:
            spec = {k: DRAFTS for k in batch if k not in new}
            self.assertEqual(run_align_step(stock, batch, post, spec=spec), run_align_step(patched, batch, post, spec=spec))
        self.assertEqual(patched.num_accepted_tokens_event.waits, 0)          # no extra wait without a skipped request

    def test_finished_while_out_dropped(self):
        r = patched_runner(base=AlignStockRunner)
        run_align_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        run_align_step(r, ['y'], [1], finished=['a'])
        self.assertNotIn('a', r._b70_resume['stash'])
        self.assertIn('x', r._b70_resume['stash'])


class DebugTest(unittest.TestCase):
    def test_debug_lines_only_on_changed_steps_and_capped(self):
        os.environ['B70_SPEC_RESUME_DEBUG'] = '2'
        try:
            lines = []
            r = patched_runner(log=lambda fmt, *a: lines.append(fmt % a))
            run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})   # changed (from nothing): debug 1
            run_step(r, ['a', 'x'], [2, 3], spec={'a': DRAFTS, 'x': DRAFTS})   # same set: no line
            run_step(r, ['y'], [1])                                            # changed: debug 2
            run_step(r, ['a', 'x', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS})   # changed, cap reached
        finally:
            os.environ.pop('B70_SPEC_RESUME_DEBUG', None)
        dbg = [l for l in lines if l.startswith('b70_spec_resume_debug')]
        self.assertEqual(len(dbg), 2)
        self.assertIn('step=1 ', dbg[0])
        self.assertIn('step=3 ', dbg[1])
        self.assertIn("prev=['a', 'x']", dbg[1])
        self.assertIn("valid_prev=[2, 3]", dbg[1])

    def test_debug_shows_stock_and_overlay_counts(self):
        os.environ['B70_SPEC_RESUME_DEBUG'] = '5'
        try:
            lines = []
            r = patched_runner(log=lambda fmt, *a: lines.append(fmt % a))
            run_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
            run_step(r, ['y'], [1])
            run_step(r, ['a', 'x', 'y'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS})
        finally:
            os.environ.pop('B70_SPEC_RESUME_DEBUG', None)
        last = [l for l in lines if l.startswith('b70_spec_resume_debug')][-1]
        self.assertIn("acc_stock={'y': 1, 'a': 1, 'x': 1}", last)
        self.assertIn("acc_overlay={'y': 1, 'a': 3, 'x': 4}", last)
        self.assertIn("stored={'a': 3, 'x': 4}", last)



class DraftStockRunner(StockRunner):
    """Adds the stock draft handling: drafts of previous-step rows come from _draft_token_ids
    (_prepare_input_ids, gpu_model_runner.py:1909-1929); the rejection sampler's draft ids are gathered from
    input_ids inside _prepare_inputs (_calc_spec_decode_metadata, :2939-2941)."""
    def __init__(self):
        super().__init__()
        self._draft_token_ids = None

    def _prepare_inputs(self, so, num_scheduled_tokens=None):
        prev = self.input_batch.prev_req_id_to_index or {}
        super()._prepare_inputs(so, num_scheduled_tokens)
        pos, draft_pos = 0, []
        for rid in self.input_batch.req_ids:
            drafts = list(so.scheduled_spec_decode_tokens.get(rid, ()))
            end = pos + so.num_scheduled_tokens[rid]
            if rid in prev and self._draft_token_ids is not None:
                for j in range(len(drafts)):
                    self.input_ids.gpu[end - len(drafts) + j] = int(self._draft_token_ids[prev[rid], j])
            draft_pos.extend(range(end - len(drafts), end))
            pos = end
        metadata = NS(draft_token_ids=self.input_ids.gpu[torch.tensor(draft_pos, dtype=torch.long)])  # a copy
        return ('logits', metadata, 6)


def run_draft_step(runner, batch, valid_after, proposals, spec=None, finished=()):
    """One step; then the drafter proposes `proposals[req]` (5 ids) for each scheduled request.
    Returns (draft ids the sampler compares per request, input-id drafts per request)."""
    so = sched_out(batch, spec, finished)
    runner._update_states(so)
    _, metadata, _ = runner._prepare_inputs(so, None)
    rows = list(runner.input_batch.req_ids)
    compared, given, pos, off = {}, {}, 0, 0
    for rid in rows:
        n = len(so.scheduled_spec_decode_tokens.get(rid, ()))
        end = pos + so.num_scheduled_tokens[rid]
        compared[rid] = metadata.draft_token_ids[off:off + n].tolist()
        given[rid] = runner.input_ids.gpu[end - n:end].tolist()
        pos, off = end, off + n
    runner.input_batch.prev_req_id_to_index = {rid: i for i, rid in enumerate(rows)}
    runner.valid_sampled_token_count_gpu = torch.tensor([valid_after[batch.index(r)] for r in rows], dtype=torch.int32)
    runner._draft_token_ids = torch.tensor([proposals[r] for r in rows], dtype=torch.int64)
    return compared, given


def prop(base):
    return [base + i for i in range(5)]


class ResumeDraftsTest(unittest.TestCase):
    def setUp(self):
        self.env = unittest.mock.patch.dict(os.environ, {'B70_SPEC_RESUME_DRAFTS': '1'})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_stock_returning_request_compares_placeholders(self):
        r = DraftStockRunner()
        run_draft_step(r, ['a', 'x'], [3, 4], {'a': prop(10), 'x': prop(20)}, spec={'a': DRAFTS, 'x': DRAFTS})
        run_draft_step(r, ['y'], [1], {'y': prop(30)})
        compared, _ = run_draft_step(r, ['a', 'x', 'y'], [1, 1, 1], {k: prop(0) for k in 'axy'},
                                     spec={k: DRAFTS for k in 'axy'})
        self.assertEqual(compared, {'a': DRAFTS, 'x': DRAFTS, 'y': prop(30)})   # a and x: every draft rejected

    def test_returning_requests_get_their_drafts(self):
        r = patched_runner(base=DraftStockRunner)
        run_draft_step(r, ['a', 'x'], [3, 4], {'a': prop(10), 'x': prop(20)}, spec={'a': DRAFTS, 'x': DRAFTS})
        run_draft_step(r, ['y'], [1], {'y': prop(30)})
        compared, given = run_draft_step(r, ['a', 'x', 'y'], [1, 1, 1], {k: prop(0) for k in 'axy'},
                                         spec={k: DRAFTS for k in 'axy'})
        self.assertEqual(compared, {'a': prop(10), 'x': prop(20), 'y': prop(30)})
        self.assertEqual(given, compared)                                        # model input == sampler's drafts
        self.assertEqual(r._b70_resume['drafts'], {})

    def test_switch_off_is_0_3_0(self):
        with unittest.mock.patch.dict(os.environ, {'B70_SPEC_RESUME_DRAFTS': '0'}):
            r = patched_runner(base=DraftStockRunner)
            run_draft_step(r, ['a'], [3], {'a': prop(10)}, spec={'a': DRAFTS})
            run_draft_step(r, ['y'], [1], {'y': prop(30)})
            compared, given = run_draft_step(r, ['a', 'y'], [1, 1], {k: prop(0) for k in 'ay'},
                                             spec={k: DRAFTS for k in 'ay'})
        self.assertEqual(compared['a'], DRAFTS)
        self.assertEqual(given['a'], [0] * 5)                                    # 0.3.0: placeholders clamped
        self.assertEqual(r._b70_resume['drafts'], {})

    def test_order_change_and_two_steps_out(self):
        r = patched_runner(base=DraftStockRunner)
        run_draft_step(r, ['a', 'b', 'x'], [2, 6, 1], {'a': prop(10), 'b': prop(40), 'x': prop(20)},
                       spec={k: DRAFTS for k in 'abx'})
        run_draft_step(r, ['y'], [1], {'y': prop(30)})
        run_draft_step(r, ['z'], [1], {'z': prop(50)})
        compared, given = run_draft_step(r, ['x', 'b', 'a'], [1, 1, 1], {k: prop(0) for k in 'abx'},
                                         spec={k: DRAFTS for k in 'abx'})
        self.assertEqual(compared, {'x': prop(20), 'b': prop(40), 'a': prop(10)})
        self.assertEqual(given, compared)

    def test_partial_skip_others_on_stock_path(self):
        r = patched_runner(base=DraftStockRunner)
        run_draft_step(r, ['a', 'x'], [3, 4], {'a': prop(10), 'x': prop(20)}, spec={'a': DRAFTS, 'x': DRAFTS})
        run_draft_step(r, ['x', 'y'], [2, 1], {'x': prop(60), 'y': prop(30)}, spec={'x': DRAFTS})
        compared, _ = run_draft_step(r, ['a', 'x', 'y'], [1, 1, 1], {k: prop(0) for k in 'axy'},
                                     spec={k: DRAFTS for k in 'axy'})
        self.assertEqual(compared, {'a': prop(10), 'x': prop(60), 'y': prop(30)})

    def test_real_drafts_and_shorter_drafts(self):
        r = patched_runner(base=DraftStockRunner)
        run_draft_step(r, ['a', 'b'], [3, 3], {'a': prop(10), 'b': prop(40)}, spec={'a': DRAFTS, 'b': DRAFTS})
        run_draft_step(r, ['y'], [1], {'y': prop(30)})
        compared, given = run_draft_step(r, ['a', 'b'], [1, 1], {k: prop(0) for k in 'ab'},
                                         spec={'a': [7, 8, 9], 'b': [-1, -1]})
        self.assertEqual(compared['a'], [7, 8, 9])                               # scheduler sent real drafts: kept
        self.assertEqual(compared['b'], [40, 41])                                # two slots: first two drafts
        self.assertEqual(given['b'], [40, 41])

    def test_finished_and_prompt_continuation_drop_the_drafts(self):
        r = patched_runner(base=DraftStockRunner)
        run_draft_step(r, ['a', 'p', 'x'], [3, 1, 2], {'a': prop(10), 'p': prop(70), 'x': prop(20)},
                       spec={'a': DRAFTS, 'x': DRAFTS})
        run_draft_step(r, ['y'], [1], {'y': prop(30)}, finished=['x'])
        compared, given = run_draft_step(r, ['a', 'p'], [1, 1], {k: prop(0) for k in 'ap'}, spec={'a': DRAFTS})
        self.assertEqual(compared, {'a': prop(10), 'p': []})
        self.assertEqual(set(r._b70_resume['drafts']), {'y'})                   # x finished, p had no drafts; y is out now

    def test_no_skip_identical_to_stock(self):
        stock, r = DraftStockRunner(), patched_runner(base=DraftStockRunner)
        for runner in (stock, r):
            run_draft_step(runner, ['a', 'x'], [3, 4], {'a': prop(10), 'x': prop(20)}, spec={'a': DRAFTS, 'x': DRAFTS})
        a = run_draft_step(stock, ['a', 'x'], [1, 1], {'a': prop(0), 'x': prop(0)}, spec={'a': DRAFTS, 'x': DRAFTS})
        b = run_draft_step(r, ['a', 'x'], [1, 1], {'a': prop(0), 'x': prop(0)}, spec={'a': DRAFTS, 'x': DRAFTS})
        self.assertEqual(a, b)
        self.assertTrue(torch.equal(stock.input_ids.gpu, r.input_ids.gpu))

    def test_first_draft_restore_logged_once(self):
        lines = []
        r = patched_runner(log=lambda *a: lines.append(a[0] % a[1:]), base=DraftStockRunner)
        for _ in range(2):
            run_draft_step(r, ['a'], [3], {'a': prop(10)}, spec={'a': DRAFTS})
            run_draft_step(r, ['y'], [1], {'y': prop(30)})
            run_draft_step(r, ['a', 'y'], [1, 1], {k: prop(0) for k in 'ay'}, spec={k: DRAFTS for k in 'ay'})
        self.assertEqual(sum('first draft restore' in l for l in lines), 1)


class LateCopyEvent:
    """num_accepted_tokens_event: the previous step's align postprocess copies its counts into the CPU array on the
    device (mamba_utils.py:1638-1639, non_blocking); waiting on the event is when those copies have landed."""
    def __init__(self, runner):
        self.runner, self.pending, self.waits = runner, [], 0

    def synchronize(self):
        self.waits += 1
        for row, value in self.pending:
            self.runner.input_batch.num_accepted_tokens_cpu[row] = value
        self.pending = []


class LateCopyAlignRunner(StockRunner):
    """Align mode as in R314, including the hand-over case: _update_states condenses rows and add_request writes 1
    (gpu_input_batch.py:484) before the previous step's postprocess copy has landed; _prepare_inputs waits on the
    event, then keeps prev-row values and gives new rows 1 when prev_req_id_to_index is non-empty, or copies the CPU
    array as is when it is empty (gpu_model_runner.py:2132-2150)."""
    cache_config = NS(mamba_cache_mode='align')

    def __init__(self):
        super().__init__()
        self.input_batch.num_accepted_tokens_cpu = torch.ones(16, dtype=torch.int32).numpy()
        self.num_accepted_tokens.np = torch.ones(16, dtype=torch.int32).numpy()
        self.num_accepted_tokens_event = LateCopyEvent(self)

    def _update_states(self, so):
        before = list(self.input_batch.req_ids)
        old = self.input_batch.num_accepted_tokens_cpu.copy()
        super()._update_states(so)
        cpu = self.input_batch.num_accepted_tokens_cpu
        for row, rid in enumerate(self.input_batch.req_ids):
            cpu[row] = old[before.index(rid)] if rid in before else 1
        return None

    def _prepare_inputs(self, so, num_scheduled_tokens=None):
        out = super()._prepare_inputs(so, num_scheduled_tokens)
        self.num_accepted_tokens_event.synchronize()
        prev = self.input_batch.prev_req_id_to_index
        cpu, host = self.input_batch.num_accepted_tokens_cpu, self.num_accepted_tokens.np
        n = len(self.input_batch.req_ids)
        if prev:
            for row, rid in enumerate(self.input_batch.req_ids):
                host[row] = cpu[prev[rid]] if rid in prev else 1
            cpu[:n] = host[:n]
        else:
            host[:n] = cpu[:n]
        self.num_accepted_tokens.gpu[:n] = torch.from_numpy(host[:n].copy())
        return out


def run_late_step(runner, batch, post_after, spec=None, finished=()):
    """One step; returns the count preprocess_mamba uses as the pre-copy bias source per request (the CPU array after
    _prepare_inputs and the overlay). The step's own postprocessed counts are left as a copy that lands later."""
    so = sched_out(batch, spec, finished)
    runner._update_states(so)
    runner._prepare_inputs(so, None)
    rows = list(runner.input_batch.req_ids)
    acc = {rid: int(runner.input_batch.num_accepted_tokens_cpu[i]) for i, rid in enumerate(rows)}
    runner.input_batch.prev_req_id_to_index = {rid: i for i, rid in enumerate(rows)}
    runner.num_accepted_tokens_event.pending = [(i, post_after[batch.index(rid)]) for i, rid in enumerate(rows)]
    runner.valid_sampled_token_count_gpu = torch.tensor([post_after[batch.index(r)] for r in rows], dtype=torch.int32)
    return acc


class FreshRowTest(unittest.TestCase):
    """0.5.0: a new request that takes over the row of a request that just finished, with nobody else left from the
    previous step (one sequence, or both users finishing together)."""

    def test_stock_new_request_reads_the_finished_requests_count(self):
        r = LateCopyAlignRunner()
        run_late_step(r, ['a'], [4], spec={'a': DRAFTS})
        acc = run_late_step(r, ['b'], [1], finished=['a'])
        self.assertEqual(acc, {'b': 4})                                  # the defect: bias 3 for b's hit pre-copy

    def test_overlay_gives_the_new_request_one(self):
        logs = []
        r = patched_runner(log=lambda fmt, *a: logs.append(fmt % a), base=LateCopyAlignRunner)
        run_late_step(r, ['a'], [4], spec={'a': DRAFTS})
        acc = run_late_step(r, ['b'], [1], finished=['a'])
        self.assertEqual(acc, {'b': 1})
        self.assertEqual(int(r.num_accepted_tokens.gpu[0]), 1)
        self.assertEqual(int(r.num_accepted_tokens.np[0]), 1)
        self.assertEqual([m for m in logs if 'new-request count reset, 1 row' in m and 'step 2' in m], logs)
        run_late_step(r, ['c'], [1], finished=['b'])                    # b left 1: nothing to reset, no new line
        self.assertEqual(len(logs), 1)

    def test_switch_off_is_0_4_0(self):
        with unittest.mock.patch.dict(os.environ, {'B70_SPEC_RESUME_FRESH': '0'}):
            r = patched_runner(base=LateCopyAlignRunner)
            run_late_step(r, ['a'], [4], spec={'a': DRAFTS})
            acc = run_late_step(r, ['b'], [1], finished=['a'])
        self.assertEqual(acc, {'b': 4})

    def test_other_user_still_running_is_stock(self):
        stock, patched = LateCopyAlignRunner(), patched_runner(base=LateCopyAlignRunner)
        for runner in (stock, patched):
            run_late_step(runner, ['a', 'c'], [4, 3], spec={'a': DRAFTS, 'c': DRAFTS})
        acc_stock = run_late_step(stock, ['c', 'b'], [2, 1], spec={'c': DRAFTS}, finished=['a'])
        acc_patched = run_late_step(patched, ['c', 'b'], [2, 1], spec={'c': DRAFTS}, finished=['a'])
        self.assertEqual(acc_stock, {'c': 3, 'b': 1})
        self.assertEqual(acc_patched, acc_stock)
        self.assertIn(patched._b70_resume.get('fresh_resets'), (None, []))   # nothing to change

    def test_returning_requests_keep_their_counts_when_prev_empties(self):
        r = patched_runner(base=LateCopyAlignRunner)
        run_late_step(r, ['a', 'x'], [3, 4], spec={'a': DRAFTS, 'x': DRAFTS})
        run_late_step(r, ['y'], [2])                                     # a and x sit out
        acc = run_late_step(r, ['a', 'x', 'z'], [1, 1, 1], spec={'a': DRAFTS, 'x': DRAFTS}, finished=['y'])
        self.assertEqual(acc, {'a': 3, 'x': 4, 'z': 1})

    def test_steady_single_user_untouched(self):
        stock, patched = LateCopyAlignRunner(), patched_runner(base=LateCopyAlignRunner)
        seq = [(['a'], [1], None), (['a'], [5], DRAFTS), (['a'], [2], DRAFTS), (['a'], [6], DRAFTS)]
        for batch, post, spec in seq:
            sp = {'a': spec} if spec else None
            self.assertEqual(run_late_step(stock, batch, post, spec=sp), run_late_step(patched, batch, post, spec=sp))


class RegisterTest(unittest.TestCase):
    def test_env_gate_and_idempotent(self):
        class GPUModelRunner(StockRunner):
            pass
        mods = {'vllm': types.ModuleType('vllm'), 'vllm.logger': types.ModuleType('vllm.logger'),
                'vllm.v1': types.ModuleType('vllm.v1'), 'vllm.v1.worker': types.ModuleType('vllm.v1.worker'),
                'vllm.v1.worker.gpu_model_runner': types.ModuleType('vllm.v1.worker.gpu_model_runner')}
        mods['vllm.logger'].init_logger = lambda name: NS(warning=lambda *a, **k: None)
        mods['vllm.v1.worker.gpu_model_runner'].GPUModelRunner = GPUModelRunner
        mods['vllm.v1.worker'].gpu_model_runner = mods['vllm.v1.worker.gpu_model_runner']
        saved = {k: sys.modules.get(k) for k in mods}
        sys.modules.update(mods)
        try:
            os.environ.pop('B70_SPEC_RESUME_ACCEPTED', None)
            resume.register()
            self.assertIs(GPUModelRunner._prepare_inputs, StockRunner._prepare_inputs)
            os.environ['B70_SPEC_RESUME_ACCEPTED'] = '1'
            resume.register()
            first = (GPUModelRunner._update_states, GPUModelRunner._prepare_inputs)
            resume.register()
            self.assertEqual((GPUModelRunner._update_states, GPUModelRunner._prepare_inputs), first)
            r = GPUModelRunner()
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

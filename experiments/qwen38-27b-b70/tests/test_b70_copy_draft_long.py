"""CPU check of the long copy drafts in the copy-draft overlay (B70_COPY_DRAFT_K_MAX, sync scheduling).

The fake runner mimics the stock pieces the overlay relies on (vLLM 0.29, R310 image):
- the drafter drafts `scheduler_output.num_spec_tokens_to_schedule` tokens (the dynamic-SD depth, 5 here), or fills
  zeros of width `num_spec_tokens` when it is skipped;
- sync bookkeeping writes the accepted tokens into token_ids_cpu before `take_draft_token_ids`;
- the scheduler schedules every token of each request's list (no clamp to num_speculative_tokens) and the greedy
  rejection sampler accepts the longest prefix of the draft that matches the target, plus one bonus token;
- `input_batch.num_accepted_tokens_cpu` holds each request's accepted count of the step just verified (bonus
  included), which the GDN builder passes as num_accepted_tokens to the next step. The Engine checks the GDN width
  rule on every verify: rows (draft length + 1) >= the previous step's accepted count, otherwise the XPU spec kernels
  read the initial SSM state from past the end of the step's state-slot row (the R313 copy-arm mismatches).
"""
import importlib.util
import random
import types
import unittest
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cdl', HERE / 'overlays/b70-copy-draft/b70_copy_draft.py')
cd = importlib.util.module_from_spec(spec); spec.loader.exec_module(cd)

NS = types.SimpleNamespace
DEPTH = 5
MTP = 99999


class Logger:
    def __init__(self):
        self.lines = []

    def warning(self, fmt, *args):
        self.lines.append(fmt % args if args else fmt)

    def exception(self, fmt, *args):
        raise AssertionError('overlay raised: ' + (fmt % args if args else fmt))


def fake_runner_class():
    class Runner:
        def __init__(self, num_spec=16, schedule=((1, 1, DEPTH),), use_async=False, max_model_len=4096, rows=4):
            self.speculative_config = NS(method='qwen3_next_mtp', disable_padded_drafter_batch=False,
                                         num_speculative_tokens=num_spec,
                                         num_speculative_tokens_per_batch_size=[list(t) for t in schedule]
                                         if schedule else None)
            self.parallel_config = NS(pipeline_parallel_size=1)
            self.enable_prompt_embeds = False
            self.num_spec_tokens = num_spec
            self.depth = cd.mtp_depth(self.speculative_config, num_spec)[0]
            self.use_async_scheduling = use_async
            self.max_model_len = max_model_len
            self.requests = {}
            self.input_batch = NS(req_ids=[], greedy_reqs=set(), req_id_to_index={},
                                  token_ids_cpu=np.zeros((rows, max_model_len), dtype=np.int32),
                                  num_tokens_no_spec=np.zeros(rows, dtype=np.int32),
                                  num_accepted_tokens_cpu=np.ones(rows, dtype=np.int32))
            self.num_accepted_tokens_event = None
            self.discard_request_mask = NS(np=np.zeros(rows, dtype=bool))
            self._draft_token_ids = None
            self._draft_probs = None
            self._draft_token_req_ids = None
            self.execute_model_state = None
            self.fits = True
            self.seen_drafts = None

        def propose_draft_token_ids(self, scheduler_output, sampled_token_ids, *args, **kwargs):
            width = scheduler_output.num_spec_tokens_to_schedule
            return torch.full((sampled_token_ids.shape[0], width), MTP, dtype=torch.int64)

        def _prepare_input_ids(self, *args, **kwargs):
            self.seen_drafts = None if self._draft_token_ids is None else self._draft_token_ids.clone()

        def take_draft_token_ids(self):
            if self._draft_token_ids is None:
                return None
            return NS(req_ids=list(self.input_batch.req_ids), draft_token_ids=self._draft_token_ids.tolist())

        def sample_tokens(self, grammar_output=None):
            self._draft_token_ids = None
            if self.execute_model_state is None:
                return None
            if self.fits:
                self._draft_token_ids = self.propose_draft_token_ids(self.sched, self.sampled)
            else:
                self._draft_token_ids = torch.zeros(1, dtype=torch.int64).expand(len(self.input_batch.req_ids),
                                                                                  self.num_spec_tokens)
            for i, row in enumerate(self.sampled.tolist()):
                self.input_batch.num_accepted_tokens_cpu[i] = len(cd.accepted_prefix(row))
            if not self.use_async_scheduling:
                for i, row in enumerate(self.sampled.tolist()):
                    accepted = cd.accepted_prefix(row)
                    n = int(self.input_batch.num_tokens_no_spec[i])
                    self.input_batch.token_ids_cpu[i, n:n + len(accepted)] = accepted
                    self.input_batch.num_tokens_no_spec[i] = n + len(accepted)
            return 'output'
    return Runner


class Engine:
    """Drives a fake runner like the sync engine core: schedule each request's list as it is, verify it greedily
    against a fixed true continuation, bookkeep, then take the next drafts."""

    def __init__(self, runner, prompts, truths, max_tokens=None, greedy=True):
        self.runner, self.prompts, self.truths = runner, prompts, truths
        self.ids = ['r%d' % i for i in range(len(prompts))]
        batch = runner.input_batch
        batch.req_ids = list(self.ids)
        batch.req_id_to_index = {r: i for i, r in enumerate(self.ids)}
        batch.greedy_reqs = set(self.ids) if greedy else set()
        for i, (r, p) in enumerate(zip(self.ids, prompts)):
            runner.requests[r] = NS(prompt_token_ids=list(p), num_prompt_tokens=len(p), num_computed_tokens=0,
                                    sampling_params=NS(max_tokens=max_tokens, structured_outputs=None))
            batch.token_ids_cpu[i, :len(p)] = p
            batch.num_tokens_no_spec[i] = len(p)
        self.emitted = [[] for _ in self.ids]
        self.drafts = None
        self.widths = []          # per step: the draft length each request was verified with
        self.verified = []        # per step: (request index, draft, accepted)
        self.prev_accepted = [1 for _ in self.ids]
        self.width_violations = []   # (step, request index, rows, previous accepted): GDN reads past its slot row

    def step(self):
        runner = self.runner
        rows, widths = [], []
        for i in range(len(self.ids)):
            truth, pos = self.truths[i], len(self.emitted[i])
            if self.drafts is None:
                row = [truth[0]]
                widths.append(0)
            else:
                n = len(self.prompts[i]) + pos
                d = self.drafts[i][:max(0, runner.max_model_len - n - 1)]   # the scheduler's max_model_len clamp
                a = 0
                while a < len(d) and d[a] == truth[pos + a]:
                    a += 1
                row = truth[pos:pos + a + 1]
                widths.append(len(d))
                self.verified.append((i, list(d), a))
                if d and len(d) + 1 < self.prev_accepted[i]:
                    self.width_violations.append((len(self.widths), i, len(d) + 1, self.prev_accepted[i],
                                                  runner.max_model_len - n - 1))
            self.prev_accepted[i] = len(row)
            rows.append(row)
            self.emitted[i].extend(row)
        width = max(len(r) for r in rows)
        runner.sampled = torch.tensor([r + [-1] * (width - len(r)) for r in rows], dtype=torch.int32)
        runner.sched = NS(num_scheduled_tokens={r: 1 + w for r, w in zip(self.ids, widths)},
                          num_spec_tokens_to_schedule=runner.depth, has_structured_output_requests=False)
        runner.execute_model_state = object()
        runner.sample_tokens()
        runner.execute_model_state = None
        self.widths.append(widths)
        result = runner.take_draft_token_ids()
        self.drafts = None if result is None else result.draft_token_ids
        return result

    def run(self, steps):
        for _ in range(steps):
            self.step()
        return self


def repeating_case(seed, length=400, body_len=120):
    rng = random.Random(seed)
    body = [rng.randrange(1, 50000) for _ in range(body_len)]
    prompt = body + [rng.randrange(1, 50000) for _ in range(30)]
    truth = (body * 6)[:length]       # the model "repeats" the prompt body
    return prompt, truth


def random_case(seed, length=400):
    rng = random.Random(seed)
    return [rng.randrange(1, 50000) for _ in range(150)], [rng.randrange(1, 50000) for _ in range(length)]


class LookupTest(unittest.TestCase):
    def test_k_max_reference_examples(self):
        ctx = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2, 3, 4, 5, 6]
        self.assertEqual(cd.find_copy_draft(ctx, 6, 6, 8, 16), [7, 8, 9, 10, 11, 1, 2, 3, 4, 5, 6])  # all that follow
        self.assertEqual(cd.find_copy_draft(ctx, 6, 6, 8, 8), [7, 8, 9, 10, 11, 1, 2, 3])
        self.assertIsNone(cd.find_copy_draft(ctx, 12, 6, 8, 16))     # fewer than the minimum follow
        self.assertEqual(cd.find_copy_draft(ctx, 5, 6, 8, None), [7, 8, 9, 10, 11])   # unchanged without k_max
        # the occurrence must have at least k after it; a more recent one with fewer is passed over
        ctx = [1, 2, 3, 4, 5, 6, 50, 51, 52, 53, 54, 55, 56, 9, 1, 2, 3, 4, 5, 6, 70, 71, 72, 73, 74, 1, 2, 3, 4, 5, 6]
        self.assertEqual(cd.find_copy_draft(ctx, 6, 6, 8, 16)[:6], [70, 71, 72, 73, 74, 1])
        self.assertEqual(cd.find_copy_draft(ctx, 12, 6, 8, 16)[:7], [50, 51, 52, 53, 54, 55, 56])

    def test_index_matches_reference_with_k_max(self):
        rng = random.Random(5)
        for trial in range(250):
            vocab = rng.choice((2, 3, 4, 8, 50))
            seq = [rng.randrange(vocab) for _ in range(rng.randrange(1, 200))]
            lo = rng.choice((1, 2, 3, 6))
            hi = lo + rng.choice((0, 1, 2, 4))
            index = cd.CopyIndex(lo, hi)
            pos = 0
            while pos < len(seq):
                step = rng.choice((1, 2, 3, 6, 17))
                index.extend(seq[pos:pos + step])
                pos = min(len(seq), pos + step)
                k = rng.choice((1, 5, 6))
                k_max = rng.choice((None, k, 9, 16, 32))
                self.assertEqual(index.propose(k, k_max), cd.find_copy_draft(seq[:pos], k, lo, hi, k_max))


class LongDraftTest(unittest.TestCase):
    def install(self, k_max=None):
        env = {} if k_max is None else {'B70_COPY_DRAFT_K_MAX': str(k_max)}
        self.settings = cd.settings_from_env(env)
        self.cls = fake_runner_class()
        self.logger = Logger()
        cd.install(self.cls, torch, self.logger, self.settings, copier_factory=cd.ImmediateCopier)

    def assert_exact(self, engine):
        for e, t in zip(engine.emitted, engine.truths):
            self.assertEqual(e, t[:len(e)])
        self.assertEqual(engine.width_violations, [])

    def test_k_max_unset_keeps_fixed_depth(self):
        self.install()
        for num_spec, schedule in ((DEPTH, None), (16, ((1, 1, DEPTH),))):
            prompt, truth = repeating_case(1)
            runner = self.cls(num_spec=num_spec, schedule=schedule)
            engine = Engine(runner, [prompt], [truth]).run(40)
            self.assert_exact(engine)
            self.assertEqual({w for step in engine.widths[1:] for w in step}, {DEPTH})
            state = runner._b70_copy_draft_state
            self.assertEqual((state.k, state.long_k), (DEPTH, 0))
            self.assertGreater(state.book.stats['copies'], 0)          # the 5-token copy still fires
            self.assertEqual(state.book.stats['long_drafts'], 0)
            self.assertNotIn('long drafts', state.book.summary('sync'))

    def test_long_draft_placed_accepted_and_exact(self):
        self.install(16)
        prompt, truth = repeating_case(2)
        runner = self.cls()
        engine = Engine(runner, [prompt], [truth]).run(30)
        self.assert_exact(engine)
        state = runner._b70_copy_draft_state
        self.assertEqual(state.long_k, 16)
        longs = [(d, a) for _, d, a in engine.verified if len(d) > DEPTH and MTP not in d]   # not width-padded MTP
        self.assertTrue(longs)
        self.assertTrue(all(len(d) <= 16 for d, _ in longs))
        self.assertTrue(any(a == 16 for _, a in longs))                # whole 16-token copies accepted
        s = state.book.stats
        pending_long = len(engine.drafts[0]) > DEPTH and MTP not in engine.drafts[0]
        self.assertEqual(s['long_drafts'], len(longs) + (1 if pending_long else 0))
        # attribution: every verified long draft is counted with exactly the accepted tokens the engine saw
        self.assertEqual(s['long_verified'], len(longs))
        self.assertEqual(s['long_accepted'], sum(a for _, a in longs))
        self.assertTrue(any('first long copy draft placed' in line for line in self.logger.lines))
        self.assertIn('long drafts (max 16)', state.book.summary('sync'))
        # far fewer steps than 6 tokens a step would need
        self.assertGreater(len(engine.emitted[0]), 30 * (DEPTH + 1))

    def test_long_draft_rejected_partway_stays_exact(self):
        self.install(16)
        prompt, truth = repeating_case(3)
        truth = list(truth)
        for p in range(130, len(truth), 37):                # the "model" departs from the copy now and then
            truth[p] = 7 + p
        runner = self.cls()
        engine = Engine(runner, [prompt], [truth]).run(60)
        self.assert_exact(engine)
        longs = [(d, a) for _, d, a in engine.verified if len(d) > DEPTH and MTP not in d]
        self.assertTrue(any(a < len(d) for d, a in longs))             # some long drafts rejected partway
        s = runner._b70_copy_draft_state.book.stats
        self.assertEqual(s['long_accepted'], sum(a for _, a in longs))
        self.assertEqual(s['rebuilds'], 0)                              # history never desynchronised

    def departing_case(self, seed, every=23):
        prompt, truth = repeating_case(seed)
        truth = list(truth)
        for p in range(140, len(truth), every):            # long copies accepted partway (7..16 tokens), then MTP
            truth[p] = 7 + p
        return prompt, truth

    def test_width_kept_after_long_acceptance(self):
        # The R313 copy-arm defect: a long draft accepting a >= DEPTH+2 tokens followed by a DEPTH-token MTP draft.
        for k_max in (9, 16):
            self.install(k_max)
            prompt, truth = self.departing_case(13)
            runner = self.cls(num_spec=k_max)
            engine = Engine(runner, [prompt], [truth]).run(80)
            self.assert_exact(engine)                                  # includes: no width violation
            s = runner._b70_copy_draft_state.book.stats
            self.assertGreater(s['width_pads'], 0)
            self.assertEqual(s['width_blocked'], 0)
            self.assertIn('width pads %d' % s['width_pads'], runner._b70_copy_draft_state.book.summary('sync'))
            self.assertTrue(all(len(d) <= k_max for _, d, _ in engine.verified))

    def test_without_width_rule_the_engine_sees_the_defect(self):
        original = cd.keep_width
        cd.keep_width = lambda *args, **kwargs: None
        try:
            self.install(9)
            prompt, truth = self.departing_case(13)
            engine = Engine(self.cls(num_spec=9), [prompt], [truth]).run(80)
        finally:
            cd.keep_width = original
        self.assertTrue(engine.width_violations)                       # e.g. 6 rows after 7..10 accepted
        self.assertTrue(all(rows == DEPTH + 1 and prev > rows for _, _, rows, prev, _ in engine.width_violations))

    def test_width_pad_capped_at_max_model_len(self):
        self.install(9)
        prompt, truth = repeating_case(14)
        runner = self.cls(num_spec=9, max_model_len=len(prompt) + 60)
        engine = Engine(runner, [prompt], [truth])
        while len(prompt) + len(engine.emitted[0]) < runner.max_model_len - 2:
            result = engine.step()
            n = len(prompt) + len(engine.emitted[0])
            d = result.draft_token_ids[0]
            if len(d) > DEPTH:
                self.assertLessEqual(len(d), runner.max_model_len - n - 1)
        # the only steps narrower than the previous acceptance are the ones max_model_len itself cuts (stock R307)
        self.assertTrue(all(rows - 1 == room for _, _, rows, _, room in engine.width_violations))

    def test_mixed_batch_only_matching_request_gets_long_draft(self):
        self.install(16)
        prompt0, truth0 = repeating_case(4)
        prompt1, truth1 = random_case(5)
        runner = self.cls(schedule=((1, 4, DEPTH),))
        engine = Engine(runner, [prompt0, prompt1], [truth0, truth1]).run(20)
        self.assert_exact(engine)
        widths1 = [step[1] for step in engine.widths[1:]]
        self.assertEqual(set(widths1), {DEPTH})                        # no copy: exactly the MTP draft shape
        drafts1 = [d for i, d, _ in engine.verified if i == 1]
        self.assertTrue(all(d == [MTP] * DEPTH for d in drafts1))     # ... and the MTP ids themselves
        self.assertTrue(any(step[0] > DEPTH for step in engine.widths[1:]))

    def test_budget_caps(self):
        self.install(16)
        prompt, truth = repeating_case(6)
        # max_tokens: a draft of L yields up to L+1 tokens, never more than are left
        runner = self.cls()
        engine = Engine(runner, [prompt], [truth], max_tokens=50)
        lengths = []
        while len(engine.emitted[0]) < 50 - 1:
            result = engine.step()
            left = 50 - len(engine.emitted[0])
            d = result.draft_token_ids[0]
            need = int(runner.input_batch.num_accepted_tokens_cpu[0]) - 1
            lengths.append(len(d))
            if len(d) > max(DEPTH, need):
                self.assertLessEqual(len(d) + 1, left)
            elif left - 1 <= DEPTH:
                self.assertEqual(len(d), max(DEPTH, need))              # short budget: fixed length or width pad
        self.assertIn(16, lengths)
        self.assertTrue(any(DEPTH < n < 16 for n in lengths))           # a long draft shortened by the budget
        self.assert_exact(engine)
        # max_model_len: positions stay below it
        runner = self.cls(max_model_len=len(prompt) + 40)
        engine = Engine(runner, [prompt], [truth])
        while len(prompt) + len(engine.emitted[0]) < runner.max_model_len - 2:
            result = engine.step()
            n = len(prompt) + len(engine.emitted[0])
            d = result.draft_token_ids[0]
            if len(d) > DEPTH:
                self.assertLessEqual(len(d), runner.max_model_len - n - 1)
        self.assertGreater(runner._b70_copy_draft_state.book.stats['long_capped'], 0)

    def test_structured_and_non_greedy_get_no_long_draft(self):
        self.install(16)
        prompt, truth = repeating_case(7)
        runner = self.cls()
        engine = Engine(runner, [prompt], [truth])
        runner.requests['r0'].sampling_params.structured_outputs = object()
        engine.run(20)
        self.assertEqual(runner._b70_copy_draft_state.book.stats['long_drafts'], 0)
        runner = self.cls()
        engine = Engine(runner, [prompt], [truth], greedy=False).run(20)
        self.assertEqual({w for step in engine.widths[1:] for w in step}, {DEPTH})
        self.assertEqual(engine.verified[-1][1], [MTP] * DEPTH)

    def test_drafter_skipped_zero_fill_cut_to_depth(self):
        self.install(16)
        prompt, truth = repeating_case(8)
        runner = self.cls()
        engine = Engine(runner, [prompt], [truth]).run(5)
        runner.fits = False
        result = engine.step()
        need = int(runner.input_batch.num_accepted_tokens_cpu[0]) - 1
        self.assertEqual(result.draft_token_ids, [[0] * max(DEPTH, need)])   # not 16 zeros (unless the width needs)
        runner.fits = True
        engine.run(10)
        self.assert_exact(engine)

    def test_async_falls_back_with_one_line(self):
        self.install(16)
        prompt, truth = repeating_case(9)
        runner = self.cls(use_async=True)
        sched = NS(num_scheduled_tokens={'r0': 1}, num_spec_tokens_to_schedule=DEPTH,
                   has_structured_output_requests=False)
        runner.input_batch.req_ids = ['r0']
        runner.input_batch.req_id_to_index = {'r0': 0}
        runner.input_batch.greedy_reqs = {'r0'}
        runner.requests['r0'] = NS(prompt_token_ids=list(prompt), num_computed_tokens=0, num_prompt_tokens=len(prompt))
        emitted, drafts = [], None
        for step in range(30):                     # async: the drafts are swapped in at the next input preparation
            runner._prepare_input_ids()
            pos = len(emitted)
            if drafts is None:
                row = [truth[0]]
            else:
                d = runner.seen_drafts[0].tolist()
                self.assertEqual(len(d), DEPTH)
                a = 0
                while a < len(d) and d[a] == truth[pos + a]:
                    a += 1
                row = truth[pos:pos + a + 1]
            runner.requests['r0'].num_computed_tokens = 0 if step == 0 else len(prompt) + pos
            emitted.extend(row)
            runner.sampled = torch.tensor([row + [-1] * (DEPTH + 1 - len(row))], dtype=torch.int32)
            sched.num_scheduled_tokens = {'r0': len(prompt) if step == 0 else DEPTH + 1}
            runner.sched = sched
            runner.execute_model_state = object(); runner.sample_tokens(); runner.execute_model_state = None
            drafts = runner._draft_token_ids
        self.assertEqual(emitted, truth[:len(emitted)])
        state = runner._b70_copy_draft_state
        self.assertEqual((state.mode, state.k, state.long_k), ('async', DEPTH, 0))
        self.assertGreater(state.book.stats['copies'], 0)             # the fixed-length copy still works
        lines = [l for l in self.logger.lines if '--no-async-scheduling' in l]
        self.assertEqual(len(lines), 1)

    def test_misconfigured_launch_turns_long_drafts_off(self):
        self.install(16)
        cases = (
            (DEPTH, None, 'launch with num_speculative_tokens=16'),           # slots not reserved
            (16, ((1, 1, DEPTH), (2, 8, 1)), 'one depth for every batch size'),
        )
        for num_spec, schedule, needle in cases:
            prompt, truth = repeating_case(10)
            runner = self.cls(num_spec=num_spec, schedule=schedule)
            engine = Engine(runner, [prompt], [truth]).run(20)
            self.assert_exact(engine)
            self.assertEqual(runner._b70_copy_draft_state.long_k, 0)
            self.assertEqual({w for step in engine.widths[1:] for w in step}, {DEPTH})
            self.assertTrue(any(needle in l for l in self.logger.lines), needle)
        # K_MAX above the reserved slots is capped to them
        self.install(32)
        prompt, truth = repeating_case(11)
        runner = self.cls(num_spec=12)
        engine = Engine(runner, [prompt], [truth]).run(20)
        self.assertEqual(runner._b70_copy_draft_state.long_k, 12)
        self.assertEqual(max(w for step in engine.widths for w in step), 12)
        self.assertTrue(any('capped to num_speculative_tokens=12' in l for l in self.logger.lines))

    def test_k_max_at_or_below_depth_is_off(self):
        for value in ('', '0', '5'):
            self.assertLessEqual(cd.settings_from_env({'B70_COPY_DRAFT_K_MAX': value})['k_max'], DEPTH)
        self.install(5)
        prompt, truth = repeating_case(12)
        runner = self.cls()
        Engine(runner, [prompt], [truth]).run(10)
        self.assertEqual(runner._b70_copy_draft_state.long_k, 0)
        self.assertFalse(any('K_MAX' in l for l in self.logger.lines))


if __name__ == '__main__':
    unittest.main()

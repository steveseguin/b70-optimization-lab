"""CPU check of the copy-draft overlay: the incremental index gives exactly the reference lookup, and the runner glue
replaces whole draft rows (same shape) only for greedy MTP requests whose history it trusts."""
import importlib.util
import random
import time
import types
import unittest
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cd', HERE / 'overlays/b70-copy-draft/b70_copy_draft.py')
cd = importlib.util.module_from_spec(spec); spec.loader.exec_module(cd)

NS = types.SimpleNamespace
K = 5


class LookupTest(unittest.TestCase):
    def test_reference_examples(self):
        ctx = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2, 3, 4, 5, 6]
        self.assertEqual(cd.find_copy_draft(ctx, 5, 6, 8), [7, 8, 9, 10, 11])
        self.assertEqual(cd.find_copy_draft(ctx, 6, 6, 8), [7, 8, 9, 10, 11, 1])   # may run into the suffix
        self.assertIsNone(cd.find_copy_draft(ctx, 12, 6, 8))           # only 11 tokens follow the occurrence
        self.assertIsNone(cd.find_copy_draft(ctx, 5, 7, 8))            # the repeat is only 6 long
        # most recent occurrence wins among equal lengths
        ctx = [9, 1, 2, 3, 4, 5, 6, 70, 71, 72, 73, 74, 8, 1, 2, 3, 4, 5, 6, 80, 81, 82, 83, 84, 1, 2, 3, 4, 5, 6]
        self.assertEqual(cd.find_copy_draft(ctx, 5, 6, 8), [80, 81, 82, 83, 84])
        # a longer match beats a more recent shorter one
        ctx = [7, 9, 1, 2, 3, 4, 5, 6, 70, 71, 72, 73, 74, 8, 1, 2, 3, 4, 5, 6, 80, 81, 82, 83, 84, 9, 1, 2, 3, 4, 5, 6]
        self.assertEqual(cd.find_copy_draft(ctx, 5, 6, 8), [70, 71, 72, 73, 74])
        # periodic text: the occurrence may overlap the suffix, the copied tokens stay inside the context
        self.assertEqual(cd.find_copy_draft([5] * 12, 5, 6, 8), [5] * 5)
        self.assertEqual(cd.find_copy_draft([1, 2] * 8, 5, 6, 8), [1, 2, 1, 2, 1])
        self.assertIsNone(cd.find_copy_draft([1, 2, 3], 5, 6, 8))
        self.assertIsNone(cd.find_copy_draft(list(range(100)), 5, 6, 8))

    def check_against_reference(self, seq, k, lo, hi, rng):
        index = cd.CopyIndex(lo, hi)
        pos = 0
        while pos < len(seq):
            step = rng.choice((1, 1, 1, 2, 3, 6, 17))
            index.extend(seq[pos:pos + step])
            pos = min(len(seq), pos + step)
            self.assertEqual(index.propose(k), cd.find_copy_draft(seq[:pos], k, lo, hi), (seq[:pos], k, lo, hi))

    def test_index_matches_reference_random(self):
        rng = random.Random(0)
        for trial in range(300):
            vocab = rng.choice((2, 3, 4, 8, 50))
            seq = [rng.randrange(vocab) for _ in range(rng.randrange(1, 160))]
            lo = rng.choice((1, 2, 3, 6))
            hi = lo + rng.choice((0, 1, 2, 4))
            self.check_against_reference(seq, rng.choice((1, 3, 5, 8)), lo, hi, rng)

    def test_index_matches_reference_repetitive(self):
        rng = random.Random(1)
        for trial in range(120):
            base = [rng.randrange(1000) for _ in range(rng.randrange(5, 40))]
            seq = []
            while len(seq) < 300:   # copy-heavy text: chunks of earlier text with small edits
                if seq and rng.random() < 0.7:
                    start = rng.randrange(len(seq))
                    seq.extend(seq[start:start + rng.randrange(3, 30)])
                else:
                    seq.extend(base[rng.randrange(len(base)):][:rng.randrange(1, 10)])
                if rng.random() < 0.2:
                    seq.append(rng.randrange(1000))
            self.check_against_reference(seq, 5, 6, 8, rng)
            self.check_against_reference([rng.choice((3, 4)) for _ in range(120)], 5, 6, 8, rng)

    def test_scan_cap_still_returns_a_real_continuation(self):
        rng = random.Random(2)
        seq = [rng.randrange(3) for _ in range(2000)]
        index = cd.CopyIndex(6, 8, max_scan=4, tokens=seq)
        draft = index.propose(5)
        self.assertIsNotNone(draft)
        found = any(seq[s:s + 6] == seq[-6:] and seq[s + 6:s + 11] == draft for s in range(len(seq) - 11 + 1))
        self.assertTrue(found)

    def test_speed_at_33k(self):
        rng = random.Random(3)
        seq = []
        while len(seq) < 33000:
            if seq and rng.random() < 0.5:
                start = rng.randrange(len(seq)); seq.extend(seq[start:start + rng.randrange(5, 60)])
            else:
                seq.extend(rng.randrange(150000) for _ in range(rng.randrange(1, 20)))
        t0 = time.perf_counter()
        index = cd.CopyIndex(6, 8, max_scan=256, tokens=seq[:32000])
        build = time.perf_counter() - t0
        t0 = time.perf_counter()
        for pos in range(32000, 33000, 3):
            index.extend(seq[pos:pos + 3]); index.propose(5)
        per_step = (time.perf_counter() - t0) / 334
        print('\n33K: build %.1f ms, per step (extend 3 + lookup) %.1f us' % (build * 1e3, per_step * 1e6))
        self.assertLess(per_step, 2e-3)


class BookTest(unittest.TestCase):
    def test_async_history_poison_and_attribution(self):
        book = cd.CopyDraftBook(K, 6, 8)
        prompt = list(range(10, 30))
        book.observe_async('a', prompt, [10], first=True)
        self.assertEqual(book.index['a'].tokens, prompt + [10])
        book.observe_async('b', prompt, [10], first=False)           # unknown and not at its prompt end
        self.assertNotIn('b', book.index); self.assertIn('b', book.poisoned)
        book.observe_async('b', prompt, [1, 2], first=True)           # poisoned stays out
        self.assertNotIn('b', book.index)
        book.observe_async('a', prompt, list(range(11, 16)), first=False)
        self.assertEqual(book.choose('a', K), list(range(16, 21)))
        book.observe_async('a', prompt, list(range(16, 22)), first=False)   # 5 accepted + bonus
        self.assertEqual((book.stats['copy_verified'], book.stats['copy_accepted']), (1, 5))
        book.prune({'x'})
        self.assertEqual(book.index, {}); self.assertEqual(book.poisoned, set())

    def test_sync_rebuilds_when_history_changes(self):
        book = cd.CopyDraftBook(K, 6, 8)
        row = np.array(list(range(40)) + [0] * 10)
        book.observe_sync('a', row, 30)
        book.observe_sync('a', row, 33)
        self.assertEqual(book.index['a'].tokens, list(range(33)))
        row[20] = 999; row[32] = 777                                 # last token differs -> rebuild
        book.observe_sync('a', row, 34)
        self.assertEqual(book.index['a'].tokens, row[:34].tolist()); self.assertEqual(book.stats['rebuilds'], 1)
        book.observe_sync('a', row, 10)                                # shorter -> rebuild
        self.assertEqual(len(book.index['a']), 10)
        row[10] = -1
        book.observe_sync('a', row, 12)                                # placeholder -> dropped
        self.assertNotIn('a', book.index)


class Logger:
    def __init__(self):
        self.lines = []

    def warning(self, fmt, *args):
        self.lines.append(fmt % args if args else fmt)

    def exception(self, fmt, *args):
        raise AssertionError('overlay raised: ' + (fmt % args if args else fmt))


def fake_runner_class():
    class Runner:
        def __init__(self, method='mtp', use_async=True):
            self.speculative_config = NS(method=method, disable_padded_drafter_batch=False)
            self.parallel_config = NS(pipeline_parallel_size=1)
            self.enable_prompt_embeds = False
            self.num_spec_tokens = K
            self.use_async_scheduling = use_async
            self.requests = {}
            self.input_batch = NS(req_ids=[], greedy_reqs=set(), req_id_to_index={},
                                  token_ids_cpu=np.zeros((4, 4096), dtype=np.int32),
                                  num_tokens_no_spec=np.zeros(4, dtype=np.int32))
            self.discard_request_mask = NS(np=np.zeros(4, dtype=bool))
            self._draft_token_ids = None
            self._draft_probs = None
            self._draft_token_req_ids = None
            self.execute_model_state = None
            self.fits = True
            self.mtp_value = 99999
            self.seen_drafts = None

        # stand-ins for the stock methods the overlay wraps
        def propose_draft_token_ids(self, scheduler_output, sampled_token_ids, *args, **kwargs):
            return torch.full((sampled_token_ids.shape[0], K), self.mtp_value, dtype=torch.int64)

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
                self._draft_token_ids = torch.zeros(1, dtype=torch.int64).expand(len(self.input_batch.req_ids), K)
            if not self.use_async_scheduling:
                for i, row in enumerate(self.sampled.tolist()):
                    accepted = cd.accepted_prefix(row)
                    n = int(self.input_batch.num_tokens_no_spec[i])
                    self.input_batch.token_ids_cpu[i, n:n + len(accepted)] = accepted
                    self.input_batch.num_tokens_no_spec[i] = n + len(accepted)
            return 'output'
    return Runner


def drive(runner, prompts, truths, steps, greedy=True):
    """Run a fake engine: verify each row's drafts against a fixed true continuation (greedy acceptance)."""
    ids = ['r%d' % i for i in range(len(prompts))]
    batch = runner.input_batch
    batch.req_ids = list(ids)
    batch.req_id_to_index = {r: i for i, r in enumerate(ids)}
    batch.greedy_reqs = set(ids) if greedy else set()
    for i, (r, p) in enumerate(zip(ids, prompts)):
        runner.requests[r] = NS(prompt_token_ids=list(p), num_computed_tokens=0)
        batch.token_ids_cpu[i, :len(p)] = p
        batch.num_tokens_no_spec[i] = len(p)
    emitted = [[] for _ in ids]
    drafts_for_next = None
    accepted_total = 0
    for step in range(steps):
        runner._prepare_input_ids()
        if not runner.use_async_scheduling and step > 0:
            result = runner.take_draft_token_ids_result
            drafts_for_next = result.draft_token_ids
        elif step > 0:
            drafts_for_next = runner.seen_drafts.tolist()
        rows = []
        for i in range(len(ids)):
            if step == 0:
                row = [truths[i][0]]
            else:
                d, pos, a = drafts_for_next[i], len(emitted[i]), 0
                while a < K and d[a] == truths[i][pos + a]:
                    a += 1
                accepted_total += a
                row = truths[i][pos:pos + a + 1]
            rows.append(row + [-1] * (K + 1 - len(row)))
            runner.requests[ids[i]].num_computed_tokens = 0 if step == 0 else len(prompts[i]) + len(emitted[i])
            emitted[i].extend(row)
        runner.sampled = torch.tensor(rows, dtype=torch.int32)
        runner.sched = NS(num_scheduled_tokens={r: (len(prompts[i]) if step == 0 else K + 1)
                                                for i, r in enumerate(ids)},
                          has_structured_output_requests=False)
        runner.execute_model_state = object()
        runner.sample_tokens()
        runner.execute_model_state = None
        if not runner.use_async_scheduling:
            runner.take_draft_token_ids_result = runner.take_draft_token_ids()
    return emitted, accepted_total


def repeating_case(seed, length=300):
    rng = random.Random(seed)
    body = [rng.randrange(1, 50000) for _ in range(120)]
    prompt = body + [rng.randrange(1, 50000) for _ in range(30)]
    truth = (body * 4)[:length]       # the model "repeats" the prompt body
    return prompt, truth


class GlueTest(unittest.TestCase):
    def setUp(self):
        self.settings = cd.settings_from_env({})
        self.cls = fake_runner_class()
        self.logger = Logger()
        cd.install(self.cls, torch, self.logger, self.settings, copier_factory=cd.ImmediateCopier)

    def test_install_once(self):
        before = self.cls.propose_draft_token_ids
        cd.install(self.cls, torch, self.logger, self.settings, copier_factory=cd.ImmediateCopier)
        self.assertIs(self.cls.propose_draft_token_ids, before)

    def run_mode(self, use_async):
        prompts, truths = zip(*(repeating_case(s) for s in (10, 11)))
        runner = self.cls(use_async=use_async)
        emitted, accepted = drive(runner, prompts, truths, 40)
        runner._prepare_input_ids()          # async: the last step's tokens are taken at the next input preparation
        for e, t in zip(emitted, truths):
            self.assertEqual(e, t[:len(e)])                               # verification unchanged: exact output
        state = runner._b70_copy_draft_state
        for i, r in enumerate(('r0', 'r1')):                              # the overlay's history is the true one
            self.assertEqual(state.book.index[r].tokens, list(prompts[i]) + emitted[i])
        self.assertGreater(state.book.stats['copies'], 0)
        self.assertGreater(accepted, 40)                                  # MTP stand-in never accepts anything
        return runner, state

    def test_async_replaces_rows_and_keeps_shape(self):
        runner, state = self.run_mode(True)
        self.assertEqual(tuple(runner._draft_token_ids.shape), (2, K))
        self.assertEqual(runner._draft_token_ids.dtype, torch.int64)
        self.assertTrue(any('first copy draft placed' in line for line in self.logger.lines))

    def test_sync_replaces_lists(self):
        runner, state = self.run_mode(False)
        self.assertEqual(state.mode, 'sync')

    def test_mixed_rows_only_matching_row_replaced(self):
        prompt0, truth0 = repeating_case(20)
        rng = random.Random(21)
        prompt1 = [rng.randrange(1, 50000) for _ in range(150)]
        truth1 = [rng.randrange(1, 50000) for _ in range(300)]
        runner = self.cls(use_async=True)
        drive(runner, [prompt0, prompt1], [truth0, truth1], 12)
        runner._prepare_input_ids()
        drafts = runner.seen_drafts
        self.assertEqual(drafts[1].tolist(), [runner.mtp_value] * K)
        self.assertNotEqual(drafts[0].tolist(), [runner.mtp_value] * K)

    def test_non_mtp_untouched(self):
        prompt, truth = repeating_case(30)
        runner = self.cls(method='ngram_gpu', use_async=True)
        _, accepted = drive(runner, [prompt], [truth], 20)
        self.assertEqual(accepted, 0)
        self.assertIs(runner._b70_copy_draft_state, False)

    def test_non_greedy_untouched(self):
        prompt, truth = repeating_case(31)
        runner = self.cls(use_async=True)
        _, accepted = drive(runner, [prompt], [truth], 20, greedy=False)
        self.assertEqual(accepted, 0)

    def test_draft_probs_or_cpu_copy_consumer_skips(self):
        prompt, truth = repeating_case(32)
        runner = self.cls(use_async=True)
        runner._draft_probs = torch.zeros(1)
        _, accepted = drive(runner, [prompt], [truth], 20)
        self.assertEqual(accepted, 0)
        self.assertGreater(runner._b70_copy_draft_state.book.stats['skipped_steps'], 0)

    def test_skipped_drafter_poisons_history(self):
        prompt, truth = repeating_case(33)
        runner = self.cls(use_async=True)
        drive(runner, [prompt], [truth], 5)
        runner.fits = False                                 # one step where the drafter did not run
        runner.execute_model_state = object(); runner.sample_tokens(); runner.execute_model_state = None
        state = runner._b70_copy_draft_state
        self.assertIn('r0', state.book.poisoned); self.assertNotIn('r0', state.book.index)
        # and the zero drafts of that step are not replaced
        runner._prepare_input_ids()
        self.assertEqual(runner.seen_drafts.tolist(), [[0] * K])


if __name__ == '__main__':
    unittest.main()

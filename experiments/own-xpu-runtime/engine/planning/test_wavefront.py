import heapq
import random
import unittest

from wavefront import Wavefront, ROW, COMMIT, ABORT


def reference(prompt, count, vocab, eos):
    inputs, outputs = list(prompt), []
    for _ in range(count):
        token = (inputs[-1] * 7 + len(inputs) + 3) % vocab
        outputs.append(token)
        if token == eos or len(outputs) == count:
            break
        inputs.append(token)
    return inputs, outputs


def simulate(stages, *, miss=(), seed=0, count=12, eos=96, no_guesses=False):
    prompt, vocab = [3, 5, 8, 11], 97
    expected_inputs, expected_outputs = reference(prompt, count, vocab, eos)
    proposals = {len(prompt) + i: token for i, token in enumerate(expected_outputs)}
    for position in miss:
        if position in proposals:
            proposals[position] = (proposals[position] + 1) % vocab
    model = Wavefront(stages, prompt, count, vocab, eos,
                      lambda p: None if no_guesses else proposals.get(p))
    committed = [[] for _ in range(stages)]
    candidate = [None] * stages
    queue, now, counter, maximum = [], 0.0, 0, 0
    rng = random.Random(seed)
    sent = []
    while not model.done:
        commands = model.commands()
        for command in commands:
            i, row = command.stage, command.row
            sent.append(command)
            if command.op == ROW:
                assert candidate[i] is None and row.position == len(committed[i])
                candidate[i] = (command.sequence, row.position, row.token)
                assert i != stages - 1 or command.speculative == 0
                token = (row.token * 7 + row.position + 1 + 3) % vocab
                stream = None if i == stages - 1 else bytes([row.token, i + 1])
                reply = dict(output_token=token if i == stages - 1 and row.fixture else None,
                             stream=stream)
                delay = 1 + rng.random() * (i + 1) * 2
            else:
                assert candidate[i] == (command.speculative, row.position, row.token)
                if command.op == COMMIT:
                    committed[i].append(row.token)
                else:
                    assert command.op == ABORT
                candidate[i] = None
                reply, delay = {}, 0.05 + rng.random()
            counter += 1
            heapq.heappush(queue, (now + delay, counter, command, reply))
        maximum = max(maximum, len(queue))
        assert queue, 'scheduler deadlocked without device work'
        now, _, command, reply = heapq.heappop(queue)
        model.complete(command, **reply)
        assert counter < 5000
    assert not queue and not any(candidate)
    assert model.emitted == expected_outputs
    assert all(tokens == expected_inputs for tokens in committed)
    return model, sent, maximum


class WavefrontTests(unittest.TestCase):
    def test_geometry_delayed_completions_hits_misses_and_committed_prefix(self):
        for stages in (1, 2, 4, 6):
            for seed in range(8):
                for misses in ((), (4,), (7, 9, 12), tuple(range(4, 16))):
                    with self.subTest(stages=stages, seed=seed, misses=misses):
                        model, commands, peak = simulate(stages, seed=seed, miss=misses)
                        self.assertTrue(model.done)
                        if stages > 1:
                            self.assertGreaterEqual(peak, 2)
                        self.assertFalse(any(c.stage == stages - 1 and c.op == ROW and c.speculative
                                             for c in commands))

    def test_real_rollback_occurs_on_issued_bad_proposal(self):
        model, _, _ = simulate(4, miss=tuple(range(4, 16)))
        self.assertTrue(any(e['event'] == 'abort' for e in model.events))
        self.assertTrue(any(e['event'] == 'proposal-miss' for e in model.events))

    def test_length_cap_and_eos_discard_unverified_work(self):
        for count, eos in ((1, 96), (2, 96), (12, 84)):
            model, commands, _ = simulate(4, count=count, eos=eos)
            self.assertLessEqual(len(model.emitted), count)
            self.assertTrue(model.done)
        # First generated token for this fixture is84: no speculative successor commits.
        model, _, _ = simulate(4, eos=84)
        self.assertEqual(model.emitted, [84])

    def test_missing_proposals_preserve_target_only_results(self):
        model, _, _ = simulate(4, no_guesses=True)
        self.assertFalse(any(e['event'] == 'abort' for e in model.events))

    def test_duplicate_or_forged_reply_rejected(self):
        model = Wavefront(2, [1], 3, 97, 96, lambda p: 9)
        cmd = model.commands()[0]
        model.complete(cmd, stream=b'good')
        with self.assertRaisesRegex(ValueError, 'stale'):
            model.complete(cmd, stream=b'good')

    def test_bad_proposals_and_partial_handoffs_rejected(self):
        model = Wavefront(2, [1], 3, 97, 96, lambda p: 97)
        with self.assertRaisesRegex(ValueError, 'vocabulary'):
            model.commands()
        model = Wavefront(2, [1], 3, 97, 96, lambda p: 2)
        cmd = model.commands()[0]
        with self.assertRaisesRegex(ValueError, 'handoff'):
            model.complete(cmd, stream=bytearray(b'not-owned'))


if __name__ == '__main__':
    unittest.main()

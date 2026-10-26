"""Event-driven CPU workers; native transport and arithmetic are not proved."""
from hashlib import sha256
import random
import unittest

import ring_coordinator as core
from test_ring_coordinator import Worker, reference, target
from rolling_provider.coordinator import RollingCoordinator
from rolling_provider.arbiter import Parent, PROVIDER


def fixture(count, *, maximum=18, eos=(96,), wire=500, provider_stage=0, speculative_depth=2):
    prompt = [3, 5, 8, 11]
    c = RollingCoordinator(stages=count, request=sha256(b'rolling').digest(), epoch=1,
        prompt=prompt, max_new=maximum, vocab=97, eos_token_ids=eos, context=128,
        initial_sequences=[wire]*count, provider_stage=provider_stage, speculative_depth=speculative_depth)
    return c, [Worker(i, count, 1, prompt, wire, speculative_depth) for i in range(count)]


def run(c, workers, *, random_seed=0, miss_first=(), miss_second=(), miss_third=(), fresh_disagreement=False,
        stop_during_provider=False, corrupt_provider=False, stop_at_tick=None, stop_when=None):
    rng = random.Random(random_seed)
    queue = []
    serial = 0
    target_commands_during_provider = 0
    disagreements = []
    stopped = False
    max_pending = 0
    cancel_output_count = None
    cancel_serial_limit = None
    for tick in range(50000):
        if not stopped and (tick == stop_at_tick or stop_when is not None and stop_when(c, queue)):
            cancel_output_count = len(c.emitted)
            cancel_serial_limit = c.provider.serial + int(c.provider.job is not None)
            c.request_stop('cancel')
            stopped = True
        if stop_during_provider and not stopped and c.provider.job is not None and c.provider.job.seed.fixture:
            c.request_stop('cancel')
            stopped = True
        for command in c.commands():
            worker = workers[command.stage]
            if command.op == PROVIDER:
                if stop_during_provider and not stopped and command.row.fixture:
                    c.request_stop('cancel')
                    stopped = True
                assert command.sequence == worker.sequence+1
                worker.sequence = command.sequence
                serial += 1
                job = c.provider_jobs[command.sequence]
                guesses = ()
                if command.row.fixture:
                    p = command.row.position
                    first = (target(command.row.token, p)+int(p in miss_first)) % 97
                    second = (target(first, p+1)+int(p in miss_second)) % 97
                    issued = c.proposals.issued.get(p+1)
                    if fresh_disagreement and issued is not None:
                        first = (issued.proposal.token+1) % 97
                        second = target(first, p+1)
                        disagreements.append((issued.row_id, issued.proposal.token, first))
                    guesses = (first, second)
                    if c.speculative_depth == 3:
                        guesses += ((target(second, p+2)+int(p in miss_third)) % 97,)
                result = dict(provider_serial=serial+int(corrupt_provider), restored_position=command.row.position,
                    physical=job.target_physical, committed=job.target_committed,
                    pending_rows=job.pending_rows, guesses=guesses)
                queue.append((command, result, None))
            else:
                if c.provider.job is not None and command.stage:
                    target_commands_during_provider += 1
                ack = worker.execute(command)
                parent = None
                if command.stage == len(workers)-1 and command.op == core.ACCEPT:
                    parent = Parent(command.row, command.row_ticket, command.sequence,
                        sha256(repr(command.row).encode()).digest(), sha256(repr(command).encode()).digest())
                queue.append((command, ack, parent))
        max_pending = max(max_pending, max(len(s.pending) for s in c.stages))
        if queue:
            # Native work finishes before reply delivery; cross-owner replies
            # are deliberately reordered, including op27 behind target owners.
            command, result, parent = queue.pop(rng.randrange(len(queue)))
            if command.op == PROVIDER:
                c.complete_provider(command, **result)
            else:
                c.complete(command, result, final_parent=parent)
        elif not c.done and c.phase is None:
            raise AssertionError('rolling deadlock: '+repr([(s.physical,s.committed,s.busy,len(s.pending)) for s in c.stages])
                +' provider='+repr((c.provider.next_seed,c.provider.local_seed,c.provider.parent,c.provider.job)))
        if c.done:
            if cancel_output_count is not None:
                assert len(c.emitted) == cancel_output_count
                assert c.provider.serial <= cancel_serial_limit
            assert not queue and c.provider.reset_allowed()
            return dict(overlap=target_commands_during_provider, disagreements=disagreements,
                max_pending=max_pending, stopped=stopped, ticks=tick+1)
    raise AssertionError('bounded rolling CPU completion')


class RollingTests(unittest.TestCase):
    def test_reordered_two_four_six_exact_outputs_both_miss_depths(self):
        for count in (2,4,6):
            for seed in range(8):
                with self.subTest(count=count,seed=seed):
                    c, workers = fixture(count)
                    result = run(c,workers,random_seed=seed,miss_first=(4,9),miss_second=(6,11))
                    inputs, outputs = reference(list(c.prompt),c.max_new,c.eos)
                    self.assertEqual(c.emitted,outputs)
                    self.assertEqual(c.provider.serial,len(inputs)-1)
                    for worker in workers:
                        self.assertEqual(worker.ring.physical['history'],inputs)
                    self.assertTrue(any(e['event']=='abort-ack' for e in c.events))
                    self.assertLessEqual(result['max_pending'],2)
                    self.assertFalse(any(w.streams for w in c.rows.values()))
                    with self.assertRaisesRegex(ValueError,'no native RESET'):
                        c.reset(request=sha256(b'next').digest(),epoch=2,prompt=[1],max_new=2)

    def test_existing_recursive_row_not_rewritten_by_new_canonical_guess(self):
        observed = []
        for count in (2,4,6):
            c, workers = fixture(count)
            result = run(c,workers,random_seed=17,fresh_disagreement=True)
            _, outputs = reference(list(c.prompt),c.max_new,c.eos)
            self.assertEqual(c.emitted,outputs)
            for row_id, old, fresh in result['disagreements']:
                created = next(e for e in c.events if e['event']=='row-created' and e['row']==row_id)
                self.assertEqual(created['token'],old)
                self.assertNotEqual(old,fresh)
            observed += result['disagreements']
        self.assertTrue(observed)

    def test_eos_and_cancel_during_provider_drain_without_phantom_lease(self):
        _, outputs = reference([3,5,8,11],8,())
        for count in (2,4,6):
            c, workers = fixture(count,eos=(outputs[2],))
            run(c,workers,random_seed=4,miss_first=(3,))
            self.assertEqual(c.emitted,outputs[:3])
            self.assertEqual(c.stop_reason,'eos')
            c, workers = fixture(count)
            result = run(c,workers,random_seed=9,stop_during_provider=True)
            self.assertTrue(result['stopped'])
            self.assertEqual(c.stop_reason,'cancel')
            self.assertFalse(c.provider_jobs)
            self.assertTrue(all(s.physical==s.committed and not s.pending for s in c.stages))

    def test_cancel_at_every_reply_boundary_and_unreserved_parent_windows(self):
        for count in (2,4,6):
            baseline,workers=fixture(count,maximum=7)
            total=run(baseline,workers,random_seed=6,miss_first=(4,),miss_second=(3,))['ticks']
            for tick in range(total):
                with self.subTest(count=count,tick=tick):
                    c,workers=fixture(count,maximum=7)
                    result=run(c,workers,random_seed=6,miss_first=(4,),miss_second=(3,),stop_at_tick=tick)
                    self.assertTrue(result['stopped'])
                    self.assertFalse(c.provider_jobs)
                    self.assertTrue(all(not s.pending and s.physical==s.committed for s in c.stages))
            for phase in ('local-row','local-accept','miss'):
                observed=False
                for random_seed in range(12):
                    c,workers=fixture(count,maximum=12)
                    def window(model,queue):
                        if model.provider.parent is None or model.provider.job is not None:return False
                        if phase=='miss':return model.phase in ('drain','abort') and model.provider.local_seed is None
                        busy=model.stages[0].busy
                        return busy is not None and busy.op==(core.ROW if phase=='local-row' else core.ACCEPT)
                    result=run(c,workers,random_seed=random_seed,miss_first=(3,5,7),stop_when=window)
                    if result['stopped']:
                        observed=True
                        self.assertTrue(c.cancelled_provider_incomplete)
                        break
                self.assertTrue(observed,(count,phase))

    def test_bad_provider_identity_latches_failure(self):
        c,workers=fixture(4)
        with self.assertRaisesRegex(ValueError,'provider wire/serial'):
            run(c,workers,corrupt_provider=True)
        self.assertIsNotNone(c.failed)
        with self.assertRaisesRegex(ValueError,'sticky failure'):
            c.commands()


if __name__ == '__main__': unittest.main()

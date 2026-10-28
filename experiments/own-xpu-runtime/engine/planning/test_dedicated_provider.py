"""CPU separate-owner scheduling with existing target worker fixtures."""
from hashlib import sha256
import random
import unittest
import ring_coordinator as core
from test_ring_coordinator import Worker, reference, target
from rolling_provider.arbiter import Parent
from rolling_provider.dedicated import DedicatedCoordinator, ProviderCommand


def run(count,depth=3,misses=False,cancel=False,corrupt=False,capture=True,eos=(96,)):
    prompt=[3,5,8,11]
    c=DedicatedCoordinator(stages=count,request=sha256(b'dedicated').digest(),epoch=1,
        prompt=prompt,max_new=18,vocab=97,eos_token_ids=eos,context=128,
        initial_sequences=[500]*count,provider_sequence=900,speculative_depth=depth)
    workers=[Worker(i,count,1,prompt,500,depth) for i in range(count)]
    queue=[];rng=random.Random(count+depth);overlap=0;stopped=False
    for tick in range(10000):
        for command in c.commands():
            if isinstance(command,ProviderCommand):
                assert not hasattr(command,'stage')
                job=c.provider_jobs[command.sequence]
                self_target_sequences=tuple(s.sequence for s in c.stages)
                assert all(s.busy is not command for s in c.stages)
                if capture:c.capture_provider(command)
                assert tuple(s.sequence for s in c.stages)==self_target_sequences
                guesses=()
                if command.row.fixture:
                    p=command.row.position;t=target(command.row.token,p)
                    if misses and p%3==0:t=(t+1)%97
                    values=[t]
                    for offset in range(1,depth):values.append(target(values[-1],p+offset))
                    guesses=tuple(values)
                queue.append((command,dict(provider_serial=job.serial+int(corrupt),restored_position=job.seed.position,guesses=guesses),None))
                if cancel and not stopped and command.row.fixture:
                    c.request_stop('cancel');stopped=True
            else:
                if c.provider_busy is not None:overlap+=1
                ack=workers[command.stage].execute(command);parent=None
                if command.op==core.ACCEPT and command.stage==count-1:
                    parent=Parent(command.row,command.row_ticket,command.sequence,sha256(repr(command.row).encode()).digest(),sha256(repr(command).encode()).digest())
                queue.append((command,ack,parent))
        if queue:
            command,result,parent=queue.pop(rng.randrange(len(queue)))
            if isinstance(command,ProviderCommand):c.complete_provider(command,**result)
            else:c.complete(command,result,final_parent=parent)
        elif not c.done:raise AssertionError('dedicated deadlock')
        if c.done:
            assert not queue and c.provider_busy is None and c.provider.reset_allowed()
            assert all(s.busy is None and not s.pending for s in c.stages)
            if not cancel:
                expected_inputs=reference(prompt,18,eos)[0]
                for worker in workers:
                    assert worker.ring.committed==c.frontier
                    assert worker.ring.physical['history']==expected_inputs
                    assert worker.ring.physical['position']==c.frontier
            return c,overlap
    raise AssertionError('bounded completion')


class DedicatedTests(unittest.TestCase):
    def test_hits_misses_two_three_targets(self):
        for count in (2,3):
            for depth in (2,3):
                for misses in (False,True):
                    c,overlap=run(count,depth,misses)
                    self.assertEqual(c.emitted,reference([3,5,8,11],18,(96,))[1])
                    self.assertGreaterEqual(overlap,0)
                    self.assertEqual(len(c.stages),count)
                    self.assertTrue(all(s.sequence<900 for s in c.stages))
                    self.assertGreater(c.provider_sequence,900)
                    self.assertEqual(c.provider.serial,c.frontier-1)

    def test_cancel_during_provider(self):
        for count in (2,3):
            c,_=run(count,cancel=True)
            self.assertEqual(c.stop_reason,'cancel')

    def test_bad_provider_frontier(self):
        with self.assertRaisesRegex(ValueError,'canonical provider frontier'):run(3,corrupt=True)

    def test_capture_required(self):
        with self.assertRaisesRegex(ValueError,'captured provider job'):run(3,capture=False)

    def test_eos_drains(self):
        for count in (2,3):
            c,_=run(count,eos=(84,))
            self.assertEqual(c.emitted,[84])

    def test_invalid_role_and_counter(self):
        kwargs=dict(stages=3,request=sha256(b'x').digest(),epoch=1,prompt=[3,5],max_new=4,vocab=97,eos_token_ids=(96,),context=32)
        for extra in ({'provider_stage':0},{'provider_sequence':-1},{'provider_sequence':True}):
            with self.assertRaises(ValueError):DedicatedCoordinator(**kwargs,**extra)


if __name__=='__main__':unittest.main()

"""Depth-three scheduling: target truth, suffix rollback, and cancellation."""
from hashlib import sha256
import unittest
import test_ring_coordinator as base
import test_rolling_provider as rolling
from ring_contract import Proposals

class DepthThreeTests(unittest.TestCase):
    check_exact = base.RingCoordinatorTests.check_exact
    def test_depth_three_reordered_rollback_and_reset(self):
        peak_slots=peak_live=largest_abort=0
        for count in (2,4,6):
            for misses in ((),(4,),(5,),(6,),(4,7,10)):
                for seed in range(4):
                    c,w=base.fixture(count,base.Publisher(misses),speculative_depth=3)
                    info=base.run(c,w,seed)
                    self.check_exact(c,w,[3,5,8,11],12,(96,))
                    peak_slots=max(peak_slots,info['peak_slots'])
                    peak_live=max(peak_live,info['peak_global'])
                    largest_abort=max([largest_abort]+[len(e['discarded']) for e in c.events if e['event']=='abort-ack'])
                    self.assertLessEqual(info['peak_slots'],3)
                    self.assertLessEqual(info['peak_global'],4)
                    c.reset(request=sha256(b'next-depth3').digest(),epoch=2,prompt=[2,7],max_new=9)
                    base.run(c,w,seed+11)
                    self.check_exact(c,w,[2,7],9,(96,))
                    self.assertEqual(c.speculative_depth,3)
        self.assertEqual((peak_slots,peak_live,largest_abort),(3,4,3))

    def test_depth_three_rolling_all_misses_and_cancel(self):
        peak=0
        for count in (2,4,6):
            for provider in (0,count-2):
                for seed in range(4):
                    c,w=rolling.fixture(count,provider_stage=provider,speculative_depth=3)
                    result=rolling.run(c,w,random_seed=seed,miss_first=(4,9),miss_second=(6,11),miss_third=(5,10))
                    inputs,outputs=base.reference(list(c.prompt),c.max_new,c.eos)
                    self.assertEqual(c.emitted,outputs)
                    self.assertTrue(all(x.ring.physical['history']==inputs for x in w))
                    self.assertLessEqual(result['max_pending'],3)
                    peak=max(peak,result['max_pending'])
                c,w=rolling.fixture(count,maximum=7,provider_stage=provider,speculative_depth=3)
                ticks=rolling.run(c,w,random_seed=6,miss_first=(4,),miss_third=(3,))['ticks']
                for tick in range(ticks):
                    c,w=rolling.fixture(count,maximum=7,provider_stage=provider,speculative_depth=3)
                    result=rolling.run(c,w,random_seed=6,miss_first=(4,),miss_third=(3,),stop_at_tick=tick)
                    self.assertTrue(result['stopped'])
                    self.assertFalse(c.provider_jobs)
                    self.assertTrue(all(not s.pending and s.physical==s.committed for s in c.stages))
        self.assertEqual(peak,3)

    def test_depth_must_be_supported_integer(self):
        for depth in (True,1,4,3.0,None):
            with self.assertRaisesRegex(ValueError,'supported speculative depth'):
                base.fixture(speculative_depth=depth)
            with self.assertRaisesRegex(ValueError,'supported speculative depth'):
                Proposals(request=bytes(32),epoch=1,prompt=[1],vocab=97,speculative_depth=depth)

if __name__=='__main__':unittest.main()

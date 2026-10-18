"""CPU boundary tests of the real storage arithmetic; no allocated test gigabytes."""
import unittest
from unittest.mock import patch
import storage as s
import window as w

class Budget(unittest.TestCase):
    def test_reported_failure_now_fits_structurally(self):
        row=s.budget(31_558_537_216,1_552_906_002,2_500_000_000,2_500_000_000)
        self.assertLess(row['build_bytes']+row['projected_build_write_bytes'],row['build_limit_bytes'])

    def test_old_cap_reproduces_failure(self):
        with patch.object(s,'BUILD_LIMIT',3_000_000_000):
            with self.assertRaises(RuntimeError):s.budget(31_558_537_216,1_552_906_002,2_500_000_000,2_500_000_000)

    def test_cap_boundary(self):
        free=100_000_000_000
        s.budget(free,s.BUILD_LIMIT-2,1,1)
        with self.assertRaises(RuntimeError):s.budget(free,s.BUILD_LIMIT-1,1,1)

    def test_headroom_bounds_cap(self):
        free=s.FREE_FLOOR+s.CHAIN_RESERVE+1_000_000_000
        row=s.budget(free,1_000_000_000,999_999_999,999_999_999)
        self.assertEqual(row['build_limit_bytes'],2_000_000_000)
        with self.assertRaises(RuntimeError):s.budget(free,1_000_000_000,1_000_000_000,1_000_000_000)

    def test_free_floor_and_remaining_chain(self):
        for free in (s.FREE_FLOOR-1,s.FREE_FLOOR,s.FREE_FLOOR+s.CHAIN_RESERVE-1):
            with self.subTest(free=free),self.assertRaises(RuntimeError):s.budget(free,0,1,0)

    def test_outside_build_still_reserves_disk(self):
        with patch.object(w,'admit') as admit:
            w.admit_output(w.P/'receipts-new/K2',2_500_000_000)
        admit.assert_called_once_with(2_500_000_000,build_extra=0)
        with self.assertRaises(RuntimeError):s.budget(s.FREE_FLOOR+s.CHAIN_RESERVE+10,0,11,0)

    def test_context_retention_and_request_growth(self):
        for c in (256,4096,32768):
            self.assertGreaterEqual(s.projected_write_bytes('W2m',context=c),s.state_write_bytes(c))
            self.assertGreater(s.projected_write_bytes('WS128x',13,c,16),s.projected_write_bytes('WS',13,c,8))
            self.assertGreater(s.projected_write_bytes('WS',25,c,8),s.projected_write_bytes('WS',13,c,8))
            self.assertGreaterEqual(s.projected_write_bytes('KD',context=c),3*2368*c)

    def test_rehearsal_cannot_substitute_64mb(self):
        from types import SimpleNamespace
        args=SimpleNamespace(window='K2',card=0,context=32768,cpu_rehearsal=True)
        df=SimpleNamespace(stdout='Filesystem Size Used Avail\nx 1 1 31558537216\n')
        # Real CPU fixture entry must refuse under the old cap before even ldd,
        # rather than silently substituting a miniature reserve and launching.
        with patch.object(s,'BUILD_LIMIT',3_000_000_000), \
             patch.object(s,'build_size',return_value=1_552_906_002), \
             patch.object(s.subprocess,'run',return_value=df), \
             patch.object(w,'ldd_preflight') as loader, \
             patch.object(w.subprocess,'Popen') as launch:
            with self.assertRaises(RuntimeError):w.run_fixtures(args,w.B/'budget-test-new',{},None)
            loader.assert_not_called();launch.assert_not_called()

    def test_invalid_counts_fail_closed(self):
        for value in (-1,1.5,True):
            with self.assertRaises(ValueError):s.budget(100_000_000_000,0,value,0)
        with self.assertRaises(ValueError):s.state_write_bytes(8192)
        with self.assertRaises(ValueError):s.projected_write_bytes('WS',0)

if __name__=='__main__':unittest.main()

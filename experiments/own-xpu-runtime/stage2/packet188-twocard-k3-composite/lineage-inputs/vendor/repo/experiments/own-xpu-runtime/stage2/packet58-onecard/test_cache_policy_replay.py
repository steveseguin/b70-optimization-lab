import unittest
from unittest.mock import patch
from cache_policy_replay import GlobalArena
import cache_policy_replay as R

class ReplayTests(unittest.TestCase):
    def test_lru_and_complete_route_touch(self):
        with patch.object(R.L,'packed',return_value=256):
            c=GlobalArena(512)
            self.assertEqual(c.route(0,[1,2]),2)
            self.assertEqual(c.route(0,[3,2]),1)
            self.assertEqual(set(c.entries),{2,3})
            self.assertEqual(c.route(0,[3,2]),0)
    def test_extent_fragmentation_can_evict_multiple(self):
        with patch.object(R.L,'packed',side_effect=lambda layer:512 if layer==2 else 256):
            c=GlobalArena(768);c.route(0,[1,2,3]);c.route(0,[2])
            self.assertEqual(c.route(2,[0]),1)
            # Oldest1 then3 free separated holes, so need also2 to create512.
            self.assertEqual(c.evictions,3)
            self.assertEqual(sum(x[1] for x in c.entries.values())+sum(n for _,n in c.free),768)
    def test_capacity_too_small_retains_host_miss(self):
        with patch.object(R.L,'packed',return_value=512):
            c=GlobalArena(256)
            self.assertEqual(c.route(0,[1]),1)
            self.assertFalse(c.entries)
            self.assertEqual(c.free,[(0,256)])
    def test_alignment_and_no_hidden_growth(self):
        with patch.object(R.L,'packed',return_value=257):
            c=GlobalArena(1024)
            for i in range(100):c.route(0,[i])
            self.assertEqual(sum(x[1] for x in c.entries.values()),1024)
            self.assertEqual(len(c.entries),2)
            self.assertLessEqual(len(c.heap),32)
if __name__=='__main__':unittest.main()

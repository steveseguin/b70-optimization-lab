import unittest
from attribute import adjacent_gaps

def event(n,start,end,rank=1):
    return dict(event=n,start_ns=start,end_ns=end,rank=rank)

class AttributionTest(unittest.TestCase):
    def test_only_adjacent_events(self):
        self.assertEqual(adjacent_gaps([event(1,1000,2000),event(2,2100,3000),event(5,9000,10000)]),[.1])

    def test_never_cross_device(self):
        with self.assertRaises(AssertionError):
            adjacent_gaps([event(1,1000,2000),event(2,2100,3000,0)])

    def test_invalid_copy_clock_refused(self):
        with self.assertRaises(AssertionError):
            adjacent_gaps([event(1,1000,2000),event(2,20,20)])

if __name__=='__main__':unittest.main()

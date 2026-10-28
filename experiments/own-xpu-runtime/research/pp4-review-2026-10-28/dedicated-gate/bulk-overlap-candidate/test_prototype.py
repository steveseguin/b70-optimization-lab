import threading
import unittest
from prototype import run,compute_only_bound

class Tests(unittest.TestCase):
    def test_opposite_parity_overlap_partial_tail_and_ack_before_reuse(self):
        slots={};busy=set();acks=[];events=[];started=threading.Event();next_target=threading.Event()
        def target(spec):
            start,count,parity=spec
            if start==256:self.assertTrue(started.wait(1))
            self.assertNotIn(parity,busy);slots[parity]=(start,count);events.append(('target',start))
            if start==256:next_target.set()
            return start,count,parity,slots[parity]
        def replay(job):
            start,count,parity,snapshot=job;busy.add(parity)
            if start==0:started.set();self.assertTrue(next_target.wait(1))
            self.assertEqual(slots[parity],snapshot);events.append(('ack',start));busy.remove(parity)
            return start+count
        run(((0,256,0),(256,256,1),(512,139,0)),target,replay,lambda _,a:acks.append(a),lambda e:self.fail(str(e)))
        self.assertEqual(acks,[256,512,651]);self.assertLess(events.index(('target',256)),events.index(('ack',0)));self.assertLess(events.index(('ack',0)),events.index(('target',512)));self.assertFalse(busy)
    def test_provider_failure_stops_before_parity_reuse(self):
        called=[];failures=[]
        def replay(_):raise ValueError('bad ACK')
        with self.assertRaisesRegex(ValueError,'bad ACK'):run(range(3),lambda n:called.append(n) or n,replay,lambda *_:self.fail('bad ACK record'),failures.append)
        self.assertEqual(called,[0,1]);self.assertEqual(len(failures),1)
    def test_target_failure_joins_provider_before_return(self):
        done=threading.Event();stop=threading.Event();calls=[]
        def target(n):
            calls.append(n)
            if n==1:raise ValueError('target fault')
            return n
        def replay(n):self.assertTrue(stop.wait(1));done.set();return n
        with self.assertRaisesRegex(ValueError,'target fault'):run(range(3),target,replay,lambda *_:None,lambda _:stop.set())
        self.assertTrue(done.is_set());self.assertEqual(calls,[0,1])
    def test_component_bound(self):
        d=compute_only_bound([3,3,2],[2,2,1]);self.assertEqual((d['serial_component_seconds'],d['overlap_component_seconds'],d['optimistic_saved_seconds']),(13,9,4))
if __name__=='__main__':unittest.main()

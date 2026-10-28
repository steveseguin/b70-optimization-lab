"""CPU-only candidate tests. Do not run while root has a measured request active.
Existing adversarial schedulers run with every live-count decision checked against
its original full-history oracle. Equal decisions preserve command/event order;
original suites assert actual truth, ACK ordering, stop and reset behavior.
"""
import importlib.util
import pathlib
import sys
import unittest
from hashlib import sha256
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'engine/planning'))
import ring_coordinator as core
from rolling_provider.coordinator import RollingCoordinator
from rolling_provider.dedicated import DedicatedCoordinator
spec=importlib.util.spec_from_file_location('bounded_candidate',HERE/'ring_coordinator.py')
candidate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=candidate;spec.loader.exec_module(candidate)
original=core.Coordinator._live_count
bounded=candidate.Coordinator._live_count
calls=0

def audited(self):
    global calls
    old=original(self);new=bounded(self)
    assert old==new,(old,new,self.frontier,[(s.committed,s.physical) for s in self.stages])
    calls+=1
    return new

class BoundedCountTests(unittest.TestCase):
    def test_existing_adversarial_suites_differential(self):
        names=['test_ring_coordinator','test_rolling_provider','test_rolling_provider_arbiter',
               'test_dedicated_provider','test_dedicated_capture','test_dedicated_bulk_seam']
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in names)
        with patch.object(core.Coordinator,'_live_count',audited):
            result=unittest.TestResult();suite.run(result)
        self.assertEqual([],result.errors,str(result.errors))
        self.assertEqual([],result.failures,str(result.failures))
        self.assertGreater(result.testsRun,20)
        self.assertGreater(calls,100)
        print('existing differential tests',result.testsRun,'live_count decisions',calls)

    def test_actual_121k_prefix_history_preserved_and_not_scanned(self):
        # Declared CPU fixture, no authentication/native proof. Real shared
        # adoption creates accepted historical Work; only count implementation
        # changes. Distinct prompt token values keep prefix hashes nontrivial.
        prompt=[(i*17+3)%97 for i in range(121854)]
        c=DedicatedCoordinator(stages=2,request=sha256(b'bounded121k').digest(),epoch=0,
           prompt=prompt,max_new=32,context=131072,vocab=97,eos_token_ids=[96],
           speculative_depth=3)
        RollingCoordinator.adopt_prefill(c,len(prompt)-2)
        self.assertEqual(original(c),bounded(c))
        before=tuple((p,w.row,w.verified,frozenset(w.accepted)) for p,w in c.rows.items())
        class NoScan(dict):
            reads=0
            def values(self):raise AssertionError('historical values scan')
            def items(self):raise AssertionError('historical items scan')
            def __iter__(self):raise AssertionError('historical key scan')
            def get(self,*args):self.reads+=1;return super().get(*args)
        c.rows=NoScan(c.rows)
        with patch.object(core.Coordinator,'_live_count',bounded):
            commands=c.commands()
        self.assertEqual(len(commands),1)
        self.assertEqual(commands[0].row.position,121852)
        self.assertEqual(commands[0].row.parent,121852)
        self.assertEqual(len(c.rows),121854)
        self.assertLess(c.rows.reads,100)
        # All original historical rows and acceptance sets remain byte-for-byte
        # identical; two actual seam rows are newly created.
        self.assertEqual(before,tuple((p,c.rows[p].row,c.rows[p].verified,
                         frozenset(c.rows[p].accepted)) for p in range(121852)))
        oracle=sum(not w.cancelled and len(w.accepted)<len(c.stages) for w in dict.values(c.rows))
        self.assertEqual(oracle,bounded(c))

    def test_frontier_lag_partial_accept_cancelled_and_missing_positions(self):
        # Actual admitted ledger from first commands, then bounded count oracle
        # at different acceptance frontiers. Cancellation must not count a row.
        c=core.Coordinator(stages=3,request=sha256(b'partial').digest(),epoch=0,
          prompt=[3,5,7,9],max_new=4,context=128,vocab=97,eos_token_ids=[96],speculative_depth=3)
        c.commands()
        for work in c.rows.values():
            for accepted in [set(),{0},{0,1},{0,1,2}]:
                work.accepted=accepted
                self.assertEqual(original(c),bounded(c))
            work.cancelled=True
            self.assertEqual(original(c),bounded(c))

if __name__=='__main__':unittest.main()

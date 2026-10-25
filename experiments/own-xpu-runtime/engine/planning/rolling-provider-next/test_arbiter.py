from dataclasses import replace
from hashlib import sha256
import unittest

from ring_coordinator import Command,Row,ROW
from ring_contract import append_prefix,Proposals,ProposalBatch
from arbiter import Arbiter,Parent,PROVIDER


def row(position,token,parent=None,fixture=1):
    request=sha256(b'request').digest();before=parent.after if parent else sha256(b'root').digest()
    return Row(0,position+1,position,position,token,fixture,request,before,append_prefix(before,position,token))

class ArbiterTests(unittest.TestCase):
    def test_early_eos_leaves_no_phantom_provider_lease(self):
        parent=row(0,7)
        a=Arbiter(stages=4,request=parent.request,epoch=0,last_input_position=20,vocab=97)
        a.local_accepted(parent)
        a.final_committed(Parent(parent,71,72,sha256(b'hidden').digest(),sha256(b'event').digest()),terminal=True)
        self.assertIsNone(a.parent)
        self.assertTrue(a.reset_allowed()) # external target suffix drain still required
        self.assertFalse(a.row_allowed(0,1,tentative=True))
        self.assertFalse(a.row_allowed(3,1,tentative=False))
        self.assertFalse(a.accept_allowed(0,1))

    def fixture(self,count):
        parent=row(0,7);seed=row(1,11,parent)
        a=Arbiter(stages=count,request=seed.request,epoch=0,last_input_position=20,vocab=97)
        a.local_accepted(parent);a.local_accepted(seed)
        event=Parent(parent,71,72,sha256(b'hidden').digest(),sha256(b'event').digest())
        a.final_committed(event)
        return a,seed
    def test_borrow_two_pending_and_other_owners_continue_two_four_six(self):
        for count in (2,4,6):
            a,seed=self.fixture(count);first=row(2,13,seed);second=row(3,17,first)
            pending=[Command(0,ROW,499,first,True),Command(0,ROW,500,second,True)]
            sequence=500;busy=None
            def reserve(op,r):
                nonlocal sequence,busy
                self.assertIsNone(busy);sequence+=1;busy=Command(0,op,sequence,r);return busy
            def release(command):
                nonlocal busy
                self.assertIs(busy,command);busy=None
            job=a.reserve(reserve,stage_busy=False,pending=pending,physical=4,committed=2)
            self.assertEqual(job.command.sequence,501)
            self.assertFalse(a.row_allowed(0,4,tentative=True))
            self.assertFalse(a.row_allowed(count-1,1,tentative=False))
            for stage in range(1,count-1):self.assertTrue(a.row_allowed(stage,2,tentative=True))
            batch=a.complete(job,command_sequence=501,provider_serial=1,restored_position=1,
                physical=4,committed=2,pending_rows=[3,4],guesses=(19,23),release_auxiliary=release)
            self.assertEqual((batch.seed_length,batch.restored_position,batch.tokens),(2,1,(19,23)))
            self.assertIsNone(busy);self.assertEqual(a.serial,1)
            self.assertTrue(a.row_allowed(count-1,1,tentative=False))
    def test_local_verified_frontier_cannot_overshoot_next_seed(self):
        a,seed=self.fixture(4)
        self.assertFalse(a.row_allowed(0,2,tentative=False));self.assertTrue(a.row_allowed(0,2,tentative=True))
        self.assertFalse(a.accept_allowed(0,2));self.assertTrue(a.accept_allowed(1,2))
        with self.assertRaises(ValueError):a.local_accepted(row(2,13,seed))
    def test_parent_lease_is_not_busy_and_does_not_block_miss_abort(self):
        a,seed=self.fixture(4)
        self.assertIsNone(a.job)
        # The adapter gates only final ROW admission; target drain/ABORT remains
        # the core's responsibility and does not wait on this retained record.
        self.assertFalse(a.row_allowed(3,1,tentative=False))
        self.assertFalse(a.can_reserve(stage_busy=False,pending=[],physical=2,committed=2,phase='abort'))
        self.assertFalse(a.reset_allowed())
        with self.assertRaises(ValueError):a.final_committed(a.parent)
    def test_wrong_reply_or_target_rewind_poison_and_no_new_work(self):
        for mutation in ('serial','physical','pending'):
            a,seed=self.fixture(4);job=a.reserve(lambda op,r:Command(0,op,501,r),stage_busy=False,pending=[],physical=2,committed=2)
            fields=dict(command_sequence=501,provider_serial=1,restored_position=1,physical=2,committed=2,pending_rows=[],guesses=(13,17),release_auxiliary=lambda c:None)
            fields[{'serial':'provider_serial','physical':'physical','pending':'pending_rows'}[mutation]]={'serial':2,'physical':1,'pending':[99]}[mutation]
            with self.assertRaises(ValueError):a.complete(job,**fields)
            self.assertFalse(a.row_allowed(1,2,tentative=False));self.assertFalse(a.reset_allowed())
    def test_new_actual_canonical_d1_does_not_replace_issued_recursive_d2(self):
        request=sha256(b'fixture').digest();p=Proposals(request=request,epoch=0,prompt=[3,5],vocab=97)
        p.register_verified_row(1,2,p.hashes[-1])
        p.publish(ProposalBatch(request,0,501,2,p.hashes[-1],(7,9),1,True))
        first=p.choose(2,p.hashes[-1]);p.issue(3,2,first)
        second=p.choose(3,first.after_digest);p.issue(4,3,second)
        p.verify(7,commit_ticket=801)
        p.publish(ProposalBatch(request,0,504,3,p.hashes[-1],(8,10),2,True))
        self.assertEqual(p.choose(3,p.hashes[-1]).token,9)
        self.assertEqual(p.issued[3].row_id,4)

if __name__=='__main__':unittest.main()

"""Adversarial event order over deterministic CPU workers; no GPU/performance proof."""
from dataclasses import replace
from hashlib import sha256
import random
import struct
import unittest

from ring_coordinator import Coordinator, Ack, ROW, ACCEPT, ABORT_SUFFIX, RESET
from ring_contract import ProposalBatch
from wavefront_ring import Ring, Ticket


def target(token,position):return (token*7+position+4)%97


def reference(prompt,maximum,eos):
    inputs=list(prompt);outputs=[]
    for _ in range(maximum):
        token=target(inputs[-1],len(inputs)-1);outputs.append(token)
        if token in eos or len(outputs)==maximum:break
        inputs.append(token)
    return inputs,outputs


class Publisher:
    def __init__(self,misses=(),fresh_disagree=False):
        self.misses=set(misses);self.seen=set();self.ticket=0;self.fresh_disagree=fresh_disagree
        self.disagreements=[]
    def __call__(self,c):
        length=len(c.proposals.verified);key=(c.epoch,length,c.proposals.hashes[-1])
        if key in self.seen:return []
        self.seen.add(key);self.ticket+=1
        first=(target(c.proposals.verified[-1],length-1)+int(length in self.misses))%97
        second=(target(first,length)+int(length+1 in self.misses))%97
        if self.fresh_disagree and length in c.proposals.issued:
            issued=c.proposals.issued[length]
            first=(issued.proposal.token+1)%97;second=target(first,length)
            self.disagreements.append((issued.row_id,issued.proposal.token,first))
        return [ProposalBatch(c.request,c.epoch,self.ticket,length,c.proposals.hashes[length],(first,second),length-1,True)]


class Worker:
    def __init__(self,index,count,epoch,prompt,sequence=0):
        self.index,self.count,self.epoch,self.prompt,self.sequence=index,count,epoch,list(prompt),sequence
        self.ring=Ring(first=index==0,final=index==count-1,context=128,vocab=97)
        self.tickets={};self.outputs={};self.accept_positions=[];self.reset_count=0
    def execute(self,command):
        assert command.stage==self.index and command.sequence==self.sequence+1
        self.sequence=command.sequence
        if command.op==RESET:
            assert not self.ring.pending and self.ring.physical['position']==self.ring.committed
            self.epoch=command.reset.epoch;self.prompt=list(command.reset.prompt)
            self.ring=Ring(first=self.index==0,final=self.index==self.count-1,context=128,vocab=97)
            self.tickets={};self.outputs={};self.reset_count+=1
            return Ack(self.epoch,self.index,self.sequence,0,0,0,0,0)
        row=command.row
        assert row.epoch==self.epoch
        ticket=Ticket(row.identity,row.parent,self.ring.generation,row.position,row.token,command.tentative)
        token=None;stream=None;discarded=()
        if command.op==ROW:
            if self.index:
                pub=command.source
                assert pub.row==row and pub.stage==self.index-1 and sha256(pub.data).digest()==pub.digest
                assert struct.unpack('<4i',pub.data)==(row.token,row.position,self.index-1,row.identity)
            self.ring.execute(ticket);self.tickets[command.sequence]=ticket
            self.outputs[row.identity]=target(row.token,row.position)
            if self.index==self.count-1:token=self.outputs[row.identity] if row.fixture else None
            else:stream=bytearray(struct.pack('<4i',row.token,row.position,self.index,row.identity))
            original=command.sequence
        elif command.op==ACCEPT:
            ticket=self.tickets[command.row_ticket]
            before=self.ring.physical['position']
            output=self.outputs[row.identity] if row.fixture else self.prompt[row.position+1]
            self.ring.accept(ticket,verified_token=row.token,target_output=output if self.index==self.count-1 else None)
            assert before==self.ring.physical['position']
            self.accept_positions.append((row.position,before,self.ring.physical['position']))
            original=command.row_ticket
        else:
            assert command.op==ABORT_SUFFIX
            discarded=self.ring.reject_suffix(self.tickets[command.row_ticket]);original=command.row_ticket
        return Ack(self.epoch,self.index,self.sequence,row.identity,original,self.ring.physical['position'],self.ring.committed,len(self.ring.pending),discarded,stream,token)


def run(c,workers,seed=0,stop_when=None):
    randomizer=random.Random(seed);queue=[];ticks=0;peak_slots=0;peak_global=0;stopped=False
    while not c.done or c.reset_pending is not None:
        if stop_when is not None and not stopped and stop_when(c,queue):
            c.request_stop('reset');stopped=True
        commands=c.commands()
        for command in commands:
            queue.append((command,workers[command.stage].execute(command)))
        peak_slots=max(peak_slots,max(len(s.pending) for s in c.stages));peak_global=max(peak_global,c._live_count())
        if queue:
            command,ack=queue.pop(randomizer.randrange(len(queue)))
            c.complete(command,ack)
        elif not c.done:
            if c.phase is not None:continue
            raise AssertionError('scheduler deadlock: '+str([(s.physical,s.committed,len(s.pending),s.busy) for s in c.stages]))
        ticks+=1
        if ticks>30000:raise AssertionError('bounded CPU completion')
    assert not queue
    return dict(peak_slots=peak_slots,peak_global=peak_global,stopped=stopped)


def fixture(count=4,publisher=None,prompt=None,maximum=12,eos=(96,),seed=0,wire=0):
    prompt=prompt or [3,5,8,11]
    c=Coordinator(stages=count,request=sha256(b'fixture').digest(),epoch=1,prompt=prompt,max_new=maximum,
                  vocab=97,eos_token_ids=eos,proposal_callback=publisher,context=128,initial_sequences=[wire]*count)
    workers=[Worker(i,count,1,prompt,wire) for i in range(count)]
    return c,workers


class RingCoordinatorTests(unittest.TestCase):
    def test_long_prompt_releases_completed_streams_with_borrowers_alive(self):
        c,w=fixture(6,Publisher(),prompt=[3]*100,maximum=20)
        queue=[];peak=0;randomizer=random.Random(175)
        while not c.done:
            for command in c.commands():queue.append((command,w[command.stage].execute(command)))
            retained=sum(len(pub.data) for work in c.rows.values() for pub in work.streams.values())
            peak=max(peak,retained)
            self.assertLessEqual(retained,3*5*16)
            for command,_ in queue:
                if command.source is not None:
                    self.assertEqual(sha256(command.source.data).digest(),command.source.digest)
            if c.done:break
            self.assertTrue(queue)
            command,ack=queue.pop(randomizer.randrange(len(queue)));c.complete(command,ack)
        self.assertGreater(len(c.rows),100)
        self.assertGreater(peak,0)
        self.assertFalse(any(work.streams for work in c.rows.values()))

    def check_exact(self,c,workers,prompt,maximum,eos):
        inputs,outputs=reference(prompt,maximum,eos)
        self.assertEqual(c.emitted,outputs)
        self.assertTrue(all(w.ring.physical['history']==inputs for w in workers))
        self.assertTrue(all(s.physical==s.committed==len(inputs) and not s.pending and s.busy is None for s in c.stages))
        self.assertEqual(c.proposals.issued,{})
        self.assertEqual(c.proposals.batches,[])
        for worker in workers:
            gold=Ring(first=worker.index==0,final=worker.index==worker.count-1,context=128,vocab=97)
            for pos,token in enumerate(inputs):
                t=Ticket(pos+1,pos,0,pos,token,False);gold.execute(t)
                expected=inputs[pos+1] if pos+1<len(inputs) else target(token,pos)
                gold.accept(t,verified_token=token,target_output=expected if gold.final else None)
            self.assertEqual(worker.ring.physical,gold.physical)
            self.assertTrue(all(before==after for _,before,after in worker.accept_positions))
    def test_reordered_replies_all_hits_and_each_miss_depth_two_four_six(self):
        peak=0
        for count in (2,4,6):
            for misses in ((),(4,),(5,),(4,5,7,8,10,11)):
                for seed in range(4):
                    with self.subTest(count=count,misses=misses,seed=seed):
                        c,w=fixture(count,Publisher(misses));info=run(c,w,seed)
                        self.check_exact(c,w,[3,5,8,11],12,(96,))
                        self.assertLessEqual(info['peak_global'],3);self.assertLessEqual(info['peak_slots'],2)
                        peak=max(peak,info['peak_slots'])
                        if misses:self.assertTrue(any(e['event']=='abort-ack' for e in c.events))
        self.assertEqual(peak,2)
    def test_oldest_accept_preserves_a_completed_later_physical_row(self):
        c,w=fixture(6,Publisher());run(c,w,3)
        ahead=[entry for worker in w for entry in worker.accept_positions if entry[1]>entry[0]+1]
        self.assertTrue(ahead)
        self.assertTrue(all(before==after for _,before,after in ahead))
    def test_randomized_request_shapes_and_guess_batches(self):
        randomizer=random.Random(817)
        for count in (2,4,6):
            for case in range(12):
                prompt=[randomizer.randrange(97) for _ in range(randomizer.randint(1,35))]
                maximum=randomizer.randint(1,16)
                misses=[p for p in range(len(prompt),len(prompt)+maximum) if randomizer.randrange(3)==0]
                eos=(96,randomizer.randrange(96))
                c,w=fixture(count,Publisher(misses,fresh_disagree=case%3==0),prompt=prompt,maximum=maximum,eos=eos)
                run(c,w,case);self.check_exact(c,w,prompt,maximum,eos)
    def test_fresh_disagreement_does_not_replace_issued_work(self):
        publisher=Publisher(fresh_disagree=True);c,w=fixture(6,publisher,maximum=20)
        run(c,w,3);self.check_exact(c,w,[3,5,8,11],20,(96,))
        self.assertTrue(publisher.disagreements)
        created={e['row']:e['token'] for e in c.events if e['event']=='row-created'}
        for row,old,fresh in publisher.disagreements:
            self.assertEqual(created[row],old);self.assertNotEqual(old,fresh)
    def test_eos_and_cap_drain_tentative_suffix(self):
        for count in (2,4,6):
            for eos,maximum in (((96,14),20),((96,),1),((96,),2)):
                c,w=fixture(count,Publisher(),maximum=maximum,eos=eos)
                run(c,w,1);self.check_exact(c,w,[3,5,8,11],maximum,eos)
    def test_reset_waits_for_verified_prefix_and_all_suffix_acks(self):
        for stop in ('prompt','tentative'):
            c,w=fixture(4,Publisher(),maximum=20,wire=500)
            predicate=(lambda c,q: bool(q) and c.frontier==0) if stop=='prompt' else (lambda c,q:any(len(s.pending)==2 for s in c.stages))
            info=run(c,w,4,stop_when=predicate);self.assertTrue(info['stopped'])
            oldseq=[s.sequence for s in c.stages]
            self.assertTrue(all(s.physical==s.committed and not s.pending for s in c.stages))
            c.reset(request=sha256(b'next').digest(),epoch=2,prompt=[7,9],max_new=6)
            run(c,w,2);self.check_exact(c,w,[7,9],6,(96,))
            self.assertTrue(all(s.sequence>old for s,old in zip(c.stages,oldseq)))
            self.assertTrue(all(worker.reset_count==1 for worker in w))
    def test_reset_requested_during_suffix_abort_does_not_resume_corrected_work(self):
        c,w=fixture(6,Publisher((4,)),maximum=20)
        info=run(c,w,3,stop_when=lambda c,q:c.phase=='abort')
        self.assertTrue(info['stopped'])
        stopped=next(i for i,e in enumerate(c.events) if e['event']=='stop-requested')
        self.assertFalse(any(e['event']=='row-created' for e in c.events[stopped:]))
        self.assertTrue(all(s.physical==s.committed==4 for s in c.stages))
    def test_two_slot_suffix_abort_waits_for_every_inflight_reply(self):
        c,w=fixture(6,Publisher((4,)));run(c,w,3)
        self.assertTrue(any(e['event']=='abort-ack' and len(e['discarded'])==2 for e in c.events))
        outstanding={}
        for event in c.events:
            if event['event']=='send':
                if event['op']==ABORT_SUFFIX:
                    self.assertTrue(all(op==ABORT_SUFFIX for op in outstanding.values()))
                self.assertNotIn(event['stage'],outstanding)
                outstanding[event['stage']]=event['op']
            elif event['event']=='reply':
                self.assertEqual(outstanding.pop(event['stage']),event['op'])
        self.assertFalse(outstanding)
    def test_wrong_epoch_ticket_extent_and_duplicate_reply_refused(self):
        c,w=fixture(2,Publisher())
        command=c.commands()[0];ack=w[command.stage].execute(command)
        for bad in (replace(ack,epoch=2),replace(ack,row_id=999),replace(ack,sequence=2),replace(ack,stream=b'bad')):
            with self.assertRaises(ValueError):c.complete(command,bad)
        c.complete(command,ack)
        with self.assertRaisesRegex(ValueError,'stale duplicate'):c.complete(command,ack)
    def test_native_sticky_failure_blocks_commands_and_reset(self):
        c,w=fixture(2,Publisher());command=c.commands()[0];ack=w[0].execute(command)
        with self.assertRaisesRegex(ValueError,'native sticky'):
            c.complete(command,replace(ack,sticky_error=1))
        with self.assertRaisesRegex(ValueError,'sticky failure'):c.commands()
        with self.assertRaisesRegex(ValueError,'sticky failure'):
            c.reset(request=sha256(b'next').digest(),epoch=2,prompt=[1,2],max_new=3)
    def test_publication_owns_full_payload_before_slot_reuse(self):
        c,w=fixture(2,Publisher());command=c.commands()[0];ack=w[0].execute(command)
        c.complete(command,ack);original=bytes(ack.stream);ack.stream[:]=b'X'*len(ack.stream)
        publication=c.rows[0].streams[0]
        self.assertEqual(publication.data,original)
        self.assertEqual(publication.digest,sha256(original).digest())
    def test_corrected_row_admission_after_every_abort_ack(self):
        c,w=fixture(6,Publisher((4,5,6,7)));run(c,w,7)
        barrier=False;pending_stages=set()
        for event in c.events:
            if event['event']=='freeze':barrier=True
            if event['event']=='send' and event['op']==ABORT_SUFFIX:pending_stages.add(event['stage'])
            if event['event']=='abort-ack':pending_stages.remove(event['stage'])
            if event['event']=='drained':self.assertFalse(pending_stages);barrier=False
            if event['event']=='row-created' and barrier:self.fail('new row admitted across incomplete suffix barrier')
    def test_capacity_transition_restores_exact_banks_and_extent(self):
        prompt=[(i*3)%97 for i in range(31)]
        c,w=fixture(4,Publisher((32,33,35)),prompt=prompt,maximum=10)
        run(c,w,5);self.check_exact(c,w,prompt,10,(96,))


if __name__=='__main__':unittest.main()

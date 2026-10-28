"""CPU socket framing/provenance tests; not native provider validation."""
from hashlib import sha256
import socket
import struct
from types import SimpleNamespace as NS
import unittest
import ring_coordinator as core
from rolling_provider.arbiter import Parent
from rolling_provider.dedicated import ProviderCommand, ProviderJob
from rolling_provider.dedicated_transport import Provider, HEADER, MAGIC, VERSION, PROPOSAL_OFFSET, base, codec

class Guard:
    def check(self): pass

class WireTests(unittest.TestCase):
    def setUp(self):
        self.client,self.server=socket.socketpair()
        self.addCleanup(self.client.close);self.addCleanup(self.server.close)
        self.request=sha256(b'dedicated wire').digest();self.shared=bytearray(base.SHARED)
        self.plan=dict(stages=[{}, {}, {}],speculative_depth=3,request_sha256=self.request.hex(),vocab=97,context=128)
        self.owner=NS(sock=self.client,shared=self.shared,guard=Guard(),plan=self.plan,sequence=0)
        self.provider=Provider(self.owner)
        self.shared[:128]=HEADER.pack(MAGIC,VERSION,128,0,64,3,3,0,0,self.request,bytes(56))
    def ready(self):
        self.server.sendall(base.REPLY.pack(0,-1,0,64,0,-1,MAGIC,VERSION,0,0,0,0))
        self.provider.receive_ready();self.provider.start_async()
    def job(self,head=1):
        before,after=sha256(b'before').digest(),sha256(b'after').digest()
        seed=NS(epoch=0,identity=22,parent=21,position=3,token=11,fixture=head,request=self.request,before=before,after=after)
        original=NS(row=seed,stage=0,op=core.ROW,tentative=False,sequence=7)
        finalrow=NS(identity=21,after=before);hidden=b'h'*64;record=b'owned-final-record'
        parent=NS(row=finalrow,row_ticket=8,commit_sequence=9,record=record,handoff=NS(hidden=hidden))
        witness=Parent(finalrow,8,9,sha256(hidden).digest(),sha256(record).digest())
        command=ProviderCommand(1,seed)
        return command,ProviderJob(command,seed,witness,1),NS(accepted_row=original,accepted_sequence=8),parent
    def proposal(self,command,parent,head=1):
        r=command.row
        raw=codec.PROPOSAL.pack(0x44525032,2,224,2+head,r.epoch,command.sequence,r.identity,r.parent,
            parent.commit_sequence,1,r.position,r.position,3,3 if head else 0,12 if head else -1,
            13 if head else -1,0,1,r.request,r.after,sha256(parent.handoff.hidden).digest())
        return raw+struct.pack('<i',14 if head else -1)+bytes(28)
    def test_ready_rejects_request(self):
        self.shared[40:72]=bytes(32)
        self.server.sendall(base.REPLY.pack(0,-1,0,64,0,-1,MAGIC,VERSION,0,0,0,0))
        with self.assertRaisesRegex(ValueError,'header/source identity'):self.provider.receive_ready()
    def test_fragmented_actual_proposal(self):
        self.ready();command,job,seed,parent=self.job()
        self.provider.issue(command,job,seed,parent);self.provider.write_ready()
        self.assertEqual(base.REQUEST.unpack(self.server.recv(32)),(27,11,3,1,3,1,MAGIC,VERSION))
        self.assertFalse(hasattr(self.provider.transport_command,'stage'));self.assertEqual(seed.accepted_sequence,8)
        self.shared[PROPOSAL_OFFSET:PROPOSAL_OFFSET+224]=self.proposal(command,parent)
        reply=base.REPLY.pack(0,12,0,224,1,-1,MAGIC,VERSION,0,0,0,0)
        self.server.sendall(reply[:17]);self.assertIsNone(self.provider.read_ready())
        self.server.sendall(reply[17:]);returned,_,result=self.provider.read_ready()
        self.assertIs(returned,command);self.assertEqual(result['guesses'],[12,13,14])
        self.assertEqual(self.provider.provider_serial,1);self.assertEqual(self.provider.received.last,reply)
    def test_nohead_canonical_pair(self):
        self.ready();command,job,seed,parent=self.job(0)
        self.provider.issue(command,job,seed,parent);self.provider.write_ready();self.server.recv(32)
        self.shared[PROPOSAL_OFFSET:PROPOSAL_OFFSET+224]=self.proposal(command,parent,0)
        self.server.sendall(base.REPLY.pack(0,-1,0,224,1,-1,MAGIC,VERSION,0,0,0,0))
        self.assertEqual(self.provider.read_ready()[2]['guesses'],[])
    def test_corrupt_hidden_refused(self):
        self.ready();command,job,seed,parent=self.job()
        self.provider.issue(command,job,seed,parent);self.provider.write_ready();self.server.recv(32)
        raw=bytearray(self.proposal(command,parent));raw[160]^=1
        self.shared[PROPOSAL_OFFSET:PROPOSAL_OFFSET+224]=raw
        self.server.sendall(base.REPLY.pack(0,12,0,224,1,-1,MAGIC,VERSION,0,0,0,0))
        with self.assertRaisesRegex(ValueError,'provenance'):self.provider.read_ready()
        self.assertIs(self.provider.command_pending,command)
    def test_target_rank_reply_refused(self):
        self.server.sendall(base.REPLY.pack(0,-1,0,64,0,0,MAGIC,VERSION,0,0,0,0))
        with self.assertRaisesRegex(ValueError,'reply identity'):self.provider.receive_ready()
    def test_wrong_parent_refused_before_send(self):
        self.ready();command,job,seed,parent=self.job();parent.record=b'changed'
        with self.assertRaisesRegex(ValueError,'final parent lease'):self.provider.issue(command,job,seed,parent)
        self.assertEqual(self.provider.sequence,0)
    def test_reset_refused(self):
        with self.assertRaisesRegex(ValueError,'dump/finish'):self.provider.control(11)
if __name__=='__main__':unittest.main()

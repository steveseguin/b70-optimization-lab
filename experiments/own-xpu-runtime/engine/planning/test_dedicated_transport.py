"""CPU socket framing/provenance tests; not native provider validation."""
from hashlib import sha256
import socket
import struct
from types import SimpleNamespace as NS
import unittest
import ring_coordinator as core
from rolling_provider.arbiter import Parent
from ring_contract import append_prefix
from rolling_provider.dedicated import ProviderCommand, ProviderJob
from rolling_provider.dedicated_transport import Provider, HEADER, MAGIC, VERSION, PROPOSAL_OFFSET, base, codec
from rolling_provider import remote

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
        before=sha256(b'before').digest();after=append_prefix(before,3,11)
        seed=NS(epoch=0,identity=22,parent=21,position=3,token=11,fixture=head,request=self.request,before=before,after=after)
        original=core.Command(0,core.ROW,7,seed)
        finalrow=NS(identity=21,after=before);hidden=b'h'*64;record=b'owned-final-record'
        parent=NS(row=finalrow,row_ticket=8,commit_sequence=9,record=record,handoff=NS(hidden=hidden))
        witness=Parent(finalrow,8,9,sha256(hidden).digest(),sha256(record).digest())
        command=ProviderCommand(1,seed)
        owner=NS(accepted_row=original,accepted_sequence=8,shared=bytearray(base.SHARED))
        meta=list(codec.wire.ROW_META.unpack(codec.wire.row_metadata(original,final=False,stream_bytes=64)[0]));meta[14]=7
        owner.shared[remote.SEED_OFFSET:remote.SEED_OFFSET+256]=remote.SEED_HEADER.pack(0x52534331,1,256,0,8,4,4)+codec.wire.ROW_META.pack(*meta)
        return command,ProviderJob(command,seed,witness,1),owner,parent
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
    def test_actual_gate_accepted_tentative_journal(self):
        # Exact native source bytes from gate r1: original tentative3355,
        # ACCEPT3358, position1677, committed1678, physical1680.
        raw=bytes.fromhex('314353520100000000010000000000001e0d000000000000900600008e060000474e495201000000e00000000100000000000000000000008e060000000000008d060000000000008d0600007f6c0000020000000000000000000000ffffffff000000001b0d00000000000001000000fcad8ce0fb62c847c5280f0ba3e522cc07c3f7078838f80906d1a9cee8618faae56866b8e5464a32bc6b099d35337dc77045662076513365b975ef4e02df2c45537cb659397b076ce5124b637cd6d01825bad53e7145ea0bd388da68cbc877bbe3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85500000000000000000000000000000000')
        fields=codec.wire.ROW_META.unpack(raw[32:])
        row=core.Row(fields[4],fields[5],fields[6],fields[7],fields[8],fields[9],fields[17],fields[18],fields[19])
        original=core.Command(0,core.ROW,fields[14],row,bool(fields[3]&1))
        self.ready();command,job,seed,parent=self.job()
        original_parent=NS(identity=row.parent,after=row.before)
        parent.row=original_parent
        witness=Parent(original_parent,parent.row_ticket,parent.commit_sequence,sha256(parent.handoff.hidden).digest(),sha256(parent.record).digest())
        command=ProviderCommand(1,row);job=ProviderJob(command,row,witness,1)
        seed.accepted_row=original;seed.accepted_sequence=3358
        seed.shared[remote.SEED_OFFSET:remote.SEED_OFFSET+256]=raw
        self.provider.issue(command,job,seed,parent)
        self.provider.write_ready()
        self.assertEqual(base.REQUEST.unpack(self.server.recv(32)),
                         (27,27775,1677,2,3,1,MAGIC,VERSION))
        self.assertTrue(self.provider.transport_command.seed.tentative)
        self.assertEqual(self.provider.transport_command.seed.sequence,3355)
        self.assertEqual(bytes(seed.shared[remote.SEED_OFFSET:remote.SEED_OFFSET+256]),raw)
        normalized=core.Command(0,core.ROW,3355,row,False)
        with self.assertRaisesRegex(ValueError,'immutable ROW identity'):
            remote.seed_journal(seed,NS(seed=normalized,accepted_sequence=3358,depth=3),64)
        with self.assertRaisesRegex(ValueError,'journal owner/frontier/ACCEPT'):
            remote.seed_journal(seed,NS(seed=original,accepted_sequence=3359,depth=3),64)
    def test_seed_without_native_accept_publication_refused(self):
        self.ready();command,job,seed,parent=self.job()
        seed.shared[remote.SEED_OFFSET:remote.SEED_OFFSET+256]=bytes(256)
        with self.assertRaisesRegex(ValueError,'journal owner/frontier/ACCEPT'):self.provider.issue(command,job,seed,parent)
        self.assertEqual(self.provider.sequence,0)
    def test_fixture_integer_roundtrip_preserved(self):
        for depth in (2,3):
            for fixture in (0,1,2,3,32,512):
                with self.subTest(depth=depth,fixture=fixture):
                    # Fresh source/socket; request fixture stays exact. Only
                    # proposal head flag/availability converts it to Boolean.
                    self.setUp();self.plan['speculative_depth']=depth
                    self.shared[:128]=HEADER.pack(MAGIC,VERSION,128,0,64,3,depth,0,0,self.request,bytes(56))
                    self.ready();command,job,seed,parent=self.job(fixture)
                    self.provider.issue(command,job,seed,parent);self.provider.write_ready()
                    self.assertEqual(base.REQUEST.unpack(self.server.recv(32)),
                                     (27,11,3,fixture,depth,1,MAGIC,VERSION))
                    head=int(fixture>0);raw=self.proposal(command,parent,head)
                    if depth==2:
                        fields=list(codec.PROPOSAL.unpack(raw[:192]))
                        fields[1]=1;fields[2]=192;fields[12]=2;fields[13]=2 if head else 0
                        raw=codec.PROPOSAL.pack(*fields)
                    self.shared[PROPOSAL_OFFSET:PROPOSAL_OFFSET+len(raw)]=raw
                    self.server.sendall(base.REPLY.pack(0,12 if head else -1,0,len(raw),1,-1,MAGIC,VERSION,0,0,0,0))
                    result=self.provider.read_ready()[2]
                    self.assertEqual(result['guesses'],[12,13,14][:depth] if head else [])
    def test_reset_refused(self):
        with self.assertRaisesRegex(ValueError,'dump/finish'):self.provider.control(11)
if __name__=='__main__':unittest.main()

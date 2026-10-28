"""CPU private mmap/socket ACK fixtures; no native inference evidence."""
import unittest
import test_dedicated_transport as fixture
from rolling_provider.dedicated_transport import base, MAGIC, VERSION, PROPOSAL_OFFSET, CAPTURE_OFFSET
from rolling_provider import capture_ready

class CaptureTests(unittest.TestCase):
    setUp=fixture.WireTests.setUp
    ready=fixture.WireTests.ready
    job=fixture.WireTests.job
    proposal=fixture.WireTests.proposal
    def issue(self,opt=True):
        self.plan['dedicated_capture_ready']=opt;self.ready()
        command,job,seed,parent=self.job(2)
        self.provider.issue(command,job,seed,parent);self.provider.write_ready();self.server.recv(32)
        self.shared[PROPOSAL_OFFSET:PROPOSAL_OFFSET+224]=self.proposal(command,parent)
        raw=capture_ready.CAPTURE.pack(*capture_ready.expected(self.provider.transport_command))
        self.shared[CAPTURE_OFFSET:CAPTURE_OFFSET+128]=raw
        return command,job,seed,parent,raw
    def ack(self,sequence=1,rank=-1,role=MAGIC):
        return base.REPLY.pack(2,-1,0,128,sequence,rank,role,VERSION,0,0,0,0)
    def completion(self):return base.REPLY.pack(0,12,0,224,1,-1,MAGIC,VERSION,0,0,0,0)
    def test_fragmented_ack_completion_retains_source_ownership(self):
        command,job,seed,parent,raw=self.issue()
        wire=self.provider.transport_command;header=self.ack()
        self.server.sendall(header[:11]);self.assertIsNone(self.provider.read_ready())
        self.server.sendall(header[11:]);event=self.provider.read_ready()
        self.assertIsInstance(event,capture_ready.Captured)
        self.assertIs(event.command,command);self.assertEqual(event.identity,raw)
        self.assertIs(self.provider.command_pending,command);self.assertIs(self.provider.transport_command,wire)
        self.assertEqual(self.provider.provider_serial,0);self.assertEqual(self.provider.sequence,1)
        self.assertIs(wire.seed,seed.accepted_row);self.assertIs(wire.parent,parent)
        self.assertEqual(seed.accepted_sequence,8)
        reply=self.completion();self.server.sendall(reply[:19]);self.assertIsNone(self.provider.read_ready())
        self.server.sendall(reply[19:]);retired,_,result=self.provider.read_ready()
        self.assertIs(retired,command);self.assertEqual(result['guesses'],[12,13,14])
        self.assertEqual(self.provider.provider_serial,1);self.assertIsNone(self.provider.command_pending)
        self.assertIsNone(self.provider.captured_sequence)
    def test_duplicate_ack_refused(self):
        self.issue();self.server.sendall(self.ack());self.provider.read_ready()
        self.server.sendall(self.ack())
        with self.assertRaisesRegex(ValueError,'duplicate/unexpected/malformed'):self.provider.read_ready()
    def test_missing_ack_refused(self):
        self.issue();self.server.sendall(self.completion())
        with self.assertRaisesRegex(ValueError,'prior matching capture ACK'):self.provider.read_ready()
    def test_default_rejects_unrequested_ack(self):
        self.issue(False);self.server.sendall(self.ack())
        with self.assertRaisesRegex(ValueError,'duplicate/unexpected/malformed'):self.provider.read_ready()
    def test_stale_wrong_role_headers_refused(self):
        for kw in ({'sequence':2},{'rank':0},{'role':MAGIC+1}):
            self.setUp();self.issue();self.server.sendall(self.ack(**kw))
            with self.assertRaisesRegex(ValueError,'duplicate/unexpected/malformed'):self.provider.read_ready()
    def test_capture_releases_only_final_row_keeps_accept_leases(self):
        from hashlib import sha256
        import ring_coordinator as core
        from test_ring_coordinator import Worker
        from rolling_provider.dedicated import DedicatedCoordinator,ProviderCommand
        from rolling_provider.arbiter import Parent
        prompt=[3,5,8,11]
        c=DedicatedCoordinator(stages=3,request=sha256(b'capture ownership').digest(),epoch=1,
            prompt=prompt,max_new=8,vocab=97,eos_token_ids=(96,),context=128,
            initial_sequences=[0]*3,speculative_depth=3)
        workers=[Worker(i,3,1,prompt,0,3) for i in range(3)]
        found=None
        for tick in range(1000):
            for command in c.commands():
                if isinstance(command,ProviderCommand):
                    found=command;break
                ack=workers[command.stage].execute(command);parent=None
                if command.op==core.ACCEPT and command.stage==2:
                    parent=Parent(command.row,command.row_ticket,command.sequence,
                        sha256(repr(command.row).encode()).digest(),sha256(repr(command).encode()).digest())
                c.complete(command,ack,final_parent=parent)
            if found:break
        self.assertIsNotNone(found);job=c.provider_jobs[found.sequence]
        self.assertFalse(c.provider.row_allowed(2,job.seed.position,tentative=False))
        c.capture_provider(found)
        self.assertTrue(c.provider.row_allowed(2,job.seed.position,tentative=False))
        self.assertIs(c.provider_busy,found);self.assertIs(c.provider.job,job)
        self.assertEqual(c.provider.local_seed,job.seed);self.assertEqual(c.provider.parent,job.parent)
        # Drive only targets while withholding completion. Source ACCEPT locks
        # remain, though the final ROW can now compute its next hidden bytes.
        final_row_seen=False
        for tick in range(30):
            commands=c.commands()
            for command in commands:
                self.assertFalse(command.op==core.ACCEPT and command.stage in (0,2))
                if command.stage==2 and command.op==core.ROW:final_row_seen=True
                ack=workers[command.stage].execute(command)
                c.complete(command,ack)
            if not commands:break
        self.assertTrue(final_row_seen)
        self.assertIs(c.provider_busy,found);self.assertIs(c.provider.parent,job.parent)
    def test_every_capture_binding_refused_on_corruption(self):
        # epoch/sequence/seed/parent/finalcommit/serial/request/finalrecord SHA.
        for index in range(3,11):
            self.setUp();self.issue();fields=list(capture_ready.expected(self.provider.transport_command))
            fields[index]=fields[index]+1 if type(fields[index]) is int else bytes([fields[index][0]^1])+fields[index][1:]
            self.shared[CAPTURE_OFFSET:CAPTURE_OFFSET+128]=capture_ready.CAPTURE.pack(*fields)
            self.server.sendall(self.ack())
            with self.assertRaisesRegex(ValueError,'exact owned parent/request/seed/provider identity'):self.provider.read_ready()
            self.assertIsNotNone(self.provider.command_pending)

if __name__=='__main__':unittest.main()

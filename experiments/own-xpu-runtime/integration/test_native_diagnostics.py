"""Real anonymous pipes and producer threads; no child/native process."""
import fcntl
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from bounded_evidence import BoundedEvidence, EvidenceLimit
from native_diagnostics import PipeDiagnostics, CaptureBackpressure, DiagnosticsError


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.writer=BoundedEvidence(self.root,total_limit_bytes=1024*1024)
        self.writer.create('stderr',limit_bytes=1024*1024)
        self.fds=[];self.drainers=[];self.producers=[];self.releases=[]

    def tearDown(self):
        for event in self.releases:event.set()
        for fd in self.fds:
            try:os.close(fd)
            except OSError:pass
        for thread in self.producers:thread.join(3)
        for drain in self.drainers:
            state=drain.join(3)
            if state['owned_read_fd_open']:
                drain.release_after_producer_exit(producer_exited=True)
            self.assertFalse(drain.status()['retained'])
        self.writer.close();self.tmp.cleanup()

    def pipe(self):
        r,w=os.pipe();self.fds.extend((r,w));return r,w

    def start(self,r,writer=None,**kwargs):
        d=PipeDiagnostics(r,writer or self.writer,'stderr',**kwargs)
        self.drainers.append(d);d.start();return d

    def close_fd(self,fd):
        os.close(fd);self.fds.remove(fd)

    def producer(self,w,payload):
        outcome={}
        def run():
            try:
                view=memoryview(payload)
                while view:view=view[os.write(w,view):]
                outcome['passed']=True
            except BaseException as error:outcome['error']=error
        thread=threading.Thread(target=run);self.producers.append(thread);thread.start()
        return thread,outcome

    def test_eof_clean_bytes_original_fd_stays_owned_by_caller(self):
        r,w=self.pipe();d=self.start(r)
        os.write(w,b'hello stderr\n');self.close_fd(w)
        status=d.join(2)
        self.assertFalse(status['retained']);self.assertTrue(status['eof']);self.assertFalse(status['incident'])
        self.assertEqual(status['successful_append_bytes'],13)
        self.assertEqual((self.root/'stderr').read_bytes(),b'hello stderr\n')
        os.fstat(r)
        self.assertFalse(status['owned_read_fd_open'])

    def test_cap_incident_does_not_block_large_producer(self):
        self.writer.create('small',limit_bytes=1)
        r,w=self.pipe();d=PipeDiagnostics(r,self.writer,'small',chunk_bytes=4096,queue_chunks=64)
        self.drainers.append(d);d.start()
        os.write(w,b'AB');self.assertTrue(d.incident_event.wait(2))
        original=d.error;self.assertIsInstance(original,EvidenceLimit)
        thread,outcome=self.producer(w,b'x'*(2*1024*1024));thread.join(3)
        self.assertFalse(thread.is_alive());self.assertTrue(outcome.get('passed'),outcome)
        self.close_fd(w);status=d.join(2)
        self.assertTrue(status['eof']);self.assertFalse(status['retained']);self.assertIs(d.error,original)
        self.assertEqual((self.root/'small').read_bytes(),b'')
        self.assertEqual(status['bytes_read'],2+2*1024*1024)

    def test_original_writer_error_preserved_while_discarding(self):
        original=OSError('injected evidence failure')
        class Failing:
            def append(self,*args):raise original
        r,w=self.pipe();d=self.start(r,Failing());os.write(w,b'first')
        self.assertTrue(d.incident_event.wait(2));self.assertIs(d.error,original);self.assertIs(d.capture_error,original)
        thread,outcome=self.producer(w,b'x'*100000);thread.join(2);self.assertTrue(outcome.get('passed'))
        self.close_fd(w);self.assertTrue(d.join(2)['eof'])

    def test_partial_writer_prefix_report_is_explicit_lower_bound(self):
        r,w=self.pipe();d=self.start(r);real=os.write;original=OSError('partial evidence failure');calls=[]
        def partial(fd,data):
            if fd==w:return real(fd,data)
            calls.append(1)
            if len(calls)==1:return real(fd,data[:2])
            raise original
        with patch('bounded_evidence.os.write',side_effect=partial):
            real(w,b'abcdef');self.assertTrue(d.incident_event.wait(2))
        self.close_fd(w);status=d.join(2)
        self.assertIs(d.capture_error,original)
        self.assertEqual((self.root/'stderr').read_bytes(),b'ab')
        self.assertEqual(self.writer.status()['payload_bytes'],2)
        self.assertEqual(status['successful_append_bytes'],0)
        self.assertIn('lower bound',status['successful_append_bytes_scope'])

    def test_join_timeout_keeps_reader_and_pipe_alive(self):
        r,w=self.pipe();d=self.start(r);self.close_fd(r)
        status=d.join(.01);self.assertTrue(status['reader_retained']);self.assertTrue(status['owned_read_fd_open'])
        os.write(w,b'after timeout');self.close_fd(w)
        self.assertFalse(d.join(2)['retained']);self.assertEqual((self.root/'stderr').read_bytes(),b'after timeout')

    def test_blocked_writer_queue_full_still_drains_and_retains_capture(self):
        entered=threading.Event();release=threading.Event();self.releases.append(release)
        writer=self.writer;late_error=OSError('late writer failure')
        class Blocked:
            def append(self,name,data):
                entered.set();release.wait();writer.append(name,data);raise late_error
        r,w=self.pipe();d=self.start(r,Blocked(),chunk_bytes=1024,queue_chunks=1)
        os.write(w,b'a');self.assertTrue(entered.wait(2))
        thread,outcome=self.producer(w,b'x'*(1024*1024));thread.join(3)
        self.assertFalse(thread.is_alive());self.assertTrue(outcome.get('passed'),outcome)
        self.assertIsInstance(d.error,CaptureBackpressure)
        self.close_fd(w);status=d.join(.05)
        self.assertTrue(status['eof']);self.assertFalse(status['reader_retained']);self.assertTrue(status['capture_retained'])
        self.assertEqual(status['payload_buffer_bound_bytes'],3072)
        release.set();self.assertFalse(d.join(2)['retained'])
        self.assertIsInstance(d.error,CaptureBackpressure);self.assertIs(d.capture_error,late_error)
        self.assertEqual((self.root/'stderr').read_bytes(),b'a')

    def test_read_failure_is_not_reported_as_eof_or_clean_drain(self):
        r,w=self.pipe();original=OSError('injected pipe read failure')
        with patch('native_diagnostics.os.read',side_effect=original):
            d=self.start(r);self.close_fd(r);status=d.join(2)
        self.assertFalse(status['eof']);self.assertTrue(status['retained'])
        self.assertTrue(status['incident']);self.assertIs(d.error,original)
        self.assertIsNone(d.capture_error)
        payload=b'producer still has a reader'
        self.assertEqual(os.write(w,payload),len(payload))
        with self.assertRaises(DiagnosticsError):d.release_after_producer_exit(producer_exited=False)
        self.close_fd(w);d.release_after_producer_exit(producer_exited=True)
        self.assertFalse(d.status()['retained'])

    def test_interrupted_reader_start_does_not_close_busy_endpoint(self):
        r,w=self.pipe();original=RuntimeError('start interrupted after thread exists')
        real=threading.Thread.start
        def interrupted(thread):
            real(thread)
            if thread.name=='bounded-diagnostics-reader':raise original
        d=PipeDiagnostics(r,self.writer,'stderr');self.drainers.append(d)
        with patch('native_diagnostics.threading.Thread.start',side_effect=interrupted,autospec=True):
            with self.assertRaises(RuntimeError) as caught:d.start()
        self.assertIs(caught.exception,original);self.close_fd(r)
        self.assertTrue(d.join(.01)['owned_read_fd_open'])
        with self.assertRaises(DiagnosticsError):d.release_after_producer_exit(producer_exited=True)
        os.write(w,b'after interrupted startup');self.close_fd(w)
        status=d.join(2);self.assertTrue(status['eof']);self.assertFalse(status['retained'])

    def test_nonblocking_or_write_end_refused_without_flags_change_or_fd_leak(self):
        r,w=self.pipe();fcntl.fcntl(r,fcntl.F_SETFL,fcntl.fcntl(r,fcntl.F_GETFL)|os.O_NONBLOCK)
        before=set(os.listdir('/proc/self/fd'))
        for fd in (r,w):
            d=PipeDiagnostics(fd,self.writer,'stderr')
            with self.assertRaises(DiagnosticsError):d.start()
            self.assertFalse(d.join(0)['retained'])
        self.assertEqual(set(os.listdir('/proc/self/fd')),before)
        self.assertTrue(fcntl.fcntl(r,fcntl.F_GETFL)&os.O_NONBLOCK)

    def test_single_use_and_no_duplicate_fd_leaks(self):
        r,w=self.pipe();before=set(os.listdir('/proc/self/fd'));d=self.start(r)
        with self.assertRaisesRegex(DiagnosticsError,'single use'):d.start()
        self.close_fd(w);self.assertFalse(d.join(2)['retained'])
        self.assertEqual(len(os.listdir('/proc/self/fd')),len(before)-1)
        self.assertFalse(d.join(0)['retained'])


if __name__=='__main__':unittest.main(verbosity=2)

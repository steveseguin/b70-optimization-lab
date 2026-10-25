"""CPU sockets/pipes: preserve observer first cause through a native-style stop."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import pipeline_driver as base
import wavefront_driver as wave


class GuardDiagnosticsTests(unittest.TestCase):
    def guard(self, folder, *, rejected=False):
        guard = base.Guard.__new__(base.Guard)
        guard.plan = dict(output=str(folder), seconds=30, grace_seconds=1,
                          memory_start_bytes=1, memory_floor_bytes=1, root_floor_bytes=1, evidence_floor_bytes=1,
                          stages=[dict(id=0, first=True, final=True)])
        guard.stop_fd = None
        guard.signal_stop = threading.Event()
        guard.deadline = time.monotonic()+30
        guard.identities, guard.stoppers, guard.tracked_processes = {}, [], []
        guard.lock = threading.Lock()
        guard.failed = guard.first_failure = guard.failure_evidence_error = None
        guard.done = threading.Event()
        guard.targets = {}
        row = dict(boot='test', drm={}, kernel=dict(faults=[]), known_fault_baseline_matches=True,
                   inventory=dict(errors=[], holders=[]), identity_races=[], memory=dict(MemAvailable=2),
                   root_free_bytes=0 if rejected else 2, witness='complete rejecting snapshot')
        guard.baseline = row.copy()
        class Observer:
            def observe(self):return row
        guard.obs = Observer()
        return guard, row

    def run_rejecting_observation(self, result_save_failure=False, empty_reason=False):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'run';guard,row=self.guard(output,rejected=True)
            expected_reason='' if empty_reason else 'root free floor'
            if empty_reason:
                def reject(row):raise ValueError()
                guard.validate=reject
            waiting=threading.Event();stopped=threading.Event();stop_bytes=[];workers=[];resources=[]
            class Gate:
                # Trigger actual watch validation after receive passed check()
                # and entered the blocking socket recv, reproducing the race.
                def wait(self, timeout):
                    waiting.wait(3)
                    return stopped.is_set()
                def set(self):stopped.set()
            guard.done=Gate();guard.thread=threading.Thread(target=guard.watch)
            class Process:
                pid=1234
                returncode=None
                def poll(self):return self.returncode
            class Stage:
                def __init__(self,spec,plan,g):
                    self.spec,self.plan,self.guard,self.sequence=spec,plan,g,0
                    left,right=socket.socketpair();read,write=os.pipe();resources.extend([left,right,read,write])
                    class ReceivingSocket:
                        def recv(self,n):waiting.set();return left.recv(n)
                    self.sock=ReceivingSocket();self.proc=Process();self.stream_bytes=None
                    g.stoppers.append(write);g.tracked_processes.append((0,self.proc))
                    def native_stop():
                        stop_bytes.append(os.read(read,1));self.proc.returncode=1;right.close()
                    thread=threading.Thread(target=native_stop);workers.append(thread);thread.start()
                receive=base.Stage.receive
            admission=dict(schema='ownrt.pipeline-admission.v1',owner_authorized=True,
                           expires_utc=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat())
            original_save=base.save
            def save(path,value):
                if result_save_failure and path.name=='result.json':raise OSError('injected result persistence failure')
                return original_save(path,value)
            try:
                with patch.object(base,'save',side_effect=save),patch.object(base,'Guard',return_value=guard),patch.object(base,'validate_unit',return_value={}),patch.object(os,'getpriority',return_value=19):
                    with self.assertRaisesRegex(ValueError,'^$' if empty_reason else 'root free floor') as caught:
                        wave.execute(guard.plan,admission,'cpu-only',stage_type=Stage,driver=lambda *args:self.fail('ROW must not run'))
                for thread in workers:thread.join(3);self.assertFalse(thread.is_alive())
                if result_save_failure:
                    self.assertIsInstance(caught.exception.__cause__,OSError)
                    self.assertIn('result persistence failure',str(caught.exception.__cause__))
                    self.assertFalse((output/'result.json').exists())
                else:
                    result=json.loads((output/'result.json').read_text())
                    self.assertEqual(result['error'],expected_reason)
                    self.assertEqual(result['guard_failure'],expected_reason)
                    self.assertEqual(result['caught_error'],"ValueError('stage channel closed')")
                    self.assertEqual(result['returncodes'],{'0':1})
                    self.assertEqual(result['live_pids'],[])
                self.assertEqual(stop_bytes,[b'!'])
                observed=output/'guard-rejected-observation.json'
                self.assertEqual(json.loads(observed.read_text()),row)
                first=json.loads((output/'guard-first-failure.json').read_text())
                self.assertEqual(first['reason'],expected_reason);self.assertEqual(first['phase'],'validate')
                self.assertEqual(first['rejected_observation']['sha256'],base.digest(observed))
                self.assertFalse((output/'observations.jsonl').exists())
                before=(output/'guard-first-failure.json').read_bytes();guard.fail('later cleanup error')
                self.assertEqual((output/'guard-first-failure.json').read_bytes(),before)
            finally:
                for item in resources:
                    try:item.close() if hasattr(item,'close') else os.close(item)
                    except OSError:pass

    def test_rejecting_observation_stop_pipe_channel_close_preserves_first_cause(self):
        self.run_rejecting_observation()

    def test_empty_reason_survives_nonzero_native_exit(self):
        self.run_rejecting_observation(empty_reason=True)

    def test_terminal_result_write_error_preserves_primary_guard_reason(self):
        self.run_rejecting_observation(result_save_failure=True)

    def test_main_thread_rejection_retains_same_full_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);guard,row=self.guard(folder,rejected=True)
            with self.assertRaisesRegex(ValueError,'root free floor'):
                guard.validate_or_stop(row,phase='main-after-ready')
            self.assertEqual(json.loads((folder/'guard-rejected-observation.json').read_text()),row)
            self.assertEqual(json.loads((folder/'guard-first-failure.json').read_text())['phase'],'main-after-ready')

    def test_empty_reason_still_closes_guard_and_evidence_io_does_not_hold_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);guard,_=self.guard(folder)
            original_save=base.save
            def unlocked_save(path,value):
                self.assertTrue(guard.lock.acquire(blocking=False))
                guard.lock.release()
                return original_save(path,value)
            with patch.object(base,'save',side_effect=unlocked_save):guard.fail(ValueError())
            with self.assertRaises(RuntimeError):guard.check()
            self.assertEqual(guard.failed,'')
            self.assertEqual(json.loads((folder/'guard-first-failure.json').read_text())['reason'],'')

    def test_recording_failure_cannot_suppress_stop_or_replace_first_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);guard,row=self.guard(folder,rejected=True)
            read,write=os.pipe();self.addCleanup(os.close,read);self.addCleanup(os.close,write)
            guard.stoppers=[write]
            (folder/'guard-first-failure.json').write_text('preserved prior artifact')
            (folder/'guard-rejected-observation.json').write_text('preserved prior artifact')
            guard.fail(ValueError('first'),observation=row,phase='validate')
            guard.fail('second')
            self.assertEqual(os.read(read,1),b'!')
            self.assertEqual(guard.failed,'first')
            self.assertIn('FileExistsError',guard.failure_evidence_error)
            self.assertIn('FileExistsError',guard.first_failure['observation_write_error'])
            self.assertEqual((folder/'guard-first-failure.json').read_text(),'preserved prior artifact')
            os.set_blocking(read,False)
            with self.assertRaises(BlockingIOError):os.read(read,1)

    def test_successful_lifecycle_result_shape_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'run';guard,row=self.guard(output)
            guard.thread=threading.Thread(target=guard.watch)
            class Process:
                pid=1234
                returncode=None
                def poll(self):return self.returncode
            class Stage:
                def __init__(self,spec,plan,g):
                    self.stream_bytes=16;self.proc=Process();g.tracked_processes.append((0,self.proc))
                def receive(self,ready=False):pass
                def command(self,op,**kwargs):
                    if op==5:self.proc.returncode=0
            admission=dict(schema='ownrt.pipeline-admission.v1',owner_authorized=True,
                           expires_utc=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat())
            with patch.object(base,'Guard',return_value=guard),patch.object(base,'validate_unit',return_value={}),patch.object(os,'getpriority',return_value=19):
                wave.execute(guard.plan,admission,'cpu-only',stage_type=Stage,driver=lambda *args:{})
            result=json.loads((output/'result.json').read_text())
            self.assertEqual(set(result),{'schema','passed','error','live_pids','returncodes','wall_seconds','mode','diagnostic_only','speed_claim','scripted_proposals'})
            self.assertTrue(result['passed']);self.assertIsNone(result['error'])
            self.assertFalse((output/'guard-first-failure.json').exists())
            self.assertFalse((output/'guard-rejected-observation.json').exists())


if __name__=='__main__':unittest.main()

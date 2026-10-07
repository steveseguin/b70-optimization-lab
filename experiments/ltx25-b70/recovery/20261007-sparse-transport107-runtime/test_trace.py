"""Synthetic CPU-only events; no Torch imports, processes, devices, or waits."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sparse_trace_under_test', HERE / 'trace.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class Stream:
    def __init__(self, device):
        self.device = device


STREAMS = {d: Stream(d) for d in t.DEVICES}


class Backend:
    def __init__(self):
        self.created, self.records, self.reads, self.tick = [], [], [], 0
        self.drained = False
        self.record_error = self.read_error = None
        self.duration = None

    def clock(self):
        self.tick += 100
        return self.tick

    def factory(self, device):
        backend = self

        class Event:
            def record(self, stream):
                if backend.record_error is not None:
                    raise backend.record_error
                if stream.device != device:
                    raise AssertionError('event recorded on wrong device')
                self.stamp = backend.clock()
                backend.records.append((self, device))

            def elapsed_time(self, other):
                if not backend.drained:
                    raise AssertionError('elapsed_time before existing drains')
                if backend.read_error is not None:
                    raise backend.read_error
                backend.reads.append((self, other))
                return backend.duration if backend.duration is not None else (other.stamp - self.stamp) / 1e6

        event = Event()
        self.created.append((event, device))
        return event


class Tests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.workers = {0: {'ident': 111, 'name': 'ltx-sample-0'}, 1: {'ident': 222, 'name': 'ltx-sample-1'}}
        self.thread = [111, 'ltx-sample-0']
        self.identity = {k: c * 64 for k, c in [('plan_sha256', 'a'), ('server_identity_sha256', 'b'), ('source_sha256', 'c')]}
        self.manager = t.TraceManager(self.workers, self.backend.factory, self.identity,
                                      self.backend.clock, lambda: tuple(self.thread))

    def job(self, worker=0, clip=99907104):
        self.thread[:] = [self.workers[worker]['ident'], self.workers[worker]['name']]
        return self.manager.begin_job(clip, worker, 'candidate-check')

    def move(self, job, kind, i):
        src, dst = ('xpu:0', 'xpu:1') if kind == 'img' else ('xpu:1', 'xpu:0')
        token = job.move_begin((kind, i), src, dst, (2, 4), 'torch.bfloat16', 16, STREAMS[src])
        job.move_d2h_end(token, STREAMS[src])
        job.wait_begin(token)
        job.wait_end(token)
        job.move_alloc_begin(token)
        job.move_alloc_end(token)
        job.move_h2d_begin(token, STREAMS[dst])
        job.move_end(token, STREAMS[dst])

    def forward(self, job, fills=True):
        for index in range(48):
            device = 'xpu:0' if index < 23 else 'xpu:1'
            stream = STREAMS[device]
            job.block_enter(index, device, 'xpu:0', index == 47, 1, 2)
            if index == 23:
                self.move(job, 'img', 0)
                self.move(job, 'img', 1)
            # All argument transfers are excluded even on selected forwards.
            job.move_begin(('arg', 'context', (4,)), 'xpu:0', 'xpu:1', (), '', 0, STREAMS['xpu:0'])
            if fills:
                token = job.fill_begin(device, stream)
                for nbytes in (16, 32, 16):
                    job.fill_add(token, nbytes)
                job.fill_end(token, stream)
            token = job.replay_begin(index, device, stream)
            job.replay_end(token, index, device, stream)
            if index == 47:
                self.move(job, 'out', 0)
                self.move(job, 'out', 1)

    def full_job(self, job, fills=True):
        for stage in ('a', 'b'):
            job.stage(stage)
            self.forward(job, fills)
            self.forward(job, fills)
            self.forward(job, fills)  # Third forward is disabled again.

    def test_worst_case_bound_and_readout_after_existing_drain(self):
        job = self.job()
        self.full_job(job)
        self.assertEqual(len(self.backend.created), 256)
        self.assertEqual(len(self.backend.records), 232)
        self.assertEqual(self.backend.reads, [])
        self.backend.drained = True
        result = job.finish_after_existing_drains(True)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['operation_count'], 108)
        self.assertEqual(result['events_reserved'], {'xpu:0': 112, 'xpu:1': 120})
        fills = [op for op in result['operations'] if op['kind'] == 'fill']
        self.assertEqual(len(fills), 96)
        self.assertTrue(all(op['nbytes'] == 64 and op['tensor_count'] == 3 for op in fills))
        self.assertTrue(all(op['forward_ordinal'] == 2 for op in result['operations']))
        self.assertEqual(len(self.backend.reads), 116)
        moves = [op for op in result['operations'] if op['kind'] == 'move']
        self.assertEqual(len(moves), 8)
        self.assertTrue(all(op['host_wait_ns'] > 0 and op['destination_allocation_ns'] > 0 for op in moves))
        json.dumps(result, allow_nan=False)
        self.assertEqual(job.finish_after_existing_drains(True), result)
        self.assertEqual(len(self.backend.reads), 116)

    def test_two_worker_claims_then_timed_disabled_audit_includes_tails(self):
        for worker in (0, 1):
            job = self.job(worker, 99907104 + worker)
            self.full_job(job, fills=False)
            self.backend.drained = True
            self.assertTrue(job.finish_after_existing_drains(True)['valid'])
            self.manager.clear()
        self.assertTrue(self.manager.close_candidate()['complete'])
        created, recorded = len(self.backend.created), len(self.backend.records)
        for clip in range(99907200, 99907214):
            job = self.manager.begin_job(clip, 1, 'timed-fast')
            self.assertFalse(job.recording)
            self.full_job(job)
            receipt = job.finish_after_existing_drains(True)
            self.assertEqual(receipt['events_recorded'], 0)
            self.manager.clear()
        snapshot = self.manager.snapshot()
        self.assertEqual(len(snapshot['jobs']), 16)
        self.assertEqual(snapshot['active_jobs'], 0)
        self.assertEqual(snapshot['phase_events']['timed-fast'], 0)
        self.assertEqual((len(self.backend.created), len(self.backend.records)), (created, recorded))

    def test_only_one_job_per_actual_worker_not_clip_parity(self):
        self.job(0, 99907105)  # Odd clip on worker0 is valid.
        self.manager.clear()
        job = self.job(0, 99907106)
        self.assertFalse(job.selected)
        self.assertEqual(job.reason, 'worker-already-claimed')
        self.assertEqual(len(self.backend.created), 256)

    def test_wrong_registered_binding_allocates_no_events(self):
        self.thread[:] = [999, 'ltx-sample-0']
        job = self.manager.begin_job(99907104, 0, 'candidate-check')
        self.assertFalse(job.selected)
        self.assertEqual(self.manager.census()['binding_failures'], 1)
        self.assertEqual(self.backend.created, [])

    def test_setup_native_and_outside_eligible_are_disabled(self):
        for clip, phase in [(99907030, 'optimized-preparation'), (99907000, 'native'), (99907103, 'candidate-check')]:
            job = self.manager.begin_job(clip, 0, phase)
            self.assertFalse(job.selected)
            self.manager.clear()
        self.assertEqual(self.backend.created, [])
        self.assertEqual(len(self.manager.snapshot()['jobs']), 3)

    def active(self):
        job = self.job()
        job.stage('a')
        self.forward(job)
        job.block_enter(0, 'xpu:0', 'xpu:0', False, 1, 2)
        return job

    def test_pair_capacity_reservation_is_atomic(self):
        job = self.active()
        job.used['xpu:0'] = 127
        self.assertIsNone(job.fill_begin('xpu:0', STREAMS['xpu:0']))
        self.assertEqual(job.used['xpu:0'], 127)
        self.assertEqual(self.backend.records, [])
        self.assertEqual(job.error, 'trace-cap-exceeded')
        self.assertFalse(job.finish_after_existing_drains(False)['valid'])

    def test_operation_cap_stops_without_record(self):
        job = self.active()
        with patch.object(t, 'MAX_OPS', 0):
            self.assertIsNone(job.fill_begin('xpu:0', STREAMS['xpu:0']))
        self.assertEqual(self.backend.records, [])

    def test_scope_failure_globally_prevents_other_worker_claim(self):
        job = self.active()
        job.block_enter(2, 'xpu:0', 'xpu:0', False, 1, 2)
        self.manager.clear()
        other = self.job(1, 99907105)
        self.assertFalse(other.selected)
        self.assertEqual(other.reason, 'diagnostic-invalid')
        self.assertEqual(len(self.backend.created), 256)

    def test_order_violation_disables_all_further_hooks(self):
        job = self.active()
        job.block_enter(2, 'xpu:0', 'xpu:0', False, 1, 2)
        self.assertFalse(job.recording)
        self.forward(job)
        self.assertEqual(self.backend.records, [])
        self.assertFalse(job.finish_after_existing_drains(True)['valid'])

    def test_unexpected_img_move_invalidates_and_arguments_do_not(self):
        job = self.active()
        self.assertIsNone(job.move_begin(('arg', 'context', (8,)), 'xpu:0', 'xpu:1', (8,), 'f', 32, STREAMS['xpu:0']))
        self.assertIsNone(job.error)
        self.assertIsNone(job.move_begin(('img', 0), 'xpu:0', 'xpu:1', (8,), 'f', 32, STREAMS['xpu:0']))
        self.assertEqual(job.error, 'activation-move-scope-mismatch')
        self.assertEqual(self.backend.records, [])

    def test_empty_or_duplicate_fill_invalid(self):
        job = self.active()
        token = job.fill_begin('xpu:0', STREAMS['xpu:0'])
        job.fill_end(token, STREAMS['xpu:0'])
        self.assertEqual(job.error, 'empty-fill-instrumented')
        self.assertEqual(len(self.backend.records), 1)
        self.assertFalse(job.finish_after_existing_drains(True)['valid'])
        self.assertEqual(self.backend.reads, [])

    def test_wrong_stream_metadata_invalidates_before_event_record(self):
        job = self.active()
        job.fill_begin('xpu:0', STREAMS['xpu:1'])
        self.assertEqual(job.error, 'event-stream-device-mismatch')
        self.assertEqual(self.backend.records, [])

    def test_backend_record_error_propagates_and_clear_never_reads(self):
        job = self.active()
        error = RuntimeError('synthetic GPU fault')
        self.backend.record_error = error
        with self.assertRaises(RuntimeError) as caught:
            job.fill_begin('xpu:0', STREAMS['xpu:0'])
        self.assertIs(caught.exception, error)
        self.manager.clear()
        self.assertEqual(self.backend.reads, [])
        self.assertFalse(self.manager.census()['receipts'][0]['valid'])
        self.assertIs(self.manager.current(), t.NOOP)
        self.assertIs(self.manager.retained_jobs[0], job)

    def test_backend_elapsed_error_propagates_without_retries(self):
        job = self.job()
        self.full_job(job)
        self.backend.drained = True
        error = RuntimeError('synthetic elapsed failure')
        self.backend.read_error = error
        with self.assertRaises(RuntimeError) as caught:
            job.finish_after_existing_drains(True)
        self.assertIs(caught.exception, error)
        self.manager.clear()
        self.assertFalse(self.manager.census()['receipts'][0]['valid'])

    def test_nonfinite_duration_invalidates(self):
        job = self.job()
        self.full_job(job)
        self.backend.drained = True
        self.backend.duration = float('nan')
        result = job.finish_after_existing_drains(True)
        self.assertFalse(result['valid'])
        self.assertEqual(result['error'], 'invalid-event-duration')

    def test_missing_selected_stage_has_no_elapsed_reads(self):
        job = self.job()
        job.stage('a')
        self.forward(job)
        self.forward(job)
        self.assertFalse(job.finish_after_existing_drains(True)['valid'])
        self.assertEqual(self.backend.reads, [])

    def test_close_candidate_during_job_disables_recording_without_wait(self):
        job = self.active()
        state = self.manager.close_candidate()
        self.assertEqual(state['audit_error'], 'candidate-close-with-active-job')
        self.assertIsNone(job.fill_begin('xpu:0', STREAMS['xpu:0']))
        self.assertEqual(self.backend.records, [])
        self.manager.clear()
        job = self.job(1, 99907105)
        self.assertFalse(job.selected)
        self.assertEqual(job.reason, 'candidate-closed')

    def test_census_missing_worker_and_unfinished_tail(self):
        job = self.job()
        self.full_job(job)
        self.backend.drained = True
        job.finish_after_existing_drains(True)
        self.manager.clear()
        self.assertFalse(self.manager.census()['complete'])
        self.manager.begin_job(99907113, 0, 'candidate-check')
        self.manager.clear()  # Original model failure: no fake success.
        audit = self.manager.snapshot()['jobs'][-1]
        self.assertTrue(audit['finished'])
        self.assertFalse(audit['existing_drains_succeeded'])
        self.assertFalse(self.manager.snapshot()['complete'])

    def test_prepare_binding_and_deferred_configure(self):
        identity = dict(self.identity)
        identity.pop('source_sha256')
        with patch.object(t, '_manager', None), patch.object(t, '_prepared_identity', None), patch.object(t, '_source_sha256', None):
            prepared = t.prepare(identity)
            self.assertEqual(prepared['source_sha256'], hashlib.sha256((HERE / 'trace.py').read_bytes()).hexdigest())
            self.assertEqual(self.backend.created, [])
            manager = t.configure(self.workers, self.backend.factory)
            self.assertEqual(manager.identity, prepared)
            self.assertIs(t.configure(self.workers, self.backend.factory, identity), manager)
            with self.assertRaises(ValueError):
                t.prepare({**identity, 'plan_sha256': 'd' * 64})
            with self.assertRaises(ValueError):
                t.prepare({**identity, 'source_sha256': 'e' * 64})

    def test_bounded_job_audit_invalidates_overflow(self):
        with patch.object(t, 'MAX_JOBS', 2):
            for clip in range(99907200, 99907204):
                self.manager.begin_job(clip, 0, 'timed-fast')
                self.manager.clear()
        state = self.manager.snapshot()
        self.assertEqual(len(state['jobs']), 2)
        self.assertEqual(state['audit_error'], 'job-audit-cap-exceeded')
        self.assertEqual(self.backend.created, [])


if __name__ == '__main__':
    unittest.main()

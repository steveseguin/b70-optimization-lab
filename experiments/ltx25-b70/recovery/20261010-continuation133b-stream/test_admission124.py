"""Packet125 admission and evidence rejections; CPU/stdlib only."""
import copy
import unittest
import stream_contract as c
import stream_receipts as receipts
import display_replica
import test_gate_receipts as fixtures


class Admission124(unittest.TestCase):
    def test_parallel_scope_and_serial_default(self):
        self.assertEqual(c.launch_display_worker({}), 'serial')
        for frames in (145, 169):
            c.check_display_worker_scope('parallel', frames, 'two-way20-28', 'frame', 0, 'cone',
                                         'legacy', 'xpu:2', 'eager-display')
            c.check_residency_scope(frames, 'two-way20-28', 'frame', 0, 'cone', 'legacy', 'xpu:2')

    def test_each_nonadmitted_parallel_dimension_fails(self):
        good = ['parallel', 169, 'two-way20-28', 'frame', 0, 'cone', 'legacy', 'xpu:2', 'eager-display']
        for index, value in enumerate(['typo', 121, 'two-way', 'latent', 1, 'full', 'xpu2', 'xpu:3', 'sampler-a']):
            args = list(good); args[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError): c.check_display_worker_scope(*args)

    def test_off_scope_keeps_123b_169_arm(self):
        c.check_display_worker_scope('serial', 169, 'two-way20-28', 'frame', 0, 'cone', 'xpu2', 'xpu:3', 'sampler-a')
        c.check_residency_scope(169, 'two-way20-28', 'frame', 0, 'cone', 'xpu2', 'xpu:3')
        with self.assertRaises(ValueError):
            c.check_residency_scope(169, 'two-way20-28', 'frame', 0, 'cone', 'legacy', 'xpu:3')

    def test_replica_screening_boundary(self):
        free = int(9.25 * 2**30)
        display_replica.budget(free, transient_bytes=int(6.5 * 2**30), screening_bytes=3*2**28)
        with self.assertRaises(RuntimeError):
            display_replica.budget(free-1, transient_bytes=int(6.5 * 2**30), screening_bytes=3*2**28)

    def test_parallel_receipt_rejects_low_snapshot_margin(self):
        rows, _, _ = fixtures.passing(frames=145, decoder_graph=0)
        r = rows[0]
        r['server_options'].update(display_worker='parallel', display_device='xpu:2',
                                   display_schedule='eager-display', aux_residency='legacy',
                                   residency_qualification_id=c.residency_qualification_id(r['qualification_id'], 'legacy'))
        r['snapshots'][0]['min_margin_bytes'] = 3*2**28 - 1
        with self.assertRaisesRegex(ValueError, '0.75GiB'): receipts.validate_measurements(r)


class WorkerProof(unittest.TestCase):
    def proof(self):
        return {'kind':'qualify-repeat', 'display_worker':'parallel', 'completion_worker':'parallel',
                'display_worker_timing': {'queued_ns':5, 'start_ns':6, 'audio_start_ns':3,
                    'audio_done_ns':4, 'gated_inline':False},
                'timing_ns':{'anchor_ready':2, 'audio_done':4, 'display_start':7}}

    def test_repeat_must_exercise_parallel_with_truthful_early_audio(self):
        receipts.validate_display_worker(self.proof(), {'display_worker':'parallel'})

    def test_forged_worker_or_timing_fails(self):
        for key in ('display_worker', 'completion_worker', 'display_worker_timing'):
            d = self.proof(); d[key] = None
            with self.subTest(key=key), self.assertRaises(ValueError):
                receipts.validate_display_worker(d, {'display_worker':'parallel'})
        for key in ('queued_ns', 'start_ns', 'audio_start_ns', 'audio_done_ns'):
            d = self.proof(); d['display_worker_timing'][key] = 999
            with self.subTest(key=key), self.assertRaises(ValueError):
                receipts.validate_display_worker(d, {'display_worker':'parallel'})

    def test_controls_must_complete_inline(self):
        d = self.proof(); d.update(kind='qualify-eager', completion_worker='serial')
        d['display_worker_timing'].update(queued_ns=None,start_ns=None,gated_inline=True)
        receipts.validate_display_worker(d, {'display_worker':'parallel'})
        d['completion_worker'] = 'parallel'
        with self.assertRaises(ValueError): receipts.validate_display_worker(d, {'display_worker':'parallel'})

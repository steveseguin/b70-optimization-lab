#!/usr/bin/env python3
"""Stdlib coordinator tests with explicit simulated transport/capture callbacks.

The real byte verifier/iterator have separate tests. These checks do not attest
GPU generation, playback or native replay, and never import tensor libraries.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import continuation_stream_state as state

RUNTIME = '1' * 64
MODEL = '2' * 64
FRAME = b'\0' * 786432
FRAME_HASH = hashlib.sha256(FRAME).hexdigest()


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fault_patch = patch.object(state, 'FAULT_ROOT', self.root / 'fault-test-only')
        self.fault_patch.start()
        self.addCleanup(self.fault_patch.stop)
        self.addCleanup(self.tmp.cleanup)
        self.stream = state.ContinuationStream('cpu-test', RUNTIME, MODEL)

    def reserve(self, stream=None, seed=42):
        stream = stream or self.stream
        return stream.reserve('A stable scene with preserved float output.', seed)

    def ready(self, stream=None, history_change=None, verify_error=None):
        stream = stream or self.stream
        graph = self.reserve(stream)
        stream.submitted('simulated-prompt-id')
        history = {'status': {'status_str': 'success', 'completed': True},
                   'prompt': [0, 'simulated-prompt-id', graph['graph'], {}, []]}
        if history_change:
            history_change(history)
        pending = stream.snapshot()['pending']
        folder = self.root / 'validation' / pending['run_name']
        folder.mkdir(parents=True)
        receipt = {'run_name': pending['run_name'], 'anchor_sha256': FRAME_HASH,
                   'summary_file_sha256': '3' * 64,
                   'tensors': {name: {'sha256': '4' * 64} for name in
                               ('images', 'video_latent', 'audio_latent', 'waveform')}}
        with patch.object(state, 'verify_capture', return_value=receipt, side_effect=verify_error) as verifier:
            stream.completed(history, self.root, RUNTIME)
        return graph, verifier

    def finish(self, stream=None):
        stream = stream or self.stream
        count = 25 if stream.snapshot()['next_chunk'] == 0 else 24
        def simulated_frames(*args):
            yield from (FRAME for _ in range(count))
        with patch.object(state, 'iter_delivery_frames', side_effect=simulated_frames):
            indices = []
            for offer in stream.frames():
                indices.append(offer['frame_index'])
                stream.acknowledge(offer['token'])
            self.assertEqual(stream.snapshot()['phase'], 'awaiting_finish')
            record = stream.finish()
        return record, indices

    def test_single_request_and_predecessor_binding(self):
        first, _ = self.ready()
        self.assertFalse(first['ready_for_submission'])
        with self.assertRaises(ValueError):
            self.reserve()
        record, indices = self.finish()
        self.assertEqual(indices, list(range(25)))
        second, _ = self.ready()
        provider = second['graph']['continuation_float_anchor']['inputs']
        self.assertEqual(provider['predecessor_run'], record['run_name'])
        self.assertEqual(provider['expected_sha256'], FRAME_HASH)
        _, indices = self.finish()
        self.assertEqual(indices, list(range(1, 25)))
        self.assertEqual(self.stream.snapshot()['acknowledged_frames'], 49)

    def test_fault_latch_halts_without_new_reservation(self):
        state.FAULT_ROOT.mkdir()
        (state.FAULT_ROOT / 'FAULT.json').write_text('{}')
        with self.assertRaises(RuntimeError):
            self.reserve()
        self.assertEqual(self.stream.snapshot()['phase'], 'halted')
        self.assertIsNone(self.stream.snapshot()['pending'])

    def test_missing_ack_halts_and_preserves_offer(self):
        self.ready()
        with patch.object(state, 'iter_delivery_frames', return_value=iter_generator(2)):
            iterator = self.stream.frames()
            offer = next(iterator)
            with self.assertRaises(ValueError):
                next(iterator)
        snapshot = self.stream.snapshot()
        self.assertEqual(snapshot['phase'], 'halted')
        self.assertEqual(snapshot['pending']['outstanding'], offer['token'])
        self.assertEqual(snapshot['acknowledged_frames'], 0)
        with self.assertRaises(ValueError):
            self.reserve()

    def test_duplicate_ack_halt_is_sticky_when_generator_resumes(self):
        self.ready()
        with patch.object(state, 'iter_delivery_frames', return_value=iter_generator(25)):
            iterator = self.stream.frames()
            offer = next(iterator)
            self.stream.acknowledge(offer['token'])
            with self.assertRaises(ValueError):
                self.stream.acknowledge(offer['token'])
            with self.assertRaises(ValueError):
                next(iterator)
        self.assertEqual(self.stream.snapshot()['phase'], 'halted')
        self.assertEqual(self.stream.snapshot()['acknowledged_frames'], 1)

    def test_early_close_is_terminal_uncertainty(self):
        self.ready()
        with patch.object(state, 'iter_delivery_frames', return_value=iter_generator(25)):
            iterator = self.stream.frames()
            next(iterator)
            iterator.close()
        self.assertEqual(self.stream.snapshot()['phase'], 'halted')
        self.assertIsNotNone(self.stream.snapshot()['pending']['outstanding'])

    def test_wrong_history_never_calls_verifier(self):
        changes = [lambda h: h['prompt'].__setitem__(1, 'different-id'),
                   lambda h: h['prompt'][2]['339']['inputs'].__setitem__('noise_seed', 99),
                   lambda h: h['status'].__setitem__('completed', False)]
        for i, change in enumerate(changes):
            stream = state.ContinuationStream(f'bad-history-{i}', RUNTIME, MODEL)
            with self.subTest(i=i), patch.object(state, 'verify_capture') as verifier:
                with self.assertRaises(ValueError):
                    self.ready(stream, history_change=change)
                verifier.assert_not_called()
            self.assertEqual(stream.snapshot()['phase'], 'halted')

    def test_verification_failure_preserves_submitted_work(self):
        with self.assertRaisesRegex(ValueError, 'corrupt'):
            self.ready(verify_error=ValueError('corrupt capture'))
        snapshot = self.stream.snapshot()
        self.assertEqual(snapshot['phase'], 'halted')
        self.assertEqual(snapshot['pending']['prompt_id'], 'simulated-prompt-id')
        self.assertEqual(snapshot['next_chunk'], 0)

    def test_wrong_sized_frame_cannot_count_as_delivery(self):
        self.ready()
        with patch.object(state, 'iter_delivery_frames', return_value=iter_generator(25, b'bad')):
            with self.assertRaises(ValueError):
                next(self.stream.frames())
        self.assertEqual(self.stream.snapshot()['phase'], 'halted')
        self.assertEqual(self.stream.snapshot()['acknowledged_frames'], 0)

    def test_retention_backpressure_and_predecessor_protection(self):
        for _ in range(3):
            self.ready()
            self.finish()
        with self.assertRaisesRegex(ValueError, 'retention'):
            self.reserve()
        records = self.stream.snapshot()['retained']
        with self.assertRaises(ValueError):
            self.stream.confirm_retired(records[-1]['run_name'], '5' * 64)
        with self.assertRaisesRegex(ValueError, 'still exists'):
            self.stream.confirm_retired(records[0]['run_name'], '5' * 64)
        Path(records[0]['capture_path']).parent.rmdir()  # Empty simulated capture directory only.
        self.stream.confirm_retired(records[0]['run_name'], '5' * 64)
        self.assertEqual(len(self.stream.snapshot()['retained']), 2)
        self.reserve()

    def test_atomic_checkpoint_and_same_identity_idle_restore(self):
        self.ready()
        self.finish()
        path = self.root / 'stream-state.json'
        self.stream.save_checkpoint(path)
        restored = state.ContinuationStream.restore(path.read_bytes(), RUNTIME, MODEL)
        self.assertEqual(restored.snapshot(), self.stream.snapshot())
        self.assertEqual(list(self.root.glob('*.tmp')), [])
        with self.assertRaises(ValueError):
            state.ContinuationStream.restore(path.read_bytes(), '9' * 64, MODEL)

    def test_interrupted_checkpoint_halts_instead_of_resubmitting(self):
        self.reserve()
        restored = state.ContinuationStream.restore(self.stream.checkpoint_bytes(), RUNTIME, MODEL)
        self.assertEqual(restored.snapshot()['phase'], 'halted')
        self.assertIsNotNone(restored.snapshot()['pending'])
        with self.assertRaises(ValueError):
            self.reserve(restored)

    def test_checkpoint_detects_counter_and_chain_inconsistency(self):
        self.ready()
        self.finish()
        for field in ('acknowledged_frames', 'chain_sha256'):
            packet = json.loads(self.stream.checkpoint_bytes())
            packet['state'][field] = 999 if field == 'acknowledged_frames' else '0' * 64
            packet['state_sha256'] = state.digest(packet['state'])
            with self.subTest(field=field), self.assertRaises(ValueError):
                state.ContinuationStream.restore(state.canonical(packet), RUNTIME, MODEL)

    def test_many_simulated_chunks_keep_metadata_bounded(self):
        largest = 0
        for _ in range(12):
            if len(self.stream.snapshot()['retained']) == 3:
                oldest = self.stream.snapshot()['retained'][0]
                Path(oldest['capture_path']).parent.rmdir()
                self.stream.confirm_retired(oldest['run_name'], '5' * 64)
            self.ready()
            self.finish()
            blob = self.stream.checkpoint_bytes()
            largest = max(largest, len(blob))
            self.stream = state.ContinuationStream.restore(blob, RUNTIME, MODEL)
        self.assertEqual(self.stream.snapshot()['acknowledged_frames'], 25 + 11 * 24)
        self.assertEqual(len(self.stream.snapshot()['retained']), 3)
        self.assertLess(largest, 16384)

    def test_escaped_prompt_budget_rejected_before_mutation(self):
        before = self.stream.snapshot()
        with self.assertRaisesRegex(ValueError, 'JSON-encoded'):
            self.stream.reserve('x' + '\0' * 65535, 42)
        self.assertEqual(before, self.stream.snapshot())
        self.stream.reserve('x' * 65534, 42)
        self.assertLess(len(self.stream.checkpoint_bytes()), state.MAX_CHECKPOINT_BYTES)

    def test_checkpoint_rejects_wrong_predecessor_even_with_rehashed_records(self):
        self.ready()
        self.finish()
        self.ready()
        self.finish()
        packet = json.loads(self.stream.checkpoint_bytes())
        record = packet['state']['retained'][-1]
        record['predecessor']['anchor_sha256'] = 'a' * 64
        record['chunk_sha256'] = state.digest({k: v for k, v in record.items() if k != 'chunk_sha256'})
        packet['state']['chain_sha256'] = record['chunk_sha256']
        packet['state_sha256'] = state.digest(packet['state'])
        with self.assertRaisesRegex(ValueError, 'predecessor'):
            state.ContinuationStream.restore(state.canonical(packet), RUNTIME, MODEL)


def iter_generator(count, payload=FRAME):
    for _ in range(count):
        yield payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StateTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    scripts = Path(__file__).resolve().parent
    receipt = {'status': 'passed-simulated-state-transitions-only' if result.wasSuccessful() else 'failed',
               'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'source_sha256': {name: hashlib.sha256((scripts / name).read_bytes()).hexdigest()
                                 for name in ('continuation_stream_state.py', Path(__file__).name,
                                              'continuation_delivery.py', 'bind-continuation-anchor.py')},
               'gpu_requests': 0, 'transport': 'simulated', 'capture_callbacks': 'simulated',
               'limitations': ['No native generation, playback, transport or deterministic replay tested',
                               'Real bounded byte verification has separate evidence',
                               'Retirement tests remove empty synthetic directories only']}
    with args.receipt.open('x') as output:
        output.write(json.dumps(receipt, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)

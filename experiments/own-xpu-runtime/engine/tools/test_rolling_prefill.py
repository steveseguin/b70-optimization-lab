"""CPU-only native prefill relay and rolling seam tests; no device/process."""
from hashlib import sha256
import struct
import threading
import time
import unittest
from unittest.mock import patch

from rolling_ring_driver import bridge
from rolling_provider import prefill

base, pending, ring = bridge.base, bridge.pending, bridge.ring


class Stage:
    def __init__(self, index, rows, stream, streams):
        self.index = index
        self.prefill_rows = rows
        self.stream_bytes = stream
        self.prefill = bytearray(prefill.map_bytes(rows, stream))
        self.prefill[:16] = struct.pack('<4I', base.PREFILL_MAGIC, 1, rows, stream)
        self.shared = bytearray(base.SHARED)
        self.sequence = self.physical = self.committed = 0
        self.calls = []
        self.streams = streams

    def command(self, op, token, position, fixture):
        self.sequence += 1
        sequence = self.sequence
        self.calls.append((op, token, position, fixture, sequence))
        if op == prefill.OP:
            count = token
            metadata = pending.wire.ROW_META.unpack(bytes(self.shared[
                pending.wire.ROW_OFFSET:pending.wire.ROW_OFFSET+224]))
            assert metadata[7] == position+count-1 and metadata[9] == 0
            tokens = struct.unpack(f'<{count}i', bytes(self.prefill[16:16+4*count])) if self.index == 0 else None
            incoming = bytes(prefill.region(self.prefill, 'forward', fixture, self.prefill_rows,
                                            self.stream_bytes, count))
            if self.index:
                previous = self.streams[(self.index-1, position)]
                assert incoming == previous
            outgoing = bytearray()
            for row in range(count):
                value = (1000*self.index + position + row + 1).to_bytes(2, 'little')
                outgoing += value * (self.stream_bytes//2)
                self.streams[(self.index, position)] = bytes(outgoing)
            kind = 'forward' if self.index == 0 else 'reverse'
            prefill.region(self.prefill, kind, fixture, self.prefill_rows,
                           self.stream_bytes, count)[:] = outgoing
            return (0, 0, 0, count*self.stream_bytes, sequence, int(self.index > 0),
                    self.index, int(self.index == 3), 0, 0, 0, 0)
        assert op == prefill.DRAFT and self.index == 0
        assert struct.unpack('<I', bytes(self.shared[prefill.REVERSE_READY_OFFSET:
                                                    prefill.REVERSE_READY_OFFSET+4]))[0] == position
        metadata = pending.wire.ROW_META.unpack(bytes(self.shared[
            pending.wire.ROW_OFFSET:pending.wire.ROW_OFFSET+224]))
        assert (metadata[7], metadata[8]) == (position, token)
        self.streams[('draft', position)] = bytes(self.shared[prefill.REVERSE_OFFSET:
                                                              prefill.REVERSE_OFFSET+self.stream_bytes])
        return (0, -1, 0, 0, sequence, 0, 0, 0, 0, 0, 0, 0)


def exercise(prompt, rows=2, pipeline=False):
    stream = 16
    plan = dict(prefill_rows=rows, provider_stage=0, speculative_depth=3,
                prefill_pipeline=pipeline)
    model = bridge.RollingCoordinator(stages=4, request=sha256(b'prefill-test').digest(), epoch=1,
        prompt=prompt, max_new=4, context=128, vocab=1000, eos_token_ids=[999],
        stream_bytes=stream, speculative_depth=3)
    history = {}
    stages = [Stage(index, rows, stream, history) for index in range(4)]
    result = prefill.run(stages, model, plan, base, pending, ring)
    return result, model, stages


class PrefillTests(unittest.TestCase):
    def test_layout_relay_partial_chunks_and_prompt_draft_seam(self):
        result, model, stages = exercise([3, 5, 8, 13, 21, 34, 55])
        self.assertEqual({k: result[k] for k in ('prefill_positions', 'prefill_chunks',
                                                'prefill_draft_replay')},
                         dict(prefill_positions=5, prefill_chunks=3, prefill_draft_replay=5))
        self.assertEqual((model.frontier, model.next_id, model.provider.next_seed,
                          model.provider.serial), (5, 5, 6, 5))
        self.assertTrue(all(s.physical == s.committed == 5 for s in stages))
        for index, stage in enumerate(stages):
            self.assertEqual([(c[1], c[2], c[3]) for c in stage.calls if c[0] == prefill.OP],
                             [(2, 0, 0), (2, 2, 1), (1, 4, 0)])
        drafts = [c for c in stages[0].calls if c[0] == prefill.DRAFT]
        self.assertEqual([(c[1], c[2], c[3]) for c in drafts],
                         [(5, 1, 0), (8, 2, 0), (13, 3, 0), (21, 4, 0), (34, 5, 0)])
        for position in range(1, 6):
            start = ((position-1)//2)*2
            offset = (position-1-start)*16
            expected = stages[-1].streams[(3, start)][offset:offset+16]
            self.assertEqual(stages[0].streams[('draft', position)], expected)
        commands = model.commands()
        self.assertTrue(commands)
        self.assertTrue(all(c.row.position == 5 for c in commands))

    def test_host_wall_accounting_keeps_target_and_draft_disjoint(self):
        # Advance only inside commands: measures their Python/transport wall,
        # without depending on scheduler timing or the number of clock reads.
        clock = [0.0]
        command = Stage.command

        def timed_command(stage, op, *args):
            clock[0] += stage.index+1 if op == prefill.OP else 0.5
            return command(stage, op, *args)

        with patch.object(prefill.time, 'perf_counter', side_effect=lambda: clock[0]), \
             patch.object(Stage, 'command', timed_command):
            result, _, _ = exercise([3, 5, 8, 13, 21, 34, 55])
        timing = result['prefill_timing']
        self.assertEqual(timing['schema'], 'rolling-prefill-host-wall-v1')
        self.assertEqual(timing['target_command_wall_s'], [3.0, 6.0, 9.0, 12.0])
        self.assertEqual(timing['target_wall_s'], 30.0)
        self.assertEqual(timing['draft_replay_wall_s'], 2.5)
        self.assertEqual(timing['total_wall_s'], 32.5)
        self.assertEqual(timing['other_wall_s'], 0.0)

    def test_pipeline_adverse_two_chunk_waves_match_serial_and_seam(self):
        # Five chunks including a partial tail: parity is reused across waves.
        prompt = list(range(3, 14))
        serial, serial_model, serial_stages = exercise(prompt)
        original = Stage.command
        barriers = {(wave, phase): threading.Barrier(2) for wave in (0, 1)
                    for phase in (2, 3, 4, 5)}
        locks = [threading.Lock() for _ in range(4)]
        replay_queue = []
        next_draft = [1]
        overlapped = set()

        def delayed(stage, op, token, position, fixture):
            self.assertTrue(locks[stage.index].acquire(False), 'same-stage command overlap')
            try:
                metadata = bytes(stage.shared[pending.wire.ROW_OFFSET:
                                              pending.wire.ROW_OFFSET+224])
                mapped = bytes(stage.prefill)
                reverse = bytes(stage.shared[prefill.REVERSE_OFFSET:
                                             prefill.REVERSE_OFFSET+stage.stream_bytes])
                if op == prefill.OP:
                    wave, offset = divmod(position, 4)
                    phase = stage.index+1+offset//2
                    if phase > 1 and wave < 2:
                        barriers[(wave, phase)].wait(timeout=3)
                        overlapped.add((wave, phase))
                elif (position-1) % 4 == 0 and position <= 8:
                    barriers[((position-1)//4, 5)].wait(timeout=3)
                # Read shared inputs late, after the peer had a chance to run.
                time.sleep(0.001*(4-stage.index))
                self.assertEqual(bytes(stage.prefill), mapped)
                self.assertEqual(bytes(stage.shared[pending.wire.ROW_OFFSET:
                                                    pending.wire.ROW_OFFSET+224]), metadata)
                self.assertEqual(bytes(stage.shared[prefill.REVERSE_OFFSET:
                                                    prefill.REVERSE_OFFSET+stage.stream_bytes]), reverse)
                if stage.index == 0:
                    if op == prefill.OP:
                        self.assertLess(len(replay_queue), 2)
                        tokens = struct.unpack(f'<{token}i', mapped[16:16+4*token])
                        self.assertEqual(tokens, tuple(prompt[position:position+token]))
                        replay_queue.append([position, tokens, 0])
                    else:
                        self.assertEqual(position, next_draft[0])
                        start, tokens, consumed = replay_queue[0]
                        self.assertEqual(position, start+consumed+1)
                        self.assertEqual(tokens[consumed], prompt[position-1])
                        replay_queue[0][2] += 1
                        if replay_queue[0][2] == len(tokens):
                            replay_queue.pop(0)
                        next_draft[0] += 1
                return original(stage, op, token, position, fixture)
            finally:
                locks[stage.index].release()

        with patch.object(Stage, 'command', delayed):
            result, model, stages = exercise(prompt, pipeline=True)
        self.assertEqual(len(overlapped), 8)
        self.assertFalse(replay_queue)
        self.assertEqual(stages[0].streams, serial_stages[0].streams)
        for actual, expected in zip(stages, serial_stages):
            for op in (prefill.OP, prefill.DRAFT):
                self.assertEqual([c[:4] for c in actual.calls if c[0] == op],
                                 [c[:4] for c in expected.calls if c[0] == op])
            self.assertEqual((actual.physical, actual.committed), (9, 9))
        self.assertEqual(model.commands(), serial_model.commands())
        self.assertEqual((model.frontier, model.next_id, model.provider.serial),
                         (serial_model.frontier, serial_model.next_id, serial_model.provider.serial))
        timing = result['prefill_timing']
        self.assertEqual(timing['schema'], 'rolling-prefill-host-wave-wall-v2')
        phases = sum(timing[k] for k in ('target_only_phase_wall_s',
                     'mixed_phase_wall_s', 'draft_only_phase_wall_s', 'other_wall_s'))
        self.assertAlmostEqual(phases, timing['total_wall_s'])
        self.assertGreaterEqual(timing['other_wall_s'], 0)
        self.assertTrue(all(t > 0 for t in timing['target_command_work_wall_s']))

    def test_pipeline_single_chunk_odd_wave_and_rows_one(self):
        for rows, length in ((1, 3), (1, 7), (2, 4), (2, 8), (3, 10)):
            prompt = list(range(3, 3+length))
            expected, baseline, serial_stages = exercise(prompt, rows=rows)
            actual, model, stages = exercise(prompt, rows=rows, pipeline=True)
            for key in ('prefill_positions', 'prefill_chunks', 'prefill_draft_replay'):
                self.assertEqual(actual[key], expected[key])
            self.assertEqual(stages[0].streams, serial_stages[0].streams)
            self.assertEqual(model.commands(), baseline.commands())

    def test_pipeline_failure_joins_peer_without_later_phase_or_retry(self):
        original = Stage.command
        entered, failed, finished = threading.Event(), threading.Event(), threading.Event()
        calls = []

        def fail(stage, op, token, position, fixture):
            calls.append((stage.index, op, position))
            if op == prefill.OP and stage.index == 0 and position == 2:
                entered.set()
                self.assertTrue(failed.wait(3))
                time.sleep(0.01)
                reply = original(stage, op, token, position, fixture)
                finished.set()
                return reply
            if op == prefill.OP and stage.index == 1 and position == 0:
                self.assertTrue(entered.wait(3))
                failed.set()
                raise RuntimeError('injected target failure')
            return original(stage, op, token, position, fixture)

        with patch.object(Stage, 'command', fail):
            with self.assertRaisesRegex(RuntimeError, 'injected target failure'):
                exercise(list(range(3, 14)), pipeline=True)
        self.assertTrue(finished.is_set(), 'peer must finish before error escapes')
        self.assertEqual(sorted(calls), [(0, prefill.OP, 0), (0, prefill.OP, 2),
                                         (1, prefill.OP, 0)])

    def test_pipeline_plan_flag_requires_boolean(self):
        with self.assertRaisesRegex(ValueError, 'prefill pipeline boolean'):
            exercise([3, 5, 8], pipeline=1)

    def test_exact_region_extents_do_not_touch_inactive_or_partial_tail(self):
        mapping = bytearray([0xA5]) * prefill.map_bytes(4, 8)
        source = bytes(range(16))
        prefill.region(mapping, 'reverse', 1, 4, 8, 2)[:] = source
        begin = prefill.HEADER_BYTES + 3*4*8
        self.assertEqual(mapping[begin:begin+16], source)
        self.assertTrue(all(value == 0xA5 for value in mapping[begin+16:begin+32]))
        self.assertTrue(all(value == 0xA5 for value in mapping[prefill.HEADER_BYTES:begin]))

    def test_short_prompt_and_default_zero_retain_rolling_start(self):
        for prompt, rows in (([3, 5, 8], 2), ([3, 5, 8, 13], 0)):
            result, model, stages = exercise(prompt, rows)
            self.assertEqual(result['prefill_positions'], 0)
            self.assertEqual((model.frontier, model.provider.next_seed, model.provider.serial), (0, 1, 0))
            self.assertTrue(all(not stage.calls for stage in stages))

    def test_prefill_adoption_rejects_late_or_overlong_start(self):
        model = bridge.RollingCoordinator(stages=4, request=sha256(b'prefill-guard').digest(), epoch=0,
            prompt=[3, 5, 8, 13], max_new=2, context=32, vocab=100, eos_token_ids=[99], stream_bytes=16)
        with self.assertRaisesRegex(ValueError, 'two-row rolling seam'):
            model.adopt_prefill(3)


if __name__ == '__main__':
    unittest.main()

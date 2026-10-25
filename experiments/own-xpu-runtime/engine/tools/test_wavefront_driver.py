import socket
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path

import pipeline_driver as base
import wavefront_driver as wave


class Guard:
    def __init__(self):
        self.deadline = time.monotonic() + 15

    def check(self):
        if time.monotonic() > self.deadline:
            raise RuntimeError('CPU protocol fixture timed out')


def exact(sock, count):
    result = bytearray()
    while len(result) < count:
        part = sock.recv(count - len(result))
        if not part:
            return None
        result.extend(part)
    return bytes(result)


def worker(sock, shared, index, count, state, errors):
    sequence, pending, snapshot, expected_next = 0, None, None, None
    try:
        while (packet := exact(sock, base.REQUEST.size)) is not None:
            op, token, position, fixture, spec, seq, stage, final = base.REQUEST.unpack(packet)
            sequence += 1
            assert seq == sequence and stage == index and final == int(index == count - 1)
            output, extent = 0, 0
            if op == wave.schedule.ROW:
                assert pending is None and position == len(state['tokens'])
                assert spec in (0, 1)
                if final:
                    assert not spec
                    if fixture > 1:
                        assert token == expected_next
                if index:
                    assert struct.unpack('<4i', shared[base.SLOT:base.SLOT + 16]) == (123, token, position, index - 1)
                snapshot = list(state['tokens']) if spec else None
                state['tokens'].append(token)
                output = (token * 7 + position + 4) % 97 if final and fixture else 0
                pending = (seq, token, position, fixture, spec, output)
                if not final:
                    shared[:16] = struct.pack('<4i', 123, token, position, index)
                    output, extent = -1, 16
                time.sleep(0.0001 * (1 + (position + index) % 5))
            elif op in (wave.schedule.COMMIT, wave.schedule.ABORT):
                assert pending and pending[:4] == (spec, token, position, fixture)
                if op == wave.schedule.ABORT:
                    assert pending[4] and snapshot is not None
                    state['tokens'] = snapshot
                    state['aborts'] += 1
                elif final and fixture:
                    expected_next = pending[5]
                pending, snapshot = None, None
            else:
                raise AssertionError('unexpected operation')
            reply = base.REPLY.pack(0, output, 0, extent, seq, 0 if index == 0 else 1,
                                     index, final, 0.1, 0.05, 0, 0)
            # Force partial Unix-stream messages, unlike the ordinary native write.
            sock.sendall(reply[:9])
            time.sleep(0.00005)
            sock.sendall(reply[9:])
    except Exception as error:
        errors.append(repr(error))
    finally:
        sock.close()


class DriverTests(unittest.TestCase):
    def run_fixture(self, count, misses, max_new=12, eos=96, cancel_force=False):
        prompt, inputs, outputs = [3, 5, 8, 11], [3, 5, 8, 11], []
        for _ in range(max_new):
            token = (inputs[-1] * 7 + len(inputs) + 3) % 97
            outputs.append(token)
            if token == eos or len(outputs) == max_new:
                break
            inputs.append(token)
        plan = dict(prompt_tokens=prompt, scripted_proposal_tokens=outputs,
                    force_miss_positions=misses, max_new=max_new, vocab=97, eos=eos)
        if cancel_force:
            plan['scripted_proposal_tokens'] = list(outputs)
            for position in misses:
                plan['scripted_proposal_tokens'][position - len(prompt)] = (outputs[position - len(prompt)] - 1) % 97
        stages, threads, states, errors = [], [], [], []
        guard = Guard()
        try:
            for i in range(count):
                stage = wave.AsyncStage.__new__(wave.AsyncStage)
                stage.sock, peer = socket.socketpair()
                stage.spec = dict(id=i, first=i == 0, final=i == count - 1)
                stage.shared = bytearray(base.SHARED)
                stage.sequence, stage.stream_bytes, stage.guard = 0, 16, guard
                state = dict(tokens=[], aborts=0)
                thread = threading.Thread(target=worker, args=(peer, stage.shared, i, count, state, errors), daemon=True)
                stages.append(stage)
                states.append(state)
                threads.append(thread)
                thread.start()
            with tempfile.TemporaryDirectory() as temp:
                result = wave.drive(stages, plan, guard, Path(temp))
                self.assertEqual(result['output_ids'], outputs)
                self.assertEqual(result['input_position'], len(inputs))
                self.assertTrue(all(s['tokens'] == inputs for s in states))
                self.assertGreaterEqual(result['peak_commands_inflight'], 2)
                self.assertTrue((Path(temp) / 'schedule.jsonl').stat().st_size)
            return states
        finally:
            for stage in stages:
                stage.sock.close()
            for thread in threads:
                thread.join(timeout=2)
            self.assertFalse(any(t.is_alive() for t in threads))
            self.assertEqual(errors, [])

    def test_real_socket_partial_replies_overlap_and_forced_recovery(self):
        for count in (2, 4, 6):
            for misses in ([], [4, 7, 10], list(range(4, 15))):
                with self.subTest(stages=count, misses=misses):
                    states = self.run_fixture(count, misses)
                    if misses:
                        self.assertGreater(sum(s['aborts'] for s in states), 0)

    def test_eos_and_output_cap_leave_no_speculative_state(self):
        self.run_fixture(4, [], max_new=1)
        self.run_fixture(4, [], eos=84)

    def test_forced_miss_requires_observed_rejection_and_abort(self):
        with self.assertRaisesRegex(ValueError, 'requested forced-miss'):
            self.run_fixture(4, [4], cancel_force=True)

    def test_wrong_reply_stage_refused(self):
        stage = wave.AsyncStage.__new__(wave.AsyncStage)
        stage.sock, peer = socket.socketpair()
        stage.spec = dict(id=0, first=True, final=False)
        stage.guard = Guard()
        stage.sequence, stage.stream_bytes = 0, 16
        stage.shared = bytearray(base.SHARED)
        stage.start_async()
        model = wave.schedule.Wavefront(2, [1], 2, 97, 96, lambda _: 4)
        stage.issue(model.commands()[0])
        stage.write_ready()
        exact(peer, base.REQUEST.size)
        peer.sendall(base.REPLY.pack(0, -1, 0, 16, 1, 0, 1, 0, 0, 0, 0, 0))
        try:
            with self.assertRaisesRegex(ValueError, 'stage/final'):
                stage.read_ready()
        finally:
            stage.sock.close()
            peer.close()


if __name__ == '__main__':
    unittest.main()

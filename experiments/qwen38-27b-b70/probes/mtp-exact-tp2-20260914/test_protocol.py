import array
import ctypes
import os
import socket
import struct
import tempfile
import threading
import unittest

from protocol import Channel, exchange_ipc, received_ipc_handle
from native import Collective


class ProtocolTests(unittest.TestCase):
    def test_received_fd_collision_preserves_metadata_and_lifetime(self):
        received = os.memfd_create("received-ipc-collision")
        os.write(received, b"original object")
        exporter_standin = os.dup(received)
        self.addCleanup(os.close, exporter_standin)
        handle = bytearray(range(64))
        struct.pack_into("i", handle, 0, received)
        modified, duplicate = received_ipc_handle(handle, received)
        self.addCleanup(os.close, duplicate)
        self.assertGreater(duplicate, received)
        self.assertEqual(struct.unpack_from("i", modified)[0], duplicate)
        self.assertEqual(modified[4:], bytes(handle[4:]))
        self.assertFalse(os.get_inheritable(duplicate))
        with self.assertRaises(OSError):
            os.fstat(received)
        self.assertEqual(os.pread(duplicate, 15, 0), b"original object")
        self.assertEqual(os.pread(exporter_standin, 15, 0), b"original object")

    def test_invalid_received_fd_is_rejected(self):
        fd = os.memfd_create("received-invalid")
        handle = bytearray(64)
        struct.pack_into("i", handle, 0, fd)
        os.close(fd)
        with self.assertRaises(OSError):
            received_ipc_handle(handle, fd)

    def pair(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        return a, b

    def together(self, functions):
        errors = []
        def run(fn):
            try:
                fn()
            except BaseException as exc:
                errors.append(exc)
        ts = [threading.Thread(target=run, args=(fn,)) for fn in functions]
        for t in ts:
            t.start()
        for t in ts:
            t.join(2)
            self.assertFalse(t.is_alive())
        return errors

    def test_reuse_changing_sizes(self):
        sockets = self.pair()
        channels = [Channel(sockets[i], i, .5) for i in range(2)]
        def run(ch):
            for n in [5120, 10240, 2621440, 20971520] * 10:
                ch.exchange("READY", elements=n)
                ch.exchange("COPIED", elements=n)
        self.assertEqual(self.together([lambda c=c: run(c) for c in channels]), [])
        self.assertEqual([c.seq for c in channels], [40, 40])

    def test_reuse_before_retirement_rejected(self):
        a, b = self.pair()
        cs = [Channel(a, 0, .1), Channel(b, 1, .1)]
        self.assertEqual(self.together([lambda c=c: c.exchange("READY") for c in cs]), [])
        with self.assertRaisesRegex(RuntimeError, "phase"):
            cs[0].exchange("READY")
        self.assertTrue(cs[0].poisoned)

    def test_mismatched_shape_poisoned(self):
        a, b = self.pair()
        cs = [Channel(a, 0, .1), Channel(b, 1, .1)]
        errors = self.together([lambda: cs[0].exchange("READY", n=1), lambda: cs[1].exchange("READY", n=2)])
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(c.poisoned for c in cs))

    def test_missing_peer_bounded(self):
        a, _ = self.pair()
        ch = Channel(a, 0, .01)
        with self.assertRaises(TimeoutError):
            ch.exchange("READY")
        with self.assertRaisesRegex(RuntimeError, "poisoned"):
            ch.exchange("READY")

    def test_peer_exit_after_ready(self):
        a, b = self.pair()
        ch = Channel(a, 0, .1)
        b.close()
        with self.assertRaises((ConnectionError, BrokenPipeError)):
            ch.exchange("READY")
        self.assertTrue(ch.poisoned)

    def test_fd_transferred_and_not_inheritable(self):
        sockets = self.pair()
        fds = [os.memfd_create("exact-tp2-test") for _ in range(2)]
        for fd in fds:
            self.addCleanup(os.close, fd)
        for i, fd in enumerate(fds):
            os.write(fd, bytes([65 + i]))
        received = {}
        def run(rank):
            h = bytearray(64)
            struct.pack_into("i", h, 0, fds[rank])
            received[rank] = exchange_ipc(sockets[rank], h)
        self.assertEqual(self.together([lambda: run(0), lambda: run(1)]), [])
        for rank, (h, fd) in received.items():
            self.addCleanup(os.close, fd)
            self.assertEqual(struct.unpack_from("i", h)[0], fd)
            self.assertFalse(os.get_inheritable(fd))
            self.assertEqual(os.pread(fd, 1, 0), bytes([66 - rank]))

    def test_copy_failure_cannot_submit_add_or_reuse(self):
        class Native:
            poisoned = False
            calls = []
            def pointer(self, name, *args):
                self.calls.append(name)
                return 1
            def wait(self, _):
                pass
            def copy(self, *args):
                raise TimeoutError("copy")
        class Chan:
            rank = 0
            def exchange(self, phase, **kw):
                self.phase = phase
        n, ch = Native(), Chan()
        c = Collective(n, ch, 1, 100, 200, 300)
        with self.assertRaises(TimeoutError):
            c.run()
        with self.assertRaisesRegex(RuntimeError, "poisoned"):
            c.run()
        self.assertEqual(n.calls, ["marker"])
        self.assertEqual(ch.phase, "READY")

    def test_peer_retirement_failure_cannot_submit_add(self):
        calls = []
        class Native:
            poisoned = False
            def pointer(self, name, *args):
                calls.append(name)
                return 1
            def wait(self, _):
                pass
            def copy(self, *args):
                calls.append("copy")
        class Chan:
            rank = 0
            def exchange(self, phase, **kw):
                calls.append(phase)
                if phase == "COPIED":
                    raise ConnectionError("peer vanished")
        n = Native()
        c = Collective(n, Chan(), 1, 100, 200, 300)
        with self.assertRaises(ConnectionError):
            c.run()
        self.assertEqual(calls, ["marker", "READY", "copy", "COPIED"])
        self.assertTrue(n.poisoned and c.poisoned)

    def fake_native(self, calls):
        class Native:
            poisoned = False
            def pointer(self, name, *args):
                calls.append((name, args))
                return 1
            def wait(self, _):
                pass
            def copy(self, *args):
                calls.append(("copy", args))
        class Chan:
            rank = 1
            def exchange(self, phase, **kw):
                calls.append((phase, ()))
        return Native(), Chan()

    def test_collective_add_mode_passes_explicit_kernel_code_after_retirement(self):
        calls = []
        n, ch = self.fake_native(calls)
        Collective(n, ch, 7, 100, 200, 300, add_mode="m2").run()
        self.assertEqual([c[0] for c in calls], ["marker", "READY", "copy", "COPIED", "add_mode"])
        self.assertEqual(calls[-1], ("add_mode", (100, 300, 7, 1, 2)))

    def test_collective_without_mode_keeps_frozen_add(self):
        calls = []
        n, ch = self.fake_native(calls)
        Collective(n, ch, 7, 100, 200, 300).run()
        self.assertEqual(calls[-1], ("add", (100, 300, 7, 1)))

    def test_unknown_add_mode_refused_before_any_call(self):
        calls = []
        n, ch = self.fake_native(calls)
        with self.assertRaisesRegex(ValueError, "unknown add mode"):
            Collective(n, ch, 7, 100, 200, 300, add_mode="m4")
        self.assertEqual(calls, [])

    def test_native_signatures_keep_add_and_require_add_mode(self):
        import ctypes as C
        from native import ADD_MODES, SIGNATURES
        self.assertEqual(ADD_MODES, {"m0": 0, "m1": 1, "m2": 2, "m3": 3})
        self.assertEqual(SIGNATURES["add"][4], C.c_int)
        self.assertEqual(len(SIGNATURES["add"]), 6)
        self.assertEqual(len(SIGNATURES["add_mode"]), 7)
        self.assertEqual(SIGNATURES["add_mode"][4:6], [C.c_int, C.c_int])

    def test_reserved_identity_rejected(self):
        a, _ = self.pair()
        ch = Channel(a, 0, .01)
        with self.assertRaisesRegex(ValueError, "reserved"):
            ch.exchange("READY", seq=5)
        self.assertTrue(ch.poisoned)


if __name__ == "__main__":
    unittest.main()

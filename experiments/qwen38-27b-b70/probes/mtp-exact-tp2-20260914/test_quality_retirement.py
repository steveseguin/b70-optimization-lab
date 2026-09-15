import unittest
from quality_retirement import retire_completed_allocations


class Native:
    poisoned = False
    def __init__(self, calls):
        self.calls = calls
    def call(self, kind, *args):
        self.calls.append((kind, args))


class Channel:
    poisoned = False
    phase = "READY"
    def __init__(self, calls, fail_on_import_ack=False):
        self.calls, self.fail = calls, fail_on_import_ack
    def exchange(self, phase, **values):
        self.calls.append((phase, values))
        if self.fail and "importers_closed" in values:
            self.poisoned = True
            raise ConnectionError("missing peer retirement acknowledgement")


class RetirementTests(unittest.TestCase):
    def run_retirement(self, native, channel, **kwargs):
        return retire_completed_allocations(native, channel, 1, 2, 3, 4, 5, 6, 1,
                                            close_fd=lambda fd: native.calls.append(("close_fd", fd)),
                                            **kwargs)

    def test_complete_and_agreed_close_order(self):
        calls = []; native = Native(calls); channel = Channel(calls)
        self.run_retirement(native, channel, completed_and_agreed=True)
        self.assertEqual([c[0] for c in calls], ["READY", "COPIED", "close", "close_fd", "READY", "COPIED", "put_export", "free", "free"])
        self.assertEqual(calls[-2:], [("free", (1, 5)), ("free", (1, 6))])

    def test_missing_peer_ack_never_frees_export(self):
        calls = []; native = Native(calls); channel = Channel(calls, True)
        with self.assertRaises(ConnectionError):
            self.run_retirement(native, channel, completed_and_agreed=True)
        self.assertFalse(any(c[0] in ("put_export", "free") for c in calls))

    def test_incomplete_or_device_fault_never_enters_teardown(self):
        for completed, poisoned in [(False, False), (True, True)]:
            calls = []; native = Native(calls); native.poisoned = poisoned
            with self.assertRaises(RuntimeError):
                self.run_retirement(native, Channel(calls), completed_and_agreed=completed)
            self.assertEqual(calls, [])

    def test_poisoned_or_incomplete_peer_phase_never_enters_teardown(self):
        for poisoned, phase in [(True, "READY"), (False, "COPIED")]:
            calls = []; native = Native(calls); channel = Channel(calls)
            channel.poisoned, channel.phase = poisoned, phase
            with self.assertRaises(RuntimeError):
                self.run_retirement(native, channel, completed_and_agreed=True)
            self.assertEqual(calls, [])


class GateRejectionTests(unittest.TestCase):
    """gate.reject_quality: the integrated, active retirement path for quality mismatches."""
    def pieces(self, calls, fail=False):
        import os
        from types import SimpleNamespace
        torch = SimpleNamespace(xpu=SimpleNamespace(synchronize=lambda: calls.append(("synchronize", ()))))
        dist = SimpleNamespace(destroy_process_group=lambda: calls.append(("destroy_process_group", ())))
        sock = SimpleNamespace(close=lambda: calls.append(("sock_close", ())))
        read_fd, write_fd = os.pipe()
        self.addCleanup(lambda: [os.close(fd) for fd in (read_fd, write_fd) if self.is_open(fd)])
        return torch, dist, Native(calls), Channel(calls, fail), sock, read_fd

    @staticmethod
    def is_open(fd):
        import os
        try:
            os.fstat(fd)
            return True
        except OSError:
            return False

    def test_mutual_rejection_retires_then_destroys_group_without_os_exit(self):
        import gate
        from unittest import mock
        calls = []
        torch, dist, native, channel, sock, fd = self.pieces(calls)
        with mock.patch("os._exit") as hard_exit, self.assertRaises(gate.QualityRejected):
            gate.reject_quality(torch, dist, native, channel, sock, 1, 2, fd, 4, 5, 6, 1, "rank0-rows1-nan_matrix-0")
        hard_exit.assert_not_called()
        self.assertEqual([c[0] for c in calls], ["synchronize", "READY", "COPIED", "close", "READY", "COPIED",
                                                 "put_export", "free", "free", "sock_close", "destroy_process_group"])
        self.assertFalse(self.is_open(fd))

    def test_missing_peer_ack_during_rejection_is_an_unknown_fault(self):
        import gate
        calls = []
        torch, dist, native, channel, sock, fd = self.pieces(calls, fail=True)
        with self.assertRaises(ConnectionError):
            gate.reject_quality(torch, dist, native, channel, sock, 1, 2, fd, 4, 5, 6, 1, "p")
        self.assertFalse(any(c[0] in ("put_export", "free", "destroy_process_group") for c in calls))

    def test_gate_uses_helper_for_normal_and_rejection_retirement(self):
        import gate
        import quality_retirement
        self.assertIs(gate.retire_completed_allocations, quality_retirement.retire_completed_allocations)
        source = __import__("pathlib").Path(gate.__file__).read_text()
        self.assertEqual(source.count("retire_completed_allocations("), 2)
        self.assertNotIn('native.call("put_export"', source)


if __name__ == "__main__":
    unittest.main()

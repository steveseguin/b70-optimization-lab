import json
import socket
import time
import unittest

from streaming_v1.delivery import Delivery, sse_event


class DeliveryTests(unittest.TestCase):
    def pair(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        left.setblocking(False)
        right.setblocking(False)
        return left, right

    def test_real_socket_sse_unicode_and_delimiter_escaping(self):
        left, right = self.pair()
        delivery = Delivery(left)
        value = {'content': '雪\n\ndata: injected\r\n🙂'}
        frame = sse_event(value)
        self.assertEqual(frame.count(b'\n\n'), 1)
        self.assertTrue(delivery.offer(frame))
        self.assertTrue(delivery.finish_delivery())
        wire = right.recv(65536)
        self.assertEqual(json.loads(wire[6:-2]), value)
        self.assertFalse(delivery.offer(b'data: replay\n\n'))
        self.assertTrue(delivery.finish_delivery())
        with self.assertRaises(BlockingIOError):
            right.recv(1)
        self.assertFalse(delivery.receipt()['peer_receipt_proven'])

    def test_real_disconnected_peer_is_delivery_failure_only(self):
        left, right = self.pair()
        right.close()
        delivery = Delivery(left)
        self.assertFalse(delivery.offer(b'data: hello\n\n'))
        self.assertIsNotNone(delivery.failed)
        self.assertEqual(delivery.pending, b'')
        self.assertFalse(delivery.finish_delivery())
        self.assertGreaterEqual(left.fileno(), 0)  # Borrowed socket stays caller-owned.

    def test_real_slow_reader_stays_bounded_and_does_not_block(self):
        left, right = self.pair()
        left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        delivery = Delivery(left, queue_bytes=8192, total_bytes=1048576)
        start = time.monotonic()
        for _ in range(256):
            if not delivery.offer(b'x' * 2048):
                break
            self.assertLessEqual(len(delivery.pending), 8192)
        self.assertIsNotNone(delivery.failed)
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual(delivery.pending, b'')
        reason = delivery.failed
        self.assertFalse(delivery.offer(b'late'))
        self.assertEqual(reason, delivery.failed)

    def test_partial_writes_preserve_exact_order_without_replay(self):
        class Partial:
            wire = bytearray()
            calls = 0
            def gettimeout(self): return 0.0
            def send(self, data, flags):
                assert flags == socket.MSG_DONTWAIT
                self.calls += 1
                count = min(3, len(data))
                self.wire.extend(data[:count])
                return count
        socket_stub = Partial()
        delivery = Delivery(socket_stub)
        expected = b'first frame|second frame'
        self.assertTrue(delivery.offer(b'first frame|'))
        self.assertLessEqual(socket_stub.calls, 4)
        before = socket_stub.calls
        self.assertTrue(delivery.offer(b'second frame'))
        self.assertLessEqual(socket_stub.calls - before, 4)
        for _ in range(10): delivery.pump()
        self.assertTrue(delivery.finish_delivery(timeout=0))
        self.assertEqual(socket_stub.wire, expected)
        self.assertEqual(delivery.sent, len(expected))

    def test_zero_send_and_total_limit_preserve_first_failure(self):
        class NoProgress:
            def gettimeout(self): return 0.0
            def send(self, data, flags): return 0
        delivery = Delivery(NoProgress(), queue_bytes=8, total_bytes=8)
        self.assertFalse(delivery.offer(b'abc'))
        self.assertIn('progress', delivery.failed)
        self.assertFalse(delivery.offer(b'longer than cap'))
        self.assertIn('progress', delivery.failed)
        left, right = self.pair()
        delivery = Delivery(left, queue_bytes=8, total_bytes=8)
        self.assertTrue(delivery.offer(b'12345678'))
        self.assertFalse(delivery.offer(b'9'))
        self.assertIn('total', delivery.failed)

    def test_final_drain_has_a_deadline_with_real_blocked_socket(self):
        left, right = self.pair()
        left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        # Fill only the socket, then create one pending event below queue limit.
        try:
            while True: left.send(b'x' * 4096)
        except BlockingIOError:
            pass
        delivery = Delivery(left)
        self.assertTrue(delivery.offer(b'data: pending\n\n'))
        start = time.monotonic()
        self.assertFalse(delivery.finish_delivery(timeout=0.02))
        self.assertLess(time.monotonic() - start, 0.5)
        self.assertEqual(delivery.failed, 'final delivery deadline')

    def test_blocking_socket_and_invalid_limits_refused_before_delivery(self):
        left, right = self.pair()
        left.setblocking(True)
        with self.assertRaises(ValueError): Delivery(left)
        left.setblocking(False)
        with self.assertRaises(ValueError): Delivery(left, queue_bytes=True)
        with self.assertRaises(ValueError): Delivery(left, queue_bytes=9, total_bytes=8)
        with self.assertRaises(ValueError): Delivery(left).finish_delivery(timeout=float('nan'))

    def test_per_send_nonblocking_survives_socket_mode_change(self):
        left, right = self.pair()
        left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        delivery = Delivery(left)
        try:
            while True: left.send(b'x' * 4096)
        except BlockingIOError:
            pass
        left.setblocking(True)
        start = time.monotonic()
        self.assertTrue(delivery.offer(b'data: queued\n\n'))
        self.assertLess(time.monotonic() - start, 0.5)
        self.assertFalse(delivery.finish_delivery(timeout=0.01))

    def test_positive_python_timeout_refused_without_readiness_wait(self):
        left, right = self.pair()
        left.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
        delivery = Delivery(left)
        try:
            while True: left.send(b'x' * 4096)
        except BlockingIOError:
            pass
        left.settimeout(1.0)
        start = time.monotonic()
        self.assertFalse(delivery.offer(b'data: refused\n\n'))
        self.assertLess(time.monotonic() - start, 0.1)
        self.assertIn('positive socket timeout', delivery.failed)


if __name__ == '__main__': unittest.main()

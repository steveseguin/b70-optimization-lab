"""Bounded nonblocking output for a future serial SSE adapter.

The caller exclusively lends a nonblocking socket and owns its lifetime. No
other thread may change its Python timeout during that loan. Token callbacks
only offer bytes; they never wait for a reader. A full queue or failed socket
abandons delivery, leaving native generation and SAVE/RELEASE to finish.
This module does not admit requests or decide when a completion is successful.
"""
from __future__ import annotations

import json
import select
import socket
import time


def sse_event(value):
    """One JSON SSE event; JSON escaping prevents embedded event delimiters."""
    return b'data: ' + json.dumps(value, ensure_ascii=False, allow_nan=False,
                                  separators=(',', ':')).encode('utf-8') + b'\n\n'


class Delivery:
    def __init__(self, connection, *, queue_bytes=65536, total_bytes=1048576):
        if connection.gettimeout() != 0.0:
            raise ValueError('borrowed socket must already be nonblocking')
        if (type(queue_bytes) is not int or type(total_bytes) is not int or
                not 1 <= queue_bytes <= 1048576 or not queue_bytes <= total_bytes <= 4194304):
            raise ValueError('invalid bounded delivery limits')
        self.connection = connection
        self.queue_bytes, self.total_bytes = queue_bytes, total_bytes
        self.pending = bytearray()
        self.offered = self.sent = 0
        self.failed = None
        self.finished = False

    def abandon(self, reason):
        if self.failed is None:
            self.failed = str(reason)[:512]
        self.pending.clear()

    def offer(self, data):
        """Enqueue one bounded frame and attempt at most four nonblocking sends."""
        if self.failed is not None or self.finished:
            return False
        if type(data) is not bytes:
            self.abandon('wire data must be bytes')
            return False
        if len(data) > self.total_bytes - self.offered:
            self.abandon('total delivery byte limit')
            return False
        self.pump()
        if self.failed is not None:
            return False
        if len(data) > self.queue_bytes - len(self.pending):
            self.abandon('slow reader exceeded delivery queue')
            return False
        self.pending.extend(data)
        self.offered += len(data)
        self.pump()
        return self.failed is None

    def pump(self):
        # Bounded work per call, including a socket whose peer always reads.
        if self.failed is not None or self.finished:
            return
        for _ in range(2):
            if not self.pending:
                return
            try:
                # Python performs a readiness wait for positive timeouts even
                # with MSG_DONTWAIT. Refuse mode drift before invoking send.
                timeout = self.connection.gettimeout()
                if timeout is not None and timeout != 0.0:
                    self.abandon('positive socket timeout during exclusive loan')
                    return
                # Per-call nonblocking survives a borrower changing socket mode.
                count = self.connection.send(self.pending[:16384], socket.MSG_DONTWAIT)
            except (BlockingIOError, InterruptedError):
                return
            except OSError as error:
                self.abandon(type(error).__name__)
                return
            if type(count) is not int or not 0 < count <= min(len(self.pending), 16384):
                self.abandon('socket made no valid progress')
                return
            del self.pending[:count]
            self.sent += count

    def finish_delivery(self, *, timeout=0.5):
        """Bounded final drain, called only AFTER native disposition by the caller.

        This proves only that offered bytes reached the local socket buffer.
        It does not prove peer receipt or semantic/native success. No terminal
        SSE message is fabricated here. Repeated calls cannot replay bytes.
        """
        if type(timeout) not in (int, float) or not 0 <= timeout <= 1:
            raise ValueError('final drain timeout must be 0..1 seconds')
        if self.finished:
            return self.failed is None
        deadline = time.monotonic() + timeout
        while self.failed is None and self.pending:
            self.pump()
            if not self.pending or self.failed is not None:
                break
            left = deadline - time.monotonic()
            if left <= 0:
                self.abandon('final delivery deadline')
                break
            try:
                select.select([], [self.connection], [], left)
            except (OSError, ValueError) as error:
                self.abandon(type(error).__name__)
        self.finished = True
        return self.failed is None

    def receipt(self):
        return dict(offered_bytes=self.offered, sent_bytes=self.sent,
                    pending_bytes=len(self.pending), failed=self.failed,
                    finished=self.finished, peer_receipt_proven=False)

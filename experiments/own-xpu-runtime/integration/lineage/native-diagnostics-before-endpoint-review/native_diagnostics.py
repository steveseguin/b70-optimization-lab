"""Drain borrowed stderr without waiting on the evidence writer or its queue.

The caller owns the original blocking read-only FIFO FD. start() duplicates it;
this object owns only that duplicate, with exclusive responsibility for reads.
No other reader may consume the pipe or change its shared file-status flags.
The original may be closed after start() returns. The writer/file remains
caller-owned and must outlive any retained capture thread.

A fixed queue decouples reads from bounded evidence writes. Queue saturation or
writer failure halts capture, records an incident and discards further bytes
while draining to EOF. There are no callbacks, signals, retries or process APIs.
Non-daemon threads deliberately retain the host process until their work ends.
"""
from __future__ import annotations

import fcntl
import math
import os
import queue
import stat
import threading
import time


class DiagnosticsError(RuntimeError):
    pass


class CaptureBackpressure(DiagnosticsError):
    pass


def require(condition, message):
    if not condition:
        raise DiagnosticsError(message)


class PipeDiagnostics:
    def __init__(self, read_fd, writer, name, *, chunk_bytes=16384, queue_chunks=4):
        require(type(read_fd) is int and read_fd >= 0, 'borrowed pipe FD required')
        require(type(chunk_bytes) is int and 1 <= chunk_bytes <= 65536, 'bounded read chunk required')
        require(type(queue_chunks) is int and 1 <= queue_chunks <= 64, 'bounded queue required')
        require(callable(getattr(writer, 'append', None)), 'bounded evidence append writer required')
        require(type(name) is str and bool(name), 'already-created evidence filename required')
        self._borrowed, self._writer, self._name = read_fd, writer, name
        self._chunk, self._queue_chunks = chunk_bytes, queue_chunks
        self._queue = queue.Queue(maxsize=queue_chunks)
        self._lock = threading.RLock()
        self._incident = threading.Event()
        self._reader_done = threading.Event()
        self._reader = self._capture = None
        self._used = self._eof = False
        self._owned_fd = None
        self._error = self._capture_error = None
        self._bytes_read = self._successful_append_bytes = self._discarded = 0

    @property
    def incident_event(self):
        """Coordinator may observe/wait only; never clear this sticky event."""
        return self._incident

    @property
    def error(self):
        """Original first incident object, including queue/read/capture errors."""
        with self._lock:
            return self._error

    @property
    def capture_error(self):
        """Original writer error, even if queue saturation happened first."""
        with self._lock:
            return self._capture_error

    def _fail(self, error, *, capture=False):
        with self._lock:
            if self._error is None:
                self._error = error
            if capture and self._capture_error is None:
                self._capture_error = error
            self._incident.set()

    def start(self):
        with self._lock:
            require(not self._used, 'diagnostics drainer is single use')
            self._used = True
            fd = None
            try:
                fd = os.dup(self._borrowed)
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                require(stat.S_ISFIFO(os.fstat(fd).st_mode) and flags & os.O_ACCMODE == os.O_RDONLY,
                        'read-only FIFO required')
                require(not flags & os.O_NONBLOCK, 'blocking FIFO required; shared flags are never changed')
                self._owned_fd = fd
                self._capture = threading.Thread(target=self._capture_loop, name='bounded-diagnostics-capture', daemon=False)
                self._reader = threading.Thread(target=self._read_loop, name='bounded-diagnostics-reader', daemon=False)
                self._capture.start()
                self._reader.start()
                fd = None  # The reader alone now owns and closes this duplicate.
            except BaseException as error:
                self._fail(error)
                self._reader_done.set()
                if fd is not None:
                    os.close(fd)
                self._owned_fd = None
                raise
        return self

    def _read_loop(self):
        fd = self._owned_fd
        try:
            while True:
                try:
                    data = os.read(fd, self._chunk)
                except InterruptedError:
                    continue  # Interrupted read, not a producer/request retry.
                if not data:
                    with self._lock:
                        self._eof = True
                    break
                with self._lock:
                    self._bytes_read += len(data)
                if self._incident.is_set():
                    with self._lock:
                        self._discarded += len(data)
                    data = None
                    continue
                try:
                    self._queue.put_nowait(data)
                except queue.Full:
                    self._fail(CaptureBackpressure('evidence queue full; capture halted, pipe still draining'))
                    with self._lock:
                        self._discarded += len(data)
                data = None
        except BaseException as error:
            self._fail(error)
        finally:
            try:
                os.close(fd)
            except OSError as error:
                self._fail(error)
            with self._lock:
                self._owned_fd = None
            self._reader_done.set()

    def _capture_loop(self):
        while True:
            try:
                data = self._queue.get(timeout=.05)
            except queue.Empty:
                if self._reader_done.is_set():
                    return
                continue
            if self._incident.is_set():
                with self._lock:
                    self._discarded += len(data)
                data = None
                continue
            try:
                count = self._writer.append(self._name, data)
                require(type(count) is int and count == len(data), 'evidence append count mismatch')
                with self._lock:
                    self._successful_append_bytes += count
            except BaseException as error:
                # append may already have persisted a partial prefix. Never call
                # writer.status() here: its lock may be involved in the failure.
                self._fail(error, capture=True)
            data = None

    def status(self):
        with self._lock:
            reader_alive = self._reader is not None and self._reader.is_alive()
            capture_alive = self._capture is not None and self._capture.is_alive()
            return dict(started=self._used, eof=self._eof, retained=reader_alive or capture_alive,
                        reader_retained=reader_alive, capture_retained=capture_alive,
                        owned_read_fd_open=self._owned_fd is not None,
                        incident=self._incident.is_set(),
                        error_type=None if self._error is None else type(self._error).__name__,
                        capture_error_type=None if self._capture_error is None else type(self._capture_error).__name__,
                        bytes_read=self._bytes_read, successful_append_bytes=self._successful_append_bytes,
                        successful_append_bytes_scope='confirmed complete appends only; lower bound after partial writer failure',
                        definitely_discarded_bytes=self._discarded,
                        payload_buffer_bound_bytes=(self._queue_chunks + 2) * self._chunk,
                        scope='routed diagnostics only; driver/native file growth excluded')

    def join(self, timeout):
        require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 <= timeout <= 60,
                'finite join timeout0..60 seconds required')
        with self._lock:
            require(self._used, 'drainer not started')
            threads = (self._reader, self._capture)
        deadline = time.monotonic() + timeout
        for thread in threads:
            if thread is not None and thread.ident is not None:
                thread.join(max(0., deadline - time.monotonic()))
        return self.status()

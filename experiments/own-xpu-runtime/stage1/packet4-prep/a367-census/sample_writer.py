"""Persist memory samples outside the timed sampler, to local scratch only.

The caller retains its authoritative rows in memory. Rows must not be mutated
after enqueue. After sampling ends, finish() drains the writer before the caller
copies the completed local file to the output mount and records its hash.
"""
import json
from pathlib import Path
import queue
import threading


class SampleWriter:
    """One unbounded in-memory queue and one independent local-file writer.

    enqueue() does not serialize, open, flush, or wait for the writer. The
    optional open_file hook receives the local Path and returns a writable text
    context manager; it permits deterministic blocked-I/O tests without a device.
    """

    def __init__(self, path, *, open_file=None):
        self.path = Path(path)
        self._open_file = open_file or (lambda path: path.open('x', encoding='utf-8'))
        self._rows = queue.SimpleQueue()
        self._end = object()
        self._started = False
        self._finished = False
        self.failure = None
        self.written_rows = 0
        self.thread = threading.Thread(target=self._run, name='a367-local-sample-writer', daemon=True)

    def start(self):
        if self._started:
            raise RuntimeError('sample writer already started')
        self._started = True
        self.thread.start()

    def enqueue(self, row):
        if self._finished:
            raise RuntimeError('sample writer already finished')
        self._rows.put(row)

    def _run(self):
        try:
            with self._open_file(self.path) as stream:
                while True:
                    row = self._rows.get()
                    if row is self._end:
                        break
                    stream.write(json.dumps(row, allow_nan=False) + '\n')
                    stream.flush()
                    self.written_rows += 1
        except BaseException as exc:
            # The sampler observes this in memory; raising is deferred to finish.
            self.failure = exc

    def finish(self):
        """Drain queued rows, close the local file, and surface writer failure."""
        if not self._started:
            raise RuntimeError('sample writer has not started')
        if not self._finished:
            self._finished = True
            self._rows.put(self._end)
        self.thread.join()
        if self.failure is not None:
            raise RuntimeError('local sample writer failed: ' + str(self.failure)) from self.failure

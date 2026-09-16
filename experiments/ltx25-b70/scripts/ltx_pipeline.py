"""Overlap clip N+1's text encode with clip N's sampling.

The text encoder costs 1.45 s per clip and that cost is irreducible: the Gemma
stack runs fp32 activations, the B70 does fp32 matmul at 20.9 TFLOP/s against
142.6 for bf16, and running it in bf16 would be lower precision, which this lane
forbids. See notes/text-encoder-is-fp32-bound.md.

But it does not have to be on the critical path. It occupies xpu:2 while the
sampler occupies xpu:0 and xpu:1, and cross-device concurrency on this host
measures ~100% efficient. So the encode for the NEXT clip is started on a worker
thread as soon as the current clip's conditioning has been handed over, and it
runs while the sampler works.

**This is not a cache.** Every clip's conditioning is computed from scratch by
its own encode; a value is consumed exactly once, by the clip it was computed
for, and is dropped afterwards. Nothing is reused between clips. The only thing
that changes is *when* the work runs, never whether it runs or what it produces.
A prefetched value that raced would change the sampler's input, and the four raw
oracles would catch it.
"""
import threading
import traceback

import torch

MODES = ('original', 'pipeline')

_LOCK = threading.Lock()
_JOBS = {}            # index -> _Job
_WORKER = None
_QUEUE = []
_QUEUE_EVENT = threading.Condition(_LOCK)
MAX_PENDING = 4


def require(value, message):
    if not value:
        raise RuntimeError(message)


class _Job:
    __slots__ = ('index', 'fn', 'done', 'value', 'error', 'started', 'finished')

    def __init__(self, index, fn):
        self.index = index
        self.fn = fn
        self.done = threading.Event()
        self.value = None
        self.error = None
        self.started = None
        self.finished = None


def _worker_loop():
    import time
    while True:
        with _QUEUE_EVENT:
            while not _QUEUE:
                _QUEUE_EVENT.wait()
            job = _QUEUE.pop(0)
        job.started = time.monotonic()
        try:
            # ComfyUI executes nodes inside torch.inference_mode(), and that is
            # THREAD-LOCAL. Without it here the encode runs in a different
            # autograd context from the one its buffers were built in, and the
            # graphed text encoder dies writing them: "Inplace update to
            # inference tensor outside InferenceMode is not allowed".
            with torch.inference_mode():
                job.value = job.fn()
        except BaseException as exc:                     # noqa: BLE001
            job.error = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        finally:
            job.finished = time.monotonic()
            job.done.set()


def _ensure_worker():
    global _WORKER
    if _WORKER is None or not _WORKER.is_alive():
        _WORKER = threading.Thread(target=_worker_loop, name='ltx-encode-ahead', daemon=True)
        _WORKER.start()


def submit(index, fn):
    """Queue the encode for `index` if it is not already queued or finished."""
    with _QUEUE_EVENT:
        _ensure_worker()
        if index in _JOBS:
            return False
        job = _Job(index, fn)
        _JOBS[index] = job
        _QUEUE.append(job)
        _QUEUE_EVENT.notify()
        return True


def collect(index):
    """Wait for `index` and hand it over exactly once."""
    with _LOCK:
        job = _JOBS.get(index)
    require(job is not None, f'No encode was queued for clip {index}')
    job.done.wait()
    with _LOCK:
        _JOBS.pop(index, None)
    require(job.error is None, f'Encode-ahead for clip {index} failed:\n{job.error}')
    return job.value, {'queued_ahead': job.started is not None,
                       'encode_seconds': round((job.finished or 0) - (job.started or 0), 4)}


def pending():
    with _LOCK:
        return sorted(_JOBS)


def clear():
    with _LOCK:
        _JOBS.clear()
        del _QUEUE[:]


def run(index, depth, fn):
    """Return clip `index`'s conditioning, and start the next `depth` ahead.

    The first clip has nothing queued, so it computes inline; from then on the
    value is already being produced while the previous clip was sampling.
    """
    require(isinstance(index, int) and index >= 0, 'Clip index must be a non-negative integer')
    require(isinstance(depth, int) and 1 <= depth <= MAX_PENDING, 'Unsupported pipeline depth')
    submitted_inline = submit(index, fn)
    value, detail = collect(index)
    # Start the next clips only AFTER handing this one over, so the worker runs
    # against this prompt's sampling rather than competing with this encode.
    started = [i for i in range(index + 1, index + 1 + depth) if submit(i, fn)]
    detail.update({'computed_inline': submitted_inline, 'started_ahead': started,
                   'pending_after': pending()})
    return value, detail

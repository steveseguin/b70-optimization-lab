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
# One worker per stage, because the stages live on different cards: the encode
# runs on xpu:2 and the decode on xpu:3, so they must be able to run at once.
STAGES = ('encode', 'decode')
MAX_PENDING = 4

_LOCK = threading.Lock()
_STAGES = {}          # stage -> {'jobs': {index: _Job}, 'queue': [], 'worker': Thread}
_QUEUE_EVENT = threading.Condition(_LOCK)


def _state(stage):
    require(stage in STAGES, 'Unknown pipeline stage: ' + repr(stage))
    return _STAGES.setdefault(stage, {'jobs': {}, 'queue': [], 'worker': None})


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


def _worker_loop(stage):
    import time
    st = _state(stage)
    while True:
        with _QUEUE_EVENT:
            while not st['queue']:
                _QUEUE_EVENT.wait()
            job = st['queue'].pop(0)
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


def _ensure_worker(stage):
    st = _state(stage)
    if st['worker'] is None or not st['worker'].is_alive():
        st['worker'] = threading.Thread(target=_worker_loop, args=(stage,),
                                        name='ltx-' + stage + '-ahead', daemon=True)
        st['worker'].start()


def submit(stage, index, fn):
    """Queue `stage` work for `index` if it is not already queued or finished."""
    with _QUEUE_EVENT:
        _ensure_worker(stage)
        st = _state(stage)
        if index in st['jobs']:
            return False
        job = _Job(index, fn)
        st['jobs'][index] = job
        st['queue'].append(job)
        _QUEUE_EVENT.notify_all()
        return True


def collect(stage, index):
    """Wait for `stage`/`index` and hand it over exactly once."""
    with _LOCK:
        job = _state(stage)['jobs'].get(index)
    require(job is not None, f'No {stage} was queued for clip {index}')
    job.done.wait()
    with _LOCK:
        _state(stage)['jobs'].pop(index, None)
    require(job.error is None, f'{stage.capitalize()}-ahead for clip {index} failed:\n{job.error}')
    return job.value, {'queued_ahead': job.started is not None,
                       'stage_seconds': round((job.finished or 0) - (job.started or 0), 4)}


def peek(stage, index):
    """Wait for `stage`/`index` but leave it in place for a later collect."""
    with _LOCK:
        job = _state(stage)['jobs'].get(index)
    require(job is not None, f'No {stage} was queued for clip {index}')
    job.done.wait()
    require(job.error is None, f'{stage.capitalize()} for clip {index} failed:\n{job.error}')
    return job.value, {'queued_ahead': job.started is not None,
                       'stage_seconds': round((job.finished or 0) - (job.started or 0), 4)}


def pending(stage):
    with _LOCK:
        return sorted(_state(stage)['jobs'])


def clear():
    with _LOCK:
        for st in _STAGES.values():
            st['jobs'].clear()
            del st['queue'][:]


def run_ahead(stage, index, depth, fn):
    """Return clip `index`'s value, and start the next `depth` clips ahead.

    For work that does not depend on this clip's sampler output -- the text
    encode. The first clip has nothing queued so it computes inline; from then on
    the value is already being produced while the previous clip was sampling.
    """
    require(isinstance(index, int) and index >= 0, 'Clip index must be a non-negative integer')
    require(isinstance(depth, int) and 1 <= depth <= MAX_PENDING, 'Unsupported pipeline depth')
    submitted_inline = submit(stage, index, fn)
    value, detail = collect(stage, index)
    # Start the next clips only AFTER handing this one over, so the worker runs
    # against this prompt's sampling rather than competing with this clip.
    started = [i for i in range(index + 1, index + 1 + depth) if submit(stage, i, fn)]
    detail.update({'computed_inline': submitted_inline, 'started_ahead': started,
                   'pending_after': pending(stage)})
    return value, detail


def run_behind(stage, index, depth, fn):
    """Start clip `index`'s work, then return clip `index - depth`'s result.

    For work that DEPENDS on this clip's sampler output -- the decode. Clip N's
    decode is started here and runs on its own card while clip N+1 samples; this
    prompt emits the clip that was decoded `depth` prompts ago. The first `depth`
    prompts have nothing to emit yet, so they wait for their own decode.
    """
    require(isinstance(index, int) and index >= 0, 'Clip index must be a non-negative integer')
    require(isinstance(depth, int) and 1 <= depth <= MAX_PENDING, 'Unsupported pipeline depth')
    submit(stage, index, fn)
    emit = index - depth
    if emit < 0:
        # Priming. Nothing was decoded `depth` prompts ago, so this prompt waits
        # for its own clip and emits it -- with no overlap, and WITHOUT
        # consuming it, because the next prompt is the one that owns it. Clip 0
        # is therefore emitted twice across the first two prompts. That is a
        # pipeline fill, disclosed in every receipt as `emitted_index`; it is not
        # a reused computation, and the steady-state interval excludes it.
        value, detail = peek(stage, index)
        detail.update({'emitted_index': index, 'primed': False,
                       'pending_after': pending(stage)})
        return value, detail
    value, detail = collect(stage, emit)
    detail.update({'emitted_index': emit, 'primed': True, 'pending_after': pending(stage)})
    return value, detail

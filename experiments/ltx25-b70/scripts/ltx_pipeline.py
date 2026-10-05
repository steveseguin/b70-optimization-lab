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

**This is not a cache, and it does not guess.** Every clip's conditioning is
computed from scratch by its own encode, from the prompt text of the request
that is actually queued for that clip (looked up in the server's own queue); a
value is consumed exactly once, by the clip it was computed for, and is dropped
afterwards. A queued job is tagged with the SHA-256 of the text it encoded, and
a collecting prompt whose text differs discards it and encodes inline. Nothing
is reused between clips. The only thing that changes is *when* the work runs,
never whether it runs or what it produces.

Earlier versions (packets 45-56) submitted the CURRENT prompt's text for the
next clip index and never checked it. That was correct only while every prompt
was identical, which is exactly what the harness of the time did.
"""
import hashlib
import json
import os
import re
import sys
import threading
import time
import traceback

import torch

MODES = ('original', 'pipeline')
# One worker per stage, because the stages live on different cards: the encode
# runs on xpu:2 and the decode on xpu:3, so they must be able to run at once.
STAGES = ('encode', 'decode', 'sample')
# Workers per stage. The encode and decode are one card each, so one worker
# saturates them. The sampler spans xpu:0 and xpu:1 and uses one at a time, so
# TWO sampler workers let one clip occupy xpu:1's blocks while the next occupies
# xpu:0's -- inter-clip pipeline parallelism. Each worker keeps its own thread
# identity, so each gets its own static buffers and captured graphs.
STAGE_WORKERS = {'encode': 1, 'decode': 1, 'sample': 2}
MAX_PENDING = 4
# Packet 97: the largest clip index the lane nodes accept as a literal (their INT input's
# 'max'; ComfyUI refuses a larger literal at validation with "value_bigger_than_max").
# Was 1,000,000 through packet 96; packet 97's index bases start at 10,000,000.
CLIP_INDEX_MAX = 100000000
# Cross-stage input fingerprints, recorded so a wrong clip can be attributed to
# a stage from receipts alone (the f82b/f83e bird clip was byte-identically
# wrong across two servers; no receipt could say whether its conditioning or
# its noise left the expected path). Keyed by clip index, bounded: an
# endurance stream keeps only the most recent entries.
_FINGERPRINTS = {}


def record_fingerprint(index, value):
    with _LOCK:
        _FINGERPRINTS[index] = value
        while len(_FINGERPRINTS) > 512:
            _FINGERPRINTS.pop(next(iter(_FINGERPRINTS)))


def fingerprint(index):
    with _LOCK:
        return _FINGERPRINTS.get(index)

def cond_fingerprint(value):
    """Strided-value fingerprint of a conditioning/latent structure.

    Not a proof of equality: a cheap tripwire, compared across stages from
    receipts, that catches a wholesale substitution of values between the
    encode handoff and the sampler (the f82b/f83e failure mode, where one
    clip per run left the stream fully wrong and no receipt could say which
    stage sent it there). A few thousand sampled values per tensor; costs
    milliseconds.
    """
    digest = hashlib.sha256()

    def walk(item):
        if isinstance(item, torch.Tensor):
            digest.update(str((tuple(item.shape), str(item.dtype), str(item.device))).encode())
            flat = item.detach().reshape(-1)
            count = flat.numel()
            if count:
                stride = max(1, count // 4096)
                digest.update(flat[::stride].float().cpu().numpy().tobytes())
        elif isinstance(item, dict):
            for key in sorted(item, key=repr):
                digest.update(repr(key).encode())
                walk(item[key])
        elif isinstance(item, (list, tuple)):
            for element in item:
                walk(element)

    walk(value)
    return digest.hexdigest()


_LOCK = threading.Lock()
_RUNNING = [0]        # packet 94f: worker jobs executing right now (read by running())
_STAGES = {}          # stage -> {'jobs': {index: _Job}, 'queue': [], 'worker': Thread}
_QUEUE_EVENT = threading.Condition(_LOCK)


def set_stage_workers(stage, count):
    """Raise a stage's worker count (packet 91: a second decode worker for the
    xpu:1 replica). Only increases are admitted once the stage has a live
    worker: a running worker is never retired, so a lower count could not be
    honoured. Packet 96: before the stage's first worker starts, any count from
    1 is admitted (one sampler job in flight)."""
    with _QUEUE_EVENT:
        require(stage in STAGES, 'Unknown pipeline stage: ' + repr(stage))
        started = any(w.is_alive() for w in _STAGES.get(stage, {}).get('workers', []))
        floor = STAGE_WORKERS.get(stage, 1) if started else 1
        require(isinstance(count, int) and floor <= count <= MAX_PENDING,
                'Stage workers may only increase, up to MAX_PENDING')
        STAGE_WORKERS[stage] = count


def _state(stage):
    require(stage in STAGES, 'Unknown pipeline stage: ' + repr(stage))
    return _STAGES.setdefault(stage, {'jobs': {}, 'queue': [], 'workers': []})


def require(value, message):
    if not value:
        raise RuntimeError(message)


class _Job:
    __slots__ = ('index', 'fn', 'tag', 'done', 'value', 'error', 'started', 'finished', 'cpu', 'target')

    def __init__(self, index, fn, tag=None, target=None):
        self.index = index
        # Packet 95: the worker thread name this job must run on (None = any worker);
        # used only by the serial capture pass to reach every sampler worker.
        self.target = target
        self.fn = fn
        # What the job was computed FOR (for the encode: the SHA-256 of the
        # prompt text). A collect with a different tag must not accept it.
        self.tag = tag
        self.done = threading.Event()
        self.value = None
        self.error = None
        self.started = None
        self.finished = None
        self.cpu = None


FAILED_JOB_SCHEMA = 'ltx.pipeline-failed-job.v1'


def _index_label(index):
    """A file-name-safe rendering of a job index (an int for every stage today)."""
    return re.sub(r'[^A-Za-z0-9_.-]', '_', str(index))[:64] or 'none'


def record_failure(stage, job, worker, exc):
    """Packet 97: a failed job of any stage leaves its error on disk and in the server log.

    Writes ``pipeline-failed-<stage>-<index>-<ms>.json`` into the run directory
    (LTX_ENCODER_RUN_DIR) with the stage, index, worker thread, target, the full
    traceback text, the time and the server identity hash, and prints one line with the
    exception type and message to stderr (the server log). Before this, the traceback lived
    only in ``job.error`` and was seen only if a prompt later waited for that job: a capture
    job that failed left nothing. Evidence only: never raises (returns the path or None)."""
    path = None
    try:
        text = job.error if isinstance(job.error, str) else ''.join(
            traceback.format_exception(type(exc), exc, exc.__traceback__))
        message = str(exc)
        record = {'schema': FAILED_JOB_SCHEMA, 'stage': stage,
                  'index': job.index if isinstance(job.index, (int, str)) else repr(job.index),
                  'clip': job.index if isinstance(job.index, int) else None,
                  'worker': worker, 'target': job.target, 'tag': job.tag,
                  'exception_type': type(exc).__name__, 'exception_message': message[:4000],
                  'traceback': text, 'failed_unix': time.time(),
                  'job_seconds': None if job.started is None else round(time.monotonic() - job.started, 4),
                  'server_identity_sha256': os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                  'pid': os.getpid()}
        run = os.environ.get('LTX_ENCODER_RUN_DIR')
        if run:
            stem = 'pipeline-failed-%s-%s-%d' % (stage, _index_label(job.index), int(time.time() * 1000))
            for n in range(100):
                candidate = os.path.join(run, stem + ('' if n == 0 else '-%d' % n) + '.json')
                try:
                    with open(candidate, 'x') as stream:
                        json.dump(record, stream, indent=2, sort_keys=True, default=repr)
                        stream.write('\n')
                    path = candidate
                    break
                except FileExistsError:
                    continue
    except BaseException:  # noqa: BLE001  (evidence only; must never reach the worker loop)
        path = None
    try:
        first = (str(exc).splitlines() or [''])[0][:500]
        print('[ltx-pipeline] FAILED JOB stage=%s index=%s worker=%s %s: %s (receipt: %s)'
              % (stage, getattr(job, 'index', None), worker, type(exc).__name__, first, path),
              file=sys.stderr, flush=True)
    except BaseException:  # noqa: BLE001
        pass
    return path


def _worker_loop(stage):
    import time
    st = _state(stage)
    while True:
        me = threading.current_thread().name
        with _QUEUE_EVENT:
            while True:
                pick = next((i for i, j in enumerate(st['queue']) if j.target is None or j.target == me), None)
                if pick is not None:
                    break
                _QUEUE_EVENT.wait()
            job = st['queue'].pop(pick)
        job.started = time.monotonic()
        with _LOCK:   # packet 94f: jobs executing now, even after clear() dropped them
            _RUNNING[0] += 1
        try:   # packet 92a: CPU seconds of this job on this thread (diagnostic only)
            cpu0 = time.thread_time()
        except Exception:  # noqa: BLE001
            cpu0 = None
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
            # Packet 97: on disk and in the log before done is set, so whoever sees the job
            # finish can also find why it failed. record_failure never raises.
            record_failure(stage, job, me, exc)
        finally:
            try:   # a clock error must never strand a job: done is set regardless
                job.finished = time.monotonic()
                job.cpu = None if cpu0 is None else time.thread_time() - cpu0
            except Exception:  # noqa: BLE001
                job.cpu = None
            finally:
                job.done.set()
                with _LOCK:
                    _RUNNING[0] -= 1


def _ensure_worker(stage):
    st = _state(stage)
    st['workers'] = [w for w in st['workers'] if w.is_alive()]
    while len(st['workers']) < STAGE_WORKERS.get(stage, 1):
        worker = threading.Thread(target=_worker_loop, args=(stage,), daemon=True,
                                  name='ltx-%s-%d' % (stage, len(st['workers'])))
        st['workers'].append(worker)
        worker.start()


def worker_names(stage):
    """Packet 95: names of the live workers of a stage ('ltx-<stage>-<i>')."""
    with _LOCK:
        return [w.name for w in _state(stage)['workers'] if w.is_alive()]


def submit(stage, index, fn, tag=None, target=None):
    """Queue `stage` work for `index` if it is not already queued or finished.
    `target` (packet 95) pins the job to one named worker of the stage."""
    with _QUEUE_EVENT:
        _ensure_worker(stage)
        st = _state(stage)
        if index in st['jobs']:
            return False
        if target is not None:
            require(target in [w.name for w in st['workers'] if w.is_alive()],
                    'No live worker named %r in stage %s' % (target, stage))
        job = _Job(index, fn, tag, target)
        st['jobs'][index] = job
        st['queue'].append(job)
        _QUEUE_EVENT.notify_all()
        return True


def collect(stage, index, tag=None):
    """Wait for `stage`/`index` and hand it over exactly once.

    If `tag` is given, the job must have been computed for that tag. A job
    computed for something else (an encode of a different prompt text) is
    discarded and reported as a speculation miss; the caller computes inline.
    """
    with _LOCK:
        job = _state(stage)['jobs'].get(index)
    require(job is not None, f'No {stage} was queued for clip {index}')
    job.done.wait()
    with _LOCK:
        _state(stage)['jobs'].pop(index, None)
    require(job.error is None, f'{stage.capitalize()}-ahead for clip {index} failed:\n{job.error}')
    detail = {'queued_ahead': job.started is not None,
              'stage_seconds': round((job.finished or 0) - (job.started or 0), 4),
              'cpu_seconds': None if job.cpu is None else round(job.cpu, 4),
              'tag': job.tag}
    if tag is not None and job.tag != tag:
        detail.update({'speculation_miss': True, 'discarded_tag': job.tag})
        return None, detail
    detail['speculation_miss'] = False
    return job.value, detail


def peek(stage, index):
    """Wait for `stage`/`index` but leave it in place for a later collect."""
    with _LOCK:
        job = _state(stage)['jobs'].get(index)
    require(job is not None, f'No {stage} was queued for clip {index}')
    job.done.wait()
    require(job.error is None, f'{stage.capitalize()} for clip {index} failed:\n{job.error}')
    return job.value, {'queued_ahead': job.started is not None,
                       'stage_seconds': round((job.finished or 0) - (job.started or 0), 4)}


def busy():
    """Packet 92a: jobs queued or running in any stage (finished, uncollected
    tail jobs do not count)."""
    with _LOCK:
        return sum(1 for st in _STAGES.values() for job in st['jobs'].values() if not job.done.is_set())


def running():
    """Packet 94f: worker jobs executing right now in any stage. Unlike busy(), this
    still counts a job that clear() dropped after a latched failure while its worker
    is finishing it."""
    with _LOCK:
        return _RUNNING[0]


def pending(stage):
    with _LOCK:
        return sorted(_state(stage)['jobs'])


def clear():
    with _LOCK:
        for st in _STAGES.values():
            st['jobs'].clear()
            del st['queue'][:]


def run_ahead(stage, index, depth, fn, tag=None, lookahead=None):
    """Return clip `index`'s value, and start the next `depth` clips ahead.

    For work that does not depend on this clip's sampler output -- the text
    encode. The first clip has nothing queued so it computes inline; from then on
    the value is already being produced while the previous clip was sampling.

    `tag` identifies what THIS clip needs (the SHA-256 of its prompt text).
    `lookahead(i)` must return `(fn_i, tag_i)` for a future clip `i` whose
    request is already known (it is looked up in the server's own queue), or
    None when it is not. Nothing is guessed: a future clip whose prompt is not
    yet queued is not encoded ahead, and a queued job whose tag does not match
    the collecting prompt is discarded and the clip is encoded inline.
    """
    require(isinstance(index, int) and index >= 0, 'Clip index must be a non-negative integer')
    require(isinstance(depth, int) and 1 <= depth <= MAX_PENDING, 'Unsupported pipeline depth')
    require(tag is None or lookahead is not None,
            'A tagged stage must supply a lookahead; it must not assume the next prompt')
    submitted_inline = submit(stage, index, fn, tag)
    value, detail = collect(stage, index, tag)
    if detail.get('speculation_miss'):
        # The queued job was for a different prompt text. Compute this clip
        # inline, on this thread, from this prompt's own inputs.
        started_at = time.monotonic()
        value = fn()
        detail['stage_seconds'] = round(time.monotonic() - started_at, 4)
        submitted_inline = True
    # Start the next clips only AFTER handing this one over, so the worker runs
    # against this prompt's sampling rather than competing with this clip.
    started = []
    for i in range(index + 1, index + 1 + depth):
        if lookahead is None:
            nxt = (fn, None)
        else:
            nxt = lookahead(i)
            if nxt is None:
                continue
        if submit(stage, i, nxt[0], nxt[1]):
            started.append({'index': i, 'tag': nxt[1]})
    detail.update({'computed_inline': submitted_inline, 'started_ahead': started,
                   'pending_after': pending(stage)})
    return value, detail


def run_behind(stage, index, depth, fn, target=None):
    """Start clip `index`'s work, then return clip `index - depth`'s result.

    For work that DEPENDS on this clip's sampler output -- the decode. Clip N's
    decode is started here and runs on its own card while clip N+1 samples; this
    prompt emits the clip that was decoded `depth` prompts ago. The first `depth`
    prompts have nothing to emit yet, so they wait for their own decode.
    """
    require(isinstance(index, int) and index >= 0, 'Clip index must be a non-negative integer')
    require(isinstance(depth, int) and 1 <= depth <= MAX_PENDING, 'Unsupported pipeline depth')
    # A run-behind stage is fed only by the prompt that owns the index, exactly
    # once. If a job already sits at this index it was parked by an EARLIER
    # stream (a warm clip's un-consumed fill, or a stream restarted at 0), and
    # collecting it later would emit a stale clip. Streams must use fresh clip
    # indices; reuse is a hard error, never a silent substitution.
    require(submit(stage, index, fn, target=target),
            f'{stage} job already exists for clip {index}: stale index from an earlier stream')
    emit = index - depth
    with _LOCK:
        have_predecessor = emit in _state(stage)['jobs']
    if emit >= 0 and not have_predecessor:
        # The first prompt of any index sequence has no predecessor in flight,
        # so it primes like clip 0 does. Self-healing rather than fatal: every
        # clip is still decoded once by its own decode and emitted once; that
        # one prompt simply gets no overlap.
        emit = -1
    if emit < 0:
        # Pipeline fill: nothing is `depth` prompts behind yet. This prompt
        # emits NOTHING (emitted_index -1) rather than a preview of its own
        # clip, so every real clip is emitted exactly once, by the prompt
        # `depth` places later, and no index is ever submitted twice. Callers
        # return placeholder outputs for a fill and the driver skips them.
        return None, {'emitted_index': -1, 'primed': False, 'fill': True,
                      'queued_ahead': True, 'stage_seconds': 0.0, 'pending_after': pending(stage)}
    value, detail = collect(stage, emit)
    detail.update({'emitted_index': emit, 'primed': True, 'pending_after': pending(stage)})
    return value, detail

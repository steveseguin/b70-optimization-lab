"""Packet114: the decode leaves the chain. Stdlib only at import; the runtime supplies the work.

With a latent anchor the next chunk needs only two small latents, so the output node
hashes the three latents, writes the 40,960-byte anchor file, stamps `anchor_ready`
and hands the decode to ONE ordered worker (`OrderedWorker`). The worker runs the
native video and audio decode on xpu:3, hashes the decoded tensors, computes the
packet113 border diagnostic on the last frame, writes the qualification capture
(qualification chunks only), commits `receipts/decode-<run_name>.json` and then
hands the MP4 to the packet113 preview writer behind it. With the frame anchor
(LTX_ANCHOR=frame) the output node submits the same job and waits for it, because
the next chunk needs the decoded frame: the decode then stays on the chain, but runs
through exactly the same code on the same thread, so the A/B differs only in the
anchor.

Rules (the packet113 preview-writer pattern):

- private CPU copies: the job owns clones of the two latents; nothing the prompt
  hashed or anchored can be touched by the worker;
- one thread, FIFO: decodes and records strictly in submission order;
- bounded queue (two waiting jobs) with a blocking submit: a full queue holds the
  output node (back-pressure); no chunk is dropped; a queue that does not move for
  SUBMIT_BOUND_S is a fault;
- a failure is recorded once, latches the worker (later jobs are skipped, never
  retried) and is reported through `on_failure`, which halts the server.

`RegistryLock` serializes ComfyUI's model registry between the decode thread and the
prompt thread. `comfy.model_management.load_models_gpu` (called inside VAE.decode)
pops an already loaded model from `current_loaded_models`, re-loads it and re-inserts
it; the prompt thread's residency snapshots read that list. Run concurrently, a
snapshot could see the VAE missing, or two loads could interleave their index
arithmetic. One re-entrant lock around `load_models_gpu` and around the adapter's
inspection keeps each of them atomic with respect to the other. Numerics are not
involved: the lock only orders bookkeeping.
"""
import functools
import queue
import threading
import time

MAXSIZE = 2             # jobs waiting behind the one being decoded
SUBMIT_BOUND_S = 120.0  # a full queue that does not move for this long is a fault
WAIT_BOUND_S = 300.0    # frame mode: the chain waits at most this long for its own decode


class DecodeFailure(RuntimeError):
    pass


class OrderedWorker:
    """One worker thread, bounded FIFO, back-pressure, failure latch, per-job completion."""

    def __init__(self, process_fn, on_failure, name='ltx114-decode', maxsize=MAXSIZE, clock=time.time_ns,
                 submit_bound_s=SUBMIT_BOUND_S):
        self.process_fn, self.on_failure = process_fn, on_failure
        self.name, self.clock, self.submit_bound_s = name, clock, submit_bound_s
        self.queue = queue.Queue(maxsize=maxsize)
        self.lock = threading.Condition()
        self.thread = None
        self.failed = None
        self.records = {}          # run_name -> committed record (the newest 64)
        self.order = []            # run names in completion order (the newest 256)
        self.submitted = 0
        self.completed = 0
        self.skipped = []
        self.current = None        # run name being processed

    def _ensure(self):
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._loop, daemon=True, name=self.name)
                self.thread.start()

    def pending(self):
        with self.queue.mutex:
            return self.queue.unfinished_tasks

    def submit(self, job):
        """job: dict with 'run_name' and 'timing' (a dict). Blocks while full.
        Returns (queued ns, queue depth on entry, seconds blocked)."""
        if self.failed is not None:
            raise DecodeFailure('%s failed earlier: %s' % (self.name, self.failed))
        self._ensure()
        job['done'] = threading.Event()
        job['result'] = job['error'] = None
        depth = self.pending()
        entered = self.clock()
        job['timing']['queued'] = entered     # stamped before the worker can see the job
        started = time.monotonic()
        deadline = started + self.submit_bound_s
        while True:
            try:
                self.queue.put(job, timeout=0.5)
                break
            except queue.Full:
                if self.failed is not None:
                    raise DecodeFailure('%s failed while this chunk waited: %s' % (self.name, self.failed))
                if time.monotonic() > deadline:
                    raise DecodeFailure('%s queue did not move for %.0f s' % (self.name, self.submit_bound_s))
        with self.lock:
            self.submitted += 1
        return entered, depth, round(time.monotonic() - started, 6)

    def wait(self, job, timeout_s=WAIT_BOUND_S):
        """Frame mode: wait (bounded) for this job's own result."""
        if not job['done'].wait(timeout_s):
            raise DecodeFailure('%s: %s not finished within %.0f s' % (self.name, job['run_name'], timeout_s))
        if job['error'] is not None or job['result'] is None:
            raise DecodeFailure('%s: %s failed: %s' % (self.name, job['run_name'], job['error']))
        return job['result']

    def _loop(self):
        while True:
            job = self.queue.get()
            try:
                if job is None:
                    return
                if self.failed is not None:
                    with self.lock:
                        self.skipped.append(job['run_name'])
                    job['error'] = 'skipped after an earlier failure'
                    continue
                with self.lock:
                    self.current = job['run_name']
                job['timing']['start'] = self.clock()
                record = self.process_fn(job)
                with self.lock:
                    self.records[job['run_name']] = record
                    while len(self.records) > 64:
                        self.records.pop(next(iter(self.records)))
                    self.order.append(job['run_name'])
                    del self.order[:-256]
                    self.completed += 1
                job['result'] = record
            except BaseException as error:  # noqa: BLE001  (latched, reported once)
                first = False
                if job is not None:
                    job['error'] = repr(error)[:1000]
                with self.lock:
                    if self.failed is None:
                        self.failed = '%s: %s' % (job['run_name'] if job else '?', repr(error)[:1000])
                        first = True
                if first:
                    try:
                        self.on_failure(job, error)
                    except BaseException:  # noqa: BLE001
                        pass
            finally:
                if job is not None and 'done' in job:
                    job['done'].set()
                with self.lock:
                    self.current = None
                self.queue.task_done()
                with self.lock:
                    self.lock.notify_all()

    def drain(self, timeout_s):
        """Wait (bounded) until nothing is queued or running. True when empty and not failed."""
        deadline = time.monotonic() + timeout_s
        with self.lock:
            while self.pending() and self.failed is None:
                left = deadline - time.monotonic()
                if left <= 0:
                    return False
                self.lock.wait(min(left, 0.25))
        return self.failed is None and self.pending() == 0

    def record(self, run_name):
        with self.lock:
            return self.records.get(run_name)

    def summary(self):
        with self.lock:
            return {'submitted': self.submitted, 'completed': self.completed, 'pending': self.pending(),
                    'current': self.current, 'failed': self.failed,
                    'skipped_after_failure': list(self.skipped), 'maxsize': self.queue.maxsize}

    def close(self):
        """Tests only: stop the thread after the queue empties."""
        if self.thread is not None and self.thread.is_alive():
            self.queue.put(None)
            self.thread.join(5)


class RegistryLock:
    """One re-entrant lock around ComfyUI's model-registry bookkeeping (see the module doc)."""

    def __init__(self):
        self.lock = threading.RLock()
        self.installed = None
        self.holds = 0

    def wrap(self, fn):
        lock = self

        @functools.wraps(fn)
        def locked(*args, **kwargs):
            with lock.lock:
                lock.holds += 1
                return fn(*args, **kwargs)
        locked._ltx114_registry_lock = self
        locked._ltx114_wrapped = fn
        return locked

    def install(self, mm):
        """Wrap mm.load_models_gpu once. Callers reach it through the module attribute."""
        if self.installed is not None:
            raise RuntimeError('Registry lock already installed')
        original = mm.load_models_gpu
        if getattr(original, '_ltx114_registry_lock', None) is not None:
            raise RuntimeError('load_models_gpu is already wrapped')
        mm.load_models_gpu = self.wrap(original)
        self.installed = (mm, original, mm.load_models_gpu)
        return {'wrapped': 'comfy.model_management.load_models_gpu', 'reentrant': True}

    def check(self):
        if self.installed is None:
            raise RuntimeError('Registry lock not installed')
        mm, _original, wrapped = self.installed
        if mm.load_models_gpu is not wrapped:
            raise RuntimeError('load_models_gpu was replaced after the registry lock')

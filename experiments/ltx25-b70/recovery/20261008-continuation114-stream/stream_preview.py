"""Packet113 preview writer, packet114 timing keys. Torch/Comfy imports are lazy.

Packet114: the writer sits behind the decode thread (stream_decode.py). A job's timing
carries `submit` and `decode_done` (not packet113's `anchor_ready`, which in packet114
precedes the decode); the record reports `decode_done_to_preview_written`. Nothing else
changes: same calls, same arguments, same atomic publish, same latch.

In packet112 the output node hashed the four tensors, wrote the anchor, then wrote
the MP4 preview inline, and only then let the chunk finish; the next chunk could
not be admitted until the preview existed (decode_done -> preview_written was
0.27-0.34 s on the live 112 receipts, of which about 0.04 s is hashing and the
anchor write, the rest the CreateVideo + SaveVideo encode).

Here the output node does everything the next chunk needs (hashes, the anchor file
fsynced, the anchor diagnostic) and marks the chunk "anchor ready"; the preview
is handed to ONE writer thread through a bounded FIFO:

- the writer receives private CPU copies (`clone`), so it cannot alias or mutate
  any tensor the prompt hashed, captured or wrote as the anchor;
- `submit` blocks while the queue is full (back-pressure): no preview is ever
  dropped, and one thread with a FIFO writes them strictly in submission order;
- the file is written under a hidden temporary name, fsynced, hard-linked to its
  final name (exclusive: it fails if the name exists) and the temporary removed,
  so the final MP4 path never shows a partial file;
- each write commits `receipts/preview-<run_name>.json` (bytes, SHA-256, times);
- a failed write records the failure and calls `on_failure` once; the server
  latches through it. Later queued previews are not written after a failure.

This is the same single-writer, bounded-queue design as packet 91's
pipeline_decode_node.PreviewWriter, as a separate instance: the packet-91 writer
object is the one the runtime observer's `preview_pending == 0` quiescence check
reads, and packet91's guarded save swallows failures, which the stream must not.
"""
import hashlib
import os
from pathlib import Path
import queue
import threading
import time

MAXSIZE = 2             # previews waiting behind the one being written
SUBMIT_BOUND_S = 120.0  # a full queue that does not move for this long is a fault
FPS = 24.0
# The exact arguments of pipeline_decode_node.save_preview (tests compare them by AST).
CREATE_VIDEO_KWARGS = {'fps': FPS, 'bit_depth': 8, 'color_space': 'sRGB', 'codec': 'none'}
SAVE_TO_KWARGS = {'metadata': None, 'crf': None}


class PreviewFailure(RuntimeError):
    pass


def private_copy(images, audio):
    """CPU copies the writer owns. `.to('cpu')` alone would return the same CPU tensor."""
    return (images.detach().to('cpu', copy=True).clone(),
            {**audio, 'waveform': audio['waveform'].detach().to('cpu', copy=True).clone()})


def predict_preview_path(prefix, output_directory, width, height):
    """The path pipeline_decode_node.save_preview would choose for this prefix, fixed now."""
    import folder_paths
    folder, filename, counter, subfolder, _prefix = folder_paths.get_save_image_path(
        prefix, output_directory, width, height)
    file = f"{filename}_{counter:05}_.mp4"
    return Path(folder) / file, os.path.join(subfolder, file)


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish_exclusive(tmp, final):
    """Make `tmp` visible as `final` only when complete; refuse an existing final name."""
    tmp, final = Path(tmp), Path(final)
    fd = os.open(tmp, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.link(tmp, final)          # FileExistsError if the final name exists
    os.unlink(tmp)
    _fsync_dir(final.parent)
    raw = final.read_bytes()
    if not raw:
        raise PreviewFailure('Preview MP4 is empty: %s' % final)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def temporary_name(final):
    final = Path(final)
    return final.with_name('.' + final.name + '.partial')


def save_preview_atomic(images, audio, final_path):
    """pipeline_decode_node.save_preview's CreateVideo + SaveVideo calls, same arguments,
    written to a temporary name and published atomically at the predicted path."""
    import torch
    from comfy_api.latest import Types
    from comfy_extras.nodes_video import CreateVideo
    final = Path(final_path)
    tmp = temporary_name(final)
    if final.exists() or tmp.exists():
        raise PreviewFailure('Preview path already exists: %s' % final)
    with torch.inference_mode():
        video = CreateVideo.execute(images=images, fps=24.0, audio=audio, bit_depth=8,
                                    color_space='sRGB', codec='none').result[0]
        video.save_to(str(tmp), format=Types.VideoContainer('mp4'),
                      codec=Types.VideoCodec('auto'), metadata=None, crf=None)
    return publish_exclusive(tmp, final)


class StreamPreviewWriter:
    """One writer thread, bounded FIFO, back-pressure, failure latch (see module doc)."""

    def __init__(self, save_fn, commit_fn, on_failure, maxsize=MAXSIZE, clock=time.time_ns,
                 submit_bound_s=SUBMIT_BOUND_S):
        self.save_fn, self.commit_fn, self.on_failure = save_fn, commit_fn, on_failure
        self.clock = clock
        self.submit_bound_s = submit_bound_s
        self.queue = queue.Queue(maxsize=maxsize)
        self.lock = threading.Condition()
        self.thread = None
        self.failed = None
        self.records = {}          # run_name -> committed record (the newest 64)
        self.written_order = []    # run names in write order (the newest 256)
        self.submitted = 0
        self.completed = 0
        self.skipped = []

    def _ensure(self):
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._loop, daemon=True, name='ltx114-preview-writer')
                self.thread.start()

    def pending(self):
        with self.queue.mutex:
            return self.queue.unfinished_tasks

    def submit(self, job):
        """job: {'run_name', 'prompt_id', 'images', 'audio', 'path', 'relative', 'timing': {'submit',
        'decode_done'}}, images/audio already private copies. Blocks while full (back-pressure).
        Returns (preview_queued ns, queue depth on entry, seconds blocked)."""
        if self.failed is not None:
            raise PreviewFailure('Preview writer failed earlier: ' + self.failed)
        self._ensure()
        depth = self.pending()
        entered = self.clock()
        job['timing']['preview_queued'] = entered     # stamped before the writer can see the job
        started = time.monotonic()
        deadline = started + self.submit_bound_s
        while True:
            try:
                self.queue.put(job, timeout=0.5)
                break
            except queue.Full:
                if self.failed is not None:
                    raise PreviewFailure('Preview writer failed while this chunk waited: ' + self.failed)
                if time.monotonic() > deadline:
                    raise PreviewFailure('Preview queue did not move for %.0f s' % self.submit_bound_s)
        with self.lock:
            self.submitted += 1
        return entered, depth, round(time.monotonic() - started, 6)

    def _loop(self):
        while True:
            job = self.queue.get()
            try:
                if job is None:
                    return
                if self.failed is not None:
                    with self.lock:
                        self.skipped.append(job['run_name'])
                    continue
                start = self.clock()
                info = self.save_fn(job)
                written = self.clock()
                timing = dict(job['timing'], write_start=start, preview_written=written)
                record = {'run_name': job['run_name'], 'prompt_id': job['prompt_id'], 'path': str(job['path']),
                          'relative_to_output_directory': job['relative'], 'bytes': info['bytes'],
                          'sha256': info['sha256'], 'container': 'mp4', 'written': True, 'order': 'fifo',
                          'timing_ns': timing, 'timing_s': {
                              'submit_to_preview_written': None if timing.get('submit') is None else
                              round((written - timing['submit']) / 1e9, 6),
                              'decode_done_to_preview_written': round((written - timing['decode_done']) / 1e9, 6),
                              'queue_wait': round((start - timing['preview_queued']) / 1e9, 6),
                              'write': round((written - start) / 1e9, 6)}}
                record = self.commit_fn(job, record) or record
                with self.lock:
                    self.records[job['run_name']] = record
                    while len(self.records) > 64:
                        self.records.pop(next(iter(self.records)))
                    self.written_order.append(job['run_name'])
                    del self.written_order[:-256]
                    self.completed += 1
            except BaseException as error:  # noqa: BLE001  (latched, reported once)
                first = False
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
                self.queue.task_done()
                with self.lock:
                    self.lock.notify_all()

    def drain(self, timeout_s):
        """Wait (bounded) until nothing is queued or being written. True when empty and not failed."""
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
                    'failed': self.failed, 'skipped_after_failure': list(self.skipped),
                    'maxsize': self.queue.maxsize}

    def close(self):
        """Tests only: stop the thread after the queue empties."""
        if self.thread is not None and self.thread.is_alive():
            self.queue.put(None)
            self.thread.join(5)


# -- anchor hand-off ------------------------------------------------------------
def anchor_bytes(torch, images, last):
    """The anchor: images[last] as complete little-endian F32 bytes, taken before any hand-off."""
    frame = images.detach().to('cpu')[last:last + 1]
    return frame.contiguous().view(torch.uint8).numpy().tobytes()


def load_anchor_tensor(torch, raw, shape):
    """What the next chunk's provider builds from the verified anchor file bytes."""
    return torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(*shape).clone()


def anchor_diagnostic(torch, images, last, border=16):
    """Border-vs-centre colour diagnostic of the anchor frame (float64; diagnostic only).
    Must agree with stream_receipts.border_diagnostic_reference (tested)."""
    import stream_receipts
    f = images.detach().to('cpu')[last].to(torch.float64)          # [H, W, 3]
    h, w = int(f.shape[0]), int(f.shape[1])
    chroma = f.amax(dim=2) - f.amin(dim=2)
    luma = 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]
    clipped = ((f.amax(dim=2) >= 0.999) | (f.amin(dim=2) <= 0.001)).to(torch.float64)
    ring = torch.ones(h, w, dtype=torch.bool)
    ring[border:h - border, border:w - border] = False
    centre = torch.zeros(h, w, dtype=torch.bool)
    centre[h // 4:h - h // 4, w // 4:w - w // 4] = True
    sums = {}
    for key, mask in (('border', ring), ('centre', centre)):
        sums[key] = (float(chroma[mask].sum()), float(luma[mask].sum()), int(clipped[mask].sum()),
                     int(mask.sum()))
    return stream_receipts.diagnostic_from_sums(sums, border)

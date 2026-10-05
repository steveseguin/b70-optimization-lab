"""Decode clip N while clip N+1 samples.

The decode depends on this clip's sampler output, so it cannot run ahead. It can
run *behind*: clip N's decode is started on a worker thread bound to the VAE's
card (xpu:3) and this prompt emits the clip that was decoded `depth` prompts
ago, while the sampler moves on to clip N+1 on xpu:0/1.

Every clip is decoded exactly once, by its own decode, and emitted once in
steady state. Nothing is cached or reused; only the moment the work runs
changes. The one exception is the pipeline fill: the first prompt has nothing
decoded `depth` prompts ago, so it waits for its own clip and emits it without
consuming it, and the next prompt emits that same clip. Every receipt records
`emitted_index`, so which clip a prompt emitted is never in doubt.

Video and audio are decoded and emitted together, with their latents, so a
prompt's four oracle inputs always describe the same clip.

`pipeline-save` additionally assembles and writes the lossy MP4 preview on the
same worker, right after the decode, so the 0.13 s of container encoding leaves
the prompt thread too. The written file is what the sealed SaveVideo node
would write (same container, codec, fps, bit depth and colour space; no
embedded prompt metadata). The prompt emits its path through
LTXPipelineSaveRecord, an output node that records but does not encode.
"""
import os
import contextlib
import hashlib
import json
import sys
from pathlib import Path
import queue
import re
import threading
import time

import torch

import ltx_pipeline as pipeline
import ltx_gil_probe as gil
import ltx_decode_child as child_proc
import ltx_decode_replica as placement
from encoder_diagnostics import _context

gil.start_probe()   # packet 92a lock-wait probe (idempotent, never raises)

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
DECODE_MODES = pipeline.MODES + ('pipeline-save', 'pipeline-replica', 'pipeline-moved', 'pipeline-child')
# Modes whose prompts also write the diagnostic MP4 preview (packet 91: on the
# single preview-writer thread, not on the decode worker).
SAVE_MODES = ('pipeline-save', 'pipeline-replica', 'pipeline-moved', 'pipeline-child')
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def done_marker(stage, index, extra=None):
    """Packet 90c: worker-side completion marker, written after the job's GPU
    work has finished, so a campaign can prove the pipeline is idle before a
    stop. File evidence only; never raises."""
    try:
        run = Path(os.environ['LTX_ENCODER_RUN_DIR'])
        write_json(run / ('pipeline-done-%s-%d.json' % (stage, index)),
                   {'stage': stage, 'index': index, 'finished_unix': time.time(), **(extra or {})})
    except Exception:  # noqa: BLE001  (evidence only)
        pass


def decode_clip(vae, audio_vae, video_latent, audio_latent, save_prefix=None, _timing=None):
    """Exactly what VAEDecode and LTXVAudioVAEDecode do, then optionally the MP4 write."""
    import nodes
    from comfy_extras.nodes_lt_audio import LTXVAudioVAEDecode
    t0 = time.monotonic()
    decoded = nodes.VAEDecode().decode(vae, video_latent)
    require(isinstance(decoded, tuple) and len(decoded) == 1,
            'VAEDecode no longer returns a single image batch')
    images = decoded[0]
    audio = LTXVAudioVAEDecode.execute(samples=audio_latent, audio_vae=audio_vae).result[0]
    t1 = time.monotonic()
    saved = ''
    if save_prefix:
        saved = save_preview_guarded(images, audio, save_prefix)
    if _timing is not None:
        try:  # timing only; must never fail the clip
            _timing['vae_s'] = round(t1 - t0, 4)
            _timing['save_s'] = round(time.monotonic() - t1, 4)
        except Exception:  # noqa: BLE001
            pass
    return images, audio, video_latent, audio_latent, saved


SAVE_FAILURES = []


def save_preview_guarded(images, audio, prefix):
    """The MP4 is a lossy preview; the raw tensors and their oracle are the product.
    A muxer/encoder failure therefore records diagnostics (and the waveform, for
    offline replay) instead of failing the clip, and returns a 'save-failed:' marker."""
    try:
        return save_preview(images, audio, prefix)
    except Exception as error:  # noqa: BLE001  (diagnostic capture, then continue)
        import folder_paths
        waveform = audio.get('waveform') if isinstance(audio, dict) else None
        row = {'prefix': prefix, 'error': repr(error)[:400],
               'images_shape': list(images.shape) if hasattr(images, 'shape') else None,
               'sample_rate': audio.get('sample_rate') if isinstance(audio, dict) else None}
        if waveform is not None:
            w = waveform.detach().float().cpu()
            row.update({'waveform_shape': list(w.shape), 'waveform_dtype': str(waveform.dtype),
                        'waveform_device': str(waveform.device), 'nan': int(torch.isnan(w).sum()),
                        'inf': int(torch.isinf(w).sum()), 'min': float(w.min()) if w.numel() else None,
                        'max': float(w.max()) if w.numel() else None})
            try:
                folder = folder_paths.get_output_directory()
                dump = os.path.join(folder, prefix.replace('/', '_') + '_audio_debug.pt')
                torch.save({'waveform': w, 'sample_rate': row['sample_rate']}, dump)
                row['dump'] = dump
            except Exception as dump_error:  # noqa: BLE001
                row['dump_error'] = repr(dump_error)[:200]
        SAVE_FAILURES.append(row)
        return 'save-failed:' + type(error).__name__


def save_preview(images, audio, prefix):
    """What the sealed CreateVideo(fps 24, 8-bit sRGB, codec none) + SaveVideo(mp4, auto) pair writes."""
    import folder_paths
    from comfy_api.latest import Types
    from comfy_extras.nodes_video import CreateVideo
    video = CreateVideo.execute(images=images, fps=24.0, audio=audio, bit_depth=8,
                                color_space='sRGB', codec='none').result[0]
    width, height = video.get_dimensions()
    folder, filename, counter, subfolder, _prefix = folder_paths.get_save_image_path(
        prefix, folder_paths.get_output_directory(), width, height)
    file = f"{filename}_{counter:05}_.mp4"
    video.save_to(os.path.join(folder, file), format=Types.VideoContainer('mp4'),
                  codec=Types.VideoCodec('auto'), metadata=None, crf=None)
    return os.path.join(subfolder, file)


class PreviewWriter:
    """Packet 91: the MP4 preview leaves the decode worker.

    One writer thread, a bounded FIFO. `submit` blocks while the queue is full
    (back-pressure, never a dropped preview) and returns the seconds it
    waited. The writer receives private CPU copies, so it can never alias the
    tensors the prompt emits to the oracle capture. Each save keeps the
    guarded-save behaviour (failures are recorded, never raised), records its
    own save time, and leaves a `save` done marker for the quiescence check.
    """

    def __init__(self, save_fn, maxsize=4, marker=None):
        self.save_fn = save_fn
        self.marker = marker
        self.queue = queue.Queue(maxsize=maxsize)
        self.records = []
        self.lock = threading.Lock()
        self.thread = None
        self.completed = 0

    def _ensure(self):
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._loop, daemon=True, name='ltx-preview-writer')
                self.thread.start()

    def submit(self, index, images, audio, prefix):
        self._ensure()
        item = (index, images.detach().to('cpu', copy=True),
                {**audio, 'waveform': audio['waveform'].detach().to('cpu', copy=True)},
                prefix, time.monotonic())
        started = time.monotonic()
        self.queue.put(item)
        return round(time.monotonic() - started, 4)

    def _loop(self):
        while True:
            index, images, audio, prefix, queued_at = self.queue.get()
            started = time.monotonic()
            try:
                # Same autograd context the decode worker saved under (ComfyUI
                # runs nodes and pipeline workers inside inference_mode).
                with torch.inference_mode():
                    saved = self.save_fn(images, audio, prefix)
            except BaseException as error:  # noqa: BLE001  (diagnostic only)
                saved = 'save-failed:' + type(error).__name__
            row = {'index': index, 'prefix': prefix, 'saved': saved,
                   'queued_s': round(started - queued_at, 4),
                   'save_s': round(time.monotonic() - started, 4)}
            with self.lock:
                self.records.append(row)
                self.completed += 1
            if self.marker is not None:
                self.marker('save', index, {'saved': saved, 'save_s': row['save_s']})
            self.queue.task_done()

    def drain(self):
        with self.lock:
            rows, self.records = self.records, []
            completed = self.completed
        return {'saves': rows, 'completed_total': completed, 'pending': self.queue.unfinished_tasks,
                'maxsize': self.queue.maxsize}


_WRITER = PreviewWriter(lambda images, audio, prefix: save_preview_guarded(images, audio, prefix),
                        maxsize=4, marker=done_marker)
# Packet 91 placement state, per server process.
_NATIVE_LOCK = threading.Lock()     # one decode at a time on xpu:3 (the control's one worker)
_REPLICA_LOCK = threading.Lock()    # one decode at a time on the (first) replica card
_REPLICAS = {}                      # 'video' / 'audio' -> placement.Replica (first replica slot)
# Packet 97: one VAE pair and one lock per replica slot ('replica' on LTX_DECODE_REPLICA_DEVICE's
# first card is the objects above, unchanged; 'replica2' only with LTX_DECODE_REPLICAS=2).
_REPLICA_SETS = {'replica': _REPLICAS}
_REPLICA_LOCKS = {'replica': _REPLICA_LOCK}
for _slot in placement.REPLICA_SLOTS[1:]:
    _REPLICA_SETS[_slot] = {}
    _REPLICA_LOCKS[_slot] = threading.Lock()
_PROBE = {'passed': False, 'outcome': 'not run', 'receipt': None}


class ReplicaNotQualified(RuntimeError):
    """A replica placement was requested before the cross-card probe passed.
    Raised before any job is submitted, so it does not latch the pipeline."""


class PlacementChangeRefused(RuntimeError):
    """A placement change while the same index stream still has decode jobs
    pending (they would be collected under the new depth, or stranded).
    Raised before any job is submitted, so it does not latch the pipeline."""


# Refusals that are raised before any decode job is submitted: they fail the
# request with a receipt but leave the decode node and the pipeline usable.
class ChildNotQualified(RuntimeError):
    """The child-process placement was requested before its probe passed on
    this server. Raised before any job is submitted; does not latch."""


NON_LATCHING = (ReplicaNotQualified, PlacementChangeRefused, ChildNotQualified)
_CHILD_LOCK = threading.Lock()      # one request in flight to the decode child
_CHILD_PROBE = {'passed': False, 'outcome': 'not run', 'receipt': None}
VAE_FILES = ('ltx-2.5-video-vae-bf16.safetensors', 'ltx-2.5-audio-vae-bf16.safetensors')


def _free3():
    """Front-end view of xpu:3 free memory (device-wide)."""
    try:
        return int(torch.xpu.mem_get_info(child_proc.CHILD_PHYSICAL_DEVICE)[0])
    except Exception:  # noqa: BLE001
        return None


def start_decode_child():
    """Packet 92b: spawn the decode child at custom-node import, after the
    launcher's preflight and before ComfyUI serves, when LTX_DECODE_CHILD=1.
    Records the outcome in decode-child-startup.json; never raises."""
    if os.environ.get('LTX_DECODE_CHILD') != '1' or not os.environ.get('LTX_ENCODER_RUN_DIR'):
        return None
    record = {'schema': 'ltx.decode-child-startup.v1', 'requested_unix': time.time()}
    try:
        run = Path(os.environ['LTX_ENCODER_RUN_DIR'])
        server = json.loads((run / 'server-identity.json').read_text())
        import folder_paths
        config = {'source_dir': str(Path(server['source_packet_path']) / 'source'),
                  'server_argv': json.loads((run / 'server-args.json').read_text()),
                  'expected_uuid': str(torch.xpu.get_device_properties(child_proc.CHILD_PHYSICAL_DEVICE).uuid),
                  'vae_paths': [folder_paths.get_full_path_or_raise('vae', name) for name in VAE_FILES],
                  'ze_affinity_mask': str(child_proc.CHILD_PHYSICAL_DEVICE), 'torch_threads': 16}
        record['config'] = config
        record['xpu3_free_before'] = _free3()
        record['state'] = child_proc.ensure_started(config)
        record['xpu3_free_after'] = _free3()
    except Exception as error:  # noqa: BLE001
        record['error'] = repr(error)[:2000]
    try:
        path = Path(os.environ['LTX_ENCODER_RUN_DIR']) / 'decode-child-startup.json'
        if not path.exists():
            write_json(path, record)
    except Exception:  # noqa: BLE001
        pass
    try:
        import atexit
        atexit.register(lambda: child_proc.alive() and child_proc.stop(timeout=30.0))
    except Exception:  # noqa: BLE001
        pass
    return record
_LAST_PLACEMENT = {'mode': None}
# A pending decode job this close below the new request's index belongs to the
# same stream; fresh index bases (>= 100 apart in every campaign) are outside it.
STREAM_WINDOW = 2 * pipeline.MAX_PENDING


def placement_change_conflicts(previous_mode, mode, decode_index, pending):
    """Pending decode indices that a mode change at `decode_index` would strand."""
    if previous_mode is None or previous_mode == mode:
        return []
    return [i for i in pending if decode_index - STREAM_WINDOW <= i < decode_index]


def _capture_lock():
    """The process-wide graph capture/replay lock the sampler uses."""
    import ltx_graph_capture
    return ltx_graph_capture.CAPTURE_LOCK


def _busy_begin(device, stream=None):
    """Decode-job busy window start on `device` (on `stream` if given). Never raises."""
    try:
        import ltx_graph_capture as capture
        if not capture._BUSY_ON[0]:
            return None, None
        with torch.xpu.device(device), (torch.xpu.stream(stream) if stream is not None
                                        else contextlib.nullcontext()):
            return capture, capture.busy_begin(device)
    except Exception:  # noqa: BLE001  (instrumentation must not fail a clip)
        return None, None


def _busy_end(capture, token, device, stream=None):
    if capture is None or token is None:
        return
    try:
        with torch.xpu.device(device), (torch.xpu.stream(stream) if stream is not None
                                        else contextlib.nullcontext()):
            capture.busy_end(token, device, 'decode')
    except Exception:  # noqa: BLE001
        pass


def _xpu_memory(index):
    return {'allocated': int(torch.xpu.memory_allocated(index)), 'reserved': int(torch.xpu.memory_reserved(index))}


def _new_stream(device):
    return torch.xpu.Stream(device=device)


def decode_native(vae, audio_vae, video_latent, audio_latent):
    """Control placement: the resident VAEs on xpu:3, native ComfyUI decode."""
    t0 = time.monotonic()
    with _NATIVE_LOCK:
        t1 = time.monotonic()
        cap, token = _busy_begin(placement.NATIVE_DEVICE)
        images, audio = decode_clip(vae, audio_vae, video_latent, audio_latent)[:2]
        _busy_end(cap, token, placement.NATIVE_DEVICE)
        t2 = time.monotonic()
    return images, audio, {'wait_s': round(t1 - t0, 4), 'vae_s': round(t2 - t1, 4)}


def decode_child(vae, audio_vae, video_latent, audio_latent, index):
    """Child placement: the decode child's own VAEs on xpu:3, bytes over a pipe.

    The round trip holds CAPTURE_LOCK in shared mode (the 91b discipline,
    extended across processes): no front-end graph capture -- including the
    text-encoder shard's on xpu:3 -- can start while the child is decoding,
    and the child never starts while a capture is recording. Lock order:
    _CHILD_LOCK -> CAPTURE_LOCK (shared)."""
    require(_CHILD_PROBE['passed'], 'Child decode without a passed child probe')
    capture_lock = _capture_lock()
    t0 = time.monotonic()
    with _CHILD_LOCK, placement.shared(capture_lock):
        t1 = time.monotonic()
        reply, out = child_proc.request('decode', {'index': index},
                                        {'video': video_latent['samples'], 'audio': audio_latent['samples']})
        t2 = time.monotonic()
    require(reply.get('index') == index, 'Decode child answered for clip %s, not %s' % (reply.get('index'), index))
    images = out['images'].to(vae.output_device)
    waveform = out['waveform'].to(audio_latent['samples'].device)
    cpu = reply.get('cpu') if isinstance(reply.get('cpu'), dict) else {}
    timing = {'wait_s': round(t1 - t0, 4), 'vae_s': reply.get('decode_s'), 'roundtrip_s': round(t2 - t1, 4),
              'child_job_cpu_s': reply.get('job_cpu_s'), 'child_process_cpu_s': cpu.get('process_cpu_s'),
              'child_wall_unix': cpu.get('wall_unix'),
              'child_free_bytes': (reply.get('memory') or {}).get('free')}
    return images, {'waveform': waveform, 'sample_rate': reply['sample_rate']}, timing


def decode_replica(vae, audio_vae, video_latent, audio_latent, slot='replica'):
    """Replica placement: the probe-qualified VAE copies on the slot's card (packet 97:
    LTX_DECODE_REPLICA_DEVICE; xpu:1 by default)."""
    require(slot in placement.REPLICA_SLOTS, 'Not an admitted replica slot: %r' % (slot,))
    pair = _REPLICA_SETS[slot]
    require(_PROBE['passed'] and 'video' in pair and 'audio' in pair,
            'Replica decode without a passed cross-card probe')
    require(_PROBE.get('sources') == (id(vae), id(audio_vae)),
            'Replica decode for VAEs other than the ones the probe qualified')
    video, audio_rep = pair['video'], pair['audio']
    device = placement.ALLOWED_DEVICES[slot]
    capture_lock = _capture_lock()
    t0 = time.monotonic()
    # Lock order: the slot's replica lock -> CAPTURE_LOCK (shared) -> Replica.lock.
    with _REPLICA_LOCKS[slot], placement.shared(capture_lock):
        t1 = time.monotonic()
        cap, token = _busy_begin(device, video.stream)
        images, audio = placement.decode_clip_replica(video, audio_rep, vae, audio_vae, video_latent, audio_latent)
        _busy_end(cap, token, device, video.stream)
        t2 = time.monotonic()
    return images, audio, {'wait_s': round(t1 - t0, 4), 'vae_s': round(t2 - t1, 4)}


class LTXPipelineDecode:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'vae': ('VAE',), 'audio_vae': ('VAE',),
                             'video_latent': ('LATENT',), 'audio_latent': ('LATENT',),
                             'mode': (list(DECODE_MODES),),
                             'clip_index': ('INT', {'default': 0, 'min': -1, 'max': pipeline.CLIP_INDEX_MAX}),
                             'depth': ('INT', {'default': 1, 'min': 1,
                                               'max': pipeline.MAX_PENDING}),
                             # How many prompts the latents arriving here already
                             # lag by, when an upstream stage runs behind too.
                             # Keeps `emitted_index` naming the clip it really is.
                             'upstream_depth': ('INT', {'default': 0, 'min': 0,
                                                        'max': pipeline.MAX_PENDING}),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('IMAGE', 'AUDIO', 'LATENT', 'LATENT', 'STRING')
    RETURN_NAMES = ('images', 'audio', 'video_latent', 'audio_latent', 'saved_file')
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, vae, audio_vae, video_latent, audio_latent, mode, clip_index, depth,
              run_name, upstream_depth=0):
        global _failed
        try:
            return self._apply(vae, audio_vae, video_latent, audio_latent,
                               mode, clip_index, depth, run_name, upstream_depth)
        except NON_LATCHING:
            raise
        except BaseException:
            _failed = True
            gil.restore_default('latched failure: pipeline-decode-')
            pipeline.clear()
            raise

    def _apply(self, vae, audio_vae, video_latent, audio_latent, mode, clip_index, depth,
               run_name, upstream_depth=0):
        require(not _failed, 'Previous pipeline failure; halt submissions and inspect evidence')
        require(mode in DECODE_MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(pipeline.__file__), 'ltx_pipeline.py'),
                           (Path(placement.__file__), 'ltx_decode_replica.py'),
                           (Path(gil.__file__), 'ltx_gil_probe.py'),
                           (Path(child_proc.__file__), 'ltx_decode_child.py'),
                           (Path(__file__), 'pipeline_decode_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(),
                'Strict determinism required')

        report = {'schema': 'ltx.pipeline-decode-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'clip_index': clip_index, 'depth': depth,
                  'upstream_depth': upstream_depth,
                  'extension_sha256s': hashes,
                  'claim': 'every clip is decoded once by its own decode and emitted once in '
                           'steady state; nothing is cached or reused. Only the moment the work '
                           'runs changes, so it overlaps the next clip sampling on other cards.',
                  'passed': False}
        started = time.monotonic()
        gil.mark_lane_thread('prompt')
        apply_cpu0 = time.thread_time()   # packet 92a
        try:
            if mode == 'pipeline-child' and not (_CHILD_PROBE['passed'] and child_proc.alive()):
                report['refused'] = ('child placement requires a passed decode-child probe and a running '
                                     'child on this server (probe outcome: %s; child: %s)'
                                     % (_CHILD_PROBE['outcome'], child_proc.state().get('error')))
                raise ChildNotQualified(report['refused'])
            if mode in placement.REPLICA_MODES and not _PROBE['passed']:
                report['refused'] = ('replica placement requires a passed cross-card decode probe on this '
                                     'server (probe outcome: %s)' % _PROBE['outcome'])
                raise ReplicaNotQualified(report['refused'])
            if mode in placement.REPLICA_MODES:
                for slot in placement.REPLICA_SLOTS:
                    for key in ('video', 'audio'):
                        placement.check_placement(_REPLICA_SETS[slot][key].module, slot)
            if mode == 'pipeline-replica':
                # Packet 97: one decode worker per slot (native + each replica).
                pipeline.set_stage_workers('decode', len(placement.PLACEMENTS['pipeline-replica']))
            report['placement'] = list(placement.PLACEMENTS.get(mode, ('native',)))
            report['decode_replica'] = placement.replica_record()
            report['stage_workers'] = pipeline.STAGE_WORKERS.get('decode')
            if mode == 'original':
                out = decode_clip(vae, audio_vae, video_latent, audio_latent)
                report['detail'] = {'emitted_index': max(0, clip_index - upstream_depth),
                                    'primed': True}
            elif clip_index < 0:
                # Upstream fill (the pipelined sampler emitted nothing): emit
                # nothing here either. Small placeholders; never decoded, never
                # saved, skipped by the driver.
                out = (torch.zeros(1, 8, 8, 3), {'waveform': torch.zeros(1, 2, 8), 'sample_rate': 48000},
                       video_latent, audio_latent, 'fill')
                report['detail'] = {'emitted_index': -1, 'fill': True, 'upstream_fill': True}
            else:
                latents = (video_latent, audio_latent)
                decode_index = max(0, clip_index - upstream_depth)
                # Packet 90: the latents submitted here must be byte-identical
                # to what the sampler's worker-side sentry recorded for this
                # clip. This is the last checkpoint before the clip leaves the
                # sampler's outputs for the decode stage (the f89 NaN bird's
                # passthrough latents were NaN at the capture node, which reads
                # this stage's inputs).
                sentry = pipeline.fingerprint(('sample-output', decode_index))
                require(sentry is not None and sentry['video_finite'] and sentry['audio_finite'],
                        'Decode input sentry missing or nonfinite for clip %d: %s' % (decode_index, sentry))
                for key, lat in (('video', video_latent), ('audio', audio_latent)):
                    tensor = lat['samples']
                    require(bool(torch.isfinite(tensor).all().item()),
                            'Nonfinite %s latents at decode submit for clip %d' % (key, decode_index))
                    sha = hashlib.sha256(tensor.detach().to('cpu', copy=True)
                                         .view(torch.uint8).numpy().tobytes()).hexdigest()
                    require(sha == sentry[key + '_sha256'],
                            'Decode-submit %s latents for clip %d differ from the sampler sentry: %s vs %s'
                            % (key, decode_index, sha[:12], sentry[key + '_sha256'][:12]))
                save_prefix = (run_name + '/preview') if mode in SAVE_MODES else None
                # During the upstream stage's own fill it emits its own clip, so
                # the index this prompt is really carrying is clamped at zero.
                # Those first few prompts re-emit an early clip; every clip is
                # still decoded exactly once, and emitted_index records which.
                # Packet 90b: the vae/save split is timed inside THIS clip's
                # job and recorded under this clip's decode index when the job
                # finishes; the receipt reports the split of the clip it
                # EMITS (decode_index - depth), whose job collect() has already
                # waited on. Timing only: the decode itself is unchanged.
                # Packet 91: the job decodes on the placement slot its clip
                # index selects (deterministic, recorded), then hands the
                # preview to the writer thread. The split records lock wait,
                # decode and enqueue time; the save time is the writer's.
                def decode_job(decode_index=decode_index):
                    slot = placement.slot_for(mode, decode_index)
                    if slot == 'native':
                        images, audio, timing = decode_native(vae, audio_vae, *latents)
                    elif slot == 'child':
                        images, audio, timing = decode_child(vae, audio_vae, *latents, decode_index)
                    elif slot == 'replica':
                        # The packet 96 call, unchanged (the first replica slot is the default).
                        images, audio, timing = decode_replica(vae, audio_vae, *latents)
                    else:
                        images, audio, timing = decode_replica(vae, audio_vae, *latents, slot=slot)
                    saved = ''
                    enqueue_s = 0.0
                    if save_prefix:
                        saved = 'queued:' + save_prefix
                        enqueue_s = _WRITER.submit(decode_index, images, audio, save_prefix)
                    try:  # timing/evidence only; must never fail the clip
                        pipeline.record_fingerprint(('decode-split', decode_index), {
                            **timing, 'slot': slot,
                            'device': placement.ALLOWED_DEVICES.get(slot, 'xpu:3 (decode child process)'),
                            'enqueue_s': enqueue_s})
                    except Exception:  # noqa: BLE001
                        pass
                    done_marker('decode', decode_index, {'slot': slot})
                    return images, audio, latents[0], latents[1], saved

                conflicts = placement_change_conflicts(_LAST_PLACEMENT['mode'], mode, decode_index,
                                                       pipeline.pending('decode'))
                if conflicts:
                    report['refused'] = ('placement change %s -> %s while decode jobs %s of this stream are '
                                         'pending; start the new placement on a fresh index base'
                                         % (_LAST_PLACEMENT['mode'], mode, conflicts))
                    raise PlacementChangeRefused(report['refused'])
                out, detail = pipeline.run_behind('decode', decode_index, depth, decode_job)
                _LAST_PLACEMENT['mode'] = mode
                if out is None:
                    out = (torch.zeros(1, 8, 8, 3), {'waveform': torch.zeros(1, 2, 8), 'sample_rate': 48000},
                           video_latent, audio_latent, 'fill')
                detail['saved_file'] = out[4]
                try:  # timing only; must never fail the clip
                    split = (pipeline.fingerprint(('decode-split', detail['emitted_index']))
                             if detail.get('emitted_index', -1) >= 0 else None)
                    detail['decode_split'] = split if split else 'not recorded (fill)'
                except Exception as error:  # noqa: BLE001
                    detail['decode_split'] = 'unavailable: ' + repr(error)[:200]
                report['detail'] = detail
            report['save_failures'] = [dict(row) for row in SAVE_FAILURES]
            try:  # diagnostic only
                report['preview_writer'] = _WRITER.drain()
            except Exception as error:  # noqa: BLE001
                report['preview_writer'] = 'unavailable: ' + repr(error)[:200]
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            report['written_unix'] = time.time()  # packet 90b: occupancy wall for analyze-phases
            try:  # packet 92a: diagnostic only, never fails the clip
                report['apply_cpu_seconds'] = round(time.thread_time() - apply_cpu0, 4)
                report['gil'] = gil.report(drain=False)
            except Exception as error:  # noqa: BLE001
                report['gil'] = 'unavailable: ' + repr(error)[:200]
            write_json(run / ('pipeline-decode-' + run_name + '.json'), report)
        return out


class LTXPipelineSaveRecord:
    """Output node: records the preview already written by the decode worker."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'saved_file': ('STRING', {'forceInput': True}),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, saved_file, run_name):
        require(isinstance(saved_file, str) and saved_file, 'The decode worker did not write a preview')
        if saved_file == 'fill':
            return {'ui': {'text': ['pipeline fill: nothing emitted']}}
        run, _identity = _context()
        if saved_file.startswith('queued:'):
            # Packet 91: the preview is written later by the writer thread; the
            # real path is in that save's done marker and in a later decode
            # receipt's preview_writer.saves. Not a file yet, so ComfyUI gets
            # text, never a path that may not exist.
            write_json(run / ('pipeline-save-' + run_name + '.json'),
                       {'schema': 'ltx.pipeline-save-record.v2', 'run_name': run_name,
                        'status': 'queued-to-writer', 'prefix': saved_file[len('queued:'):],
                        'saved_file': None})
            return {'ui': {'text': ['preview queued to the writer: ' + saved_file[len('queued:'):]]}}
        write_json(run / ('pipeline-save-' + run_name + '.json'),
                   {'schema': 'ltx.pipeline-save-record.v1', 'run_name': run_name, 'saved_file': saved_file})
        subfolder, file = os.path.split(saved_file)
        return {'ui': {'images': [{'filename': file, 'subfolder': subfolder, 'type': 'output'}]}}


PROBE_FIXTURES = 'probe/decode-replica-fixtures.json'


def _load_probe_fixtures(packet):
    """The packet's pinned fixture list (its sha256 must match the packet manifest)."""
    manifest = json.loads((packet / 'manifest.json').read_text())
    path = packet / PROBE_FIXTURES
    require(hashlib.sha256(path.read_bytes()).hexdigest() == manifest['files'][PROBE_FIXTURES],
            'Probe fixture list differs from the packet manifest')
    fixtures = json.loads(path.read_text())['fixtures']
    require(len(fixtures) == 10 and len({f['fixture'] for f in fixtures}) == 10,
            'Probe needs the ten distinct fixtures')
    return fixtures


def _load_fixture_tensors(row):
    from safetensors.torch import load_file
    digest = hashlib.sha256()
    with open(row['source'], 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    require(digest.hexdigest() == row['source_sha256'], 'Probe source tensors changed: ' + row['source'])
    return load_file(row['source'], device='cpu')


class LTXDecodeReplicaProbe:
    """Packet 91 gate for the replica placements: build the xpu:1 VAE replicas
    and decode the ten fixtures' certified latents on xpu:3 (native) and on
    xpu:1 (replica). Passes only if every image and waveform is byte-identical
    across the cards and to the stored references, and xpu:1 keeps enough free
    memory. Until a probe passes in this server process, the replica modes are
    refused. 'replica-not-exact' is a valid, recorded outcome, not an error."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'vae': ('VAE',), 'audio_vae': ('VAE',),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, vae, audio_vae, run_name):
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(placement.__file__), 'ltx_decode_replica.py'),
                           (Path(__file__), 'pipeline_decode_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        report = {'schema': 'ltx.decode-replica-probe.v1', **identity, 'run_name': run_name,
                  'extension_sha256s': hashes, 'native_device': placement.NATIVE_DEVICE,
                  'replica_device': placement.REPLICA_DEVICE, 'passed': False, 'outcome': 'error',
                  'decode_replica': placement.replica_record()}
        slots = placement.REPLICA_SLOTS
        devices = [placement.ALLOWED_DEVICES[s] for s in slots]
        started = time.monotonic()
        _PROBE.update(passed=False, outcome='running')
        capture_lock = None
        try:
            fixtures = _load_probe_fixtures(Path(server['source_packet_path']))
            capture_lock = _capture_lock()
            import comfy.model_management as mm
            load_lock = getattr(mm.load_models_gpu, '__globals__', {}).get('_LOAD_LOCK')
            require(load_lock is not None, 'The resident fast path (and its load lock) is not installed')
            report['memory_before'] = {}
            for dev in devices:
                report['memory_before'][dev] = _xpu_memory(torch.device(dev).index)
                report['memory_before'][dev + '_free'] = placement.free_bytes(dev)
            if not any(_REPLICA_SETS[s] for s in slots):
                # Packet 94d: the VAEs are made wholly resident on xpu:3 by an explicit
                # serial step here, not by the side effect of an earlier decode.
                # The freeze flag lives in ltx_graph_capture; if that module was never
                # imported, nothing can have been frozen.
                _cap = sys.modules.get('ltx_graph_capture')
                frozen = bool(_cap is not None and _cap.LOADS_FROZEN[0])
                report['vae_residency'] = placement.ensure_vaes_resident(
                    mm.load_models_gpu, (vae, audio_vae), pipeline.busy() == 0, frozen)
                # Registered as soon as each copy exists, so any non-pass
                # verdict below (including an exception half-way) releases it.
                _PROBE['sources'] = (id(vae), id(audio_vae))
                for slot, dev in zip(slots, devices):
                    stream = _new_stream(dev)    # one stream per replica card, shared by its VAE pair
                    for key, source in (('video', vae), ('audio', audio_vae)):
                        _REPLICA_SETS[slot][key] = placement.build_replica(source, dev, load_lock, capture_lock,
                                                                           make_stream=lambda _d, s=stream: s)
                report['replicas'] = {k: r.report for k, r in _REPLICAS.items()}
                if len(slots) > 1:
                    report['replica_sets'] = {s: {k: r.report for k, r in _REPLICA_SETS[s].items()} for s in slots}
                short = False
                for dev in devices:
                    free, how = placement.free_bytes(dev)
                    report[dev + '_free_after_build'] = [free, how]
                    short = short or free < placement.MIN_FREE_AFTER_BUILD
                if short:
                    report['outcome'] = 'insufficient-memory'
                    return {'ui': {'text': [report['outcome']]}}
            require(_PROBE.get('sources') == (id(vae), id(audio_vae)),
                    'Probe VAEs differ from the ones the replicas were built from')
            require(all(set(_REPLICA_SETS[s]) == {'video', 'audio'} for s in slots),
                    'A replica slot is missing its VAE pair')
            replicas_ok = all(placement.check_placement(r.module, s) for s in slots for r in _REPLICA_SETS[s].values())
            report['placement_checked'] = replicas_ok

            def native(v, a):
                return decode_native(vae, audio_vae, v, a)[:2]

            def replica_on(slot):
                def replica(v, a):
                    pair = _REPLICA_SETS[slot]
                    # Lock order: the slot's replica lock -> CAPTURE_LOCK (shared) -> Replica.lock.
                    with _REPLICA_LOCKS[slot], placement.shared(capture_lock):
                        return placement.decode_clip_replica(pair['video'], pair['audio'], vae, audio_vae, v, a)
                return replica

            decoders = replica_on('replica') if len(slots) == 1 else {s: replica_on(s) for s in slots}
            passed, rows = placement.probe_rows(fixtures, _load_fixture_tensors, native, decoders)
            report['rows'] = rows
            short = False
            report['memory_after'] = {}
            for dev in devices:
                free, how = placement.free_bytes(dev)
                report[dev + '_free_after_probe'] = [free, how]
                report['memory_after'][dev] = _xpu_memory(torch.device(dev).index)
                short = short or free < placement.MIN_FREE_AFTER_PROBE
            if not passed:
                report['outcome'] = 'replica-not-exact'
            elif short:
                report['outcome'] = 'insufficient-memory'
            else:
                report['outcome'] = 'replica-exact'
                report['passed'] = True
        except Exception as error:  # noqa: BLE001  (the receipt carries it; replica stays refused)
            import traceback
            report['outcome'] = 'error'
            report['error'] = ''.join(traceback.format_exception(type(error), error, error.__traceback__))[-4000:]
        finally:
            if not report['passed'] and any(_REPLICA_SETS[s] for s in slots):
                # Only a passed probe may leave replicas resident on their card(s).
                for slot, dev in zip(slots, devices):
                    if not _REPLICA_SETS[slot]:
                        continue
                    try:
                        with _REPLICA_LOCKS[slot]:
                            released = placement.release_replicas(
                                _REPLICA_SETS[slot], dev, capture_lock or _capture_lock())
                        if slot == 'replica':
                            report['released'] = released
                        else:
                            report.setdefault('released_sets', {})[slot] = released
                    except Exception as error:  # noqa: BLE001
                        _REPLICA_SETS[slot].clear()
                        report['release_error' if slot == 'replica' else 'release_error_' + slot] = repr(error)[:400]
                _PROBE.pop('sources', None)
            report['replicas_resident'] = sorted(_REPLICAS)
            if len(slots) > 1:
                report['replica_sets_resident'] = {s: sorted(_REPLICA_SETS[s]) for s in slots}
            _PROBE.update(passed=bool(report['passed']), outcome=report['outcome'])
            report['seconds'] = round(time.monotonic() - started, 3)
            report['written_unix'] = time.time()
            receipt = run / ('decode-probe-' + run_name + '.json')
            _PROBE['receipt'] = str(receipt)
            write_json(receipt, report)
        return {'ui': {'text': [report['outcome']]}}


class LTXSchedulerKnob:
    """Packet 92a: set the interpreter switch interval between arms.

    Applies sys.setswitchinterval only when no pipeline job is queued or
    running (waits up to 60 s, then refuses with a receipt). Also drains the
    lock-wait histogram and snapshots per-thread CPU time, so a knob request
    after an idle wait is the idle baseline. Never raises after the identity
    checks; touches no tensor, stream or device."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'switch_interval_ms': ('FLOAT', {'default': 5.0, 'min': 0.1, 'max': 100.0,
                                                              'step': 0.1}),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, switch_interval_ms, run_name):
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        report = {'schema': 'ltx.scheduler-knob.v1', **identity, 'run_name': run_name,
                  'requested_ms': switch_interval_ms}
        try:
            report['knob'] = gil.set_switch_interval(float(switch_interval_ms) / 1000.0, pipeline.busy)
            report['gil'] = gil.report(drain=True)
            report['probe_started'] = gil.start_probe()
        except Exception as error:  # noqa: BLE001  (diagnostic only)
            report['error'] = repr(error)[:300]
        report['written_unix'] = time.time()
        write_json(run / ('scheduler-knob-' + run_name + '.json'), report)
        applied = bool(report.get('knob', {}).get('applied'))
        return {'ui': {'text': ['switch interval %s ms: %s' % (switch_interval_ms,
                                                                'applied' if applied else 'REFUSED')]}}


def _child_node_context(run_name, extra_files=()):
    require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
            'Unsafe request name')
    run, identity = _context()
    require(identity['model_verification_sha256'] == MODEL_SHA256 and
            identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
            'Model/startup identity changed')
    server = json.loads((run / 'server-identity.json').read_text())
    hashes = {}
    for path, name in ((Path(child_proc.__file__), 'ltx_decode_child.py'),
                       (Path(__file__), 'pipeline_decode_node.py')):
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
        hashes[name] = actual
    return run, identity, server, hashes


class LTXDecodeChildProbe:
    """Packet 92b gate for the child placement: the decode child decodes the
    ten fixtures' certified latents and every image and waveform must equal the
    stored references byte-for-byte, with enough device-wide free memory on
    xpu:3 after the child's load and after the decodes. On any other verdict
    the child is stopped cooperatively (its memory goes with its process) and
    the child arm stays refused. 'child-not-exact' is a valid outcome."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, run_name):
        run, identity, server, hashes = _child_node_context(run_name)
        report = {'schema': 'ltx.decode-child-probe.v1', **identity, 'run_name': run_name,
                  'extension_sha256s': hashes, 'passed': False, 'outcome': 'error',
                  'thresholds': {'min_free_after_load': child_proc.MIN_FREE_AFTER_LOAD,
                                 'min_free_after_probe': child_proc.MIN_FREE_AFTER_PROBE}}
        started = time.monotonic()
        _CHILD_PROBE.update(passed=False, outcome='running')
        try:
            report['child_state'] = child_proc.state()
            if not child_proc.alive():
                report['outcome'] = 'child-unavailable'
                return {'ui': {'text': [report['outcome']]}}
            ready = child_proc.state().get('ready') or {}
            free_load = (ready.get('memory') or {}).get('free')
            report['xpu3_free_after_child_load'] = free_load
            if free_load is None or free_load < child_proc.MIN_FREE_AFTER_LOAD:
                report['outcome'] = 'insufficient-memory'
                return {'ui': {'text': [report['outcome']]}}
            fixtures = _load_probe_fixtures(Path(server['source_packet_path']))
            capture_lock = _capture_lock()
            rows = []
            for fx in fixtures:
                tensors = _load_fixture_tensors(fx)
                row = {'fixture': fx['fixture'], 'source': fx['source'],
                       'inputs_certified': all(placement.tensor_sha256(tensors[k]) == fx['expected'][k]
                                               for k in ('video_latent', 'audio_latent'))}
                if row['inputs_certified']:
                    with _CHILD_LOCK, placement.shared(capture_lock):
                        reply, out = child_proc.request('decode', {'index': -1},
                                                        {'video': tensors['video_latent'],
                                                         'audio': tensors['audio_latent']})
                    row['images_sha256'] = placement.tensor_sha256(out['images'])
                    row['waveform_sha256'] = placement.tensor_sha256(out['waveform'])
                    row['decode_s'] = reply.get('decode_s')
                    row['passed'] = (row['images_sha256'] == fx['expected']['images'] and
                                     row['waveform_sha256'] == fx['expected']['waveform'])
                else:
                    row['passed'] = False
                rows.append(row)
            report['rows'] = rows
            with _CHILD_LOCK:
                stats, _ = child_proc.request('stats')
            free_probe = (stats.get('memory') or {}).get('free')
            report['xpu3_free_after_probe'] = free_probe
            report['child_memory_after_probe'] = stats.get('memory')
            if not (rows and all(r['passed'] for r in rows)):
                report['outcome'] = 'child-not-exact'
            elif free_probe is None or free_probe < child_proc.MIN_FREE_AFTER_PROBE:
                report['outcome'] = 'insufficient-memory'
            else:
                report['outcome'] = 'child-exact'
                report['passed'] = True
        except Exception as error:  # noqa: BLE001  (the receipt carries it; the child arm stays refused)
            import traceback
            report['outcome'] = 'error'
            report['error'] = ''.join(traceback.format_exception(type(error), error, error.__traceback__))[-4000:]
        finally:
            if not report['passed'] and child_proc.state().get('pid') is not None \
                    and not child_proc.state().get('stopped'):
                before = _free3()
                with _CHILD_LOCK:
                    report['child_stop'] = child_proc.stop()
                report['xpu3_free_before_stop'], report['xpu3_free_after_stop'] = before, _free3()
            _CHILD_PROBE.update(passed=bool(report['passed']), outcome=report['outcome'])
            report['seconds'] = round(time.monotonic() - started, 3)
            report['written_unix'] = time.time()
            write_json(run / ('decode-child-probe-' + run_name + '.json'), report)
        return {'ui': {'text': [report['outcome']]}}


class LTXDecodeChildStop:
    """Packet 92b: cooperative stop of the decode child, for the runner's
    proven-quiescence stop (child first, then the server). Waits up to 60 s
    for the pipeline to go idle, then asks the child to exit and waits for the
    process; never kills. The receipt says whether the child exited."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, run_name):
        run, identity, _server, hashes = _child_node_context(run_name)
        report = {'schema': 'ltx.decode-child-stop.v1', **identity, 'run_name': run_name,
                  'extension_sha256s': hashes, 'exited': False}
        try:
            waited = 0.0
            while pipeline.busy() and waited < 60.0:
                time.sleep(0.5)
                waited += 0.5
            report['pipeline_busy_after_wait'] = pipeline.busy()
            if report['pipeline_busy_after_wait']:
                report['reason'] = 'pipeline still busy; child left running'
            else:
                before = _free3()
                with _CHILD_LOCK:
                    report['stop'] = child_proc.stop()
                report['exited'] = bool(report['stop'].get('exited'))
                report['returncode'] = report['stop'].get('returncode')
                report['xpu3_free_before'], report['xpu3_free_after'] = before, _free3()
            report['child_state'] = child_proc.state()
        except Exception as error:  # noqa: BLE001
            report['error'] = repr(error)[:400]
        report['written_unix'] = time.time()
        write_json(run / ('decode-child-stop-' + run_name + '.json'), report)
        return {'ui': {'text': ['decode child exited' if report['exited'] else 'decode child NOT stopped']}}


start_decode_child()


NODE_CLASS_MAPPINGS = {'LTXPipelineDecode': LTXPipelineDecode, 'LTXPipelineSaveRecord': LTXPipelineSaveRecord,
                       'LTXDecodeReplicaProbe': LTXDecodeReplicaProbe, 'LTXSchedulerKnob': LTXSchedulerKnob,
                       'LTXDecodeChildProbe': LTXDecodeChildProbe, 'LTXDecodeChildStop': LTXDecodeChildStop}

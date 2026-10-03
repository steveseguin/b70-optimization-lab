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
from pathlib import Path
import queue
import re
import threading
import time

import torch

import ltx_pipeline as pipeline
import ltx_decode_replica as placement
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
DECODE_MODES = pipeline.MODES + ('pipeline-save', 'pipeline-replica', 'pipeline-moved')
# Modes whose prompts also write the diagnostic MP4 preview (packet 91: on the
# single preview-writer thread, not on the decode worker).
SAVE_MODES = ('pipeline-save', 'pipeline-replica', 'pipeline-moved')
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
_REPLICA_LOCK = threading.Lock()    # one decode at a time on the xpu:1 replica
_REPLICAS = {}                      # 'video' / 'audio' -> placement.Replica
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
NON_LATCHING = (ReplicaNotQualified, PlacementChangeRefused)
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


def decode_replica(vae, audio_vae, video_latent, audio_latent):
    """Replica placement: the probe-qualified VAE copies on xpu:1."""
    require(_PROBE['passed'] and 'video' in _REPLICAS and 'audio' in _REPLICAS,
            'Replica decode without a passed cross-card probe')
    require(_PROBE.get('sources') == (id(vae), id(audio_vae)),
            'Replica decode for VAEs other than the ones the probe qualified')
    video, audio_rep = _REPLICAS['video'], _REPLICAS['audio']
    capture_lock = _capture_lock()
    t0 = time.monotonic()
    # Lock order: _REPLICA_LOCK -> CAPTURE_LOCK (shared) -> Replica.lock.
    with _REPLICA_LOCK, placement.shared(capture_lock):
        t1 = time.monotonic()
        cap, token = _busy_begin(placement.REPLICA_DEVICE, video.stream)
        images, audio = placement.decode_clip_replica(video, audio_rep, vae, audio_vae, video_latent, audio_latent)
        _busy_end(cap, token, placement.REPLICA_DEVICE, video.stream)
        t2 = time.monotonic()
    return images, audio, {'wait_s': round(t1 - t0, 4), 'vae_s': round(t2 - t1, 4)}


class LTXPipelineDecode:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'vae': ('VAE',), 'audio_vae': ('VAE',),
                             'video_latent': ('LATENT',), 'audio_latent': ('LATENT',),
                             'mode': (list(DECODE_MODES),),
                             'clip_index': ('INT', {'default': 0, 'min': -1, 'max': 1000000}),
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
        try:
            if mode in placement.REPLICA_MODES and not _PROBE['passed']:
                report['refused'] = ('replica placement requires a passed cross-card decode probe on this '
                                     'server (probe outcome: %s)' % _PROBE['outcome'])
                raise ReplicaNotQualified(report['refused'])
            if mode in placement.REPLICA_MODES:
                for key in ('video', 'audio'):
                    placement.check_placement(_REPLICAS[key].module, 'replica')
            if mode == 'pipeline-replica':
                pipeline.set_stage_workers('decode', 2)
            report['placement'] = list(placement.PLACEMENTS.get(mode, ('native',)))
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
                    else:
                        images, audio, timing = decode_replica(vae, audio_vae, *latents)
                    saved = ''
                    enqueue_s = 0.0
                    if save_prefix:
                        saved = 'queued:' + save_prefix
                        enqueue_s = _WRITER.submit(decode_index, images, audio, save_prefix)
                    try:  # timing/evidence only; must never fail the clip
                        pipeline.record_fingerprint(('decode-split', decode_index), {
                            'slot': slot, 'device': placement.ALLOWED_DEVICES[slot],
                            'wait_s': timing['wait_s'], 'vae_s': timing['vae_s'], 'enqueue_s': enqueue_s})
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
                  'replica_device': placement.REPLICA_DEVICE, 'passed': False, 'outcome': 'error'}
        started = time.monotonic()
        _PROBE.update(passed=False, outcome='running')
        capture_lock = None
        try:
            fixtures = _load_probe_fixtures(Path(server['source_packet_path']))
            capture_lock = _capture_lock()
            import comfy.model_management as mm
            load_lock = getattr(mm.load_models_gpu, '__globals__', {}).get('_LOAD_LOCK')
            require(load_lock is not None, 'The resident fast path (and its load lock) is not installed')
            report['memory_before'] = {'xpu:1': _xpu_memory(1),
                                       'xpu:1_free': placement.free_bytes(placement.REPLICA_DEVICE)}
            if not _REPLICAS:
                stream = _new_stream(placement.REPLICA_DEVICE)
                # Registered as soon as each copy exists, so any non-pass
                # verdict below (including an exception half-way) releases it.
                _PROBE['sources'] = (id(vae), id(audio_vae))
                for key, source in (('video', vae), ('audio', audio_vae)):
                    _REPLICAS[key] = placement.build_replica(source, placement.REPLICA_DEVICE, load_lock,
                                                             capture_lock, make_stream=lambda _d: stream)
                report['replicas'] = {k: r.report for k, r in _REPLICAS.items()}
                free, how = placement.free_bytes(placement.REPLICA_DEVICE)
                report['xpu:1_free_after_build'] = [free, how]
                if free < placement.MIN_FREE_AFTER_BUILD:
                    report['outcome'] = 'insufficient-memory'
                    return {'ui': {'text': [report['outcome']]}}
            require(_PROBE.get('sources') == (id(vae), id(audio_vae)),
                    'Probe VAEs differ from the ones the replicas were built from')
            replicas_ok = all(placement.check_placement(r.module, 'replica') for r in _REPLICAS.values())
            report['placement_checked'] = replicas_ok

            def native(v, a):
                return decode_native(vae, audio_vae, v, a)[:2]

            def replica(v, a):
                video, audio_rep = _REPLICAS['video'], _REPLICAS['audio']
                # Lock order: _REPLICA_LOCK -> CAPTURE_LOCK (shared) -> Replica.lock.
                with _REPLICA_LOCK, placement.shared(capture_lock):
                    return placement.decode_clip_replica(video, audio_rep, vae, audio_vae, v, a)

            passed, rows = placement.probe_rows(fixtures, _load_fixture_tensors, native, replica)
            report['rows'] = rows
            free, how = placement.free_bytes(placement.REPLICA_DEVICE)
            report['xpu:1_free_after_probe'] = [free, how]
            report['memory_after'] = {'xpu:1': _xpu_memory(1)}
            if not passed:
                report['outcome'] = 'replica-not-exact'
            elif free < placement.MIN_FREE_AFTER_PROBE:
                report['outcome'] = 'insufficient-memory'
            else:
                report['outcome'] = 'replica-exact'
                report['passed'] = True
        except Exception as error:  # noqa: BLE001  (the receipt carries it; replica stays refused)
            import traceback
            report['outcome'] = 'error'
            report['error'] = ''.join(traceback.format_exception(type(error), error, error.__traceback__))[-4000:]
        finally:
            if not report['passed'] and _REPLICAS:
                # Only a passed probe may leave replicas resident on xpu:1.
                try:
                    with _REPLICA_LOCK:
                        report['released'] = placement.release_replicas(
                            _REPLICAS, placement.REPLICA_DEVICE, capture_lock or _capture_lock())
                except Exception as error:  # noqa: BLE001
                    _REPLICAS.clear()
                    report['release_error'] = repr(error)[:400]
                _PROBE.pop('sources', None)
            report['replicas_resident'] = sorted(_REPLICAS)
            _PROBE.update(passed=bool(report['passed']), outcome=report['outcome'])
            report['seconds'] = round(time.monotonic() - started, 3)
            report['written_unix'] = time.time()
            receipt = run / ('decode-probe-' + run_name + '.json')
            _PROBE['receipt'] = str(receipt)
            write_json(receipt, report)
        return {'ui': {'text': [report['outcome']]}}


NODE_CLASS_MAPPINGS = {'LTXPipelineDecode': LTXPipelineDecode, 'LTXPipelineSaveRecord': LTXPipelineSaveRecord,
                       'LTXDecodeReplicaProbe': LTXDecodeReplicaProbe}

"""Packet114 streaming runtime (packet113 plus a latent anchor and the decode off the chain).

Inert until the sealed launcher calls install().

Packet114 changes against packet113:

1. Latent anchor (LTX_ANCHOR=latent, default). The output node takes the stage-A latent
   (node 367), the stage-B latents (node 369) and the two resident VAEs. It hashes the
   three latents, writes the 40,960-byte latent anchor (last latent slot of stage A and
   of stage B, latent_anchor.py), stamps `anchor_ready` and commits the receipt. The
   next chunk conditions both stages on that file through LTXStreamLatentCondition114:
   the native slot-0 copy and mask of LTXVImgToVideoInplace without the VAE encode.
   LTX_ANCHOR=frame keeps packet113's decoded-frame anchor and native conditioning.
2. The decode leaves the graph. One ordered decode thread (stream_decode.OrderedWorker)
   runs the native VAEDecode / LTXVAudioVAEDecode calls on xpu:3, writes the
   qualification capture, commits receipts/decode-<run_name>.json and hands the MP4 to
   the packet113 preview writer behind it. In frame mode the output node waits for its
   own decode (the anchor is the decoded frame).
3. Chunk length 49 or 97 at launch; text reuse ON by default; `stream114-` names.
4. Node-start events for 364, 344, 367, 348, the stage-B condition node, 340, 368, 369
   and the output node split the old sampler-A bucket.

Setup (window probe, full-residency preparation) -> nine qualification chunks ->
explicit verdict action -> unbounded serial stream chunks. Any failure inside an
admitted request, the decode thread or the preview writer latches the authority and
refuses later requests. No retry, allocator reset, settings change, process action or
device import at module import.
"""
import asyncio
import copy
import hashlib
import os
from pathlib import Path
import re
import shutil
import threading
import time

import stream_contract as contract
import stream_preview
import stream_decode

_CTX = None
_ROUTES_INSTALLED = False
GIB = 2 ** 30
RESERVE_BYTES = 50 * GIB
RUN_ALLOWANCE = 3 * GIB
XPU3_DECODE_FLOOR = 9 * GIB       # the packet's xpu:3 pre-request floor, applied before every decode
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
RUN_NAME_RE = contract.RUN_NAME_RE
PREVIEW_DRAIN_BOUND_S = 120.0     # the verdict waits at most this long for queued previews
DECODE_DRAIN_BOUND_S = 300.0      # ... and for queued decodes (also before every gated request)
CHUNK_KINDS = contract.KINDS
NON_TENSOR_CURRENT = ('anchor_image', 'latent_parts', 'decode_job')


def _tensor_rows(torch, value, path='conditioning'):
    """Every tensor in a conditioning structure, in a fixed walk order."""
    rows = []
    if isinstance(value, torch.Tensor):
        t = value.detach().to('cpu').contiguous()
        rows.append({'path': path, 'shape': list(t.shape), 'dtype': str(t.dtype),
                     'sha256': hashlib.sha256(t.view(torch.uint8).numpy()).hexdigest()})
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            rows.extend(_tensor_rows(torch, item, '%s[%d]' % (path, i)))
    elif isinstance(value, dict):
        for key in sorted(value, key=str):
            rows.extend(_tensor_rows(torch, value[key], '%s.%s' % (path, key)))
    return rows


def _summary(torch, tensor, shape, name, require):
    t = tensor.detach().to('cpu').contiguous()
    require(t.dtype is torch.float32 and list(t.shape) == list(shape), 'Tensor geometry differs: %s %s %s'
            % (name, list(t.shape), t.dtype))
    require(bool(torch.isfinite(t).all()), 'Nonfinite tensor: ' + name)
    return {'shape': list(t.shape), 'dtype': str(t.dtype), 'finite': True,
            'sha256': hashlib.sha256(t.view(torch.uint8).numpy()).hexdigest()}


class Runtime:
    def __init__(self, packet, manifest, manifest_sha, run):
        import ltx_resolution_session as session
        import ltx_duration_guard as capture
        self.session = session
        self.packet, self.run, self.manifest = Path(packet), Path(run), manifest
        self.root = self.run.parent
        self.manifest_sha = manifest_sha
        self.identity_sha = session.digest(session.read_regular(self.run / 'server-identity.json'))
        identity = session.strict_json(session.read_regular(self.run / 'server-identity.json'))
        session.require(identity['source_packet_manifest_sha256'] == manifest_sha,
                        'Server/source manifest identity differs')
        self.text_reuse = contract.launch_text_reuse()
        self.frames = contract.launch_frames()
        self.placement = contract.launch_placement()
        self.anchor = contract.launch_anchor()
        self.geometry = contract.geometry(self.frames)
        (self.run / 'receipts').mkdir()
        (self.run / 'anchors').mkdir()
        self.lock = threading.RLock()
        self.action_busy = False
        self.actions_done = set()
        self.action_worker = self.action_cleanup = None
        self.action_halt_receipt_error = None
        self.adapter = self.bindings = self.conditioning = self.latent_guard = None
        self.frozen_signatures = None
        self.qualified_windows = None   # text-window buckets exercised by qualification
        self.current = None
        self.submit_ns = {}
        self.events = {}
        self.text_cache = None     # the last fresh encode: {'chain', 'run_name', 'text_sha256', 'value', 'rows'}
        self.capturing = None      # the decode thread's capture identity while it writes a capture
        self.decode_sequence = 0
        self.geometry_recorded = False
        self.authority = session.configure(self.packet / 'resolution/stream-plan.json', manifest_sha,
                                           self.identity_sha, self.run, self.inspect_state, self.text_reuse,
                                           self.frames, self.placement, self.anchor)
        session.require(session.digest(Path(capture.__file__).read_bytes()) ==
                        manifest['files']['source/scripts/ltx_duration_guard.py'],
                        'Capture guard differs from sealed source')
        self.capture_rows = [{'name': row['name'], 'role': 'full',
                              'graph_sha256': row['graph_sha256'][self.authority.variant + '/%d' % self.text_reuse]}
                             for row in self.authority.qualification_rows]
        self.capture_guard = capture.configure(session.PLAN_SHA256, self.capture_rows, self.active_capture_request)
        self.preview = stream_preview.StreamPreviewWriter(self._save_preview, self._commit_preview,
                                                          self._preview_failed)
        self.decoder = stream_decode.OrderedWorker(self._decode_job, self._decode_failed, name='ltx114-decode')
        self.registry = stream_decode.RegistryLock()
        self.free_at_install = shutil.disk_usage(self.root).free
        self.storage_check()

    # -- observation ----------------------------------------------------------
    def fault(self):
        return ((self.root / 'FAULT.json').exists() or (self.run / 'stream-halt.json').exists() or
                self.preview.failed is not None or self.decoder.failed is not None)

    def _halt_async(self, error, label):
        # Latch without holding the worker: the executor thread may own the authority lock.
        threading.Thread(target=self.authority.halt, name='ltx114-%s-halt' % label, daemon=True,
                         args=(error,)).start()

    # -- preview writer (packet113, behind the decode thread) -------------------
    def _save_preview(self, job):
        return stream_preview.save_preview_atomic(job['images'], job['audio'], job['path'])

    def _commit_preview(self, job, record):
        import stream_receipts
        record = dict(record, schema=stream_receipts.PREVIEW_SCHEMA, frames=self.frames, fps=contract.FPS,
                      lossy=True, includes_overlap_frame=job['includes_overlap_frame'])
        stream_receipts.validate_preview_record(record)
        self.write('receipts/preview-' + job['run_name'] + '.json', record)
        return record

    def _preview_failed(self, job, error):
        name = job['run_name'] if isinstance(job, dict) else 'unknown'
        try:
            self.write('stream-preview-failure-' + name + '.json', {
                'run_name': name, 'error': repr(error)[:4000], 'writer': self.preview.summary(),
                'time_ns': time.time_ns()})
        finally:
            self._halt_async(RuntimeError('Preview write failed for %s: %r' % (name, error)), 'preview')

    # -- decode thread (packet114) ------------------------------------------------
    def _decode_failed(self, job, error):
        name = job['run_name'] if isinstance(job, dict) else 'unknown'
        try:
            self.write('stream-decode-failure-' + name + '.json', {
                'run_name': name, 'error': repr(error)[:4000], 'decoder': self.decoder.summary(),
                'time_ns': time.time_ns()})
        finally:
            self._halt_async(RuntimeError('Decode failed for %s: %r' % (name, error)), 'decode')

    def _geometry_mismatch(self, name, observed):
        """Record the measured shapes before latching, so a wrong 97-frame derivation is visible."""
        try:
            self.write('stream-geometry-mismatch-' + name + '.json', {
                'run_name': name, 'frames': self.frames, 'observed': observed,
                'expected': self.geometry['tensor_shapes'], 'stage_a': self.geometry['stage_shapes']['A'],
                'provenance': self.geometry['provenance'], 'time_ns': time.time_ns()})
        except Exception:
            pass

    def _xpu3_free(self):
        """Physical free bytes on xpu:3 (driver reading, no synchronize; the decode thread's floor check)."""
        import torch
        return torch.xpu.mem_get_info('xpu:3')[0]

    def _decode_job(self, job):
        """Runs on the decode thread. Never takes the authority lock."""
        import torch
        import nodes
        import stream_receipts
        require = self.session.require
        self.registry.check()
        self.bindings.check_native()
        self.bindings.settings()
        vae, audio_vae = job['vae'], job['audio_vae']
        require(vae is self.adapter.objects['video_vae'] and audio_vae is self.adapter.objects['audio_vae'],
                'Decode VAEs are not the admitted resident VAEs')
        free = self._xpu3_free()
        require(type(free) is int and free >= XPU3_DECODE_FLOOR,
                'xpu:3 below the 9 GiB decode floor (%s bytes free); refused before VAE.decode' % free)
        with torch.inference_mode():
            images = nodes.VAEDecode().decode(vae, {'samples': job['video_latent']})[0]
            audio = nodes.NODE_CLASS_MAPPINGS['LTXVAudioVAEDecode'].execute(
                samples={'samples': job['audio_latent']}, audio_vae=audio_vae).result[0]
        done = time.time_ns()
        require(type(audio) is dict and audio.get('sample_rate') == contract.SAMPLE_RATE, 'Audio sample rate differs')
        observed = {'images': list(images.shape), 'waveform': list(audio['waveform'].shape)}
        if observed != self.geometry['decoded_shapes']:
            self._geometry_mismatch(job['run_name'], observed)
        tensors = {name: _summary(torch, value, self.geometry['decoded_shapes'][name], name, require)
                   for name, value in (('images', images), ('waveform', audio['waveform']))}
        last = self.geometry['anchor_frame_index']
        frame_raw = stream_preview.anchor_bytes(torch, images, last)
        last_sha = hashlib.sha256(frame_raw).hexdigest()
        diagnostic = stream_preview.anchor_diagnostic(torch, images, last)
        capture = None
        if job['capture'] is not None:
            import folder_paths
            self.capturing = dict(job['capture'], thread=threading.get_ident())
            try:
                nodes.NODE_CLASS_MAPPINGS['LTXBaselineCapture']().capture(
                    images=images, video_latent={'samples': job['video_latent']},
                    audio_latent={'samples': job['audio_latent']}, audio=audio, run_name=job['run_name'])
            finally:
                self.capturing = None
            used = self.capture_guard.receipt()['captures']
            require(used and used[-1]['name'] == job['run_name'] and used[-1]['prompt_id'] == job['prompt_id'],
                    'Qualification capture missing')
            capture = {'path': str(Path(folder_paths.get_output_directory()) / 'validation' / job['run_name'] /
                                   'tensors.safetensors'), 'prewrite': used[-1]}
        frame_anchor = None
        if self.anchor == 'frame':
            job['anchor_bytes'] = frame_raw
            frame_anchor = {'sha256': last_sha, 'bytes': len(frame_raw)}
        self.decode_sequence += 1
        timing = {'submit': job['timing'].get('submit'), 'anchor_ready': job['timing'].get('anchor_ready'),
                  'decode_queued': job['timing']['queued'], 'decode_start': job['timing']['start'],
                  'decode_done': done}
        record = {'schema': stream_receipts.DECODE_SCHEMA, 'run_name': job['run_name'], 'prompt_id': job['prompt_id'],
                  'kind': job['kind'], 'stream_seq': job['stream_seq'], 'chunk_index': job['chunk_index'],
                  'frames': self.frames, 'anchor': self.anchor, 'device': 'xpu:3', 'order': 'fifo',
                  'sequence': self.decode_sequence, 'thread': threading.current_thread().name,
                  'sample_rate': contract.SAMPLE_RATE, 'tensors': tensors, 'last_frame_sha256': last_sha,
                  'anchor_diagnostics': diagnostic, 'capture': capture, 'frame_anchor': frame_anchor,
                  'xpu3_free_before_decode': free,
                  'preview': {'path': str(job['preview_path']),
                              'record': str(self.run / 'receipts' / ('preview-' + job['run_name'] + '.json'))},
                  'timing_ns': timing,
                  'timing_s': {'queue_wait': stream_receipts.seconds(timing, 'decode_queued', 'decode_start'),
                               'decode': stream_receipts.seconds(timing, 'decode_start', 'decode_done'),
                               'anchor_ready_to_decode_done':
                                   stream_receipts.seconds(timing, 'anchor_ready', 'decode_done'),
                               'submit_to_decode_done': stream_receipts.seconds(timing, 'submit', 'decode_done')}}
        stream_receipts.validate_decode_record(record)
        self.write('receipts/decode-' + job['run_name'] + '.json', record)
        if not self.geometry_recorded:
            self.geometry_recorded = True
            self.write('stream-geometry-measured.json', {
                'frames': self.frames, 'first_chunk': job['run_name'],
                'latent_shapes': job['latent_shapes'], 'decoded_shapes': observed,
                'expected': {**self.geometry['latent_shapes'], **self.geometry['decoded_shapes']},
                'provenance': self.geometry['provenance'], 'matches': True})
        preview_images, preview_audio = stream_preview.private_copy(images, audio)
        del images, audio
        self.preview.submit({'run_name': job['run_name'], 'prompt_id': job['prompt_id'], 'images': preview_images,
                             'audio': preview_audio, 'path': job['preview_path'], 'relative': job['relative'],
                             'includes_overlap_frame': job['includes_overlap_frame'],
                             'timing': {'submit': timing['submit'], 'decode_done': done}})
        return record

    def inspect_state(self):
        import runtime_observer
        return runtime_observer.actual_state(fault=self.fault())

    def storage_check(self, mutate=True):
        free = shutil.disk_usage(self.root).free
        consumed = self.free_at_install - free
        self.session.require(free >= RESERVE_BYTES and consumed <= RUN_ALLOWANCE,
                             'Stream storage allowance exhausted (50 GiB reserve, 3 GiB run allowance)')
        return {'free_bytes': free, 'consumed_bytes': consumed, 'allowance_bytes': RUN_ALLOWANCE,
                'reserve_bytes': RESERVE_BYTES}

    def expected_routes(self):
        a = self.authority
        return {'state': a.expected_routes(), 'owner_thread': a.owner_thread, 'placement': self.placement,
                'frozen': a.expected_frozen(), 'frozen_signatures': self.frozen_signatures}

    def write(self, name, value):
        return self.session.write_exclusive(self.run / name, value)

    def active_row(self, name):
        self.authority.healthy()
        self.session.require(not self.fault(), 'Fault prevents streaming')
        active = self.authority.active
        self.session.require(active is not None and active['name'] == name, 'No admitted active request ' + name)
        return active

    def active_capture_request(self):
        """Capture-guard callback. Packet114 captures are written by the decode thread; the guard
        still admits exactly the nine registered rows in order, each once, by prompt identity."""
        cap = self.capturing
        self.session.require(cap is not None and cap['thread'] == threading.get_ident(),
                             'Full captures are written only by the decode thread for qualification chunks')
        return {'name': cap['name'], 'prompt_id': cap['prompt_id'], 'plan_sha256': cap['plan_sha256'],
                'graph_sha256': cap['graph_sha256']}

    # -- executor hooks -------------------------------------------------------
    def before_request(self, row, prompt_id):
        import stream_receipts
        self.session.require(not self.action_busy, 'An action is active')
        self.storage_check()
        if row['kind'] in CHUNK_KINDS:
            drained = False
            if row['kind'] in contract.GATED_KINDS:
                # Gated requests may capture sampler or text graphs; no decode runs beside a capture.
                self.session.require(self.decoder.drain(DECODE_DRAIN_BOUND_S),
                                     'Decode thread did not drain before a gated request: %r' % self.decoder.summary())
                drained = True
            self.session.require(self.decoder.failed is None and self.preview.failed is None,
                                 'Decode or preview worker failed')
            self.session.require(self.adapter is not None and self.adapter.ready and
                                 self.adapter.failed is None and self.conditioning is not None and
                                 self.latent_guard is not None, 'Stream runtime has not been prepared')
            self.session.require(self.conditioning.active is None and self.latent_guard.active is None and
                                 self.current is None, 'Prior request ownership remains active')
            self.registry.check()
            self.bindings.check_native()
            self.bindings.settings()
            self.current = {'name': row['name'], 'prompt_id': prompt_id, 'row': copy.deepcopy(row),
                            'timing': {k: None for k in stream_receipts.TIMING_KEYS},
                            'anchor_in': None, 'anchor_image': None, 'latent_parts': None, 'provided': False,
                            'text': None, 'output': None, 'decode_job': None,
                            'decode_at_start': {'drained': drained, 'pending': self.decoder.pending(),
                                                'current': self.decoder.summary()['current']}}
            self.current['timing']['submit'] = self.submit_ns.pop(prompt_id, None)
            self.current['timing']['execution_start'] = self.authority.active['start_ns']
            before = self.adapter.before_request(row['name'])
            self.current['memory_before'] = before
            self.current['captured_before'] = self.adapter.last_inventory['captured_graphs']

    def _consumer(self, name, kind):
        """Common checks of the single anchor provider of an admitted conditioned request."""
        active = self.active_row(name)
        cur = self.current
        params = active['params']
        self.session.require(cur is not None and cur['name'] == name and params is not None and
                             contract.anchored(params) and not cur['provided'] and self.anchor == kind,
                             'Anchor provider is not the single admitted consumer')
        self.session.require(self.adapter.current_name == name and self.adapter.guard is not None,
                             'Anchor loading requires the active no-eviction scope')
        pred = cur['row']['predecessor']
        self.session.require(type(pred) is dict and pred['last_chunk'] == params['chunk_index'] - 1 and
                             pred.get('anchor_kind') == kind,
                             'Predecessor is not the last completed chunk of this chain')
        live = self.authority.chains[active['chain']]
        self.session.require(live['anchor_sha256'] == pred['anchor_sha256'] and
                             live['anchor_path'] == pred['anchor_path'], 'Scene anchor changed during request')
        return active, cur, params, pred

    def provide_anchor(self, name, predecessor_anchor_sha256):
        """Frame anchor (LTX_ANCHOR=frame): packet113's provider."""
        import torch
        import stream_receipts
        with self.authority.lock:
            active, cur, params, pred = self._consumer(name, 'frame')
            self.session.require(predecessor_anchor_sha256 == params['predecessor_anchor_sha256'],
                                 'Provider input differs from the admitted request')
            if params['kind'] == 'stream':
                self.session.require(predecessor_anchor_sha256 == pred['anchor_sha256'], 'Stale predecessor anchor')
            raw = stream_receipts.read_anchor(pred['anchor_path'], pred['anchor_sha256'])
            self.bindings.check_native()
            image = torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(*contract.ANCHOR_SHAPE).clone()
            self.active_row(name)
            self.conditioning.begin_request(name, anchor=image, expected_anchor_sha256=pred['anchor_sha256'])
            cur.update(provided=True, anchor_image=image,
                       anchor_in={'kind': 'frame', 'sha256': pred['anchor_sha256'], 'path': pred['anchor_path'],
                                  'source_run_name': pred['run_name']})
            return image

    def provide_latent_anchor(self, name, predecessor_anchor_sha256):
        """Latent anchor (LTX_ANCHOR=latent): the two verified slices of the predecessor's anchor file."""
        import torch
        import latent_anchor
        with self.authority.lock:
            active, cur, params, pred = self._consumer(name, 'latent')
            self.session.require(predecessor_anchor_sha256 == params['predecessor_anchor_sha256'],
                                 'Provider input differs from the admitted request')
            if params['kind'] == 'stream':
                self.session.require(predecessor_anchor_sha256 == pred['anchor_sha256'], 'Stale predecessor anchor')
            raw = latent_anchor.read_anchor(pred['anchor_path'], pred['anchor_sha256'])
            parts = latent_anchor.split(torch, raw)
            self.active_row(name)
            self.latent_guard.begin_request(name, pred['anchor_sha256'], parts)
            cur.update(provided=True, latent_parts=parts,
                       anchor_in={'kind': 'latent', 'sha256': pred['anchor_sha256'], 'path': pred['anchor_path'],
                                  'source_run_name': pred['run_name']})
            return ({'samples': parts[0]}, {'samples': parts[1]})

    def condition(self, vae, image, latent, strength, bypass, run_name, stage):
        """Frame anchor: packet113's native image conditioning through the stage guard."""
        with self.authority.lock:
            self.active_row(run_name)
            cur = self.current
            self.session.require(self.anchor == 'frame' and cur is not None and cur['name'] == run_name and
                                 cur['provided'] and image is cur['anchor_image'] and
                                 image is self.conditioning.anchor and
                                 type(strength) in (float, int) and strength == 1.0 and bypass is False and
                                 stage in ('A', 'B'), 'Conditioning node differs from its fixed inputs')
            self.session.require(self.adapter.current_name == run_name and self.adapter.guard is not None,
                                 'Conditioning requires the active no-eviction scope')
            return self.conditioning.run_stage(stage, request_id=run_name, vae=vae, latent=latent,
                                               native_call=self.bindings.native_call)

    def latent_condition(self, latent, anchor, strength, run_name, stage):
        with self.authority.lock:
            self.active_row(run_name)
            cur = self.current
            self.session.require(self.anchor == 'latent' and cur is not None and cur['name'] == run_name and
                                 cur['provided'] and cur['latent_parts'] is not None and stage in ('A', 'B'),
                                 'Latent conditioning node differs from its fixed inputs')
            self.session.require(self.adapter.current_name == run_name and self.adapter.guard is not None,
                                 'Conditioning requires the active no-eviction scope')
            self.bindings.check_native()
            return self.latent_guard.run_stage(stage, request_id=run_name, latent=latent, anchor=anchor,
                                               strength=strength)

    def text(self, run_name, text, conditioning):
        import torch
        with self.authority.lock:
            active = self.active_row(run_name)
            cur, params = self.current, active['params']
            self.session.require(cur is not None and cur['text'] is None and text == params['prompt'],
                                 'Text node differs from the admitted request')
            text_sha = contract.text_sha256(text)
            if conditioning is not None:
                self.session.require(not params['reuse_text'], 'Fresh encode in a reuse request')
                rows = _tensor_rows(torch, conditioning)
                self.session.require(rows, 'Conditioning carries no tensor')
                if self.text_reuse and params['kind'] != 'qualify-eager':
                    # Keep exactly one cached encode: the chain's most recent fresh prompt.
                    self.text_cache = {'chain': active['chain'], 'run_name': run_name, 'text_sha256': text_sha,
                                       'value': copy.deepcopy(conditioning), 'rows': rows}
                cur['text'] = {'reused': False, 'tensors': rows, 'prompt_sha256': text_sha}
                return conditioning
            self.session.require(params['reuse_text'] == 1, 'Missing conditioning in a fresh-encode request')
            entry = self.text_cache
            self.session.require(entry is not None and entry['chain'] == active['chain'] and
                                 entry['text_sha256'] == text_sha, 'No cached conditioning for this prompt')
            served = copy.deepcopy(entry['value'])
            rows = _tensor_rows(torch, served)
            self.session.require(rows == entry['rows'], 'Cached conditioning changed')
            cur['text'] = {'reused': True, 'tensors': rows, 'prompt_sha256': text_sha,
                           'source_run_name': entry['run_name']}
            return served

    def output(self, run_name, video_latent, audio_latent, stage_a_latent, vae, audio_vae, fields):
        import torch
        import folder_paths
        import latent_anchor
        import stream_receipts
        require = self.session.require
        with self.authority.lock:
            active = self.active_row(run_name)
            cur, params = self.current, active['params']
            require(cur is not None and cur['output'] is None and cur['name'] == run_name,
                    'Output node is not the single admitted consumer')
            require(fields == {k: params[k] for k in fields} and set(fields) == set(params) - {'prompt'},
                    'Output node inputs differ from request')
            require(vae is self.adapter.objects['video_vae'] and audio_vae is self.adapter.objects['audio_vae'],
                    'Output node VAEs are not the admitted resident VAEs')
            latents = {'video_latent': video_latent['samples'], 'audio_latent': audio_latent['samples'],
                       'stage_a_latent': stage_a_latent['samples']}
            observed = {k: list(v.shape) for k, v in latents.items()}
            if observed != self.geometry['latent_shapes']:
                self._geometry_mismatch(run_name, observed)
            summary = {name: _summary(torch, value, self.geometry['latent_shapes'][name], name, require)
                       for name, value in latents.items()}
            anchored = contract.anchored(params)
            pin = None
            anchor_out = None
            if self.anchor == 'latent':
                raw = latent_anchor.anchor_bytes(torch, latents['stage_a_latent'], latents['video_latent'],
                                                 self.frames)
                anchor_out = latent_anchor.write_anchor(self.run / 'anchors', run_name, raw, self.frames)
                # Anchor ready: everything the next chunk consumes is hashed and durable.
                cur['timing']['anchor_ready'] = time.time_ns()
                if anchored:
                    a, b = cur['latent_parts']
                    pin = {'A': latent_anchor.pin_diagnostic(torch, latents['stage_a_latent'], a),
                           'B': latent_anchor.pin_diagnostic(torch, latents['video_latent'], b)}
            output_dir = Path(folder_paths.get_output_directory())
            path, relative = stream_preview.predict_preview_path(run_name + '/preview', str(output_dir),
                                                                 contract.WIDTH, contract.HEIGHT)
            require(path.is_absolute() and path.parent.parent == output_dir and
                    path.parent.name == run_name and not path.exists() and path.name.endswith('.mp4'),
                    'Preview path is not a fresh MP4 in this chunk\'s output folder')
            capture = None
            if params['kind'] in contract.CAPTURE_KINDS:
                row = next(r for r in self.capture_rows if r['name'] == run_name)
                capture = {'name': run_name, 'prompt_id': cur['prompt_id'], 'plan_sha256': self.session.PLAN_SHA256,
                           'graph_sha256': row['graph_sha256']}
            job = {'run_name': run_name, 'prompt_id': cur['prompt_id'], 'kind': params['kind'],
                   'stream_seq': params['stream_seq'], 'chunk_index': params['chunk_index'],
                   # Private CPU copies: the decode thread can never alias what this chunk hashed.
                   'video_latent': latents['video_latent'].detach().to('cpu', copy=True).clone(),
                   'audio_latent': latents['audio_latent'].detach().to('cpu', copy=True).clone(),
                   'latent_shapes': observed, 'vae': vae, 'audio_vae': audio_vae,
                   'preview_path': path, 'relative': relative, 'includes_overlap_frame': anchored,
                   'capture': capture,
                   'timing': {'submit': cur['timing']['submit'], 'anchor_ready': cur['timing']['anchor_ready']}}
            cur['decode_job'] = job
            cur['output'] = {'tensors': summary, 'anchor_out': anchor_out, 'slot0_pin': pin,
                             'decode': {'state': 'queued', 'device': 'xpu:3',
                                        'record': str(self.run / 'receipts' / ('decode-' + run_name + '.json'))},
                             'preview': {'path': str(path), 'relative_to_output_directory': relative,
                                         'state': 'queued', 'bytes': None,
                                         'record': str(self.run / 'receipts' / ('preview-' + run_name + '.json')),
                                         'container': 'mp4', 'lossy': True, 'fps': contract.FPS,
                                         'frames': self.frames, 'includes_overlap_frame': anchored}}
        # Outside the authority lock: back-pressure must not block the status route.
        queued, depth, blocked = self.decoder.submit(job)
        record = self.decoder.wait(job) if self.anchor == 'frame' else None
        with self.authority.lock:
            self.active_row(run_name)
            cur['timing']['decode_queued'] = queued
            cur['output']['decode'].update(queue_depth_at_submit=depth, submit_blocked_s=blocked)
            if record is not None:
                # Frame anchor: the decoded last frame, written by the chain once the decode returned.
                raw = job.pop('anchor_bytes')
                require(hashlib.sha256(raw).hexdigest() == record['last_frame_sha256'],
                        'Decoded anchor frame differs from its decode record')
                anchor_out = stream_receipts.write_anchor(self.run / 'anchors', run_name, raw, self.frames)
                cur['timing']['decode_done'] = record['timing_ns']['decode_done']
                cur['timing']['anchor_ready'] = time.time_ns()
                cur['output'].update(anchor_out=anchor_out)
                cur['output']['decode'].update(state='done', sequence=record['sequence'])
        return {'ui': {'text': [str(path)]}}

    def _conditioning_policy(self, name):
        receipts = [r for r in self.conditioning.receipts if r['request_id'] == name]
        stages = [r for r in receipts if r['event'] == 'stage']
        self.session.require(len(stages) == 2 and [r['stage'] for r in stages] == ['A', 'B'] and
                             all(r['completed'] is True for r in stages), 'Conditioning stages incomplete')
        before = [[r['before']['required_physical_free_bytes']['xpu:%d' % i] for i in range(4)] for r in stages]
        after = [v for r in stages for v in r['after']['required_physical_free_bytes'].values()]
        self.session.require(before == [[8 * GIB, 8 * GIB, 2 * GIB, 9 * GIB]] * 2 and after == [2 * GIB] * 8,
                             'Conditioning memory floors changed')
        return receipts, [{'stage': r['stage'],
                           'free_before': r['before']['snapshot']['physical_free_bytes'],
                           'free_after': r['after']['snapshot']['physical_free_bytes']} for r in stages]

    def after_request(self, row, prompt_id):
        name = row['name']
        if row['kind'] == 'window-probe':
            import setup_gates
            value = self.session.strict_json(self.session.read_regular(self.run / ('text-window-probe-' + name + '.json')))
            checked = setup_gates.validate_window(value, name, self.identity_sha)
            self.write('stream-setup-accepted-' + name + '.json', checked)
        elif row['kind'] == 'prepare':
            self.session.require(self.adapter is not None and self.adapter.ready and self.adapter.failed is None,
                                 'Preparation did not finish')
        else:
            self._after_chunk(row, prompt_id)
        self.storage_check()

    def _after_chunk(self, row, prompt_id):
        import stream_receipts
        name, params, cur = row['name'], row['params'], self.current
        self.session.require(cur is not None and cur['name'] == name and cur['output'] is not None and
                             cur['text'] is not None and cur['output']['anchor_out'] is not None,
                             'Chunk request skipped its output or text node')
        conditioning_memory = []
        guard_receipts = []
        anchored = contract.anchored(params)
        if anchored:
            self.session.require(cur['provided'], 'Conditioned request skipped its provider')
            if self.anchor == 'frame':
                self.conditioning.finish_request(name)
                guard_receipts, conditioning_memory = self._conditioning_policy(name)
            else:
                self.latent_guard.finish_request(name)
                guard_receipts = self.latent_guard.drain(name)
                stages = [r for r in guard_receipts if r['event'] == 'stage']
                self.session.require([r['stage'] for r in stages] == ['A', 'B'] and
                                     all(r['completed'] is True for r in stages), 'Latent conditioning incomplete')
        else:
            self.session.require(not cur['provided'] and self.conditioning.active is None and
                                 self.latent_guard.active is None, 'An unanchored chunk cannot consume an anchor')
        after = self.adapter.after_request(name)
        inventory = self.adapter.last_inventory
        verdict = inventory['verdict']
        graph = {'gate_mode': 'original' if params['kind'] == 'qualify-eager' else 'graph',
                 'routes': verdict['routes'], 'signatures_per_route': verdict.get('signatures_per_route', 0),
                 'captured_graphs_total': inventory['captured_graphs'],
                 'new_captures': inventory['captured_graphs'] - cur['captured_before'],
                 'route_state': verdict['state'], 'captures_frozen': self.authority.expected_frozen()}
        capture = None
        if params['kind'] in contract.CAPTURE_KINDS:
            capture = {'path': str(self.root / 'output/validation' / name / 'tensors.safetensors'),
                       'writer': 'decode thread', 'record': cur['output']['decode']['record']}
        pred = row['predecessor']
        chain_ok = (cur['anchor_in'] is None) if not anchored else (
            cur['anchor_in']['sha256'] == pred['anchor_sha256'] and cur['anchor_in']['kind'] == self.anchor and
            (params['kind'] != 'stream' or params['predecessor_anchor_sha256'] == pred['anchor_sha256']))
        self.session.require(chain_ok, 'Anchor chain check failed')
        events = self.events.pop(cur['prompt_id'], {})
        timing = cur['timing']
        for node, key in stream_receipts.EVENT_NODES.items():
            timing[key] = events.get(node)
        timing['receipt_staged'] = time.time_ns()
        prior = prior_decode = None
        if pred is not None:
            record = self.preview.record(pred['run_name'])
            if record is not None:
                prior = {'run_name': record['run_name'], 'preview_written_ns': record['timing_ns']['preview_written'],
                         'bytes': record['bytes'], 'sha256': record['sha256'], 'timing_s': record['timing_s']}
            record = self.decoder.record(pred['run_name'])
            if record is not None:
                prior_decode = {'run_name': record['run_name'], 'decode_done_ns': record['timing_ns']['decode_done'],
                                'images_sha256': record['tensors']['images']['sha256'],
                                'timing_s': record['timing_s']}
        compact = lambda r: {'free': r['snapshot']['physical_free_bytes'],
                             'peaks': r['snapshot']['peaks'], 'required': r['required_physical_free_bytes']}
        s = stream_receipts.seconds
        receipt = {
            'schema': stream_receipts.SCHEMA, 'run_name': name, 'prompt_id': prompt_id, 'kind': params['kind'],
            'scene_id': params['scene_id'], 'chunk_index': params['chunk_index'], 'seed': params['seed'],
            'stream_seq': params['stream_seq'], 'prompt_sha256': contract.text_sha256(params['prompt']),
            'frames': self.frames, 'placement': self.placement, 'anchor': self.anchor,
            'reuse_text': params['reuse_text'], 'server_text_reuse': self.text_reuse,
            'anchored': anchored, 'reset': bool(params['reset']),
            'reset_predecessor_anchor_sha256': params['predecessor_anchor_sha256'] if params['reset'] else None,
            'prompt_changed': (None if not params['chunk_index'] else
                               contract.text_sha256(params['prompt']) != pred['text_sha256']),
            'plan_sha256': self.session.PLAN_SHA256,
            'qualification_id': self.authority.qid, 'runtime_manifest_sha256': self.manifest_sha,
            'server_identity_sha256': self.identity_sha,
            'qualification_verdict_sha256': self.authority.verdict_sha,
            'tensors': cur['output']['tensors'], 'anchor_in': cur['anchor_in'],
            'anchor_out': cur['output']['anchor_out'], 'slot0_pin': cur['output']['slot0_pin'],
            'delivery': stream_receipts.delivery(params['chunk_index'], self.frames, anchored),
            'decode': cur['output']['decode'], 'preview': cur['output']['preview'],
            'predecessor_preview': prior, 'predecessor_decode': prior_decode,
            'decode_at_start': cur['decode_at_start'],
            'capture': capture, 'timing_ns': timing,
            'timing_s': {'submit_to_sampler_start': s(timing, 'submit', 'sampler_a_start'),
                         'sampler_a_bucket': s(timing, 'sampler_a_start', 'sampler_b_start'),
                         'sampler_a_split': {'sampler_a': s(timing, 'sampler_a_start', 'stage_a_done'),
                                             'separate_to_upsampler': s(timing, 'stage_a_done', 'upsampler_start'),
                                             'upsampler_to_condition_b': s(timing, 'upsampler_start',
                                                                           'condition_b_start'),
                                             'condition_b_to_concat': s(timing, 'condition_b_start', 'concat_b_start'),
                                             'concat_to_sampler_b': s(timing, 'concat_b_start', 'sampler_b_start')},
                         'sampler_b': s(timing, 'sampler_b_start', 'stage_b_done'),
                         'stage_b_done_to_anchor_ready': s(timing, 'stage_b_done', 'anchor_ready'),
                         'submit_to_anchor_ready': s(timing, 'submit', 'anchor_ready'),
                         'anchor_ready_to_receipt_staged': s(timing, 'anchor_ready', 'receipt_staged'),
                         'decode_in_chain': s(timing, 'decode_queued', 'decode_done'),
                         # Latent anchor: in receipts/decode-<run_name>.json and preview-<run_name>.json.
                         'submit_to_decode_done': s(timing, 'submit', 'decode_done'),
                         'submit_to_preview_written': None},
            'text': cur['text'], 'graph': graph,
            'memory': {'before': compact(cur['memory_before']), 'after': compact(after),
                       'conditioning': conditioning_memory},
            'storage': self.storage_check(),
            'sanity': {'finite': True, 'shapes': True, 'anchor_chain': True}}
        stream_receipts.validate_receipt(receipt)
        safety = self.adapter.controller.drain()
        if params['kind'] != 'stream':
            self.write('safety-' + name + '.json', {'controller_receipts': safety, 'guard_receipts': guard_receipts,
                                                    'adapter_receipts': self.adapter.drain_receipts()})
        self.conditioning.receipts = [r for r in self.conditioning.receipts if r['request_id'] != name]
        self.authority.stage_receipt(name, receipt)
        self.current = None

    def on_failure(self, row, prompt_id, error):
        adapter = self.adapter
        try:
            if adapter is not None and adapter.controller is not None:
                adapter.abort_request(error)
        finally:
            self.write('stream-failure-' + row['name'] + '.json', {
                'run_name': row['name'], 'prompt_id': prompt_id, 'error': str(error)[:4000],
                'adapter_receipts': adapter.receipts if adapter is not None else [],
                'controller_receipts': adapter.controller.receipts if adapter is not None and adapter.controller is not None else [],
                'conditioning_receipts': self.conditioning.receipts if self.conditioning is not None else [],
                'latent_guard_receipts': self.latent_guard.receipts if self.latent_guard is not None else [],
                'preview_writer': self.preview.summary(), 'decoder': self.decoder.summary(),
                'current': {k: v for k, v in (self.current or {}).items() if k not in NON_TENSOR_CURRENT}})

    def prepare(self, name):
        import torch
        import nodes
        import comfy.model_management as mm
        import continuation_anchor
        import conditioning_guard
        import latent_anchor
        from comfy_api.latest import io
        from candidate_safety import CandidateAdapter
        from native_bindings import NativeBindings
        active = self.active_row(name)
        self.session.require(active['kind'] == 'prepare' and self.adapter is None, 'Unexpected/repeated preparation')
        hashes = {str(self.packet / path): value for path, value in self.manifest['files'].items()
                  if path.startswith('source/')}
        hashes.update(self.manifest['runtime']['files'])
        self.adapter = CandidateAdapter(expected_routes=self.expected_routes, torch=torch, nodes=nodes,
            model_management=mm, session=self.session, qualification_id=self.authority.qid,
            run_name=name, plan_sha256=self.session.PLAN_SHA256, runtime_sha256=self.manifest_sha,
            source_hashes=hashes, fault_check=self.fault)
        # Packet114: the decode thread and the prompt thread share ComfyUI's model registry.
        # Serialize load_models_gpu and the adapter's residency inspection (stream_decode.RegistryLock).
        lock_receipt = self.registry.install(mm)
        self.adapter._inspect = self.registry.wrap(self.adapter._inspect)
        snapshot = self.adapter.prepare()
        self.write('stream-preparation.json', {'snapshot': snapshot, 'receipts': self.adapter.drain_receipts(),
                                               'registry_lock': lock_receipt})
        self.bindings = NativeBindings(packet=self.packet, manifest=self.manifest, torch=torch, nodes=nodes,
            model_management=mm, adapter=self.adapter, anchor_module=continuation_anchor,
            guard_module=conditioning_guard, output_type=io.NodeOutput)
        self.conditioning = conditioning_guard.ConditioningStageGuard(controller=self.adapter.controller,
            tensor_metadata=self.bindings.tensor_metadata, inspect_anchor=self.bindings.inspect_anchor,
            inspect_encoder_cache=self.bindings.inspect_encoder_cache, unwrap_output=self.bindings.unwrap_output)
        native = self.bindings.function.__globals__
        get_noise_mask = native.get('get_noise_mask')
        self.session.require(callable(get_noise_mask) and
                             Path(get_noise_mask.__code__.co_filename).resolve() ==
                             (self.packet / 'source/comfy_extras/nodes_lt.py').resolve(),
                             'Native get_noise_mask is not the sealed nodes_lt.py function')
        self.latent_guard = latent_anchor.LatentConditionGuard(
            tensor_metadata=self.bindings.tensor_metadata, get_noise_mask=get_noise_mask, frames=self.frames)
        for node in ('VAEDecode', 'LTXVAudioVAEDecode', 'LTXBaselineCapture'):
            self.session.require(node in nodes.NODE_CLASS_MAPPINGS, 'Decode-thread node missing: ' + node)
        self.adapter.controller.drain()
        self.write('stream-native-binding.json', dict(self.bindings.receipt(), anchor=self.anchor,
                                                      latent_condition='nodes_lt.get_noise_mask (pinned source)'))
        return snapshot

    # -- admission (middleware) --------------------------------------------------
    def precheck(self, graph):
        """Non-mutating admission; raises session.Refusal."""
        Refusal = self.session.Refusal
        if self.action_busy:
            raise Refusal('busy', 'An action is running')
        if self.fault():
            raise Refusal('halted', 'Fault recorded; generation halted')
        try:
            self.storage_check(mutate=False)
        except RuntimeError as error:
            raise Refusal('storage', str(error))
        state = self.inspect_state()
        descriptor = self.authority.precheck(graph, state['queue_running_ids'], state['queue_pending'])
        params = descriptor['params']
        if params is not None:
            if params['reuse_text']:
                entry = self.text_cache
                if entry is None or entry['chain'] != descriptor['chain'] or \
                        entry['text_sha256'] != contract.text_sha256(params['prompt']):
                    raise Refusal('text-cache-missing', 'No cached conditioning for this prompt on this chain')
            else:
                window = self.window_precheck(params['prompt'])
                if self.qualified_windows is not None and window not in self.qualified_windows:
                    # A different text window changes the context length the transformer
                    # blocks see; after the freeze that would be a new graph signature.
                    raise Refusal('window-not-qualified', 'Prompt uses text window %s; this server qualified %s'
                                  % (window, sorted(self.qualified_windows)))
        return descriptor

    def window_precheck(self, text):
        if self.adapter is None or not self.adapter.ready:
            raise self.session.Refusal('not-prepared', 'Setup has not completed')
        try:
            return self.adapter.window.precheck(self.adapter.clip, text, self._encode_workers())['window']
        except Exception as error:
            raise self.session.Refusal('window-not-captured', str(error)[:500])

    def _encode_workers(self):
        stages = getattr(self.adapter.pipeline, '_STAGES', {})
        return [w.ident for w in stages.get('encode', {}).get('workers', []) if w.is_alive()]

    def record_event(self, data):
        import stream_receipts
        prompt_id, node = data.get('prompt_id'), data.get('node')
        if type(prompt_id) is str and type(node) is str and node in stream_receipts.EVENT_NODES:
            self.events.setdefault(prompt_id, {}).setdefault(node, time.time_ns())

    # -- verdict action ----------------------------------------------------------
    def quiescent(self):
        self.authority.healthy()
        self.session.require(self.authority.active is None and not self.fault(), 'Active/faulted action barrier')
        state = self.authority.check_state(self.inspect_state())
        return state

    def action(self, action):
        import qualification_gate
        with self.lock, self.authority.lock:
            self.authority.healthy()
            self.session.require(action == 'qualify-verdict' and action not in self.actions_done,
                                 'Only one qualify-verdict action exists')
            self.storage_check()
            self.session.require(self.decoder.drain(DECODE_DRAIN_BOUND_S),
                                 'Qualification decodes were not all done: %r' % self.decoder.summary())
            self.session.require(self.preview.drain(PREVIEW_DRAIN_BOUND_S),
                                 'Qualification previews were not all written: %r' % self.preview.summary())
            for row in self.authority.qualification_rows:
                self.session.require(self.preview.record(row['name']) is not None and
                                     self.decoder.record(row['name']) is not None,
                                     'Qualification decode or preview record missing: ' + row['name'])
            state = self.quiescent()
            self.session.require(self.authority.phase == 'stream_qualification' and
                                 len(self.authority.completed) == 11, 'Nine qualification requests required')
            receipts, decodes, captures, decode_bindings = [], {}, {}, {}
            for row in self.authority.qualification_rows:
                binding = self.authority.receipts[row['name']]
                raw = self.session.read_regular(Path(binding['path']))
                self.session.require(self.session.digest(raw) == binding['sha256'], 'Receipt changed: ' + row['name'])
                receipt = self.session.strict_json(raw)
                receipts.append(receipt)
                path = self.run / 'receipts' / ('decode-' + row['name'] + '.json')
                raw = self.session.read_regular(path)
                decodes[row['name']] = self.session.strict_json(raw)
                decode_bindings[row['name']] = {'path': str(path), 'sha256': self.session.digest(raw)}
                captures[row['name']] = qualification_gate.capture_tensor_hashes(receipt['capture']['path'], self.frames)
            observed = self.adapter.native_state()
            verdict = qualification_gate.decide(receipts, decodes, captures, self.session.PLAN_SHA256, self.frames,
                                                self.text_reuse, self.placement, self.anchor)
            verdict.update(receipts={r['run_name']: self.authority.receipts[r['run_name']] for r in receipts},
                           decode_records=decode_bindings,
                           preview_writer=self.preview.summary(), decoder=self.decoder.summary(),
                           captures=captures, observation_routes=observed['route_inventory'],
                           signature_digests=self.adapter.last_inventory['signature_digests'],
                           capture_guard=self.capture_guard.receipt(), state=state,
                           time_ns=time.time_ns())
            sha = self.write('stream-qualification-verdict.json', verdict)
            self.actions_done.add(action)
            if not verdict['passed']:
                self.authority.halt(RuntimeError('Qualification failed: ' + '; '.join(verdict['failures'])[:2000]))
                return {'passed': False, 'failures': verdict['failures'], 'verdict_sha256': sha}
            capture = self.adapter.capture
            self.qualified_windows = {self.window_precheck(p) for p in set(contract.QUALIFICATION_PROMPTS)}
            self.frozen_signatures = dict(self.adapter.last_inventory['signature_digests'])
            capture.CAPTURES_FROZEN[0] = True
            self.authority.accept_verdict(verdict, sha)
            self.adapter.native_state()  # the frozen contract must hold immediately
            self.write('stream-freeze.json', {'qualified_text_windows': sorted(self.qualified_windows),
                                              'frozen_signature_digests': self.frozen_signatures,
                                              'verdict_sha256': sha, 'time_ns': time.time_ns()})
            return {'passed': True, 'verdict_sha256': sha, 'phase': self.authority.phase,
                    'qualified_text_windows': sorted(self.qualified_windows)}


def _consume_task_exception(task):
    if not task.cancelled():
        task.exception()


async def _halt_after_worker(ctx, worker, error):
    try:
        try:
            await asyncio.shield(worker)
        except Exception:
            pass
        try:
            await asyncio.to_thread(ctx.authority.halt, error)
        except Exception as receipt_error:
            ctx.action_halt_receipt_error = repr(receipt_error)
    finally:
        if worker.done() and ctx.authority.failed is not None:
            ctx.action_busy = False


def _schedule_action_halt(ctx, worker, error):
    ctx.action_busy = True
    cleanup = asyncio.create_task(_halt_after_worker(ctx, worker, error))
    ctx.action_cleanup = cleanup
    cleanup.add_done_callback(_consume_task_exception)
    return cleanup


async def run_owned_action(ctx, action):
    """Own the worker thread even if the HTTP waiter is cancelled (as packet111)."""
    ctx.session.require(not ctx.action_busy and ctx.authority.failed is None,
                        'Action already active or authority halted')
    ctx.action_busy = True
    worker = asyncio.create_task(asyncio.to_thread(ctx.action, action))
    ctx.action_worker = worker
    worker.add_done_callback(_consume_task_exception)
    try:
        result = await asyncio.shield(worker)
    except asyncio.CancelledError:
        _schedule_action_halt(ctx, worker, RuntimeError('HTTP action cancelled; no retry'))
        raise
    except BaseException as error:
        cleanup = _schedule_action_halt(ctx, worker, error)
        await asyncio.shield(cleanup)
        raise
    else:
        ctx.action_busy = False
        return result


# -- nodes ---------------------------------------------------------------------
def _ctx():
    if _CTX is None:
        raise RuntimeError('Stream runtime not installed')
    return _CTX


class LTXStreamPrepare114:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING',)}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, run_name):
        _ctx().prepare(run_name)
        return {'ui': {'text': ['full residence admitted']}}


class LTXStreamAnchor114:
    """Frame anchor provider (LTX_ANCHOR=frame)."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING',), 'predecessor_anchor_sha256': ('STRING',)}}
    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def apply(self, run_name, predecessor_anchor_sha256):
        return (_ctx().provide_anchor(run_name, predecessor_anchor_sha256),)


class LTXStreamCondition114:
    """Frame anchor conditioning (LTX_ANCHOR=frame): native LTXVImgToVideoInplace through the stage guard."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'vae': ('VAE',), 'image': ('IMAGE',), 'latent': ('LATENT',),
            'strength': ('FLOAT', {'default': 1.0}), 'bypass': ('BOOLEAN', {'default': False}),
            'run_name': ('STRING',), 'stage': (['A', 'B'],)}}
    RETURN_TYPES = ('LATENT',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, vae, image, latent, strength, bypass, run_name, stage):
        return _ctx().condition(vae, image, latent, strength, bypass, run_name, stage)


class LTXStreamLatentAnchor114:
    """Latent anchor provider (LTX_ANCHOR=latent): (stage-A anchor, stage-B anchor)."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING',), 'predecessor_anchor_sha256': ('STRING',)}}
    RETURN_TYPES = ('LATENT', 'LATENT')
    RETURN_NAMES = ('anchor_a', 'anchor_b')
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def apply(self, run_name, predecessor_anchor_sha256):
        return _ctx().provide_latent_anchor(run_name, predecessor_anchor_sha256)


class LTXStreamLatentCondition114:
    """nodes_lt.py:156,172-175 with the anchor latent in place of the VAE encode."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'latent': ('LATENT',), 'anchor': ('LATENT',),
            'strength': ('FLOAT', {'default': 1.0}), 'run_name': ('STRING',), 'stage': (['A', 'B'],)}}
    RETURN_TYPES = ('LATENT',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, latent, anchor, strength, run_name, stage):
        return (_ctx().latent_condition(latent, anchor, strength, run_name, stage),)


class LTXStreamText114:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING',), 'text': ('STRING', {'multiline': True})},
                'optional': {'conditioning': ('CONDITIONING',)}}
    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, run_name, text, conditioning=None):
        return (_ctx().text(run_name, text, conditioning),)


class LTXStreamChunk114:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'video_latent': ('LATENT',), 'audio_latent': ('LATENT',),
            'stage_a_latent': ('LATENT',), 'vae': ('VAE',), 'audio_vae': ('VAE',),
            'run_name': ('STRING',), 'kind': (list(contract.KINDS),),
            'frames': ('INT', {'min': 49, 'max': 97}), 'placement': (sorted(contract.PLACEMENTS),),
            'anchor': (list(contract.ANCHORS),),
            'scene_id': ('STRING',), 'chunk_index': ('INT', {'min': 0, 'max': contract.MAX_STREAM_SEQ}),
            'seed': ('INT', {'min': 0, 'max': contract.SEED_MAX}),
            'stream_seq': ('INT', {'min': -1, 'max': contract.MAX_STREAM_SEQ}),
            'predecessor_anchor_sha256': ('STRING',), 'reuse_text': ('INT', {'min': 0, 'max': 1})},
                'optional': {'reset': ('INT', {'min': 0, 'max': 1})}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, video_latent, audio_latent, stage_a_latent, vae, audio_vae, run_name, kind, frames, placement,
              anchor, scene_id, chunk_index, seed, stream_seq, predecessor_anchor_sha256, reuse_text, reset=0):
        fields = {'kind': kind, 'frames': frames, 'placement': placement, 'anchor': anchor, 'scene_id': scene_id,
                  'chunk_index': chunk_index, 'seed': seed,
                  'stream_seq': stream_seq, 'predecessor_anchor_sha256': predecessor_anchor_sha256,
                  'reuse_text': reuse_text, 'reset': reset}
        return _ctx().output(run_name, video_latent, audio_latent, stage_a_latent, vae, audio_vae, fields)


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in (LTXStreamPrepare114, LTXStreamAnchor114,
    LTXStreamCondition114, LTXStreamLatentAnchor114, LTXStreamLatentCondition114, LTXStreamText114,
    LTXStreamChunk114)}


def install(packet, manifest, manifest_sha, run):
    global _CTX
    if _CTX is not None:
        raise RuntimeError('Stream runtime already installed')
    import execution
    import executor_guard
    _CTX = Runtime(packet, manifest, manifest_sha, run)
    result = executor_guard.install(execution.PromptExecutor, _CTX.authority,
                                    _CTX.before_request, _CTX.after_request, _CTX.on_failure)
    _CTX.write('stream-executor-guard.json', result)


def install_routes():
    global _ROUTES_INSTALLED
    if _ROUTES_INSTALLED or _CTX is None:
        raise RuntimeError('Stream routes require one sealed installation')
    from aiohttp import web
    from server import PromptServer
    ctx = _CTX
    server = PromptServer.instance
    original_send_sync = server.send_sync

    def send_sync(event, data, sid=None):
        if event == 'executing' and isinstance(data, dict):
            try:
                ctx.record_event(data)
            except Exception:  # observation only; never fails the prompt
                pass
        return original_send_sync(event, data, sid)
    server.send_sync = send_sync

    def refuse(code, message, status=409):
        return web.json_response({'error': {'code': code, 'message': message}}, status=status)

    @web.middleware
    async def admission(request, handler):
        if request.method == 'POST' and request.path == '/prompt':
            if ctx.action_busy:
                return refuse('busy', 'An action is running')
            if ctx.authority.failed is not None or ctx.fault():
                return refuse('halted', 'Stream server halted; inspect evidence', 503)
            try:
                body = await request.json()
            except Exception:
                return refuse('contract', 'Body must be JSON', 400)
            if type(body) is not dict or type(body.get('prompt')) is not dict:
                return refuse('contract', 'Body needs a prompt graph', 400)
            client_id, prompt_id = body.get('client_id'), body.get('prompt_id')
            if type(client_id) is not str or not client_id:
                return refuse('missing-client-id', 'client_id is required (timing events need it)', 400)
            if type(prompt_id) is not str or not UUID_RE.fullmatch(prompt_id):
                return refuse('missing-prompt-id', 'prompt_id must be a canonical lowercase UUID', 400)
            if set(body) - {'prompt', 'client_id', 'prompt_id'}:
                return refuse('contract', 'Only prompt, client_id and prompt_id are accepted', 400)
            submitted = time.time_ns()
            try:
                descriptor = await asyncio.to_thread(ctx.precheck, body['prompt'])
            except ctx.session.Refusal as error:
                return refuse(error.code, str(error))
            except Exception as error:
                return refuse('precheck-error', str(error)[:500], 503)
            ctx.submit_ns[prompt_id] = submitted
            while len(ctx.submit_ns) > 16:
                ctx.submit_ns.pop(next(iter(ctx.submit_ns)))
            response = await handler(request)
            if getattr(response, 'status', 200) != 200:
                ctx.submit_ns.pop(prompt_id, None)
            return response
        return await handler(request)
    server.app.middlewares.append(admission)

    @server.routes.get('/ltx-stream/status')
    async def status(request):
        if ctx.action_busy:
            return web.json_response({'error': {'code': 'busy', 'message': 'action active'}}, status=409)
        result = ctx.authority.status()
        result.update(server_identity_sha256=ctx.identity_sha, runtime_manifest_sha256=ctx.manifest_sha,
                      plan_sha256=ctx.session.PLAN_SHA256, qualification_id=ctx.authority.qid, frames=ctx.frames,
                      anchor=ctx.anchor, fault=ctx.fault(), receipt_dir=str(ctx.run / 'receipts'),
                      qualified_text_windows=None if ctx.qualified_windows is None else sorted(ctx.qualified_windows),
                      output_directory=str(ctx.root / 'output'), packet=contract.PACKET,
                      features={'latent_anchor': ctx.anchor == 'latent', 'decode_thread': True,
                                'async_preview': True, 'chain_reset': True, 'anchor_diagnostics': True,
                                'chunk_length_choice': True, 'text_reuse_default_on': True},
                      decode_worker=ctx.decoder.summary(), preview_writer=ctx.preview.summary())
        try:
            result['storage'] = ctx.storage_check(mutate=False)
        except RuntimeError as error:
            result['storage'] = {'refused': str(error)}
        return web.json_response(result)

    def record_route(prefix, *workers):
        async def route(request):
            name = request.match_info['run_name']
            if not RUN_NAME_RE.fullmatch(name):
                return refuse('contract', 'Invalid run name', 400)
            path = ctx.run / 'receipts' / (prefix + name + '.json')
            if not path.is_file():
                # A record that can no longer come: its own worker or one upstream of it failed.
                for worker in workers:
                    if worker.failed is not None:
                        return refuse('halted', '%s failed: %s' % (worker.name if hasattr(worker, 'name') else
                                                                  'preview writer', worker.failed[:500]), 503)
                return refuse('not-found', 'No committed %s record for %s' % (prefix.rstrip('-'), name), 404)
            return web.Response(body=ctx.session.read_regular(path), content_type='application/json')
        return route

    server.routes.get('/ltx-stream/receipt/{run_name}')(record_route('receipt-'))
    server.routes.get('/ltx-stream/decode/{run_name}')(record_route('decode-', ctx.decoder))
    server.routes.get('/ltx-stream/preview/{run_name}')(record_route('preview-', ctx.decoder, ctx.preview))

    @server.routes.post('/ltx-stream/action')
    async def action(request):
        if ctx.action_busy:
            return refuse('busy', 'action already active')
        body = await request.json()
        if type(body) is not dict or set(body) != {'action'} or type(body['action']) is not str:
            return refuse('contract', 'one named action required', 400)
        try:
            return web.json_response(await run_owned_action(ctx, body['action']))
        except Exception as error:
            return web.json_response({'error': {'code': 'action-failed', 'message': str(error)[:2000]},
                                      'halted': ctx.authority.failed is not None}, status=409)
    _ROUTES_INSTALLED = True

"""Packet113 streaming runtime (packet112 plus two changes). Inert until the sealed launcher calls install().

Packet113 changes, nothing else: (1) the chunk is committed at "anchor ready" and its
MP4 preview is written afterwards by one bounded, in-order preview-writer thread
(stream_preview.py), which commits receipts/preview-<run_name>.json; (2) a stream
chunk flagged `reset` is an unanchored chunk in the stream_seq 0 form that restarts
the anchor chain. Receipts also carry a diagnostic border-vs-centre colour summary
of the anchor frame. The sampler, conditioning, decoder and every numerical path
are packet112's.


Setup (window probe, full-residency preparation) -> nine qualification chunks ->
explicit verdict action -> unbounded serial stream chunks. Per-block graph replay
(LTXGraphCaptureGate all48, chain 1) under the candidate safety contract; both
native image-conditioning nodes before both samplers; native decoders; the
preview MP4 written by the registered pipeline-save writer. Any failure inside
an admitted request latches the authority and refuses later requests. No retry,
allocator reset, settings change, process action or device import at module import.
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

_CTX = None
_ROUTES_INSTALLED = False
GIB = 2 ** 30
RESERVE_BYTES = 50 * GIB
RUN_ALLOWANCE = 3 * GIB
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
RUN_NAME_RE = re.compile(r'stream112-(s[0-9]{8}|q(eager|graph|repeat)-c00000[0-2])')
PREVIEW_DRAIN_BOUND_S = 120.0     # the verdict waits at most this long for queued previews
CHUNK_KINDS = contract.KINDS


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
        reuse = os.environ.get('LTX_STREAM_TEXT_REUSE', '0')
        session.require(reuse in ('0', '1'), 'LTX_STREAM_TEXT_REUSE must be 0 or 1')
        self.text_reuse = int(reuse)
        self.frames = contract.launch_frames()
        self.placement = contract.launch_placement()
        self.geometry = contract.geometry(self.frames)
        (self.run / 'receipts').mkdir()
        (self.run / 'anchors').mkdir()
        self.lock = threading.RLock()
        self.action_busy = False
        self.actions_done = set()
        self.action_worker = self.action_cleanup = None
        self.action_halt_receipt_error = None
        self.adapter = self.bindings = self.conditioning = None
        self.frozen_signatures = None
        self.qualified_windows = None   # text-window buckets exercised by qualification
        self.current = None
        self.submit_ns = {}
        self.events = {}
        self.text_cache = None     # the last fresh encode: {'chain', 'run_name', 'text_sha256', 'value', 'rows'}
        self.authority = session.configure(self.packet / 'resolution/stream-plan.json', manifest_sha,
                                           self.identity_sha, self.run, self.inspect_state, self.text_reuse,
                                           self.frames, self.placement)
        session.require(session.digest(Path(capture.__file__).read_bytes()) ==
                        manifest['files']['source/scripts/ltx_duration_guard.py'],
                        'Capture guard differs from sealed source')
        rows = [{'name': row['name'], 'role': 'full',
                 'graph_sha256': row['graph_sha256'][self.authority.variant + '/%d' % self.text_reuse]}
                for row in self.authority.qualification_rows]
        self.capture_guard = capture.configure(session.PLAN_SHA256, rows, self.active_capture_request)
        self.preview = stream_preview.StreamPreviewWriter(self._save_preview, self._commit_preview,
                                                          self._preview_failed)
        self.free_at_install = shutil.disk_usage(self.root).free
        self.storage_check()

    # -- observation ----------------------------------------------------------
    def fault(self):
        return ((self.root / 'FAULT.json').exists() or (self.run / 'stream-halt.json').exists() or
                self.preview.failed is not None)

    # -- preview writer (packet113) -------------------------------------------
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
            # Latch without holding the writer: the executor thread may own the authority lock.
            threading.Thread(target=self.authority.halt, name='ltx113-preview-halt', daemon=True,
                             args=(RuntimeError('Preview write failed for %s: %r' % (name, error)),)).start()

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
        with self.authority.lock:
            active = self.authority.active
            self.session.require(active is not None and active['kind'] in contract.CAPTURE_KINDS,
                                 'Full captures are written only by qualification requests')
            self.active_row(active['name'])
            row = next(r for r in self.authority.qualification_rows if r['name'] == active['name'])
            return {'name': active['name'], 'prompt_id': active['prompt_id'],
                    'plan_sha256': self.session.PLAN_SHA256,
                    'graph_sha256': row['graph_sha256'][self.authority.variant + '/%d' % self.text_reuse]}

    # -- executor hooks -------------------------------------------------------
    def before_request(self, row, prompt_id):
        self.session.require(not self.action_busy, 'An action is active')
        self.storage_check()
        if row['kind'] in CHUNK_KINDS:
            self.session.require(self.adapter is not None and self.adapter.ready and
                                 self.adapter.failed is None and self.conditioning is not None,
                                 'Stream runtime has not been prepared')
            self.session.require(self.conditioning.active is None and self.current is None,
                                 'Prior request ownership remains active')
            self.bindings.check_native()
            self.bindings.settings()
            self.current = {'name': row['name'], 'prompt_id': prompt_id, 'row': copy.deepcopy(row),
                            'timing': {k: None for k in ('submit', 'execution_start', 'sampler_a_start',
                                       'sampler_b_start', 'decode_start', 'decode_done', 'anchor_ready',
                                       'preview_queued', 'preview_written', 'receipt_staged')},
                            'anchor_in': None, 'anchor_image': None, 'provided': False,
                            'text': None, 'output': None}
            self.current['timing']['submit'] = self.submit_ns.pop(prompt_id, None)
            self.current['timing']['execution_start'] = self.authority.active['start_ns']
            before = self.adapter.before_request(row['name'])
            self.current['memory_before'] = before
            self.current['captured_before'] = self.adapter.last_inventory['captured_graphs']

    def provide_anchor(self, name, predecessor_anchor_sha256):
        import torch
        with self.authority.lock:
            active = self.active_row(name)
            cur = self.current
            params = active['params']
            self.session.require(cur is not None and cur['name'] == name and params is not None and
                                 contract.anchored(params) and not cur['provided'],
                                 'Anchor provider is not the single admitted consumer')
            self.session.require(predecessor_anchor_sha256 == params['predecessor_anchor_sha256'],
                                 'Provider input differs from the admitted request')
            self.session.require(self.adapter.current_name == name and self.adapter.guard is not None,
                                 'Anchor loading requires the active no-eviction scope')
            pred = cur['row']['predecessor']
            self.session.require(type(pred) is dict and pred['last_chunk'] == params['chunk_index'] - 1,
                                 'Predecessor is not the last completed chunk of this chain')
            live = self.authority.chains[active['chain']]
            self.session.require(live['anchor_sha256'] == pred['anchor_sha256'] and
                                 live['anchor_path'] == pred['anchor_path'], 'Scene anchor changed during request')
            if params['kind'] == 'stream':
                self.session.require(predecessor_anchor_sha256 == pred['anchor_sha256'], 'Stale predecessor anchor')
            import stream_receipts
            raw = stream_receipts.read_anchor(pred['anchor_path'], pred['anchor_sha256'])
            self.bindings.check_native()
            image = torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(*contract.ANCHOR_SHAPE).clone()
            self.active_row(name)
            self.conditioning.begin_request(name, anchor=image, expected_anchor_sha256=pred['anchor_sha256'])
            cur.update(provided=True, anchor_image=image,
                       anchor_in={'sha256': pred['anchor_sha256'], 'path': pred['anchor_path'],
                                  'source_run_name': pred['run_name']})
            return image

    def condition(self, vae, image, latent, strength, bypass, run_name, stage):
        with self.authority.lock:
            self.active_row(run_name)
            cur = self.current
            self.session.require(cur is not None and cur['name'] == run_name and cur['provided'] and
                                 image is cur['anchor_image'] and image is self.conditioning.anchor and
                                 type(strength) in (float, int) and strength == 1.0 and bypass is False and
                                 stage in ('A', 'B'), 'Conditioning node differs from its fixed inputs')
            self.session.require(self.adapter.current_name == run_name and self.adapter.guard is not None,
                                 'Conditioning requires the active no-eviction scope')
            return self.conditioning.run_stage(stage, request_id=run_name, vae=vae, latent=latent,
                                               native_call=self.bindings.native_call)

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

    def output(self, run_name, images, audio, video_latent, audio_latent, fields):
        import torch
        import folder_paths
        import stream_receipts
        with self.authority.lock:
            active = self.active_row(run_name)
            cur, params = self.current, active['params']
            self.session.require(cur is not None and cur['output'] is None and cur['name'] == run_name,
                                 'Output node is not the single admitted consumer')
            self.session.require(fields == {k: params[k] for k in fields} and set(fields) == set(params) - {'prompt'},
                                 'Output node inputs differ from request')
            cur['timing']['decode_done'] = self.events.get(cur['prompt_id'], {}).get('stream_output', time.time_ns())
            tensors = {'images': images, 'video_latent': video_latent['samples'],
                       'audio_latent': audio_latent['samples'], 'waveform': audio['waveform']}
            self.session.require(audio.get('sample_rate') == contract.SAMPLE_RATE, 'Audio sample rate differs')
            summary = {}
            for name, tensor in tensors.items():
                t = tensor.detach().to('cpu').contiguous()
                self.session.require(t.dtype is torch.float32 and list(t.shape) == self.geometry['tensor_shapes'][name],
                                     'Output tensor geometry differs: ' + name)
                finite = bool(torch.isfinite(t).all())
                self.session.require(finite, 'Nonfinite output tensor: ' + name)
                summary[name] = {'shape': list(t.shape), 'dtype': str(t.dtype), 'finite': True,
                                 'sha256': hashlib.sha256(t.view(torch.uint8).numpy()).hexdigest()}
            last = self.geometry['anchor_frame_index']
            raw = stream_preview.anchor_bytes(torch, images, last)
            anchor = stream_receipts.write_anchor(self.run / 'anchors', run_name, raw, self.frames)
            # Anchor ready: everything the next chunk consumes is hashed and durable.
            cur['timing']['anchor_ready'] = time.time_ns()
            diagnostic = stream_preview.anchor_diagnostic(torch, images, last)
            output_dir = Path(folder_paths.get_output_directory())
            path, relative = stream_preview.predict_preview_path(run_name + '/preview', str(output_dir),
                                                                 contract.WIDTH, contract.HEIGHT)
            self.session.require(path.is_absolute() and path.parent.parent == output_dir and
                                 path.parent.name == run_name and not path.exists() and path.name.endswith('.mp4'),
                                 'Preview path is not a fresh MP4 in this chunk\'s output folder')
            preview_images, preview_audio = stream_preview.private_copy(images, audio)
            anchored = contract.anchored(params)
            job = {'run_name': run_name, 'prompt_id': cur['prompt_id'], 'images': preview_images,
                   'audio': preview_audio, 'path': path, 'relative': relative, 'includes_overlap_frame': anchored,
                   'timing': {'submit': cur['timing']['submit'], 'anchor_ready': cur['timing']['anchor_ready']}}
            cur['output'] = {'tensors': summary, 'anchor_out': anchor, 'anchor_diagnostics': diagnostic,
                             'preview': {'path': str(path), 'relative_to_output_directory': relative,
                                         'state': 'queued', 'bytes': None,
                                         'record': str(self.run / 'receipts' / ('preview-' + run_name + '.json')),
                                         'container': 'mp4', 'lossy': True, 'fps': contract.FPS,
                                         'frames': self.frames, 'includes_overlap_frame': anchored}}
        # Outside the authority lock: back-pressure must not block the status route.
        queued, depth, blocked = self.preview.submit(job)
        with self.authority.lock:
            self.active_row(run_name)
            cur['timing']['preview_queued'] = queued
            cur['output']['preview'].update(queue_depth_at_submit=depth, submit_blocked_s=blocked)
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
                             cur['text'] is not None, 'Chunk request skipped its output or text node')
        conditioning_memory = []
        guard_receipts = []
        anchored = contract.anchored(params)
        if anchored:
            self.session.require(cur['provided'], 'Conditioned request skipped its provider')
            self.conditioning.finish_request(name)
            guard_receipts, conditioning_memory = self._conditioning_policy(name)
        else:
            self.session.require(not cur['provided'] and self.conditioning.active is None,
                                 'An unanchored chunk cannot consume an anchor')
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
            used = self.capture_guard.receipt()['captures']
            self.session.require(used and used[-1]['name'] == name and used[-1]['prompt_id'] == prompt_id,
                                 'Qualification capture missing')
            capture = {'path': str(self.root / 'output/validation' / name / 'tensors.safetensors'),
                       'prewrite': used[-1]}
        pred = row['predecessor']
        chain_ok = (cur['anchor_in'] is None) if not anchored else (
            cur['anchor_in']['sha256'] == pred['anchor_sha256'] and
            (params['kind'] != 'stream' or params['predecessor_anchor_sha256'] == pred['anchor_sha256']))
        self.session.require(chain_ok, 'Anchor chain check failed')
        events = self.events.pop(cur['prompt_id'], {})
        timing = cur['timing']
        timing.update(sampler_a_start=events.get('344'), sampler_b_start=events.get('368'),
                      decode_start=events.get('374'))
        timing['receipt_staged'] = time.time_ns()
        prior = None
        if pred is not None:
            record = self.preview.record(pred['run_name'])
            if record is not None:
                prior = {'run_name': record['run_name'], 'preview_written_ns': record['timing_ns']['preview_written'],
                         'bytes': record['bytes'], 'sha256': record['sha256'], 'timing_s': record['timing_s']}
        compact = lambda r: {'free': r['snapshot']['physical_free_bytes'],
                             'peaks': r['snapshot']['peaks'], 'required': r['required_physical_free_bytes']}
        receipt = {
            'schema': stream_receipts.SCHEMA, 'run_name': name, 'prompt_id': prompt_id, 'kind': params['kind'],
            'scene_id': params['scene_id'], 'chunk_index': params['chunk_index'], 'seed': params['seed'],
            'stream_seq': params['stream_seq'], 'prompt_sha256': contract.text_sha256(params['prompt']),
            'frames': self.frames, 'placement': self.placement, 'reuse_text': params['reuse_text'],
            'server_text_reuse': self.text_reuse,
            'anchored': anchored, 'reset': bool(params['reset']),
            'reset_predecessor_anchor_sha256': params['predecessor_anchor_sha256'] if params['reset'] else None,
            'prompt_changed': (None if not params['chunk_index'] else
                               contract.text_sha256(params['prompt']) != pred['text_sha256']),
            'plan_sha256': self.session.PLAN_SHA256,
            'qualification_id': self.authority.qid, 'runtime_manifest_sha256': self.manifest_sha,
            'server_identity_sha256': self.identity_sha,
            'qualification_verdict_sha256': self.authority.verdict_sha,
            'tensors': cur['output']['tensors'], 'anchor_in': cur['anchor_in'],
            'anchor_out': cur['output']['anchor_out'],
            'delivery': stream_receipts.delivery(params['chunk_index'], self.frames, anchored),
            'preview': cur['output']['preview'], 'predecessor_preview': prior,
            'anchor_diagnostics': cur['output']['anchor_diagnostics'], 'capture': capture, 'timing_ns': timing,
            'timing_s': {'submit_to_sampler_start': stream_receipts.seconds(timing, 'submit', 'sampler_a_start'),
                         'submit_to_decode_done': stream_receipts.seconds(timing, 'submit', 'decode_done'),
                         'submit_to_anchor_ready': stream_receipts.seconds(timing, 'submit', 'anchor_ready'),
                         'anchor_ready_to_receipt_staged':
                             stream_receipts.seconds(timing, 'anchor_ready', 'receipt_staged'),
                         # Written later by the preview writer: see receipts/preview-<run_name>.json.
                         'submit_to_preview_written': None,
                         'execution_start_to_preview_written': None},
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
                'preview_writer': self.preview.summary(),
                'current': {k: v for k, v in (self.current or {}).items() if k != 'anchor_image'}})

    def prepare(self, name):
        import torch
        import nodes
        import comfy.model_management as mm
        import continuation_anchor
        import conditioning_guard
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
        snapshot = self.adapter.prepare()
        self.write('stream-preparation.json', {'snapshot': snapshot, 'receipts': self.adapter.drain_receipts()})
        self.bindings = NativeBindings(packet=self.packet, manifest=self.manifest, torch=torch, nodes=nodes,
            model_management=mm, adapter=self.adapter, anchor_module=continuation_anchor,
            guard_module=conditioning_guard, output_type=io.NodeOutput)
        self.conditioning = conditioning_guard.ConditioningStageGuard(controller=self.adapter.controller,
            tensor_metadata=self.bindings.tensor_metadata, inspect_anchor=self.bindings.inspect_anchor,
            inspect_encoder_cache=self.bindings.inspect_encoder_cache, unwrap_output=self.bindings.unwrap_output)
        self.adapter.controller.drain()
        self.write('stream-native-binding.json', self.bindings.receipt())
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
        prompt_id, node = data.get('prompt_id'), data.get('node')
        if type(prompt_id) is str and type(node) is str and node in ('344', '368', '374', 'stream_output'):
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
            self.session.require(self.preview.drain(PREVIEW_DRAIN_BOUND_S),
                                 'Qualification previews were not all written: %r' % self.preview.summary())
            for row in self.authority.qualification_rows:
                self.session.require(self.preview.record(row['name']) is not None,
                                     'Qualification preview record missing: ' + row['name'])
            state = self.quiescent()
            self.session.require(self.authority.phase == 'stream_qualification' and
                                 len(self.authority.completed) == 11, 'Nine qualification requests required')
            receipts, captures = [], {}
            for row in self.authority.qualification_rows:
                binding = self.authority.receipts[row['name']]
                raw = self.session.read_regular(Path(binding['path']))
                self.session.require(self.session.digest(raw) == binding['sha256'], 'Receipt changed: ' + row['name'])
                receipt = self.session.strict_json(raw)
                receipts.append(receipt)
                captures[row['name']] = qualification_gate.capture_tensor_hashes(receipt['capture']['path'], self.frames)
            observed = self.adapter.native_state()
            verdict = qualification_gate.decide(receipts, captures, self.session.PLAN_SHA256, self.frames,
                                                self.text_reuse, self.placement)
            verdict.update(receipts={r['run_name']: self.authority.receipts[r['run_name']] for r in receipts},
                           preview_writer=self.preview.summary(),
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


class LTXStreamPrepare112:
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


class LTXStreamAnchor112:
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


class LTXStreamCondition112:
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


class LTXStreamText112:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING',), 'text': ('STRING', {'multiline': True})},
                'optional': {'conditioning': ('CONDITIONING',)}}
    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, run_name, text, conditioning=None):
        return (_ctx().text(run_name, text, conditioning),)


class LTXStreamChunk112:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'images': ('IMAGE',), 'audio': ('AUDIO',), 'video_latent': ('LATENT',),
            'audio_latent': ('LATENT',), 'run_name': ('STRING',), 'kind': (list(contract.KINDS),),
            'frames': ('INT', {'min': 25, 'max': 49}), 'placement': (sorted(contract.PLACEMENTS),),
            'scene_id': ('STRING',), 'chunk_index': ('INT', {'min': 0, 'max': contract.MAX_STREAM_SEQ}),
            'seed': ('INT', {'min': 0, 'max': contract.SEED_MAX}),
            'stream_seq': ('INT', {'min': -1, 'max': contract.MAX_STREAM_SEQ}),
            'predecessor_anchor_sha256': ('STRING',), 'reuse_text': ('INT', {'min': 0, 'max': 1})},
                'optional': {'reset': ('INT', {'min': 0, 'max': 1})}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, images, audio, video_latent, audio_latent, run_name, kind, frames, placement, scene_id,
              chunk_index, seed, stream_seq, predecessor_anchor_sha256, reuse_text, reset=0):
        fields = {'kind': kind, 'frames': frames, 'placement': placement, 'scene_id': scene_id,
                  'chunk_index': chunk_index, 'seed': seed,
                  'stream_seq': stream_seq, 'predecessor_anchor_sha256': predecessor_anchor_sha256,
                  'reuse_text': reuse_text, 'reset': reset}
        return _ctx().output(run_name, images, audio, video_latent, audio_latent, fields)


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in (LTXStreamPrepare112, LTXStreamAnchor112,
    LTXStreamCondition112, LTXStreamText112, LTXStreamChunk112)}


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
                      fault=ctx.fault(), receipt_dir=str(ctx.run / 'receipts'),
                      qualified_text_windows=None if ctx.qualified_windows is None else sorted(ctx.qualified_windows),
                      output_directory=str(ctx.root / 'output'), packet=113,
                      features={'async_preview': True, 'chain_reset': True, 'anchor_diagnostics': True},
                      preview_writer=ctx.preview.summary())
        try:
            result['storage'] = ctx.storage_check(mutate=False)
        except RuntimeError as error:
            result['storage'] = {'refused': str(error)}
        return web.json_response(result)

    @server.routes.get('/ltx-stream/receipt/{run_name}')
    async def receipt(request):
        name = request.match_info['run_name']
        if not RUN_NAME_RE.fullmatch(name):
            return refuse('contract', 'Invalid run name', 400)
        path = ctx.run / 'receipts' / ('receipt-' + name + '.json')
        if not path.is_file():
            return refuse('not-found', 'No committed receipt for ' + name, 404)
        return web.Response(body=ctx.session.read_regular(path), content_type='application/json')

    @server.routes.get('/ltx-stream/preview/{run_name}')
    async def preview(request):
        name = request.match_info['run_name']
        if not RUN_NAME_RE.fullmatch(name):
            return refuse('contract', 'Invalid run name', 400)
        path = ctx.run / 'receipts' / ('preview-' + name + '.json')
        if not path.is_file():
            if ctx.preview.failed is not None:
                return refuse('halted', 'Preview writer failed: ' + ctx.preview.failed[:500], 503)
            return refuse('not-found', 'No committed preview record for ' + name, 404)
        return web.Response(body=ctx.session.read_regular(path), content_type='application/json')

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

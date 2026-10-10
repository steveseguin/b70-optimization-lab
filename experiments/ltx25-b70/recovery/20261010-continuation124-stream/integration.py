"""Packet123 streaming runtime: packet118b plus CPU-prepared, byte-gated scheduling options.

Inert until the sealed launcher calls install().

Packet123 options (all off by default; XPU identity and performance still require qualification):
- display sampler-a: packet118b path; sampler-b: wait for the actual successor's sampler-B event under
  the shared 3 s go deadline; eager-display: retain the graph cone but use uncached eager full display.
- anchor read-ahead: after receipt commit, prepare one immutable verified CPU frame; consume with
  fresh file identity and SHA checks, or native read on miss. Successor text is not guessed/prepared.
- snapshot full: packet118b barriers; a-xpu3-sync: owner-level safety option implemented by the inspector.

Packet118b inherited behavior (off forms retain packet 117's model operations).
Timing adds CPU locks, allocations, timestamps and receipt I/O; its cost is not measured here.

A. Timing split (always on, measurement only): the admission middleware, an outer timing wrapper of the
   executor, the before_request hook, the stage nodes and the 'executing' events record marks; the receipt
   splits submit -> sampler A into named sub-buckets (stream_receipts.SUBMIT_SPLIT), lists every snapshot with
   its duration and parts, counts the authority's healthy() calls, and splits the predecessor's receipt -> this
   submit (commit, receipt HTTP response construction, client turnaround; stream_receipts.TURNAROUND_SPLIT).
B. LTX_SNAPSHOT_MODE=walk|fingerprint (snapshot_fingerprint.py): the controller's inspect callable is the
   SnapshotInspector. walk = packet 117's CandidateAdapter._inspect (timed). fingerprint = the same checks
   with the residence/ownership and the sampler placement from fact tuples bound at the placement event to the
   admitted fingerprints (the walk itself whenever a fact differs); setup and qualification run both modes on
   every snapshot, streaming every 20th chunk and from any near-floor reading on; a disagreement latches and
   writes snapshot-118-refused.json. The decode thread's xpu:3 snapshot (P7) uses the same ledger and policy.
C. LTX_DECODER_GRAPH_POOL_CAP_GB (stream_decoder_graph.DecoderGraph pool_cap_bytes): unset = packet 117; set =
   decoder methods are captured, in first-call order, only while the measured pool growth of the captures
   already made is below the cap; a capped method runs eagerly with the same bounded caches for the life of the
   server (byte-gated like the graph decode it replaces).
Latches: anchor-decode-118-refused.json, precompute-118-refused.json, snapshot-118-refused.json (the launcher also
honours the packet-117 cone/precompute latches); decoder-graph-116-refused.json stays shared.

Packet117 (frame anchor; every lever exact by construction and gated in qualification):

1. LTX_ANCHOR_DECODE=cone (stream_anchor_decode.py): the decode the chain waits for is a native
   VAEDecode whose stage-5 step is the cone-restricted step (only the calls the last pixel frame depends
   on); its last frame is the anchor. The full decode for display runs later on the decode thread, after
   the successor's sampler A has started (bounded wait), and its last frame must equal the anchor byte for
   byte; a mismatch latches and writes the anchor-decode latch.
2. LTX_BENCODE_OVERLAP=1 (precompute_guard.py): the stage-B anchor encode runs on the decode thread when
   the successor's sampler A starts, between xpu:3-only safety snapshots; the stage-B node runs the native
   LTXVImgToVideoInplace with the precomputed encode inside the unchanged four-card conditioning guard.
3. LTX_STREAM_FRAMES=121 (5.04 s chunks; geometry measured on the first eager chunk as before).
4. LTX_PREP_AHEAD=1: the stage-A anchor encode runs on the decode thread right after the predecessor's
   receipt commits, under the same guard; the stage-A node consumes it the same way.
Decode-thread order per frame chunk: anchor decode (cone or full) -> anchor file -> hand-off -> [prep: wait
for the receipt commit, stage-A encode] -> [cone or overlap: wait for the successor's sampler A, stage-B
encode] -> [cone: display decode + byte check] -> audio, hashes, diagnostics, capture, record, preview.
Gated qualification chunks run the same steps without the waits (the chain waits for the whole job). The
eager chain runs every lever off (the reference); the graph chain runs the levers AND their native
counterparts on the same inputs (precomputed vs native conditioning, byte-identical); the repeat chain
runs the levers in the stream form. Prompt-thread conditioning-guard calls and the decode thread's encodes
are serialised by one encoder lock (the encoder's per-thread cache checks stay exact).

Packet116:

1. Default anchor `frame` (packet113 semantics at both stages). The other three modes stay.
2. 116a scheduling (no arithmetic change). The output node hands the decode to the decode thread
   and, in frame mode, waits only for the job stage `anchor`: the decode thread runs the VIDEO
   decode, checks the images' shape, writes the decoded last frame as the anchor file (exclusive,
   fsynced, finiteness-checked) and publishes it. The chain then commits the receipt and the next
   chunk starts. Behind it, on the same thread and in this order: the audio decode, the tensor
   hashes and finiteness checks, the border and sharpness diagnostics, the qualification capture,
   the fsynced decode record, and the preview hand-off. Timestamps: video_done, anchor_ready,
   audio_done, hashed, record_staged (decode record), record_written and preview_written
   (preview record). Gated qualification chunks wait for their whole decode in every mode.
3. Decoder graph (LTX_DECODER_GRAPH=1, stream_decoder_graph.py): graph replay of the NA diffusion
   decoder with bounded device-resident caches. The eager chain decodes with the uncached eager
   decoder (the reference); each graph-chain chunk is decoded twice on the same latents (uncached
   eager, then graph) and must be byte-identical; the repeat chain and the stream replay only. A
   mismatch or a refused capture latches the server and writes the decoder-graph latch in the
   results root, which makes the launcher refuse LTX_DECODER_GRAPH=1 until it is archived.
4. LTX_BENCODE_OVERLAP (stage-B encode beside stage A) is NOT implemented: the conditioning
   guard's snapshots synchronise all four cards through the sealed NativeReferenceSafety and are
   bound to the prompt thread; the launcher refuses LTX_BENCODE_OVERLAP=1.

Packet114 (kept): the decode leaves the graph. One ordered decode thread
(stream_decode.OrderedWorker) runs the native VAEDecode / LTXVAudioVAEDecode calls on xpu:3,
writes the qualification capture, commits receipts/decode-<run_name>.json and hands the MP4 to
the packet113 preview writer behind it. Chunk length 49 or 97 at launch; text reuse ON by
default; node-start events split the sampler-A bucket.

Packet115 anchor modes (LTX_ANCHOR, kept):

1. `mixed`. Stage A conditions on the last latent slot of the predecessor's stage-A
   output (node 367) through LTXStreamLatentCondition116 (the native slot-0 copy without the
   encode, as packet114). Stage B conditions on the predecessor's DECODED last frame through the
   native LTXVImgToVideoInplace with its VAE encode (as packet113), after the upsampler. The
   output node writes the 40,960-byte latent file and commits the receipt at anchor ready, as
   packet114; the decode thread writes the decoded last frame as a frame-anchor file and names
   it in its decode record. The next chunk's text encode and stage A therefore run while the
   decode runs; its stage-B condition node (LTXStreamFrameConditionB116, prompt thread) waits,
   bounded and outside the authority lock, for the predecessor's decode record, verifies the
   frame file against it, and only then runs the native encode (conditioning_guard,
   first_stage='B'). The VAE encode and the VAE decode therefore never run at the same time.
2. `guide`. The native LTXVAddLatentGuide appends the predecessor's last two latent slots
   (stage A from node 367, stage B from node 369; one 81,920-byte file) as guide tokens at
   latent index -2 for both stages, and LTXVCropGuides removes them after each sampler
   (LTXStreamGuide116 / LTXStreamCropGuides116 through latent_anchor.GuideGuard).
3. `latent` (packet114) and `frame` (packet113's decoded-frame anchor).

The decode thread also commits a sharpness profile (Laplacian variance of decoded frames 0, 1,
2, 5, 10, 24, the middle and the last) in every decode record.

Setup (window probe, full-residency preparation) -> nine qualification chunks ->
explicit verdict action -> unbounded serial stream chunks. Any failure inside an
admitted request, the decode thread or the preview writer latches the authority and
refuses later requests. No retry, allocator reset, settings change, process action or
device import at module import.
"""
import asyncio
import copy
from contextlib import nullcontext
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
import display_replica
import residency123
import stream_decoder_graph
import stream_anchor_decode
import precompute_guard
import stream_schedule
import snapshot_fingerprint

_CTX = None
_ROUTES_INSTALLED = False
GIB = 2 ** 30
RESERVE_BYTES = 50 * GIB
import run_storage
XPU3_DECODE_FLOOR = 9 * GIB       # the packet's xpu:3 pre-request floor, applied before every decode
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
RUN_NAME_RE = contract.RUN_NAME_RE
PREVIEW_DRAIN_BOUND_S = 120.0     # the verdict waits at most this long for queued previews
DECODE_DRAIN_BOUND_S = 300.0      # ... and for queued decodes (also before every gated request)
CHUNK_KINDS = contract.KINDS
NON_TENSOR_CURRENT = ('anchor_image', 'latent_parts', 'guide_parts', 'decode_job')
FRAME_WAIT_BOUND_S = 300.0        # mixed: stage B waits at most this long for the predecessor's decode
ANCHOR_WAIT_BOUND_S = 300.0       # frame: the chain waits at most this long for its own video decode + anchor
REFERENCE_PATH = 'resolution/reference-frame-hashes.json'   # packet116 cross-packet reference (sealed)
GO_BOUND_S = 3.0                  # packet117: the deferred work waits at most this long for the successor's sampler A
COMMIT_BOUND_S = 10.0             # ... and prep-ahead at most this long for the predecessor's receipt commit
PRECOMPUTE_WAIT_BOUND_S = 60.0    # a stage node waits at most this long for a reserved precomputed encode


def _bound(*tables, keep=64):
    """Packet123: keep the newest `keep` entries of the measurement tables (insertion order)."""
    for table in tables:
        while len(table) > keep:
            table.pop(next(iter(table)))


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
        self.decoder_graph_flag = contract.launch_decoder_graph()
        self.decoder_graph = None   # stream_decoder_graph.DecoderGraph once prepared (LTX_DECODER_GRAPH=1)
        # Packet123 server-side levers (not request fields, not in the qualification id).
        self.snapshot_mode = contract.launch_snapshot_mode()
        self.pool_cap = contract.launch_pool_cap()
        self.run_write_allowance = run_storage.launch_allowance_bytes()
        self.storage_account = run_storage.OwnWrites(self.root, self.run, contract.RUN_PREFIX)
        self.server_options = {'run_write_allowance_bytes': self.run_write_allowance, 'snapshot_mode': self.snapshot_mode, 'decoder_graph_pool_cap_bytes': self.pool_cap}
        self.display_schedule, self.anchor_read_ahead, self.snapshot_schedule = stream_schedule.launch_options()
        session.require(self.anchor == 'frame' or (self.display_schedule == 'sampler-a' and not self.anchor_read_ahead),
                        'Packet123 scheduling levers require frame anchors')
        self.server_options.update(display_schedule=self.display_schedule, anchor_read_ahead=self.anchor_read_ahead,
                                   snapshot_schedule=self.snapshot_schedule)
        self.successor_barrier = stream_schedule.SuccessorBarrier()
        self.anchor_reads = stream_schedule.AnchorReadAhead()
        self.inspector = None       # snapshot_fingerprint.SnapshotInspector once prepared
        self.ledger = None          # snapshot_fingerprint.ResidenceLedger (fingerprint mode)
        # Packet123 timing split (measurement only): per prompt id / run name, bounded.
        self.admission_marks = {}   # prompt_id -> {admission_received, precheck_done, queued}
        self.exec_marks = {}        # prompt_id -> {entry, exit} of the executor (outer timing wrapper)
        self.node_events = {}       # prompt_id -> {node: first executing ns}
        self.receipt_served = {}    # run_name -> first constructed receipt HTTP 200 (ns), not delivery
        self.receipt_polls = {}     # run_name -> HTTP 404s of its receipt before that
        self.staged_ns = {}         # run_name -> its receipt_staged mark
        self.route_lock = threading.Lock()
        self.route_stats = {'status_calls': 0, 'status_seconds': 0.0}   # the status route (event-loop thread)
        # Packet117 levers (frame anchor only; full/0/0 otherwise).
        self.levers = contract.launch_levers()
        self.anchor_decode, self.bencode_overlap, self.prep_ahead = self.levers
        session.require(self.display_schedule == 'sampler-a' or self.anchor_decode == 'cone',
                        'Alternate display schedules require the cone anchor path')
        self.display_device = display_replica.launch_device()
        display_replica.validate_scope(self.display_device, self.frames, self.anchor, self.anchor_decode,
                                       self.display_schedule)
        self.server_options['display_device'] = self.display_device
        if 'LTX_DISPLAY_REPLICA_TRANSIENT_GIB' in os.environ:
            self.server_options['display_replica_transient_budget_bytes'] = contract.launch_display_transient_bytes(self.frames)
        self.aux_residency = contract.launch_aux_residency()
        contract.check_residency_scope(self.frames, self.placement, self.anchor, self.decoder_graph_flag,
            self.anchor_decode, self.aux_residency, self.display_device)
        self.server_options.update(aux_residency=self.aux_residency, residency_qualification_id=
            contract.residency_qualification_id(contract.qualification_id(self.frames, self.placement,
                self.anchor, self.decoder_graph_flag, *self.levers), self.aux_residency))
        self.display_worker = os.environ.get('LTX_DISPLAY_WORKER', 'serial')
        session.require(self.display_worker in ('serial', 'parallel'),
                        'LTX_DISPLAY_WORKER must be serial or parallel')
        session.require(self.display_worker == 'serial' or
                        (self.frames in (145, 169) and self.anchor == 'frame' and
                         self.anchor_decode == 'cone' and self.decoder_graph_flag == 0 and
                         self.display_device == 'xpu:2' and self.display_schedule == 'eager-display' and
                         self.aux_residency == 'legacy'),
                        'Parallel display requires 145/169 frame/cone/dg0/xpu2/eager-display/legacy')
        self.server_options['display_worker'] = self.display_worker
        self.display_replica = None
        self.cone = None            # stream_anchor_decode.ConeAnchorDecode once prepared (LTX_ANCHOR_DECODE=cone)
        self.precompute = precompute_guard.PrecomputeStore()
        self.xpu3_snapshot = None   # precompute_guard.Xpu3Snapshot once prepared
        self.encoder_lock = threading.RLock()   # prompt-thread guard calls vs the decode thread's encodes
        self.go = threading.Condition()          # notified at every sampler-A start (node 344 'executing')
        self.sampler_a_starts = 0
        self.geometry = contract.geometry(self.frames)
        (self.run / 'receipts').mkdir()
        (self.run / 'anchors').mkdir()
        self.lock = threading.RLock()
        self.action_busy = False
        self.actions_done = set()
        self.action_worker = self.action_cleanup = None
        self.action_halt_receipt_error = None
        self.adapter = self.bindings = self.conditioning = self.latent_guard = self.guide_guard = None
        self.guide_native = None    # guide mode: the pinned native LTXVAddLatentGuide / LTXVCropGuides
        self.frame_anchor_files = []   # mixed: (stream_seq, path) of the decode thread's stream frame anchors
        self.frame_anchor_lock = threading.Lock()
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
                                           self.frames, self.placement, self.anchor, self.decoder_graph_flag,
                                           self.levers, server_options=self.server_options)
        session.require(session.digest(Path(capture.__file__).read_bytes()) ==
                        manifest['files']['source/scripts/ltx_duration_guard.py'],
                        'Capture guard differs from sealed source')
        self.capture_rows = [{'name': row['name'], 'role': 'full',
                              'graph_sha256': row['graph_sha256'][self.authority.variant + '/%d' % self.text_reuse]}
                             for row in self.authority.qualification_rows]
        self.capture_guard = capture.configure(session.PLAN_SHA256, self.capture_rows, self.active_capture_request)
        self.preview = stream_preview.StreamPreviewWriter(self._save_preview, self._commit_preview,
                                                          self._preview_failed)
        worker = stream_decode.SplitWorker if self.display_worker == 'parallel' else stream_decode.OrderedWorker
        self.decoder = worker(self._decode_job, self._decode_failed, name='ltx120-decode')
        self.registry = stream_decode.RegistryLock()
        self.write('stream-launch-options.json', {'server_options': dict(self.server_options),
            'storage_accounting': run_storage.ACCOUNTING, 'reserve_bytes': RESERVE_BYTES})
        self.storage_check()

    # -- observation ----------------------------------------------------------
    def fault(self):
        return ((self.root / 'FAULT.json').exists() or (self.run / 'stream-halt.json').exists() or
                self.preview.failed is not None or self.decoder.failed is not None)

    def _halt_async(self, error, label):
        # Latch without holding the worker: the executor thread may own the authority lock.
        threading.Thread(target=self.authority.halt, name='ltx120-%s-halt' % label, daemon=True,
                         args=(error,)).start()

    # -- preview writer (packet113, behind the decode thread) -------------------
    def _save_preview(self, job):
        return stream_preview.save_preview_atomic(job['images'], job['audio'], job['path'])

    def _commit_preview(self, job, record):
        import stream_receipts
        record = dict(record, server_options=dict(self.server_options), schema=stream_receipts.PREVIEW_SCHEMA, frames=self.frames, fps=contract.FPS,
                      lossy=True, includes_overlap_frame=job['includes_overlap_frame'])
        stream_receipts.validate_preview_record(record)
        stream_preview.write_record_atomic(
            self.session, self.run / 'receipts' / ('preview-' + job['run_name'] + '.json'), record)
        return record

    def _preview_failed(self, job, error):
        name = job['run_name'] if isinstance(job, dict) else 'unknown'
        try:
            self.write('stream-preview-failure-' + name + '.json', {
                'run_name': name, 'error': repr(error)[:4000], 'writer': self.preview.summary(),
                'time_ns': time.time_ns()})
        finally:
            self._halt_async(RuntimeError('Preview write failed for %s: %r' % (name, error)), 'preview')

    # -- decode thread (packet116) ------------------------------------------------
    def _decode_failed(self, job, error):
        if getattr(self, 'display_device', 'xpu:3') == 'xpu:2':
            self._lever_refused(display_replica.LATCH_NAME, job.get('run_name'), repr(error))
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

    def _decoder_graph_refused(self, name, reason):
        """Packet116 latch: the first decoder-graph mismatch or refusal writes ROOT/<LATCH_NAME> (exclusive;
        an existing latch is kept). The launcher refuses LTX_DECODER_GRAPH=1 while it exists."""
        latch = self.root / stream_decoder_graph.LATCH_NAME
        try:
            self.session.write_exclusive(latch, {
                'schema': 'ltx.stream116.decoder-graph-latch.v1', 'run_dir': str(self.run), 'run_name': name,
                'reason': str(reason)[:4000], 'decoder_graph': (None if self.decoder_graph is None else
                                                                self.decoder_graph.receipt()),
                'time_ns': time.time_ns(),
                'rule': 'the launcher refuses LTX_DECODER_GRAPH=1 until an owner archives this file; relaunch '
                        'with LTX_DECODER_GRAPH=0 (no automatic fallback)'})
        except FileExistsError:
            pass

    def note_status_route(self, seconds):
        """Packet123 (measurement only): the status route's calls and seconds on the event-loop thread."""
        with self.route_lock:
            self.route_stats['status_calls'] += 1
            self.route_stats['status_seconds'] += seconds

    def route_snapshot(self):
        with self.route_lock:
            return dict(self.route_stats)

    def _snapshot_refused(self, reason):
        """Packet123: the snapshot fingerprint disagreed with the walk; the launcher then refuses fingerprint."""
        active = self.authority.active
        self._lever_refused(snapshot_fingerprint.LATCH_NAME, None if active is None else active['name'], reason,
                            {'ledger': None if self.ledger is None else self.ledger.receipt()})

    def _lever_refused(self, latch_name, name, reason, detail=None):
        """Packet117/118 latch: the first cone, precompute or snapshot-fingerprint failure writes ROOT/<latch_name>
        (exclusive; an existing latch is kept). The launcher refuses the lever while it exists."""
        try:
            self.session.write_exclusive(self.root / latch_name, {
                'schema': 'ltx.stream118.lever-latch.v1', 'latch': latch_name, 'run_dir': str(self.run),
                'run_name': name, 'reason': str(reason)[:4000], 'detail': detail, 'levers': list(self.levers),
                'server_options': dict(self.server_options),
                'time_ns': time.time_ns(),
                'rule': 'the launcher refuses this lever until an owner archives this file; relaunch with it off '
                        '(no automatic fallback)'})
        except FileExistsError:
            pass

    def _video_decode(self, vae, latent, graph):
        """The native VAEDecode on the decode thread: uncached eager, or inside the decoder graph scope."""
        import nodes
        if not graph:
            if self.decoder_graph is not None:
                self.decoder_graph.note_eager()
            return nodes.VAEDecode().decode(vae, {'samples': latent})[0]
        with self.decoder_graph.graph_decode():
            return nodes.VAEDecode().decode(vae, {'samples': latent})[0]

    def _cone_decode(self, vae, latent, graph):
        """Packet117: the native VAEDecode with the cone-restricted stage-5 step (eager or graph scope)."""
        import nodes
        if not graph:
            if self.decoder_graph is not None:
                self.decoder_graph.note_eager()
            with self.cone.cone_decode():
                return nodes.VAEDecode().decode(vae, {'samples': latent})[0]
        with self.decoder_graph.graph_decode(), self.cone.cone_decode():
            return nodes.VAEDecode().decode(vae, {'samples': latent})[0]

    def _reference_decode(self, vae, latent):
        """Packet116 graph chain: the uncached eager decode of the same latents must equal the graph decode."""
        ref_start = time.time_ns()
        with self.encoder_lock if self.display_worker == 'parallel' else nullcontext():
            self.session.require(self.decoder.failed is None, 'Reference refused after companion worker failure')
            ref_images = self._video_decode(vae, latent, False)
        reference = {'mode': 'eager-uncached', 'seconds': round((time.time_ns() - ref_start) / 1e9, 6)}
        return ref_images, reference

    def _wait_go(self, base, bound_s):
        """Packet117 (decode thread): wait until a newer sampler A has started (the successor is past its
        stage-A conditioning and its samplers run on xpu:0/xpu:1), the bound, or a halt."""
        started = time.monotonic()
        deadline = started + bound_s
        with self.go:
            while self.sampler_a_starts <= base:
                left = deadline - time.monotonic()
                if left <= 0 or self.authority.failed is not None:
                    return 'bound', round(time.monotonic() - started, 6)
                self.go.wait(min(left, 0.05))
        return 'sampler-a-start', round(time.monotonic() - started, 6)

    def _successor_consumes(self, anchor_sha):
        """Is the request running now anchored on `anchor_sha` (the chunk the stage-B encode is for)?"""
        cur = self.current
        anchor_in = cur.get('anchor_in') if type(cur) is dict else None
        return type(anchor_in) is dict and anchor_in.get('kind') == 'frame' and anchor_in.get('sha256') == anchor_sha

    def _precompute(self, entry, frame_raw, anchor_sha, stage, run_name):
        """Packet117 (decode thread): the native stage conditioning node with a capturing VAE, between the
        xpu:3-only safety snapshots, under the encoder lock; keeps the encode for the stage's node."""
        import torch
        pg = precompute_guard
        require = self.session.require
        if not self.precompute.start(entry):
            return entry.summary()
        try:
            vae = self.adapter.objects['video_vae']
            encoder = vae.first_stage_model.encoder
            with self.encoder_lock:                                                        # E1
                require(self.decoder.failed is None, 'Precompute refused after companion worker failure')
                self.bindings.check_native()                                               # E4
                self.bindings.settings()
                anchor = torch.frombuffer(bytearray(frame_raw), dtype=torch.float32).reshape(*contract.ANCHOR_SHAPE).clone()
                meta = self.bindings.tensor_metadata(anchor)
                require(meta['shape'] == contract.ANCHOR_SHAPE, 'Precompute anchor geometry differs')
                checked = self.bindings.inspect_anchor(anchor)                             # E2
                require(checked == {'sha256': anchor_sha, 'finite': True}, 'Precompute anchor bytes differ')
                tid = threading.get_ident()

                def cache_clear(label):                                                   # E3
                    row = self.bindings.inspect_encoder_cache(encoder, tid)
                    require(row['entry_count'] == 0 and row['foreign_entry_count'] == 0,
                            'Encoder temporal cache not empty %s the precomputed stage-%s encode' % (label, stage))
                    return row
                cache_before = cache_clear('before')
                before = self.xpu3_snapshot.take('precompute-%s-before' % stage, pg.PRE_FLOOR)   # P1-P8
                capture = pg.CaptureVAE(torch, vae)
                shape = self.geometry['stage_shapes'][stage]
                latent = {'samples': torch.zeros(shape, dtype=torch.float32)}
                started = time.time_ns()
                with torch.inference_mode():
                    result = self.bindings.native_call(vae=capture, image=anchor, latent=latent, strength=1.0,
                                                       bypass=False)
                encoded = time.time_ns()
                out = self.bindings.unwrap_output(result)
                require(type(out) is dict and set(out) == {'samples', 'noise_mask'} and
                        list(out['samples'].shape) == shape, 'Precompute native node output differs')
                require(len(capture.calls) == 1, 'The native node did not encode exactly once')
                record, t = capture.calls[0]
                require(record['t_shape'] == [1, 128, 1, shape[3], shape[4]] and record['t_dtype'] == 'torch.float32'
                        and str(t.device) == 'cpu', 'Precomputed encode geometry differs')
                cache_after = cache_clear('after')
                after = self.xpu3_snapshot.take('precompute-%s-after' % stage, pg.POST_FLOOR)
                require(self.bindings.inspect_anchor(anchor) == checked, 'Anchor changed during the precompute')
            record.update(schema=pg.SCHEMA, stage=stage, anchor_sha256=anchor_sha, source_run_name=run_name,
                          thread=threading.current_thread().name, encode_s=round((encoded - started) / 1e9, 6),
                          before=before, after=after, cache_before=cache_before, cache_after=cache_after,
                          checks=sorted(pg.CHECKS))
            self.precompute.finish(entry, t.detach().clone(), record)
            return entry.summary()
        except BaseException as error:
            self.precompute.fail(entry, error)
            # A halt elsewhere is not a precompute failure; nor is a snapshot-fingerprint disagreement (packet123:
            # it wrote its own latch).
            if self.authority.failed is None and not isinstance(error, snapshot_fingerprint.SnapshotDisagreement):
                self._lever_refused(pg.LATCH_NAME, run_name, repr(error), {'stage': stage})
            raise

    def _decode_audio_early(self, job, audio_vae):
        """Parallel only: finish xpu:3 audio before submitting the xpu:2 display.

        The unchanged native decoder consumes this job's private immutable audio
        latent. The CPU waveform is retained until the display/evidence tail; no
        native audio workspace remains live beside the successor's cone.
        """
        import torch
        import nodes
        require = self.session.require
        require(self.display_worker == 'parallel' and self.aux_residency == 'legacy',
                'Early audio requires the admitted parallel legacy path')
        with self.encoder_lock:
            require(self.decoder.failed is None, 'Early audio refused after companion worker failure')
            before = residency123.guard_aux(torch, 'audio', True, self.aux_residency)
            started = time.time_ns()
            with torch.inference_mode():
                audio = nodes.NODE_CLASS_MAPPINGS['LTXVAudioVAEDecode'].execute(
                    samples={'samples': job['audio_latent']}, audio_vae=audio_vae).result[0]
            done = time.time_ns()
            after = residency123.guard_aux(torch, 'audio', False, self.aux_residency)
        return {'audio': audio, 'start_ns': started, 'done_ns': done, 'before': before, 'after': after}

    def _decode_job(self, job):
        """Runs on the decode thread. Never takes the authority lock (wait_committed only reads its state).

        Packet117 order (frame anchor): anchor decode (cone or full) -> anchor file + hand-off -> [prep-ahead:
        wait for the receipt commit, stage-A encode] -> [cone or overlap: wait for the successor's sampler A,
        stage-B encode] -> [cone: display decode, byte check] -> audio decode -> hashes, finiteness,
        diagnostics -> qualification capture -> decode record -> preview hand-off.

        Packet124 parallel repeat/live only: after B preparation, audio completes
        on the original worker, then display/hashes/record/preview transfer to a
        separate bounded FIFO. Eager/graph controls and serial keep the order above.
        The next cone and all xpu:3 audio/reference work share encoder_lock."""
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
        kind = job['kind']
        gated = kind in contract.GATED_KINDS
        graph = self.decoder_graph_flag == 1 and kind != 'qualify-eager'
        require(not graph or self.decoder_graph is not None, 'Decoder graph mode without an installed decoder graph')
        levers_live = self.anchor == 'frame' and kind != 'qualify-eager'
        cone = levers_live and self.anchor_decode == 'cone'
        require(not cone or self.cone is not None, 'Cone anchor decode without an installed cone')
        captured_before = 0 if self.decoder_graph is None else len(self.decoder_graph.captures)
        reference = None
        replica_check = None
        replica_live = self.display_device == "xpu:2"
        timing = {k: None for k in stream_receipts.DECODE_TIMING_KEYS}
        timing.update(submit=job['timing'].get('submit'), anchor_ready=job['timing'].get('anchor_ready'),
                      decode_queued=job['timing']['queued'], decode_start=job['timing']['start'])
        schedule = {'gated': gated, 'levers_live': levers_live, 'commit': None, 'commit_wait_s': None,
                    'go': None, 'go_wait_s': None, 'display_schedule': self.display_schedule,
                    'display_release': None, 'anchor_read_ahead': None}
        anchor_decode = {'mode': 'cone' if cone else 'full', 'flag': self.anchor_decode}
        # -- 1. the decode the chain waits for -------------------------------------------------------------
        try:
            with (self.encoder_lock if self.display_worker == 'parallel' else nullcontext()), torch.inference_mode():
                require(self.decoder.failed is None, 'Cone refused after companion worker failure')
                video_start = time.time_ns()
                if cone:
                    first = self._cone_decode(vae, job['video_latent'], graph)
                else:
                    ref_images = None
                    if graph and kind == 'qualify-graph':
                        # Same latents, uncached eager decode first: the byte-identity reference.
                        ref_images, reference = self._reference_decode(vae, job['video_latent'])
                        video_start = time.time_ns()
                    first = self._video_decode(vae, job['video_latent'], graph)
            timing['video_done'] = time.time_ns()
            if not cone and reference is not None:
                same = stream_decoder_graph.bitwise_equal(torch, first, ref_images)
                reference.update(equal=bool(same), images_sha256=hashlib.sha256(
                    ref_images.detach().to('cpu').contiguous().view(torch.uint8).numpy()).hexdigest())
                del ref_images
                require(same, 'Decoder graph: the graph decode differs from the uncached eager decode of the same '
                              'latents (%s)' % job['run_name'])
        except BaseException as error:
            if graph:
                self._decoder_graph_refused(job['run_name'], repr(error))
            if cone:
                self._lever_refused(stream_anchor_decode.LATCH_NAME, job['run_name'], repr(error))
            raise
        want = self.geometry['decoded_shapes']['images']
        if list(first.shape) != want:
            self._geometry_mismatch(job['run_name'], {'images': list(first.shape)})
        require(first.dtype is torch.float32 and list(first.shape) == want,
                'Tensor geometry differs: images %s %s' % (list(first.shape), first.dtype))
        last = self.geometry['anchor_frame_index']
        frame_raw = stream_preview.anchor_bytes(torch, first, last)
        last_sha = hashlib.sha256(frame_raw).hexdigest()
        anchor_decode.update(seconds=round((timing['video_done'] - video_start) / 1e9, 6), last_frame_sha256=last_sha)
        if cone:
            anchor_decode['plan'] = (self.cone.receipt()['plans'] or [None])[-1]
        anchor_ready = timing['anchor_ready']
        frame_anchor = None
        reserved = {}
        go_base = None
        if self.anchor in ('frame', 'mixed'):
            # Written once (exclusive create, finiteness check, fsync) before anything names it.
            written = stream_receipts.write_anchor(self.run / 'anchors', job['run_name'], frame_raw, self.frames)
            require(written['sha256'] == last_sha and written['path'] == job['frame_anchor_path'],
                    'Frame anchor differs from the decoded last frame')
            frame_anchor = {'sha256': last_sha, 'bytes': len(frame_raw), 'path': written['path']}
            if self.anchor == 'frame':
                if levers_live:
                    stages = [s for s, on in (('A', self.prep_ahead), ('B', self.bencode_overlap)) if on]
                    reserved = {e.stage: e for e in self.precompute.reserve(last_sha, stages, job['run_name'])}
                with self.go:
                    go_base = self.sampler_a_starts
                anchor_ready = time.time_ns()
                # 116a hand-off: the chain continues from here; everything below runs behind it.
                self.decoder.publish(job, 'anchor', {'anchor_out': written, 'video_done': timing['video_done'],
                                                     'anchor_ready': anchor_ready})
            elif kind == 'stream':
                with self.frame_anchor_lock:
                    self.frame_anchor_files.append((job['stream_seq'], written['path']))
        timing['anchor_ready'] = anchor_ready
        # -- 2. prep-ahead: the successor's stage-A encode, after this chunk's receipt commits ----------------
        precomputed = {}
        read_ahead_live = levers_live and self.anchor_read_ahead
        if 'A' in reserved or read_ahead_live:
            if not gated:
                started = time.monotonic()
                schedule['commit'] = self.authority.wait_committed(job['run_name'], COMMIT_BOUND_S)
                schedule['commit_wait_s'] = round(time.monotonic() - started, 6)
            if read_ahead_live and (gated or schedule['commit']) and self.authority.failed is None:
                schedule['anchor_read_ahead'] = self.anchor_reads.prepare(
                    written['path'], last_sha, stream_receipts.read_anchor)
        if 'A' in reserved:
            if (gated or schedule['commit']) and self.authority.failed is None:
                timing['precompute_a_start'] = time.time_ns()
                precomputed['A'] = self._precompute(reserved['A'], frame_raw, last_sha, 'A', job['run_name'])
                timing['precompute_a_done'] = time.time_ns()
            else:
                # No successor can be admitted (no commit within the bound, or a halt): nothing to prepare.
                self.precompute.cancel(reserved['A'], 'halted' if self.authority.failed is not None else
                                       'receipt not committed within %.0f s' % COMMIT_BOUND_S)
                precomputed['A'] = reserved['A'].summary()
        # -- 3. wait for the successor's sampler A; then the stage-B encode (overlap) -------------------------
        # The sampler-B option shares ONE 3 s deadline with the original sampler-A wait and B preparation.
        # A missing successor/reset/end-of-stream therefore cannot cause two consecutive 3 s waits.
        go_deadline = time.monotonic() + GO_BOUND_S
        if levers_live and (cone or 'B' in reserved) and not gated:
            schedule['go'], schedule['go_wait_s'] = self._wait_go(go_base, GO_BOUND_S)
        timing['go'] = time.time_ns() if levers_live and (cone or 'B' in reserved) else None
        if 'B' in reserved:
            if self.authority.failed is not None:
                self.precompute.cancel(reserved['B'], 'halted')
                precomputed['B'] = reserved['B'].summary()
            elif not gated and not self._successor_consumes(last_sha):
                self.precompute.cancel(reserved['B'], 'no running request is anchored on this frame (%s)'
                                       % schedule['go'])
                precomputed['B'] = reserved['B'].summary()
            else:
                timing['precompute_b_start'] = time.time_ns()
                precomputed['B'] = self._precompute(reserved['B'], frame_raw, last_sha, 'B', job['run_name'])
                timing['precompute_b_done'] = time.time_ns()
        early_audio = (self._decode_audio_early(job, audio_vae)
                       if self.display_worker == 'parallel' and not gated else None)

        def finish_display():
            nonlocal first, reference, replica_check
            require(self.decoder.failed is None, 'Completion refused after companion worker failure')
            # -- 4. cone: the full decode for display, and the per-chunk byte check ------------------------------
            if cone:
                if self.display_schedule == 'sampler-b':
                    if gated:
                        schedule['display_release'] = {'reason': 'gated-no-wait', 'waited_s': 0.0,
                                                       'event': None, 'released_ns': time.time_ns()}
                    else:
                        schedule['display_release'] = self.successor_barrier.wait(
                            job['run_name'], last_sha, go_deadline, lambda: self.authority.failed is not None)
                try:
                    with torch.inference_mode():
                        ref_images = None
                        if graph and kind == 'qualify-graph':
                            ref_images, reference = self._reference_decode(vae, job['video_latent'])
                        elif replica_live and kind in ('qualify-eager', 'qualify-graph', 'qualify-repeat'):
                            ref_images, _ = self._reference_decode(vae, job['video_latent'])
                        require(self.decoder.failed is None, 'Display refused after companion worker failure')
                        timing['display_start'] = time.time_ns()
                        display_graph = graph and self.display_schedule != 'eager-display'
                        images = (self.display_replica.decode(job['video_latent']) if replica_live else
                                  self._video_decode(vae, job['video_latent'], display_graph))
                        timing['display_done'] = time.time_ns()
                    if replica_live and ref_images is not None:
                        replica_check = display_replica.compare(torch, images, ref_images)
                        require(replica_check['equal'], 'Cross-card display differs from xpu:3 uncached eager')
                    if reference is not None:
                        same = stream_decoder_graph.bitwise_equal(torch, images, ref_images)
                        reference.update(equal=bool(same), images_sha256=hashlib.sha256(
                            ref_images.detach().to('cpu').contiguous().view(torch.uint8).numpy()).hexdigest())
                        del ref_images
                        require(same, 'Decoder graph: the graph decode differs from the uncached eager decode of the '
                                      'same latents (%s)' % job['run_name'])
                except BaseException as error:
                    if graph:
                        self._decoder_graph_refused(job['run_name'], repr(error))
                    raise
                require(images.dtype is torch.float32 and list(images.shape) == want,
                        'Tensor geometry differs: display images %s %s' % (list(images.shape), images.dtype))
                display_raw = stream_preview.anchor_bytes(torch, images, last)
                equal = display_raw == frame_raw
                self.cone.note_check(equal)
                anchor_decode.update(display_seconds=round((timing['display_done'] - timing['display_start']) / 1e9, 6),
                                     display_last_frame_sha256=hashlib.sha256(display_raw).hexdigest(), equal=equal,
                                     differing_bytes=None if equal else sum(a != b for a, b in zip(display_raw, frame_raw)))
                if not equal:
                    self._lever_refused(stream_anchor_decode.LATCH_NAME, job['run_name'],
                                        'cone anchor frame differs from the display decode\'s last frame', anchor_decode)
                    require(False, 'Cone anchor decode: the anchor differs from the full decode\'s last frame (%s)'
                            % job['run_name'])
                del first
            else:
                images = first
                anchor_decode.update(display_seconds=None, display_last_frame_sha256=last_sha, equal=None)
            if replica_live:
                if kind == 'qualify-eager':
                    # The eager control remains xpu:3; the auxiliary replica comparison is separate evidence.
                    with torch.inference_mode():
                        candidate_images = self.display_replica.decode(job['video_latent'])
                    replica_check = display_replica.compare(torch, candidate_images, images)
                    require(replica_check['equal'], 'Cross-card eager control display differs')
                    del candidate_images
                if replica_check is None:
                    replica_check = {'device': 'xpu:2', 'reference_device': 'xpu:3',
                                     'mode': 'eager-uncached', 'equal': None}
                replica_check['residency'] = self.display_replica.receipt()
            # -- 5. audio, hashes, diagnostics, capture, record, preview ------------------------------------------
            if early_audio is None:
                with self.encoder_lock if self.display_worker == 'parallel' else nullcontext():
                    require(self.decoder.failed is None, 'Audio refused after companion worker failure')
                    aux_audio_before = residency123.guard_aux(torch, 'audio', True, self.aux_residency)
                    with torch.inference_mode():
                        audio = nodes.NODE_CLASS_MAPPINGS['LTXVAudioVAEDecode'].execute(
                            samples={'samples': job['audio_latent']}, audio_vae=audio_vae).result[0]
                    aux_audio_after = residency123.guard_aux(torch, 'audio', False, self.aux_residency)
                timing['audio_done'] = timing['decode_done'] = time.time_ns()
            else:
                audio = early_audio['audio']
                aux_audio_before, aux_audio_after = early_audio['before'], early_audio['after']
                timing['audio_done'] = early_audio['done_ns']
            timing['decode_done'] = max(timing['audio_done'], timing['display_done'] or timing['video_done'])
            require(type(audio) is dict and audio.get('sample_rate') == contract.SAMPLE_RATE, 'Audio sample rate differs')
            observed = {'images': list(images.shape), 'waveform': list(audio['waveform'].shape)}
            if observed != self.geometry['decoded_shapes']:
                self._geometry_mismatch(job['run_name'], observed)
            tensors = {name: _summary(torch, value, self.geometry['decoded_shapes'][name], name, require)
                       for name, value in (('images', images), ('waveform', audio['waveform']))}
            require(hashlib.sha256(stream_preview.anchor_bytes(torch, images, last)).hexdigest() == last_sha,
                    'Decoded last frame differs from the anchor frame')
            diagnostic = stream_preview.anchor_diagnostic(torch, images, last)
            sharpness = stream_preview.sharpness_profile(torch, images, self.frames)
            timing['hashed'] = time.time_ns()
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
            dg = self.decoder_graph
            decoder = {'flag': self.decoder_graph_flag, 'mode': 'graph' if graph else 'eager', 'reference': reference,
                       'video_decode_s': anchor_decode['seconds'],
                       'new_captures': 0 if dg is None else len(dg.captures) - captured_before,
                       'captured_graphs_total': 0 if dg is None else len(dg.captures),
                       'signatures': {} if dg is None else dg.signatures(),
                       'replays': {} if dg is None else dict(dg.replays),
                       'frozen': None if dg is None else dg.frozen,
                       'pool': None if dg is None else dg.pool_receipt()}     # packet123
            self.decode_sequence += 1
            timing['record_staged'] = time.time_ns()
            s = stream_receipts.seconds
            record = {'server_options': dict(self.server_options), 'schema': stream_receipts.DECODE_SCHEMA, 'run_name': job['run_name'], 'prompt_id': job['prompt_id'],
                      'kind': kind, 'stream_seq': job['stream_seq'], 'chunk_index': job['chunk_index'],
                      'frames': self.frames, 'anchor': self.anchor, 'device': 'xpu:3', 'order': 'fifo',
                      'audio_device': 'xpu:2' if self.aux_residency == 'xpu2' else 'xpu:3',
                      'aux_residency': self.aux_residency,
                      'aux_audio_workspace': {'before': aux_audio_before, 'after': aux_audio_after},
                      'sequence': self.decode_sequence, 'thread': threading.current_thread().name,
                      'sample_rate': contract.SAMPLE_RATE, 'tensors': tensors, 'last_frame_sha256': last_sha,
                      'anchor_diagnostics': diagnostic, 'sharpness': sharpness, 'capture': capture,
                      'frame_anchor': frame_anchor, 'decoder': decoder,
                      'display_device': self.display_device if cone else 'xpu:3',
                      'display_replica': replica_check,
                  'display_worker': self.display_worker,
                  'completion_worker': 'parallel' if self.display_worker == 'parallel' and not gated else 'serial',
                  'display_worker_timing': {
                      'queued_ns': job['timing'].get('display_worker_queued'),
                      'start_ns': job['timing'].get('display_worker_start'),
                      'gated_inline': gated,
                      'audio_start_ns': None if early_audio is None else early_audio['start_ns'],
                      'audio_done_ns': None if early_audio is None else early_audio['done_ns']},
                      'levers': {'anchor_decode': self.anchor_decode, 'bencode_overlap': self.bencode_overlap,
                                 'prep_ahead': self.prep_ahead},
                      'anchor_decode': anchor_decode, 'precompute': precomputed or None, 'schedule': schedule,
                      'xpu3_free_before_decode': free,
                      'preview': {'path': str(job['preview_path']),
                                  'record': str(self.run / 'receipts' / ('preview-' + job['run_name'] + '.json'))},
                      'timing_ns': timing,
                      'timing_s': {'queue_wait': s(timing, 'decode_queued', 'decode_start'),
                                   'video_decode': s(timing, 'decode_start', 'video_done'),
                                   'video_done_to_anchor_ready': (s(timing, 'video_done', 'anchor_ready')
                                                                  if self.anchor == 'frame' else None),
                                   'precompute_a': s(timing, 'precompute_a_start', 'precompute_a_done'),
                                   'precompute_b': s(timing, 'precompute_b_start', 'precompute_b_done'),
                                   'anchor_ready_to_go': s(timing, 'anchor_ready', 'go'),
                                   'display_decode': s(timing, 'display_start', 'display_done'),
                                   'audio_decode': ((early_audio['done_ns'] - early_audio['start_ns']) / 1e9
                                       if early_audio is not None else s(timing, 'display_done' if cone else (
                                       'video_done' if self.anchor != 'frame' else 'anchor_ready'), 'audio_done')),
                                   'hash_and_diagnostics': s(timing, 'decode_done', 'hashed'),
                                   'capture_and_record': s(timing, 'hashed', 'record_staged'),
                                   'decode': s(timing, 'decode_start', 'decode_done'),
                                   'anchor_ready_to_decode_done': s(timing, 'anchor_ready', 'decode_done'),
                                   'submit_to_decode_done': s(timing, 'submit', 'decode_done')}}
            stream_receipts.validate_decode_record(record)
            self.write('receipts/decode-' + job['run_name'] + '.json', record)
            record_written = time.time_ns()
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
                                 'timing': {'submit': timing['submit'], 'video_done': timing['video_done'],
                                            'anchor_ready': anchor_ready, 'audio_done': timing['audio_done'],
                                            'decode_done': timing['decode_done'], 'hashed': timing['hashed'],
                                            'record_written': record_written}})
            return record

        if self.display_worker == 'parallel' and not gated:
            return stream_decode.DeferredDisplay(finish_display)
        return finish_display()

    def inspect_state(self):
        import runtime_observer
        return runtime_observer.actual_state(fault=self.fault())

    def storage_check(self, mutate=True):
        # The launch value is frozen; later environment changes cannot increase it.
        return self.storage_account.check(self.run_write_allowance, self.session.require)

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
        """Capture-guard callback. Packet116 captures are written by the decode thread; the guard
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
                                 self.latent_guard is not None and self.guide_guard is not None,
                                 'Stream runtime has not been prepared')
            self.session.require(self.conditioning.active is None and self.latent_guard.active is None and
                                 self.guide_guard.active is None and self.current is None,
                                 'Prior request ownership remains active')
            self.registry.check()
            self.bindings.check_native()
            self.bindings.settings()
            self.current = {'name': row['name'], 'prompt_id': prompt_id, 'row': copy.deepcopy(row),
                            'timing': {k: None for k in stream_receipts.TIMING_KEYS},
                            'anchor_in': None, 'anchor_image': None, 'latent_parts': None, 'provided': False,
                            'guide_parts': None, 'guide_pin': {}, 'frame_in': None,
                            'text': None, 'output': None, 'decode_job': None, 'conditioning_sources': {},
                            'decode_at_start': {'drained': drained, 'pending': self.decoder.pending(),
                                                'current': self.decoder.summary()['current']}}
            timing = self.current['timing']
            timing['submit'] = self.submit_ns.pop(prompt_id, None)
            timing['execution_start'] = self.authority.active['start_ns']
            # Packet123 timing split (measurement only).
            # Keep the shared marks: the executor can enter before the POST handler returns.
            self.current['admission_marks'] = self.admission_marks.pop(prompt_id, {})
            stream_receipts.refresh_admission_timing(timing, self.current['admission_marks'])
            timing['executor_entry'] = (self.exec_marks.get(prompt_id) or {}).get('entry')
            self.current['health_before'] = self.authority.health_snapshot()
            self.current['routes_before'] = self.route_snapshot()
            params = row.get('params') or {}
            self.inspector.begin_request(params.get('stream_seq'), self.authority.phase)
            self.inspector.expect('request-before')
            timing['request_snapshot_start'] = time.time_ns()
            before = self.adapter.before_request(row['name'])
            timing['request_snapshot_done'] = time.time_ns()
            self.current['memory_before'] = before
            self.current['captured_before'] = self.adapter.last_inventory['captured_graphs']
            timing['before_request_done'] = time.time_ns()

    def _consumer(self, name, kinds):
        """Common checks of the single anchor provider of an admitted conditioned request."""
        active = self.active_row(name)
        cur = self.current
        params = active['params']
        kind = self.anchor
        self.session.require(cur is not None and cur['name'] == name and params is not None and
                             contract.anchored(params) and not cur['provided'] and kind in kinds,
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
            active, cur, params, pred = self._consumer(name, ('frame',))
            self.session.require(predecessor_anchor_sha256 == params['predecessor_anchor_sha256'],
                                 'Provider input differs from the admitted request')
            if params['kind'] == 'stream':
                self.session.require(predecessor_anchor_sha256 == pred['anchor_sha256'], 'Stale predecessor anchor')
            if self.anchor_read_ahead and params['kind'] != 'qualify-eager':
                raw, read_source = self.anchor_reads.take(pred['anchor_path'], pred['anchor_sha256'],
                                                         stream_receipts.read_anchor)
            else:
                raw, read_source = stream_receipts.read_anchor(pred['anchor_path'], pred['anchor_sha256']), 'native'
            cur['anchor_read_source'] = read_source
            self.bindings.check_native()
            image = torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(*contract.ANCHOR_SHAPE).clone()
            self.active_row(name)
            with self.encoder_lock:
                self.conditioning.begin_request(name, anchor=image, expected_anchor_sha256=pred['anchor_sha256'])
            cur.update(provided=True, anchor_image=image,
                       anchor_in={'kind': 'frame', 'sha256': pred['anchor_sha256'], 'path': pred['anchor_path'],
                                  'source_run_name': pred['run_name']})
            return image

    def provide_latent_anchor(self, name, predecessor_anchor_sha256):
        """Latent anchor (LTX_ANCHOR=latent): the two verified slices of the predecessor's anchor file.
        Mixed (LTX_ANCHOR=mixed): the same file; only the stage-A slice is consumed (stage B waits for
        the decoded frame in mixed_condition_b)."""
        import torch
        import latent_anchor
        with self.authority.lock:
            active, cur, params, pred = self._consumer(name, ('latent', 'mixed'))
            self.session.require(predecessor_anchor_sha256 == params['predecessor_anchor_sha256'],
                                 'Provider input differs from the admitted request')
            if params['kind'] == 'stream':
                self.session.require(predecessor_anchor_sha256 == pred['anchor_sha256'], 'Stale predecessor anchor')
            raw = latent_anchor.read_anchor(pred['anchor_path'], pred['anchor_sha256'], self.anchor)
            parts = latent_anchor.split(torch, raw, self.anchor)
            self.active_row(name)
            self.latent_guard.begin_request(name, pred['anchor_sha256'], parts,
                                            stages=('A', 'B') if self.anchor == 'latent' else ('A',))
            cur.update(provided=True, latent_parts=parts,
                       anchor_in={'kind': self.anchor, 'sha256': pred['anchor_sha256'], 'path': pred['anchor_path'],
                                  'source_run_name': pred['run_name']})
            return ({'samples': parts[0]}, {'samples': parts[1]})

    def condition(self, vae, image, latent, strength, bypass, run_name, stage):
        """Frame anchor: packet113's native image conditioning through the stage guard. Packet117: with
        prep-ahead (stage A) or the stage-B overlap (stage B) the native node runs with the encode the decode
        thread precomputed for this anchor; the graph chain also runs the native encode and requires the two
        results to be byte-identical."""
        def fixed_inputs():
            self.active_row(run_name)
            cur = self.current
            self.session.require(self.anchor == 'frame' and cur is not None and cur['name'] == run_name and
                                 cur['provided'] and image is cur['anchor_image'] and
                                 image is self.conditioning.anchor and
                                 type(strength) in (float, int) and strength == 1.0 and bypass is False and
                                 stage in ('A', 'B'), 'Conditioning node differs from its fixed inputs')
            self.session.require(self.adapter.current_name == run_name and self.adapter.guard is not None,
                                 'Conditioning requires the active no-eviction scope')
            return cur
        with self.authority.lock:
            cur = fixed_inputs()
            kind = cur['row']['kind']
            anchor_sha = cur['anchor_in']['sha256']
            lever = {'A': 'prep_ahead', 'B': 'bencode_overlap'}[stage]
            use = kind != 'qualify-eager' and bool(getattr(self, lever))
            entry = self.precompute.lookup(anchor_sha, stage) if use else None
        source = {'stage': stage, 'lever': lever, 'lever_on': use, 'source': 'native', 'reason': None,
                  'waited_s': None, 'dual_equal': None, 'precompute': None}
        stage_key = 'condition_%s' % stage.lower()
        got = None
        if use:
            if entry is None:
                source.update(source='native-inline', reason='not scheduled for this anchor')
            else:
                # Outside the authority lock: the decode thread and the status route keep moving while we wait.
                got, source['waited_s'] = self.precompute.take(entry, run_name, PRECOMPUTE_WAIT_BOUND_S)
                if got is None:
                    source.update(source='native-inline', reason=entry.state)
                else:
                    source.update(source='precomputed', precompute=got.summary())
        with self.authority.lock:
            cur = fixed_inputs()
            cur['timing'][stage_key + '_lookup_done'] = time.time_ns()      # packet123 (measurement)
            native_call = self.bindings.native_call
            if got is not None:
                native_call = self._precomputed_call(got, kind == 'qualify-graph', source, run_name)
            self.inspector.expect(stage + '-before', stage + '-after')
            with self.encoder_lock:
                result = self.conditioning.run_stage(stage, request_id=run_name, vae=vae, latent=latent,
                                                     native_call=native_call)
            cur['timing'][stage_key + '_done'] = time.time_ns()
            cur['conditioning_sources'][stage] = source
            return result

    def _precomputed_call(self, entry, dual, source, run_name):
        """The guard's native_call with the precomputed encode (ReplayVAE); dual: also the native encode."""
        import torch
        pg = precompute_guard
        require = self.session.require

        def call(vae, image, latent, strength, bypass):
            require(vae is self.adapter.objects['video_vae'], 'Precomputed conditioning needs the bound VAE')
            replay = pg.ReplayVAE(torch, vae, entry)
            result = self.bindings.native_call(vae=replay, image=image, latent=latent, strength=strength,
                                               bypass=bypass)
            require(replay.used, 'The native node did not consume the precomputed encode')
            if dual:
                native = self.bindings.native_call(vae=vae, image=image, latent=latent, strength=strength,
                                                   bypass=bypass)
                a, b = self.bindings.unwrap_output(result), self.bindings.unwrap_output(native)
                equal = (pg.bitwise_equal(torch, a['samples'], b['samples']) and
                         pg.bitwise_equal(torch, a['noise_mask'], b['noise_mask']))
                source.update(dual_equal=bool(equal),
                              precomputed_samples_sha256=pg.tensor_sha256(torch, a['samples']),
                              native_samples_sha256=pg.tensor_sha256(torch, b['samples']))
                if not equal:
                    self._lever_refused(pg.LATCH_NAME, run_name, 'precomputed stage-%s conditioning differs from '
                                        'the native conditioning' % source['stage'], dict(source))
                    require(False, 'Precomputed stage-%s conditioning differs from the native one (%s)'
                            % (source['stage'], run_name))
            return result
        return call

    def latent_condition(self, latent, anchor, strength, run_name, stage):
        with self.authority.lock:
            self.active_row(run_name)
            cur = self.current
            self.session.require(self.anchor in ('latent', 'mixed') and cur is not None and cur['name'] == run_name and
                                 cur['provided'] and cur['latent_parts'] is not None and
                                 stage in (('A', 'B') if self.anchor == 'latent' else ('A',)),
                                 'Latent conditioning node differs from its fixed inputs')
            self.session.require(self.adapter.current_name == run_name and self.adapter.guard is not None,
                                 'Conditioning requires the active no-eviction scope')
            self.bindings.check_native()
            return self.latent_guard.run_stage(stage, request_id=run_name, latent=latent, anchor=anchor,
                                               strength=strength)

    def mixed_condition_b(self, vae, latent, strength, bypass, run_name):
        """Mixed anchor, stage B: wait (bounded, outside the authority lock) for the predecessor's decode
        record, verify its frame-anchor file, then run packet113's native image conditioning (VAE encode)
        through the stage guard as a stage-B-only request. Runs on the prompt thread after the upsampler."""
        import torch
        import stream_receipts
        require = self.session.require
        with self.authority.lock:
            active = self.active_row(run_name)
            cur, params = self.current, active['params']
            require(self.anchor == 'mixed' and cur is not None and cur['name'] == run_name and cur['provided'] and
                    cur['latent_parts'] is not None and cur['frame_in'] is None and
                    type(strength) in (float, int) and strength == 1.0 and bypass is False and
                    vae is self.adapter.objects['video_vae'], 'Mixed stage-B node differs from its fixed inputs')
            require(self.adapter.current_name == run_name and self.adapter.guard is not None,
                    'Conditioning requires the active no-eviction scope')
            pred = cur['row']['predecessor']
            require(type(pred) is dict and pred['run_name'] == cur['anchor_in']['source_run_name'],
                    'Mixed stage B has no admitted predecessor')
            cur['timing']['frame_wait_start'] = time.time_ns()
        # Outside the authority lock: the decode thread and the status route keep moving while we wait.
        record, waited = self.decoder.wait_for(pred['run_name'], FRAME_WAIT_BOUND_S)
        with self.authority.lock:
            self.active_row(run_name)
            frame = record.get('frame_anchor') or {}
            require(record['run_name'] == pred['run_name'] and record['anchor'] == 'mixed' and
                    frame.get('sha256') == record['last_frame_sha256'] and type(frame.get('path')) is str,
                    'Predecessor decode record has no frame anchor')
            path = self.run / 'receipts' / ('decode-' + pred['run_name'] + '.json')
            raw_record = self.session.read_regular(path)
            require(self.session.canonical(self.session.strict_json(raw_record)) == self.session.canonical(record),
                    'Predecessor decode record on disk differs from the decode thread\'s')
            raw = stream_receipts.read_anchor(frame['path'], frame['sha256'])
            self.bindings.check_native()
            image = torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(*contract.ANCHOR_SHAPE).clone()
            self.conditioning.begin_request(run_name, anchor=image, expected_anchor_sha256=frame['sha256'],
                                            first_stage='B')
            cur['anchor_image'] = image
            cur['frame_in'] = {'sha256': frame['sha256'], 'path': frame['path'], 'source_run_name': pred['run_name'],
                               'decode_record_sha256': self.session.digest(raw_record),
                               'decode_sequence': record['sequence'], 'waited_s': waited}
            cur['anchor_in']['frame'] = dict(cur['frame_in'])
            cur['timing']['frame_ready'] = time.time_ns()
            self.inspector.expect('B-before', 'B-after')
            return self.conditioning.run_stage('B', request_id=run_name, vae=vae, latent=latent,
                                               native_call=self.bindings.native_call)

    def provide_guide_anchor(self, name, predecessor_anchor_sha256):
        """Guide anchor (LTX_ANCHOR=guide): the predecessor's last two latent slots of each stage."""
        import torch
        import latent_anchor
        with self.authority.lock:
            active, cur, params, pred = self._consumer(name, ('guide',))
            self.session.require(predecessor_anchor_sha256 == params['predecessor_anchor_sha256'],
                                 'Provider input differs from the admitted request')
            if params['kind'] == 'stream':
                self.session.require(predecessor_anchor_sha256 == pred['anchor_sha256'], 'Stale predecessor anchor')
            raw = latent_anchor.read_anchor(pred['anchor_path'], pred['anchor_sha256'], 'guide')
            parts = latent_anchor.split(torch, raw, 'guide')
            self.active_row(name)
            self.guide_guard.begin_request(name, pred['anchor_sha256'], parts)
            cur.update(provided=True, guide_parts=parts,
                       anchor_in={'kind': 'guide', 'sha256': pred['anchor_sha256'], 'path': pred['anchor_path'],
                                  'source_run_name': pred['run_name']})
            return ({'samples': parts[0]}, {'samples': parts[1]})

    def _guide_native(self, which):
        """The pinned native guide/crop call, re-checked at every use (registration, code object, file)."""
        cls, fn, code = self.guide_native[which]
        import nodes
        self.session.require(nodes.NODE_CLASS_MAPPINGS.get(cls.__name__) is cls and
                             cls.execute.__func__ is fn and fn.__code__ is code, 'Native %s node changed' % which)
        self.bindings.check_native()   # re-pins source/comfy_extras/nodes_lt.py

        def call(**kwargs):
            result = cls.execute(**kwargs)
            out = getattr(result, 'result', None)
            self.session.require(type(out) is tuple and len(out) == 3, 'Native %s must return three outputs' % which)
            return out
        return call

    def guide(self, positive, negative, vae, latent, guide, strength, run_name, stage):
        with self.authority.lock:
            self.active_row(run_name)
            cur = self.current
            self.session.require(self.anchor == 'guide' and cur is not None and cur['name'] == run_name and
                                 cur['provided'] and cur['guide_parts'] is not None and stage in ('A', 'B') and
                                 vae is self.adapter.objects['video_vae'],
                                 'Guide node differs from its fixed inputs')
            self.session.require(self.adapter.current_name == run_name and self.adapter.guard is not None,
                                 'Conditioning requires the active no-eviction scope')
            return self.guide_guard.run_guide(stage, request_id=run_name, positive=positive, negative=negative,
                                              vae=vae, latent=latent, guide=guide, strength=strength,
                                              native_call=self._guide_native('guide'))

    def crop(self, positive, negative, latent, run_name, stage):
        import torch
        import latent_anchor
        with self.authority.lock:
            self.active_row(run_name)
            cur = self.current
            self.session.require(self.anchor == 'guide' and cur is not None and cur['name'] == run_name and
                                 cur['guide_parts'] is not None and stage in ('A', 'B') and stage not in cur['guide_pin'],
                                 'Crop node differs from its fixed inputs')
            part = cur['guide_parts'][0 if stage == 'A' else 1]
            cur['guide_pin'][stage] = latent_anchor.pin_diagnostic(torch, latent['samples'], part, tail=True)
            return self.guide_guard.run_crop(stage, request_id=run_name, positive=positive, negative=negative,
                                             latent=latent, native_call=self._guide_native('crop'))

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
            pin = guide_pin = None
            anchor_out = None
            frame_path = None
            if self.anchor in contract.OFF_CHAIN_DECODE:
                raw = latent_anchor.anchor_bytes(torch, latents['stage_a_latent'], latents['video_latent'],
                                                 self.frames, self.anchor)
                anchor_out = latent_anchor.write_anchor(self.run / 'anchors', run_name, raw, self.frames, self.anchor)
                if self.anchor == 'mixed':
                    # The decode thread writes this chunk's decoded last frame here before its record.
                    frame_path = stream_receipts.anchor_path(self.run / 'anchors', run_name)
                    require(not frame_path.exists(), 'Mixed frame anchor path already exists')
                    anchor_out['frame'] = {'writer': 'decode thread', 'path': str(frame_path),
                                           'record': str(self.run / 'receipts' / ('decode-' + run_name + '.json'))}
                # Anchor ready: everything the next chunk's text encode and stage A consume (and, for the
                # latent and guide anchors, stage B too) is hashed and durable.
                cur['timing']['anchor_ready'] = time.time_ns()
                if anchored and self.anchor == 'latent':
                    a, b = cur['latent_parts']
                    pin = {'A': latent_anchor.pin_diagnostic(torch, latents['stage_a_latent'], a),
                           'B': latent_anchor.pin_diagnostic(torch, latents['video_latent'], b)}
                elif anchored and self.anchor == 'mixed':
                    pin = {'A': latent_anchor.pin_diagnostic(torch, latents['stage_a_latent'], cur['latent_parts'][0])}
                elif anchored:
                    require(set(cur['guide_pin']) == {'A', 'B'}, 'Guide crops did not record their pins')
                    guide_pin = dict(cur['guide_pin'])
            if self.anchor == 'frame':
                # Packet116: the decode thread writes this chunk's decoded last frame here right after the
                # video decode and hands it to the chain (job stage 'anchor').
                frame_path = stream_receipts.anchor_path(self.run / 'anchors', run_name)
                require(not frame_path.exists(), 'Frame anchor path already exists')
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
                   'preview_path': path, 'relative': relative,
                   'includes_overlap_frame': anchored and self.anchor in contract.SLOT0_ANCHORS,
                   'frame_anchor_path': None if frame_path is None else str(frame_path),
                   'capture': capture,
                   'stage_names': ('anchor',) if self.anchor == 'frame' else (),
                   'timing': {'submit': cur['timing']['submit'], 'anchor_ready': cur['timing']['anchor_ready']}}
            cur['decode_job'] = job
            cur['output'] = {'tensors': summary, 'anchor_out': anchor_out, 'slot0_pin': pin, 'guide_pin': guide_pin,
                             'decode': {'state': 'queued', 'device': 'xpu:3',
                                        'record': str(self.run / 'receipts' / ('decode-' + run_name + '.json'))},
                             'preview': {'path': str(path), 'relative_to_output_directory': relative,
                                         'state': 'queued', 'bytes': None,
                                         'record': str(self.run / 'receipts' / ('preview-' + run_name + '.json')),
                                         'container': 'mp4', 'lossy': True, 'fps': contract.FPS,
                                         'frames': self.frames,
                                         'includes_overlap_frame': anchored and self.anchor in contract.SLOT0_ANCHORS}}
        # Outside the authority lock: back-pressure must not block the status route.
        queued, depth, blocked = self.decoder.submit(job)
        record = stage = None
        if params['kind'] in contract.GATED_KINDS:
            # Gated qualification chunks wait for their whole decode in every anchor mode: no decode,
            # capture or replay runs beside the eager or graph chain (the controls; the decoder graph is
            # captured on the graph chain's chunk 0 while the chain waits here).
            record = self.decoder.wait(job, DECODE_DRAIN_BOUND_S)
            if self.anchor == 'frame':
                stage = job['stages'].get('anchor')
        elif self.anchor == 'frame':
            # 116a: wait for the video decode and the anchor file only.
            stage = self.decoder.wait_stage(job, 'anchor', ANCHOR_WAIT_BOUND_S)
        with self.authority.lock:
            self.active_row(run_name)
            cur['timing']['decode_queued'] = queued
            cur['output']['decode'].update(queue_depth_at_submit=depth, submit_blocked_s=blocked)
            if self.anchor == 'frame':
                anchor_out = stage['anchor_out'] if type(stage) is dict else None
                require(type(anchor_out) is dict and anchor_out.get('path') == str(frame_path) and
                        anchor_out.get('kind') == 'frame' and anchor_out.get('bytes') == contract.ANCHOR_BYTES and
                        type(stage.get('video_done')) is int and type(stage.get('anchor_ready')) is int,
                        'Frame anchor hand-off from the decode thread differs')
                cur['timing']['video_done'] = stage['video_done']
                cur['timing']['anchor_ready'] = stage['anchor_ready']
                cur['output'].update(anchor_out=anchor_out)
                cur['output']['decode'].update(state='video_done')
            if record is not None:
                if self.anchor == 'frame':
                    require(record['last_frame_sha256'] == cur['output']['anchor_out']['sha256'],
                            'Decoded anchor frame differs from its decode record')
                cur['timing']['decode_done'] = record['timing_ns']['decode_done']
                cur['output']['decode'].update(state='done', sequence=record['sequence'])
        return {'ui': {'text': [str(path)]}}

    def _conditioning_policy(self, name, expected=('A', 'B')):
        receipts = [r for r in self.conditioning.receipts if r['request_id'] == name]
        stages = [r for r in receipts if r['event'] == 'stage']
        self.session.require(len(stages) == len(expected) and [r['stage'] for r in stages] == list(expected) and
                             all(r['completed'] is True for r in stages), 'Conditioning stages incomplete')
        before = [[r['before']['required_physical_free_bytes']['xpu:%d' % i] for i in range(4)] for r in stages]
        after = [v for r in stages for v in r['after']['required_physical_free_bytes'].values()]
        self.session.require(before == [[8 * GIB, 8 * GIB, 2 * GIB, 9 * GIB]] * len(expected) and
                             after == [2 * GIB] * (4 * len(expected)), 'Conditioning memory floors changed')
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
                with self.encoder_lock:
                    self.conditioning.finish_request(name)
                guard_receipts, conditioning_memory = self._conditioning_policy(name)
            elif self.anchor == 'guide':
                self.guide_guard.finish_request(name)
                guard_receipts = self.guide_guard.drain(name)
                steps = [(r['event'], r['stage']) for r in guard_receipts if r['event'] in ('guide', 'crop')]
                self.session.require(steps == list(self.guide_guard.ORDER) and
                                     all(r['completed'] is True for r in guard_receipts
                                         if r['event'] in ('guide', 'crop')), 'Guide conditioning incomplete')
            else:
                expected = ['A', 'B'] if self.anchor == 'latent' else ['A']
                self.latent_guard.finish_request(name)
                guard_receipts = self.latent_guard.drain(name)
                stages = [r for r in guard_receipts if r['event'] == 'stage']
                self.session.require([r['stage'] for r in stages] == expected and
                                     all(r['completed'] is True for r in stages), 'Latent conditioning incomplete')
                if self.anchor == 'mixed':
                    self.session.require(cur['frame_in'] is not None, 'Mixed stage B skipped its frame')
                    self.conditioning.finish_request(name)
                    native_receipts, conditioning_memory = self._conditioning_policy(name, ('B',))
                    guard_receipts = guard_receipts + native_receipts
        else:
            self.session.require(not cur['provided'] and self.conditioning.active is None and
                                 self.latent_guard.active is None and self.guide_guard.active is None and
                                 cur['frame_in'] is None, 'An unanchored chunk cannot consume an anchor')
        self.inspector.expect('request-after')
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
            (params['kind'] != 'stream' or params['predecessor_anchor_sha256'] == pred['anchor_sha256']) and
            (self.anchor != 'mixed' or cur['frame_in']['source_run_name'] == pred['run_name']))
        self.session.require(chain_ok, 'Anchor chain check failed')
        events = self.events.pop(cur['prompt_id'], {})
        timing = cur['timing']
        # Snapshot late handler marks before freezing the receipt; never wait for HTTP.
        stream_receipts.refresh_admission_timing(timing, cur.get('admission_marks', {}))
        for node, key in stream_receipts.EVENT_NODES.items():
            timing[key] = events.get(node)
        node_starts = self.node_events.pop(cur['prompt_id'], {})
        snapshots = self.inspector.drain()
        health = self.authority.health_snapshot()
        routes = self.route_snapshot()
        timing['receipt_staged'] = time.time_ns()
        turnaround = self._turnaround(pred, timing)
        self.staged_ns[name] = timing['receipt_staged']
        _bound(self.staged_ns, self.receipt_served, self.receipt_polls, self.exec_marks)
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
            'decoder_graph': self.decoder_graph_flag,
            'levers': {'anchor_decode': self.anchor_decode, 'bencode_overlap': self.bencode_overlap,
                       'prep_ahead': self.prep_ahead},
            'server_options': dict(self.server_options),
            'aux_upsampler_workspace': (getattr(self.adapter.objects['upsampler'], '_ltx123_aux_workspace', None)
                if self.aux_residency == 'xpu2' else None),
            'snapshots': snapshots, 'node_starts_ns': node_starts, 'turnaround': turnaround,
            'authority_checks': {
                'healthy_calls': health['calls'] - cur['health_before']['calls'],
                'healthy_s': round(health['seconds'] - cur['health_before']['seconds'], 6),
                'plan_digest_s': round(health['plan_digest_seconds'] - cur['health_before']['plan_digest_seconds'], 6),
                'status_route_calls': routes['status_calls'] - cur['routes_before']['status_calls'],
                'status_route_s': round(routes['status_seconds'] - cur['routes_before']['status_seconds'], 6),
                'window': 'execution start -> receipt staged (prompt thread, decode thread, status route)'},
            'anchor_read_source': cur.get('anchor_read_source'),
            'conditioning_sources': (dict(cur['conditioning_sources']) if anchored and self.anchor == 'frame'
                                     else None),
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
            'guide_pin': cur['output']['guide_pin'],
            'delivery': stream_receipts.delivery(params['chunk_index'], self.frames, anchored, self.anchor),
            'decode': cur['output']['decode'], 'preview': cur['output']['preview'],
            'predecessor_preview': prior, 'predecessor_decode': prior_decode,
            'decode_at_start': cur['decode_at_start'],
            'capture': capture, 'timing_ns': timing,
            'timing_s': {'submit_to_sampler_start': s(timing, 'submit', 'sampler_a_start'),
                         'submit_split': stream_receipts.submit_split(timing, snapshots, node_starts),   # packet123
                         'sampler_a_bucket': s(timing, 'sampler_a_start', 'sampler_b_start'),
                         'sampler_a_split': {'sampler_a': s(timing, 'sampler_a_start', 'stage_a_done'),
                                             'separate_to_upsampler': s(timing, 'stage_a_done', 'upsampler_start'),
                                             'upsampler_to_condition_b': s(timing, 'upsampler_start',
                                                                           'condition_b_start'),
                                             'condition_b_to_concat': s(timing, 'condition_b_start', 'concat_b_start'),
                                             'concat_to_sampler_b': s(timing, 'concat_b_start', 'sampler_b_start')},
                         'sampler_b': s(timing, 'sampler_b_start', 'stage_b_done'),
                         # mixed: how long stage B waited for the predecessor's decoded frame (0 when the
                         # decode finished during text + stage A), and the frame read + native encode after it
                         'frame_wait': s(timing, 'frame_wait_start', 'frame_ready'),
                         'frame_ready_to_concat': s(timing, 'frame_ready', 'concat_b_start'),
                         'stage_b_done_to_anchor_ready': s(timing, 'stage_b_done', 'anchor_ready'),
                         'submit_to_anchor_ready': s(timing, 'submit', 'anchor_ready'),
                         'anchor_ready_to_receipt_staged': s(timing, 'anchor_ready', 'receipt_staged'),
                         # frame (116a): the chain waited for the video decode and the anchor hand-off only
                         'decode_in_chain': (s(timing, 'decode_queued', 'anchor_ready') if self.anchor == 'frame'
                                             else s(timing, 'decode_queued', 'decode_done')),
                         'video_decode_in_chain': s(timing, 'decode_queued', 'video_done'),
                         # packet117: the anchor decode the chain waited for (cone or full)
                         'anchor_decode_in_chain': (s(timing, 'decode_queued', 'video_done')
                                                    if self.anchor == 'frame' else None),
                         'video_done_to_anchor_ready': s(timing, 'video_done', 'anchor_ready'),
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
        if self.anchor == 'mixed' and params['kind'] == 'stream':
            self._prune_frame_anchors(params['stream_seq'])
        self.authority.stage_receipt(name, receipt)
        self.current = None

    def _turnaround(self, pred, timing):
        """Packet123: the predecessor's receipt -> this submit (measurement only; None for chain starts)."""
        import stream_receipts
        if pred is None or pred.get('commit_ns') is None:
            return None
        name = pred['run_name']
        pid = self.authority.request_prompt_ids.get(name)
        marks = {'receipt_staged': self.staged_ns.get(name), 'commit': pred.get('commit_ns'), 'commit_written': pred.get('commit_written_ns'),
                 'executor_exit': (self.exec_marks.get(pid) or {}).get('exit'),
                 'first_served': self.receipt_served.get(name), 'admission_received': timing.get('admission_received'),
                 'submit': timing.get('submit')}
        return {'predecessor_run_name': name, 'marks_ns': marks,
                'receipt_polls_before_served': self.receipt_polls.get(name, 0),
                'split': stream_receipts.turnaround_split(marks),
                'commit_to_executor_exit_s': stream_receipts.seconds(marks, 'commit_written', 'executor_exit')}

    def _prune_frame_anchors(self, stream_seq):
        """Mixed: keep the decode thread's stream frame anchors of this chunk and its predecessor only
        (an older one can never be consumed again: strict predecessor rule)."""
        with self.frame_anchor_lock:
            stale = [row for row in self.frame_anchor_files if row[0] < stream_seq - 1]
            self.frame_anchor_files = [row for row in self.frame_anchor_files if row[0] >= stream_seq - 1]
        for _, path in stale:
            Path(path).unlink()

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
                'guide_guard_receipts': self.guide_guard.receipts if self.guide_guard is not None else [],
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
        # Packet116: the decode thread and the prompt thread share ComfyUI's model registry.
        # Serialize load_models_gpu and the adapter's residency inspection (stream_decode.RegistryLock).
        lock_receipt = self.registry.install(mm)
        # Packet123: the controller's inspect callable is the SnapshotInspector (walk mode: packet 117's _inspect,
        # timed; fingerprint mode: armed once the ledger is bound below), under the same registry lock.
        import native_adapter
        from native_safety import CARDS, PRE_BYTES, ROLES
        walk_inspect = self.adapter._inspect
        self.inspector = snapshot_fingerprint.SnapshotInspector(
            mode=self.snapshot_mode, adapter=self.adapter, walk_inspect=walk_inspect, ledger=None if
            self.snapshot_mode == 'walk' else snapshot_fingerprint.ResidenceLedger(
                adapter=self.adapter, roles=ROLES, fingerprint=native_adapter.fingerprint,
                require_fn=native_adapter.require),
            roles=ROLES, cards=CARDS, pre_floors=PRE_BYTES,
            phase=lambda: self.authority.phase, latch=self._snapshot_refused, require_fn=native_adapter.require)
        self.inspector.schedule = self.snapshot_schedule
        inspector = self.inspector

        def inspect(objects, observation=False):
            return inspector(objects, observation)
        self.adapter._inspect = self.registry.wrap(inspect)
        snapshot = self.adapter.prepare()
        self.inspector.bind_synchronize(self.adapter.controller)
        if self.snapshot_mode == 'fingerprint':
            # The placement event: bind the fact tuples to the admitted fingerprints (one walk, under the lock).
            self.ledger = self.inspector.ledger
            ledger_receipt = self.registry.wrap(self.ledger.capture)(self.adapter.controller)
        else:
            ledger_receipt = None
        self.write('stream-preparation.json', {'snapshot': snapshot, 'receipts': self.adapter.drain_receipts(),
                                               'registry_lock': lock_receipt, 'snapshot_mode': self.snapshot_mode,
                                               'residence_ledger': ledger_receipt})
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
        # Packet116 guide anchor: the native guide/crop nodes and get_keyframe_idxs from the pinned nodes_lt.py.
        sealed = (self.packet / 'source/comfy_extras/nodes_lt.py').resolve()
        get_keyframe_idxs = native.get('get_keyframe_idxs')
        self.session.require(callable(get_keyframe_idxs) and
                             Path(get_keyframe_idxs.__code__.co_filename).resolve() == sealed,
                             'Native get_keyframe_idxs is not the sealed nodes_lt.py function')
        self.guide_native = {}
        for which, node in (('guide', 'LTXVAddLatentGuide'), ('crop', 'LTXVCropGuides')):
            cls = nodes.NODE_CLASS_MAPPINGS.get(node)
            fn = getattr(getattr(cls, 'execute', None), '__func__', None)
            self.session.require(cls is not None and fn is not None and
                                 Path(fn.__code__.co_filename).resolve() == sealed and
                                 native.get(node) is cls, 'Native %s is not the sealed nodes_lt.py node' % node)
            self.guide_native[which] = (cls, fn, fn.__code__)
        self.guide_guard = latent_anchor.GuideGuard(torch=torch, tensor_metadata=self.bindings.tensor_metadata,
                                                    get_keyframe_idxs=get_keyframe_idxs, frames=self.frames)
        for node in ('VAEDecode', 'LTXVAudioVAEDecode', 'LTXBaselineCapture'):
            self.session.require(node in nodes.NODE_CLASS_MAPPINGS, 'Decode-thread node missing: ' + node)
        if self.display_device == 'xpu:2':
            self.display_replica = self._install_display_replica(torch, name)
        if self.decoder_graph_flag:
            self.decoder_graph = self._install_decoder_graph(torch)
        if self.anchor_decode == 'cone':
            self.cone = self._install_cone(torch)
        if self.prep_ahead or self.bencode_overlap:
            self.xpu3_snapshot = self._xpu3_guard(torch)
        self.adapter.controller.drain()
        self.write('stream-native-binding.json', dict(self.bindings.receipt(), anchor=self.anchor,
                                                      latent_condition='nodes_lt.get_noise_mask (pinned source)',
                                                      guide='nodes_lt.LTXVAddLatentGuide / LTXVCropGuides / '
                                                            'get_keyframe_idxs (pinned source)'))
        return snapshot

    def _install_display_replica(self, torch, name):
        try:
            replica = display_replica.ResidentDisplay(torch, self.adapter.objects['video_vae'], self.frames,
                lambda: torch.xpu.mem_get_info('xpu:2')[0],
                lambda reason: self._lever_refused(display_replica.LATCH_NAME, name, reason))
            import importlib
            na = importlib.import_module('comfy_kitchen.backends.eager.na')
            route, _ = self._na3d_route(torch, na, replica.model.decoder)
            self.write('stream-display-replica-install.json', dict(replica.receipt(), na3d_route=route))
            return replica
        except BaseException as error:
            self._lever_refused(display_replica.LATCH_NAME, name, repr(error))
            raise

    def _install_decoder_graph(self, torch):
        """Packet116 (LTX_DECODER_GRAPH=1): bind the decoder-graph controller to the resident decoder.
        Pins the decoder source (sealed manifest) and the eager na3d backend (dependency overlay), and
        proves that na3d on the decoder's device dispatches to the eager backend whose mask builder
        the cache wraps. Nothing is captured here; the graph chain's chunk 0 captures on the decode thread."""
        import importlib
        import ltx_graph_capture
        require = self.session.require
        dg_mod = stream_decoder_graph
        nd = importlib.import_module('comfy.ldm.lightricks.vae.na_diffusion_decoder')
        na = importlib.import_module('comfy_kitchen.backends.eager.na')
        sealed = (self.packet / dg_mod.DECODER_SOURCE_PATH).resolve()
        require(Path(nd.__file__).resolve() == sealed and
                self.session.digest(Path(nd.__file__).read_bytes()) == self.manifest['files'][dg_mod.DECODER_SOURCE_PATH],
                'Decoder module is not the sealed na_diffusion_decoder.py')
        require(Path(na.__file__).resolve() == Path(dg_mod.NA_EAGER_PATH).resolve() and
                self.session.digest(Path(na.__file__).read_bytes()) == dg_mod.NA_EAGER_SHA256,
                'Eager na3d backend differs from the pinned dependency overlay file')
        vae = self.adapter.objects['video_vae']
        decoder = vae.first_stage_model.decoder
        route, router = self._na3d_route(torch, na, decoder)
        dg = dg_mod.DecoderGraph(torch, nd, na, decoder, ltx_graph_capture, router=router,
                                 pool_cap_bytes=self.pool_cap)        # packet123 (None = packet 117)
        receipt = dg.install()
        self.write('stream-decoder-graph-install.json', dict(receipt, na3d_route=route,
                                                             decoder_source=str(sealed),
                                                             na_eager_source=dg_mod.NA_EAGER_PATH))
        return dg

    def _na3d_route(self, torch, na, decoder):
        """Prove that na3d on the decoder's device dispatches to the pinned eager backend (or the pinned NA
        axis router's no-scope route to it). Packet116b's proof, shared by the decoder graph and the cone."""
        require = self.session.require
        dg_mod = stream_decoder_graph
        from comfy_kitchen.registry import registry
        probe = torch.zeros((1, 2, 2, 2, 1, 64), dtype=next(decoder.parameters()).dtype, device=next(decoder.parameters()).device)
        impl = registry.get_implementation('na3d', kwargs={'q': probe, 'k': probe, 'v': probe,
                                                           'kernel_size': [1, 1, 1], 'is_causal': [False] * 3,
                                                           'scale': 1.0})
        del probe
        # Packet116b: the live server's whitelisted ltx_na_axis_decode_lab installs the NA axis router over the
        # eager backend attribute; accept it only in its pinned no-scope route to the eager na3d.
        route, router = dg_mod.na_route(impl, na, lambda path: self.session.digest(Path(path).read_bytes()))
        if router is not None:
            require(Path(sys_modules_file(router)).resolve() == (self.packet / dg_mod.ROUTER_SOURCE_PATH).resolve() and
                    self.manifest['files'][dg_mod.ROUTER_SOURCE_PATH] == dg_mod.ROUTER_SHA256,
                    'NA axis router is not the sealed packet file')
        return route, router

    def _install_cone(self, torch):
        """Packet117 (LTX_ANCHOR_DECODE=cone): the cone-restricted stage-5 step on the resident decoder, over
        the decoder-graph shadow when LTX_DECODER_GRAPH=1. Pins the decoder source and the eager na3d file,
        and proves the na3d dispatch the cone re-implements (the eager backend)."""
        import importlib
        require = self.session.require
        sad = stream_anchor_decode
        nd = importlib.import_module('comfy.ldm.lightricks.vae.na_diffusion_decoder')
        na = importlib.import_module('comfy_kitchen.backends.eager.na')
        sealed = (self.packet / sad.DECODER_SOURCE_PATH).resolve()
        require(Path(nd.__file__).resolve() == sealed and
                self.manifest['files'][sad.DECODER_SOURCE_PATH] == sad.DECODER_SOURCE_SHA256,
                'Decoder module is not the sealed na_diffusion_decoder.py')
        require(Path(na.__file__).resolve() == Path(stream_decoder_graph.NA_EAGER_PATH).resolve(),
                'Eager na3d backend is not the pinned dependency overlay file')
        decoder = self.adapter.objects['video_vae'].first_stage_model.decoder
        route, _router = self._na3d_route(torch, na, decoder)
        require(str(next(decoder.parameters()).device) == 'xpu:3', 'Cone decode expects the decoder on xpu:3')
        cone = sad.ConeAnchorDecode(torch, nd, na, decoder, nd.comfy_kitchen,
                                    lambda path: self.session.digest(Path(path).read_bytes()),
                                    decoder_graph=self.decoder_graph)
        receipt = cone.install()
        self.write('stream-anchor-decode-install.json', dict(receipt, na3d_route=route, decoder_source=str(sealed),
                                                             na_eager_source=stream_decoder_graph.NA_EAGER_PATH))
        return cone

    def _xpu3_guard(self, torch):
        """Packet117: the xpu:3-only safety snapshot of the decode thread's precomputed encodes."""
        import native_adapter
        pg = precompute_guard
        controller = self.adapter.controller
        rows = lambda role: self.adapter._rows(role, require_loaded=True)
        fingerprint = native_adapter.fingerprint
        if self.snapshot_mode == 'fingerprint':
            # Packet123: P7 from the residence ledger, dual with the walk under the inspector's policy.
            rows, fingerprint = self.inspector.xpu3_callbacks(lambda: torch.xpu.mem_get_info('xpu:3')[0],
                                                              pg.PRE_FLOOR, always_dual=True)
        return pg.Xpu3Snapshot(
            controller=controller,
            phase_ok=lambda: (self.authority.failed is None and
                              self.authority.phase in ('stream_qualification', 'stream')),
            fault=self.fault,
            synchronize=torch.xpu.synchronize,
            free_bytes=lambda card: torch.xpu.mem_get_info(card)[0],
            counters=lambda card: {'allocated': int(torch.xpu.memory_allocated(card)),
                                   'reserved': int(torch.xpu.memory_reserved(card)),
                                   'peak': int(torch.xpu.max_memory_allocated(card))},
            rows=rows, fingerprint=fingerprint,
            observe_free=(lambda free: self.inspector.observe_xpu3_free(free, pg.PRE_FLOOR))
            if self.snapshot_mode == 'fingerprint' else None)

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
        now = time.time_ns()
        if type(prompt_id) is str and type(node) is str:
            # Packet123: every node start of the request (measurement only, bounded by the graph).
            table = self.node_events.setdefault(prompt_id, {})
            if len(table) < 64:
                table.setdefault(node, now)
            _bound(self.node_events, keep=16)
        if type(prompt_id) is str and type(node) is str and node in stream_receipts.EVENT_NODES:
            self.events.setdefault(prompt_id, {}).setdefault(node, now)
            if node == '344':
                # Packet117: a sampler A started; the decode thread's deferred work may go.
                with self.go:
                    self.sampler_a_starts += 1
                    self.go.notify_all()
            elif node == '368':
                # Bind the release to the *actual* consuming request. A reset or unrelated chain's
                # sampler B must not release the previous chunk's display as a matching successor.
                cur = self.current
                anchor = (cur or {}).get('anchor_in')
                if cur is not None and cur.get('prompt_id') == prompt_id and type(anchor) is dict and \
                        anchor.get('kind') == 'frame':
                    self.successor_barrier.mark(anchor['source_run_name'], anchor['sha256'],
                                                cur['name'], prompt_id, now)

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
            raw_ref = self.session.read_regular(self.packet / REFERENCE_PATH)
            self.session.require(self.session.digest(raw_ref) == self.manifest['files'][REFERENCE_PATH],
                                 'Reference hashes differ from the sealed packet')
            references = self.session.strict_json(raw_ref)
            verdict = qualification_gate.decide(receipts, decodes, captures, self.session.PLAN_SHA256, self.frames,
                                                self.text_reuse, self.placement, self.anchor,
                                                decoder_graph=self.decoder_graph_flag, references=references,
                                                levers=self.levers, server_options=self.server_options)
            verdict.update(receipts={r['run_name']: self.authority.receipts[r['run_name']] for r in receipts},
                           decode_records=decode_bindings,
                           preview_writer=self.preview.summary(), decoder=self.decoder.summary(),
                           captures=captures, observation_routes=observed['route_inventory'],
                           signature_digests=self.adapter.last_inventory['signature_digests'],
                           capture_guard=self.capture_guard.receipt(), state=state,
                           time_ns=time.time_ns())
            sha = self.write('stream-qualification-verdict.json', verdict)
            self.actions_done.add(action)
            if self.decoder_graph_flag and verdict.get('decoder_graph_failures'):
                self._decoder_graph_refused('qualify-verdict', '; '.join(verdict['decoder_graph_failures'])[:4000])
            for latch, key in ((stream_anchor_decode.LATCH_NAME, 'anchor_decode_failures'),
                               (precompute_guard.LATCH_NAME, 'precompute_failures'),
                               (snapshot_fingerprint.LATCH_NAME, 'snapshot_failures'),
                               (display_replica.LATCH_NAME, 'display_replica_failures')):
                if verdict.get(key):
                    self._lever_refused(latch, 'qualify-verdict', '; '.join(verdict[key])[:4000])
            if not verdict['passed']:
                self.authority.halt(RuntimeError('Qualification failed: ' + '; '.join(verdict['failures'])[:2000]))
                return {'passed': False, 'failures': verdict['failures'], 'verdict_sha256': sha}
            capture = self.adapter.capture
            self.qualified_windows = {self.window_precheck(p) for p in set(contract.QUALIFICATION_PROMPTS)}
            self.frozen_signatures = dict(self.adapter.last_inventory['signature_digests'])
            capture.CAPTURES_FROZEN[0] = True
            if self.decoder_graph is not None:
                self.decoder_graph.freeze()      # no new decoder signature or cache entry after the verdict
            self.authority.accept_verdict(verdict, sha)
            self.adapter.native_state()  # the frozen contract must hold immediately
            self.write('stream-freeze.json', {'qualified_text_windows': sorted(self.qualified_windows),
                                              'frozen_signature_digests': self.frozen_signatures,
                                              'decoder_graph': (None if self.decoder_graph is None else
                                                                self.decoder_graph.receipt()),
                                              'anchor_decode': None if self.cone is None else self.cone.receipt(),
                                              'precompute': self.precompute.summary(),
                                              'snapshot': self.inspector.summary(),
                                              'server_options': dict(self.server_options),
                                              'verdict_sha256': sha, 'time_ns': time.time_ns()})
            return {'passed': True, 'verdict_sha256': sha, 'phase': self.authority.phase,
                    'qualified_text_windows': sorted(self.qualified_windows)}


def sys_modules_file(router):
    """The source file of the module that defines `router`'s class."""
    import sys
    return sys.modules[type(router).__module__].__file__


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


class LTXStreamPrepare116:
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


class LTXStreamAnchor116:
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


class LTXStreamCondition116:
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


class LTXStreamLatentAnchor116:
    """Latent anchor provider (LTX_ANCHOR=latent or mixed): (stage-A anchor, stage-B anchor); mixed uses
    only the stage-A anchor."""
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


class LTXStreamLatentCondition116:
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


class LTXStreamFrameConditionB116:
    """Mixed anchor, stage B: native LTXVImgToVideoInplace on the predecessor's decoded last frame,
    after waiting (bounded) for its decode record."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'vae': ('VAE',), 'latent': ('LATENT',), 'strength': ('FLOAT', {'default': 1.0}),
                             'bypass': ('BOOLEAN', {'default': False}), 'run_name': ('STRING',)}}
    RETURN_TYPES = ('LATENT',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, vae, latent, strength, bypass, run_name):
        return _ctx().mixed_condition_b(vae, latent, strength, bypass, run_name)


class LTXStreamGuideAnchor116:
    """Guide anchor provider (LTX_ANCHOR=guide): (stage-A guide, stage-B guide), two latent slots each."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING',), 'predecessor_anchor_sha256': ('STRING',)}}
    RETURN_TYPES = ('LATENT', 'LATENT')
    RETURN_NAMES = ('guide_a', 'guide_b')
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def apply(self, run_name, predecessor_anchor_sha256):
        return _ctx().provide_guide_anchor(run_name, predecessor_anchor_sha256)


class LTXStreamGuide116:
    """Native LTXVAddLatentGuide at latent index -2, strength 1.0, through the guide guard."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'positive': ('CONDITIONING',), 'negative': ('CONDITIONING',), 'vae': ('VAE',),
                             'latent': ('LATENT',), 'guide': ('LATENT',), 'strength': ('FLOAT', {'default': 1.0}),
                             'run_name': ('STRING',), 'stage': (['A', 'B'],)}}
    RETURN_TYPES = ('CONDITIONING', 'CONDITIONING', 'LATENT')
    RETURN_NAMES = ('positive', 'negative', 'latent')
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, positive, negative, vae, latent, guide, strength, run_name, stage):
        return tuple(_ctx().guide(positive, negative, vae, latent, guide, strength, run_name, stage))


class LTXStreamCropGuides116:
    """Native LTXVCropGuides after a guided sampler, through the guide guard (records the guide pin)."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'positive': ('CONDITIONING',), 'negative': ('CONDITIONING',), 'latent': ('LATENT',),
                             'run_name': ('STRING',), 'stage': (['A', 'B'],)}}
    RETURN_TYPES = ('CONDITIONING', 'CONDITIONING', 'LATENT')
    RETURN_NAMES = ('positive', 'negative', 'latent')
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, positive, negative, latent, run_name, stage):
        return tuple(_ctx().crop(positive, negative, latent, run_name, stage))


class LTXStreamText116:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING',), 'text': ('STRING', {'multiline': True})},
                'optional': {'conditioning': ('CONDITIONING',)}}
    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, run_name, text, conditioning=None):
        return (_ctx().text(run_name, text, conditioning),)


class LTXStreamChunk116:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'video_latent': ('LATENT',), 'audio_latent': ('LATENT',),
            'stage_a_latent': ('LATENT',), 'vae': ('VAE',), 'audio_vae': ('VAE',),
            'run_name': ('STRING',), 'kind': (list(contract.KINDS),),
            'frames': ('INT', {'min': 49, 'max': 169}), 'placement': (sorted(contract.PLACEMENTS),),
            'anchor': (list(contract.ANCHORS),),
            'decoder_graph': ('INT', {'min': 0, 'max': 1}),
            'anchor_decode': (list(contract.ANCHOR_DECODE_CHOICES),),
            'bencode_overlap': ('INT', {'min': 0, 'max': 1}), 'prep_ahead': ('INT', {'min': 0, 'max': 1}),
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
              anchor, decoder_graph, anchor_decode, bencode_overlap, prep_ahead, scene_id, chunk_index, seed,
              stream_seq, predecessor_anchor_sha256, reuse_text, reset=0):
        fields = {'kind': kind, 'frames': frames, 'placement': placement, 'anchor': anchor,
                  'decoder_graph': decoder_graph, 'anchor_decode': anchor_decode,
                  'bencode_overlap': bencode_overlap, 'prep_ahead': prep_ahead, 'scene_id': scene_id,
                  'chunk_index': chunk_index, 'seed': seed,
                  'stream_seq': stream_seq, 'predecessor_anchor_sha256': predecessor_anchor_sha256,
                  'reuse_text': reuse_text, 'reset': reset}
        return _ctx().output(run_name, video_latent, audio_latent, stage_a_latent, vae, audio_vae, fields)


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in (LTXStreamPrepare116, LTXStreamAnchor116,
    LTXStreamCondition116, LTXStreamLatentAnchor116, LTXStreamLatentCondition116, LTXStreamFrameConditionB116,
    LTXStreamGuideAnchor116, LTXStreamGuide116, LTXStreamCropGuides116, LTXStreamText116,
    LTXStreamChunk116)}


def install(packet, manifest, manifest_sha, run):
    global _CTX
    if _CTX is not None:
        raise RuntimeError('Stream runtime already installed')
    import execution
    import executor_guard
    _CTX = Runtime(packet, manifest, manifest_sha, run)
    result = executor_guard.install(execution.PromptExecutor, _CTX.authority,
                                    _CTX.before_request, _CTX.after_request, _CTX.on_failure)
    result['packet123_timing'] = install_executor_timing(execution.PromptExecutor, _CTX)
    _CTX.write('stream-executor-guard.json', result)


def install_executor_timing(executor_class, ctx):
    """Packet123 (measurement only): an outer wrapper of the guarded execute_async that records when the prompt
    worker entered and left it (the turnaround split needs the executor's exit after the success message)."""
    import functools
    guarded = executor_class.execute_async
    if getattr(guarded, '_ltx118_timing', False) or not getattr(executor_class, '_resolution_guard_installed', False):
        raise RuntimeError('Executor timing needs the resolution guard installed exactly once')

    @functools.wraps(guarded)
    async def timed(self, prompt, prompt_id, extra_data=None, execute_outputs=None):
        marks = {'entry': time.time_ns(), 'exit': None}
        ctx.exec_marks[prompt_id] = marks
        try:
            return await guarded(self, prompt, prompt_id, extra_data, execute_outputs)
        finally:
            marks['exit'] = time.time_ns()
    timed._ltx118_timing = True
    executor_class.execute_async = timed
    return {'installed': True, 'wraps': getattr(guarded, '__qualname__', None), 'behavior': 'timestamps only'}


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
            received = time.time_ns()      # packet123: before the body is read
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
            marks = {'admission_received': received, 'precheck_done': time.time_ns(), 'queued': None}
            ctx.admission_marks[prompt_id] = marks
            while len(ctx.submit_ns) > 16:
                ctx.submit_ns.pop(next(iter(ctx.submit_ns)))
            _bound(ctx.admission_marks, keep=16)
            response = await handler(request)
            marks['queued'] = time.time_ns()  # POST handler return, not the queue's actual put
            if getattr(response, 'status', 200) != 200:
                ctx.submit_ns.pop(prompt_id, None)
                ctx.admission_marks.pop(prompt_id, None)
            return response
        return await handler(request)
    server.app.middlewares.append(admission)

    @server.routes.get('/ltx-stream/status')
    async def status(request):
        started = time.perf_counter()        # packet123: the status route's own cost (measurement only)
        if ctx.action_busy:
            return web.json_response({'error': {'code': 'busy', 'message': 'action active'}}, status=409)
        result = ctx.authority.status()
        result.update(server_identity_sha256=ctx.identity_sha, runtime_manifest_sha256=ctx.manifest_sha,
                      plan_sha256=ctx.session.PLAN_SHA256, qualification_id=ctx.authority.qid, frames=ctx.frames,
                      anchor=ctx.anchor, decoder_graph=ctx.decoder_graph_flag,
                      anchor_decode=ctx.anchor_decode, bencode_overlap=ctx.bencode_overlap, prep_ahead=ctx.prep_ahead,
                      snapshot_mode=ctx.snapshot_mode, decoder_graph_pool_cap_bytes=ctx.pool_cap,
                      display_device=ctx.display_device,
                      display_schedule=ctx.display_schedule, anchor_read_ahead=ctx.anchor_read_ahead,
                      snapshot_schedule=ctx.snapshot_schedule,
                      fault=ctx.fault(), receipt_dir=str(ctx.run / 'receipts'),
                      qualified_text_windows=None if ctx.qualified_windows is None else sorted(ctx.qualified_windows),
                      output_directory=str(ctx.root / 'output'), packet=contract.PACKET,
                      features={'latent_anchor': ctx.anchor == 'latent', 'mixed_anchor': ctx.anchor == 'mixed',
                                'guide_anchor': ctx.anchor == 'guide', 'decode_thread': True,
                                'async_preview': True, 'chain_reset': True, 'anchor_diagnostics': True,
                                'sharpness_diagnostic': True, 'chunk_length_choice': True,
                                'text_reuse_default_on': True,
                                'frame_anchor': ctx.anchor == 'frame', 'video_first_handoff': True,
                                'decoder_graph': ctx.decoder_graph_flag == 1,
                                'cone_anchor_decode': ctx.anchor_decode == 'cone',
                                'bencode_overlap': ctx.bencode_overlap == 1, 'prep_ahead': ctx.prep_ahead == 1,
                                'chunk_121': True, 'chunk_145': True, 'chunk_169': True, 'atomic_preview': True, 'timing_split': True,
                                'snapshot_fingerprint': ctx.snapshot_mode == 'fingerprint',
                                'decoder_graph_pool_cap': ctx.pool_cap is not None},
                      decoder_graph_state=(None if ctx.decoder_graph is None else
                                           {k: v for k, v in ctx.decoder_graph.receipt().items() if k != 'captures'}),
                      anchor_decode_state=None if ctx.cone is None else ctx.cone.receipt(),
                      precompute_state=ctx.precompute.summary(),
                      snapshot_state=None if ctx.inspector is None else ctx.inspector.summary(),
                      display_worker=ctx.display_worker,
                      decode_worker=ctx.decoder.summary(), preview_writer=ctx.preview.summary())
        result.update(ctx.server_options)  # Includes an explicitly selected replica reserve.
        try:
            result['storage'] = ctx.storage_check(mutate=False)
        except RuntimeError as error:
            result['storage'] = {'refused': str(error)}
        response = web.json_response(result)
        ctx.note_status_route(time.perf_counter() - started)
        return response

    def record_route(prefix, *workers):
        async def route(request):
            name = request.match_info['run_name']
            if not RUN_NAME_RE.fullmatch(name):
                return refuse('contract', 'Invalid run name', 400)
            path = ctx.run / 'receipts' / (prefix + name + '.json')
            if not path.is_file():
                if prefix == 'receipt-':
                    ctx.receipt_polls[name] = ctx.receipt_polls.get(name, 0) + 1
                    _bound(ctx.receipt_served, ctx.receipt_polls)
                # A record that can no longer come: its own worker or one upstream of it failed.
                for worker in workers:
                    if worker.failed is not None:
                        return refuse('halted', '%s failed: %s' % (worker.name if hasattr(worker, 'name') else
                                                                  'preview writer', worker.failed[:500]), 503)
                return refuse('not-found', 'No committed %s record for %s' % (prefix.rstrip('-'), name), 404)
            raw = (await stream_preview.read_preview_record(
                ctx.session, path, writer_complete=lambda: ctx.preview.record(name) is not None)
                if prefix == 'preview-' else ctx.session.read_regular(path))
            response = web.Response(body=raw, content_type='application/json')
            if prefix == 'receipt-':
                # first_served means successfully read and HTTP 200 constructed, not bytes delivered.
                # The file may be visible before its writer's fsync; retain negative commit intervals.
                ctx.receipt_served.setdefault(name, time.time_ns())
                _bound(ctx.receipt_served, ctx.receipt_polls)
            return response
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

"""Sample clip N while clips N-1 and N-2 are still moving through the pipeline.

The transformer's 48 blocks are split 21/27 across xpu:0 and xpu:1, so a single
clip's forward uses one card at a time and leaves the other idle. Diffusion is
sequential *within* a clip but not *between* clips, so two clips sampling at
once let one occupy xpu:1's blocks while the other occupies xpu:0's. The GPU
serialises each card by itself, so two workers settle into a two-stage pipeline.

This is run-behind, not run-ahead: the sampler needs THIS clip's conditioning,
which only exists once this prompt has it. So the prompt submits its own clip's
sampling and emits the clip sampled `depth` prompts earlier. Every clip is
sampled exactly once, by its own sampler, from its own conditioning and its own
noise; nothing is cached or shared between clips. Only the overlap changes.

Each worker thread gets its own static buffers and captured graphs
(`ltx_graph_capture.GroupRegistry` keys them by (device, thread)), which is what
makes two concurrent forwards safe.

One more shared thing: the initial noise. `comfy.sample.prepare_noise` seeds
the GLOBAL CPU generator (`torch.manual_seed(seed)`) and then draws from it.
Two sampler threads interleaving seed and draw would hand one clip the other
clip's noise. With equal seeds that is invisible; with distinct seeds it
corrupts a clip. Every `Noise` handed to the sampler here is wrapped so
`generate_noise` runs under one process-wide lock. Same generator sequence,
never interleaved: bit-identical by construction.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import ltx_pipeline as pipeline
import ltx_gil_probe as gil
import ltx_lean_conditioning as lean
from encoder_diagnostics import _context

gil.start_probe()   # packet 92a lock-wait probe (idempotent, never raises)

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
# Packet 93: 'pipeline-lean' = 'pipeline' plus the per-clip connector memo
# (ltx_lean_conditioning; exact by construction, off unless requested).
SAMPLER_MODES = pipeline.MODES + ('pipeline-lean',)
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


_ACTIVE = [0]
_ACTIVE_LOCK = __import__('threading').Lock()
_PINNED = {}
_NOISE_LOCK = __import__('threading').Lock()
_PHASE_MARKS = {}


class _SerialisedNoise:
    """A Noise whose generate_noise cannot interleave with another thread's."""

    def __init__(self, inner):
        self.inner = inner
        self.seed = getattr(inner, 'seed', 0)

    def generate_noise(self, input_latent):
        with _NOISE_LOCK:
            return self.inner.generate_noise(input_latent)


def pin_current_patcher(base_model):
    """Stop a finishing sampler from clearing `current_patcher` under a running one.

    `comfy.model_base.BaseModel.current_patcher` is a plain attribute on the ONE
    shared model object, set at the start of a sample and set back to None at the
    end (model_patcher.py:1394). With two clips sampling at once, the first to
    finish clears it while the second is mid-forward, which fails as
    "'NoneType' object has no attribute 'prepare_state'".

    Both concurrent samplers use the same patcher -- there is one model in the
    graph -- so holding the attribute at that patcher while any sampler is active
    is inert: every read that mattered already returned this value. Assignments
    of a real patcher are honoured as normal; only the None clear is deferred
    until the last sampler leaves. Asserted on every entry, and the four raw
    oracles gate the result either way.
    """
    cls = type(base_model)
    if cls in _PINNED:
        return
    store = {}
    previous = base_model.__dict__.pop('current_patcher', None)
    if previous is not None:
        store[id(base_model)] = previous

    def getter(self):
        return store.get(id(self))

    def setter(self, value):
        if value is None and _ACTIVE[0] > 0:
            return
        store[id(self)] = value

    cls.current_patcher = property(getter, setter)
    _PINNED[cls] = store


class _Active:
    """Counts samplers in flight, so the pin knows when the last one leaves."""

    def __enter__(self):
        with _ACTIVE_LOCK:
            _ACTIVE[0] += 1
        return self

    def __exit__(self, *exc):
        with _ACTIVE_LOCK:
            _ACTIVE[0] -= 1
        return False


def stall_overlaps(path, start, end):
    """Known host stalls (launcher's host-stalls.jsonl) whose window overlaps [start, end]."""
    out = []
    p = Path(path)
    if not p.is_file():
        return out
    for line in p.read_text().splitlines():
        try:
            e = json.loads(line)
            a, b = e['window_unix']
        except (ValueError, KeyError, TypeError):
            continue
        if a <= end and b >= start:
            out.append({'window_unix': [a, b], 'duration_s': e.get('duration_s')})
    return out


def placement_devices(guider):
    """Devices of a multi-segment placement (packet 94); empty for two-way."""
    try:
        identity = guider.model_patcher.model.diffusion_model._ltx_layer_shard_identity
    except AttributeError:
        return []
    return list(identity.get('devices') or []) if identity.get('segments') else []


MEMORY_FLOOR_GIB = 2.0
_FREEZE_DEVICES = [None]     # transformer segment devices seen by the sampler (packet 94c)
MEMORY_FLOOR_BYTES = int(MEMORY_FLOOR_GIB * 2**30)


class SerialPassRequired(RuntimeError):
    """Packet 94b: before the freeze a pipelined sampler request must run alone (the
    serial capture pass). Refused with a receipt; does not latch."""


def expected_residents(segment_devices):
    """Packet 94c: what must be resident (model type, card) at the freeze. Two-way:
    segment_devices = ['xpu:0', 'xpu:1']."""
    want = {('LTXAV', 'xpu:0'), ('LatentUpsampler', 'xpu:0'), ('LTXAVTEModel_', 'xpu:2'),
            ('_TextShard', 'xpu:3'), ('CausalDiffusionVAE', 'xpu:3'), ('AudioVAE', 'xpu:3')}
    want |= {('_Shard', d) for d in segment_devices[1:]}
    return want


def residents_missing(resident, segment_devices):
    have = {(t, d) for t, d, nbytes in resident if nbytes > 0}
    return sorted(expected_residents(segment_devices) - have)


def freeze_verdict(free_bytes, busy, coverage_ok=True, floor_bytes=MEMORY_FLOOR_BYTES, missing=()):
    """Packet 94/94b/94c admission for timed arms: pipeline idle, every sampler signature
    captured on both workers, every expected model resident on its card, every card
    at or above the floor (raw bytes)."""
    if busy:
        return False, 'pipeline-busy'
    if not coverage_ok:
        return False, 'captures-incomplete'
    if missing:
        return False, 'residents-missing'
    short = {d: v for d, v in free_bytes.items() if v is None or v < floor_bytes}
    if short:
        return False, 'memory-floor'
    return True, 'frozen'


def serial_admission(frozen, busy, pending_prompts):
    """Before the freeze only one request may be in the server (no lookahead, no
    decode-behind, no second sampler worker busy). After it, pipelining is free."""
    if frozen:
        return True, None
    if busy:
        return False, 'pipeline jobs still running (%d)' % busy
    if pending_prompts:
        return False, '%d other prompts queued' % pending_prompts
    return True, None


def resident_set():
    """(model type, device, loaded bytes) of every model ComfyUI holds."""
    import comfy.model_management as _mm
    return sorted((type(getattr(lm.model, 'model', lm.model)).__name__, str(lm.device), int(lm.model.loaded_size()))
                  for lm in list(_mm.current_loaded_models))


def _pending_prompts():
    try:
        import server
        _running, queued = server.PromptServer.instance.prompt_queue.get_current_queue_volatile()
        return len(queued)
    except Exception:  # noqa: BLE001
        return 0


def _sample_worker_idents():
    st = getattr(pipeline, '_STAGES', {}).get('sample', {})
    return [w.ident for w in st.get('workers', []) if w.is_alive()]


class LTXSamplerCaptureFreeze:
    """Packet 94/94b: after the serial capture pass, check that every sampler block
    signature was captured on both sampler workers and that every card keeps the
    2 GiB floor, then freeze captures AND model loads so timed arms only replay on
    resident weights. Records the resident models and free memory per card. Never
    latches; a refusal is a recorded outcome."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, run_name):
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        import ltx_graph_capture as capture
        free = {}
        for i in range(torch.xpu.device_count()):
            try:
                free['xpu:%d' % i] = int(torch.xpu.mem_get_info(i)[0])
            except Exception:  # noqa: BLE001
                free['xpu:%d' % i] = None
        coverage_ok, coverage = capture.capture_coverage(_sample_worker_idents())
        resident = resident_set()
        devices = _FREEZE_DEVICES[0] or ['xpu:0', 'xpu:1']
        missing = residents_missing(resident, devices)
        ok, outcome = freeze_verdict(free, pipeline.busy(), coverage_ok, missing=missing)
        if ok:
            capture.CAPTURES_FROZEN[0] = True
            capture.LOADS_FROZEN[0] = True
            capture.RESIDENT_SNAPSHOT[0] = resident
        report = {'schema': 'ltx.sampler-capture-freeze.v2', **identity, 'run_name': run_name,
                  'outcome': outcome, 'frozen': bool(capture.CAPTURES_FROZEN[0]),
                  'loads_frozen': bool(capture.LOADS_FROZEN[0]), 'coverage': coverage,
                  'free_bytes': free,
                  'free_gib': {d: (None if v is None else round(v / 2**30, 3)) for d, v in free.items()},
                  'floor_bytes': MEMORY_FLOOR_BYTES,
                  'reserved_gib': {'xpu:%d' % i: round(torch.xpu.memory_reserved(i) / 2**30, 3)
                                   for i in range(torch.xpu.device_count())},
                  'resident_models': [list(r) for r in resident],
                  'residents_missing': [list(m) for m in missing], 'segment_devices': devices,
                  'placement': __import__('os').environ.get('LTX_SAMPLER_PLACEMENT', 'two-way')}
        write_json(run / ('sampler-capture-freeze-' + run_name + '.json'), report)
        return {'ui': {'text': ['capture freeze: %s' % outcome]}}


class LTXSamplerCaptureCoverage:
    """Packet 94c: report (never change) whether the serial capture pass has captured
    every sampler block signature on both workers. Lets the runner finish the capture
    pass, then build the decode replica, before the one freeze."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, run_name):
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        import ltx_graph_capture as capture
        ok, coverage = capture.capture_coverage(_sample_worker_idents())
        busy = pipeline.busy()
        executing = pipeline.running()
        outcome = 'covered' if ok and not busy else ('pipeline-busy' if busy else 'captures-incomplete')
        # Packet 94f: also the read-only quiescence evidence the runner uses after a
        # failed arm (queued/unfinished jobs and jobs executing on workers).
        write_json(run / ('sampler-capture-coverage-' + run_name + '.json'),
                   {'schema': 'ltx.sampler-capture-coverage.v2', **identity, 'run_name': run_name,
                    'outcome': outcome, 'coverage': coverage, 'frozen': bool(capture.CAPTURES_FROZEN[0]),
                    'pipeline_busy': busy, 'pipeline_running': executing, 'time': time.time()})
        return {'ui': {'text': ['capture coverage: %s' % outcome]}}


def _node(name):
    import nodes
    cls = nodes.NODE_CLASS_MAPPINGS.get(name)
    require(cls is not None, 'Missing node class: ' + name)
    return cls


def sample_clip_original(noise_a, guider_a, sampler_a, sigmas_a,
                         noise_b, guider_b, sampler_b, sigmas_b,
                         video_latent, audio_latent, upscale_model, vae):
    """The sealed chain on the prompt thread, default streams, no staging."""
    return _sample_chain(_node('LTXVConcatAVLatent'), _node('LTXVSeparateAVLatent'),
                         _node('LTXVLatentUpsampler'), _node('SamplerCustomAdvanced'),
                         noise_a, guider_a, sampler_a, sigmas_a,
                         noise_b, guider_b, sampler_b, sigmas_b,
                         video_latent, audio_latent, upscale_model, vae)


def sample_clip(clip_index, noise_a, guider_a, sampler_a, sigmas_a,
                noise_b, guider_b, sampler_b, sigmas_b,
                video_latent, audio_latent, upscale_model, vae, lean_mode=False):
    """Exactly the sealed chain 377 -> 344 -> 367 -> 348 -> 340 -> 368 -> 369."""
    concat = _node('LTXVConcatAVLatent')
    separate = _node('LTXVSeparateAVLatent')
    upsampler = _node('LTXVLatentUpsampler')
    sampler_node = _node('SamplerCustomAdvanced')

    import ltx_graph_capture as capture
    capture.set_pipelined(True)
    # Fingerprint what this clip is about to be sampled FROM, on this worker
    # thread at execution time: the guider conditionings, the two noise seeds
    # and the input latents. The encode stage fingerprinted the conditioning
    # at its handoff; if this clip later fails the oracle, the pair of
    # fingerprints says whether the conditioning mutated in flight or the
    # sampler itself left the expected path.
    pipeline.record_fingerprint(('sample-inputs', clip_index), {
        'guider_a_conds': pipeline.cond_fingerprint(getattr(guider_a, 'original_conds', None)),
        'guider_b_conds': pipeline.cond_fingerprint(getattr(guider_b, 'original_conds', None)),
        'noise_seeds': [getattr(noise_a, 'seed', None), getattr(noise_b, 'seed', None)],
        'video_latent': pipeline.cond_fingerprint(video_latent),
        'audio_latent': pipeline.cond_fingerprint(audio_latent),
    })
    # This thread owns one clip: everything it issues goes to its own streams
    # on both shard cards (probe 5: the overlap needs per-clip streams and
    # staged cross-card moves; shared default streams fence the clips).
    streams = [capture.thread_stream(torch.device('xpu', i)) for i in range(2)]
    # Packet 94: a multi-segment placement also runs blocks on other cards; their
    # thread streams are drained with these at the end (two-way: none).
    extra_streams = [capture.thread_stream(torch.device(d)) for d in placement_devices(guider_a)
                     if d not in ('xpu:0', 'xpu:1')]
    # Packet 93: per-clip context for the context-hash sentry (every pipelined
    # arm) and, under 'pipeline-lean' only, the connector memo.
    lean.begin_clip(clip_index, lean_mode)
    try:
        with _Active(), torch.xpu.stream(streams[0]):
            torch.xpu.set_stream(streams[1])
            result = _sample_chain(clip_index, streams,
                                   concat, separate, upsampler, sampler_node,
                                   _SerialisedNoise(noise_a), guider_a, sampler_a, sigmas_a,
                                   _SerialisedNoise(noise_b), guider_b, sampler_b, sigmas_b,
                                   video_latent, audio_latent, upscale_model, vae)
    finally:
        for st in streams + extra_streams:
            st.synchronize()
        capture.set_pipelined(False)
        pipeline.record_fingerprint(('context-sentry', clip_index), lean.end_clip())
        marks = _PHASE_MARKS.pop(clip_index, None)
        if marks is not None:
            phases = {}
            for (name, t0, ev0), (next_name, t1, ev1) in zip(marks, marks[1:]):
                phases[name + '->' + next_name] = {
                    'cpu_s': round(t1 - t0, 4),
                    'xpu0_ms': round(ev0[0].elapsed_time(ev1[0]), 2),
                    'xpu1_ms': round(ev0[1].elapsed_time(ev1[1]), 2)}
            pipeline.record_fingerprint(('phases', clip_index), phases)
    # Packet 90 sentry: scan and hash the finished latents on the worker, after
    # this clip's streams have drained. The collect side of run_behind reads
    # the same tensors and compares; equal sha256s at both ends exonerate the
    # handoff, a byte change in transit convicts it, and a NaN here convicts
    # the graph itself (the f80/f81/f82b/f88/f89 wrong-clip class).
    video_b, audio_b = result
    v_s, a_s = video_b['samples'], audio_b['samples']
    sentry = {'video_finite': bool(torch.isfinite(v_s).all().item()),
              'audio_finite': bool(torch.isfinite(a_s).all().item()),
              'video_ptr': int(v_s.data_ptr()), 'audio_ptr': int(a_s.data_ptr())}
    for key, tensor in (('video', v_s), ('audio', a_s)):
        sentry[key + '_sha256'] = (hashlib.sha256(tensor.detach().to('cpu', copy=True)
                                                  .view(torch.uint8).numpy().tobytes()).hexdigest()
                                   if sentry[key + '_finite'] else None)
    pipeline.record_fingerprint(('sample-output', clip_index), sentry)
    done_marker('sample', clip_index, {'finite': sentry['video_finite'] and sentry['audio_finite']})
    return result

def _sample_chain(clip_index, streams,
                  concat, separate, upsampler, sampler_node,
                  noise_a, guider_a, sampler_a, sigmas_a,
                  noise_b, guider_b, sampler_b, sigmas_b,
                  video_latent, audio_latent, upscale_model, vae):
    # GPU-timeline phase marks: a timing event on each of this worker's two
    # streams at every chain boundary, plus a CPU timestamp. Events never
    # block submission, so the overlap is undisturbed; the elapsed times are
    # read in sample_clip's finally block, after the streams drain.
    import time
    marks = []

    def mark(name):
        events = []
        for st in streams:
            ev = torch.xpu.Event(enable_timing=True)
            ev.record(st)
            events.append(ev)
        marks.append((name, time.perf_counter(), events))

    mark('start')
    av = concat.execute(video_latent=video_latent, audio_latent=audio_latent).result[0]
    mark('concat_a')
    lean.set_stage('a')
    stage_a = sampler_node.execute(noise=noise_a, guider=guider_a, sampler=sampler_a,
                                   sigmas=sigmas_a, latent_image=av).result[0]
    mark('sample_a')
    video_a, audio_a = separate.execute(av_latent=stage_a).result[:2]
    mark('separate_a')
    upscaled = upsampler.execute(samples=video_a, upscale_model=upscale_model, vae=vae).result[0]
    mark('upsample')
    av2 = concat.execute(video_latent=upscaled, audio_latent=audio_a).result[0]
    mark('concat_b')
    lean.set_stage('b')
    stage_b = sampler_node.execute(noise=noise_b, guider=guider_b, sampler=sampler_b,
                                   sigmas=sigmas_b, latent_image=av2).result[0]
    mark('sample_b')
    video_b, audio_b = separate.execute(av_latent=stage_b).result[:2]
    mark('separate_b')
    _PHASE_MARKS[clip_index] = marks
    return video_b, audio_b


class LTXPipelineSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'noise_a': ('NOISE',), 'guider_a': ('GUIDER',), 'sampler_a': ('SAMPLER',),
            'sigmas_a': ('SIGMAS',),
            'noise_b': ('NOISE',), 'guider_b': ('GUIDER',), 'sampler_b': ('SAMPLER',),
            'sigmas_b': ('SIGMAS',),
            'video_latent': ('LATENT',), 'audio_latent': ('LATENT',),
            'upscale_model': ('LATENT_UPSCALE_MODEL',), 'vae': ('VAE',),
            'mode': (list(SAMPLER_MODES),),
            'clip_index': ('INT', {'default': 0, 'min': 0, 'max': 1000000}),
            'depth': ('INT', {'default': 2, 'min': 1, 'max': pipeline.MAX_PENDING}),
            'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('LATENT', 'LATENT', 'INT')
    RETURN_NAMES = ('video_latent', 'audio_latent', 'emitted_index')
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, **kwargs):
        global _failed
        try:
            return self._apply(**kwargs)
        except SerialPassRequired:
            raise
        except BaseException:
            _failed = True
            gil.restore_default('latched failure: pipeline-sampler-')
            pipeline.clear()
            raise

    def _apply(self, mode, clip_index, depth, run_name, **chain):
        require(not _failed, 'Previous pipeline failure; halt submissions and inspect evidence')
        require(mode in SAMPLER_MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        actual = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        require(server['extension_sha256s']['pipeline_sampler_node.py'] == actual,
                'Sealed extension changed: pipeline_sampler_node.py')
        lean_sha = hashlib.sha256(Path(lean.__file__).read_bytes()).hexdigest()
        require(server['extension_sha256s']['ltx_lean_conditioning.py'] == lean_sha,
                'Sealed extension changed: ltx_lean_conditioning.py')
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(),
                'Strict determinism required')

        if mode != 'original':
            # Packet 94b: before the freeze, a pipelined request must be alone in the
            # server, so a sampler capture can never overlap encode or decode work.
            import ltx_graph_capture as _cap
            admitted, why = serial_admission(_cap.CAPTURES_FROZEN[0], pipeline.busy(), _pending_prompts())
            if not admitted:
                refusal = {'schema': 'ltx.pipeline-sampler-request.v1', **identity, 'run_name': run_name,
                           'mode': mode, 'clip_index': clip_index, 'passed': False,
                           'refused': 'serial capture pass required before the freeze: ' + why}
                write_json(run / ('pipeline-sampler-' + run_name + '.json'), refusal)
                raise SerialPassRequired(refusal['refused'])
        report = {'schema': 'ltx.pipeline-sampler-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'clip_index': clip_index, 'depth': depth,
                  'extension_sha256s': {'pipeline_sampler_node.py': actual,
                                        'ltx_lean_conditioning.py': lean_sha},
                  'claim': 'every clip is sampled exactly once by its own sampler, from its own '
                           'conditioning and its own noise; nothing is cached or shared between '
                           'clips. Two clips sample at once so one occupies xpu:1 while the other '
                           'occupies xpu:0. Each worker has its own static buffers and graphs; '
                           'initial-noise generation is serialised so the global CPU generator '
                           'cannot interleave between clips.',
                  'passed': False}
        started = time.monotonic()
        gil.mark_lane_thread('prompt')
        apply_cpu0 = time.thread_time()   # packet 92a
        try:
            if mode != 'original':
                patcher = getattr(chain['guider_a'], 'model_patcher', None)
                require(patcher is not None, 'Guider has no model patcher to pin')
                require(getattr(chain['guider_b'], 'model_patcher', None) is patcher,
                        'The two sampler stages use different patchers; pinning would be unsound')
                pin_current_patcher(patcher.model)
                # Packet 93: the context sentry on every pipelined arm; the
                # memo shadow only from the first lean request on (a control
                # arm run before it never sees the shadow).
                report['sentry_installed_now'] = lean.install_sentry(patcher.model.diffusion_model)
                _FREEZE_DEVICES[0] = placement_devices(chain['guider_a']) or ['xpu:0', 'xpu:1']
                if mode == 'pipeline-lean':
                    report['lean'] = {'memo_installed_now': lean.install_memo(patcher.model.diffusion_model),
                                      'claim': 'connector pass computed once per clip and reused only for '
                                               'byte-identical inputs (asserted); the negative, identical '
                                               'to the positive and unused at cfg 1, is served the same way'}
            if mode == 'original':
                with torch.inference_mode():
                    out = sample_clip_original(**chain)
                report['detail'] = {'emitted_index': clip_index, 'primed': True}
                emitted = clip_index
            else:
                lean_mode = mode == 'pipeline-lean'
                out, detail = pipeline.run_behind(
                    'sample', clip_index, depth,
                    lambda: sample_clip(clip_index, lean_mode=lean_mode, **chain))
                # The worker fingerprints the clip's actual sample inputs at
                # execution time; tie the emitted clip's pair to this receipt,
                # together with the conditioning fingerprint the encode stage
                # recorded for it, so a wrong clip attributes itself to a stage.
                detail['submitted_noise_seeds'] = [
                    getattr(chain['noise_a'], 'seed', None), getattr(chain['noise_b'], 'seed', None)]
                report['detail'] = detail
                emitted = detail['emitted_index']
                if out is not None:
                    detail['emitted_sample_inputs'] = pipeline.fingerprint(('sample-inputs', emitted))
                    detail['emitted_conditioning_fingerprint'] = pipeline.fingerprint(('encode', emitted))
                    detail['emitted_phases'] = pipeline.fingerprint(('phases', emitted))
                    detail['emitted_context_sentry'] = pipeline.fingerprint(('context-sentry', emitted))
                    # Packet 90: compare the emitted clip's bytes against the
                    # worker-side sentry recorded when its streams drained. A
                    # change between the two reads is in-transit corruption
                    # (pool alias, in-place overwrite); equal bytes move any
                    # later oracle failure downstream of this node.
                    sentry = pipeline.fingerprint(('sample-output', emitted))
                    detail['emitted_sample_output'] = sentry
                    require(sentry is not None, 'Sample-output sentry missing for clip %d' % emitted)
                    require(sentry['video_finite'] and sentry['audio_finite'],
                            'Sample worker produced nonfinite latents for clip %d: %s' % (emitted, sentry))
                    v_s, a_s = out[0]['samples'], out[1]['samples']
                    require(bool(torch.isfinite(v_s).all().item()) and
                            bool(torch.isfinite(a_s).all().item()),
                            'Nonfinite latents at sampler collect for clip %d (worker-side was finite)' % emitted)
                    v_sha = hashlib.sha256(v_s.detach().to('cpu', copy=True)
                                           .view(torch.uint8).numpy().tobytes()).hexdigest()
                    a_sha = hashlib.sha256(a_s.detach().to('cpu', copy=True)
                                           .view(torch.uint8).numpy().tobytes()).hexdigest()
                    require(v_sha == sentry['video_sha256'] and a_sha == sentry['audio_sha256'],
                            'Sampler handoff corrupted clip %d: worker %s/%s vs collect %s/%s'
                            % (emitted, sentry['video_sha256'][:12], sentry['audio_sha256'][:12],
                               v_sha[:12], a_sha[:12]))
                if out is None:
                    # Fill: nothing to emit yet. Placeholder latents of the
                    # input shapes; the decode stage treats index -1 as a fill.
                    out = ({**chain['video_latent'], 'samples': torch.zeros_like(chain['video_latent']['samples'])},
                           {**chain['audio_latent'], 'samples': torch.zeros_like(chain['audio_latent']['samples'])})
            report['memory'] = {f'xpu:{i}': {'allocated_bytes': int(torch.xpu.memory_allocated(i)),
                                           'reserved_bytes': int(torch.xpu.memory_reserved(i))}
                                for i in range(torch.xpu.device_count())}
            try:
                import ltx_graph_capture as _capture
                report['route_busy_ms'] = _capture.busy_window_report()
            except Exception as error:  # noqa: BLE001  (diagnostic only)
                report['route_busy_ms'] = 'unavailable: ' + repr(error)
            import ltx_graph_capture as _cap2
            if _cap2.RESIDENT_SNAPSHOT[0] is not None:
                # Packet 94b: after the freeze the resident models never change.
                now = resident_set()
                report['resident_unchanged'] = now == _cap2.RESIDENT_SNAPSHOT[0]
                require(report['resident_unchanged'], 'Resident models changed since the freeze: %s vs %s'
                        % (now, _cap2.RESIDENT_SNAPSHOT[0]))
            try:
                import comfy.model_management as _mm
                report['loaded_models'] = [
                    {'model': type(getattr(lm.model, 'model', lm.model)).__name__, 'device': str(lm.device),
                     'loaded_bytes': int(lm.model.loaded_size()), 'currently_used': bool(lm.currently_used)}
                    for lm in list(_mm.current_loaded_models)]
            except Exception as error:  # noqa: BLE001  (diagnostic only)
                report['loaded_models'] = 'unavailable: ' + repr(error)
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            report['written_unix'] = time.time()  # packet 90b: occupancy wall for analyze-phases
            try:  # packet 94d: mark a request that overlapped a known host stall (evidence only)
                marks = stall_overlaps(run / 'host-stalls.jsonl', report['written_unix'] - report['seconds'],
                                       report['written_unix'])
                if marks:
                    report['host_stall'] = marks
            except Exception:  # noqa: BLE001
                pass
            try:  # packet 92a: diagnostic only, never fails the clip
                report['apply_cpu_seconds'] = round(time.thread_time() - apply_cpu0, 4)
                report['gil'] = gil.report(drain=True)
            except Exception as error:  # noqa: BLE001
                report['gil'] = 'unavailable: ' + repr(error)[:200]
            write_json(run / ('pipeline-sampler-' + run_name + '.json'), report)
        return (out[0], out[1], emitted)


NODE_CLASS_MAPPINGS = {'LTXPipelineSampler': LTXPipelineSampler,
                       'LTXSamplerCaptureFreeze': LTXSamplerCaptureFreeze,
                       'LTXSamplerCaptureCoverage': LTXSamplerCaptureCoverage}

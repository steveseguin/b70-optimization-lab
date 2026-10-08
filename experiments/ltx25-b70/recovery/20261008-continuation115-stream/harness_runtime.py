#!/usr/bin/env python3
"""CPU harness: drive the real packet115 integration.Runtime end to end with fake ComfyUI/device modules.

Runs in its own process (test_runtime_flow.py starts it). Real modules: integration, session (as
ltx_resolution_session), stream_contract, stream_receipts, stream_preview (writer and publish),
stream_decode, latent_anchor, qualification_gate, the transformed 115 ltx_duration_guard (capture
guard), and (cpu_native_lt.py) the sealed native LTXVAddLatentGuide / LTXVCropGuides / get_keyframe_idxs
compiled from the packet-114 nodes_lt.py, registered as the native guide nodes. Fakes: ComfyUI nodes (decoders, capture node), folder_paths, model management, the candidate
adapter, native bindings, the frame-mode conditioning guard, the runtime observer, setup gates, and a
deterministic stand-in for the samplers (outputs depend only on their inputs, and slot 0 of a masked
latent is pinned, as the real sampler blend does; with a guide, the masked guide frames are pinned). Every torch.xpu entry point raises: no device is
touched. All files go to a temporary directory under /dev/shm, removed at the end.

Prints one JSON summary line.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import types
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
GIB = 2 ** 30

ap = argparse.ArgumentParser()
ap.add_argument('--frames', type=int, default=49)
ap.add_argument('--anchor', default='mixed')
ap.add_argument('--reuse', type=int, default=1)
ap.add_argument('--placement', default='two-way20-28')
ap.add_argument('--stream-chunks', type=int, default=4)
ap.add_argument('--reset-at', type=int, default=-1)
ap.add_argument('--decode-delay', type=float, default=0.15)
ap.add_argument('--inject', default='none', choices=('none', 'decode-fail', 'repeat-diff', 'geometry', 'frame-tamper'))
args = ap.parse_args()
os.environ.update(LTX_STREAM_FRAMES=str(args.frames), LTX_ANCHOR=args.anchor, LTX_STREAM_TEXT_REUSE=str(args.reuse),
                  LTX_SAMPLER_PLACEMENT=args.placement, LTX_OUTPUT_SIZE='256x256')

import torch  # noqa: E402


def _no_device(*a, **k):
    raise RuntimeError('harness: a device API was called')


for _name in ('mem_get_info', 'synchronize', 'device_count', 'set_device', 'memory_allocated', 'memory_reserved',
              'max_memory_allocated', 'get_device_properties', 'current_device', 'init'):
    setattr(torch.xpu, _name, _no_device)

sys.path.insert(0, str(HERE))
import runtime_packet as rp  # noqa: E402  (reads the sealed parents only)
import stream_contract as c  # noqa: E402
import stream_receipts as rec  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix='ltx115-harness-', dir='/dev/shm'))
ROOT, PACKET, MODS = TMP / 'root', TMP / 'packet', TMP / 'mods'
RUN = ROOT / 'encoder-server-harness'
for d in (ROOT / 'output/validation', PACKET / 'resolution', PACKET / 'source/comfy_extras', MODS, RUN):
    d.mkdir(parents=True)
shutil.copyfile(HERE / 'stream-plan.json', PACKET / 'resolution/stream-plan.json')
(MODS / 'ltx_duration_guard.py').write_bytes(rp.capture_guard_source(
    rp.regular(rp.PARENT / 'source/scripts/ltx_duration_guard.py')))
sys.path.insert(0, str(MODS))
NODES_LT = PACKET / 'source/comfy_extras/nodes_lt.py'
NODES_LT.write_bytes((rp.PARENT / 'source/comfy_extras/nodes_lt.py').read_bytes())
for rel in ('node_helpers.py', 'comfy/ldm/lightricks/symmetric_patchifier.py'):
    (PACKET / 'source' / rel).parent.mkdir(parents=True, exist_ok=True)
    (PACKET / 'source' / rel).write_bytes((rp.PARENT / 'source' / rel).read_bytes())
G = c.geometry(args.frames)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tsha(t):
    return sha(t.detach().contiguous().view(torch.uint8).numpy().tobytes())


def gen(*parts):
    return torch.Generator().manual_seed(int(sha(repr(parts).encode())[:15], 16))


# -- native get_noise_mask, compiled from the sealed source with the packet's filename ---------------
import ast  # noqa: E402
_tree = ast.parse(NODES_LT.read_bytes())
_gnm = next(n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == 'get_noise_mask')
_ns = {'torch': torch}
exec(compile(ast.Module(body=[_gnm], type_ignores=[]), str(NODES_LT), 'exec'), _ns)
get_noise_mask = _ns['get_noise_mask']
import cpu_native_lt  # noqa: E402
NATIVE_LT = cpu_native_lt.load(rp.PARENT / 'source', PACKET / 'source')   # compiled under the fake packet's file name

# -- fake ComfyUI modules ---------------------------------------------------------------------------
import session as real_session  # noqa: E402
sys.modules['ltx_resolution_session'] = real_session

folder_paths = types.ModuleType('folder_paths')
folder_paths.get_output_directory = lambda: str(ROOT / 'output')


def get_save_image_path(prefix, output_dir, w=0, h=0):
    subfolder = os.path.dirname(os.path.normpath(prefix))
    filename = os.path.basename(os.path.normpath(prefix))
    folder = os.path.join(output_dir, subfolder)
    os.makedirs(folder, exist_ok=True)
    return folder, filename, 1, subfolder, prefix


folder_paths.get_save_image_path = get_save_image_path
sys.modules['folder_paths'] = folder_paths

VAE = types.SimpleNamespace(role='video_vae', downscale_index_formula=(8, 32, 32))
AUDIO_VAE = types.SimpleNamespace(role='audio_vae')
STATS = {'decodes': [], 'loads': 0, 'load_threads': set(), 'captures': 0, 'encode_threads': set(),
         'encode_during_decode': 0, 'decoding': 0}


def fake_images(v, name):
    STATS['decoding'] += 1
    try:
        time.sleep(args.decode_delay)
    finally:
        STATS['decoding'] -= 1
    if args.inject == 'decode-fail' and name.endswith('s00000002'):
        raise RuntimeError('injected decode failure')
    images = torch.rand([G['frames'], 256, 256, 3], generator=gen('img', tsha(v)), dtype=torch.float32)
    if args.inject == 'repeat-diff' and 'qrepeat-c000001' in name:
        images[0, 0, 0, 0] += 1e-3
    return images


CURRENT_DECODE = threading.local()


class VAEDecode:
    def decode(self, vae, samples):
        assert vae is VAE and torch.is_inference_mode_enabled()
        mm.load_models_gpu([vae])
        STATS['decodes'].append(threading.current_thread().name)
        return (fake_images(samples['samples'], CURRENT_DECODE.name),)


class LTXVAudioVAEDecode:
    @classmethod
    def execute(cls, samples, audio_vae):
        assert audio_vae is AUDIO_VAE
        n = G['audio_samples'] + (480 if args.inject == 'geometry' else 0)
        wave = torch.rand([1, 2, n], generator=gen('wave', tsha(samples['samples'])), dtype=torch.float32)
        return types.SimpleNamespace(result=({'waveform': wave, 'sample_rate': 48000},))


class LTXBaselineCapture:
    """Same steps as the sealed capture node: stats, the capture guard's prewrite, exclusive mkdir, save."""
    def capture(self, images, video_latent, audio_latent, audio, run_name):
        import ltx_duration_guard
        from safetensors.torch import save_file
        out = Path(folder_paths.get_output_directory()) / 'validation' / run_name
        tensors = {'images': images.detach().cpu().contiguous(),
                   'video_latent': video_latent['samples'].detach().cpu().contiguous(),
                   'audio_latent': audio_latent['samples'].detach().cpu().contiguous(),
                   'waveform': audio['waveform'].detach().cpu().contiguous()}
        report = {'run_name': run_name, 'sample_rate': audio['sample_rate'], 'tensors': {}}
        for name, t in tensors.items():
            report['tensors'][name] = {'dtype': str(t.dtype), 'shape': list(t.shape), 'sha256': tsha(t),
                                       'finite': bool(torch.isfinite(t).all()), 'min': float(t.min()),
                                       'max': float(t.max()), 'std': float(t.float().std())}
        ltx_duration_guard.require_capture_prewrite(tensors, report, run_name)
        out.mkdir(parents=True, exist_ok=False)
        save_file(tensors, str(out / 'tensors.safetensors'))
        STATS['captures'] += 1


nodes = types.ModuleType('nodes')
nodes.VAEDecode = VAEDecode
nodes.NODE_CLASS_MAPPINGS = {'VAEDecode': VAEDecode, 'LTXVAudioVAEDecode': LTXVAudioVAEDecode,
                             'LTXBaselineCapture': LTXBaselineCapture,
                             'LTXVAddLatentGuide': NATIVE_LT['LTXVAddLatentGuide'],
                             'LTXVCropGuides': NATIVE_LT['LTXVCropGuides']}
sys.modules['nodes'] = nodes

comfy = types.ModuleType('comfy')
mm = types.ModuleType('comfy.model_management')


def load_models_gpu(models, **kw):
    STATS['loads'] += 1
    STATS['load_threads'].add(threading.current_thread().name)


mm.load_models_gpu = load_models_gpu
comfy.model_management = mm
sys.modules['comfy'], sys.modules['comfy.model_management'] = comfy, mm
comfy_api = types.ModuleType('comfy_api')
latest = types.ModuleType('comfy_api.latest')
latest.io = types.SimpleNamespace(NodeOutput=type('NodeOutput', (), {}))
comfy_api.latest = latest
sys.modules['comfy_api'], sys.modules['comfy_api.latest'] = comfy_api, latest

CAPTURE_STATE = types.SimpleNamespace(CAPTURES_FROZEN=[False])
FREE = {'xpu:0': 10 * GIB, 'xpu:1': 10 * GIB, 'xpu:2': 10 * GIB, 'xpu:3': 13 * GIB}


def snapshot(required):
    return {'snapshot': {'physical_free_bytes': dict(FREE), 'peaks': {k: {'allocated': 1, 'reserved': 1, 'peak': 1}
                                                                     for k in FREE}},
            'required_physical_free_bytes': {k: required for k in FREE}}


class FakeController:
    def __init__(self):
        self.receipts = []

    def drain(self):
        rows, self.receipts = self.receipts, []
        return rows


class CandidateAdapter:
    def __init__(self, *, expected_routes, session, **kw):
        self.expected_routes, self.session = expected_routes, session
        self.ready, self.failed, self.current_name, self.guard = False, None, None, None
        self.controller = FakeController()
        self.objects = {'video_vae': VAE, 'audio_vae': AUDIO_VAE}
        self.captured = 0
        self.last_inventory = None
        self.capture = CAPTURE_STATE
        self.window = types.SimpleNamespace(precheck=lambda clip, text, workers: {'window': 64})
        self.clip = object()
        self.pipeline = types.SimpleNamespace(_STAGES={})
        self.receipts = []
        self.inspections = 0

    def _inspect(self, objects, observation=False):
        self.inspections += 1
        return {'route_inventory': self.inventory()['verdict']}

    def inventory(self):
        state = self.expected_routes()['state']
        routes = 48 if state != 'absent' else 0
        self.last_inventory = {'verdict': {'routes': routes, 'signatures_per_route': 4 if routes else 0,
                                           'state': state, 'passed': True},
                               'captured_graphs': self.captured, 'signature_digests': {i: 'd' for i in range(48)}}
        return self.last_inventory

    def prepare(self):
        assert getattr(self._inspect, '_ltx115_registry_lock', None) is not None, 'inspection not under the lock'
        assert getattr(mm.load_models_gpu, '_ltx115_registry_lock', None) is not None
        self.ready = True
        self._inspect(self.objects)
        return {'prepared': True}

    def before_request(self, name):
        self.current_name, self.guard = name, object()
        self._inspect(self.objects)
        self.inventory()
        return snapshot(8 * GIB)

    def after_request(self, name):
        if name.endswith('qgraph-c000000'):
            self.captured += 96
        elif name.endswith('qgraph-c000001'):
            self.captured += 8
        self._inspect(self.objects)
        self.inventory()
        self.current_name, self.guard = None, None
        return snapshot(2 * GIB)

    def abort_request(self, error):
        self.current_name, self.guard = None, None
        self.failed = str(error)

    def native_state(self):
        return self._inspect(self.objects, observation=True)

    def drain_receipts(self):
        return []


candidate_safety = types.ModuleType('candidate_safety')
candidate_safety.CandidateAdapter = CandidateAdapter
sys.modules['candidate_safety'] = candidate_safety


def tensor_metadata(t):
    return {'object_id': id(t), 'storage_id': int(t.untyped_storage().data_ptr()), 'shape': list(t.shape),
            'dtype': str(t.dtype), 'device': str(t.device), 'contiguous': t.is_contiguous()}


class NativeBindings:
    def __init__(self, **kw):
        # The globals of the native conditioner are the sealed nodes_lt.py namespace (as in the server).
        ns = NATIVE_LT
        ns['get_noise_mask'] = get_noise_mask
        exec(compile('def execute(cls, vae, image, latent, strength, bypass=False):\n    pass\n', str(NODES_LT), 'exec'), ns)
        self.function = ns['execute']
        self.tensor_metadata = tensor_metadata
        self.inspect_anchor = self.inspect_encoder_cache = self.unwrap_output = lambda *a, **k: None
        self.native_call = None

    def check_native(self):
        return None

    def settings(self):
        return {}

    def receipt(self):
        return {'method': 'fake'}


native_bindings = types.ModuleType('native_bindings')
native_bindings.NativeBindings = NativeBindings
sys.modules['native_bindings'] = native_bindings


class ConditioningStageGuard:
    """Frame anchor stand-in: 'encodes' the anchor image into slot 0 and records the 113 floor receipts."""
    def __init__(self, **kw):
        self.active = self.anchor = None
        self.receipts = []

    def begin_request(self, name, anchor, expected_anchor_sha256, first_stage='A'):
        assert sha(anchor.contiguous().view(torch.uint8).numpy().tobytes()) == expected_anchor_sha256
        assert first_stage in ('A', 'B')
        self.active, self.anchor, self.first_stage = name, anchor, first_stage
        self.stages = []

    def run_stage(self, stage, request_id, vae, latent, native_call):
        assert request_id == self.active and vae is VAE and 'noise_mask' not in latent
        assert self.stages == [] and stage == self.first_stage or self.stages == ['A'] and stage == 'B'
        self.stages.append(stage)
        STATS['encode_threads'].add(threading.current_thread().name)
        STATS['encode_during_decode'] += int(STATS['decoding'] > 0)
        t = torch.rand([1, 128, 1] + list(latent['samples'].shape[3:]), generator=gen('enc', tsha(self.anchor), stage))
        out = {'samples': latent['samples'].clone(), 'noise_mask': get_noise_mask(latent)}
        out['samples'][:, :, :1] = t
        out['noise_mask'][:, :, :1] = 0.0
        floors = {'xpu:0': 8 * GIB, 'xpu:1': 8 * GIB, 'xpu:2': 2 * GIB, 'xpu:3': 9 * GIB}
        self.receipts.append({'event': 'stage', 'request_id': request_id, 'stage': stage, 'completed': True,
                              'before': {'required_physical_free_bytes': floors,
                                         'snapshot': {'physical_free_bytes': dict(FREE)}},
                              'after': {'required_physical_free_bytes': {k: 2 * GIB for k in floors},
                                        'snapshot': {'physical_free_bytes': dict(FREE)}}})
        return out

    def finish_request(self, name):
        assert name == self.active
        self.active = self.anchor = None


conditioning_guard = types.ModuleType('conditioning_guard')
conditioning_guard.ConditioningStageGuard = ConditioningStageGuard
sys.modules['conditioning_guard'] = conditioning_guard
sys.modules['continuation_anchor'] = types.ModuleType('continuation_anchor')

runtime_observer = types.ModuleType('runtime_observer')


def actual_state(fault=False):
    a = integration._CTX.authority
    state = a.expected_routes()
    return {'fault': fault, 'preview_pending': 0, 'preview_failures': 0,
            'captures_frozen': bool(CAPTURE_STATE.CAPTURES_FROZEN[0]), 'loads_frozen': False,
            'sampler_routes': 0 if state == 'absent' else 48, 'lean_state': 0, 'decode_replicas': 0,
            'queue_running': 0, 'queue_pending': 0, 'queue_running_ids': [], 'queue_pending_ids': [],
            'pipeline': {'running': 0, 'stages': {}}}


runtime_observer.actual_state = actual_state
sys.modules['runtime_observer'] = runtime_observer
setup_gates = types.ModuleType('setup_gates')
setup_gates.validate_window = lambda value, name, identity: {'passed': True, 'run_name': name}
sys.modules['setup_gates'] = setup_gates

# -- the runtime under test -------------------------------------------------------------------------
import integration  # noqa: E402

MANIFEST_SHA = 'ab' * 32
manifest = {'files': {'source/scripts/ltx_duration_guard.py': sha((MODS / 'ltx_duration_guard.py').read_bytes())},
            'runtime': {'files': {}}}
(RUN / 'server-identity.json').write_text(json.dumps({'source_packet_manifest_sha256': MANIFEST_SHA}))
integration.RESERVE_BYTES = 0
rt = integration.Runtime(PACKET, manifest, MANIFEST_SHA, RUN)
integration._CTX = rt
rt._xpu3_free = lambda: 13 * GIB
_real_decode_job = rt._decode_job


def decode_job(job):
    CURRENT_DECODE.name = job['run_name']
    record = _real_decode_job(job)
    if args.inject == 'frame-tamper' and job['run_name'].endswith('s00000002') and record['frame_anchor']:
        with open(record['frame_anchor']['path'], 'r+b') as stream:   # same size, same inode: only the bytes change
            stream.seek(4)
            stream.write(b'\x00\x00\x80\x3f')
    return record


rt.decoder.process_fn = decode_job


def fake_save(job):
    from stream_preview import publish_exclusive, temporary_name
    tmp = temporary_name(job['path'])
    tmp.write_bytes(b'mp4:' + tsha(job['images']).encode())
    return publish_exclusive(tmp, job['path'])


rt.preview.save_fn = fake_save
auth = rt.authority
N = integration


def fake_text(prompt):
    return [[torch.randn([1, 16, 32], generator=gen('text', prompt)), {'pooled_output': None}]]


def sample(lat, seed, cond, stage):
    rows = integration._tensor_rows(torch, cond)
    out = torch.randn(list(lat['samples'].shape), generator=gen('sample', seed, stage, repr(rows),
                                                                tsha(lat['samples'])), dtype=torch.float32)
    if 'noise_mask' in lat:
        pinned = (lat['noise_mask'].reshape(-1) == 0).nonzero().reshape(-1).tolist()
        for k in pinned:                               # the sampler's blend pins every masked slot
            out[:, :, k:k + 1] = lat['samples'][:, :, k:k + 1]
    audio = torch.randn(G['tensor_shapes']['audio_latent'], generator=gen('audio', seed, stage, repr(rows)))
    return out, audio


def execute(graph):
    pid = str(uuid.uuid4())
    descriptor = rt.precheck(graph)
    rt.submit_ns[pid] = time.time_ns()
    name = descriptor['name']
    row = auth.begin(name, graph, pid)
    try:
        rt.before_request(row, pid)
        with torch.inference_mode():
            run_nodes(graph, name, pid)
        rt.after_request(row, pid)
        auth.finish([('execution_start', {'prompt_id': pid}), ('execution_success', {'prompt_id': pid})])
    except Exception as error:
        rt.on_failure(row, pid, error)
        auth.halt(error)
        raise
    return name


def event(pid, node):
    rt.record_event({'prompt_id': pid, 'node': node})


def run_nodes(graph, name, pid):
    if '470' in graph:
        (RUN / ('text-window-probe-' + name + '.json')).write_text(json.dumps({'run_name': name}))
        return
    if '490' in graph:
        N.LTXStreamPrepare115().apply(name)
        return
    out = graph['stream_output']['inputs']
    params = {k: out[k] for k in ('kind', 'frames', 'placement', 'anchor', 'scene_id', 'chunk_index', 'seed',
                                  'stream_seq', 'predecessor_anchor_sha256', 'reuse_text')}
    params['reset'] = out.get('reset', 0)
    prompt = graph['stream_text']['inputs']['text']
    cond = None
    if '364' in graph:
        event(pid, '364')
        cond = fake_text(prompt)
    cond = N.LTXStreamText115().apply(name, prompt, conditioning=cond)[0]
    cond_a = cond_b = cond
    lat_a = {'samples': torch.zeros(G['stage_shapes']['A'])}
    anchored = 'stream_anchor' in graph
    mode = args.anchor
    if anchored:
        if mode in ('latent', 'mixed'):
            anchor_a, anchor_b = N.LTXStreamLatentAnchor115().apply(name, params['predecessor_anchor_sha256'])
            lat_a = N.LTXStreamLatentCondition115().apply(lat_a, anchor_a, 1.0, name, 'A')[0]
        elif mode == 'guide':
            guide_a, guide_b = N.LTXStreamGuideAnchor115().apply(name, params['predecessor_anchor_sha256'])
            cond_a, neg_a, lat_a = N.LTXStreamGuide115().apply(cond, cond, VAE, lat_a, guide_a, 1.0, name, 'A')
        else:
            image = N.LTXStreamAnchor115().apply(name, params['predecessor_anchor_sha256'])[0]
            lat_a = N.LTXStreamCondition115().apply(VAE, image, lat_a, 1.0, False, name, 'A')
    event(pid, '344')
    va, aa = sample(lat_a, params['seed'], cond_a, 'A')
    stage_a = {'samples': va, 'noise_mask': lat_a['noise_mask']} if 'noise_mask' in lat_a else {'samples': va}
    event(pid, '367')
    if anchored and mode == 'guide':
        event(pid, 'stream_crop_a')
        stage_a = N.LTXStreamCropGuides115().apply(cond_a, neg_a, stage_a, name, 'A')[2]
    event(pid, '348')
    up = {'samples': torch.randn(G['stage_shapes']['B'], generator=gen('up', tsha(stage_a['samples'])))}
    lat_b = up
    if anchored:
        event(pid, 'stream_condition_b')
        if mode == 'latent':
            lat_b = N.LTXStreamLatentCondition115().apply(up, anchor_b, 1.0, name, 'B')[0]
        elif mode == 'mixed':
            lat_b = N.LTXStreamFrameConditionB115().apply(VAE, up, 1.0, False, name)
        elif mode == 'guide':
            cond_b, neg_b, lat_b = N.LTXStreamGuide115().apply(cond, cond, VAE, up, guide_b, 1.0, name, 'B')
        else:
            lat_b = N.LTXStreamCondition115().apply(VAE, image, up, 1.0, False, name, 'B')
    event(pid, '340')
    event(pid, '368')
    vb, ab = sample(lat_b, params['seed'], cond_b, 'B')
    stage_b = {'samples': vb, 'noise_mask': lat_b['noise_mask']} if 'noise_mask' in lat_b else {'samples': vb}
    event(pid, '369')
    if anchored and mode == 'guide':
        event(pid, 'stream_crop_b')
        stage_b = N.LTXStreamCropGuides115().apply(cond_b, neg_b, stage_b, name, 'B')[2]
    event(pid, 'stream_output')
    N.LTXStreamChunk115().apply({'samples': stage_b['samples']}, {'samples': ab}, {'samples': stage_a['samples']},
                                VAE, AUDIO_VAE, name, **{k: v for k, v in params.items()})

summary = {'frames': args.frames, 'anchor': args.anchor, 'reuse': args.reuse, 'inject': args.inject}
try:
    for r in c.setup_graphs():
        execute(r['graph'])
    for p in c.qualification_params(args.frames, args.reuse, args.placement, args.anchor):
        execute(c.build_chunk_graph(p))
    verdict = rt.action('qualify-verdict')
    summary['verdict'] = verdict
    stream_names = []
    if verdict['passed']:
        prompts = ['a red boat on calm water', 'a red boat on calm water', 'a lighthouse at dusk']
        for seq in range(args.stream_chunks):
            status = auth.status()
            pred = status['chain']['anchor_sha256'] if seq else ''
            prompt = prompts[min(seq, 2)] if seq < 3 else prompts[2]
            reset = int(seq == args.reset_at)
            same = seq > 0 and c.text_sha256(prompt) == status['chain']['prompt_sha256']
            reuse = int(bool(args.reuse) and same and not reset)
            params = c.stream_params(args.frames, seq, prompt, 1000 + seq, pred, 's', reuse, args.placement,
                                     reset=reset, anchor=args.anchor)
            try:
                stream_names.append(execute(c.build_chunk_graph(params)))
            except Exception as error:
                summary['stream_error'] = repr(error)[:300]
                break
            if args.inject == 'decode-fail':
                time.sleep(2 * args.decode_delay + 0.3)    # let the failing decode reach its latch
    summary['decoder_drained'] = rt.decoder.drain(60)
    summary['preview_drained'] = rt.preview.drain(60)
    time.sleep(0.2)
    summary['halted'] = auth.failed
    summary['decoder'] = rt.decoder.summary()
    summary['preview'] = rt.preview.summary()
    names = [row['name'] for row in auth.qualification_rows] + stream_names
    checked = []
    for name in names:
        receipt = json.loads((RUN / 'receipts' / ('receipt-' + name + '.json')).read_text())
        rec.validate_receipt(receipt)
        drec = RUN / 'receipts' / ('decode-' + name + '.json')
        prec = RUN / 'receipts' / ('preview-' + name + '.json')
        row = {'name': name, 'anchor_kind': receipt['anchor_out']['kind'], 'anchor_bytes': receipt['anchor_out']['bytes'],
               'decode_at_start': receipt['decode_at_start'], 'reused': receipt['text']['reused'],
               'slot0_pin': None if receipt['slot0_pin'] is None else
               {k: v['bytes_equal'] for k, v in receipt['slot0_pin'].items()},
               'guide_pin': None if receipt.get('guide_pin') is None else
               {k: v['bytes_equal'] for k, v in receipt['guide_pin'].items()},
               'frame_in': (receipt['anchor_in'] or {}).get('frame'), 'drop': receipt['delivery']['drop_leading_frames'],
               'delivery_new_frames': receipt['delivery']['new_frames'], 'decode_record': drec.is_file(),
               'preview_record': prec.is_file(), 'timing_s': receipt['timing_s']}
        if drec.is_file():
            d = rec.validate_decode_record(json.loads(drec.read_text()), receipt)
            row['decode_sequence'] = d['sequence']
            row['sharpness_frames'] = d['sharpness']['frames']
            row['last_frame_sha256'] = d['last_frame_sha256']
        if prec.is_file():
            p = rec.validate_preview_record(json.loads(prec.read_text()), receipt)
            raw = Path(p['path']).read_bytes()
            assert sha(raw) == p['sha256'] and len(raw) == p['bytes']
        checked.append(row)
    summary['chunks'] = checked
    summary['anchors_on_disk'] = sorted(x.name for x in (RUN / 'anchors').iterdir())
    summary['run_files'] = sorted(x.name for x in RUN.iterdir() if x.is_file())
    summary['geometry_record'] = (json.loads((RUN / 'stream-geometry-measured.json').read_text())
                                  if (RUN / 'stream-geometry-measured.json').exists() else None)
    summary['decode_threads'] = sorted(set(STATS['decodes']))
    summary['load_threads'] = sorted(STATS['load_threads'])
    summary['captures'] = STATS['captures']
    summary['registry_holds'] = rt.registry.holds
    summary['encode_threads'] = sorted(STATS['encode_threads'])
    summary['encode_during_decode'] = STATS['encode_during_decode']
    summary['xpu_initialized'] = bool(torch.xpu.is_initialized())
except Exception as error:
    import traceback
    summary['error'] = traceback.format_exc()[-3000:]
    summary['halted'] = auth.failed
    summary['run_files'] = sorted(x.name for x in RUN.iterdir() if x.is_file())
finally:
    rt.decoder.close()
    rt.preview.close()
    shutil.rmtree(TMP, ignore_errors=True)
print(json.dumps(summary, default=str))

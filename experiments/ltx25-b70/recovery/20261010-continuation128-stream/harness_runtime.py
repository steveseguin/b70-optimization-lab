#!/usr/bin/env python3
"""CPU harness: drive the real packet123 integration.Runtime end to end with fake ComfyUI/device modules.

Packet123 additions: --snapshot-mode walk|fingerprint (default fingerprint) and --pool-cap. The candidate adapter
is still a fake, but its residence world is a set of fake tensors (str(device) is the role's card) behind seven
fake patchers, its walk is the REAL CandidateAdapter._inspect (sealed candidate_safety.py) with the REAL
NativeAdapter._rows and native_adapter.fingerprint bound to it, and its controller checks the residence of every
snapshot against the admitted fingerprints like CandidateSafety does. Every snapshot (request before/after and,
through the fake guard, stage A/B before/after) goes through the runtime's SnapshotInspector. Injections:
`snap-diff` (the walk's residence differs on the graph chain's chunk 1 A-after snapshot: a dual disagreement
latches snapshot-118-refused.json), `snap-mutate` (a sampler tensor's storage moves before stream chunk 2: both
modes refuse the request alike), `snap-near` (xpu:0 reads within 0.5 GiB of its floor from stream chunk 3 on:
the walk runs beside the fingerprint from that snapshot).

Packet117 additions: a fake cone controller (inside its scope the fake VAE decode returns the full decode's
last frame and zeros elsewhere, as the real cone does for the frames outside the cone; `cone-diff` perturbs
the cone's last frame of the graph chain's chunk 0, `cone-repeat-diff` that of the repeat chain's chunk 1),
fake native conditioning that really calls `vae.encode` (so the decode thread's precomputed encodes go
through precompute_guard's CaptureVAE / ReplayVAE and the real Xpu3Snapshot with fake device callbacks;
`pre-diff` perturbs the decode thread's encodes, `pre-floor` drops xpu:3 below the precompute floor), and
the lever launch options --anchor-decode / --bencode-overlap / --prep-ahead.

Packet116 additions: the decoder-graph controller is a fake with the real controller's interface
(graph_decode scope, captures on first use, freeze, signatures); the fake VAE decode is a function
of the latent only, so the dual decode of the graph chain is byte-identical unless a fault is
injected (`dg-diff`: the graph-mode decode differs; `dg-repeat-diff`: only the repeat chain's
graph decode differs, which only the cross-chain gate can see). The fake audio decode sleeps
(`--audio-delay`), so the 116a overlap of chunk n's audio/hash/record with chunk n+1 is visible.

Runs in its own process (test_runtime_flow.py starts it). Real modules: integration, session (as
ltx_resolution_session), stream_contract, stream_receipts, stream_preview (writer and publish),
stream_decode, latent_anchor, qualification_gate, the transformed 116 ltx_duration_guard (capture
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
ap.add_argument('--audio-delay', type=float, default=0.25)
ap.add_argument('--decoder-graph', type=int, default=1, choices=(0, 1))
ap.add_argument('--reference', default='none', choices=('none', 'sealed'))
ap.add_argument('--anchor-decode', default=None, choices=('full', 'cone'))
ap.add_argument('--bencode-overlap', type=int, default=None, choices=(0, 1))
ap.add_argument('--prep-ahead', type=int, default=None, choices=(0, 1))
ap.add_argument('--client-delay', type=float, default=0.05)
ap.add_argument('--inject', default='none', choices=('none', 'decode-fail', 'repeat-diff', 'geometry', 'frame-tamper',
                                                     'dg-diff', 'dg-repeat-diff', 'audio-fail', 'cone-diff',
                                                     'cone-repeat-diff', 'pre-diff', 'pre-floor', 'snap-diff',
                                                     'snap-mutate', 'snap-near', 'replica-diff', 'replica-repeat-diff', 'replica-floor', 'replica-live-diff'))
ap.add_argument('--snapshot-mode', default='fingerprint', choices=('walk', 'fingerprint'))
ap.add_argument('--pool-cap', default=None)
ap.add_argument('--display-schedule', default='sampler-a', choices=('sampler-a', 'sampler-b', 'eager-display'))
ap.add_argument('--anchor-read-ahead', type=int, default=0, choices=(0, 1))
ap.add_argument('--snapshot-schedule', default='full', choices=('full', 'a-xpu3-sync'))
ap.add_argument('--display-device', default='xpu:3', choices=('xpu:3', 'xpu:2'))
ap.add_argument('--aux-residency', default='legacy', choices=('legacy', 'xpu2'))
args = ap.parse_args()
_LEVER_DEFAULTS = ('cone', 1, 1) if args.anchor == 'frame' else ('full', 0, 0)
LEVERS = (args.anchor_decode or _LEVER_DEFAULTS[0],
          _LEVER_DEFAULTS[1] if args.bencode_overlap is None else args.bencode_overlap,
          _LEVER_DEFAULTS[2] if args.prep_ahead is None else args.prep_ahead)
os.environ.update(LTX_AUX_RESIDENCY=args.aux_residency, LTX_STREAM_FRAMES=str(args.frames), LTX_ANCHOR=args.anchor, LTX_STREAM_TEXT_REUSE=str(args.reuse),
                  LTX_SAMPLER_PLACEMENT=args.placement, LTX_OUTPUT_SIZE='256x256',
                  LTX_DECODER_GRAPH=str(args.decoder_graph), LTX_ANCHOR_DECODE=LEVERS[0],
                  LTX_BENCODE_OVERLAP=str(LEVERS[1]), LTX_PREP_AHEAD=str(LEVERS[2]),
                  LTX_DISPLAY_DEVICE=args.display_device, LTX_SNAPSHOT_MODE=args.snapshot_mode, LTX_DISPLAY_SCHEDULE=args.display_schedule,
                  LTX_ANCHOR_READ_AHEAD=str(args.anchor_read_ahead), LTX_SNAPSHOT_SCHEDULE=args.snapshot_schedule)
if args.pool_cap is not None:
    os.environ['LTX_DECODER_GRAPH_POOL_CAP_GB'] = args.pool_cap

import torch  # noqa: E402


def _no_device(*a, **k):
    raise RuntimeError('harness: a device API was called')


for _name in ('mem_get_info', 'synchronize', 'device_count', 'set_device', 'memory_allocated', 'memory_reserved',
              'max_memory_allocated', 'get_device_properties', 'current_device', 'init'):
    setattr(torch.xpu, _name, _no_device)

sys.path.insert(0, str(HERE))
# Packet123: the sealed native_safety / native_adapter (the runtime imports them in prepare); -B keeps them untouched.
sys.path.append('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-native-111/source/scripts')
import runtime_packet as rp  # noqa: E402  (reads the sealed parents only)
import stream_contract as c  # noqa: E402
import stream_receipts as rec  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix='ltx120-harness-', dir='/dev/shm'))
ROOT, PACKET, MODS = TMP / 'root', TMP / 'packet', TMP / 'mods'
RUN = ROOT / 'encoder-server-harness'
for d in (ROOT / 'output/validation', PACKET / 'resolution', PACKET / 'source/comfy_extras', MODS, RUN):
    d.mkdir(parents=True)
shutil.copyfile(HERE / 'stream-plan.json', PACKET / 'resolution/stream-plan.json')
# The cross-packet reference: 'none' = a document without this variant (the fake outputs match no real run);
# 'sealed' = the real packet-113/114 frame references (a frame-anchor 49/97 two-way20-28 run must then fail them).
_REFERENCE = (HERE / 'reference-frame-qualification-hashes.json').read_bytes() if args.reference == 'sealed' else \
    json.dumps({'schema': 'ltx.stream116.reference-frame-hashes.v1', 'variants': {}}).encode()
(PACKET / 'resolution/reference-frame-hashes.json').write_bytes(_REFERENCE)
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

STATS = {'decodes': [], 'loads': 0, 'load_threads': set(), 'captures': 0, 'encode_threads': set(),
         'encode_during_decode': 0, 'decoding': 0, 'encodes': [], 'concurrent_encodes': 0, 'encoding': 0,
         'display_after_go': [], 'cone_decodes': 0}


def fake_encode(pixels):
    """The fake VAE encode: a deterministic function of the pixel bytes (shape [1, 128, 1, H/32, W/32])."""
    STATS['encoding'] += 1
    try:
        if STATS['encoding'] > 1:
            STATS['concurrent_encodes'] += 1
        STATS['encode_threads'].add(threading.current_thread().name)
        STATS['encode_during_decode'] += int(STATS['decoding'] > 0)
        STATS['encodes'].append((threading.current_thread().name, list(pixels.shape)))
        time.sleep(0.01)
        h, w = pixels.shape[1] // 32, pixels.shape[2] // 32
        t = torch.rand([1, 128, 1, h, w], generator=gen('enc', tsha(pixels)), dtype=torch.float32)
        if args.inject == 'pre-diff' and threading.current_thread().name == 'ltx120-decode':
            t[0, 0, 0, 0, 0] += 1e-3
        return t
    finally:
        STATS['encoding'] -= 1


VAE = types.SimpleNamespace(role='video_vae', downscale_index_formula=(8, 32, 32), encode=fake_encode,
                            first_stage_model=types.SimpleNamespace(encoder=object()))
AUDIO_VAE = types.SimpleNamespace(role='audio_vae')


def fake_images(v, name):
    STATS['decoding'] += 1
    try:
        time.sleep(args.decode_delay * (0.4 if CONE.active else 1.0))
    finally:
        STATS['decoding'] -= 1
    if args.inject == 'decode-fail' and name.endswith('s00000002'):
        raise RuntimeError('injected decode failure')
    images = torch.rand([G['frames'], 256, 256, 3], generator=gen('img', tsha(v)), dtype=torch.float32)
    if args.inject == 'repeat-diff' and 'qrepeat-c000001' in name:
        images[0, 0, 0, 0] += 1e-3
    if DG.active and not CONE.active and (args.inject == 'dg-diff' or
                                          (args.inject == 'dg-repeat-diff' and 'qrepeat-c000001' in name)):
        images[3, 7, 7, 1] += 1e-3
    if CONE.active:
        # The cone computes only the last frame's dependency cone: the other frames are not the decode's.
        STATS['cone_decodes'] += 1
        images[:-1] = 0.0
        if (args.inject == 'cone-diff' and 'qgraph-c000000' in name) or \
                (args.inject == 'cone-repeat-diff' and 'qrepeat-c000001' in name):
            images[-1, 5, 5, 0] += 1e-3
    else:
        STATS['display_after_go'].append((name, rt.sampler_a_starts if 'rt' in globals() else None))
    return images


class FakeCone:
    """The interface integration uses of stream_anchor_decode.ConeAnchorDecode (no torch device)."""
    def __init__(self):
        self._local = threading.local()
        self.active, self.owner, self.decodes = False, None, 0
        self.checks = {'equal': 0, 'differ': 0}

    @property
    def active(self):
        return getattr(self._local, 'active', False)

    @active.setter
    def active(self, value):
        self._local.active = value

    def cone_decode(self):
        import contextlib
        import stream_anchor_decode as sad

        @contextlib.contextmanager
        def scope():
            if self.owner is None:
                self.owner = threading.get_ident()
            sad.require(self.owner == threading.get_ident(), 'Cone decode is bound to the decode thread')
            self.active = True
            try:
                yield self
            finally:
                self.active = False
            self.decodes += 1
        return scope()

    def note_check(self, equal):
        self.checks['equal' if equal else 'differ'] += 1

    def receipt(self):
        return {'fake': True, 'decodes': self.decodes, 'checks': dict(self.checks),
                'plans': [{'frames': G['frames'], 'cone': [[G['frames'] - 46, G['frames']]]}]}


CONE = FakeCone()


class FakeDecoderGraph:
    """The interface integration uses of stream_decoder_graph.DecoderGraph (no torch device). Packet123: with a pool
    cap the fake captures forward_pre_diffusion only and keeps forward_diff_step eager (as a 121-frame cap would)."""
    METHODS = ('forward_pre_diffusion', 'forward_diff_step')

    def pool_receipt(self):
        cap = c.parse_pool_cap(args.pool_cap)
        captured = sorted({x['method'] for x in self.captures})
        return {'cap_bytes': cap, 'growth_bytes': 3 * 10 ** 9 if captured else 0, 'captured': captured,
                'capped': [] if cap is None or not self.sigs['forward_diff_step'] else ['forward_diff_step'],
                'capped_calls': {}}

    def __init__(self):
        self.captures, self.frozen, self.active, self.owner = [], False, False, None
        self.sigs = {m: 0 for m in self.METHODS}
        self.replays = {m: 0 for m in self.METHODS}
        self.decodes = {'graph': 0, 'eager': 0}

    def graph_decode(self):
        import contextlib
        import stream_decoder_graph as dgm

        @contextlib.contextmanager
        def scope():
            if self.owner is None:
                self.owner = threading.get_ident()
            dgm.require(self.owner == threading.get_ident(), 'Decoder graph is bound to the decode thread')
            self.active = True
            try:
                yield self
            finally:
                self.active = False
            self.decodes['graph'] += 1
        return scope()

    def call_methods(self, cone):
        # The real cone replaces the diff shadow, so an eager display never registers that signature.
        for method in self.METHODS[:1] if cone else self.METHODS:
            if not self.sigs[method]:
                assert not self.frozen, 'decoder graph captures are frozen'
                self.sigs[method] = 1
                if args.pool_cap is None or method == 'forward_pre_diffusion':
                    self.captures.append({'method': method})
            else:
                self.replays[method] += 1

    def note_eager(self):
        self.decodes['eager'] += 1

    def signatures(self):
        return dict(self.sigs)

    def freeze(self):
        self.frozen = True

    def receipt(self):
        return {'fake': True, 'signatures': self.signatures(), 'captured_graphs': len(self.captures),
                'replays': dict(self.replays), 'decodes': dict(self.decodes), 'frozen': self.frozen}


DG = FakeDecoderGraph()


CURRENT_DECODE = threading.local()


class VAEDecode:
    def decode(self, vae, samples):
        assert vae is VAE and torch.is_inference_mode_enabled()
        if DG.active:
            DG.call_methods(CONE.active)
        mm.load_models_gpu([vae])
        STATS['decodes'].append(threading.current_thread().name)
        return (fake_images(samples['samples'], CURRENT_DECODE.name),)


class LTXVAudioVAEDecode:
    @classmethod
    def execute(cls, samples, audio_vae):
        assert audio_vae is AUDIO_VAE
        time.sleep(args.audio_delay)
        if args.inject == 'audio-fail' and CURRENT_DECODE.name.endswith('s00000002'):
            raise RuntimeError('injected audio decode failure')
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


# -- packet123: a fake residence world for the real walk (CandidateAdapter._inspect + NativeAdapter._rows) --------
class FakeDevice:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return str(other) == self.name

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.name)


class FakeStorage:
    def __init__(self, ptr):
        self.ptr = ptr

    def data_ptr(self):
        return self.ptr


class FakeTensor:
    _next = [0x10000]

    def __init__(self, shape, device, dtype='torch.bfloat16'):
        self.shape, self.device, self.dtype = tuple(shape), FakeDevice(device), dtype
        FakeTensor._next[0] += 0x1000
        self.ptr = FakeTensor._next[0]

    def untyped_storage(self):
        return FakeStorage(self.ptr)

    def numel(self):
        n = 1
        for s in self.shape:
            n *= s
        return n

    def element_size(self):
        return 2


class FakeModel:
    def __init__(self, role, device, count):
        self.params = [('%s.w%d' % (role, i), FakeTensor([4, i + 1], device)) for i in range(count)]
        self.buffers_ = [('%s.b0' % role, FakeTensor([2], device, 'torch.int64'))]

    def named_parameters(self):
        return iter(self.params)

    def named_buffers(self):
        return iter(self.buffers_)

    def parameters(self):
        return iter(t for _, t in self.params)

    def buffers(self):
        return iter(t for _, t in self.buffers_)


class FakePatcher:
    def __init__(self, role, device, count=6):
        self.role, self.load_device, self.model = role, FakeDevice(device), FakeModel(role, device, count)
        self.patches, self.hook_patches, self.forced_hooks = {}, {}, []
        self.shards = []

    def is_dynamic(self):
        return False

    def loaded_size(self):
        return 100

    def model_size(self):
        return 100

    def get_additional_models_with_key(self, key):
        assert key == 'ltx_layer_shard'
        return list(self.shards)

    def verify_placement(self):           # the sealed ltx_layer_shard verify_placement, on the fake tensors
        if not self.shards:
            raise RuntimeError('LTX shard registration is missing')
        for patcher in (self, *self.shards):
            misplaced = [str(t.device) for t in list(patcher.model.parameters()) + list(patcher.model.buffers())
                         if t.device != patcher.load_device]
            if misplaced:
                raise RuntimeError('LTX shard is not fully resident on %s: %s' % (patcher.load_device, set(misplaced)))
        if self.patches or self.hook_patches or self.forced_hooks:
            raise RuntimeError('Native LTX shard acquired unsupported weight/hooks patches')


import native_safety  # noqa: E402  (sealed arithmetic, fake placement owners below)
import residency123  # noqa: E402
# Simulate the packet123 loader's roles before importing the real CPU inspectors.
# This dictionary is process-local; the sealed parent files remain untouched.
native_safety.ROLES.clear()
native_safety.ROLES.update(residency123.roles(args.aux_residency))
_real_aux_guard = residency123.guard_aux


def _fake_aux_guard(torch_module, label, before, mode):
    # Execute the real guard against explicit fake counters, leaving torch.xpu
    # globally forbidden. This covers refusal logic without touching a device.
    fake = types.SimpleNamespace(xpu=types.SimpleNamespace(
        synchronize=lambda card: None, mem_get_info=lambda card: (10 * GIB, 32 * GIB)))
    return _real_aux_guard(fake, label, before, mode)


residency123.guard_aux = _fake_aux_guard
import native_adapter  # noqa: E402  (sealed 111)
import importlib.util as _ilu  # noqa: E402
_spec = _ilu.spec_from_file_location('candidate_safety_real', str(HERE / 'candidate_safety.py'))
REAL_CS = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(REAL_CS)
ROLE_DEVICES = dict(native_adapter.ROLES)
AUDIO_VAE.device = ROLE_DEVICES['audio_vae']
PATCHERS = {role: FakePatcher(role, device) for role, device in ROLE_DEVICES.items()}
PATCHERS['sampler_primary'].shards = [PATCHERS['sampler_secondary']]
SNAP_STATE = {'walk_calls': 0, 'mutated': False}
FREE = {'xpu:0': 10 * GIB, 'xpu:1': 10 * GIB, 'xpu:2': 10 * GIB, 'xpu:3': 13 * GIB}


def free_readings():
    free = dict(FREE)
    cur = getattr(integration, '_CTX', None) if 'integration' in globals() else None
    if args.inject == 'snap-near' and cur is not None and cur.current and \
            cur.current['name'].startswith('stream128-s') and cur.current['name'] >= 'stream128-s00000003':
        free['xpu:0'] = 8 * GIB + 2 ** 28          # 0.25 GiB above the 8 GiB pre-request floor
    return free


def snapshot(required):
    return {'snapshot': {'physical_free_bytes': dict(FREE), 'peaks': {k: {'allocated': 1, 'reserved': 1, 'peak': 1}
                                                                     for k in FREE}},
            'required_physical_free_bytes': {k: required for k in FREE}}


class FakeController:
    def __init__(self):
        self.receipts = []
        self.synchronize = lambda card: SNAP_CALLS.append('controller-sync:' + card)

    def drain(self):
        rows, self.receipts = self.receipts, []
        return rows


class CandidateAdapter:
    enable_signature_digest_cache = REAL_CS.CandidateAdapter.enable_signature_digest_cache
    signature_cache_summary = REAL_CS.CandidateAdapter.signature_cache_summary
    def __init__(self, *, expected_routes, session, **kw):
        self.expected_routes, self.session = expected_routes, session
        self.ready, self.failed, self.current_name, self.guard = False, None, None, None
        self.controller = FakeController()
        # Packet123: seven roles over fake patchers; the VAE roles are the fake VAEs with a .patcher.
        VAE.patcher, AUDIO_VAE.patcher = PATCHERS['video_vae'], PATCHERS['audio_vae']
        self.objects = {r: (VAE if r == 'video_vae' else AUDIO_VAE if r == 'audio_vae' else PATCHERS[r])
                        for r in ROLE_DEVICES}
        self.patchers = dict(PATCHERS)
        self.mm = types.SimpleNamespace(loaded_models=lambda: list(PATCHERS.values()), __file__=str(TMP / 'mm.py'))
        self.source_hashes = {}
        self.plan_sha256, self.runtime_sha256 = 'p' * 64, 'r' * 64
        self.torch = types.SimpleNamespace(xpu=types.SimpleNamespace(
            memory_allocated=lambda c: 1, memory_reserved=lambda c: 2, max_memory_allocated=lambda c: 3,
            synchronize=lambda c: SNAP_CALLS.append('inspector-sync:' + c),
            mem_get_info=lambda c: (free_readings()[c], 32 * GIB)))
        self.captured = 0
        self.last_inventory = None
        self.capture = CAPTURE_STATE
        self.window = types.SimpleNamespace(precheck=lambda clip, text, workers: {'window': 64})
        self.clip = object()
        self.pipeline = types.SimpleNamespace(_STAGES={})
        self.receipts = []
        self.inspections = 0

    # -- the real walk, bound to this fake (packet123) ---------------------------------------------
    _rows = native_adapter.NativeAdapter._rows
    _dtype_exception = native_adapter.NativeAdapter._dtype_exception

    def _state(self, observation=False):
        return {'route_inventory': self.inventory()['verdict']}

    def _free(self):
        return free_readings()

    def _inspect(self, objects, observation=False):
        self.inspections += 1
        SNAP_STATE['walk_calls'] += 1
        snap = REAL_CS.CandidateAdapter._inspect(self, objects, observation)
        cur = getattr(integration, '_CTX', None)
        name = cur.current['name'] if cur is not None and cur.current else None
        if args.inject == 'snap-diff' and name == 'stream128-qgraph-c000001' and \
                cur.inspector.labels[:1] == ['A-after']:
            snap['residence']['video_vae'] = dict(snap['residence']['video_vae'], ownership_sha256='0' * 64)
        return snap

    def check_snapshot(self, snap):
        """CandidateSafety's residence check (the harness controller is a fake)."""
        residence = snap.get('residence') or {}
        for role in ROLE_DEVICES:
            if residence.get(role, {}).get('ownership_sha256') != self.controller.expected_residence[role]:
                raise RuntimeError('Residence/ownership changed: ' + role)
        return snap

    def inventory(self):
        state = self.expected_routes()['state']
        routes = 48 if state != 'absent' else 0
        self.last_inventory = {'verdict': {'routes': routes, 'signatures_per_route': 4 if routes else 0,
                                           'state': state, 'passed': True},
                               'captured_graphs': self.captured, 'signature_digests': {i: 'd' for i in range(48)}}
        return self.last_inventory

    def prepare(self):
        assert getattr(self._inspect, '_ltx116_registry_lock', None) is not None, 'inspection not under the lock'
        assert getattr(mm.load_models_gpu, '_ltx116_registry_lock', None) is not None
        self.controller.expected_residence = {r: native_adapter.fingerprint(self._rows(r, require_loaded=True))
                                              for r in ROLE_DEVICES}
        self.ready = True
        self._inspect(self.objects)
        return {'prepared': True}

    def before_request(self, name):
        self.current_name, self.guard = name, object()
        if args.inject == 'snap-mutate' and name == 'stream128-s00000002' and not SNAP_STATE['mutated']:
            SNAP_STATE['mutated'] = True
            PATCHERS['sampler_secondary'].model.params[3][1].ptr += 0x40      # a storage move (.data = ...)
        self.check_snapshot(self._inspect(self.objects))
        self.inventory()
        return snapshot(8 * GIB)

    def after_request(self, name):
        if name.endswith('qgraph-c000000'):
            self.captured += 96
        elif name.endswith('qgraph-c000001'):
            self.captured += 8
        self.check_snapshot(self._inspect(self.objects))
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


NodeOutput = type('NodeOutput', (), {})


def fake_native(vae, image, latent, strength, bypass=False):
    """LTXVImgToVideoInplace.execute's arithmetic with a fake VAE: resize (stride), vae.encode, slot copy, mask."""
    assert not bypass and strength == 1.0
    samples = latent['samples'].clone()
    _, hs, ws = vae.downscale_index_formula
    height, width = samples.shape[3] * hs, samples.shape[4] * ws
    pixels = image if image.shape[1] == height else image[:, ::image.shape[1] // height,
                                                         ::image.shape[2] // width, :].contiguous()
    t = vae.encode(pixels[:, :, :, :3])
    samples[:, :, :t.shape[2]] = t
    mask = get_noise_mask(latent)
    mask[:, :, :t.shape[2]] = 1.0 - strength
    out = NodeOutput()
    out.result = ({'samples': samples, 'noise_mask': mask},)
    return out


class NativeBindings:
    def __init__(self, **kw):
        # The globals of the native conditioner are the sealed nodes_lt.py namespace (as in the server).
        ns = NATIVE_LT
        ns['get_noise_mask'] = get_noise_mask
        exec(compile('def execute(cls, vae, image, latent, strength, bypass=False):\n    pass\n', str(NODES_LT), 'exec'), ns)
        self.function = ns['execute']
        self.tensor_metadata = tensor_metadata
        self.native_calls = []

    def native_call(self, **kwargs):
        self.native_calls.append(threading.current_thread().name)
        return fake_native(**kwargs)

    def inspect_anchor(self, image):
        raw = image.detach().contiguous().view(torch.uint8).numpy().tobytes()
        return {'sha256': sha(raw), 'finite': bool(torch.isfinite(image).all())}

    def inspect_encoder_cache(self, encoder, thread_ident):
        assert thread_ident == threading.get_ident()
        return {'source_sha256': 'e' * 64, 'encoder_id': id(encoder), 'thread_ident': thread_ident,
                'entry_count': 0, 'foreign_entry_count': 0}

    def unwrap_output(self, result):
        assert type(result) is NodeOutput and len(result.result) == 1
        return result.result[0]

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
    """Frame anchor stand-in: runs the given native call on the anchor and records the 113 floor receipts."""
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
        assert threading.current_thread().name == 'MainThread'
        adapter = integration._CTX.adapter
        adapter.check_snapshot(adapter._inspect(adapter.objects))          # conditioning-<stage>-before
        out = native_call(vae=vae, image=self.anchor, latent=latent, strength=1.0, bypass=False).result[0]
        adapter.check_snapshot(adapter._inspect(adapter.objects))          # conditioning-<stage>-after
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
manifest = {'files': {'source/scripts/ltx_duration_guard.py': sha((MODS / 'ltx_duration_guard.py').read_bytes()),
                      'resolution/reference-frame-hashes.json': sha(_REFERENCE)},
            'runtime': {'files': {}}}
(RUN / 'server-identity.json').write_text(json.dumps({'source_packet_manifest_sha256': MANIFEST_SHA}))
integration.RESERVE_BYTES = 0
integration.run_storage.RESERVE_BYTES = 0  # CPU tmpfs fixture only; production remains 50 GiB
rt = integration.Runtime(PACKET, manifest, MANIFEST_SHA, RUN)
integration._CTX = rt
rt._xpu3_free = lambda: 13 * GIB
rt._install_decoder_graph = lambda torch_module: DG
rt._install_cone = lambda torch_module: CONE


class FakeDisplayReplica:
    def __init__(self):
        self.calls = 0
    def decode(self, latent):
        import display_replica
        free = (5 if args.inject == 'replica-floor' else 12) * GIB
        display_replica.budget(free, transient_bytes=display_replica.transient_bytes(args.frames))
        images = fake_images(latent, CURRENT_DECODE.name)
        name = CURRENT_DECODE.name
        if args.inject == 'replica-diff' or (args.inject == 'replica-repeat-diff' and 'qrepeat-c000001' in name):
            images[0, 0, 0, 0] += 0.001
        if args.inject == 'replica-live-diff' and 's00000001' in name:
            images[-1, 0, 0, 0] += 0.001
        self.calls += 1
        return images
    def receipt(self):
        import display_replica
        return {'device': 'xpu:2', 'resident_bytes': 834268000, 'encoder_bytes': 0, 'graph_pool_bytes': 0,
                'transient_budget_bytes': display_replica.transient_bytes(args.frames), 'floor_bytes': 2*GIB,
                'before_install': display_replica.budget(12*GIB, 834268000, display_replica.transient_bytes(args.frames)),
                'after_install': display_replica.budget(11*GIB, transient_bytes=display_replica.transient_bytes(args.frames)), 'calls': self.calls,
                'last_decode': {'before': display_replica.budget(11*GIB, transient_bytes=display_replica.transient_bytes(args.frames)), 'after_free_bytes': 8*GIB, 'seconds': 0.1,
                                'allocator_before': {'allocated': 1, 'reserved': 2, 'peak_allocated': 2},
                                'allocator_after': {'allocated': 1, 'reserved': 2, 'peak_allocated': 2},
                                'observed_peak_or_reservation_growth_bytes': 1, 'peak_is_device_global_not_reset': True},
                'weight_copy_bitwise_equal': True, 'native_seed': 0, 'dtype': 'torch.bfloat16',
                'single_decode_thread': True}
rt._install_display_replica = lambda torch_module, name: FakeDisplayReplica()


class FakeSafety:
    failed, closed = None, False
    expected_residence = {role: 'r' * 64 for role in ('text_secondary', 'video_vae', 'audio_vae')}


SAFETY = FakeSafety()
SAFETY.objects = {'video_vae': VAE, 'audio_vae': AUDIO_VAE}
VAE._ltx_native_reference_safety = AUDIO_VAE._ltx_native_reference_safety = SAFETY
SNAP_CALLS = []


def _xpu3_guard(torch_module):
    import precompute_guard as pg

    def free(card):
        SNAP_CALLS.append(card)
        if args.inject == 'pre-floor' and len(STATS['encodes']) > 6:
            return 8 * GIB
        return 13 * GIB
    return pg.Xpu3Snapshot(controller=SAFETY,
                           phase_ok=lambda: auth.failed is None and auth.phase in ('stream_qualification', 'stream'),
                           fault=rt.fault, synchronize=lambda card: SNAP_CALLS.append('sync:' + card),
                           free_bytes=free, counters=lambda card: {'allocated': 1, 'reserved': 2, 'peak': 3},
                           rows=lambda role: [role], fingerprint=lambda rows: 'r' * 64)


rt._xpu3_guard = _xpu3_guard
_real_decode_job = rt._decode_job


def decode_job(job):
    CURRENT_DECODE.name = job['run_name']
    record = _real_decode_job(job)
    if isinstance(record, integration.stream_decode.DeferredDisplay):
        finish = record.finish
        def finish_on_display_thread():
            CURRENT_DECODE.name = job['run_name']
            return finish()
        return integration.stream_decode.DeferredDisplay(finish_on_display_thread)
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
        N.LTXStreamPrepare116().apply(name)
        return
    out = graph['stream_output']['inputs']
    params = {k: out[k] for k in ('kind', 'frames', 'placement', 'anchor', 'decoder_graph', 'anchor_decode',
                                  'bencode_overlap', 'prep_ahead', 'scene_id', 'chunk_index',
                                  'seed', 'stream_seq', 'predecessor_anchor_sha256', 'reuse_text')}
    params['reset'] = out.get('reset', 0)
    prompt = graph['stream_text']['inputs']['text']
    cond = None
    if '364' in graph:
        event(pid, '364')
        cond = fake_text(prompt)
    cond = N.LTXStreamText116().apply(name, prompt, conditioning=cond)[0]
    cond_a = cond_b = cond
    lat_a = {'samples': torch.zeros(G['stage_shapes']['A'])}
    anchored = 'stream_anchor' in graph
    mode = args.anchor
    if anchored:
        if mode in ('latent', 'mixed'):
            anchor_a, anchor_b = N.LTXStreamLatentAnchor116().apply(name, params['predecessor_anchor_sha256'])
            lat_a = N.LTXStreamLatentCondition116().apply(lat_a, anchor_a, 1.0, name, 'A')[0]
        elif mode == 'guide':
            guide_a, guide_b = N.LTXStreamGuideAnchor116().apply(name, params['predecessor_anchor_sha256'])
            cond_a, neg_a, lat_a = N.LTXStreamGuide116().apply(cond, cond, VAE, lat_a, guide_a, 1.0, name, 'A')
        else:
            image = N.LTXStreamAnchor116().apply(name, params['predecessor_anchor_sha256'])[0]
            lat_a = N.LTXStreamCondition116().apply(VAE, image, lat_a, 1.0, False, name, 'A')
    event(pid, '344')
    va, aa = sample(lat_a, params['seed'], cond_a, 'A')
    stage_a = {'samples': va, 'noise_mask': lat_a['noise_mask']} if 'noise_mask' in lat_a else {'samples': va}
    event(pid, '367')
    if anchored and mode == 'guide':
        event(pid, 'stream_crop_a')
        stage_a = N.LTXStreamCropGuides116().apply(cond_a, neg_a, stage_a, name, 'A')[2]
    event(pid, '348')
    aux_before = residency123.guard_aux(torch, 'upsampler', True, args.aux_residency)
    up = {'samples': torch.randn(G['stage_shapes']['B'], generator=gen('up', tsha(stage_a['samples'])))}
    aux_after = residency123.guard_aux(torch, 'upsampler', False, args.aux_residency)
    if args.aux_residency == 'xpu2':
        PATCHERS['upsampler']._ltx123_aux_workspace = {'before': aux_before, 'after': aux_after}
    lat_b = up
    if anchored:
        event(pid, 'stream_condition_b')
        if mode == 'latent':
            lat_b = N.LTXStreamLatentCondition116().apply(up, anchor_b, 1.0, name, 'B')[0]
        elif mode == 'mixed':
            lat_b = N.LTXStreamFrameConditionB116().apply(VAE, up, 1.0, False, name)
        elif mode == 'guide':
            cond_b, neg_b, lat_b = N.LTXStreamGuide116().apply(cond, cond, VAE, up, guide_b, 1.0, name, 'B')
        else:
            lat_b = N.LTXStreamCondition116().apply(VAE, image, up, 1.0, False, name, 'B')
    event(pid, '340')
    event(pid, '368')
    vb, ab = sample(lat_b, params['seed'], cond_b, 'B')
    stage_b = {'samples': vb, 'noise_mask': lat_b['noise_mask']} if 'noise_mask' in lat_b else {'samples': vb}
    event(pid, '369')
    if anchored and mode == 'guide':
        event(pid, 'stream_crop_b')
        stage_b = N.LTXStreamCropGuides116().apply(cond_b, neg_b, stage_b, name, 'B')[2]
    event(pid, 'stream_output')
    N.LTXStreamChunk116().apply({'samples': stage_b['samples']}, {'samples': ab}, {'samples': stage_a['samples']},
                                VAE, AUDIO_VAE, name, **{k: v for k, v in params.items()})

summary = {'frames': args.frames, 'anchor': args.anchor, 'reuse': args.reuse, 'inject': args.inject,
           'decoder_graph': args.decoder_graph, 'levers': list(LEVERS)}
EXEC_START = {}
try:
    for r in c.setup_graphs():
        execute(r['graph'])
    for p in c.qualification_params(args.frames, args.reuse, args.placement, args.anchor, args.decoder_graph,
                                    *LEVERS):
        execute(c.build_chunk_graph(p))
        time.sleep(args.client_delay)
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
                                     reset=reset, anchor=args.anchor, decoder_graph=args.decoder_graph,
                                     anchor_decode=LEVERS[0], bencode_overlap=LEVERS[1], prep_ahead=LEVERS[2])
            try:
                stream_names.append(execute(c.build_chunk_graph(params)))
            except Exception as error:
                summary['stream_error'] = repr(error)[:300]
                break
            time.sleep(args.client_delay)
            if args.inject in ('decode-fail', 'audio-fail'):
                time.sleep(2 * args.decode_delay + args.audio_delay + 0.3)    # let the failing decode reach its latch
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
               'preview_record': prec.is_file(), 'timing_s': receipt['timing_s'],
               'timing_ns': receipt['timing_ns'], 'decode_state': receipt['decode']['state'],
               'decoder_graph': receipt['decoder_graph'], 'levers': receipt['levers'],
               'conditioning_sources': receipt['conditioning_sources'],
               'anchor_read_source': receipt.get('anchor_read_source'),
               'snapshots': receipt['snapshots'], 'server_options': receipt['server_options'],
               'authority_checks': receipt['authority_checks'], 'turnaround': receipt['turnaround'],
               'node_starts': sorted(receipt['node_starts_ns'])}
        if drec.is_file():
            d = rec.validate_decode_record(json.loads(drec.read_text()), receipt)
            row['decode_sequence'] = d['sequence']
            row['decode_timing_ns'] = d['timing_ns']
            row['decoder'] = d['decoder']
            row['display_replica'] = d['display_replica']
            row['display_device'] = d['display_device']
            row['display_worker'] = d.get('display_worker')
            row['completion_worker'] = d.get('completion_worker')
            row['display_worker_timing'] = d.get('display_worker_timing')
            row['decode_timing_s'] = d['timing_s']
            row['decoded_tensors'] = d['tensors']
            row['anchor_decode'] = d['anchor_decode']
            row['precompute'] = d['precompute']
            row['schedule'] = d['schedule']
            row['sharpness_frames'] = d['sharpness']['frames']
            row['last_frame_sha256'] = d['last_frame_sha256']
        if prec.is_file():
            p = rec.validate_preview_record(json.loads(prec.read_text()), receipt)
            raw = Path(p['path']).read_bytes()
            assert sha(raw) == p['sha256'] and len(raw) == p['bytes']
            row['preview_timing_ns'] = p['timing_ns']
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
    summary['decoder_graph_state'] = DG.receipt()
    summary['cone_state'] = CONE.receipt()
    summary['encodes'] = STATS['encodes']
    summary['concurrent_encodes'] = STATS['concurrent_encodes']
    summary['display_after_go'] = STATS['display_after_go']
    summary['snap_calls'] = sorted(set(SNAP_CALLS))
    summary['native_call_threads'] = sorted(set(rt.bindings.native_calls)) if rt.bindings is not None else []
    summary['precompute_store'] = rt.precompute.summary()
    summary['snapshot_state'] = rt.inspector.summary()
    summary['walk_calls'] = SNAP_STATE['walk_calls']
    summary['latch'] = ((ROOT / 'decoder-graph-116-refused.json').read_text()
                        if (ROOT / 'decoder-graph-116-refused.json').exists() else None)
    summary['verdict_file'] = (json.loads((RUN / 'stream-qualification-verdict.json').read_text())
                               if (RUN / 'stream-qualification-verdict.json').exists() else None)
    if args.anchor == 'frame' and args.inject == 'none' and len(stream_names) > 1:
        import stream_schedule_gate
        live_receipts = [json.loads((RUN / 'receipts' / ('receipt-' + n + '.json')).read_text())
                         for n in stream_names[:-1]]
        live_decodes = [json.loads((RUN / 'receipts' / ('decode-' + n + '.json')).read_text())
                       for n in stream_names[:-1]]
        summary['live_schedule_gate'] = stream_schedule_gate.check(live_receipts, live_decodes)
except Exception as error:
    import traceback
    summary['error'] = traceback.format_exc()[-3000:]
    summary['halted'] = auth.failed
    summary['run_files'] = sorted(x.name for x in RUN.iterdir() if x.is_file())
    summary['latch'] = ((ROOT / 'decoder-graph-116-refused.json').read_text()
                        if (ROOT / 'decoder-graph-116-refused.json').exists() else None)
finally:
    summary['lever_latches'] = {name: json.loads((ROOT / name).read_text()) for name in
                                ('anchor-decode-118-refused.json', 'precompute-118-refused.json',
                                 'snapshot-118-refused.json', 'display-replica-120-refused.json')
                                if (ROOT / name).exists()}
    rt.decoder.close()
    rt.preview.close()
    if rt.storage_scan_mode == 'background':
        rt.storage_background.close()
    shutil.rmtree(TMP, ignore_errors=True)
print(json.dumps(summary, default=str))

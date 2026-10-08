#!/usr/bin/env python3
"""Exact sealed-115 successor assembly for packet116. Default inventories; --build is explicit.

Installed in the packet as launch/encoder_runtime_common.py. Packet116 is the sealed
packet115 with replaced stream components (the frame anchor by default; 116a scheduling, in
which the chain waits only for its video decode and the anchor file; the decoder-graph
experiment `stream_decoder_graph.py` behind LTX_DECODER_GRAPH; the cross-packet reference
hashes; `stream116-` names), the geometry/capture-guard literals that name the plan, the
qualification ids and the prewrite schema, and the launcher literals that name the packet.
Every other file is copied byte-for-byte from 115 (which is itself verified against 114, 113,
112 and 111 at load and at launch). Reading the sealed packets needs no process action. This
builder never contacts an endpoint, imports Torch or touches a device. Changed parent files
survive under provenance/packet115/.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-continuation-stream-115'
PARENT_SHA = 'a934bac2ba8f9673f98f7b1186919d341c74b10e54f308979ca9cff5ef4c7137'
PACKET = ROOT / 'prepared-continuation-stream-116'
FRAMES = ('49', '97')
PLACEMENTS = ('two-way', 'two-way20-28')
ANCHORS = ('mixed', 'latent', 'frame', 'guide')
DECODER_GRAPH = ('0', '1')
RUN_NAMES = {'%s/%s/%s/dg%s' % (f, p, a, d): 'encoder-server-continuation-stream-116-%s-dg%s-%s-w1-b1-p1-dxpu2-s256x256-f%s'
             % (a, d, p, f) for f in FRAMES for p in PLACEMENTS for a in ANCHORS for d in DECODER_GRAPH}
AUTHOR = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation116-stream')
REFERENCE_SOURCE = 'reference-frame-qualification-hashes.json'
REFERENCE_PATH = 'resolution/reference-frame-hashes.json'
DECODER_GRAPH_LATCH = 'decoder-graph-116-refused.json'   # = stream_decoder_graph.LATCH_NAME
PLAN = AUTHOR / 'stream-plan.json'
PLAN_SHA = 'af735204558fb7fad0a9814858208b1be2d7e3b7c9379f456ea09d6c1d829a98'
PARENT_PLAN_SHA = 'c5b94b1ec73eb048a4cd6d1d6829d77d9a60e8da819490b3c3d4e8934ce2c689'
PARENT_QIDS = {
    '49/two-way/frame': 'be3685134f9f764bc330db359c2afc2ebaa294fff823aa1e7a7726b8ddeff4da',
    '49/two-way/guide': '989ec19702321071d84da42e76da761ce6c54706faa3ffbdc543b37e44030fb5',
    '49/two-way/latent': '809eb997bd0f801f7dd4e5c509d3f9909d609d496300b58468558c0f207214dd',
    '49/two-way/mixed': 'da5873b07ca69f5eb83ed11493daa0262ae66a9ae62e2fb44ee03d502b405445',
    '49/two-way20-28/frame': 'c16a3ad5f381a2190c635bc1275e87c1a6fe23fac1de025f04d8cbaeba459858',
    '49/two-way20-28/guide': '22950b412f16444ee1a453769178aedaea84d3ee5a2b541e93b0de1fcb11e61b',
    '49/two-way20-28/latent': '9d616e607f132a274b9ed93a02419089cd871857e3172713eead5c9f74c16633',
    '49/two-way20-28/mixed': '6e27770b1782f2dfa8692443e15b8d3ec89dc3efad2a20f96bb6d14f2de21f8b',
    '97/two-way/frame': '30511cfe1371acad43081bf588a09287b3828eb7d33781d174871149aa7a1e75',
    '97/two-way/guide': 'dc5fcea3b8c3cc5407fddc5adc1a3394ed30106857b8cd02702396a0a9f393eb',
    '97/two-way/latent': '744298bb0111cbd598e355713addc9a1d662cdbfcbe2be60134ad9c1deb98ec2',
    '97/two-way/mixed': '7786c2a49820a11b1c99b64380e99528ea1885d9b970f34f284c7da4816eac2b',
    '97/two-way20-28/frame': 'edc3f8a0d5bf9034fc444e5a3daec9a16a8b3e8fb93e3956ca2cfe9cdca8070c',
    '97/two-way20-28/guide': 'e635827df76f79dc757e5eefd68b6d2f7d49c321cf2e031319f62c7670cdadd1',
    '97/two-way20-28/latent': '126c43938785a87a1e925dbb2a763dce808704265c154ec6ac47ce6b2750dfd7',
    '97/two-way20-28/mixed': '5618f90760303be889a0281a5a0bce4b7738fcc66ce2d74f353153a53953b367',
}
QIDS = {
    '49/two-way/frame/dg0': '8698eb1e41f19b85e6a9d8250d2603d9c21f1656cffffdcad79df8d37407f826',
    '49/two-way/frame/dg1': '9113ae3533b3025b6c7c7a8c9e5b94ce6d4cc357c444affd808f8db5857e0c3f',
    '49/two-way/guide/dg0': '2bf9bcf986ac29a3fb2c1eb83f418015d4880ab3c594dff6be3935abd81c9d8f',
    '49/two-way/guide/dg1': '850d63b909af1f608611c30b055fb7f8e10a3cb8b82ca34e20a579a0afaa5754',
    '49/two-way/latent/dg0': '00833111380fc3f6cd7091da771e904313fc4db986d4894aebc2d4e0cb77e5bd',
    '49/two-way/latent/dg1': '213e7d641531c9015057b8ed9b93e6410e5fe64465ecfbf6857a94d317045a81',
    '49/two-way/mixed/dg0': '15be4ac341ba0c59b1b2ab4b0221a95c1fb7836999ff273f780028994d371a55',
    '49/two-way/mixed/dg1': '831161b7921180110ffff94f168c72438e2304e3cf8fd1ef42ecb9a9e13abae6',
    '49/two-way20-28/frame/dg0': 'd10b958d05594d315d77380a7f7ad9ecfb3ab690fd1ad21ed5d527975b10d843',
    '49/two-way20-28/frame/dg1': '73ea22cf8e6bb65337137a5f7207f0fbac92672cc695db914a8ed7db48431645',
    '49/two-way20-28/guide/dg0': '48617a1112196b9dade15305c02ec1925578043e7fa90b01fc5d3f48e8cacf99',
    '49/two-way20-28/guide/dg1': 'cc093ff4a721c51c49e1c12ea886b5200dd46bfd4e0ff2eac9177c941cb18d48',
    '49/two-way20-28/latent/dg0': '54c2ba1ba98b389674cbec53ef691625f7782a6a74608e4ea7593de86ceec9f3',
    '49/two-way20-28/latent/dg1': '78238ad2b75d0c53bd36f5bfcae928ef5ef677e26d8cc6f5d8a9c1db903a6f44',
    '49/two-way20-28/mixed/dg0': 'bb680104facef7b24041f3af906fdea2aa2655d293f74e0aeb7a96c71fd49cfa',
    '49/two-way20-28/mixed/dg1': 'ed6c53782025791ed9be12ef58107af6f61c263231ac7ea9e9e515f4882f70cd',
    '97/two-way/frame/dg0': 'e3abe14024238c11ac16155b8d04815be05fff168ce162dd97351a31bd33d759',
    '97/two-way/frame/dg1': '041daf8e17ea2e754ef7a82473e292068bc6a8e1d3bf8cd197b51c1b7662819b',
    '97/two-way/guide/dg0': 'dba0e530889d8b65470f2dbc2d71589b8772f43a447d8539cc72667677de15dd',
    '97/two-way/guide/dg1': '62d41fd98c9f9ef3205e0fd85edf3d4958e2b2461592719bcc104416a7ea5b51',
    '97/two-way/latent/dg0': 'c69663708e14c73ae1fa2837ba9ca7fe87d08a9ccd8157ab2b3ff1bb4b68ebc6',
    '97/two-way/latent/dg1': '00552a54ff5aec8e389f5cb9a312f03e2cb1ceb3974efa7fe5ede4e0d16590d0',
    '97/two-way/mixed/dg0': '5b45859e2a9b2b7e34fc47906bcf986ebe521158ab9cf0907efc5efd4a3cd5ce',
    '97/two-way/mixed/dg1': '983afbf868eaceb851f3042cb823e62d6fbce8c5bf1c007699fed14cafb94992',
    '97/two-way20-28/frame/dg0': '79d7ab8c8c846dd9dd72974a9c5f09215644a154498d01ae7fd11f471a3489e7',
    '97/two-way20-28/frame/dg1': '2b63b6c759a856b7eb6738dd88547e9b06f897ae786279f194bb842811ed6fec',
    '97/two-way20-28/guide/dg0': '1c1788afef7dab853d251e69c3e557163d387628227c3fc2cdd9872654f5170a',
    '97/two-way20-28/guide/dg1': 'd15f79c84790521a06db2fedbf71a0c8415df2f9d30307dc74c8f4e9c5fa9cdc',
    '97/two-way20-28/latent/dg0': '874d316fdc308cc7a42bba35db38206795db4e5e770ae925090f819006d13201',
    '97/two-way20-28/latent/dg1': 'e46073b6403b6dbdcf2a805b9d6c1f80c4ed879935e528a0318329942d19eb52',
    '97/two-way20-28/mixed/dg0': '3e504ed3c105e52436f28b6768f91c771511ba5dca11aa37620930cfa3269c73',
    '97/two-way20-28/mixed/dg1': '7417c17285e742f78461dd8bcb79b7b38f68aba99a64dd8023032a206c930217',
}
COMMON, LAUNCHER = 'launch/encoder_runtime_common.py', 'launch/serve-encoder.py'
STATUS = (b'Packet116 = packet115 256x256 continuation stream with the frame anchor by default (packet113 '
          b'semantics, sharp seams), 116a scheduling (the chain waits only for the video decode and the anchor '
          b'file; audio, hashing, record and preview follow on the decode thread), and the decoder-graph '
          b'experiment (LTX_DECODER_GRAPH, default 1: graph replay of the NA diffusion decoder with bounded '
          b'device-resident caches, qualified by byte identity against the uncached eager decode; a mismatch '
          b'latches and the launcher then refuses the graph mode); mixed, latent and guide anchors kept for A/B; '
          b'49- or 97-frame chunks, text reuse on; nine-capture exact qualification plus the packet-113/114 '
          b'frame references gate streaming; not GPU-qualified.\n')
COMPONENTS = ('session.py', 'integration.py', 'stream_contract.py', 'stream_receipts.py', 'stream_preview.py',
              'stream_decode.py', 'latent_anchor.py',
              'qualification_gate.py', 'candidate_safety.py', 'conditioning_guard.py',
              'native_bindings.py', 'continuation_anchor.py', 'stream_decoder_graph.py',
              'qualify_client.py', 'plan.py', 'derive_from_111.py', 'runtime_packet.py')
MODULES = {n: ('ltx_resolution_session.py' if n == 'session.py' else n) for n in COMPONENTS
           if n not in ('qualify_client.py', 'plan.py', 'derive_from_111.py', 'runtime_packet.py')}
NAME_DIRECTORIES = ('output', 'output/validation', 'requests')
GIB, MIB = 2 ** 30, 2 ** 20
RESERVE = 50 * GIB
BUILD_ALLOWANCE = 160 * MIB
RUN_ALLOWANCE = 3 * GIB
CONTROL_ENVIRONMENT = {
    'LTX_OUTPUT_SIZE': '256x256', 'LTX_BUSY_WINDOWS': '0',
    'LTX_SAMPLER_WORKERS': '1', 'LTX_SAMPLER_BATCH': '1', 'LTX_SAMPLER_SHARED_POOL': '1',
    'LTX_DECODE_REPLICA_DEVICE': 'xpu:2', 'LTX_DECODE_REPLICAS': '1',
    'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0'}


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_parent_raw = (PARENT / 'manifest.json').read_bytes()
require(digest(_parent_raw) == PARENT_SHA, 'Sealed115 parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
require(digest((PARENT / COMMON).read_bytes()) == _parent_manifest['files'][COMMON], 'Sealed115 checker changed')
BASE = load(PARENT / COMMON, 'stream116_parent115')
regular, sha, safe_path, module = BASE.regular, BASE.sha, BASE.safe_path, BASE.module
NODES = list(BASE.NODES)


def __getattr__(name):
    return getattr(BASE, name)


def replace(raw, old, new, count=1):
    text = raw.decode() if isinstance(raw, bytes) else raw
    require(text.count(old) == count, 'Source anchor count differs: ' + repr(old[:90]))
    return text.replace(old, new)


# -- launch-time overrides (used by the sealed launcher through this module) ------
def decoder_graph_latch(root=ROOT):
    """Packet116: the decoder-graph latch a mismatch or refused capture wrote (None when absent)."""
    path = Path(root) / DECODER_GRAPH_LATCH
    return str(path) if path.exists() or path.is_symlink() else None


def check_control_environment(root=ROOT):
    require(all(os.environ.get(k) == v for k, v in CONTROL_ENVIRONMENT.items()),
            'Explicit packet116 environment differs: ' + json.dumps(CONTROL_ENVIRONMENT, sort_keys=True))
    require(os.environ.get('LTX_DECODER_GRAPH') in DECODER_GRAPH, 'LTX_DECODER_GRAPH must be set to 0 or 1')
    require(os.environ.get('LTX_BENCODE_OVERLAP', '0') == '0',
            'LTX_BENCODE_OVERLAP=1 is not implemented in packet116 (the conditioning guard snapshots all four '
            'cards on the prompt thread); unset it or set 0')
    latch = decoder_graph_latch(root)
    require(os.environ.get('LTX_DECODER_GRAPH') == '0' or latch is None,
            'Decoder-graph latch present (%s): a decoder-graph mismatch or refused capture was recorded; relaunch '
            'with LTX_DECODER_GRAPH=0, or archive the latch after an owner review' % latch)
    require(os.environ.get('LTX_STREAM_TEXT_REUSE') in ('0', '1'), 'LTX_STREAM_TEXT_REUSE must be set to 0 or 1')
    require(os.environ.get('LTX_STREAM_FRAMES') in FRAMES, 'LTX_STREAM_FRAMES must be set to 49 or 97')
    require(os.environ.get('LTX_SAMPLER_PLACEMENT') in PLACEMENTS,
            'LTX_SAMPLER_PLACEMENT must be set to two-way or two-way20-28')
    require(os.environ.get('LTX_ANCHOR') in ANCHORS, 'LTX_ANCHOR must be set to mixed, latent, frame or guide')


def expected_run_name(environ=None):
    environ = os.environ if environ is None else environ
    return RUN_NAMES.get('%s/%s/%s/dg%s' % (environ.get('LTX_STREAM_FRAMES'), environ.get('LTX_SAMPLER_PLACEMENT'),
                                           environ.get('LTX_ANCHOR'), environ.get('LTX_DECODER_GRAPH')))


def name_collisions(names, prefix, root=ROOT):
    """Entries under output/, output/validation/ and requests/ that a packet116 server would collide with."""
    found = []
    for directory in NAME_DIRECTORIES:
        path = Path(root) / directory
        if not path.exists():
            continue
        require(path.is_dir() and not path.is_symlink(), 'Name directory is not a plain directory: ' + str(path))
        for entry in sorted(os.listdir(path)):
            if entry in names or entry.startswith(prefix):
                found.append(directory + '/' + entry)
    return found


def check_name_collisions(packet, root=ROOT):
    """Launcher preflight (also in --check-only): refuse when any setup/qualification name, or any
    entry with the packet's stream prefix, already exists where the server creates names."""
    contract = module(Path(packet) / 'resolution/components/stream_contract.py', 'stream116_names')
    names, prefix = set(contract.fixed_names()), contract.RUN_PREFIX + '-'
    require(prefix == 'stream116-' and all(n.startswith(prefix) for n in names), 'Packet116 name prefix differs')
    found = name_collisions(names, prefix, root)
    require(not found, 'Packet116 names already exist (archive them first): ' + ', '.join(found[:12]) +
            (' and %d more' % (len(found) - 12) if len(found) > 12 else ''))
    return {'checked': list(NAME_DIRECTORIES), 'fixed_names': sorted(names), 'prefix': prefix, 'collisions': []}


def admit_storage(packet, run):
    helper = module(packet / 'launch/check-storage-headroom.py', 'stream116_storage')
    result = helper.inspect_destination(run, RESERVE, RUN_ALLOWANCE)
    require(result['admitted'], '50GiB reserve plus 3GiB stream allowance required')
    return result


# -- source transforms (applied to the sealed 115 files) ----------------------------
def geometry_source(raw, plan_sha, qids):
    """115's ltx_output_size_98.py: the 116 plan, ids keyed by frames/placement/anchor/decoder graph
    (defaults frame and 1), mode 116."""
    t = replace(raw, "_RESOLUTION_PLAN_SHA256 = '" + PARENT_PLAN_SHA + "'", "_RESOLUTION_PLAN_SHA256 = '" + plan_sha + "'")
    t = replace(t, "_RESOLUTION_QUALIFICATION_ID = " + repr(PARENT_QIDS) +
                "[_STREAM_FRAMES + '/' + os.environ.get('LTX_SAMPLER_PLACEMENT', 'two-way') + '/' + "
                "os.environ.get('LTX_ANCHOR', 'mixed')]",
                "_RESOLUTION_QUALIFICATION_ID = " + repr(qids) +
                "[_STREAM_FRAMES + '/' + os.environ.get('LTX_SAMPLER_PLACEMENT', 'two-way') + '/' + "
                "os.environ.get('LTX_ANCHOR', 'frame') + '/dg' + os.environ.get('LTX_DECODER_GRAPH', '1')]")
    t = replace(t, "_RESOLUTION_MODE = 'stream-candidate-115-v1'", "_RESOLUTION_MODE = 'stream-candidate-116-v1'")
    ast.parse(t)
    return t.encode()


def capture_guard_source(raw):
    """115's ltx_duration_guard.py: the 116 prewrite schema (shapes unchanged: 49 and 97 frames)."""
    t = replace(raw, "'ltx.stream115-prewrite.v1'", "'ltx.stream116-prewrite.v1'")
    ast.parse(t)
    return t.encode()


def launcher_source(raw):
    """115's serve-encoder.py: the packet name in two literals. The packet116 environment rules
    (LTX_DECODER_GRAPH, the decoder-graph latch, LTX_BENCODE_OVERLAP) live in check_control_environment,
    which the launcher already calls in prepare_start (launch and --check-only)."""
    t = replace(raw, "                   'Packet115 admits only the 256x256 continuation stream server')",
                "                   'Packet116 admits only the 256x256 continuation stream server')")
    t = replace(t, "    # Packet115 naming rule (the 113 naming incident): refuse before any device work, also in --check-only.\n",
                "    # Packet116 naming rule (the 113 naming incident): refuse before any device work, also in --check-only.\n"
                "    # Packet116: check_control_environment also refuses LTX_DECODER_GRAPH=1 while the decoder-graph latch\n"
                "    # exists and refuses LTX_BENCODE_OVERLAP=1 (not implemented).\n")
    ast.parse(t)
    return t.encode()


# -- assembly -------------------------------------------------------------------
def check_plan(raw):
    envelope = json.loads(raw)
    require(envelope['plan_sha256'] == PLAN_SHA == digest(canonical(envelope['plan'])) and
            envelope['plan']['qualification_ids'] == QIDS, 'Reviewed116 plan changed')
    return envelope['plan']


def input_inventory():
    files = {n: sha(AUTHOR / n) for n in COMPONENTS}
    check_plan(regular(PLAN))
    files['stream-plan.json'] = sha(PLAN)
    files[REFERENCE_SOURCE] = sha(AUTHOR / REFERENCE_SOURCE)
    return files


def check_reference(raw):
    value = json.loads(raw)
    require(value.get('schema') == 'ltx.stream116.reference-frame-hashes.v1' and
            set(value.get('variants', {})) == {'49/two-way20-28/frame', '97/two-way20-28/frame'} and
            all(len(v['chunks']) == 3 and v['verdict_passed'] is True for v in value['variants'].values()),
            'Reference hash document differs')
    return raw


def successor_files(component_dir, plan_raw, reference_raw):
    check_plan(plan_raw)
    result = {'provenance/packet115-manifest.json': regular(PARENT / 'manifest.json'),
              'resolution/stream-plan.json': plan_raw, REFERENCE_PATH: check_reference(reference_raw)}
    require(digest(result['provenance/packet115-manifest.json']) == PARENT_SHA, 'Parent manifest changed')
    for name in COMPONENTS:
        raw = regular(component_dir / name)
        ast.parse(raw)
        result['resolution/components/' + name] = raw
        if name in MODULES:
            result['source/scripts/' + MODULES[name]] = raw
    result[COMMON] = regular(component_dir / 'runtime_packet.py')
    result[LAUNCHER] = launcher_source(regular(PARENT / LAUNCHER))
    result['source/scripts/ltx_output_size_98.py'] = geometry_source(
        regular(PARENT / 'source/scripts/ltx_output_size_98.py'), PLAN_SHA, QIDS)
    result['source/scripts/ltx_duration_guard.py'] = capture_guard_source(
        regular(PARENT / 'source/scripts/ltx_duration_guard.py'))
    # Components identical to the sealed 115 copies are not 'changed' (they stay inherited).
    for path in [p for p in result if p in _parent_manifest['files']]:
        if digest(result[path]) == _parent_manifest['files'][path]:
            del result[path]
    for path, raw in result.items():
        if path.endswith('.py'):
            ast.parse(raw)
    return result


def manifest_files(parent, changed):
    files = dict(parent['files'])
    for path, raw in changed.items():
        if path in parent['files']:
            files['provenance/packet115/' + path] = parent['files'][path]
        files[path] = digest(raw)
    return files


def transition(parent, changed, inventory, admission):
    return {'schema': 'ltx.stream116.transition.v1', 'packet_revision': '116',
            'parent_packet': str(PARENT), 'parent_manifest_sha256': PARENT_SHA,
            'plan_sha256': PLAN_SHA, 'qualification_ids': QIDS, 'input_inventory': inventory,
            'input_inventory_sha256': digest(canonical(inventory)),
            'source_delta': {p: {'before_sha256': parent['files'].get(p), 'after_sha256': digest(raw)}
                             for p, raw in changed.items()},
            'control': {'size': '256x256', 'frame_count': 'LTX_STREAM_FRAMES (49 or 97; launched at 49 first)',
                        'fps': 24, 'layout': 'LTX_SAMPLER_PLACEMENT (two-way or two-way20-28; launched two-way20-28)',
                        'anchor': 'LTX_ANCHOR (frame default = packet113 decoded-frame anchor at both stages; '
                                  'mixed = stage A latent anchor + stage B decoded-frame anchor; guide = native latent '
                                  'guide of the last two latents; latent = packet114)',
                        'workers': 1, 'batch': 1, 'shared_pool': 1,
                        'decode_replica_env': 'xpu:2 (environment only; native VAEDecode, zero replicas)',
                        'decoder_graph_capture': 'LTX_DECODER_GRAPH (1 default): forward_pre_diffusion and '
                                                 'forward_diff_step graph replay on xpu:3, one shared pool, bounded '
                                                 'rope/axis-mask/noise caches; qualified by byte identity against the '
                                                 'uncached eager decode; latch file refuses graph mode after a mismatch',
                        'decode': 'one ordered decode thread on xpu:3, bounded FIFO, back-pressure, latch; '
                                  'frame and mixed: writes the frame anchor; frame (116a): the chain waits for the '
                                  'video decode and the anchor file only; sharpness profile per chunk',
                        'bencode_overlap': 'LTX_BENCODE_OVERLAP not implemented (launcher refuses 1)',
                        'mixed_wait': 'stage-B condition node waits (bounded 300 s) for the predecessor decode',
                        'preview': 'one bounded FIFO writer thread behind the decode thread',
                        'chain_reset': 'stream chunk reset=1 is unanchored (stream_seq 0 form)',
                        'graph_replay': 'LTXGraphCaptureGate all48 chain1', 'qualification_requests': 9,
                        'full_captures': 9, 'stream_requests': 'unbounded, serial, storage-bounded',
                        'environment': CONTROL_ENVIRONMENT, 'text_reuse_env': 'LTX_STREAM_TEXT_REUSE (1 default)',
                        'names': 'stream116- prefix; launcher refuses existing names (also --check-only)',
                        'reference_hashes': REFERENCE_PATH,
                        'stage_overlap_across_cards': 'not in 116'},
            'storage_admission': admission, 'qualification': False, 'model_requests': 0,
            'claims': {'quality_adopted': False, 'seam_accepted': False, 'audio_alignment_resolved': False,
                       'speed_improvement': False, 'decoder_graph_exact_on_xpu': False}}


def semantic_manifest(parent, files, change):
    result = copy.deepcopy(parent)
    result.update(schema='ltx.continuation-stream-runtime.v3', files=files,
                  preparer_sha256=files['resolution/components/runtime_packet.py'], resolution101=change)
    result['startup_tools'] = {Path(k).name: files[k] for k in (COMMON, LAUNCHER)}
    for name in list(result['extension_sha256s']):
        path = 'source/scripts/' + name
        if path in files:
            result['extension_sha256s'][name] = files[path]
    for name in MODULES.values():
        result['extension_sha256s'][name] = files['source/scripts/' + name]
    result['output_size']['module_sha256'] = files['source/scripts/ltx_output_size_98.py']
    result['output_size']['stream116'] = {'plan_sha256': PLAN_SHA, 'size': '256x256', 'frame_count': [49, 97],
                                          'anchor': list(ANCHORS), 'default_anchor': 'frame',
                                          'decoder_graph': [0, 1], 'default_decoder_graph': 1,
                                          'comparison_mode': 'stream-candidate-116-v1', 'qualified': False,
                                          'numerics_from': 'packet113 sampler/decoder (frame anchor); the decoder '
                                                           'graph must reproduce the uncached eager decode'}
    return result


def assembly_bytes(parent, changed):
    original = sum((PARENT / p).stat().st_size for p in parent['files'])
    return original + sum(len(raw) for raw in changed.values()) + len(STATUS)


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET and re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or ''),
            'Unexpected116 packet or manifest identity')
    require(sha(packet / 'manifest.json') == expected_manifest_sha256, '116 manifest changed')
    manifest = json.loads(regular(packet / 'manifest.json'))
    require(regular(packet / 'STATUS.txt') == STATUS, '116 status identity changed')
    require(type(manifest.get('files')) is dict, '116 file inventory missing')
    for path, expected in manifest['files'].items():
        require(type(path) is str and type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected)
                and sha(safe_path(packet, path)) == expected, '116 file changed before component import: ' + str(path))
    require(all('resolution/components/' + n in manifest['files'] for n in COMPONENTS),
            '116 component inventory incomplete')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(packet / 'resolution/components', regular(packet / 'resolution/stream-plan.json'),
                              regular(packet / REFERENCE_PATH))
    expected_files = manifest_files(parent, changed)
    require(manifest['files'] == expected_files, '116 source closure differs')
    checker_path = 'provenance/source99/check-upstream-source-99.py'
    require(sha(PARENT / checker_path) == parent['files'][checker_path], 'Inventory checker changed')
    checker = module(PARENT / checker_path, 'stream116_inventory')
    require(checker.inventory(packet) == set(expected_files) | {'manifest.json', 'STATUS.txt'},
            'Unbound116 packet file')
    inventory = {n: expected_files['resolution/components/' + n] for n in COMPONENTS}  # all bound
    inventory['stream-plan.json'] = expected_files['resolution/stream-plan.json']
    inventory[REFERENCE_SOURCE] = expected_files[REFERENCE_PATH]
    admission = manifest['resolution101']['storage_admission']
    require(admission['admitted'] is True, '116 build was not admitted')
    change = transition(parent, changed, inventory, admission)
    require(manifest == semantic_manifest(parent, expected_files, change), '116 semantic identity differs')
    return manifest


def write_new(path, raw, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
        os.fchmod(stream.fileno(), mode)
        stream.flush()
        os.fsync(stream.fileno())


def inspect_assembly():
    inventory = input_inventory()
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(AUTHOR, regular(PLAN), regular(AUTHOR / REFERENCE_SOURCE))
    require(input_inventory() == inventory, 'Authored inputs changed during assembly')
    amount = assembly_bytes(parent, changed)
    require(amount + 4 * MIB < BUILD_ALLOWANCE, 'Source assembly exceeds the build allowance')
    return {'status': 'source-assembly-checked', 'input_inventory': inventory,
            'input_inventory_sha256': digest(canonical(inventory)), 'source_payload_bytes': amount,
            'build_allowance_bytes': BUILD_ALLOWANCE, 'run_allowance_bytes': RUN_ALLOWANCE,
            'changed_files': {p: digest(raw) for p, raw in changed.items()},
            'materialized': False, 'model_requests': 0}


def build(expected_inventory_sha256):
    inspected = inspect_assembly()
    require(inspected['input_inventory_sha256'] == expected_inventory_sha256, 'Reviewed116 inputs differ')
    require(not PACKET.exists() and not PACKET.is_symlink() and
            not any(p.is_symlink() for p in PACKET.parents), 'Exclusive regular packet destination required')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(AUTHOR, regular(PLAN), regular(AUTHOR / REFERENCE_SOURCE))
    inventory = input_inventory()
    require(inventory == inspected['input_inventory'], 'Inputs changed after review')
    helper = module(PARENT / 'launch/check-storage-headroom.py', 'stream116_build_storage')
    admission = helper.inspect_destination(PACKET, RESERVE + RUN_ALLOWANCE, BUILD_ALLOWANCE)
    require(admission['admitted'], '50GiB reserve plus 3GiB run plus 160MiB build allowance required')
    PACKET.mkdir(mode=0o700)
    write_new(PACKET / 'STATUS.txt', STATUS)
    for path, expected in parent['files'].items():
        raw = regular(PARENT / path)
        require(digest(raw) == expected, 'Parent file changed while copying: ' + path)
        mode = stat.S_IMODE((PARENT / path).stat().st_mode)
        if path in changed:
            write_new(PACKET / 'provenance/packet115' / path, raw, mode)
            raw = changed[path]
        write_new(PACKET / path, raw, mode)
    for path, raw in changed.items():
        if path not in parent['files']:
            write_new(PACKET / path, raw)
    files = manifest_files(parent, changed)
    change = transition(parent, changed, inventory, admission)
    manifest = semantic_manifest(parent, files, change)
    write_new(PACKET / 'manifest.json', json.dumps(manifest, indent=2, sort_keys=True).encode() + b'\n')
    for directory in [p for p in PACKET.rglob('*') if p.is_dir()] + [PACKET, PACKET.parent]:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    manifest_sha = sha(PACKET / 'manifest.json')
    verify_packet(PACKET, manifest_sha)
    return {'status': 'prepared-not-GPU-qualified', 'packet': str(PACKET), 'manifest_sha256': manifest_sha,
            'input_inventory_sha256': expected_inventory_sha256, 'storage_admission': admission,
            'model_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--input-inventory-sha256')
    parser.add_argument('--inspect-assembly', action='store_true')
    parser.add_argument('--verify-manifest-sha256')
    args = parser.parse_args()
    require(sum((args.build, args.inspect_assembly, bool(args.verify_manifest_sha256))) <= 1, 'Select one operation')
    if args.build:
        result = build(args.input_inventory_sha256)
    elif args.inspect_assembly:
        result = inspect_assembly()
    elif args.verify_manifest_sha256:
        verify_packet(PACKET, args.verify_manifest_sha256)
        result = {'status': 'source-closure-verified', 'model_requests': 0}
    else:
        inventory = input_inventory()
        result = {'status': 'plan-only', 'packet': str(PACKET), 'input_inventory': inventory,
                  'input_inventory_sha256': digest(canonical(inventory)), 'materialized': False,
                  'model_requests': 0}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

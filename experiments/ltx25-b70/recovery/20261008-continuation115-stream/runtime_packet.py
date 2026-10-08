#!/usr/bin/env python3
"""Exact sealed-114 successor assembly for packet115. Default inventories; --build is explicit.

Installed in the packet as launch/encoder_runtime_common.py. Packet115 is the sealed
packet114 with replaced stream components (the mixed and guide anchor modes, mixed the
default; the decode thread's sharpness profile; the conditioning guard's stage-B-only
request; `stream115-` names), the geometry/capture-guard literals that name the plan,
the qualification ids and the prewrite schema, and the launcher literals that name the
packet. Every other file is copied byte-for-byte from 114 (which is itself verified
against 113, 112 and 111 at load and at launch). Reading the sealed packets needs no
process action. This builder never contacts an endpoint, imports Torch or touches a
device. Changed parent files survive under provenance/packet114/.
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
PARENT = ROOT / 'prepared-continuation-stream-114'
PARENT_SHA = '3e8b7abeb21fff903869907fd67c41128dd6179fa17fa441abdd5544468c97f3'
PACKET = ROOT / 'prepared-continuation-stream-115'
FRAMES = ('49', '97')
PLACEMENTS = ('two-way', 'two-way20-28')
ANCHORS = ('mixed', 'latent', 'frame', 'guide')
RUN_NAMES = {'%s/%s/%s' % (f, p, a): 'encoder-server-continuation-stream-115-%s-%s-w1-b1-p1-dxpu2-s256x256-f%s'
             % (a, p, f) for f in FRAMES for p in PLACEMENTS for a in ANCHORS}
AUTHOR = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation115-stream')
PLAN = AUTHOR / 'stream-plan.json'
PLAN_SHA = 'c5b94b1ec73eb048a4cd6d1d6829d77d9a60e8da819490b3c3d4e8934ce2c689'
PARENT_PLAN_SHA = 'e87c62149c1310617da15510ed71167c0fb9cceb52556d220ffca69f57949b5b'
PARENT_QIDS = {
    '49/two-way/frame': 'f1f0214eb35003db3f1a3c7485a9811fd900b0a946b785b91c073c77a577f5f1',
    '49/two-way/latent': '53d3e465e40f96358138a80eca86dc6e0c94109caa670e03745652954c936eb8',
    '49/two-way20-28/frame': '9cc374ee97d4d00d278f5a6c562ebf0d5da77331860ebc686a0106f818d64f1e',
    '49/two-way20-28/latent': 'd49c4874b23d5e03b545d123c44b7aedbd764e332e18e54d1eb47442fed577eb',
    '97/two-way/frame': 'a8b9f54441e6517d2e1717928ac2b812a14b6937868db9d494487ca2456196ab',
    '97/two-way/latent': 'ab1f02edeab2e88e6c885199daa51ce36b1690aedc0b6627e90e5531f1f5115a',
    '97/two-way20-28/frame': 'f213bfd0b228152e05fe36de935d705d5ddeaa7e717f08d003745f515da4562e',
    '97/two-way20-28/latent': 'd85b23d7b79386a05c42dce3a5d86d5d5df68af6fab2d8d16932eebdb07e3d52',
}
QIDS = {
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
COMMON, LAUNCHER = 'launch/encoder_runtime_common.py', 'launch/serve-encoder.py'
STATUS = (b'Packet115 = packet114 256x256 continuation stream with the mixed anchor by default (stage A on the '
          b'latent anchor, stage B on the decoded frame) and the latent-guide anchor as a launch option (latent '
          b'and frame kept for A/B), a per-chunk sharpness profile on the decode thread, 49- or 97-frame chunks '
          b'and text reuse on by default; nine-capture exact qualification gates streaming; not GPU-qualified.\n')
COMPONENTS = ('session.py', 'integration.py', 'stream_contract.py', 'stream_receipts.py', 'stream_preview.py',
              'stream_decode.py', 'latent_anchor.py',
              'qualification_gate.py', 'candidate_safety.py', 'conditioning_guard.py',
              'native_bindings.py', 'continuation_anchor.py', 'qualify_client.py', 'plan.py',
              'derive_from_111.py', 'runtime_packet.py')
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
require(digest(_parent_raw) == PARENT_SHA, 'Sealed114 parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
require(digest((PARENT / COMMON).read_bytes()) == _parent_manifest['files'][COMMON], 'Sealed114 checker changed')
BASE = load(PARENT / COMMON, 'stream115_parent114')
regular, sha, safe_path, module = BASE.regular, BASE.sha, BASE.safe_path, BASE.module
NODES = list(BASE.NODES)


def __getattr__(name):
    return getattr(BASE, name)


def replace(raw, old, new, count=1):
    text = raw.decode() if isinstance(raw, bytes) else raw
    require(text.count(old) == count, 'Source anchor count differs: ' + repr(old[:90]))
    return text.replace(old, new)


# -- launch-time overrides (used by the sealed launcher through this module) ------
def check_control_environment():
    require(all(os.environ.get(k) == v for k, v in CONTROL_ENVIRONMENT.items()),
            'Explicit packet115 environment differs: ' + json.dumps(CONTROL_ENVIRONMENT, sort_keys=True))
    require(os.environ.get('LTX_STREAM_TEXT_REUSE') in ('0', '1'), 'LTX_STREAM_TEXT_REUSE must be set to 0 or 1')
    require(os.environ.get('LTX_STREAM_FRAMES') in FRAMES, 'LTX_STREAM_FRAMES must be set to 49 or 97')
    require(os.environ.get('LTX_SAMPLER_PLACEMENT') in PLACEMENTS,
            'LTX_SAMPLER_PLACEMENT must be set to two-way or two-way20-28')
    require(os.environ.get('LTX_ANCHOR') in ANCHORS, 'LTX_ANCHOR must be set to mixed, latent, frame or guide')


def expected_run_name(environ=None):
    environ = os.environ if environ is None else environ
    return RUN_NAMES.get('%s/%s/%s' % (environ.get('LTX_STREAM_FRAMES'), environ.get('LTX_SAMPLER_PLACEMENT'),
                                       environ.get('LTX_ANCHOR')))


def name_collisions(names, prefix, root=ROOT):
    """Entries under output/, output/validation/ and requests/ that a packet115 server would collide with."""
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
    contract = module(Path(packet) / 'resolution/components/stream_contract.py', 'stream115_names')
    names, prefix = set(contract.fixed_names()), contract.RUN_PREFIX + '-'
    require(prefix == 'stream115-' and all(n.startswith(prefix) for n in names), 'Packet115 name prefix differs')
    found = name_collisions(names, prefix, root)
    require(not found, 'Packet115 names already exist (archive them first): ' + ', '.join(found[:12]) +
            (' and %d more' % (len(found) - 12) if len(found) > 12 else ''))
    return {'checked': list(NAME_DIRECTORIES), 'fixed_names': sorted(names), 'prefix': prefix, 'collisions': []}


def admit_storage(packet, run):
    helper = module(packet / 'launch/check-storage-headroom.py', 'stream115_storage')
    result = helper.inspect_destination(run, RESERVE, RUN_ALLOWANCE)
    require(result['admitted'], '50GiB reserve plus 3GiB stream allowance required')
    return result


# -- source transforms (applied to the sealed 114 files) ----------------------------
def geometry_source(raw, plan_sha, qids):
    """114's ltx_output_size_98.py: the 115 plan, ids keyed by frames/placement/anchor (default mixed), mode 115."""
    t = replace(raw, "_RESOLUTION_PLAN_SHA256 = '" + PARENT_PLAN_SHA + "'", "_RESOLUTION_PLAN_SHA256 = '" + plan_sha + "'")
    t = replace(t, "_RESOLUTION_QUALIFICATION_ID = " + repr(PARENT_QIDS) +
                "[_STREAM_FRAMES + '/' + os.environ.get('LTX_SAMPLER_PLACEMENT', 'two-way') + '/' + "
                "os.environ.get('LTX_ANCHOR', 'latent')]",
                "_RESOLUTION_QUALIFICATION_ID = " + repr(qids) +
                "[_STREAM_FRAMES + '/' + os.environ.get('LTX_SAMPLER_PLACEMENT', 'two-way') + '/' + "
                "os.environ.get('LTX_ANCHOR', 'mixed')]")
    t = replace(t, "_RESOLUTION_MODE = 'stream-candidate-114-v1'", "_RESOLUTION_MODE = 'stream-candidate-115-v1'")
    ast.parse(t)
    return t.encode()


def capture_guard_source(raw):
    """114's ltx_duration_guard.py: the 115 prewrite schema (shapes unchanged: 49 and 97 frames)."""
    t = replace(raw, "'ltx.stream114-prewrite.v1'", "'ltx.stream115-prewrite.v1'")
    ast.parse(t)
    return t.encode()


def launcher_source(raw):
    t = replace(raw, "                   'Packet114 admits only the 256x256 continuation stream server')",
                "                   'Packet115 admits only the 256x256 continuation stream server')")
    t = replace(t, "    # Packet114 naming rule (the 113 naming incident): refuse before any device work, also in --check-only.\n",
                "    # Packet115 naming rule (the 113 naming incident): refuse before any device work, also in --check-only.\n")
    # Packet115 (live 114 finding, 2026-10-08 15:06:16 UTC): the driver's devcoredump CLEANUP line
    # `xe 0000:43:00.0: [drm] Xe device coredump has been deleted.` matched the bare `coredump` term and
    # latched FAULT without a new fault. Creation lines (`... coredump has been created`, the
    # devcoredump_snapshot / xe_devcoredump trace) still latch; only the deletion line is excluded.
    t = replace(t, "GPU_FAULT = re.compile(r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump|Timedout job|wedged',\n"
                   "                       re.I)\n",
                "GPU_FAULT = re.compile(r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump|Timedout job|wedged',\n"
                "                       re.I)\n"
                "# Packet115: the driver deleting an earlier devcoredump is cleanup, not a fault (the 114 false latch of\n"
                "# 2026-10-08 15:06:16 UTC). Creation lines and the devcoredump trace still latch.\n"
                "COREDUMP_DELETED = re.compile(r'coredump has been deleted', re.I)\n")
    t = replace(t, "        if GPU_FAULT.search(line):\n",
                "        if GPU_FAULT.search(line) and not COREDUMP_DELETED.search(line):\n")
    t = replace(t, "    return [line for line in journal.splitlines() if FAULT.search(line)]\n",
                "    return [line for line in journal.splitlines() if FAULT.search(line) and not COREDUMP_DELETED.search(line)]\n")
    ast.parse(t)
    return t.encode()


# -- assembly -------------------------------------------------------------------
def check_plan(raw):
    envelope = json.loads(raw)
    require(envelope['plan_sha256'] == PLAN_SHA == digest(canonical(envelope['plan'])) and
            envelope['plan']['qualification_ids'] == QIDS, 'Reviewed115 plan changed')
    return envelope['plan']


def input_inventory():
    files = {n: sha(AUTHOR / n) for n in COMPONENTS}
    check_plan(regular(PLAN))
    files['stream-plan.json'] = sha(PLAN)
    return files


def successor_files(component_dir, plan_raw):
    check_plan(plan_raw)
    result = {'provenance/packet114-manifest.json': regular(PARENT / 'manifest.json'),
              'resolution/stream-plan.json': plan_raw}
    require(digest(result['provenance/packet114-manifest.json']) == PARENT_SHA, 'Parent manifest changed')
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
    # Components identical to the sealed 114 copies are not 'changed' (they stay inherited).
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
            files['provenance/packet114/' + path] = parent['files'][path]
        files[path] = digest(raw)
    return files


def transition(parent, changed, inventory, admission):
    return {'schema': 'ltx.stream115.transition.v1', 'packet_revision': '115',
            'parent_packet': str(PARENT), 'parent_manifest_sha256': PARENT_SHA,
            'plan_sha256': PLAN_SHA, 'qualification_ids': QIDS, 'input_inventory': inventory,
            'input_inventory_sha256': digest(canonical(inventory)),
            'source_delta': {p: {'before_sha256': parent['files'].get(p), 'after_sha256': digest(raw)}
                             for p, raw in changed.items()},
            'control': {'size': '256x256', 'frame_count': 'LTX_STREAM_FRAMES (49 or 97; launched at 49 first)',
                        'fps': 24, 'layout': 'LTX_SAMPLER_PLACEMENT (two-way or two-way20-28; launched two-way20-28)',
                        'anchor': 'LTX_ANCHOR (mixed default = stage A latent anchor + stage B decoded-frame '
                                  'anchor; guide = native latent guide of the last two latents; latent = packet114; '
                                  'frame = packet113)',
                        'workers': 1, 'batch': 1, 'shared_pool': 1,
                        'decode_replica_env': 'xpu:2 (environment only; native VAEDecode, zero replicas)',
                        'decoder_graph_capture': 'not enabled',
                        'decode': 'one ordered decode thread on xpu:3, bounded FIFO, back-pressure, latch; '
                                  'mixed: writes the frame anchor; sharpness profile per chunk',
                        'mixed_wait': 'stage-B condition node waits (bounded 300 s) for the predecessor decode',
                        'preview': 'one bounded FIFO writer thread behind the decode thread',
                        'chain_reset': 'stream chunk reset=1 is unanchored (stream_seq 0 form)',
                        'graph_replay': 'LTXGraphCaptureGate all48 chain1', 'qualification_requests': 9,
                        'full_captures': 9, 'stream_requests': 'unbounded, serial, storage-bounded',
                        'environment': CONTROL_ENVIRONMENT, 'text_reuse_env': 'LTX_STREAM_TEXT_REUSE (1 default)',
                        'names': 'stream115- prefix; launcher refuses existing names (also --check-only)',
                        'stage_overlap_across_cards': 'not in 115'},
            'storage_admission': admission, 'qualification': False, 'model_requests': 0,
            'claims': {'quality_adopted': False, 'seam_accepted': False, 'audio_alignment_resolved': False,
                       'speed_improvement': False, 'geometry_97_measured': False}}


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
    result['output_size']['stream115'] = {'plan_sha256': PLAN_SHA, 'size': '256x256', 'frame_count': [49, 97],
                                          'anchor': list(ANCHORS), 'comparison_mode': 'stream-candidate-115-v1',
                                          'qualified': False,
                                          'numerics_from': 'packet113 sampler/decoder; mixed and guide anchors are '
                                                           'new output'}
    return result


def assembly_bytes(parent, changed):
    original = sum((PARENT / p).stat().st_size for p in parent['files'])
    return original + sum(len(raw) for raw in changed.values()) + len(STATUS)


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET and re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or ''),
            'Unexpected115 packet or manifest identity')
    require(sha(packet / 'manifest.json') == expected_manifest_sha256, '115 manifest changed')
    manifest = json.loads(regular(packet / 'manifest.json'))
    require(regular(packet / 'STATUS.txt') == STATUS, '115 status identity changed')
    require(type(manifest.get('files')) is dict, '115 file inventory missing')
    for path, expected in manifest['files'].items():
        require(type(path) is str and type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected)
                and sha(safe_path(packet, path)) == expected, '115 file changed before component import: ' + str(path))
    require(all('resolution/components/' + n in manifest['files'] for n in COMPONENTS),
            '115 component inventory incomplete')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(packet / 'resolution/components', regular(packet / 'resolution/stream-plan.json'))
    expected_files = manifest_files(parent, changed)
    require(manifest['files'] == expected_files, '115 source closure differs')
    checker_path = 'provenance/source99/check-upstream-source-99.py'
    require(sha(PARENT / checker_path) == parent['files'][checker_path], 'Inventory checker changed')
    checker = module(PARENT / checker_path, 'stream115_inventory')
    require(checker.inventory(packet) == set(expected_files) | {'manifest.json', 'STATUS.txt'},
            'Unbound115 packet file')
    inventory = {n: expected_files['resolution/components/' + n] for n in COMPONENTS}  # all bound
    inventory['stream-plan.json'] = expected_files['resolution/stream-plan.json']
    admission = manifest['resolution101']['storage_admission']
    require(admission['admitted'] is True, '115 build was not admitted')
    change = transition(parent, changed, inventory, admission)
    require(manifest == semantic_manifest(parent, expected_files, change), '115 semantic identity differs')
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
    changed = successor_files(AUTHOR, regular(PLAN))
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
    require(inspected['input_inventory_sha256'] == expected_inventory_sha256, 'Reviewed115 inputs differ')
    require(not PACKET.exists() and not PACKET.is_symlink() and
            not any(p.is_symlink() for p in PACKET.parents), 'Exclusive regular packet destination required')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(AUTHOR, regular(PLAN))
    inventory = input_inventory()
    require(inventory == inspected['input_inventory'], 'Inputs changed after review')
    helper = module(PARENT / 'launch/check-storage-headroom.py', 'stream115_build_storage')
    admission = helper.inspect_destination(PACKET, RESERVE + RUN_ALLOWANCE, BUILD_ALLOWANCE)
    require(admission['admitted'], '50GiB reserve plus 3GiB run plus 160MiB build allowance required')
    PACKET.mkdir(mode=0o700)
    write_new(PACKET / 'STATUS.txt', STATUS)
    for path, expected in parent['files'].items():
        raw = regular(PARENT / path)
        require(digest(raw) == expected, 'Parent file changed while copying: ' + path)
        mode = stat.S_IMODE((PARENT / path).stat().st_mode)
        if path in changed:
            write_new(PACKET / 'provenance/packet114' / path, raw, mode)
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

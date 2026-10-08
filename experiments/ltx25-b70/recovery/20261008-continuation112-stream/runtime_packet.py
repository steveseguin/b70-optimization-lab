#!/usr/bin/env python3
"""Exact sealed-111 successor assembly for packet112. Default inventories; --build is explicit.

Installed in the packet as launch/encoder_runtime_common.py. Reading the sealed
111 packet needs no process action. This builder never contacts an endpoint,
imports Torch or touches a device. Changed parent files survive under
provenance/packet111/.
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
PARENT = ROOT / 'prepared-continuation-native-111'
PARENT_SHA = '65adf13fca14f92047960ed939c507cd7e28a08b41940decd089189c86c41363'
PACKET = ROOT / 'prepared-continuation-stream-112'
RUN_NAMES = {'%s/%s' % (f, p): 'encoder-server-continuation-stream-112-%s-w1-b1-p1-dxpu2-s256x256-f%s' % (p, f)
             for f in ('49', '25') for p in ('two-way', 'two-way20-28')}
AUTHOR = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation112-stream')
PLAN = AUTHOR / 'stream-plan.json'
PLAN_SHA = '7c37f64883394c729562a84d5b411494eadeb67e89808b415b27e209467f49e1'
QIDS = {
    '49/two-way': '09c1fda000494fb391e934fcffc83aa5169d80626a13f3c9edf715111da318b8',
    '49/two-way20-28': '0f7cda48784e92bdb6ff99708ae12809838eaf0b1db535d259f0a116a2ab9b0e',
    '25/two-way': 'b5ea97da305a36b13922d78d8fb4f5b6353ab71ad5e9680ad8bf81ce60c4a2b3',
    '25/two-way20-28': '7d40ff29e6d76a9b5bfc5503933d1d4e95d6e36532a51d8e76a2bd3a5e5f01ad',
}
COMMON, LAUNCHER = 'launch/encoder_runtime_common.py', 'launch/serve-encoder.py'
STATUS = (b'Packet112 256x256 continuation stream with per-block graph replay; nine-capture exact '
          b'qualification gates streaming; not GPU-qualified or quality-adopted.\n')
COMPONENTS = ('session.py', 'integration.py', 'stream_contract.py', 'stream_receipts.py',
              'qualification_gate.py', 'candidate_safety.py', 'conditioning_guard.py',
              'native_bindings.py', 'continuation_anchor.py', 'qualify_client.py', 'plan.py',
              'derive_from_111.py', 'runtime_packet.py')
MODULES = {n: ('ltx_resolution_session.py' if n == 'session.py' else n) for n in COMPONENTS
           if n not in ('qualify_client.py', 'plan.py', 'derive_from_111.py', 'runtime_packet.py')}
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
require(digest(_parent_raw) == PARENT_SHA, 'Sealed111 parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
require(digest((PARENT / COMMON).read_bytes()) == _parent_manifest['files'][COMMON], 'Sealed111 checker changed')
BASE = load(PARENT / COMMON, 'stream112_parent111')
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
            'Explicit packet112 environment differs: ' + json.dumps(CONTROL_ENVIRONMENT, sort_keys=True))
    require(os.environ.get('LTX_STREAM_TEXT_REUSE') in ('0', '1'), 'LTX_STREAM_TEXT_REUSE must be set to 0 or 1')
    require(os.environ.get('LTX_STREAM_FRAMES') in ('49', '25'), 'LTX_STREAM_FRAMES must be set to 49 or 25')
    require(os.environ.get('LTX_SAMPLER_PLACEMENT') in ('two-way', 'two-way20-28'),
            'LTX_SAMPLER_PLACEMENT must be set to two-way or two-way20-28')


def admit_storage(packet, run):
    helper = module(packet / 'launch/check-storage-headroom.py', 'stream112_storage')
    result = helper.inspect_destination(run, RESERVE, RUN_ALLOWANCE)
    require(result['admitted'], '50GiB reserve plus 3GiB stream allowance required')
    return result


# -- source transforms ----------------------------------------------------------
def geometry_source(raw, plan_sha):
    t = replace(raw, "if OUTPUT_SIZE != '640x384':\n    raise RuntimeError('duration110 requires640x384')\n"
                     "FRAMES, TEMPORAL_LATENTS, AUDIO_LATENTS, AUDIO_SAMPLES = 49, 7, 51, 96480",
                "if OUTPUT_SIZE != '256x256':\n    raise RuntimeError('stream112 requires256x256')\n"
                "_STREAM_FRAMES = os.environ.get('LTX_STREAM_FRAMES', '49')\n"
                "if _STREAM_FRAMES not in ('49', '25'):\n    raise RuntimeError('LTX_STREAM_FRAMES must be 49 or 25')\n"
                "FRAMES, TEMPORAL_LATENTS, AUDIO_LATENTS, AUDIO_SAMPLES = "
                "{'49': (49, 7, 51, 96480), '25': (25, 4, 26, 48480)}[_STREAM_FRAMES]")
    t = replace(t, "_RESOLUTION_PLAN_SHA256 = '7944f8701244bd386c41bc5cdd6c4e9df1ea8fcf4d9dedf91e249f476105b2c5'",
                "_RESOLUTION_PLAN_SHA256 = '" + plan_sha + "'")
    t = replace(t, "_RESOLUTION_QUALIFICATION_ID = '705fa3d73c603833591ac5ae13b5f2d4d79c329b860794ff4d061c71e8942266'",
                "_RESOLUTION_QUALIFICATION_ID = " + repr(QIDS) +
                "[_STREAM_FRAMES + '/' + os.environ.get('LTX_SAMPLER_PLACEMENT', 'two-way')]")
    t = replace(t, "_RESOLUTION_MODE = 'same-size-native-v1'", "_RESOLUTION_MODE = 'stream-candidate-112-v1'")
    t = replace(t, "== '640x384'", "== '256x256'", count=4)
    t = replace(t, "'Same-size mode requires640x384 and explicit non-speed comparison'",
                "'Stream mode requires256x256 and explicit non-speed comparison'")
    t = replace(t, "env = {'LTX_SAMPLER_PLACEMENT': 'two-way20-28', 'LTX_SAMPLER_WORKERS': '2',",
                "_resolution_require(os.environ.get('LTX_SAMPLER_PLACEMENT') in ('two-way', 'two-way20-28'),\n"
                "                        'Stream mode requires two-way or two-way20-28')\n"
                "    env = {'LTX_SAMPLER_WORKERS': '1',")
    t = replace(t, "'Same-size mode requires exact20/28 W2 B1 shared-pool configuration'",
                "'Stream mode requires exact W1 B1 shared-pool configuration'")
    t = replace(t, "phase in (('native_reference', 'optimized_preparation', 'timing') if role == 'text'\n"
                   "                                 else ('optimized_preparation', 'timing'))",
                "phase in (('stream_qualification', 'stream') if role == 'text'\n"
                "                                 else ())")
    t = replace(t, "    if phase != 'native_reference':\n", "    if phase == 'stream':\n")
    t = replace(t, "auxiliary.get('phase') in ('native_reference', 'reference_verified',\n"
                   "                                'optimized_preparation', 'candidate_verified', 'timing')",
                "auxiliary.get('phase') in ('stream_setup', 'stream_qualification', 'stream')")
    t = replace(t, "'frame_count': 49", "'frame_count': FRAMES", count=2)
    ast.parse(t)
    return t.encode()


def setup_gates_source(raw):
    t = replace(raw, "report['output_size'] == '640x384' and\n"
                     "            type(report.get('frame_count')) is int and report['frame_count'] == 49",
                "report['output_size'] == '256x256' and\n"
                "            type(report.get('frame_count')) is int and "
                "report['frame_count'] == int(__import__('os').environ.get('LTX_STREAM_FRAMES', '49'))")
    ast.parse(t)
    return t.encode()


def capture_guard_source(raw):
    t = replace(raw, "FULL_SHAPES = {'images': (49, 384, 640, 3), 'video_latent': (1, 128, 7, 12, 20),\n"
                     "               'audio_latent': (1, 8, 51, 16), 'waveform': (1, 2, 96480)}",
                "_STREAM_FRAMES = __import__('os').environ.get('LTX_STREAM_FRAMES', '49')\n"
                "_T, _AL, _AS = {'49': (7, 51, 96480), '25': (4, 26, 48480)}[_STREAM_FRAMES]\n"
                "FULL_SHAPES = {'images': (int(_STREAM_FRAMES), 256, 256, 3), 'video_latent': (1, 128, _T, 8, 8),\n"
                "               'audio_latent': (1, 8, _AL, 16), 'waveform': (1, 2, _AS)}")
    t = replace(t, 'STAGE_A = (1, 128, 7, 6, 10)', 'STAGE_A = (1, 128, _T, 4, 4)')
    t = replace(t, 'FULL_PAYLOAD_BYTES = 146164992',
                'FULL_PAYLOAD_BYTES = sum(math.prod(s) * 4 for s in FULL_SHAPES.values())')
    t = replace(t, 'RAW_CAPTURE_BUDGET = 6 * FULL_FILE_BOUND', 'RAW_CAPTURE_BUDGET = 9 * FULL_FILE_BOUND')
    t = replace(t, 'WRITE_ALLOWANCE = 4 * 1024 ** 3', 'WRITE_ALLOWANCE = 3 * 1024 ** 3')
    t = replace(t, 'Bind6 full capture rows', 'Bind9 full qualification capture rows')
    t = replace(t, 'role counts are6 full,0 fill,0 setup', 'role counts are9 full,0 fill,0 setup')
    t = replace(t, "len(capture_rows) == 6, 'Exactly6 full capture rows required'",
                "len(capture_rows) == 9, 'Exactly9 full capture rows required'")
    t = replace(t, "len({r['name'] for r in capture_rows}) == 6", "len({r['name'] for r in capture_rows}) == 9")
    t = replace(t, "{'full': 6, 'fill': 0, 'setup': 0}", "{'full': 9, 'fill': 0, 'setup': 0}")
    t = replace(t, "'ltx.continuation111-prewrite.v1'", "'ltx.stream112-prewrite.v1'")
    t = replace(t, "'capture_cap': 6", "'capture_cap': 9")
    ast.parse(t)
    return t.encode()


def launcher_source(raw):
    t = replace(raw, "run_name == 'encoder-server-continuation-native-111-two-way20-28-w2-b1-p1-dxpu2-s640x384-f49'",
                'run_name == ' + repr(RUN_NAMES) +
                ".get('%s/%s' % (os.environ.get('LTX_STREAM_FRAMES'), os.environ.get('LTX_SAMPLER_PLACEMENT')))")
    t = replace(t, "'Packet111 admits only the fixed native continuation reference'",
                "'Packet112 admits only the 256x256 continuation stream server'")
    ast.parse(t)
    return t.encode()


# -- assembly -------------------------------------------------------------------
def check_plan(raw):
    envelope = json.loads(raw)
    require(envelope['plan_sha256'] == PLAN_SHA == digest(canonical(envelope['plan'])) and
            envelope['plan']['qualification_ids'] == QIDS, 'Reviewed112 plan changed')
    return envelope['plan']


def input_inventory():
    files = {n: sha(AUTHOR / n) for n in COMPONENTS}
    check_plan(regular(PLAN))
    files['stream-plan.json'] = sha(PLAN)
    return files


def successor_files(component_dir, plan_raw):
    check_plan(plan_raw)
    result = {'provenance/packet111-manifest.json': regular(PARENT / 'manifest.json'),
              'resolution/stream-plan.json': plan_raw}
    require(digest(result['provenance/packet111-manifest.json']) == PARENT_SHA, 'Parent manifest changed')
    for name in COMPONENTS:
        raw = regular(component_dir / name)
        ast.parse(raw)
        result['resolution/components/' + name] = raw
        if name in MODULES:
            result['source/scripts/' + MODULES[name]] = raw
    result[COMMON] = regular(component_dir / 'runtime_packet.py')
    result[LAUNCHER] = launcher_source(regular(PARENT / LAUNCHER))
    result['source/scripts/ltx_output_size_98.py'] = geometry_source(
        regular(PARENT / 'source/scripts/ltx_output_size_98.py'), PLAN_SHA)
    result['source/scripts/setup_gates.py'] = setup_gates_source(regular(PARENT / 'source/scripts/setup_gates.py'))
    result['source/scripts/ltx_duration_guard.py'] = capture_guard_source(
        regular(PARENT / 'source/scripts/ltx_duration_guard.py'))
    for path, raw in result.items():
        if path.endswith('.py'):
            ast.parse(raw)
    return result


def manifest_files(parent, changed):
    files = dict(parent['files'])
    for path, raw in changed.items():
        if path in parent['files']:
            files['provenance/packet111/' + path] = parent['files'][path]
        files[path] = digest(raw)
    return files


def transition(parent, changed, inventory, admission):
    return {'schema': 'ltx.stream112.transition.v1', 'packet_revision': '112',
            'parent_packet': str(PARENT), 'parent_manifest_sha256': PARENT_SHA,
            'plan_sha256': PLAN_SHA, 'qualification_ids': QIDS, 'input_inventory': inventory,
            'input_inventory_sha256': digest(canonical(inventory)),
            'source_delta': {p: {'before_sha256': parent['files'].get(p), 'after_sha256': digest(raw)}
                             for p, raw in changed.items()},
            'control': {'size': '256x256', 'frame_count': 'LTX_STREAM_FRAMES (49 default, 25 alternative)',
                        'fps': 24, 'layout': 'LTX_SAMPLER_PLACEMENT (two-way 23/25 default, two-way20-28 alternative)',
                        'workers': 1, 'batch': 1, 'shared_pool': 1,
                        'decode_replica_env': 'xpu:2 (environment only; native VAEDecode, zero replicas)',
                        'graph_replay': 'LTXGraphCaptureGate all48 chain1', 'qualification_requests': 9,
                        'full_captures': 9, 'stream_requests': 'unbounded, serial, storage-bounded',
                        'environment': CONTROL_ENVIRONMENT, 'text_reuse_env': 'LTX_STREAM_TEXT_REUSE (0 default)'},
            'storage_admission': admission, 'qualification': False, 'model_requests': 0,
            'claims': {'quality_adopted': False, 'seam_accepted': False, 'audio_alignment_resolved': False,
                       'speed_improvement': False}}


def semantic_manifest(parent, files, change):
    result = copy.deepcopy(parent)
    result.update(schema='ltx.continuation-stream-runtime.v1', files=files,
                  preparer_sha256=files['resolution/components/runtime_packet.py'], resolution101=change)
    result['startup_tools'] = {Path(k).name: files[k] for k in (COMMON, LAUNCHER)}
    for name in list(result['extension_sha256s']):
        path = 'source/scripts/' + name
        if path in files:
            result['extension_sha256s'][name] = files[path]
    for name in MODULES.values():
        result['extension_sha256s'][name] = files['source/scripts/' + name]
    result['output_size']['module_sha256'] = files['source/scripts/ltx_output_size_98.py']
    result['output_size'].pop('same_size_native', None)
    result['output_size']['stream112'] = {'plan_sha256': PLAN_SHA, 'size': '256x256', 'frame_count': [49, 25],
                                          'comparison_mode': 'stream-candidate-112-v1', 'qualified': False}
    return result


def assembly_bytes(parent, changed):
    original = sum((PARENT / p).stat().st_size for p in parent['files'])
    return original + sum(len(raw) for raw in changed.values()) + len(STATUS)


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET and re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or ''),
            'Unexpected112 packet or manifest identity')
    require(sha(packet / 'manifest.json') == expected_manifest_sha256, '112 manifest changed')
    manifest = json.loads(regular(packet / 'manifest.json'))
    require(regular(packet / 'STATUS.txt') == STATUS, '112 status identity changed')
    require(type(manifest.get('files')) is dict, '112 file inventory missing')
    for path, expected in manifest['files'].items():
        require(type(path) is str and type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected)
                and sha(safe_path(packet, path)) == expected, '112 file changed before component import: ' + str(path))
    require(all('resolution/components/' + n in manifest['files'] for n in COMPONENTS),
            '112 component inventory incomplete')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(packet / 'resolution/components', regular(packet / 'resolution/stream-plan.json'))
    expected_files = manifest_files(parent, changed)
    require(manifest['files'] == expected_files, '112 source closure differs')
    checker_path = 'provenance/source99/check-upstream-source-99.py'
    require(sha(PARENT / checker_path) == parent['files'][checker_path], 'Inventory checker changed')
    checker = module(PARENT / checker_path, 'stream112_inventory')
    require(checker.inventory(packet) == set(expected_files) | {'manifest.json', 'STATUS.txt'},
            'Unbound112 packet file')
    inventory = {n: expected_files['resolution/components/' + n] for n in COMPONENTS}
    inventory['stream-plan.json'] = expected_files['resolution/stream-plan.json']
    admission = manifest['resolution101']['storage_admission']
    require(admission['admitted'] is True, '112 build was not admitted')
    change = transition(parent, changed, inventory, admission)
    require(manifest == semantic_manifest(parent, expected_files, change), '112 semantic identity differs')
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
    require(inspected['input_inventory_sha256'] == expected_inventory_sha256, 'Reviewed112 inputs differ')
    require(not PACKET.exists() and not PACKET.is_symlink() and
            not any(p.is_symlink() for p in PACKET.parents), 'Exclusive regular packet destination required')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(AUTHOR, regular(PLAN))
    inventory = input_inventory()
    require(inventory == inspected['input_inventory'], 'Inputs changed after review')
    helper = module(PARENT / 'launch/check-storage-headroom.py', 'stream112_build_storage')
    admission = helper.inspect_destination(PACKET, RESERVE + RUN_ALLOWANCE, BUILD_ALLOWANCE)
    require(admission['admitted'], '50GiB reserve plus 3GiB run plus 160MiB build allowance required')
    PACKET.mkdir(mode=0o700)
    write_new(PACKET / 'STATUS.txt', STATUS)
    for path, expected in parent['files'].items():
        raw = regular(PARENT / path)
        require(digest(raw) == expected, 'Parent file changed while copying: ' + path)
        mode = stat.S_IMODE((PARENT / path).stat().st_mode)
        if path in changed:
            write_new(PACKET / 'provenance/packet111' / path, raw, mode)
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

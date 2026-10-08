#!/usr/bin/env python3
"""Exact110 CPU successor assembly. Default inventories; --build is explicit.

Reading the retained110 source never requires stopping its application. This
builder does not own a process, contact an endpoint, or perform device work.
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
PARENT = ROOT / 'prepared-duration-full-110'
PARENT_SHA = 'bfa78fcf6af59acc3d63318ca97c61846b3a9b80999f6f17cb4c4d3651f2ad09'
PACKET = ROOT / 'prepared-continuation-native-111'
RUN_NAME = 'encoder-server-continuation-native-111-two-way20-28-w2-b1-p1-dxpu2-s640x384-f49'
AUTHOR = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261007-continuation111-runtime')
PLAN = AUTHOR.parent / '20261007-continuation111-plan/candidate-plan.json'
PLAN_SHA = '7944f8701244bd386c41bc5cdd6c4e9df1ea8fcf4d9dedf91e249f476105b2c5'
QID = '705fa3d73c603833591ac5ae13b5f2d4d79c329b860794ff4d061c71e8942266'
COMMON, LAUNCHER = 'launch/encoder_runtime_common.py', 'launch/serve-encoder.py'
STATUS = b'Packet111 native three-chunk continuation reference; six captures, exact replay required; not GPU-qualified or quality-adopted.\n'
COMPONENTS = ('session.py', 'integration.py', 'native_bindings.py', 'proof.py',
              'request_client.py', 'campaign.py', 'continuation_anchor.py',
              'conditioning_guard.py', 'encode_safety.py', 'capture_adapter.py',
              'runtime_packet.py')
MODULES = {n: ('ltx_resolution_session.py' if n == 'session.py' else n)
           for n in COMPONENTS if n not in ('request_client.py', 'campaign.py',
                                           'encode_safety.py', 'capture_adapter.py', 'runtime_packet.py')}
GIB = 2**30
BUILD_ALLOWANCE = 384 * 2**20
RUN_ALLOWANCE = 4 * GIB


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def digest(raw): return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_parent_raw = (PARENT / 'manifest.json').read_bytes()
require(digest(_parent_raw) == PARENT_SHA, 'Sealed110 parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
require(digest((PARENT / COMMON).read_bytes()) == _parent_manifest['files'][COMMON],
        'Sealed110 parent checker changed')
BASE = load(PARENT / COMMON, 'continuation111_parent110')
regular, sha, safe_path, module = BASE.regular, BASE.sha, BASE.safe_path, BASE.module
NODES = list(BASE.NODES)


def __getattr__(name): return getattr(BASE, name)


def replace_once(raw, old, new):
    require(raw.count(old) == 1, 'Source anchor changed: ' + repr(old))
    return raw.replace(old, new, 1)


def admit_storage(packet, run):
    helper = module(packet / 'launch/check-storage-headroom.py', 'continuation111_storage')
    result = helper.inspect_destination(run, 50 * GIB, RUN_ALLOWANCE)
    require(result['admitted'], '50GiB reserve plus4GiB continuation allowance required')
    return result


def check_plan(raw):
    envelope = json.loads(raw)
    require(envelope['plan_sha256'] == PLAN_SHA == digest(canonical(envelope['plan'])) and
            envelope['plan']['qualification_id'] == QID, 'Frozen111 plan changed')
    return envelope['plan']


def input_inventory():
    files = {n: sha(AUTHOR / n) for n in COMPONENTS}
    check_plan(regular(PLAN))
    files['candidate-plan.json'] = sha(PLAN)
    return files


def successor_files(component_dir, plan_raw):
    """Return exact replacements/additions, without writing or changing parent."""
    check_plan(plan_raw)
    result = {'provenance/packet110-manifest.json': regular(PARENT / 'manifest.json'),
              'resolution/candidate-plan.json': plan_raw}
    require(digest(result['provenance/packet110-manifest.json']) == PARENT_SHA,
            'Parent manifest changed during assembly')
    for name in COMPONENTS:
        raw = regular(component_dir / name)
        ast.parse(raw)
        result['resolution/components/' + name] = raw
        if name in MODULES:
            result['source/scripts/' + MODULES[name]] = raw
    result[COMMON] = regular(component_dir / 'runtime_packet.py')
    launcher = regular(PARENT / LAUNCHER)
    launcher = replace_once(launcher,
        b"run_name == 'encoder-server-duration-full-110-two-way20-28-w2-b1-p1-dxpu2-s640x384-f49'",
        ('run_name == ' + repr(RUN_NAME)).encode())
    launcher = replace_once(launcher,
        b'Packet101 admits only the reviewed W2 same-size reference experiment',
        b'Packet111 admits only the fixed native continuation reference')
    result[LAUNCHER] = launcher
    geometry_path = 'source/scripts/ltx_output_size_98.py'
    geometry = replace_once(regular(PARENT / geometry_path),
        b"_RESOLUTION_PLAN_SHA256 = 'cafb272fcb182d80022a0e73eff838dc7fd0aeb5001704d0b9ccbd37fadeccab'",
        ("_RESOLUTION_PLAN_SHA256 = '" + PLAN_SHA + "'").encode())
    geometry = replace_once(geometry,
        b"_RESOLUTION_QUALIFICATION_ID = '28ad14c062af8e5bf80b904a895f422a76ccf6c95c176d5630b23a4027097560'",
        ("_RESOLUTION_QUALIFICATION_ID = '" + QID + "'").encode())
    result[geometry_path] = geometry
    encode = load(component_dir / 'encode_safety.py', 'continuation111_encode_delta')
    result['source/comfy/sd.py'] = encode.transform_sd(regular(PARENT / 'source/comfy/sd.py'))
    for path in ('source/scripts/na_axis_decode_node.py',
                 'source/custom_nodes/ltx_na_axis_decode_lab/__init__.py'):
        result[path] = replace_once(regular(PARENT / path),
            ("SD_SHA = '" + encode.SOURCE_SHA256 + "'").encode(),
            ("SD_SHA = '" + digest(result['source/comfy/sd.py']) + "'").encode())
    capture = load(component_dir / 'capture_adapter.py', 'continuation111_capture_delta')
    result['source/scripts/ltx_duration_guard.py'] = capture.transform_guard(
        regular(PARENT / 'source/scripts/ltx_duration_guard.py'))
    for path, raw in result.items():
        if path.endswith('.py'): ast.parse(raw)
    return result


def manifest_files(parent, changed):
    files = dict(parent['files'])
    for path, raw in changed.items():
        if path in parent['files']:
            files['provenance/packet110/' + path] = parent['files'][path]
        files[path] = digest(raw)
    return files


def transition(parent, changed, inventory, admission):
    return {'schema': 'ltx.continuation111.transition.v1', 'packet_revision': '111',
        'parent_packet': str(PARENT), 'parent_manifest_sha256': PARENT_SHA,
        'plan_sha256': PLAN_SHA, 'input_inventory': inventory,
        'input_inventory_sha256': digest(canonical(inventory)),
        'source_delta': {p: {'before_sha256': parent['files'].get(p), 'after_sha256': digest(raw)}
                         for p, raw in changed.items()},
        'control': {'size': '640x384', 'frame_count': 49, 'layout': 'two-way20-28',
                    'blocks': [20, 28], 'workers': 2, 'batch': 1, 'shared_pool': 1,
                    'native_only': True, 'requests': 8, 'full_captures': 6,
                    'actual_sampler_routes': 0, 'actual_decoder_replicas': 0,
                    'unique_frames_per_chain': 145, 'replay_pairs': 3},
        'storage_admission': admission, 'qualification': False, 'model_requests': 0,
        'claims': {'quality_adopted': False, 'seam_accepted': False, 'audio_alignment_resolved': False,
                   'speed_improvement': False},
        'inherited_unused': '110 optimized schedule and comparison helpers remain source-bound historical files;111 authority admits only its eight native graphs'}


def semantic_manifest(parent, files, change):
    result = copy.deepcopy(parent)
    result.update(schema='ltx.continuation-native-runtime.v1', files=files,
                  preparer_sha256=files['resolution/components/runtime_packet.py'], resolution101=change)
    result['startup_tools'] = {Path(k).name: files[k] for k in (COMMON, LAUNCHER)}
    for name in result['extension_sha256s']:
        path = 'source/scripts/' + name
        if path in files: result['extension_sha256s'][name] = files[path]
    for name in MODULES.values():
        result['extension_sha256s'][name] = files['source/scripts/' + name]
    result['output_size']['module_sha256'] = files['source/scripts/ltx_output_size_98.py']
    result['output_size']['same_size_native'] = {'plan_sha256': PLAN_SHA, 'size': '640x384',
        'frame_count': 49, 'comparison_mode': 'same-size-native-v1', 'qualified': False}
    return result


def assembly_bytes(parent, changed):
    """Exact payload bytes (metadata/filesystem overhead separately reserved)."""
    original = sum((PARENT / p).stat().st_size for p in parent['files'])
    # Replaced originals survive once in provenance; additions and replacements
    # add precisely their successor bytes to the copied parent inventory.
    return original + sum(len(raw) for raw in changed.values()) + len(STATUS)


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET and re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or ''),
            'Unexpected111 packet or manifest identity')
    require(sha(packet / 'manifest.json') == expected_manifest_sha256, '111 manifest changed')
    manifest = json.loads(regular(packet / 'manifest.json'))
    require(regular(packet / 'STATUS.txt') == STATUS, '111 status identity changed')
    require(type(manifest.get('files')) is dict, '111 file inventory missing')
    for path, expected in manifest['files'].items():
        require(type(path) is str and type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected)
                and sha(safe_path(packet, path)) == expected, '111 file changed before component import: ' + str(path))
    require(all('resolution/components/' + n in manifest['files'] for n in COMPONENTS),
            '111 component inventory incomplete')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(packet / 'resolution/components', regular(packet / 'resolution/candidate-plan.json'))
    expected_files = manifest_files(parent, changed)
    require(manifest['files'] == expected_files, '111 source closure differs')
    checker = module(BASE.PARENT / 'provenance/source99/check-upstream-source-99.py', 'continuation111_inventory')
    require(checker.inventory(packet) == set(expected_files) | {'manifest.json', 'STATUS.txt'},
            'Unbound111 packet file')
    inventory = {n: expected_files['resolution/components/' + n] for n in COMPONENTS}
    inventory['candidate-plan.json'] = expected_files['resolution/candidate-plan.json']
    admission = manifest['resolution101']['storage_admission']
    require(admission['admitted'] is True, '111 build was not admitted')
    change = transition(parent, changed, inventory, admission)
    require(manifest == semantic_manifest(parent, expected_files, change), '111 semantic identity differs')
    return manifest


def write_new(path, raw, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw); os.fchmod(stream.fileno(), mode); stream.flush(); os.fsync(stream.fileno())


def inspect_assembly():
    inventory = input_inventory()
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(AUTHOR, regular(PLAN))
    require(input_inventory() == inventory, 'Authored inputs changed during assembly')
    amount = assembly_bytes(parent, changed)
    require(amount + 4 * 2**20 < BUILD_ALLOWANCE, 'Source assembly exceeds reserved build allowance')
    return {'status': 'source-assembly-checked', 'input_inventory': inventory,
        'input_inventory_sha256': digest(canonical(inventory)), 'source_payload_bytes': amount,
        'build_allowance_bytes': BUILD_ALLOWANCE, 'run_allowance_bytes': RUN_ALLOWANCE,
        'changed_files': {p: digest(raw) for p, raw in changed.items()},
        'materialized': False, 'model_requests': 0}


def build(expected_inventory_sha256):
    inspected = inspect_assembly()
    require(inspected['input_inventory_sha256'] == expected_inventory_sha256, 'Reviewed111 inputs differ')
    require(not PACKET.exists() and not PACKET.is_symlink() and
            not any(p.is_symlink() for p in PACKET.parents), 'Exclusive regular packet destination required')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(AUTHOR, regular(PLAN))
    inventory = input_inventory()
    require(inventory == inspected['input_inventory'], 'Inputs changed after review')
    helper = module(PARENT / 'launch/check-storage-headroom.py', 'continuation111_build_storage')
    admission = helper.inspect_destination(PACKET, 50 * GIB + RUN_ALLOWANCE, BUILD_ALLOWANCE)
    require(admission['admitted'], '50GiB reserve plus4GiB run plus384MiB build allowance required')
    PACKET.mkdir(mode=0o700)
    write_new(PACKET / 'STATUS.txt', STATUS)
    for path, expected in parent['files'].items():
        raw = regular(PARENT / path)
        require(digest(raw) == expected, 'Parent file changed while copying: ' + path)
        mode = stat.S_IMODE((PARENT / path).stat().st_mode)
        if path in changed:
            write_new(PACKET / 'provenance/packet110' / path, raw, mode)
            raw = changed[path]
        write_new(PACKET / path, raw, mode)
    for path, raw in changed.items():
        if path not in parent['files']: write_new(PACKET / path, raw)
    files = manifest_files(parent, changed)
    change = transition(parent, changed, inventory, admission)
    manifest = semantic_manifest(parent, files, change)
    write_new(PACKET / 'manifest.json', json.dumps(manifest, indent=2, sort_keys=True).encode() + b'\n')
    for directory in [p for p in PACKET.rglob('*') if p.is_dir()] + [PACKET, PACKET.parent]:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    manifest_sha = sha(PACKET / 'manifest.json')
    verify_packet(PACKET, manifest_sha)
    return {'status': 'prepared-not-GPU-qualified', 'packet': str(PACKET),
            'manifest_sha256': manifest_sha, 'model_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--input-inventory-sha256')
    parser.add_argument('--inspect-assembly', action='store_true')
    parser.add_argument('--verify-manifest-sha256')
    args = parser.parse_args()
    require(sum((args.build, args.inspect_assembly, bool(args.verify_manifest_sha256))) <= 1,
            'Select one operation')
    if args.build: result = build(args.input_inventory_sha256)
    elif args.inspect_assembly: result = inspect_assembly()
    elif args.verify_manifest_sha256:
        verify_packet(PACKET, args.verify_manifest_sha256)
        result = {'status': 'source-closure-verified', 'model_requests': 0}
    else:
        inventory = input_inventory()
        result = {'status': 'plan-only', 'packet': str(PACKET), 'input_inventory': inventory,
            'input_inventory_sha256': digest(canonical(inventory)), 'materialized': False, 'model_requests': 0}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__': main()

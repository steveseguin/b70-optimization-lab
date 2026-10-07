#!/usr/bin/env python3
"""CPU-only, exact99b successor builder/checker. Default does not materialize.

All integration components and an explicitly reviewed input-inventory hash are
required to build. No source edit is made in the qualified parent packet.
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
PARENT = ROOT / 'prepared-encoder-upstream-99b'
PARENT_SHA = 'f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a'
PACKET = ROOT / 'prepared-resolution-reference-101b'
RUN_NAME = 'encoder-server-resolution-reference-101b-two-way-w1-b1-p1-dxpu2-s640x384'
HERE = Path(__file__).resolve().parent
AUTHOR = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261007-resolution-runtime')
PLAN = AUTHOR.parent / '20261007-resolution-reference/candidate-plan.json'
PLAN_SHA = '307ff7547b8275c75d7f642673174cac11a45e0d7bc0041958a834544faa8745'
COMMON, LAUNCHER = 'launch/encoder_runtime_common.py', 'launch/serve-encoder.py'
STATUS = b'Packet101b successor after packet101 native-preparation refusal; same-size native reference candidate, not GPU-qualified.\n'
# File names are deliberately explicit: no ambient files or caller-chosen code.
COMPONENTS = ('geometry_overlay.py', 'native_safety.py', 'native_adapter.py',
              'session.py', 'executor_guard.py', 'runtime_observer.py', 'setup_gates.py',
              'reference_gate.py', 'candidate_gate.py', 'request_client.py',
              'schedule.py', 'integration.py', 'campaign.py', 'runtime_packet.py')
RUNTIME_MODULES = {n: ('ltx_resolution_session.py' if n == 'session.py' else n)
                   for n in COMPONENTS if n not in ('geometry_overlay.py', 'runtime_packet.py', 'campaign.py', 'request_client.py')}


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_parent_raw = (PARENT / 'manifest.json').read_bytes()
require(digest(_parent_raw) == PARENT_SHA, 'Qualified99b parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
require(digest((PARENT / COMMON).read_bytes()) == _parent_manifest['files'][COMMON], 'Parent checker changed')
BASE = load(PARENT / COMMON, 'resolution101_qualified_parent')
regular, sha, safe_path, module = BASE.regular, BASE.sha, BASE.safe_path, BASE.module
NODES = [*BASE.NODES, 'ltx_resolution_lab']


def __getattr__(name):
    return getattr(BASE, name)


def replace_once(text, old, new):
    require(text.count(old) == 1, 'Source anchor changed: ' + repr(old))
    return text.replace(old, new)


def check_control_environment():
    expected = {'LTX_OUTPUT_SIZE': '640x384', 'LTX_BUSY_WINDOWS': '0',
                'LTX_SAMPLER_PLACEMENT': 'two-way', 'LTX_SAMPLER_WORKERS': '1',
                'LTX_SAMPLER_BATCH': '1', 'LTX_SAMPLER_SHARED_POOL': '1',
                'LTX_DECODE_REPLICA_DEVICE': 'xpu:2', 'LTX_DECODE_REPLICAS': '1',
                'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0'}
    require(all(os.environ.get(k) == v for k, v in expected.items()), 'Explicit101 environment differs')


def launcher_source(raw):
    text = raw.decode()
    text = replace_once(text,
        "re.fullmatch(r'encoder-server-upstream-99b-two-way-w2-b1-p1-dxpu2-s256x256(?:-r[2-5])?', run_name)",
        "run_name == " + repr(RUN_NAME))
    text = replace_once(text, 'Packet99b admits only the frozen batch-one compatibility control',
                        'Packet101 admits only the reviewed W1 same-size reference experiment')
    text = replace_once(text, "    identity = {'runtime99b_transition': manifest['rope99b'],",
                        "    identity = {'resolution101_transition': manifest['resolution101'],\n"
                        "                'runtime99b_transition': manifest['rope99b'],")
    text = replace_once(text, "    runpy.run_path(str(packet / 'source/main.py'), run_name='__main__')",
                        "    import integration as resolution_integration\n"
                        "    resolution_integration.install(packet, manifest, digest, run)\n"
                        "    runpy.run_path(str(packet / 'source/main.py'), run_name='__main__')")
    ast.parse(text)
    return text.encode()


def source_delta(component_dir):
    geom = load(component_dir / 'geometry_overlay.py', 'resolution101_geometry')
    safety = load(component_dir / 'native_safety.py', 'resolution101_safety')
    delta = geom.transform_sources({p: regular(PARENT / p) for p in geom.SOURCE_HASHES})
    delta['source/comfy/sd.py'] = safety.transform_sd(regular(PARENT / 'source/comfy/sd.py'))
    # Existing NA decoder initialization verifies comfy.sd's source bytes even
    # when its numerical path is not selected. Update only this integrity pin
    # in both mirrors to the reviewed OOM-refusal overlay, preserving its code.
    for path in ('source/scripts/na_axis_decode_node.py',
                 'source/custom_nodes/ltx_na_axis_decode_lab/__init__.py'):
        raw = regular(PARENT / path)
        require(digest(raw) == _parent_manifest['files'][path], 'Parent NA decoder node changed')
        text = replace_once(raw.decode(),
            "SD_SHA = '" + safety.SOURCE_SHA256 + "'",
            "SD_SHA = '" + digest(delta['source/comfy/sd.py']) + "'")
        ast.parse(text)
        delta[path] = text.encode()
    delta[LAUNCHER] = launcher_source(regular(PARENT / LAUNCHER))
    delta[COMMON] = regular(component_dir / 'runtime_packet.py')
    return delta


def input_inventory():
    missing = [n for n in COMPONENTS if not (AUTHOR / n).is_file()]
    require(not missing, 'Integration incomplete: ' + ', '.join(missing))
    files = {n: sha(AUTHOR / n) for n in COMPONENTS}
    plan = json.loads(regular(PLAN))
    require(plan['plan_sha256'] == PLAN_SHA == digest(canonical(plan['plan'])), 'Reviewed plan changed')
    files['candidate-plan.json'] = sha(PLAN)
    return files


def extra_files(component_dir, plan_raw, plan_path=PLAN):
    result = {'provenance/packet99b-manifest.json': regular(PARENT / 'manifest.json'),
              'resolution/candidate-plan.json': plan_raw}
    for name in COMPONENTS:
        raw = regular(component_dir / name)
        result['resolution/components/' + name] = raw
        if name in RUNTIME_MODULES:
            result['source/scripts/' + RUNTIME_MODULES[name]] = raw
    schedule = load(component_dir / 'schedule.py', 'resolution101_schedule')
    # The reviewed plan is identical in author and packet copies. Source graph
    # inputs remain the immutable99b packet even when verifying a successor.
    schedule_value = schedule.build_schedule(plan_path=plan_path)
    result['resolution/setup-schedule.json'] = json.dumps(schedule_value, indent=2, sort_keys=True).encode() + b'\n'
    result['source/custom_nodes/ltx_resolution_lab/__init__.py'] = (
        b'from integration import NODE_CLASS_MAPPINGS, install_routes\ninstall_routes()\n')
    return result


def semantic_manifest(parent, files, transition):
    result = copy.deepcopy(parent)
    result.update(schema='ltx.resolution-reference-runtime.v1', files=files,
                  preparer_sha256=files['resolution/components/runtime_packet.py'], resolution101=transition)
    result['startup_tools'] = {Path(k).name: files[k] for k in (COMMON, LAUNCHER)}
    for name in result['extension_sha256s']:
        path = 'source/scripts/' + name
        if path in files:
            result['extension_sha256s'][name] = files[path]
    for name in RUNTIME_MODULES.values():
        result['extension_sha256s'][name] = files['source/scripts/' + name]
    result['output_size']['module_sha256'] = files['source/scripts/ltx_output_size_98.py']
    result['output_size']['same_size_native'] = {'plan_sha256': PLAN_SHA,
        'size': '640x384', 'comparison_mode': 'same-size-native-v1', 'qualified': False}
    return result


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET, 'Unexpected101 packet path')
    require(re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or '') and
            sha(packet / 'manifest.json') == expected_manifest_sha256, '101 manifest hash differs')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    manifest = json.loads(regular(packet / 'manifest.json'))
    require(regular(packet / 'STATUS.txt') == STATUS, 'Status identity differs')
    # Verify bytes against the externally pinned manifest BEFORE executing any
    # successor component, including its source-transform helpers.
    require(isinstance(manifest.get('files'), dict), '101 file inventory missing')
    for path, expected in manifest['files'].items():
        require(isinstance(path, str) and isinstance(expected, str) and
                re.fullmatch('[0-9a-f]{64}', expected) and
                sha(safe_path(packet, path)) == expected, '101 file changed before component import: ' + str(path))
    require(all('resolution/components/' + n in manifest['files'] for n in COMPONENTS),
            '101 component inventory incomplete')
    component_dir = packet / 'resolution/components'
    delta = source_delta(component_dir)
    extras = extra_files(component_dir, regular(packet / 'resolution/candidate-plan.json'),
                         packet / 'resolution/candidate-plan.json')
    want = dict(parent['files'])
    for path, raw in delta.items():
        require(regular(packet / 'provenance/packet99b' / path) == regular(PARENT / path),
                'Parent delta provenance changed')
        want['provenance/packet99b/' + path] = parent['files'][path]
        want[path] = digest(raw)
    want.update({path: digest(raw) for path, raw in extras.items()})
    require(manifest['files'] == want, '101 source closure differs')
    checker = module(PARENT / 'provenance/source99/check-upstream-source-99.py', 'resolution101_inventory')
    require(checker.inventory(packet) == set(want) | {'manifest.json', 'STATUS.txt'}, 'Unbound101 packet file')
    for path, expected in want.items():
        require(sha(safe_path(packet, path)) == expected, '101 file changed: ' + path)
    plan = json.loads(regular(packet / 'resolution/candidate-plan.json'))
    require(plan['plan_sha256'] == PLAN_SHA == digest(canonical(plan['plan'])), '101 plan changed')
    transition = manifest['resolution101']
    inventory = {n: filesha for n, filesha in
                 ((n, want['resolution/components/' + n]) for n in COMPONENTS)}
    inventory['candidate-plan.json'] = want['resolution/candidate-plan.json']
    expected_transition = {'schema': 'ltx.resolution101.transition.v1', 'packet_revision': '101b',
        'parent_packet': str(PARENT), 'parent_manifest_sha256': PARENT_SHA,
        'plan_sha256': PLAN_SHA, 'input_inventory': inventory,
        'input_inventory_sha256': digest(canonical(inventory)),
        'source_delta': {p: {'before_sha256': parent['files'][p], 'after_sha256': digest(raw)}
                         for p, raw in delta.items()},
        'control': {'size': '640x384', 'batch': 1, 'workers': 1, 'layout': 'two-way',
                    'shared_pool': 1, 'decode_replica': 'xpu:2'},
        'storage_admission': transition['storage_admission'], 'qualification': False, 'model_requests': 0}
    require(transition == expected_transition and transition['storage_admission']['admitted'] is True,
            '101 transition differs')
    require(manifest == semantic_manifest(parent, want, transition), '101 semantic contract differs')
    return manifest


def write_new(path, raw, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw); os.fchmod(f.fileno(), mode); f.flush(); os.fsync(f.fileno())


def build(expected_inventory_sha256, parent_stopped=False):
    require(parent_stopped is True, 'Coordinator must establish parent cleanly stopped')
    inventory = input_inventory()
    require(digest(canonical(inventory)) == expected_inventory_sha256, 'Reviewed source inventory differs')
    require(not PACKET.exists() and not PACKET.is_symlink() and
            not any(p.is_symlink() for p in PACKET.parents), 'Exclusive regular destination required')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    storage = module(PARENT / 'launch/check-storage-headroom.py', 'resolution101_build_storage')
    admission = storage.inspect_destination(PACKET, 50 * 1024**3, 384 * 1024**2)
    require(admission['admitted'], '50GiB reserve plus384MiB build allowance required')
    delta = source_delta(AUTHOR)
    extras = extra_files(AUTHOR, regular(PLAN))
    require(input_inventory() == inventory, 'Authored components changed during read')
    PACKET.mkdir(mode=0o700)
    write_new(PACKET / 'STATUS.txt', STATUS)
    for path, expected in parent['files'].items():
        raw = regular(PARENT / path)
        require(digest(raw) == expected, 'Parent changed during copy')
        mode = stat.S_IMODE((PARENT / path).stat().st_mode)
        if path in delta:
            write_new(PACKET / 'provenance/packet99b' / path, raw, mode)
            raw = delta[path]
        write_new(PACKET / path, raw, mode)
    for path, raw in extras.items():
        require(path not in parent['files'], 'New helper collides with parent: ' + path)
        write_new(PACKET / path, raw)
    files = {str(p.relative_to(PACKET)): sha(p) for p in PACKET.rglob('*')
             if p.is_file() and p.name != 'STATUS.txt'}
    transition = {'schema': 'ltx.resolution101.transition.v1', 'packet_revision': '101b', 'parent_packet': str(PARENT),
        'parent_manifest_sha256': PARENT_SHA, 'plan_sha256': PLAN_SHA,
        'input_inventory': inventory, 'input_inventory_sha256': expected_inventory_sha256,
        'source_delta': {p: {'before_sha256': parent['files'][p], 'after_sha256': digest(raw)}
                         for p, raw in delta.items()},
        'control': {'size': '640x384', 'batch': 1, 'workers': 1, 'layout': 'two-way',
                    'shared_pool': 1, 'decode_replica': 'xpu:2'},
        'storage_admission': admission, 'qualification': False, 'model_requests': 0}
    manifest = semantic_manifest(parent, files, transition)
    write_new(PACKET / 'manifest.json', json.dumps(manifest, indent=2, sort_keys=True).encode() + b'\n')
    for directory in [p for p in PACKET.rglob('*') if p.is_dir()] + [PACKET, PACKET.parent]:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    manifest_sha = sha(PACKET / 'manifest.json')
    verify_packet(PACKET, manifest_sha)
    return {'status': 'prepared-not-GPU-qualified', 'packet': str(PACKET),
            'manifest_sha256': manifest_sha, 'model_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--input-inventory-sha256')
    parser.add_argument('--parent-stopped', action='store_true')
    parser.add_argument('--verify-manifest-sha256')
    args = parser.parse_args()
    if args.build:
        result = build(args.input_inventory_sha256, args.parent_stopped)
    elif args.verify_manifest_sha256:
        verify_packet(PACKET, args.verify_manifest_sha256)
        result = {'status': 'source-closure-verified', 'model_requests': 0}
    else:
        missing = [n for n in COMPONENTS if not (AUTHOR / n).is_file()]
        result = {'status': 'plan-only', 'packet': str(PACKET), 'missing_components': missing,
                  'model_requests': 0, 'materialized': False}
        if not missing:
            inventory = input_inventory()
            result.update(input_inventory=inventory, input_inventory_sha256=digest(canonical(inventory)))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

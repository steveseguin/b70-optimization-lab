#!/usr/bin/env python3
"""Exact sealed-113 successor assembly for packet114. Default inventories; --build is explicit.

Installed in the packet as launch/encoder_runtime_common.py. Packet114 is the sealed
packet113 with replaced stream components (latent anchor, ordered decode thread, chunk
length 49/97, text reuse on by default, `stream114-` names), two geometry literals
(ltx_output_size_98.py, ltx_duration_guard.py) and the launcher literals that name the
packet, plus the launcher name-collision preflight. Every other file is copied
byte-for-byte from 113 (which is itself verified against 112 and 111 at load and at
launch). Reading the sealed packets needs no process action. This builder never
contacts an endpoint, imports Torch or touches a device. Changed parent files survive
under provenance/packet113/.
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
PARENT = ROOT / 'prepared-continuation-stream-113'
PARENT_SHA = 'a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b'
PACKET = ROOT / 'prepared-continuation-stream-114'
FRAMES = ('49', '97')
PLACEMENTS = ('two-way', 'two-way20-28')
ANCHORS = ('latent', 'frame')
RUN_NAMES = {'%s/%s/%s' % (f, p, a): 'encoder-server-continuation-stream-114-%s-%s-w1-b1-p1-dxpu2-s256x256-f%s'
             % (a, p, f) for f in FRAMES for p in PLACEMENTS for a in ANCHORS}
PARENT_RUN_NAMES = {'%s/%s' % (f, p): 'encoder-server-continuation-stream-113-%s-w1-b1-p1-dxpu2-s256x256-f%s' % (p, f)
                    for f in ('49', '25') for p in PLACEMENTS}
AUTHOR = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation114-stream')
PLAN = AUTHOR / 'stream-plan.json'
PLAN_SHA = 'e87c62149c1310617da15510ed71167c0fb9cceb52556d220ffca69f57949b5b'
PARENT_PLAN_SHA = '9dd583d41c9c3c5e8d123cefecba815ac1810b15601c23da15941e2372a27317'
PARENT_QIDS = {
    '49/two-way': '09c1fda000494fb391e934fcffc83aa5169d80626a13f3c9edf715111da318b8',
    '49/two-way20-28': '0f7cda48784e92bdb6ff99708ae12809838eaf0b1db535d259f0a116a2ab9b0e',
    '25/two-way': 'b5ea97da305a36b13922d78d8fb4f5b6353ab71ad5e9680ad8bf81ce60c4a2b3',
    '25/two-way20-28': '7d40ff29e6d76a9b5bfc5503933d1d4e95d6e36532a51d8e76a2bd3a5e5f01ad',
}
QIDS = {
    '49/two-way/frame': 'f1f0214eb35003db3f1a3c7485a9811fd900b0a946b785b91c073c77a577f5f1',
    '49/two-way/latent': '53d3e465e40f96358138a80eca86dc6e0c94109caa670e03745652954c936eb8',
    '49/two-way20-28/frame': '9cc374ee97d4d00d278f5a6c562ebf0d5da77331860ebc686a0106f818d64f1e',
    '49/two-way20-28/latent': 'd49c4874b23d5e03b545d123c44b7aedbd764e332e18e54d1eb47442fed577eb',
    '97/two-way/frame': 'a8b9f54441e6517d2e1717928ac2b812a14b6937868db9d494487ca2456196ab',
    '97/two-way/latent': 'ab1f02edeab2e88e6c885199daa51ce36b1690aedc0b6627e90e5531f1f5115a',
    '97/two-way20-28/frame': 'f213bfd0b228152e05fe36de935d705d5ddeaa7e717f08d003745f515da4562e',
    '97/two-way20-28/latent': 'd85b23d7b79386a05c42dce3a5d86d5d5df68af6fab2d8d16932eebdb07e3d52',
}
COMMON, LAUNCHER = 'launch/encoder_runtime_common.py', 'launch/serve-encoder.py'
STATUS = (b'Packet114 = packet113 256x256 continuation stream with a latent anchor (frame anchor as a launch '
          b'option), the decode on one ordered thread off the chain, 49- or 97-frame chunks and text reuse on '
          b'by default; nine-capture exact qualification gates streaming; not GPU-qualified.\n')
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
require(digest(_parent_raw) == PARENT_SHA, 'Sealed113 parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
require(digest((PARENT / COMMON).read_bytes()) == _parent_manifest['files'][COMMON], 'Sealed113 checker changed')
BASE = load(PARENT / COMMON, 'stream114_parent113')
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
            'Explicit packet114 environment differs: ' + json.dumps(CONTROL_ENVIRONMENT, sort_keys=True))
    require(os.environ.get('LTX_STREAM_TEXT_REUSE') in ('0', '1'), 'LTX_STREAM_TEXT_REUSE must be set to 0 or 1')
    require(os.environ.get('LTX_STREAM_FRAMES') in FRAMES, 'LTX_STREAM_FRAMES must be set to 49 or 97')
    require(os.environ.get('LTX_SAMPLER_PLACEMENT') in PLACEMENTS,
            'LTX_SAMPLER_PLACEMENT must be set to two-way or two-way20-28')
    require(os.environ.get('LTX_ANCHOR') in ANCHORS, 'LTX_ANCHOR must be set to latent or frame')


def expected_run_name(environ=None):
    environ = os.environ if environ is None else environ
    return RUN_NAMES.get('%s/%s/%s' % (environ.get('LTX_STREAM_FRAMES'), environ.get('LTX_SAMPLER_PLACEMENT'),
                                       environ.get('LTX_ANCHOR')))


def name_collisions(names, prefix, root=ROOT):
    """Entries under output/, output/validation/ and requests/ that a packet114 server would collide with."""
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
    contract = module(Path(packet) / 'resolution/components/stream_contract.py', 'stream114_names')
    names, prefix = set(contract.fixed_names()), contract.RUN_PREFIX + '-'
    require(prefix == 'stream114-' and all(n.startswith(prefix) for n in names), 'Packet114 name prefix differs')
    found = name_collisions(names, prefix, root)
    require(not found, 'Packet114 names already exist (archive them first): ' + ', '.join(found[:12]) +
            (' and %d more' % (len(found) - 12) if len(found) > 12 else ''))
    return {'checked': list(NAME_DIRECTORIES), 'fixed_names': sorted(names), 'prefix': prefix, 'collisions': []}


def admit_storage(packet, run):
    helper = module(packet / 'launch/check-storage-headroom.py', 'stream114_storage')
    result = helper.inspect_destination(run, RESERVE, RUN_ALLOWANCE)
    require(result['admitted'], '50GiB reserve plus 3GiB stream allowance required')
    return result


# -- source transforms (applied to the sealed 113 files) ----------------------------
def geometry_source(raw, plan_sha, qids):
    """113's ltx_output_size_98.py: frames 49|97, the 114 plan, ids keyed by frames/placement/anchor, mode 114."""
    t = replace(raw, "if _STREAM_FRAMES not in ('49', '25'):\n    raise RuntimeError('LTX_STREAM_FRAMES must be 49 or 25')\n"
                     "FRAMES, TEMPORAL_LATENTS, AUDIO_LATENTS, AUDIO_SAMPLES = "
                     "{'49': (49, 7, 51, 96480), '25': (25, 4, 26, 48480)}[_STREAM_FRAMES]",
                "if _STREAM_FRAMES not in ('49', '97'):\n    raise RuntimeError('LTX_STREAM_FRAMES must be 49 or 97')\n"
                "FRAMES, TEMPORAL_LATENTS, AUDIO_LATENTS, AUDIO_SAMPLES = "
                "{'49': (49, 7, 51, 96480), '97': (97, 13, 101, 192480)}[_STREAM_FRAMES]")
    t = replace(t, "_RESOLUTION_PLAN_SHA256 = '" + PARENT_PLAN_SHA + "'", "_RESOLUTION_PLAN_SHA256 = '" + plan_sha + "'")
    t = replace(t, "_RESOLUTION_QUALIFICATION_ID = " + repr(PARENT_QIDS) +
                "[_STREAM_FRAMES + '/' + os.environ.get('LTX_SAMPLER_PLACEMENT', 'two-way')]",
                "_RESOLUTION_QUALIFICATION_ID = " + repr(qids) +
                "[_STREAM_FRAMES + '/' + os.environ.get('LTX_SAMPLER_PLACEMENT', 'two-way') + '/' + "
                "os.environ.get('LTX_ANCHOR', 'latent')]")
    t = replace(t, "_RESOLUTION_MODE = 'stream-candidate-112-v1'", "_RESOLUTION_MODE = 'stream-candidate-114-v1'")
    ast.parse(t)
    return t.encode()


def capture_guard_source(raw):
    """113's ltx_duration_guard.py: the 97-frame capture shapes."""
    t = replace(raw, "_T, _AL, _AS = {'49': (7, 51, 96480), '25': (4, 26, 48480)}[_STREAM_FRAMES]",
                "_T, _AL, _AS = {'49': (7, 51, 96480), '97': (13, 101, 192480)}[_STREAM_FRAMES]")
    t = replace(t, "'ltx.stream112-prewrite.v1'", "'ltx.stream114-prewrite.v1'")
    ast.parse(t)
    return t.encode()


def launcher_source(raw):
    t = replace(raw, 'common.require(run_name == ' + repr(PARENT_RUN_NAMES) +
                ".get('%s/%s' % (os.environ.get('LTX_STREAM_FRAMES'), os.environ.get('LTX_SAMPLER_PLACEMENT'))),\n"
                "                   'Packet113 admits only the 256x256 continuation stream server')",
                "common.require(run_name == common.expected_run_name(),\n"
                "                   'Packet114 admits only the 256x256 continuation stream server')")
    t = replace(t, "    manifest = common.verify_packet(packet, digest)\n",
                "    manifest = common.verify_packet(packet, digest)\n"
                "    # Packet114 naming rule (the 113 naming incident): refuse before any device work, also in --check-only.\n"
                "    common.check_name_collisions(packet)\n")
    ast.parse(t)
    return t.encode()


# -- assembly -------------------------------------------------------------------
def check_plan(raw):
    envelope = json.loads(raw)
    require(envelope['plan_sha256'] == PLAN_SHA == digest(canonical(envelope['plan'])) and
            envelope['plan']['qualification_ids'] == QIDS, 'Reviewed114 plan changed')
    return envelope['plan']


def input_inventory():
    files = {n: sha(AUTHOR / n) for n in COMPONENTS}
    check_plan(regular(PLAN))
    files['stream-plan.json'] = sha(PLAN)
    return files


def successor_files(component_dir, plan_raw):
    check_plan(plan_raw)
    result = {'provenance/packet113-manifest.json': regular(PARENT / 'manifest.json'),
              'resolution/stream-plan.json': plan_raw}
    require(digest(result['provenance/packet113-manifest.json']) == PARENT_SHA, 'Parent manifest changed')
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
    # Components identical to the sealed 113 copies are not 'changed' (they stay inherited).
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
            files['provenance/packet113/' + path] = parent['files'][path]
        files[path] = digest(raw)
    return files


def transition(parent, changed, inventory, admission):
    return {'schema': 'ltx.stream114.transition.v1', 'packet_revision': '114',
            'parent_packet': str(PARENT), 'parent_manifest_sha256': PARENT_SHA,
            'plan_sha256': PLAN_SHA, 'qualification_ids': QIDS, 'input_inventory': inventory,
            'input_inventory_sha256': digest(canonical(inventory)),
            'source_delta': {p: {'before_sha256': parent['files'].get(p), 'after_sha256': digest(raw)}
                             for p, raw in changed.items()},
            'control': {'size': '256x256', 'frame_count': 'LTX_STREAM_FRAMES (49 or 97; launched at 97)',
                        'fps': 24, 'layout': 'LTX_SAMPLER_PLACEMENT (two-way or two-way20-28; launched two-way20-28)',
                        'anchor': 'LTX_ANCHOR (latent default; frame = packet113 decoded-frame anchor for the A/B)',
                        'workers': 1, 'batch': 1, 'shared_pool': 1,
                        'decode_replica_env': 'xpu:2 (environment only; native VAEDecode, zero replicas)',
                        'decoder_graph_capture': 'not enabled',
                        'decode': 'one ordered decode thread on xpu:3, bounded FIFO, back-pressure, latch',
                        'preview': 'one bounded FIFO writer thread behind the decode thread',
                        'chain_reset': 'stream chunk reset=1 is unanchored (stream_seq 0 form)',
                        'graph_replay': 'LTXGraphCaptureGate all48 chain1', 'qualification_requests': 9,
                        'full_captures': 9, 'stream_requests': 'unbounded, serial, storage-bounded',
                        'environment': CONTROL_ENVIRONMENT, 'text_reuse_env': 'LTX_STREAM_TEXT_REUSE (1 default)',
                        'names': 'stream114- prefix; launcher refuses existing names (also --check-only)',
                        'stage_overlap_across_cards': 'not in 114 (packet 115)'},
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
    result['output_size']['stream114'] = {'plan_sha256': PLAN_SHA, 'size': '256x256', 'frame_count': [49, 97],
                                          'anchor': list(ANCHORS), 'comparison_mode': 'stream-candidate-114-v1',
                                          'qualified': False,
                                          'numerics_from': 'packet113 sampler/decoder; latent anchor is new output'}
    return result


def assembly_bytes(parent, changed):
    original = sum((PARENT / p).stat().st_size for p in parent['files'])
    return original + sum(len(raw) for raw in changed.values()) + len(STATUS)


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET and re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or ''),
            'Unexpected114 packet or manifest identity')
    require(sha(packet / 'manifest.json') == expected_manifest_sha256, '114 manifest changed')
    manifest = json.loads(regular(packet / 'manifest.json'))
    require(regular(packet / 'STATUS.txt') == STATUS, '114 status identity changed')
    require(type(manifest.get('files')) is dict, '114 file inventory missing')
    for path, expected in manifest['files'].items():
        require(type(path) is str and type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected)
                and sha(safe_path(packet, path)) == expected, '114 file changed before component import: ' + str(path))
    require(all('resolution/components/' + n in manifest['files'] for n in COMPONENTS),
            '114 component inventory incomplete')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(packet / 'resolution/components', regular(packet / 'resolution/stream-plan.json'))
    expected_files = manifest_files(parent, changed)
    require(manifest['files'] == expected_files, '114 source closure differs')
    checker_path = 'provenance/source99/check-upstream-source-99.py'
    require(sha(PARENT / checker_path) == parent['files'][checker_path], 'Inventory checker changed')
    checker = module(PARENT / checker_path, 'stream114_inventory')
    require(checker.inventory(packet) == set(expected_files) | {'manifest.json', 'STATUS.txt'},
            'Unbound114 packet file')
    inventory = {n: expected_files['resolution/components/' + n] for n in COMPONENTS}  # all bound
    inventory['stream-plan.json'] = expected_files['resolution/stream-plan.json']
    admission = manifest['resolution101']['storage_admission']
    require(admission['admitted'] is True, '114 build was not admitted')
    change = transition(parent, changed, inventory, admission)
    require(manifest == semantic_manifest(parent, expected_files, change), '114 semantic identity differs')
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
    require(inspected['input_inventory_sha256'] == expected_inventory_sha256, 'Reviewed114 inputs differ')
    require(not PACKET.exists() and not PACKET.is_symlink() and
            not any(p.is_symlink() for p in PACKET.parents), 'Exclusive regular packet destination required')
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    changed = successor_files(AUTHOR, regular(PLAN))
    inventory = input_inventory()
    require(inventory == inspected['input_inventory'], 'Inputs changed after review')
    helper = module(PARENT / 'launch/check-storage-headroom.py', 'stream114_build_storage')
    admission = helper.inspect_destination(PACKET, RESERVE + RUN_ALLOWANCE, BUILD_ALLOWANCE)
    require(admission['admitted'], '50GiB reserve plus 3GiB run plus 160MiB build allowance required')
    PACKET.mkdir(mode=0o700)
    write_new(PACKET / 'STATUS.txt', STATUS)
    for path, expected in parent['files'].items():
        raw = regular(PARENT / path)
        require(digest(raw) == expected, 'Parent file changed while copying: ' + path)
        mode = stat.S_IMODE((PARENT / path).stat().st_mode)
        if path in changed:
            write_new(PACKET / 'provenance/packet113' / path, raw, mode)
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

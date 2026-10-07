#!/usr/bin/env python3
"""Plan the one 20/28 successor, or explicitly build after packet99 qualifies/stops.

Default is read-only. Never launches, stops, modifies or deletes an existing
packet. The coordinator must stop99 before invoking --build; no retry policy.
"""
import argparse
import difflib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('build100_checker', HERE / 'check-runtime-100.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def plan():
    parent = C.BASE.load_json(C.regular(C.PARENT / 'manifest.json'))
    C.require(C.sha(C.PARENT / 'manifest.json') == C.PARENT_SHA, 'Parent manifest changed')
    delta = C.source_delta(C.regular(C.PARENT / C.SHARD), C.regular(C.PARENT / C.CAPTURE))
    return {'status': 'plan-only-no-materialization-no-qualification',
            'parent': str(C.PARENT), 'parent_manifest_sha256': C.PARENT_SHA,
            'output': str(C.PACKET), 'control': C.control(),
            'source_delta': {p: {'before_sha256': parent['files'][p], 'after_sha256': C.digest(raw),
                'diff': ''.join(difflib.unified_diff(C.regular(C.PARENT / p).decode().splitlines(keepends=True),
                    raw.decode().splitlines(keepends=True), fromfile='packet99/' + p, tofile='packet100/' + p))}
                for p, raw in delta.items()},
            'unchanged': ['23/25 default layout', 'upstream source identity except named placement/pin',
                'all graph JSON/arithmetic/native attention guards', 'isolated dependency overlay and baseline Torch',
                'model/references', 'health/fault halt/progress lock/NOFILE/storage gates'],
            'build_requires': ['qualified99 control basis SHA and original identity/freeze/quality receipts',
                'reviewed bound runner100 and memory-helper100', 'coordinator confirms parent99 stopped',
                '50GiB reserve plus384MiB preparation allowance', 'new destination only'],
            'memory_projection': 'Validated99 freeze minus3*.97+.25GiB on card1; no card0 credit; live gates remain required',
            'qualification': False, 'model_requests': 0}


def write_new(path, raw, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw); os.fchmod(f.fileno(), mode); f.flush(); os.fsync(f.fileno())


def build(output, runner, memory_helper, control_basis, control_basis_sha256, parent_stopped):
    C.require(parent_stopped is True, 'Coordinator must confirm parent99 cleanly stopped; no live materialization')
    C.require(output == C.PACKET and not output.exists() and not output.is_symlink() and
              output.parent.is_dir() and not any(p.is_symlink() for p in output.parents),
              'Only agreed new output with regular existing parent admitted')
    parent = C.BASE.verify_packet(C.PARENT, C.PARENT_SHA)
    C.require(runner is not None and memory_helper is not None and control_basis is not None,
              'Explicit reviewed runner, memory helper and qualified99 basis required')
    bindings = {}
    for kind, path, filename in [('runner', runner, 'run-campaign-100.sh'),
                                 ('memory_helper', memory_helper, 'worker-headroom-100.py')]:
        C.require(path.name == filename, 'Unexpected campaign helper filename')
        raw = C.regular(path)
        bindings[kind] = {'source': str(path), 'sha256': C.digest(raw), 'packet_path': 'campaign/' + filename}
    helper = C.module(memory_helper, 'packet100_build_memory')
    C.validate_basis(helper, control_basis, control_basis_sha256)
    basis_raw = C.regular(control_basis)
    C.require(C.digest(basis_raw) == control_basis_sha256, 'Control basis changed after validation')
    storage = C.module(C.PARENT / 'launch/check-storage-headroom.py', 'packet100_build_storage')
    admission = storage.inspect_destination(output, 50 * 1024**3, 384 * 1024**2)
    C.require(admission['admitted'], '50GiB reserve plus384MiB required before any write')
    delta = C.source_delta(C.regular(C.PARENT / C.SHARD), C.regular(C.PARENT / C.CAPTURE))
    source_receipt = {p: {'before_sha256': parent['files'][p], 'after_sha256': C.digest(raw)}
                      for p, raw in delta.items()}
    delta[C.LAUNCHER] = C.launcher_source(C.regular(C.PARENT / C.LAUNCHER))
    delta[C.COMMON] = C.regular(HERE / 'check-runtime-100.py')
    # No output exists before qualified-control/helper/parent/storage admission.
    output.mkdir(mode=0o700)
    write_new(output / 'STATUS.txt', C.STATUS)
    for path, expected in parent['files'].items():
        raw = C.regular(C.PARENT / path)
        C.require(C.digest(raw) == expected, 'Parent changed while copying: ' + path)
        mode = stat.S_IMODE((C.PARENT / path).stat().st_mode)
        if path in delta:
            write_new(output / 'provenance/packet99' / path, raw, mode)
            raw = delta[path]
        write_new(output / path, raw, mode)
    for name in ('build-runtime-100.py', 'check-runtime-100.py'):
        write_new(output / 'provenance' / name, C.regular(HERE / name))
    write_new(output / 'provenance/packet99-manifest.json', C.regular(C.PARENT / 'manifest.json'))
    write_new(output / 'provenance/control-basis.json', basis_raw)
    for binding in bindings.values():
        raw = C.regular(Path(binding['source']))
        C.require(C.digest(raw) == binding['sha256'], 'Campaign helper changed during build')
        write_new(output / binding['packet_path'], raw)
    files = {str(p.relative_to(output)): C.sha(p) for p in output.rglob('*')
             if p.is_file() and p != output / 'STATUS.txt'}
    transition = {'schema': 'ltx.rebalance100.transition.v1', 'parent_packet': str(C.PARENT),
        'parent_manifest_sha256': C.PARENT_SHA, 'control': C.control(), 'source_delta': source_receipt,
        'campaign_bindings': bindings, 'control_basis': {'source': str(control_basis),
            'sha256': control_basis_sha256, 'packet_path': 'provenance/control-basis.json'},
        'storage_admission': admission, 'qualification': False, 'model_requests': 0}
    manifest = C.semantic_manifest(parent, files, C.sha(Path(__file__).resolve()), transition)
    write_new(output / 'manifest.json', (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    for directory in [p for p in output.rglob('*') if p.is_dir()] + [output, output.parent]:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    digest = C.sha(output / 'manifest.json')
    C.verify_packet(output, digest)
    return {'status': 'prepared-candidate-not-GPU-qualified', 'packet': str(output),
            'manifest_sha256': digest, 'qualification': False, 'model_requests': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', action='store_true')
    p.add_argument('--output', type=Path, default=C.PACKET)
    p.add_argument('--runner', type=Path); p.add_argument('--memory-helper', type=Path)
    p.add_argument('--control-basis', type=Path); p.add_argument('--control-basis-sha256')
    p.add_argument('--parent-stopped', action='store_true', help='Coordinator assertion of clean99 shutdown; never stops it')
    args = p.parse_args()
    result = build(args.output, args.runner, args.memory_helper, args.control_basis,
                   args.control_basis_sha256, args.parent_stopped) if args.build else plan()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

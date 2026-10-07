#!/usr/bin/env python3
"""Prepare a separate process-local RoPE compatibility candidate; never launch.

Default is read-only. Parent99 source/dependencies are copied unchanged; only
startup/common and the bound compatibility installer differ. No overwrite.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('build99b_checker', HERE / 'check-runtime-99b.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def plan():
    parent = C.BASE.load_json(C.regular(C.PARENT / 'manifest.json'))
    C.require(C.sha(C.PARENT / 'manifest.json') == C.PARENT_SHA, 'Parent changed')
    return {'status': 'plan-only-no-materialization-no-qualification',
            'parent': str(C.PARENT), 'parent_manifest_sha256': C.PARENT_SHA,
            'output': str(C.PACKET), 'control': parent['upstream99']['control'],
            'source_delta': {}, 'dependencies': 'Byte-identical99 overlay; process-local RoPE override only',
            'installer_source': str(C.INSTALLER_ROOT),
            'installer_files': C.installer_files() if C.INSTALLER_ROOT.exists() else None,
            'activation': 'after GPU preflight and normal CLI/quant_ops policy, before final identity and main',
            'launch_gates': 'All99 limits/storage/health/fault/ownership/progress/determinism/reference gates retained',
            'qualification': False, 'model_requests': 0}


def write_new(path, raw, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw); os.fchmod(f.fileno(), mode); f.flush(); os.fsync(f.fileno())


def build(output, runner, memory_helper, parent_stopped):
    C.require(parent_stopped is True, 'Coordinator must confirm parent99 cleanly stopped')
    C.require(output == C.PACKET and not output.exists() and not output.is_symlink() and
              output.parent.is_dir() and not any(p.is_symlink() for p in output.parents),
              'Only agreed new output with regular existing parent admitted')
    parent = C.BASE.verify_packet(C.PARENT, C.PARENT_SHA)
    C.require(runner is not None and memory_helper is not None, 'Explicit reviewed campaign helper paths required')
    bindings = {}
    for kind, path, filename in [('runner', runner, 'run-campaign-99b.sh'),
                                 ('memory_helper', memory_helper, 'worker-headroom-98.py')]:
        C.require(path.name == filename, 'Unexpected campaign filename')
        raw = C.regular(path)
        bindings[kind] = {'source': str(path), 'sha256': C.digest(raw), 'packet_path': 'campaign/' + filename}
    C.require(bindings['memory_helper'] == parent['upstream99']['campaign_bindings']['memory_helper'],
              'Baseline headroom helper must remain unchanged')
    installer = C.installer_files()
    storage = C.module(C.PARENT / 'launch/check-storage-headroom.py', 'packet99b_build_storage')
    admission = storage.inspect_destination(output, 50 * 1024**3, 384 * 1024**2)
    C.require(admission['admitted'], '50GiB reserve plus384MiB required before any write')
    delta = {C.LAUNCHER: C.launcher_source(C.regular(C.PARENT / C.LAUNCHER)),
             C.COMMON: C.regular(HERE / 'check-runtime-99b.py')}
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
    for name in ('build-runtime-99b.py', 'check-runtime-99b.py'):
        write_new(output / 'provenance' / name, C.regular(HERE / name))
    write_new(output / 'provenance/packet99-manifest.json', C.regular(C.PARENT / 'manifest.json'))
    for name, expected in installer.items():
        raw = C.regular(C.INSTALLER_ROOT / name)
        C.require(C.digest(raw) == expected, 'Installer changed during build')
        write_new(output / 'launch/rope-compat' / name, raw)
    for binding in bindings.values():
        # The identical memory helper is already preserved from the parent.
        if binding['packet_path'] in parent['files']:
            C.require(parent['files'][binding['packet_path']] == binding['sha256'], 'Inherited campaign changed')
            continue
        raw = C.regular(Path(binding['source']))
        C.require(C.digest(raw) == binding['sha256'], 'Campaign helper changed during build')
        write_new(output / binding['packet_path'], raw)
    files = {str(p.relative_to(output)): C.sha(p) for p in output.rglob('*')
             if p.is_file() and p != output / 'STATUS.txt'}
    transition = {'schema': 'ltx.rope99b.transition.v1', 'parent_packet': str(C.PARENT),
        'parent_manifest_sha256': C.PARENT_SHA, 'control': parent['upstream99']['control'],
        'installer': {'source': str(C.INSTALLER_ROOT), 'files': installer,
                      'activation': 'after-preflight-and-normal-quant-ops-import-before-identity-and-main'},
        'campaign_bindings': bindings, 'storage_admission': admission, 'qualification': False, 'model_requests': 0}
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
    return {'status': 'prepared-compatibility-candidate-not-GPU-qualified', 'packet': str(output),
            'manifest_sha256': digest, 'qualification': False, 'model_requests': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', action='store_true')
    p.add_argument('--output', type=Path, default=C.PACKET)
    p.add_argument('--runner', type=Path); p.add_argument('--memory-helper', type=Path)
    p.add_argument('--parent-stopped', action='store_true', help='Coordinator assertion of clean99 shutdown; never stops it')
    a = p.parse_args()
    result = build(a.output, a.runner, a.memory_helper, a.parent_stopped) if a.build else plan()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

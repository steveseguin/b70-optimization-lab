#!/usr/bin/env python3
"""Compile only packet46; read-only link reuse of sealed packet45 dependencies.

No compiler, cmake or hashing of large binary inputs before the timing cutoff.
No accelerator enumeration or device binary runs occur in this script.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from preparation import exclusive_cpu_work
from mirror_inputs import validate_baseline_mirror, own_mirror

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = HERE.parent / 'packet45-merged3'

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def baseline(mode):
    kind = 'gnu-host' if mode == 'host' else 'device'
    directory = BASE / 'build' / kind
    receipt_path = BASE / f'build-{kind}-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('passed') is not True or receipt.get('device_executed') is not False:
        raise ValueError('missing CPU-only passing baseline build receipt')
    closure = receipt['compiled_sources_sha256']
    for name, digest in closure.items():
        if sha(ROOT / name) != digest:
            raise ValueError('sealed baseline source changed: ' + name)
    commands = directory / 'compile_commands.json'
    if sha(commands) != receipt['compile_commands_sha256']:
        raise ValueError('baseline compile commands changed')
    binary = directory / 'own-rt-iq3'
    if sha(binary) != receipt['artifacts_sha256'][f'{kind}/own-rt-iq3']:
        raise ValueError('baseline binary changed')
    link = directory / 'CMakeFiles/own-rt-iq3.dir/link.txt'
    if sha(link) != receipt['link_files_sha256'][f'{kind}/CMakeFiles/own-rt-iq3.dir/link.txt']:
        raise ValueError('baseline link command changed')
    # The old receipt binds final executables, not individual .o files. Prove
    # these exact cached objects are the original binary's inputs by relinking
    # the unchanged parent command into packet46 and requiring identical bytes.
    proof_dir = HERE / 'build' / ('baseline-proof-' + mode)
    proof_dir.mkdir(parents=True, exist_ok=True)
    proof_binary = proof_dir / 'own-rt-iq3'
    proof_command = shlex.split(link.read_text())
    output_index = proof_command.index('-o') + 1
    proof_command[output_index] = str(proof_binary)
    with (proof_dir / 'relink.log').open('w') as log:
        subprocess.run(proof_command, cwd=directory, check=True, stdout=log, stderr=subprocess.STDOUT)
    if sha(proof_binary) != sha(binary):
        raise ValueError('cached object relink does not reproduce sealed baseline binary; source rebuild required')
    objects = []
    for token in shlex.split(link.read_text()):
        if not token.endswith('.o') or 'entry-' in token or 'own-rt-iq3-entry' in token:
            continue
        path = (directory / token).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError('missing baseline dependency object: ' + str(path))
        objects.append(path)
    if len(objects) < 20:
        raise ValueError('incomplete baseline object closure')
    compile_rows = json.loads(commands.read_text())
    compile_by_output = {(directory / row['output']).resolve(): row for row in compile_rows}
    inventory = {}
    for path in objects:
        row = compile_by_output[path]
        command = shlex.split(row['command'])
        for flag in ('-fno-fast-math', '-ffp-contract=off'):
            if flag not in command:
                raise ValueError('baseline precision flag missing')
        inventory[str(path.relative_to(ROOT))] = dict(sha256=sha(path), bytes=path.stat().st_size,
                                                     command=row['command'], source=row['file'])
    return objects, inventory, closure, {str(receipt_path.relative_to(ROOT)): sha(receipt_path),
                                        str(commands.relative_to(ROOT)): sha(commands),
                                        str(link.relative_to(ROOT)): sha(link),
                                        str(binary.relative_to(ROOT)): sha(binary),
                                        str(proof_binary.relative_to(ROOT)): sha(proof_binary)}

def run(mode):
    output = HERE / 'build' / ('host' if mode == 'host' else 'device')
    with exclusive_cpu_work(planned_write_bytes=1_000_000_000) as limits:
        mirror_hashes = validate_baseline_mirror()
        objects, inventory, closure, provenance = baseline(mode)
        output.mkdir(parents=True, exist_ok=True)
        manifest = output / 'baseline.cmake'
        manifest.write_text('set(P46_BASELINE_OBJECTS\n' + ''.join(f'  "{p}"\n' for p in objects) + ')\n')
        own_sources = ['CMakeLists.txt', 'build_layer.py', 'mirror_inputs.py', 'preparation.py', 'layer_bench.cpp',
                       'specialized.hpp', 'specialized_cpu_test.cpp', 'fixture_bytes.hpp',
                       'dispatch-baseline.json']
        closure = dict(closure, **mirror_hashes)
        closure.update({str((HERE / n).relative_to(ROOT)): sha(HERE / n) for n in own_sources})
        for source in (HERE.parent / 'packet34-replay-bench/directory.tsv', BASE / 'rope.bf16'):
            closure[str(source.relative_to(ROOT))] = sha(source)
        mirror_dir = output / 'source'
        own_mirror(mirror_dir)
        compiler = '/usr/bin/g++' if mode == 'host' else '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
        commands = [
            ['cmake', '-S', str(HERE), '-B', str(output), '-DCMAKE_CXX_COMPILER=' + compiler,
             '-DOWN_RT_HOST_ONLY=' + ('ON' if mode == 'host' else 'OFF'),
             '-DP46_BASELINE_MANIFEST=' + str(manifest), '-DP46_SOURCE_MIRROR=' + str(mirror_dir)],
            ['cmake', '--build', str(output), '--parallel', '1'],
        ]
        with (output / 'build.log').open('w') as log:
            for command in commands:
                log.write(shlex.join(command) + '\n'); log.flush()
                subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
        # Include all candidate sources and inherited source receipt. Object
        # files stay in their original tree and are opened for reading only.
        for name, digest in closure.items():
            if sha(ROOT / name) != digest: raise ValueError('source changed during build: ' + name)
        for name, row in inventory.items():
            if sha(ROOT / name) != row['sha256']: raise ValueError('object changed during build: ' + name)
        artifacts = {'layer-bench': sha(output / 'layer-bench')}
        if mode == 'host': artifacts['specialized-cpu-test'] = sha(output / 'specialized-cpu-test')
        record = dict(schema='ownrt.packet46.layer-build.v1', passed=True,
                      device_executed=False, mode=mode, limits=limits,
                      completed_utc=datetime.now(timezone.utc).isoformat(), commands=commands,
                      source_hashes=closure, baseline_provenance=provenance,
                      baseline_objects=inventory,
                      artifacts={str((output / n).relative_to(ROOT)): h for n, h in artifacts.items()},
                      compile_commands_sha256=sha(output / 'compile_commands.json'))
        (HERE / f'build-layer-{mode}.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps(dict(passed=True, mode=mode, binaries=artifacts, device_executed=False)))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--kind', choices=['host', 'device'], required=True)
    run(parser.parse_args().kind)
